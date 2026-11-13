"""Score the classifier against the hand-labelled validation set.

    python -m eval.evaluate --mode keywords
    python -m eval.evaluate --mode llm          # uses LLM_* env vars and the disk cache
    python -m eval.evaluate --mode llm --audit  # high-severity audit set (borderline cases)

Reports category accuracy, a confusion table, and precision/recall of the
high-severity flag (what drives urgency), plus every disagreement.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
from collections import Counter
from pathlib import Path

import pandas as pd

from app.classify import classify_messages
from app.config import CATEGORIES, get_settings
from app.ingest import load_messages

HERE = Path(__file__).resolve().parent
LABELS = HERE / "validation_labels.csv"
AUDIT = HERE / "severity_audit.csv"
DATA = HERE.parent.parent / "data"
SOURCE = DATA / "messages_sample.csv"


def load_labels() -> pd.DataFrame:
    with LABELS.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return pd.DataFrame(rows).assign(high=lambda d: d["high"].str.lower() == "true")


def evaluate(mode: str, source: Path = SOURCE) -> dict:
    labels = load_labels()
    msgs = load_messages(source).set_index("message_id").loc[labels["message_id"]].reset_index()
    settings = get_settings()
    if mode == "keywords":
        settings = dataclasses.replace(settings, llm_base_url=None)
    run = classify_messages(msgs, settings)
    pred_cat = [lab.category for lab in run.labels]
    pred_high = [lab.high_severity for lab in run.labels]
    gold_cat, gold_high = labels["category"].tolist(), labels["high"].tolist()

    tp = sum(p and g for p, g in zip(pred_high, gold_high))
    fp = sum(p and not g for p, g in zip(pred_high, gold_high))
    fn = sum(g and not p for p, g in zip(pred_high, gold_high))
    return {
        "mode": mode, "n": len(labels), "stats": run.stats,
        "category_accuracy": sum(p == g for p, g in zip(pred_cat, gold_cat)) / len(labels),
        "high_precision": tp / (tp + fp) if tp + fp else 1.0,
        "high_recall": tp / (tp + fn) if tp + fn else 1.0,
        "high_tp_fp_fn": (tp, fp, fn),
        "confusion": Counter(zip(gold_cat, pred_cat)),
        "errors": [
            (mid, g, p, gh, ph, subj or body[:60])
            for mid, g, p, gh, ph, subj, body in zip(
                labels["message_id"], gold_cat, pred_cat, gold_high, pred_high,
                labels["subject"], labels["body"])
            if g != p or gh != ph
        ],
    }


def evaluate_audit(mode: str) -> dict:
    """High-severity only, on borderline cases from both exports (expected values
    follow the user-approved definition; see severity_audit.csv)."""
    with AUDIT.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    settings = get_settings()
    if mode == "keywords":
        settings = dataclasses.replace(settings, llm_base_url=None)
    wrong = []
    for export in sorted({r["export"] for r in rows}):
        want = {r["message_id"]: (r["high"] == "true", r["rule"]) for r in rows if r["export"] == export}
        msgs = load_messages(DATA / export).set_index("message_id").loc[list(want)].reset_index()
        run = classify_messages(msgs, settings)
        for mid, lab in zip(msgs["message_id"], run.labels):
            if lab.high_severity != want[mid][0]:
                wrong.append((export, mid, want[mid][0], want[mid][1]))
    return {"mode": mode, "n": len(rows), "correct": len(rows) - len(wrong), "wrong": wrong}


def print_report(r: dict) -> None:
    print(f"== {r['mode']}  (n={r['n']})  {r['stats']}")
    tp, fp, fn = r["high_tp_fp_fn"]
    print(f"category accuracy: {r['category_accuracy']:.1%}")
    print(f"high severity: precision {r['high_precision']:.1%}  recall {r['high_recall']:.1%}  (tp={tp} fp={fp} fn={fn})")
    short = {c: c[:7] for c in CATEGORIES}
    print("confusion (rows = hand label, cols = predicted):")
    print("            " + " ".join(f"{short[c]:>8}" for c in CATEGORIES))
    for g in CATEGORIES:
        print(f"  {short[g]:>8}  " + " ".join(f"{r['confusion'].get((g, p), 0):>8}" for p in CATEGORIES))
    for mid, g, p, gh, ph, text in r["errors"]:
        what = []
        if g != p:
            what.append(f"category {g} -> {p}")
        if gh != ph:
            what.append(f"high {gh} -> {ph}")
        print(f"  {mid}: {', '.join(what)}  | {text}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["keywords", "llm"], default="keywords")
    parser.add_argument("--audit", action="store_true", help="score the high-severity audit set")
    args = parser.parse_args()
    if args.audit:
        r = evaluate_audit(args.mode)
        print(f"== audit {r['mode']}: {r['correct']}/{r['n']} high-severity flags as defined")
        for export, mid, want, rule in r["wrong"]:
            print(f"  {export} {mid}: expected high={want} ({rule})")
    else:
        print_report(evaluate(args.mode))


if __name__ == "__main__":
    main()
