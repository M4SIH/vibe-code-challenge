"""Jalali (Solar Hijri) calendar conversion and export-timestamp parsing.

About 5% of export rows carry timestamps like ``1405/05/26 14:10`` or
``۱۴۰۵/۰۵/۲۳ ۰۶:۵۴`` instead of ISO-8601 UTC. Comparing them with matching
``answered_at`` values shows they are Tehran local time, not UTC.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from .textnorm import to_latin_digits

# Iran abolished daylight saving time in 2022, so Tehran is a fixed +03:30.
TEHRAN = timezone(timedelta(hours=3, minutes=30), "Asia/Tehran")

_JALALI_TS = re.compile(
    r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$"
)


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> date:
    """Convert a Jalali date to a Gregorian ``date`` (arithmetic 33-year cycle
    algorithm, exact for the 1300-1500 range we care about)."""
    if not (1 <= jm <= 12 and 1 <= jd <= (31 if jm <= 6 else 30)):
        raise ValueError(f"invalid Jalali date {jy}/{jm}/{jd}")
    if jm == 12 and jd == 30 and not is_leap_year(jy):
        raise ValueError(f"invalid Jalali date {jy}/{jm}/{jd}: {jy} is not a leap year")
    return _to_gregorian(jy, jm, jd)


def is_leap_year(jy: int) -> bool:
    """A Jalali year is leap when Esfand has 30 days, i.e. 1 Farvardin of the
    next year is 30 days after 1 Esfand."""
    return (_to_gregorian(jy + 1, 1, 1) - _to_gregorian(jy, 12, 1)).days == 30


def _to_gregorian(jy: int, jm: int, jd: int) -> date:
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
    days += (jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    return date(gy, 1, 1) + timedelta(days=days)


def parse_timestamp(value: str | None) -> pd.Timestamp:
    """Parse one export timestamp into a tz-aware UTC Timestamp, or NaT.

    * ISO-8601 (``2026-08-22T08:58:00Z``): as given; naive values are UTC.
    * Jalali ``YYYY/MM/DD HH:MM`` with Latin or Persian digits: Tehran time.
    """
    text = to_latin_digits((value or "").strip())
    if not text:
        return pd.NaT
    m = _JALALI_TS.match(text)
    if m and 1300 <= int(m.group(1)) <= 1500:
        try:
            day = jalali_to_gregorian(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            local = datetime(day.year, day.month, day.day,
                             int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0),
                             tzinfo=TEHRAN)
        except ValueError:
            return pd.NaT
        return pd.Timestamp(local).tz_convert("UTC")
    try:
        ts = pd.Timestamp(text)
    except (ValueError, TypeError):
        return pd.NaT
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def parse_timestamps(values: pd.Series) -> pd.Series:
    return pd.Series([parse_timestamp(v) for v in values], index=values.index,
                     dtype="datetime64[ns, UTC]")
