"""Write predictions.csv for an export (README deliverable 4).

    python -m scripts.make_predictions --input ../data/eval_messages.csv \
        --now 2026-04-15T07:00:00Z --output ../predictions.csv

Uses exactly the CLI pipeline (same LLM cache), one row per message in the export,
header ``message_id,category,is_urgent``.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.analysis import analyze, parse_now


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--now", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    report = analyze(args.input, now=parse_now(args.now), include_details=True)
    with args.output.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["message_id", "category", "is_urgent"])
        for m in report["messages"]:
            w.writerow([m["message_id"], m["category"], "true" if m["is_urgent"] else "false"])
    print(f"wrote {args.output}: {len(report['messages'])} rows, "
          f"{len(report['urgent_message_ids'])} urgent, classification={report['classification']}")


if __name__ == "__main__":
    main()
