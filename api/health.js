module.exports = async function handler(request, response) {
  response.setHeader("Cache-Control", "no-store");
  if (request.method !== "GET") {
    response.setHeader("Allow", "GET");
    return response.status(405).json({ status: "unavailable" });
  }
  try {
    const base = new URL(process.env.MODEL_API_URL);
    if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash) {
      throw new Error("Invalid upstream URL");
    }
    const result = await fetch(new URL(base.pathname.replace(/\/$/, "") + "/health", base.origin), {
      signal: AbortSignal.timeout(5000),
      cache: "no-store",
    });
    if (!result.ok) {
      if (result.status === 404 && base.pathname !== "/") {
        const direct = await fetch(new URL("/health", base.origin), {
          signal: AbortSignal.timeout(5000),
          cache: "no-store",
        });
        console.error(`Prefixed health returned HTTP 404; root health returned HTTP ${direct.status}`);
      }
      throw new Error(`Upstream health returned HTTP ${result.status}`);
    }
    return response.status(200).json({ status: "ok" });
  } catch (error) {
    console.error("Model health check failed:", error.message, error.cause?.code || "");
    return response.status(503).json({ status: "unavailable" });
  }
};
