"""Business-time rules from the README: Sat-Wed 09:00-17:00 Tehran time,
closed Thursday, Friday and the listed 1405 public holidays."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.jalali import TEHRAN, jalali_to_gregorian
from app.sla import (
    HOLIDAYS,
    add_business_minutes,
    business_hours_between,
    business_minutes_between,
    is_business_day,
)


def teh(*args: int) -> datetime:
    return datetime(*args, tzinfo=TEHRAN)


def test_jalali_reference_dates() -> None:
    assert jalali_to_gregorian(1405, 1, 1).isoformat() == "2026-03-21"   # Nowruz
    assert jalali_to_gregorian(1405, 6, 1).isoformat() == "2026-08-23"
    assert jalali_to_gregorian(1405, 1, 25).isoformat() == "2026-04-14"
    assert jalali_to_gregorian(1403, 12, 30).isoformat() == "2025-03-20"  # leap year end


def test_holiday_list_is_complete() -> None:
    assert len(HOLIDAYS) == 26


def test_holidays_outside_1405_are_not_known() -> None:
    # 1404/11/22 (Wed 2026-02-11) is a real public holiday, but the README only
    # lists 1405 holidays, so we deliberately treat it as a normal working day.
    day = jalali_to_gregorian(1404, 11, 22)
    assert day.isoformat() == "2026-02-11" and day.strftime("%A") == "Wednesday"
    assert is_business_day(day)
    assert business_minutes_between(teh(2026, 2, 11, 9, 0), teh(2026, 2, 11, 17, 0)) == 480


def test_business_days() -> None:
    assert is_business_day(teh(2026, 10, 24).date())        # Saturday
    assert is_business_day(teh(2026, 10, 28).date())        # Wednesday
    assert not is_business_day(teh(2026, 10, 29).date())    # Thursday
    assert not is_business_day(teh(2026, 10, 30).date())    # Friday
    assert not is_business_day(teh(2026, 8, 23).date())     # 1405/06/01, a Sunday holiday


def test_within_one_day() -> None:
    assert business_hours_between(teh(2026, 10, 24, 10, 0), teh(2026, 10, 24, 13, 30)) == 3.5


def test_inputs_in_utc_are_counted_in_tehran_time() -> None:
    # 05:30Z is 09:00 in Tehran; the old code would have counted from 09:00Z.
    start = datetime(2026, 10, 24, 5, 30, tzinfo=timezone.utc)
    end = datetime(2026, 10, 24, 7, 30, tzinfo=timezone.utc)
    assert business_hours_between(start, end) == 2.0


def test_thursday_and_friday_are_skipped() -> None:
    # Wednesday 16:00 -> Saturday 10:00: one hour each side of the weekend.
    assert business_hours_between(teh(2026, 10, 21, 16, 0), teh(2026, 10, 24, 10, 0)) == 2.0


def test_old_monday_to_friday_case() -> None:
    # Friday 19:30 Tehran -> Monday 13:30 Tehran = Sat 8h + Sun 8h + Mon 4.5h.
    start = datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    assert business_hours_between(start, end) == 20.5


def test_nights_do_not_count() -> None:
    assert business_minutes_between(teh(2026, 10, 24, 22, 0), teh(2026, 10, 25, 9, 30)) == 30
    assert business_minutes_between(teh(2026, 10, 24, 7, 0), teh(2026, 10, 24, 9, 0)) == 0


def test_holiday_is_skipped() -> None:
    # Sat 1405/05/31 16:30 -> Mon 1405/06/02 09:30, Sunday 1405/06/01 is a holiday.
    assert business_minutes_between(teh(2026, 8, 22, 16, 30), teh(2026, 8, 24, 9, 30)) == 60


def test_holiday_run_around_nowruz() -> None:
    # Wed 1404/12/27 16:00 -> Wed 1405/01/05 10:00: Thu-Fri off, then Sat 1-Tue 4 Farvardin holidays.
    assert business_minutes_between(teh(2026, 3, 18, 16, 0), teh(2026, 3, 25, 10, 0)) == 120


def test_empty_and_reversed_intervals() -> None:
    t = teh(2026, 10, 24, 10, 0)
    assert business_hours_between(t, t) == 0.0
    assert business_hours_between(t, teh(2026, 10, 24, 9, 0)) == 0.0


@pytest.mark.parametrize(
    ("start", "deadline"),
    [
        (teh(2026, 10, 24, 10, 0), teh(2026, 10, 24, 12, 0)),   # plain business hours
        (teh(2026, 10, 24, 16, 0), teh(2026, 10, 25, 10, 0)),   # rolls over the night
        (teh(2026, 10, 21, 16, 30), teh(2026, 10, 24, 10, 30)), # Wed -> Sat
        (teh(2026, 10, 22, 11, 0), teh(2026, 10, 24, 11, 0)),   # received on a Thursday
        (teh(2026, 10, 24, 6, 0), teh(2026, 10, 24, 11, 0)),    # received before opening
        (teh(2026, 8, 22, 16, 0), teh(2026, 8, 24, 10, 0)),     # over the 1405/06/01 holiday
        (teh(2026, 4, 13, 16, 0), teh(2026, 4, 15, 10, 0)),     # over the 1405/01/25 holiday
    ],
)
def test_deadline(start: datetime, deadline: datetime) -> None:
    assert add_business_minutes(start, 120) == deadline
    assert business_minutes_between(start, deadline) == 120
