"""
MBAX 6418 — Assignment 1, Step 2
Score a 100-row first batch against the star rating.

The assignment's requirements for this step:
  - "Score a 100-row first batch and see how the model does against the
     'correct answer' you work out from the rating (>=4 positive, else negative)."
  - "The model must never see the rating - it's only for checking afterwards."
  - "at minimum, be able to say how often the model agrees with the rating,
     which reviews it gets wrong, and a feel for how often it's right on each class."

Everything is written to results/ as JSON. That file is the evidence base for
the dashboard and the README. Step 7 says to check the numbers on the page
against the numbers saved here, so nothing gets quoted that was not saved.

Run:  python score.py              # first 100 rows
      python score.py --limit 25   # smaller trial first
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from classify import MODEL, BASE_URL, classify_review_safe
from data import download_if_missing, iter_reviews, slim
from prompt import rating_to_label

RESULTS_DIR = Path(__file__).parent / "results"
LABELS = ("POSITIVE", "NEGATIVE")


def run(limit: int) -> list[dict]:
    """Classify the first `limit` reviews and record every outcome."""
    download_if_missing()
    rows = []
    started = time.time()

    print(f"Scoring first {limit} rows against {MODEL} at {BASE_URL}\n")

    for row in iter_reviews(limit=limit):
        record = slim(row)
        record["truth"] = rating_to_label(record["rating"])

        result = classify_review_safe(record["title"], record["text"])
        if result is None:
            record.update(prediction=None, confidence=None, correct=None)
        else:
            record.update(
                prediction=result.sentiment,
                confidence=result.confidence,
                correct=result.sentiment == record["truth"],
            )

        rows.append(record)

        mark = {True: "ok", False: "MISS", None: "ERR"}[record["correct"]]
        idx = record["row_index"] + 1
        print(
            f"  [{idx:>3}/{limit}] {mark:<5} "
            f"{int(record['rating'])}* truth={record['truth']:<8} "
            f"pred={str(record['prediction']):<8} {str(record['title'])[:38]!r}"
        )

    print(f"\nCompleted in {time.time() - started:.1f}s")
    return rows


def metrics(rows: list[dict]) -> dict:
    """Everything the assignment asks you to be able to state."""
    scored = [r for r in rows if r["correct"] is not None]
    failures = len(rows) - len(scored)
    correct = sum(1 for r in scored if r["correct"])

    per_class = {}
    for label in LABELS:
        subset = [r for r in scored if r["truth"] == label]
        hits = sum(1 for r in subset if r["correct"])
        per_class[label] = {
            "n": len(subset),
            "correct": hits,
            "accuracy": hits / len(subset) if subset else None,
        }

    # confusion[truth][prediction]
    confusion = {t: {p: 0 for p in LABELS} for t in LABELS}
    for r in scored:
        if r["prediction"] in LABELS:
            confusion[r["truth"]][r["prediction"]] += 1

    truth_counts = Counter(r["truth"] for r in scored)
    majority = truth_counts.most_common(1)[0][1] / len(scored) if scored else None

    return {
        "n_attempted": len(rows),
        "n_scored": len(scored),
        "n_failed": failures,
        "agreement_with_rating": correct / len(scored) if scored else None,
        "majority_class_baseline": majority,
        "per_class": per_class,
        "confusion_truth_by_prediction": confusion,
        "rating_distribution": dict(
            sorted(Counter(int(r["rating"]) for r in rows).items(), reverse=True)
        ),
    }


def report(rows: list[dict], m: dict) -> None:
    print("\n" + "=" * 62)
    print("STEP 2 RESULTS")
    print("=" * 62)

    print(f"\nScored {m['n_scored']} of {m['n_attempted']} rows"
          + (f" ({m['n_failed']} failed to classify)" if m["n_failed"] else ""))
    print(f"Agreement with the star rating : {m['agreement_with_rating']:.1%}")
    print(f"Always-guess-majority baseline : {m['majority_class_baseline']:.1%}")

    gap = m["agreement_with_rating"] - m["majority_class_baseline"]
    print(f"  The model beats that baseline by {gap:+.1%}.")
    print("  On a skewed sample the baseline is the number that keeps you honest:")
    print("  a high accuracy that barely clears it is not evidence of much.")

    print("\nPer-class accuracy:")
    for label, stats in m["per_class"].items():
        if stats["n"]:
            print(f"  {label:<9} {stats['correct']:>3}/{stats['n']:<3} = {stats['accuracy']:.1%}")
        else:
            print(f"  {label:<9} no examples in this sample")

    print("\nConfusion matrix (rows = truth, columns = prediction):")
    print(f"  {'':<10}" + "".join(f"{p:>10}" for p in LABELS))
    for truth in LABELS:
        cells = "".join(f"{m['confusion_truth_by_prediction'][truth][p]:>10}" for p in LABELS)
        print(f"  {truth:<10}{cells}")

    print("\nRating distribution in this sample:")
    for star, n in m["rating_distribution"].items():
        print(f"  {star} star  {n:>3}  {'#' * round(40 * n / m['n_attempted'])}")

    misses = [r for r in rows if r["correct"] is False]
    print(f"\nReviews the model got wrong ({len(misses)}):")
    for r in misses:
        print(f"  row {r['row_index']:<4} {int(r['rating'])}* "
              f"truth={r['truth']:<8} pred={r['prediction']:<8} conf={r['confidence']}")
        print(f"      title: {str(r['title'])[:70]!r}")
        print(f"      text : {str(r['text'])[:110]!r}")
    if not misses:
        print("  none")


def save(rows: list[dict], m: dict, limit: int) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"step2_first{limit}.json"
    payload = {
        "run": {
            "step": 2,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "endpoint": BASE_URL,
            "model": MODEL,
            "sampling": f"first {limit} rows in file order",
        },
        "metrics": m,
        "rows": rows,
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    rows = run(args.limit)
    m = metrics(rows)
    report(rows, m)
    path = save(rows, m, args.limit)

    print(f"\nSaved to {path.relative_to(Path(__file__).parent)}")
    print("Every number above came from that file. Quote nothing you did not save.")


if __name__ == "__main__":
    main()
