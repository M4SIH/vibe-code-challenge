"""Runtime configuration, read from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

CATEGORIES: tuple[str, ...] = (
    "delivery",
    "payment",
    "refund",
    "product_quality",
    "account",
    "other",
)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"


@dataclass(frozen=True)
class Settings:
    urgent_sla_business_hours: float
    llm_base_url: str | None
    llm_api_key: str | None
    llm_model: str
    llm_timeout_seconds: float
    # Classification batching / pacing (Groq free tier: 8000 tokens per minute).
    llm_batch_size: int = 20
    llm_tokens_per_minute: int = 7000
    llm_max_wait_seconds: float = 90.0
    # Stop calling the LLM after this many seconds and use keywords for the rest
    # (None = no limit; the API sets one so an upload never hangs).
    llm_classify_budget_seconds: float | None = None
    llm_cache_dir: Path = DEFAULT_CACHE_DIR
    llm_draft_timeout_seconds: float = 20.0


def _optional(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def _float(name: str, default: float | None) -> float | None:
    value = _optional(name)
    return float(value) if value is not None else default


def get_settings() -> Settings:
    return Settings(
        urgent_sla_business_hours=float(os.environ.get("URGENT_SLA_BUSINESS_HOURS", "2")),
        llm_base_url=_optional("LLM_BASE_URL"),
        llm_api_key=_optional("LLM_API_KEY"),
        # default = the model the shipped cache (backend/.cache/classify-v3.json) was built with
        llm_model=os.environ.get("LLM_MODEL", "").strip() or "openai/gpt-oss-120b",
        llm_timeout_seconds=float(os.environ.get("LLM_TIMEOUT_SECONDS", "60")),
        llm_batch_size=int(os.environ.get("LLM_BATCH_SIZE", "20")),
        llm_tokens_per_minute=int(os.environ.get("LLM_TOKENS_PER_MINUTE", "7000")),
        llm_max_wait_seconds=float(os.environ.get("LLM_MAX_WAIT_SECONDS", "90")),
        llm_classify_budget_seconds=_float("LLM_CLASSIFY_BUDGET_SECONDS", None),
        llm_cache_dir=Path(_optional("LLM_CACHE_DIR") or DEFAULT_CACHE_DIR),
        llm_draft_timeout_seconds=float(os.environ.get("LLM_DRAFT_TIMEOUT_SECONDS", "20")),
    )
