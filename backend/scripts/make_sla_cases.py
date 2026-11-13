"""Write the business-time cases shared by the Python and TypeScript tests.

    python -m scripts.make_sla_cases   (from backend/)

Values come from app.sla (verified against the independent oracle in
tests/test_sla_oracle.py). tests/test_shared_sla_cases.py fails if the file
drifts from app.sla, and frontend/src/businessTime.test.ts must reproduce it.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.sla import HOLIDAYS, add_business_minutes, business_seconds_between
from app.urgency import business_minutes_left

OUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "businessTime.cases.json"
UTC = timezone.utc


def iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build() -> dict:
    rng = random.Random(1405)
    base = datetime(2026, 3, 1, tzinfo=UTC)
    span = int((datetime(2027, 3, 25, tzinfo=UTC) - base).total_seconds())
    tehran = timezone(timedelta(hours=3, minutes=30))
    fixed = [  # README boundaries, in Tehran time
        (datetime(2026, 10, 24, 9, 0, tzinfo=tehran), datetime(2026, 10, 24, 11, 0, tzinfo=tehran)),   # exactly 2h
        (datetime(2026, 10, 24, 9, 0, tzinfo=tehran), datetime(2026, 10, 24, 10, 59, tzinfo=tehran)),
        (datetime(2026, 10, 24, 9, 0, tzinfo=tehran), datetime(2026, 10, 24, 10, 59, 30, tzinfo=tehran)),
        (datetime(2026, 10, 21, 16, 0, tzinfo=tehran), datetime(2026, 10, 24, 10, 0, tzinfo=tehran)),  # Wed -> Sat
        (datetime(2026, 8, 22, 16, 30, tzinfo=tehran), datetime(2026, 8, 24, 9, 30, tzinfo=tehran)),   # 1405/06/01
        (datetime(2026, 4, 13, 16, 0, tzinfo=tehran), datetime(2026, 4, 15, 10, 30, tzinfo=tehran)),   # 1405/01/25
        (datetime(2026, 3, 18, 16, 0, tzinfo=tehran), datetime(2026, 3, 25, 10, 0, tzinfo=tehran)),    # Nowruz
        (datetime(2026, 10, 24, 22, 0, tzinfo=tehran), datetime(2026, 10, 25, 9, 30, tzinfo=tehran)),  # night
        (datetime(2026, 10, 24, 12, 0, tzinfo=tehran), datetime(2026, 10, 24, 9, 0, tzinfo=tehran)),   # reversed
    ]
    pairs = fixed + [
        (s := base + timedelta(seconds=rng.randrange(span)), s + timedelta(seconds=rng.randrange(12 * 86400)))
        for _ in range(400)
    ]
    return {
        "holidays": sorted(d.isoformat() for d in HOLIDAYS),
        "between": [{"start": iso(a), "end": iso(b), "seconds": business_seconds_between(a, b)} for a, b in pairs],
        "minutes_left": [{"received": iso(a), "now": iso(b), "left": business_minutes_left(a, b, 2.0)}
                         for a, b in pairs],
        "deadline": [{"start": iso(a), "deadline": iso(add_business_minutes(a, 120))} for a, _ in pairs],
    }


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
