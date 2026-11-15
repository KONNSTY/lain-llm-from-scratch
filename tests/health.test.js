const { describe, test } = require("node:test");
const assert = require("node:assert/strict");
const handler = require("../api/health.js");

process.env.MODEL_API_URL = "https://api.example.com";
process.env.MODEL_API_TOKEN = "y".repeat(64);

function makeResponse() {
  return {
    code: 200,
    headers: {},
    ended: false,
    setHeader(key, value) { this.headers[key] = value; },
    status(code) { this.code = code; return this; },
    json(data) { this.body = data; return this; },
    end() { this.ended = true; return this; },
  };
}

describe("health proxy", { concurrency: false }, () => {
  test("reports upstream health without sending the API token", async () => {
    let forwarded;
    global.fetch = async (url, options) => {
      forwarded = { url: url.toString(), options };
      return { ok: true, status: 200, body: { cancel: async () => {} } };
    };
    const response = makeResponse();
    await handler({ method: "GET", headers: {} }, response);
    assert.equal(response.code, 200);
    assert.deepEqual(response.body, { status: "ok" });
    assert.equal(forwarded.url, "https://api.example.com/health");
    assert.equal(forwarded.options.redirect, "error");
    assert.equal(forwarded.options.headers, undefined);
    assert.equal(response.headers["X-Content-Type-Options"], "nosniff");
    assert.equal(response.headers["Cache-Control"], "no-store");
  });

  test("hides upstream failures and rejects other methods", async () => {
    global.fetch = async () => { throw new Error("private upstream detail"); };
    const failed = makeResponse();
    await handler({ method: "GET", headers: {} }, failed);
    assert.equal(failed.code, 503);
    assert.ok(!JSON.stringify(failed.body).includes("private upstream detail"));

    const denied = makeResponse();
    await handler({ method: "POST", headers: {} }, denied);
    assert.equal(denied.code, 405);
    assert.equal(denied.headers.Allow, "GET");
  });

  test("does not call a non-https upstream", async () => {
    process.env.MODEL_API_URL = "http://api.example.com";
    global.fetch = () => { throw new Error("unexpected upstream call"); };
    const response = makeResponse();
    await handler({ method: "GET", headers: {} }, response);
    assert.equal(response.code, 503);
    process.env.MODEL_API_URL = "https://api.example.com";
  });
});
