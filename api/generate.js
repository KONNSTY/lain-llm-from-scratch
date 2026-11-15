const { MAX_RESPONSE_BYTES, readLimited, setSafeHeaders, upstreamEndpoint } = require("../lib/upstream");

const MAX_BODY_BYTES = 4096;
const MAX_COMPLETION_CHARS = 4000;

function isJsonRequest(header) {
  if (typeof header !== "string") return false;
  return header.split(";", 1)[0].trim().toLowerCase() === "application/json";
}

function contentLength(headers) {
  const raw = headers["content-length"];
  if (raw === undefined) return 0;
  if (typeof raw !== "string" || !/^\d+$/.test(raw)) return null;
  const value = Number(raw);
  return Number.isSafeInteger(value) ? value : null;
}

function parseBody(body) {
  if (typeof body === "string") {
    try {
      return JSON.parse(body);
    } catch {
      return null;
    }
  }
  return body;
}

function invalidRequest(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return true;
  if (Object.keys(body).some((key) => key !== "prompt" && key !== "max_tokens")) return true;
  if (typeof body.prompt !== "string" || !body.prompt.trim() || body.prompt.length > 1000) return true;
  if (body.max_tokens !== undefined && (!Number.isInteger(body.max_tokens) || body.max_tokens < 1 || body.max_tokens > 60)) {
    return true;
  }
  return Buffer.byteLength(JSON.stringify(body), "utf8") > MAX_BODY_BYTES;
}

module.exports = async function handler(request, response) {
  setSafeHeaders(response);

  if (request.method !== "POST") {
    response.setHeader("Allow", "POST");
    return response.status(405).json({ error: "Method not allowed" });
  }
  if (!isJsonRequest(request.headers["content-type"])) {
    return response.status(415).json({ error: "JSON required" });
  }
  const length = contentLength(request.headers);
  if (length === null) return response.status(400).json({ error: "Invalid request" });
  if (length > MAX_BODY_BYTES) return response.status(413).json({ error: "Request too large" });

  const body = parseBody(request.body);
  if (invalidRequest(body)) return response.status(400).json({ error: "Invalid request" });

  let upstream;
  try {
    upstream = upstreamEndpoint("/api/generate");
  } catch {
    return response.status(503).json({ error: "Model not configured" });
  }

  try {
    const result = await fetch(upstream.url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${upstream.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt: body.prompt.trim(), max_tokens: body.max_tokens ?? 15 }),
      redirect: "error",
      signal: AbortSignal.timeout(15000),
      cache: "no-store",
    });
    if (!result.ok) {
      await result.body?.cancel?.();
      if (result.status === 429 || result.status === 503) {
        return response.status(result.status).json({ error: "Model busy" });
      }
      throw new Error("Upstream failure");
    }
    const raw = await readLimited(result, MAX_RESPONSE_BYTES);
    const data = JSON.parse(raw);
    if (typeof data.completion !== "string" || data.completion.length > MAX_COMPLETION_CHARS) {
      throw new Error("Invalid upstream response");
    }
    return response.status(200).json({ completion: data.completion });
  } catch {
    return response.status(502).json({ error: "Model unavailable" });
  }
};
