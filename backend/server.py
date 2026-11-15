"""Private model API. Run behind an HTTPS reverse proxy on the VPS."""

import hashlib
import hmac
import json
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from threading import Lock, Semaphore
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from model import SimpleLLM, load_corpus

MAX_BODY_BYTES = 8192
MAX_COMPLETION_CHARS = 4000
MAX_TOKEN_LENGTH = 256
RATE_WINDOW_SECONDS = 60
_requests = deque()
_rate_lock = Lock()
_slots = Semaphore(4)


def _bounded_int(name, default, low, high):
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    if not raw.isdigit():
        raise RuntimeError(f"{name} must be an integer")
    value = int(raw)
    if not low <= value <= high:
        raise RuntimeError(f"{name} is out of range")
    return value


RATE_LIMIT = _bounded_int("MODEL_RATE_LIMIT", 120, 1, 10_000)


def _valid_token(value):
    return 32 <= len(value) <= MAX_TOKEN_LENGTH and all(33 <= ord(char) <= 126 for char in value)


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            length = _content_length(scope)
        except ValueError:
            await _send_json(send, 400, {"detail": "Invalid request"})
            return
        if length is not None and length > MAX_BODY_BYTES:
            await _send_json(send, 413, {"detail": "Request too large"})
            return
        if scope.get("method") in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return

        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            piece = message.get("body", b"")
            size += len(piece)
            if size > MAX_BODY_BYTES:
                await _send_json(send, 413, {"detail": "Request too large"})
                return
            chunks.append(piece)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


class SecurityHeadersMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() not in _SECURITY_HEADER_NAMES
                ]
                headers.extend(_SECURITY_HEADERS)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _content_length(scope):
    values = [value for name, value in scope.get("headers", []) if name == b"content-length"]
    if not values:
        return None
    if len(values) != 1 or not values[0].isdigit():
        raise ValueError("invalid content length")
    return int(values[0])


async def _send_json(send, status, payload):
    body = json.dumps(payload).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": body})


_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cache-control", b"no-store"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
]
_SECURITY_HEADER_NAMES = {key for key, _value in _SECURITY_HEADERS}


@asynccontextmanager
async def lifespan(app: FastAPI):
    token = os.environ.get("MODEL_API_TOKEN", "")
    if not _valid_token(token):
        raise RuntimeError("MODEL_API_TOKEN must be 32 to 256 visible ASCII characters")
    model = SimpleLLM(max_context=7)
    model.train(load_corpus())
    app.state.model = model
    app.state.token_hash = hashlib.sha256(token.encode("utf-8")).digest()
    yield


app = FastAPI(
    title="Lain model API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    redirect_slashes=False,
)
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=1000)
    max_tokens: int = Field(default=25, ge=1, le=100, strict=True)
    temperature: float = Field(default=0.7, ge=0.1, le=2.0, strict=True)

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt must not be blank")
        return value


def require_token(request: Request, authorization: Optional[str] = Header(default=None)):
    if authorization is None or len(authorization) > MAX_TOKEN_LENGTH + len("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    scheme, separator, supplied = authorization.partition(" ")
    if scheme != "Bearer" or separator != " " or not _valid_token(supplied):
        raise HTTPException(status_code=401, detail="Unauthorized")
    supplied_hash = hashlib.sha256(supplied.encode("utf-8")).digest()
    if not hmac.compare_digest(supplied_hash, request.app.state.token_hash):
        raise HTTPException(status_code=401, detail="Unauthorized")


def reserve_capacity():
    if not _slots.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="Model busy", headers={"Retry-After": "2"})
    try:
        now = time.monotonic()
        with _rate_lock:
            while _requests and _requests[0] <= now - RATE_WINDOW_SECONDS:
                _requests.popleft()
            if len(_requests) >= RATE_LIMIT:
                raise HTTPException(
                    status_code=429, detail="Too many requests", headers={"Retry-After": "60"}
                )
            _requests.append(now)
    except Exception:
        _slots.release()
        raise


@app.post("/api/generate", dependencies=[Depends(require_token)])
def generate_text_endpoint(payload: GenerateRequest):
    reserve_capacity()
    try:
        completion = app.state.model.generate(
            payload.prompt,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
        )
        if not isinstance(completion, str) or len(completion) > MAX_COMPLETION_CHARS:
            raise HTTPException(status_code=502, detail="Model unavailable")
        return {"completion": completion}
    finally:
        _slots.release()


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8080,
        proxy_headers=False,
        server_header=False,
    )
