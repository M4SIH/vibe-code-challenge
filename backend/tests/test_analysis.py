from __future__ import annotations

import json
from pathlib import Path

from app.analysis import analyze, parse_now
from app.cli import main


def test_category_counts_use_unique_messages(sample_csv: Path) -> None:
    report = analyze(sample_csv, now=parse_now("2026-10-26T10:00:00Z"))
    assert report["total_unique_messages"] == 3
    assert sum(report["category_counts"].values()) == 3
    assert report["category_counts"]["delivery"] == 1
    assert report["category_counts"]["account"] == 1


def test_cli_writes_output_schema(sample_csv: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    assert main(["analyze", "--input", str(sample_csv), "--output", str(out),
                 "--now", "2026-10-26T12:00:00Z"]) == 0

    report = json.loads(out.read_text(encoding="utf-8"))
    assert set(report) == {"total_unique_messages", "category_counts",
                           "urgent_message_ids", "messages"}
    assert len(report["messages"]) == 4
    first = report["messages"][0]
    assert set(first) == {"message_id", "category", "is_urgent", "order_ref", "duplicate_of"}
    assert first["order_ref"] == "BZ-10234"
    assert report["messages"][2]["duplicate_of"] == "M001"
    assert report["urgent_message_ids"] == ["M002"]


def test_all_categories_present_even_when_zero(sample_csv: Path) -> None:
    report = analyze(sample_csv, now=parse_now("2026-10-26T10:00:00Z"))
    assert set(report["category_counts"]) == {
        "delivery", "payment", "refund", "product_quality", "account", "other"}
    assert report["category_counts"]["refund"] == 0


PIPELINE_CSV = """\
message_id,customer_id,channel,received_at,answered_at,subject,body,order_ref,severity_hint
A1,C1,app,۱۴۰۵/۰۵/۳۱ ۱۶:۰۰,,Charged twice,I was charged twice for order BZ-۱۲۳۴۵.,,low
A2,C1,app,2026-08-22T13:00:00Z,,Charged twice,I was  charged twice for order BZ-12345.,,low
B1,C2,app,2026-08-22T12:30:00Z,,Hacked,Someone accessed my account,,low
B2,C2,app,2026-08-22T12:45:00Z,2026-08-22T13:00:00Z,Hacked,someone accessed my account,,low
C1,C3,app,2026-08-22T12:30:00Z,,URGENT!!!,THE INVOICE FONT IS UGLY!!!,,high
D1,C4,app,garbage,,Charged twice,charged twice,,high
"""


def test_pipeline_rules(tmp_path: Path) -> None:
    path = tmp_path / "in.csv"
    path.write_text(PIPELINE_CSV, encoding="utf-8")
    # Mon 1405/06/02 10:30 Tehran, the day after the 1405/06/01 holiday (sample export time).
    report = analyze(path, now=parse_now("2026-08-24T07:00:00Z"), include_details=True)
    by_id = {m["message_id"]: m for m in report["messages"]}

    assert [m["message_id"] for m in report["messages"]] == ["A1", "A2", "B1", "B2", "C1", "D1"]
    # Jalali-dated original (Sat 16:00 Tehran): 1h Sat + holiday Sunday + 1.5h Mon = overdue.
    assert by_id["A1"]["is_urgent"] and by_id["A1"]["business_minutes_left"] == -30
    assert by_id["A1"]["order_ref"] == "BZ-12345"
    # Resend points at the original and is never urgent itself.
    assert by_id["A2"]["duplicate_of"] == "A1" and not by_id["A2"]["is_urgent"]
    # Only the resend was answered: the whole group counts as handled.
    assert by_id["B2"]["duplicate_of"] == "B1" and not by_id["B1"]["is_urgent"]
    # severity_hint "high" alone does not make something urgent.
    assert not by_id["C1"]["is_urgent"]
    # Unparseable timestamp: kept, never urgent.
    assert not by_id["D1"]["is_urgent"] and by_id["D1"]["received_at"] is None
    assert report["urgent_message_ids"] == ["A1"]
    assert report["total_unique_messages"] == 4
    assert report["data_quality"]["unparseable_received_at"] == ["D1"]


UNREADABLE_ANSWER_CSV = """\
message_id,customer_id,channel,received_at,answered_at,subject,body,order_ref,severity_hint
U1,C1,app,2026-08-22T06:00:00Z,sometime monday,Hacked,Someone accessed my account,,high
U2,C2,app,2026-08-22T06:00:00Z,,Hacked,Someone accessed my account,,high
V1,C3,app,2026-08-22T06:00:00Z,,Charged twice,I was charged twice,,high
V2,C3,app,2026-08-22T06:30:00Z,۱۴۰۵/۱۳/۰۱ ۱۰:۰۰,Charged twice,I was charged twice,,high
"""


def test_unreadable_answered_at_means_handled(tmp_path: Path) -> None:
    path = tmp_path / "in.csv"
    path.write_text(UNREADABLE_ANSWER_CSV, encoding="utf-8")
    report = analyze(path, now=parse_now("2026-08-22T12:00:00Z"), include_details=True)
    by_id = {m["message_id"]: m for m in report["messages"]}
    assert not by_id["U1"]["is_urgent"] and by_id["U1"]["answered"]
    assert by_id["U2"]["is_urgent"]                       # same text, other customer, no answer
    # The resend's unreadable answer covers the original too.
    assert by_id["V2"]["duplicate_of"] == "V1" and not by_id["V1"]["is_urgent"]
    assert report["urgent_message_ids"] == ["U2"]
    assert report["data_quality"]["unparseable_answered_at"] == ["U1", "V2"]


RESEND_AFTER_ANSWER_CSV = """\
message_id,customer_id,channel,received_at,answered_at,subject,body,order_ref,severity_hint
H1,C1,app,2026-08-22T06:00:00Z,2026-08-22T06:30:00Z,Hacked,Someone accessed my account,,high
H2,C1,app,2026-08-22T07:00:00Z,,Hacked,someone accessed my account ,,high
H3,C1,app,2026-08-22T07:30:00Z,,Hacked,Someone accessed my account,,high
"""


def test_resend_after_answer_is_new_and_can_be_urgent(tmp_path: Path) -> None:
    path = tmp_path / "in.csv"
    path.write_text(RESEND_AFTER_ANSWER_CSV, encoding="utf-8")
    report = analyze(path, now=parse_now("2026-08-22T12:00:00Z"), include_details=True)
    by_id = {m["message_id"]: m for m in report["messages"]}
    assert by_id["H1"]["duplicate_of"] is None and by_id["H1"]["answered"]
    # H2 came after H1's answer: a new message, unanswered and past 2 business hours.
    assert by_id["H2"]["duplicate_of"] is None and not by_id["H2"]["answered"]
    assert by_id["H3"]["duplicate_of"] == "H2"
    assert report["total_unique_messages"] == 2
    assert report["urgent_message_ids"] == ["H2"]
