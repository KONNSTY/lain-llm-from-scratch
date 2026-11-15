const net = require("net");

const MAX_RESPONSE_BYTES = 8192;

class ConfigError extends Error {}

const BLOCKED_HOSTS = new Set([
  "localhost",
  "localhost.localdomain",
  "metadata.google.internal",
  "metadata.google.com",
]);

function assertToken(token) {
  if (typeof token !== "string" || token.length < 32 || token.length > 256 || /[^\x21-\x7e]/.test(token)) {
    throw new ConfigError("Invalid API token");
  }
}

function hostnameOf(url) {
  return url.hostname.toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
}

function isNonPublicIPv4(address) {
  const parts = address.split(".").map(Number);
  if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) {
    return true;
  }
  const [a, b] = parts;
  if (a === 0 || a === 10 || a === 127) return true;
  if (a === 169 && b === 254) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  if (a === 100 && b >= 64 && b <= 127) return true;
  if (a >= 224) return true;
  return false;
}

function ipv6Value(address) {
  let text = address.toLowerCase();
  const tail = text.match(/^(.*:)(\d+\.\d+\.\d+\.\d+)$/);
  if (tail) {
    const parts = tail[2].split(".").map(Number);
    if (parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) return null;
    const high = ((parts[0] << 8) | parts[1]).toString(16);
    const low = ((parts[2] << 8) | parts[3]).toString(16);
    text = `${tail[1]}${high}:${low}`;
  }
  const halves = text.split("::");
  if (halves.length > 2) return null;
  const left = halves[0] ? halves[0].split(":") : [];
  const right = halves.length === 2 && halves[1] ? halves[1].split(":") : [];
  const missing = halves.length === 2 ? 8 - (left.length + right.length) : 0;
  if (missing < 0) return null;
  const groups = halves.length === 2 ? [...left, ...Array(missing).fill("0"), ...right] : left;
  if (groups.length !== 8) return null;
  let value = 0n;
  for (const group of groups) {
    if (!/^[0-9a-f]{1,4}$/.test(group)) return null;
    value = (value << 16n) + BigInt(parseInt(group, 16));
  }
  return value;
}

function isNonPublicIPv6(address) {
  const value = ipv6Value(address);
  if (value === null) return true;
  const documentation = 0x20010db8n;
  if ((value >> 96n) === documentation) return true;
  // Only global unicast (2000::/3). This also rejects mapped IPv4 and link-local addresses.
  return (value >> 125n) !== 1n;
}

function isBlockedHost(hostname) {
  const host = String(hostname || "").trim().toLowerCase().replace(/^\[|\]$/g, "").replace(/\.$/, "");
  if (!host || BLOCKED_HOSTS.has(host) || host.endsWith(".localhost") || host.endsWith(".local")) {
    return true;
  }
  const version = net.isIP(host);
  if (version === 4) return isNonPublicIPv4(host);
  if (version === 6) return isNonPublicIPv6(host);
  return false;
}

function upstreamEndpoint(suffix) {
  assertToken(process.env.MODEL_API_TOKEN || "");
  let base;
  try {
    base = new URL(process.env.MODEL_API_URL || "");
  } catch {
    throw new ConfigError("Invalid upstream URL");
  }
  if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash) {
    throw new ConfigError("Invalid upstream URL");
  }
  if (isBlockedHost(hostnameOf(base))) {
    throw new ConfigError("Invalid upstream URL");
  }
  const url = new URL(`${base.pathname.replace(/\/+$/, "")}${suffix}`, base.origin);
  if (url.origin !== base.origin || url.username || url.password || url.search || url.hash || url.protocol !== "https:") {
    throw new ConfigError("Invalid upstream URL");
  }
  return { url, token: process.env.MODEL_API_TOKEN };
}

function setSafeHeaders(response) {
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("X-Frame-Options", "DENY");
  response.setHeader("Referrer-Policy", "no-referrer");
}

async function readLimited(response, maxBytes = MAX_RESPONSE_BYTES) {
  const declared = Number(response.headers?.get?.("content-length"));
  if (Number.isFinite(declared) && declared > maxBytes) {
    await response.body?.cancel?.();
    throw new Error("Response too large");
  }
  if (response.body?.getReader) {
    const reader = response.body.getReader();
    const chunks = [];
    let total = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        total += value.byteLength;
        if (total > maxBytes) throw new Error("Response too large");
        chunks.push(Buffer.from(value));
      }
    } finally {
      reader.releaseLock?.();
    }
    return Buffer.concat(chunks).toString("utf8");
  }
  const text = typeof response.text === "function"
    ? await response.text()
    : JSON.stringify(await response.json());
  if (Buffer.byteLength(text) > maxBytes) throw new Error("Response too large");
  return text;
}

module.exports = {
  ConfigError,
  MAX_RESPONSE_BYTES,
  isBlockedHost,
  readLimited,
  setSafeHeaders,
  upstreamEndpoint,
};
