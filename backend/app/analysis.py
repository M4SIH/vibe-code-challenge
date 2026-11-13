"""End-to-end analysis pipeline shared by the API and the CLI."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

import pandas as pd

from .classify import classify_messages
from .config import CATEGORIES, Settings, get_settings
from .dedup import mark_duplicates
from .ingest import load_messages
from .orders import extract_order_ref
from .sla import add_business_minutes
from .urgency import business_minutes_left, is_answered, is_urgent


def parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    ts = pd.Timestamp(value)
    if pd.isna(ts):
        raise ValueError(f"not a timestamp: {value!r}")
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").to_pydatetime()


def _iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def enrich(df: pd.DataFrame, now: datetime, settings: Settings) -> pd.DataFrame:
    """Add order_ref, duplicate_of, category, high_severity, is_urgent and the
    SLA columns. Resends inherit everything from their original."""
    df = df.copy()
    df["order_ref"] = [
        extract_order_ref(o, b, s) for o, b, s in zip(df["order_ref"], df["body"], df["subject"])
    ]
    df["duplicate_of"] = mark_duplicates(df, now)
    canonical = df["duplicate_of"].isna()
    group = df["duplicate_of"].where(~canonical, df["message_id"])

    run = classify_messages(df[canonical], settings)
    df.attrs["classification"] = run.stats
    by_id = dict(zip(df.loc[canonical, "message_id"], run.labels))
    df["category"] = [by_id[g].category for g in group]
    df["high_severity"] = [by_id[g].high_severity for g in group]
    df["label_source"] = [by_id[g].source for g in group]

    # A group is answered as soon as any copy of it is: the earliest answer wins.
    first_answer = df.groupby(group)["answered_at"].min()
    df["group_answered_at"] = group.map(first_answer)
    # ...including an answer whose time could not be parsed.
    unknown = df.groupby(group)["answered_time_unknown"].any()
    df["group_answered_time_unknown"] = group.map(unknown).astype(bool)

    sla_hours = settings.urgent_sla_business_hours
    df["is_urgent"] = [
        bool(is_canon) and is_urgent(high, received, answered, now, sla_hours, unknown_time)
        for is_canon, high, received, answered, unknown_time in zip(
            canonical, df["high_severity"], df["received_at"], df["group_answered_at"],
            df["group_answered_time_unknown"],
        )
    ]
    df["answered"] = [
        is_answered(a, now, u)
        for a, u in zip(df["group_answered_at"], df["group_answered_time_unknown"])
    ]
    df["business_minutes_left"] = [business_minutes_left(r, now, sla_hours) for r in df["received_at"]]
    df["sla_deadline"] = [
        None if pd.isna(r) else add_business_minutes(r, sla_hours * 60) for r in df["received_at"]
    ]
    return df


def build_report(df: pd.DataFrame, include_details: bool = False) -> dict[str, Any]:
    unique = df[df["duplicate_of"].isna()]
    counts = unique["category"].value_counts()

    messages: list[dict[str, Any]] = []
    for row in df.itertuples(index=False):
        item: dict[str, Any] = {
            "message_id": row.message_id,
            "category": row.category,
            "is_urgent": bool(row.is_urgent),
            "order_ref": row.order_ref,
            "duplicate_of": row.duplicate_of,
        }
        if include_details:
            item.update(
                {
                    "customer_id": row.customer_id,
                    "channel": row.channel,
                    "received_at": _iso(row.received_at),
                    "answered_at": _iso(row.answered_at),
                    "subject": row.subject,
                    "body": row.body,
                    "severity": "high" if row.high_severity else "normal",
                    "severity_hint": row.severity_hint,
                    "label_source": row.label_source,
                    "answered": bool(row.answered),
                    # for the browser's live clock: first answer in the resend group,
                    # and whether some copy has an answer whose time could not be read
                    "group_answered_at": _iso(row.group_answered_at),
                    "answer_time_unknown": bool(row.group_answered_time_unknown),
                    "sla_deadline": _iso(row.sla_deadline),
                    "business_minutes_left": row.business_minutes_left,
                }
            )
        messages.append(item)

    report: dict[str, Any] = {
        "total_unique_messages": int(len(unique)),
        # every category is always present so consumers never see a missing key
        "category_counts": {c: int(counts.get(c, 0)) for c in CATEGORIES},
        "urgent_message_ids": sorted(unique.loc[unique["is_urgent"], "message_id"].tolist()),
        "messages": messages,
    }
    if include_details and "ingest" in df.attrs:
        report["data_quality"] = df.attrs["ingest"]
    if include_details and "classification" in df.attrs:
        report["classification"] = df.attrs["classification"]
    return report


def analyze(
    source: str | Path | IO[bytes] | IO[str],
    now: datetime | None = None,
    settings: Settings | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    df = load_messages(source)
    df = enrich(df, now, settings)
    return build_report(df, include_details=include_details)
