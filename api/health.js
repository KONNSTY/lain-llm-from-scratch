const { setSafeHeaders, upstreamEndpoint } = require("../lib/upstream");

module.exports = async function handler(request, response) {
  setSafeHeaders(response);
  if (request.method !== "GET") {
    response.setHeader("Allow", "GET");
    return response.status(405).json({ status: "unavailable" });
  }
  try {
    const upstream = upstreamEndpoint("/health");
    const result = await fetch(upstream.url, {
      method: "GET",
      redirect: "error",
      signal: AbortSignal.timeout(5000),
      cache: "no-store",
    });
    await result.body?.cancel?.();
    if (!result.ok) throw new Error("Unhealthy");
    return response.status(200).json({ status: "ok" });
  } catch {
    return response.status(503).json({ status: "unavailable" });
  }
};
