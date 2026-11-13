"""Invariants that must hold for any export, checked on the real exports when
they are present (data/ is mounted at /data in docker, ../data locally)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.analysis import analyze, parse_now
from app.config import CATEGORIES
from app.ingest import load_messages

DATA = next((p for p in (Path("/data"), Path(__file__).resolve().parents[2] / "data") if p.is_dir()), None)
EXPORTS = [("messages_sample.csv", "2026-08-24T07:00:00Z"), ("eval_messages.csv", "2026-04-15T07:00:00Z")]


@pytest.mark.parametrize(("name", "now"), EXPORTS)
def test_report_invariants(name: str, now: str) -> None:
    path = DATA / name if DATA else None
    if path is None or not path.exists():
        pytest.skip(f"{name} not available")
    report = analyze(path, now=parse_now(now), include_details=True)
    msgs = report["messages"]
    by_id = {m["message_id"]: m for m in msgs}
    canon = [m for m in msgs if m["duplicate_of"] is None]

    assert len(msgs) == len(load_messages(path)) == len(by_id)
    assert report["total_unique_messages"] == len(canon)
    assert list(report["category_counts"]) == list(CATEGORIES)
    assert sum(report["category_counts"].values()) == len(canon)
    for m in msgs:
        assert m["category"] in CATEGORIES
        if m["duplicate_of"]:
            original = by_id[m["duplicate_of"]]
            assert original["duplicate_of"] is None
            assert m["category"] == original["category"]
            assert not m["is_urgent"]
    assert report["urgent_message_ids"] == sorted(m["message_id"] for m in msgs if m["is_urgent"])
    # README: the urgent count must match the needs-attention list.
    attention = [m for m in canon if m["severity"] == "high" and not m["answered"]]
    overdue = {m["message_id"] for m in attention
               if m["business_minutes_left"] is not None and m["business_minutes_left"] <= 0}
    assert set(report["urgent_message_ids"]) == overdue
