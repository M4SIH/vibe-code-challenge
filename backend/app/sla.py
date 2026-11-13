"""Business-time arithmetic for the support SLA.

Support works Saturday-Wednesday, 09:00-17:00 Tehran time, and is closed on
the official holidays listed in the README. All arithmetic is done in Tehran
local time; inputs and outputs are tz-aware datetimes (any zone).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from .jalali import TEHRAN, jalali_to_gregorian

BUSINESS_START = time(9, 0)
BUSINESS_END = time(17, 0)
# Python weekday(): Monday=0 ... Sunday=6. Sat, Sun, Mon, Tue, Wed are open.
BUSINESS_WEEKDAYS = frozenset({5, 6, 0, 1, 2})

HOLIDAYS_JALALI: tuple[str, ...] = (
    "1405/01/01", "1405/01/02", "1405/01/03", "1405/01/04", "1405/01/12",
    "1405/01/13", "1405/01/25", "1405/03/07", "1405/03/14", "1405/03/15",
    "1405/04/05", "1405/04/06", "1405/05/15", "1405/05/23", "1405/05/25",
    "1405/06/01", "1405/06/10", "1405/08/24", "1405/10/03", "1405/10/17",
    "1405/11/05", "1405/11/22", "1405/12/10", "1405/12/20", "1405/12/21",
    "1405/12/29",
)
HOLIDAYS: frozenset[date] = frozenset(
    jalali_to_gregorian(*map(int, d.split("/"))) for d in HOLIDAYS_JALALI
)


def is_business_day(day: date) -> bool:
    return day.weekday() in BUSINESS_WEEKDAYS and day not in HOLIDAYS


def _window(day: date) -> tuple[datetime, datetime]:
    return (datetime.combine(day, BUSINESS_START, tzinfo=TEHRAN),
            datetime.combine(day, BUSINESS_END, tzinfo=TEHRAN))


def business_seconds_between(start: datetime, end: datetime) -> float:
    """Business seconds in ``[start, end)``; 0 when ``end <= start``."""
    if end <= start:
        return 0.0
    start, end = start.astimezone(TEHRAN), end.astimezone(TEHRAN)
    total = 0.0
    day = start.date()
    while day <= end.date():
        if is_business_day(day):
            opens, closes = _window(day)
            lo, hi = max(opens, start), min(closes, end)
            if hi > lo:
                total += (hi - lo).total_seconds()
        day += timedelta(days=1)
    return total


def business_minutes_between(start: datetime, end: datetime) -> float:
    return business_seconds_between(start, end) / 60.0


def business_hours_between(start: datetime, end: datetime) -> float:
    return business_seconds_between(start, end) / 3600.0


def add_business_minutes(start: datetime, minutes: float) -> datetime:
    """The instant at which ``minutes`` business minutes have elapsed since
    ``start`` (the SLA deadline). Returned in Tehran time."""
    remaining = timedelta(minutes=minutes)
    cursor = start.astimezone(TEHRAN)
    day = cursor.date()
    for _ in range(3660):  # ten years of days: a hard stop, never reached
        if is_business_day(day):
            opens, closes = _window(day)
            lo = max(opens, cursor)
            if lo < closes:
                available = closes - lo
                if remaining <= available:
                    return lo + remaining
                remaining -= available
        day += timedelta(days=1)
    raise ValueError("deadline is more than ten years away")
