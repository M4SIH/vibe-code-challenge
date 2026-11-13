from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest

from app.ingest import load_messages
from app.jalali import parse_timestamp

HEADER = "message_id,customer_id,channel,received_at,answered_at,subject,body,order_ref,severity_hint\n"


def test_loads_all_clean_rows(sample_csv: Path) -> None:
    df = load_messages(sample_csv)
    assert list(df["message_id"]) == ["M001", "M002", "M003", "M004"]
    assert "does not work" in df.loc[3, "body"]


def test_iso_timestamps_are_utc(sample_csv: Path) -> None:
    df = load_messages(sample_csv)
    assert df.loc[0, "received_at"] == pd.Timestamp("2026-10-26T08:00:00Z")
    assert str(df["received_at"].dt.tz) == "UTC"
    assert pd.isna(df.loc[1, "answered_at"])


@pytest.mark.parametrize(
    ("raw", "utc"),
    [
        ("2026-08-22T08:58:00Z", "2026-08-22T08:58:00Z"),
        ("1405/05/26 14:10", "2026-08-17T10:40:00Z"),          # Tehran local, Latin digits
        ("۱۴۰۵/۰۵/۲۳ ۰۶:۵۴", "2026-08-14T03:24:00Z"),           # Persian digits
        ("١٤٠٥/٠١/٢٥ ١٤:٣٢", "2026-04-14T11:02:00Z"),           # Arabic-Indic digits
        ("  2026-04-15T07:00:00+00:00 ", "2026-04-15T07:00:00Z"),
    ],
)
def test_parse_timestamp(raw: str, utc: str) -> None:
    assert parse_timestamp(raw) == pd.Timestamp(utc)


@pytest.mark.parametrize("raw", ["", "   ", "not a date", "1405/07/31 10:00", "1405/13/01 10:00"])
def test_parse_timestamp_invalid(raw: str) -> None:
    assert pd.isna(parse_timestamp(raw))


def test_every_row_with_an_id_is_kept() -> None:
    csv = HEADER + (
        "M1,C1,app,1405/05/26 14:10,,s,b,,high\n"
        ",,,,,,,,\n"
        "\n"
        "M2,C2,app,garbage,,s,b,,low\n"
        ",C3,app,2026-08-22T08:58:00Z,,s,orphan,,low\n"
        "M3,C4,app,2026-08-22T09:00:00Z,2026-08-22T08:00:00Z,s,b,,low\n"
    )
    df = load_messages(io.StringIO(csv))
    assert list(df["message_id"]) == ["M1", "M2", "M3"]
    assert df.loc[0, "received_at"] == pd.Timestamp("2026-08-17T10:40:00Z")
    assert pd.isna(df.loc[1, "received_at"])
    report = df.attrs["ingest"]
    # ",,,,,,,," and the empty line are both blank records.
    assert report["blank_rows_skipped"] == 2
    assert report["records_read"] == (
        report["rows_kept"] + report["blank_rows_skipped"] + report["rows_without_id_skipped"])
    assert report["rows_without_id_skipped"] == 1
    assert report["unparseable_received_at"] == ["M2"]
    assert report["answered_before_received"] == ["M3"]


def test_short_rows_and_bom() -> None:
    csv = "﻿" + HEADER + "M1,C1,app,2026-08-22T08:58:00Z\n"
    df = load_messages(io.BytesIO(csv.encode("utf-8")))
    assert list(df["message_id"]) == ["M1"]
    assert df.loc[0, "body"] == ""


def test_missing_required_column() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        load_messages(io.StringIO("message_id,body\nM1,hi\n"))


# --- Edge cases a future export could contain -------------------------------

def _load(text: str) -> pd.DataFrame:
    return load_messages(io.StringIO(text))


def test_whitespace_only_line_is_counted_as_blank() -> None:
    # Both real exports contain a line of three spaces; pandas used to drop it silently.
    df = _load(HEADER + "M1,C1,app,2026-08-22T08:58:00Z,,s,b,,low\n   \n")
    assert list(df["message_id"]) == ["M1"]
    assert df.attrs["ingest"]["blank_rows_skipped"] == 1


def test_crlf_line_endings() -> None:
    csv = (HEADER + "M1,C1,app,2026-08-22T08:58:00Z,,s,\"line one\r\nline two\",,low\n").replace(
        "\n", "\r\n")
    df = load_messages(io.BytesIO(csv.encode("utf-8")))
    assert list(df["message_id"]) == ["M1"]
    assert df.loc[0, "body"].startswith("line one") and "line two" in df.loc[0, "body"]


def test_quoted_body_with_commas_quotes_and_newlines_is_preserved() -> None:
    body = 'Hi, "urgent", my order\nBZ-1 is late,\tthanks'
    quoted = '"' + body.replace('"', '""') + '"'
    df = _load(HEADER + f"M1,C1,app,2026-08-22T08:58:00Z,,s,{quoted},,low\n")
    assert df.loc[0, "body"] == body


def test_customer_text_is_not_trimmed_or_altered() -> None:
    # Shape of a real resend in messages_sample.csv; dedup normalises later, ingest must not.
    body = " Do you offer gift wrapping for orders?\t"
    subject = "  پاسخ ندادن پشتيباني "
    df = _load(HEADER + f'M1,C1,app,2026-08-22T08:58:00Z,,"{subject}","{body}",,low\n')
    assert df.loc[0, "body"] == body
    assert df.loc[0, "subject"] == subject


def test_header_case_order_and_extra_columns() -> None:
    csv = (" Body ,Message_ID,RECEIVED_AT,customer_id,extra\n"
           "hello,M1,2026-08-22T08:58:00Z,C1,ignored\n")
    df = _load(csv)
    assert df.loc[0, "message_id"] == "M1" and df.loc[0, "body"] == "hello"
    assert df.loc[0, "received_at"] == pd.Timestamp("2026-08-22T08:58:00Z")
    assert df.loc[0, "order_ref"] == "" and df.loc[0, "severity_hint"] == ""


def test_short_and_long_rows_are_kept_and_reported() -> None:
    df = _load(HEADER + "M1,C1,app,2026-08-22T08:58:00Z\n"
                        "M2,C2,app,2026-08-22T08:58:00Z,,s,b,,low,surplus\n")
    assert list(df["message_id"]) == ["M1", "M2"]
    assert df.attrs["ingest"]["short_rows"] == ["M1"]
    assert df.attrs["ingest"]["rows_with_extra_fields"] == ["M2"]


def test_message_id_whitespace_is_trimmed() -> None:
    df = _load(HEADER + "  M1 ,C1,app,2026-08-22T08:58:00Z,,s,b,,low\n")
    assert df.loc[0, "message_id"] == "M1"


def test_duplicate_message_ids_are_reported() -> None:
    df = _load(HEADER + "M1,C1,app,2026-08-22T08:58:00Z,,s,a,,low\n"
                        "M1,C2,app,2026-08-22T09:58:00Z,,s,b,,low\n")
    assert len(df) == 2
    assert df.attrs["ingest"]["duplicate_message_ids"] == ["M1"]


def test_missing_and_unparseable_received_are_reported_separately() -> None:
    df = _load(HEADER + "M1,C1,app,,,s,b,,low\nM2,C2,app,yesterday,,s,b,,low\n")
    assert df.attrs["ingest"]["missing_received_at"] == ["M1"]
    assert df.attrs["ingest"]["unparseable_received_at"] == ["M2"]


def test_header_only_export_gives_empty_frame() -> None:
    df = _load(HEADER)
    assert len(df) == 0 and df.attrs["ingest"]["records_read"] == 0


@pytest.mark.parametrize("content", ["", "\n\n  \n"])
def test_empty_export_is_rejected(content: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        _load(content)


def test_non_utf8_export_is_rejected() -> None:
    with pytest.raises(ValueError, match="UTF-8"):
        load_messages(io.BytesIO(HEADER.encode() + "M1,C1,app,x,,s,\xe9t\xe9,,\n".encode("latin-1")))


@pytest.mark.parametrize(
    ("raw", "utc"),
    [
        ("1405/05/26 14:10:30", "2026-08-17T10:40:30Z"),   # Jalali with seconds
        ("1405-05-26 14:10", "2026-08-17T10:40:00Z"),      # Jalali with dashes
        ("1405/5/6 9:05", "2026-07-28T05:35:00Z"),         # no zero padding
        ("1405/05/26", "2026-08-16T20:30:00Z"),            # date only -> 00:00 Tehran
        ("2026-08-17T10:40:00", "2026-08-17T10:40:00Z"),   # naive ISO is taken as UTC
        ("2026-08-17T14:10:00+03:30", "2026-08-17T10:40:00Z"),
        ("۲۰۲۶-۰۸-۱۷T۱۰:۴۰:۰۰Z", "2026-08-17T10:40:00Z"),   # ISO typed in Persian digits
    ],
)
def test_parse_timestamp_variants(raw: str, utc: str) -> None:
    assert parse_timestamp(raw) == pd.Timestamp(utc)


def test_esfand_30_only_in_leap_years() -> None:
    # 1403 is a leap year, 1405 is not (checked against jdatetime).
    assert parse_timestamp("1403/12/30 10:00") == pd.Timestamp("2025-03-20T06:30:00Z")
    assert pd.isna(parse_timestamp("1405/12/30 10:00"))  # used to roll into 1406/01/01


@pytest.mark.parametrize("raw", ["1405/12/31 10:00", "1405/02/32 10:00", "1405/05/26 25:00",
                                 "1405/00/10 10:00", "1405/05/00 10:00"])
def test_parse_timestamp_impossible_jalali(raw: str) -> None:
    assert pd.isna(parse_timestamp(raw))
