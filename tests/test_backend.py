"""Exercise the real ASGI server over loopback, including authentication."""

import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
TOKEN = "test-token-" + "x" * 48


class BackendHTTPTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        env = dict(os.environ, MODEL_API_TOKEN=TOKEN)
        cls.process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "server:app",
                "--host", "127.0.0.1", "--port", str(cls.port),
                "--no-proxy-headers", "--no-server-header",
            ],
            cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/health", timeout=1) as res:
                    if res.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        cls.process.terminate()
        raise RuntimeError("backend did not become healthy")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)

    def post(self, payload, token=None):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/generate",
            data=json.dumps(payload).encode(), headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as res:
                return res.status, json.load(res), res.headers
        except urllib.error.HTTPError as err:
            return err.code, json.load(err), err.headers

    def test_requires_token(self):
        self.assertEqual(self.post({"prompt": "who are"})[0], 401)
        self.assertEqual(self.post({"prompt": "who are"}, "wrong-token")[0], 401)

    def test_generation_and_validation(self):
        status, body, headers = self.post({"prompt": "who are", "max_tokens": 5}, TOKEN)
        self.assertEqual(status, 200)
        self.assertIsInstance(body["completion"], str)
        self.assertNotIn("access-control-allow-origin", headers)
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertIsNone(headers.get("server"))
        for payload in (
            {"prompt": " "},
            {"prompt": "hi", "max_tokens": 1000000},
            {"prompt": "x", "unexpected": 1},
            {"prompt": "hi", "temperature": True},
            {"prompt": "hi", "temperature": "1"},
        ):
            self.assertEqual(self.post(payload, TOKEN)[0], 422)

    def test_rejects_oversized_and_malformed_requests(self):
        self.assertEqual(self.post({"prompt": "hi"}, "z" * 5000)[0], 401)
        status, _body, headers = self.raw_request(
            b"POST /api/generate HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: nope\r\n"
            + b"Authorization: Bearer " + TOKEN.encode() + b"\r\n"
            b"Connection: close\r\n\r\n"
            b"{}"
        )
        self.assertEqual(status, 400)

        payload = b'{"prompt":"' + (b"a" * 9000) + b'"}'
        status, body, _headers = self.raw_request(
            b"POST /api/generate HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(payload)}\r\n".encode()
            + b"Authorization: Bearer " + TOKEN.encode() + b"\r\n"
            b"Connection: close\r\n\r\n"
            + payload
        )
        self.assertEqual(status, 413)
        self.assertNotIn(b"a" * 100, body)

    def raw_request(self, raw):
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
            sock.sendall(raw)
            data = b""
            while True:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                data += chunk
        head, _, body = data.partition(b"\r\n\r\n")
        status = int(head.split()[1])
        return status, body, head

    def test_docs_disabled(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/docs", timeout=2)
        self.assertEqual(raised.exception.code, 404)


class RateLimitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        env = dict(os.environ, MODEL_API_TOKEN=TOKEN, MODEL_RATE_LIMIT="2")
        cls.process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "server:app",
                "--host", "127.0.0.1", "--port", str(cls.port),
                "--no-proxy-headers", "--no-server-header",
            ],
            cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/health", timeout=1) as res:
                    if res.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        stderr = cls.process.stderr.read().decode("utf-8", "replace")
        cls.process.terminate()
        raise RuntimeError("rate-limited backend did not become healthy\n" + stderr)

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=5)

    def test_rate_limit_then_still_rejects_without_leaking_capacity(self):
        def post():
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/api/generate",
                data=json.dumps({"prompt": "hi", "max_tokens": 1}).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOKEN},
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as res:
                    return res.status, res.headers.get("Retry-After")
            except urllib.error.HTTPError as err:
                return err.code, err.headers.get("Retry-After")

        self.assertEqual(post()[0], 200)
        self.assertEqual(post()[0], 200)
        status, retry_after = post()
        self.assertEqual(status, 429)
        self.assertEqual(retry_after, "60")
        self.assertEqual(post()[0], 429)


if __name__ == "__main__":
    unittest.main()
