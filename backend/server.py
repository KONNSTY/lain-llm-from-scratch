"""Private model API. Run behind an HTTPS reverse proxy on the VPS."""

import os
import secrets
import time
from collections import deque
from contextlib import asynccontextmanager
from threading import Lock, Semaphore
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from model import SimpleLLM, load_corpus

RATE_LIMIT = 120
RATE_WINDOW_SECONDS = 60
_requests = deque()
_rate_lock = Lock()
_slots = Semaphore(4)


@asynccontextmanager
async def lifespan(app: FastAPI):
    token = os.environ.get("MODEL_API_TOKEN", "")
    if len(token) < 32:
        raise RuntimeError("MODEL_API_TOKEN must contain at least 32 characters")
    model = SimpleLLM(max_context=7)
    model.train(load_corpus())
    app.state.model = model
    app.state.token = token
    yield


app = FastAPI(
    title="Lain model API",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=1000)
    max_tokens: int = Field(default=25, ge=1, le=100, strict=True)
    temperature: float = Field(default=0.7, ge=0.1, le=2.0)

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt must not be blank")
        return value


def require_token(request: Request, authorization: Optional[str] = Header(default=None)):
    expected = request.app.state.token
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if (not authorization or not authorization.startswith("Bearer ") or
            len(supplied) != len(expected) or not secrets.compare_digest(supplied, expected)):
        raise HTTPException(status_code=401, detail="Unauthorized")


def check_capacity():
    now = time.monotonic()
    with _rate_lock:
        while _requests and _requests[0] <= now - RATE_WINDOW_SECONDS:
            _requests.popleft()
        if len(_requests) >= RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Too many requests", headers={"Retry-After": "60"})
        _requests.append(now)
    if not _slots.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="Model busy", headers={"Retry-After": "2"})


@app.post("/api/generate", dependencies=[Depends(require_token)])
def generate_text_endpoint(payload: GenerateRequest):
    check_capacity()
    try:
        return {
            "completion": app.state.model.generate(
                payload.prompt,
                max_tokens=payload.max_tokens,
                temperature=payload.temperature
            )
        }
    finally:
        _slots.release()


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080, proxy_headers=False)
