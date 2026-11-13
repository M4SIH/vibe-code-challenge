"""Deep checks of the business calendar against an independent oracle.

The oracle shares no code with app.sla / app.jalali:
* time zone comes from the IANA database (zoneinfo "Asia/Tehran") instead of
  our fixed +03:30, which also verifies the "no DST since 2022" assumption;
* holidays are a hard-coded Gregorian list (cross-checked once against the
  jdatetime library) instead of our Jalali converter;
* it simply asks "is support open during this minute?" for every minute.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

import pytest

from app.jalali import TEHRAN
from app.sla import (
    HOLIDAYS,
    add_business_minutes,
    business_minutes_between,
    business_seconds_between,
    is_business_day,
)

try:
    from zoneinfo import ZoneInfo

    IANA_TEHRAN = ZoneInfo("Asia/Tehran")
except Exception:  # pragma: no cover - tzdata missing in a slim image
    IANA_TEHRAN = None

UTC = timezone.utc

# README holidays for 1405, written out in Gregorian by hand.
ORACLE_HOLIDAYS = {
    date.fromisoformat(d)
    for d in (
        "2026-03-21", "2026-03-22", "2026-03-23", "2026-03-24", "2026-04-01",
        "2026-04-02", "2026-04-14", "2026-05-28", "2026-06-04", "2026-06-05",
        "2026-06-26", "2026-06-27", "2026-08-06", "2026-08-14", "2026-08-16",
        "2026-08-23", "2026-09-01", "2026-11-15", "2026-12-24", "2027-01-07",
        "2027-01-25", "2027-02-11", "2027-03-01", "2027-03-11", "2027-03-12",
        "2027-03-20",
    )
}
OPEN_WEEKDAYS = {"Saturday", "Sunday", "Monday", "Tuesday", "Wednesday"}


def _tehran(t: datetime) -> datetime:
    return t.astimezone(IANA_TEHRAN or TEHRAN)


def oracle_open(t: datetime) -> bool:
    local = _tehran(t)
    return (
        local.strftime("%A") in OPEN_WEEKDAYS
        and local.date() not in ORACLE_HOLIDAYS
        and 9 <= local.hour < 17
    )


def oracle_minutes(start: datetime, end: datetime) -> int:
    """Count open minutes in [start, end); start/end must be on whole minutes."""
    n, t = 0, start
    while t < end:
        n += oracle_open(t)
        t += timedelta(minutes=1)
    return n


def oracle_deadline(start: datetime, minutes: int) -> datetime:
    t = start.replace(second=0, microsecond=0)
    if t < start:
        t += timedelta(minutes=1)
    left = minutes
    while True:
        if oracle_open(t):
            left -= 1
            if left == 0:
                return t + timedelta(minutes=1)
        t += timedelta(minutes=1)


# Whole-minute instants spread over 1404/12 .. 1405/12, so every holiday,
# Nowruz and the year end are reachable.
RANGE_START = datetime(2026, 3, 1, tzinfo=UTC)
RANGE_MINUTES = int((datetime(2027, 3, 25, tzinfo=UTC) - RANGE_START).total_seconds() // 60)


def _random_instant(rng: random.Random) -> datetime:
    return RANGE_START + timedelta(minutes=rng.randrange(RANGE_MINUTES))


def _random_intervals(seed: int, n: int, max_days: int) -> list[tuple[datetime, datetime]]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        start = _random_instant(rng)
        out.append((start, start + timedelta(minutes=rng.randrange(max_days * 1440))))
    return out


# --- 1. Time zone ----------------------------------------------------------

@pytest.mark.skipif(IANA_TEHRAN is None, reason="IANA tz database not available")
def test_tehran_is_fixed_plus_0330_all_year() -> None:
    """Our fixed offset must equal the IANA rule for every hour of 1405."""
    t = RANGE_START
    while t < RANGE_START + timedelta(minutes=RANGE_MINUTES):
        assert t.astimezone(IANA_TEHRAN).utcoffset() == timedelta(hours=3, minutes=30), t
        t += timedelta(hours=1)


# --- 2. Holidays and weekdays ----------------------------------------------

def test_holiday_set_matches_hand_written_gregorian_list() -> None:
    assert HOLIDAYS == ORACLE_HOLIDAYS


def test_is_business_day_matches_oracle_for_every_day() -> None:
    day = date(2026, 3, 1)
    while day <= date(2027, 3, 25):
        expected = day.strftime("%A") in OPEN_WEEKDAYS and day not in ORACLE_HOLIDAYS
        assert is_business_day(day) == expected, day
        day += timedelta(days=1)


@pytest.mark.parametrize("holiday", sorted(ORACLE_HOLIDAYS))
def test_each_holiday_counts_zero(holiday: date) -> None:
    opens = datetime(holiday.year, holiday.month, holiday.day, 9, 0, tzinfo=TEHRAN)
    assert business_minutes_between(opens, opens + timedelta(hours=8)) == 0
    # The whole calendar day, midnight to midnight, also counts zero.
    midnight = opens.replace(hour=0)
    assert business_minutes_between(midnight, midnight + timedelta(days=1)) == 0


# --- 3. Boundaries (second precision) --------------------------------------

def teh(*args: int) -> datetime:
    return datetime(*args, tzinfo=TEHRAN)


@pytest.mark.parametrize(
    ("start", "end", "seconds"),
    [
        (teh(2026, 10, 24, 8, 59, 59), teh(2026, 10, 24, 9, 0, 1), 1),     # opening
        (teh(2026, 10, 24, 16, 59, 59), teh(2026, 10, 24, 17, 0, 1), 1),   # closing
        (teh(2026, 10, 24, 17, 0), teh(2026, 10, 24, 23, 59, 59), 0),      # after close
        (teh(2026, 10, 24, 0, 0), teh(2026, 10, 24, 9, 0), 0),             # before open
        (teh(2026, 10, 24, 0, 0), teh(2026, 10, 25, 0, 0), 8 * 3600),      # one full day
        (teh(2026, 10, 24, 0, 0), teh(2026, 10, 31, 0, 0), 5 * 8 * 3600),  # one full week
        (teh(2026, 10, 28, 16, 59, 30), teh(2026, 10, 31, 9, 0, 30), 60),  # Wed -> Sat
    ],
)
def test_boundaries(start: datetime, end: datetime, seconds: float) -> None:
    assert business_seconds_between(start, end) == seconds


def test_deadline_lands_exactly_on_close_not_next_morning() -> None:
    # 15:00 + 120 min ends at 17:00 the same day, not 09:00 tomorrow.
    assert add_business_minutes(teh(2026, 10, 24, 15, 0), 120) == teh(2026, 10, 24, 17, 0)
    # One second later it has to roll over to the next morning.
    assert add_business_minutes(teh(2026, 10, 24, 15, 0, 1), 120) == teh(2026, 10, 25, 9, 0, 1)


def test_deadline_with_zero_minutes() -> None:
    t = teh(2026, 10, 24, 10, 0)
    assert add_business_minutes(t, 0) == t


def test_results_do_not_depend_on_input_time_zone() -> None:
    start_utc = datetime(2026, 8, 22, 12, 30, tzinfo=UTC)
    end_utc = datetime(2026, 8, 24, 7, 0, tzinfo=UTC)
    other = timezone(timedelta(hours=-5))
    assert business_seconds_between(start_utc, end_utc) == business_seconds_between(
        start_utc.astimezone(other), end_utc.astimezone(TEHRAN)
    )


# --- 4. Random intervals against the oracle --------------------------------

@pytest.mark.parametrize(("start", "end"), _random_intervals(seed=1405, n=300, max_days=12))
def test_minutes_between_matches_oracle(start: datetime, end: datetime) -> None:
    assert business_minutes_between(start, end) == oracle_minutes(start, end)


@pytest.mark.parametrize(("start", "_end"), _random_intervals(seed=2026, n=300, max_days=1))
def test_deadline_matches_oracle(start: datetime, _end: datetime) -> None:
    assert add_business_minutes(start, 120) == oracle_deadline(start, 120)


def test_seconds_precision_against_oracle() -> None:
    """Off-minute starts: compare against the oracle shifted by whole seconds."""
    rng = random.Random(7)
    for _ in range(200):
        start = _random_instant(rng) + timedelta(seconds=rng.randrange(1, 60))
        end = start + timedelta(minutes=rng.randrange(5 * 1440))
        # Both edges are shifted by the same number of seconds, and the shift
        # never crosses 09:00/17:00 unless the oracle minute itself does, so
        # compare the exact count with a 1-minute tolerance at each edge.
        exact = business_seconds_between(start, end) / 60
        coarse = oracle_minutes(start.replace(second=0), end.replace(second=0))
        assert abs(exact - coarse) <= 1, (start, end, exact, coarse)


# --- 5. Invariants ---------------------------------------------------------

@pytest.mark.parametrize("seed", range(5))
def test_additivity(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(200):
        a = _random_instant(rng)
        b = a + timedelta(seconds=rng.randrange(10 * 86400))
        c = b + timedelta(seconds=rng.randrange(10 * 86400))
        assert business_seconds_between(a, c) == pytest.approx(
            business_seconds_between(a, b) + business_seconds_between(b, c)
        )


@pytest.mark.parametrize("seed", range(5))
def test_deadline_is_inverse_and_inside_opening_hours(seed: int) -> None:
    rng = random.Random(100 + seed)
    for _ in range(200):
        start = _random_instant(rng) + timedelta(seconds=rng.randrange(60))
        minutes = rng.choice([1, 30, 119, 120, 121, 480, 481, 2400])
        deadline = add_business_minutes(start, minutes)
        assert business_seconds_between(start, deadline) == pytest.approx(minutes * 60)
        local = deadline.astimezone(TEHRAN)
        assert is_business_day(local.date())
        assert teh(local.year, local.month, local.day, 9, 0) < local <= teh(
            local.year, local.month, local.day, 17, 0)


def test_monotonic_in_end() -> None:
    rng = random.Random(42)
    start = _random_instant(rng)
    prev = 0.0
    for step in range(0, 14 * 1440, 17):
        cur = business_seconds_between(start, start + timedelta(minutes=step))
        assert cur >= prev
        prev = cur
