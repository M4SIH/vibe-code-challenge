"""HTTP API used by the dashboard frontend."""
from __future__ import annotations

import dataclasses
import io
from typing import Any

from pydantic import BaseModel, Field
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .analysis import analyze, parse_now
from .config import get_settings
from .drafts import generate

app = FastAPI(title="Bazarcheh Support Triage", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze_upload(
    file: UploadFile = File(...),
    now: str | None = Query(default=None, description="ISO-8601 UTC timestamp"),
) -> dict[str, Any]:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="uploaded file is empty")
    try:
        reference_time = parse_now(now)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid 'now': {exc}") from exc
    try:
        settings = get_settings()
        # An upload must never hang on the LLM quota: after this budget, the
        # remaining messages get keyword labels (the CLI has no budget).
        settings = dataclasses.replace(
            settings, llm_classify_budget_seconds=settings.llm_classify_budget_seconds or 40.0)
        return analyze(io.BytesIO(content), now=reference_time, settings=settings,
                       include_details=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class DraftRequest(BaseModel):
    message_id: str = Field(min_length=1, max_length=200)
    customer_id: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default="", max_length=20_000)
    body: str | None = Field(default="", max_length=20_000)


@app.post("/api/draft")
def draft_reply(req: DraftRequest) -> dict[str, Any]:
    """Generated only on click; always 200 (blocked=true when no safe draft)."""
    return generate(req.message_id, req.subject or "", req.body or "")
