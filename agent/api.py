"""FastAPI wrapper over core.answer().

    uvicorn agent.api:app --reload

POST /ask  {"query": "..."}  ->  {"kind", "target", "answer"}
GET  /healthz                ->  {"status": "ok"}
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .core import answer

app = FastAPI(title="Coffee Recipe Lookup Agent", version="1.0.0")

# CORS: permissive by default for local dev; set ALLOWED_ORIGINS (comma-separated)
# to the deployed frontend origin(s) in production (e.g. the Vercel URL).
_origins = os.environ.get("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    query: str


class AskResponse(BaseModel):
    kind: str
    target: str | None
    answer: str


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> dict:
    return answer(request.query)
