from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.dedup import mark_duplicates, normalize_body
from app.ingest import load_messages


def _frame(bodies: list[str], customers: list[str] | None = None,
           times: list[str] | None = None) -> pd.DataFrame:
    n = len(bodies)
    return pd.DataFrame(
        {
            "message_id": [f"M{i}" for i in range(n)],
            "customer_id": customers or ["C1"] * n,
            "body": bodies,
            "received_at": pd.to_datetime(
                times or [f"2026-10-26T08:{i:02d}:00Z" for i in range(n)], utc=True
            ),
        }
    )


def test_normalize_body_whitespace_and_case() -> None:
    assert normalize_body("  Hello   THERE\n friend ") == "hello there friend"


def test_resent_message_marked_as_duplicate(sample_csv: Path) -> None:
    df = load_messages(sample_csv)
    dups = mark_duplicates(df)
    assert dups.tolist() == [None, None, "M001", None]


# Pairs taken from the shape of real resends in messages_sample.csv.
@pytest.mark.parametrize(
    ("original", "resend"),
    [
        ("Tracking for BZ-506237 has said 'at warehouse' for 2 days.",
         "Tracking for BZ-۵۰۶۲۳۷   has said 'at warehouse' for ۲ days. "),           # digits + spaces
        ("اگه کالا رو پس بدم پولم رو کامل برمی‌گردونید؟",
         "اگه کالا رو پس بدم پولم رو کامل برمی‌گر‌دونید؟"),             # extra ZWNJ
        ("چند روز پیش تیکت زدم. لطفاً رسیدگی کنید.",
         "چند روز پیش تیكت زدم. لطفاً رسیدگی كنید."),                               # Arabic kaf
        ("سلام خسته نباشید، می‌خواستم بدونم",
         "سلام خسته نباشيد، مي‌خواستم بدونم"),                                 # Arabic yeh
        ("Do you offer gift wrapping for orders?",
         " Do you offer gift wrapping for orders?\t"),                              # tab/space
        ("WHERE IS MY ORDER", "where is my order"),                                 # case
        ("BZ-٩٥٥٣٥٣ نرسید", "BZ-955353 نرسید"),                                     # Arabic-Indic digits
        ("سلام سفارشم نرسید", "\ufeb3\ufefc\ufee1 سفارشم نرسید"),                  # presentation forms (NFKC)
    ],
)
def test_cosmetic_variants_are_duplicates(original: str, resend: str) -> None:
    assert mark_duplicates(_frame([original, resend])).tolist() == [None, "M0"]


def test_same_text_from_different_customers_is_not_duplicate() -> None:
    df = _frame(["Where is my parcel?", "Where is my parcel?"], customers=["C1", "C2"])
    assert mark_duplicates(df).tolist() == [None, None]


def test_different_text_is_not_duplicate() -> None:
    assert mark_duplicates(_frame(["order BZ-1 late", "order BZ-2 late"])).tolist() == [None, None]


def test_earliest_received_is_canonical_even_if_later_in_file() -> None:
    df = _frame(["same text", "same text", "same text"],
                times=["2026-10-26T10:00:00Z", "2026-10-26T08:00:00Z", "2026-10-26T09:00:00Z"])
    assert mark_duplicates(df).tolist() == ["M1", None, "M1"]


def test_empty_bodies_are_not_collapsed() -> None:
    assert mark_duplicates(_frame(["", "  "])).tolist() == [None, None]


def test_unknown_received_time_sorts_last() -> None:
    df = _frame(["same", "same"])
    df.loc[0, "received_at"] = pd.NaT
    assert mark_duplicates(df).tolist() == ["M1", None]


# --- A resend after an answer is a new message -------------------------------

def _thread(received: list[str], answered: list[str | None]) -> pd.DataFrame:
    df = _frame(["my account was hacked"] * len(received), times=received)
    df["answered_at"] = pd.to_datetime(answered, utc=True)
    return df


def test_resend_while_unanswered_is_merged() -> None:
    df = _thread(["2026-10-26T08:00:00Z", "2026-10-26T09:00:00Z"], [None, None])
    assert mark_duplicates(df).tolist() == [None, "M0"]


def test_resend_before_the_answer_is_merged() -> None:
    df = _thread(["2026-10-26T08:00:00Z", "2026-10-26T09:00:00Z"], ["2026-10-26T10:00:00Z", None])
    assert mark_duplicates(df).tolist() == [None, "M0"]


def test_resend_after_the_answer_is_a_new_message() -> None:
    df = _thread(["2026-10-26T08:00:00Z", "2026-10-26T11:00:00Z"], ["2026-10-26T10:00:00Z", None])
    assert mark_duplicates(df).tolist() == [None, None]


def test_resend_at_the_exact_answer_minute_is_merged() -> None:
    df = _thread(["2026-10-26T08:00:00Z", "2026-10-26T10:00:00Z"], ["2026-10-26T10:00:00Z", None])
    assert mark_duplicates(df).tolist() == [None, "M0"]


def test_answer_on_a_resend_closes_the_group() -> None:
    # M1 (merged into M0) is the copy that got answered; M2 comes after that answer.
    df = _thread(["2026-10-26T08:00:00Z", "2026-10-26T09:00:00Z", "2026-10-26T12:00:00Z"],
                 [None, "2026-10-26T10:00:00Z", None])
    assert mark_duplicates(df).tolist() == [None, "M0", None]


def test_copies_of_the_new_message_merge_into_it() -> None:
    df = _thread(["2026-10-26T08:00:00Z", "2026-10-26T11:00:00Z", "2026-10-26T12:00:00Z"],
                 ["2026-10-26T10:00:00Z", None, None])
    assert mark_duplicates(df).tolist() == [None, None, "M1"]


def test_split_works_when_file_order_is_not_time_order() -> None:
    df = _thread(["2026-10-26T11:00:00Z", "2026-10-26T08:00:00Z"], [None, "2026-10-26T10:00:00Z"])
    assert mark_duplicates(df).tolist() == [None, None]


def test_answer_after_now_does_not_split() -> None:
    df = _thread(["2026-10-26T08:00:00Z", "2026-10-26T11:00:00Z"], ["2026-10-26T10:00:00Z", None])
    now = pd.Timestamp("2026-10-26T09:30:00Z").to_pydatetime()
    assert mark_duplicates(df, now).tolist() == [None, "M0"]


def test_unreadable_answer_time_never_splits() -> None:
    df = _thread(["2026-10-26T08:00:00Z", "2026-10-26T11:00:00Z"], [None, None])
    assert mark_duplicates(df).tolist() == [None, "M0"]
