"""Loading the support-system CSV export into a DataFrame.

Every row that has a ``message_id`` is kept, even when its timestamps cannot
be parsed: the CLI contract is "one entry per message in the export".
Records without an id (``,,,,,,,,``, a line of spaces) cannot be reported and
are skipped. Every record is accounted for in ``df.attrs["ingest"]``.

We parse with the stdlib ``csv`` module rather than ``pandas.read_csv`` so
that we see every record: pandas silently drops whitespace-only lines and
cannot tell us about short or overlong rows.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import IO, Any

import pandas as pd

from .jalali import parse_timestamps

COLUMNS: list[str] = [
    "message_id",
    "customer_id",
    "channel",
    "received_at",
    "answered_at",
    "subject",
    "body",
    "order_ref",
    "severity_hint",
]
REQUIRED: tuple[str, ...] = ("message_id", "customer_id", "received_at", "body")


def _read_text(source: str | Path | IO[bytes] | IO[str]) -> str:
    data = Path(source).read_bytes() if isinstance(source, (str, Path)) else source.read()
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"export is not valid UTF-8: {exc}") from exc
    return data.lstrip("﻿")


def load_messages(source: str | Path | IO[bytes] | IO[str]) -> pd.DataFrame:
    """Read a support export and return one row per message, in file order."""
    try:
        records = list(csv.reader(io.StringIO(_read_text(source), newline="")))
    except csv.Error as exc:
        raise ValueError(f"could not read CSV: {exc}") from exc

    def blank(rec: list[str]) -> bool:
        return all(field.strip() == "" for field in rec)

    while records and blank(records[0]):
        records.pop(0)
    if not records:
        raise ValueError("export is empty")
    header = [h.strip().lstrip("﻿").lower() for h in records[0]]
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise ValueError(f"export is missing columns: {', '.join(missing)}")
    position = {name: header.index(name) for name in COLUMNS if name in header}

    rows: list[dict[str, str]] = []
    blank_records = no_id = 0
    short_rows: list[str] = []
    long_rows: list[str] = []
    for rec in records[1:]:
        if blank(rec):
            blank_records += 1
            continue
        row = {c: (rec[i] if i < len(rec) else "") for c, i in position.items()}
        row = {c: row.get(c, "") for c in COLUMNS}
        row["message_id"] = row["message_id"].strip()
        if not row["message_id"]:
            no_id += 1
            continue
        if len(rec) < len(header):
            short_rows.append(row["message_id"])
        elif len(rec) > len(header):
            long_rows.append(row["message_id"])
        rows.append(row)

    df = pd.DataFrame(rows, columns=COLUMNS, dtype=object).fillna("")
    for col in ("customer_id", "channel", "order_ref", "severity_hint"):
        df[col] = df[col].str.strip()
    df["severity_hint"] = df["severity_hint"].str.lower()

    raw_received = df["received_at"].str.strip()
    raw_answered = df["answered_at"].str.strip()
    df["received_at"] = parse_timestamps(df["received_at"])
    df["answered_at"] = parse_timestamps(df["answered_at"])
    # Someone filled in answered_at but we cannot read it: still answered
    # ("once someone has answered it, it's handled"), just at an unknown time.
    df["answered_time_unknown"] = df["answered_at"].isna() & (raw_answered != "")

    df.attrs["ingest"] = {
        "records_read": len(records) - 1,
        "rows_kept": int(len(df)),
        "blank_rows_skipped": blank_records,
        "rows_without_id_skipped": no_id,
        "short_rows": short_rows,
        "rows_with_extra_fields": long_rows,
        "duplicate_message_ids": sorted(df.loc[df["message_id"].duplicated(), "message_id"].unique()),
        "missing_received_at": df.loc[raw_received == "", "message_id"].tolist(),
        "unparseable_received_at": df.loc[
            df["received_at"].isna() & (raw_received != ""), "message_id"
        ].tolist(),
        "unparseable_answered_at": df.loc[df["answered_time_unknown"], "message_id"].tolist(),
        "answered_before_received": df.loc[
            df["answered_at"].notna() & (df["answered_at"] < df["received_at"]), "message_id"
        ].tolist(),
    }
    return df
