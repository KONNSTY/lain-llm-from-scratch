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
            [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", str(cls.port)],
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
        for payload in ({"prompt": " "}, {"prompt": "hi", "max_tokens": 1000000}, {"prompt": "x", "unexpected": 1}):
            self.assertEqual(self.post(payload, TOKEN)[0], 422)

    def test_docs_disabled(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/docs", timeout=2)
        self.assertEqual(raised.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
