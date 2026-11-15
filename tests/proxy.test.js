const { describe, test } = require("node:test");
const assert = require("node:assert/strict");
const handler = require("../api/generate.js");
const { isBlockedHost } = require("../lib/upstream");

process.env.MODEL_API_URL = "https://api.example.com";
process.env.MODEL_API_TOKEN = "x".repeat(64);

function makeResponse() {
  return {
    code: 200,
    headers: {},
    setHeader(key, value) { this.headers[key] = value; },
    status(code) { this.code = code; return this; },
    json(data) { this.body = data; return this; },
  };
}

function jsonResult(payload, status = 200) {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => payload,
  };
}

describe("generate proxy", { concurrency: false }, () => {
  test("rejects invalid browser requests before contacting the VPS", async () => {
    global.fetch = () => { throw new Error("unexpected upstream call"); };
    const cases = [
      [{ method: "GET", headers: {} }, 405],
      [{ method: "POST", headers: { "content-type": "text/plain" }, body: {} }, 415],
      [{ method: "POST", headers: { "content-type": "application/jsonx" }, body: { prompt: "hi" } }, 415],
      [{ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: " " } }, 400],
      [{ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: "hi", max_tokens: 999 } }, 400],
      [{ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: "hi", extra: true } }, 400],
      [{ method: "POST", headers: { "content-type": "application/json", "content-length": "nope" }, body: { prompt: "hi" } }, 400],
      [{ method: "POST", headers: { "content-type": "application/json", "content-length": "5000" }, body: { prompt: "hi" } }, 413],
    ];
    for (const [request, expected] of cases) {
      const response = makeResponse();
      await handler(request, response);
      assert.equal(response.code, expected);
    }
  });

  test("forwards a valid request with the secret only on the server side", async () => {
    let forwarded;
    global.fetch = async (url, options) => {
      forwarded = { url: url.toString(), options };
      return jsonResult({ completion: "hello" });
    };
    const response = makeResponse();
    await handler({
      method: "POST",
      headers: { "content-type": "application/json; charset=utf-8" },
      body: { prompt: " who are " },
    }, response);
    assert.equal(response.code, 200);
    assert.deepEqual(response.body, { completion: "hello" });
    assert.equal(forwarded.url, "https://api.example.com/api/generate");
    assert.equal(forwarded.options.headers.Authorization, `Bearer ${process.env.MODEL_API_TOKEN}`);
    assert.equal(forwarded.options.redirect, "error");
    assert.deepEqual(JSON.parse(forwarded.options.body), { prompt: "who are", max_tokens: 15 });
    assert.equal(response.headers["Cache-Control"], "no-store");
    assert.equal(response.headers["X-Content-Type-Options"], "nosniff");
  });

  test("accepts a JSON string body", async () => {
    global.fetch = async () => jsonResult({ completion: "hello" });
    const response = makeResponse();
    await handler({
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt: "hi", max_tokens: 4 }),
    }, response);
    assert.equal(response.code, 200);
    assert.deepEqual(response.body, { completion: "hello" });
  });

  test("does not expose upstream errors or oversized completions", async () => {
    global.fetch = async () => { throw new Error("private internal detail"); };
    const failed = makeResponse();
    await handler({ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: "hi" } }, failed);
    assert.equal(failed.code, 502);
    assert.ok(!JSON.stringify(failed.body).includes("private internal detail"));

    global.fetch = async () => jsonResult({ completion: "z".repeat(5000) });
    const oversized = makeResponse();
    await handler({ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: "hi" } }, oversized);
    assert.equal(oversized.code, 502);
    assert.ok(!JSON.stringify(oversized.body).includes("zzzz"));
  });

  test("supports a dedicated API path on an existing HTTPS host", async () => {
    process.env.MODEL_API_URL = "https://api.example.com/lain";
    let target;
    global.fetch = async (url) => {
      target = url.toString();
      return jsonResult({ completion: "hello" });
    };
    const response = makeResponse();
    await handler({ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: "hi" } }, response);
    assert.equal(target, "https://api.example.com/lain/api/generate");
    assert.equal(response.code, 200);
    process.env.MODEL_API_URL = "https://api.example.com";
  });

  test("rejects unsafe upstream configuration without calling it", async () => {
    const originalUrl = process.env.MODEL_API_URL;
    const originalToken = process.env.MODEL_API_TOKEN;
    global.fetch = () => { throw new Error("unexpected upstream call"); };
    const blocked = [
      "http://api.example.com",
      "https://user:pass@api.example.com",
      "https://api.example.com/path?x=1",
      "https://127.0.0.1",
      "https://2130706433",
      "https://169.254.169.254",
      "https://[::1]",
      "https://[::ffff:127.0.0.1]",
      "https://localhost",
      "https://metadata.google.internal",
    ];
    for (const url of blocked) {
      process.env.MODEL_API_URL = url;
      process.env.MODEL_API_TOKEN = "x".repeat(64);
      const response = makeResponse();
      await handler({ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: "hi" } }, response);
      assert.equal(response.code, 503, url);
      assert.deepEqual(response.body, { error: "Model not configured" });
      assert.ok(!JSON.stringify(response.body).includes("example"));
    }
    process.env.MODEL_API_URL = originalUrl;
    process.env.MODEL_API_TOKEN = "bad token\r\nX-Injected: 1";
    const injected = makeResponse();
    await handler({ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: "hi" } }, injected);
    assert.equal(injected.code, 503);
    process.env.MODEL_API_TOKEN = originalToken;
  });

  test("blocks non-public addresses and allows a public address", () => {
    assert.equal(isBlockedHost("127.0.0.1"), true);
    assert.equal(isBlockedHost("[::1]"), true);
    assert.equal(isBlockedHost("::ffff:7f00:1"), true);
    assert.equal(isBlockedHost("2001:db8::1"), true);
    assert.equal(isBlockedHost("8.8.8.8"), false);
    assert.equal(isBlockedHost("2001:4860:4860::8888"), false);
    assert.equal(isBlockedHost("api.example.com"), false);
  });
});
