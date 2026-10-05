const MAX_BODY_BYTES = 4096;

module.exports = async function handler(request, response) {
  response.setHeader("Cache-Control", "no-store");
  response.setHeader("X-Content-Type-Options", "nosniff");

  if (request.method !== "POST") {
    response.setHeader("Allow", "POST");
    return response.status(405).json({ error: "Method not allowed" });
  }
  if (!request.headers["content-type"]?.startsWith("application/json")) {
    return response.status(415).json({ error: "JSON required" });
  }
  if (Number(request.headers["content-length"] || 0) > MAX_BODY_BYTES) {
    return response.status(413).json({ error: "Request too large" });
  }

  const body = request.body;
  if (!body || typeof body !== "object" || Array.isArray(body) ||
      Object.keys(body).some((key) => !["prompt", "max_tokens"].includes(key)) ||
      typeof body.prompt !== "string" || !body.prompt.trim() || body.prompt.length > 1000 ||
      (body.max_tokens !== undefined && (!Number.isInteger(body.max_tokens) || body.max_tokens < 1 || body.max_tokens > 60)) ||
      Buffer.byteLength(JSON.stringify(body), "utf8") > MAX_BODY_BYTES) {
    return response.status(400).json({ error: "Invalid request" });
  }

  let upstream;
  try {
    const base = new URL(process.env.MODEL_API_URL);
    if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash) {
      throw new Error("Invalid upstream URL");
    }
    if (!process.env.MODEL_API_TOKEN || process.env.MODEL_API_TOKEN.length < 32) {
      throw new Error("Missing API token");
    }
    upstream = new URL(base.pathname.replace(/\/$/, "") + "/api/generate", base.origin);
  } catch {
    return response.status(503).json({ error: "Model not configured" });
  }

  try {
    const result = await fetch(upstream, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${process.env.MODEL_API_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt: body.prompt.trim(), max_tokens: body.max_tokens ?? 15 }),
      signal: AbortSignal.timeout(15000),
      cache: "no-store",
    });
    if (result.status === 429 || result.status === 503) {
      return response.status(result.status).json({ error: "Model busy" });
    }
    if (!result.ok) throw new Error("Upstream failure");
    const data = await result.json();
    if (typeof data.completion !== "string") throw new Error("Invalid upstream response");
    return response.status(200).json({ completion: data.completion });
  } catch {
    return response.status(502).json({ error: "Model unavailable" });
  }
};
