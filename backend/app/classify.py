"""Category + high-severity classification.

LLM when configured (batched, paced, cached on disk); keyword rules for every
message the LLM could not label (not configured, error, quota, time budget).

High severity is "keyword rules OR LLM". On the full exports the LLM drifted on
borderline cases between prompt versions (wallet top-ups, delays), while the
keyword rules encode the agreed definition but cannot read unfamiliar wording
or negation. Their misses are different, and a missed emergency costs more than
a false alarm in the attention list, so either source is enough.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .config import Settings
from .llm import (PROMPT_VERSION, DiskCache, LLMClient, LLMUnavailable, MessageToClassify,
                  classification_key)
from .severity import is_high_severity_keywords
from .textnorm import normalize_text

KEYWORDS: dict[str, tuple[str, ...]] = {
    "refund": (
        "refund", "money back", "bargasht", "pas bedid",
        "مرجوع", "بازگشت وجه", "برگشت پول", "پول برنگشته", "استرداد", "عودت",
    ),
    "payment": (
        "payment", "paid", "charged", "card", "wallet", "invoice", "factor", "pardakht",
        "پرداخت", "برداشت", "کارت", "کیف پول", "فاکتور", "تراکنش", "درگاه",
    ),
    "delivery": (
        "delivery", "deliver", "arrive", "arrived", "shipping", "courier", "tracking", "package", "parcel",
        "tahvil", "ersal", "post",
        "ارسال", "تحویل", "مرسوله", "پیک", "بسته", "پست", "کد رهگیری",
    ),
    "product_quality": (
        "broken", "damaged", "defective", "quality", "fake", "not working", "wrong item",
        "different item", "manual", "install", "colour", "color", "kharab", "rang", "taviz",
        "خراب", "شکسته", "کیفیت", "معیوب", "تقلبی", "کار نمی", "رنگ", "لک", "راهنما",
        "نصب", "مشخصات", "تعویض", "بو ",
    ),
    "account": (
        "account", "password", "login", "log in", "sign in", "otp", "hesab", "ramz",
        "حساب", "رمز", "ورود", "پسورد", "کد تایید", "شماره موبایل",
    ),
}

CATEGORY_ORDER: tuple[str, ...] = ("refund", "payment", "account", "product_quality", "delivery")
# Keywords are matched against normalize_text() output, so normalise them the same way.
_NORMALIZED_KEYWORDS = {
    cat: tuple(normalize_text(w) + (" " if w.endswith(" ") else "") for w in words)
    for cat, words in KEYWORDS.items()
}


@dataclass(frozen=True)
class Label:
    category: str
    high_severity: bool
    source: str = "keywords"  # "llm" or "keywords"


@dataclass
class ClassificationRun:
    labels: list[Label]
    stats: dict[str, Any] = field(default_factory=dict)


def classify_keywords(subject: str, body: str) -> str:
    text = normalize_text(f"{subject} {body}") + " "
    for category in CATEGORY_ORDER:
        if any(word in text for word in _NORMALIZED_KEYWORDS[category]):
            return category
    return "other"


def label_keywords(subject: str, body: str) -> Label:
    return Label(classify_keywords(subject, body), is_high_severity_keywords(subject, body))


def classify_messages(df: pd.DataFrame, settings: Settings, client: LLMClient | None = None
                      ) -> ClassificationRun:
    """Return a Label per row of ``df`` (in order) plus run statistics."""
    fallback = [label_keywords(s, b) for s, b in zip(df["subject"], df["body"])]
    cache = DiskCache(settings.llm_cache_dir / f"{PROMPT_VERSION}.json")
    keys = [classification_key(settings.llm_model, s, b) for s, b in zip(df["subject"], df["body"])]
    if not settings.llm_base_url:
        # No LLM configured: answers already in the cache (shipped with the repo for the
        # sample/eval exports) are still used, so results reproduce without an API key.
        labels = [Label(h["category"], bool(h["high"]) or fb.high_severity, "llm") if (h := cache.get(k)) else fb
                  for k, fb in zip(keys, fallback)]
        cached = sum(lab.source == "llm" for lab in labels)
        return ClassificationRun(labels, {"mode": "cache+keywords" if cached else "keywords",
                                          "llm_labels": cached, "keyword_labels": len(labels) - cached,
                                          "served_from_cache": cached, "llm_requests": 0})

    pending: dict[str, MessageToClassify] = {}
    for key, mid, s, b in zip(keys, df["message_id"], df["subject"], df["body"]):
        if cache.get(key) is None and key not in pending:
            pending[key] = MessageToClassify(mid, s, b)
    cached_before = sum(cache.get(k) is not None for k in keys)

    error: str | None = None
    own_client = client is None
    requests = 0
    if pending:
        try:
            client = client or LLMClient(settings)
            budget = settings.llm_classify_budget_seconds
            deadline = client.clock() + budget if budget else None
            todo = list(pending.items())
            size = max(1, settings.llm_batch_size)
            for start in range(0, len(todo), size):
                chunk = todo[start:start + size]
                results = client.classify_batch([m for _, m in chunk], deadline)
                cache.set_many({k: {"category": r.category, "high": r.high_severity}
                                for (k, _), r in zip(chunk, results) if r is not None})
        except LLMUnavailable as exc:
            error = str(exc)
        finally:
            if client is not None:
                requests = client.requests_made
                if own_client:
                    client.close()

    labels: list[Label] = []
    for key, fb in zip(keys, fallback):
        hit = cache.get(key)
        labels.append(Label(hit["category"], bool(hit["high"]) or fb.high_severity, "llm") if hit else fb)
    llm_count = sum(lab.source == "llm" for lab in labels)
    high_by_keywords_only = sum(
        1 for key, fb in zip(keys, fallback)
        if cache.get(key) and fb.high_severity and not cache.get(key)["high"])
    return ClassificationRun(labels, {
        "mode": "llm",
        "model": settings.llm_model,
        "llm_labels": llm_count,
        "keyword_labels": len(labels) - llm_count,
        "served_from_cache": cached_before,
        "llm_requests": requests,
        "llm_error": error,
        "high_added_by_keyword_rules": high_by_keywords_only,
    })
