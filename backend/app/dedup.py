"""Duplicate detection: the same customer resending the same text.

Resends in the export differ from the original only cosmetically: Persian vs
Latin digits, a zero-width non-joiner dropped or inserted mid-word, Arabic
ي/ك instead of Persian ی/ک, extra spaces/tabs, letter case. We compare the
normalised body (see ``textnorm.normalize_text``) per customer.

A resend only merges into its original while that message is still waiting
for an answer: customers resend "when they don't hear back". Once the group
has been answered, the same text again is a new message with its own SLA
clock, so it cannot hide behind the earlier answer.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from .textnorm import normalize_text


def normalize_body(text: str) -> str:
    return normalize_text(text)


def dedup_key(customer_id: str, body: str) -> str | None:
    """``None`` means "never a duplicate" (no customer or no text to compare)."""
    customer = (customer_id or "").strip()
    norm = normalize_body(body)
    if not customer or not norm:
        return None
    return f"{customer}|{norm}"


def _answer_time(value: object, now: datetime | None) -> pd.Timestamp | None:
    """A usable answer time, or None (no answer, unreadable, or after ``now``)."""
    if value is None or pd.isna(value):
        return None
    ts = pd.Timestamp(value)
    if now is not None and ts > pd.Timestamp(now):
        return None
    return ts


def mark_duplicates(df: pd.DataFrame, now: datetime | None = None) -> pd.Series:
    """Return a Series (aligned to ``df``) with the canonical message_id for
    duplicates and ``None`` for canonical messages.

    Messages are processed in received order (ties, and rows with an unknown
    received time, which sort last, keep file order). A copy joins the open
    group for its key unless that group was already answered before the copy
    arrived; then the copy starts a new group. An answer with an unreadable
    time (NaT in ``answered_at``) cannot be ordered, so it never splits.
    """
    keys = [dedup_key(c, b) for c, b in zip(df["customer_id"], df["body"])]
    answered = df["answered_at"] if "answered_at" in df.columns else pd.Series(pd.NaT, index=df.index)
    order = df.assign(_key=keys, _pos=range(len(df)), _ans=answered).sort_values(
        ["received_at", "_pos"], kind="stable", na_position="last"
    )

    open_group: dict[str, tuple[str, pd.Timestamp | None]] = {}  # key -> (canonical id, first answer)
    duplicate_of: dict[object, str | None] = {}
    for idx, key, message_id, received, ans in zip(
        order.index, order["_key"], order["message_id"], order["received_at"], order["_ans"]
    ):
        answer = _answer_time(ans, now)
        if key is not None and key in open_group:
            canonical, group_answer = open_group[key]
            arrived_after_answer = group_answer is not None and (pd.isna(received) or received > group_answer)
            if not arrived_after_answer:
                duplicate_of[idx] = canonical
                if answer is not None and (group_answer is None or answer < group_answer):
                    open_group[key] = (canonical, answer)
                continue
        duplicate_of[idx] = None
        if key is not None:
            open_group[key] = (message_id, answer)

    return pd.Series([duplicate_of[i] for i in df.index], index=df.index, dtype=object)
