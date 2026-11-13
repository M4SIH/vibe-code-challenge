"""Urgency rule: high severity, unanswered, >= 2 business hours (exactly 2 counts)."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.jalali import TEHRAN
from app.urgency import business_minutes_left, is_urgent

SLA = 2.0
RECEIVED = datetime(2026, 10, 24, 9, 0, tzinfo=TEHRAN)  # Saturday opening time


def at(h: int, m: int = 0) -> datetime:
    return datetime(2026, 10, 24, h, m, tzinfo=TEHRAN)


def test_exactly_two_business_hours_is_urgent() -> None:
    assert is_urgent(True, RECEIVED, None, at(11, 0), SLA)
    assert business_minutes_left(RECEIVED, at(11, 0), SLA) == 0


def test_one_minute_before_is_not_urgent() -> None:
    assert not is_urgent(True, RECEIVED, None, at(10, 59), SLA)
    assert business_minutes_left(RECEIVED, at(10, 59), SLA) == 1


def test_partial_minute_left_rounds_up() -> None:
    now = datetime(2026, 10, 24, 10, 59, 30, tzinfo=TEHRAN)
    assert business_minutes_left(RECEIVED, now, SLA) == 1


def test_overdue_minutes_are_negative() -> None:
    assert business_minutes_left(RECEIVED, at(12, 30), SLA) == -90


def test_not_high_severity_is_never_urgent() -> None:
    assert not is_urgent(False, RECEIVED, None, at(16, 0), SLA)


def test_answered_late_is_handled() -> None:
    assert not is_urgent(True, RECEIVED, at(15, 0), at(16, 0), SLA)


def test_answer_after_now_does_not_count_yet() -> None:
    assert is_urgent(True, RECEIVED, at(16, 30), at(16, 0), SLA)


def test_answer_stamped_before_receipt_still_counts_as_answered() -> None:
    assert not is_urgent(True, RECEIVED, at(8, 0), at(16, 0), SLA)


def test_nan_answered_and_missing_received() -> None:
    assert is_urgent(True, RECEIVED, pd.NaT, at(16, 0), SLA)
    assert not is_urgent(True, pd.NaT, None, at(16, 0), SLA)
    assert business_minutes_left(pd.NaT, at(16, 0), SLA) is None


def test_weekend_does_not_make_it_urgent() -> None:
    # Received Wednesday 16:30 Tehran, checked Friday: only 30 business minutes.
    received = datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)
    now = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    assert not is_urgent(True, received, None, now, SLA)
    assert business_minutes_left(received, now, SLA) == 90


def test_answer_with_unreadable_time_counts_as_answered() -> None:
    # Someone filled in answered_at but it did not parse: handled, not urgent.
    assert not is_urgent(True, RECEIVED, pd.NaT, at(16, 0), SLA, answered_time_unknown=True)
