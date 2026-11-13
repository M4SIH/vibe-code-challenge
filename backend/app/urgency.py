"""Urgency rule for the support dashboard.

A message is urgent when it is high severity, has not been answered, and at
least the SLA (2 business hours) has elapsed since it was received. Exactly
2 hours already counts. An answer, even a late one, means it is handled.
"""
from __future__ import annotations

import math
from datetime import datetime

import pandas as pd

from .sla import business_seconds_between


def _missing(value: object) -> bool:
    return value is None or bool(pd.isna(value))


def is_answered(answered_at: datetime | None, now: datetime, time_unknown: bool = False) -> bool:
    """Answered at or before ``now``. Answers stamped before the message was
    received are a data anomaly; we still count them as answered. An answer
    whose time could not be read (``time_unknown``) also counts as answered."""
    if time_unknown:
        return True
    return not _missing(answered_at) and answered_at <= now


def business_minutes_left(received_at: datetime | None, now: datetime, sla_hours: float) -> int | None:
    """Whole business minutes until the SLA breaks; ``<= 0`` means overdue.
    Rounded up, so 0 is only reported once the full SLA has elapsed."""
    if _missing(received_at):
        return None
    left = sla_hours * 3600 - business_seconds_between(received_at, now)
    return math.ceil(left / 60)


def is_urgent(
    high_severity: bool,
    received_at: datetime | None,
    answered_at: datetime | None,
    now: datetime,
    sla_hours: float,
    answered_time_unknown: bool = False,
) -> bool:
    if (not high_severity or is_answered(answered_at, now, answered_time_unknown)
            or _missing(received_at)):
        return False
    return business_seconds_between(received_at, now) >= sla_hours * 3600
