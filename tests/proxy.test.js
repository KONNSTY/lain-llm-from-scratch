const { test } = require("node:test");
const assert = require("node:assert/strict");
const handler = require("../api/generate.js");

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

test("rejects invalid browser requests before contacting the VPS", async () => {
  global.fetch = () => { throw new Error("unexpected upstream call"); };
  for (const [request, expected] of [
    [{ method: "GET", headers: {} }, 405],
    [{ method: "POST", headers: { "content-type": "text/plain" }, body: {} }, 415],
    [{ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: " " } }, 400],
    [{ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: "hi", max_tokens: 999 } }, 400],
  ]) {
    const response = makeResponse();
    await handler(request, response);
    assert.equal(response.code, expected);
  }
});

test("forwards a valid request with the secret only on the server side", async () => {
  let forwarded;
  global.fetch = async (url, options) => {
    forwarded = { url: url.toString(), options };
    return { ok: true, json: async () => ({ completion: "hello" }) };
  };
  const response = makeResponse();
  await handler({
    method: "POST",
    headers: { "content-type": "application/json" },
    body: { prompt: " who are " },
  }, response);
  assert.equal(response.code, 200);
  assert.deepEqual(response.body, { completion: "hello" });
  assert.equal(forwarded.url, "https://api.example.com/api/generate");
  assert.equal(forwarded.options.headers.Authorization, `Bearer ${process.env.MODEL_API_TOKEN}`);
  assert.deepEqual(JSON.parse(forwarded.options.body), { prompt: "who are", max_tokens: 15 });
  assert.equal(response.headers["Cache-Control"], "no-store");
});

test("does not expose upstream errors", async () => {
  global.fetch = async () => { throw new Error("private internal detail"); };
  const response = makeResponse();
  await handler({ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: "hi" } }, response);
  assert.equal(response.code, 502);
  assert.ok(!JSON.stringify(response.body).includes("private internal detail"));
});

test("supports a dedicated API path on an existing HTTPS host", async () => {
  process.env.MODEL_API_URL = "https://api.example.com/lain";
  let target;
  global.fetch = async (url) => {
    target = url.toString();
    return { ok: true, json: async () => ({ completion: "hello" }) };
  };
  const response = makeResponse();
  await handler({ method: "POST", headers: { "content-type": "application/json" }, body: { prompt: "hi" } }, response);
  assert.equal(target, "https://api.example.com/lain/api/generate");
  assert.equal(response.code, 200);
  process.env.MODEL_API_URL = "https://api.example.com";
});
