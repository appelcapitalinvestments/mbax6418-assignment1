"""
MBAX 6418 - Assignment 1, Steps 5 and 6
Three-class scoring on a balanced sample, with both emotion methods.

Produces the run that the dashboard and the report are built from, and the
"one balanced run's raw output" the deliverables list requires.

Each review gets:
- three-class sentiment from the LLM, scored against the star rating
- a primary emotion from the LLM
- a primary emotion derived independently from the NRC word list
- the full NRC score vector, so the comparison can be inspected

Run:  python score3.py                 # ~50 per class
      python score3.py --per-class 5   # quick trial
      python score3.py --fresh         # ignore a saved checkpoint and redo everything

Interrupting is safe. Every scored review is written to a checkpoint as it
completes, and re-running the same command resumes from where it stopped. That
matters here: the class endpoint had an outage severe enough to move the
deadline, and a 150-call loop that only saved at the end would lose twenty
minutes of work to one stall.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from classify import (BASE_URL, MAX_RETRIES, MAX_TOKENS, MODEL, REQUEST_TIMEOUT,
                      classify_review_safe)
from emotion import EMOTIONS, primary_emotion
from sample import PER_CLASS, SEED, balanced_sample

RESULTS_DIR = Path(__file__).parent / "results"
CLASSES = ("POSITIVE", "NEUTRAL", "NEGATIVE")


def checkpoint_path(per_class: int) -> Path:
    return RESULTS_DIR / f".step6_partial{per_class}.json"


def load_checkpoint(per_class: int) -> dict[int, dict]:
    """Rows already scored in an interrupted run, keyed by row_index.

    The endpoint went down this week badly enough that the deadline moved. A
    150-call loop that saves only at the end means one stall costs the whole
    run, so every row is written as it completes and a restart picks up where
    the last one stopped.
    """
    path = checkpoint_path(per_class)
    if not path.exists():
        return {}
    try:
        saved = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        print(f"  (checkpoint at {path.name} is unreadable - starting fresh)")
        return {}
    # max_tokens is part of the key on purpose. A checkpoint written under a
    # smaller budget contains failures the current budget would not produce,
    # and resuming onto it would silently carry them into the results file.
    if (saved.get("model") != MODEL
            or saved.get("seed") != SEED
            or saved.get("max_tokens") != MAX_TOKENS):
        print("  (checkpoint was written under different settings - starting fresh)")
        return {}
    return {r["row_index"]: r for r in saved.get("rows", [])}


def save_checkpoint(per_class: int, done: dict[int, dict]) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    checkpoint_path(per_class).write_text(json.dumps({
        "model": MODEL,
        "seed": SEED,
        "max_tokens": MAX_TOKENS,
        "per_class": per_class,
        "rows": list(done.values()),
    }))


def score_one(record: dict) -> None:
    """Fill one sampled row in place: model call, then the word-list read."""
    result = classify_review_safe(record["title"], record["text"])
    if result is None:
        record.update(prediction=None, llm_emotion=None, confidence=None, correct=None)
    else:
        record.update(
            prediction=result.sentiment,
            llm_emotion=result.primary_emotion,
            confidence=result.confidence,
            correct=result.sentiment == record["truth"],
        )

    # Independent word-list read. No model call.
    nrc_top, nrc_scores = primary_emotion(record["title"], record["text"])
    record["nrc_emotion"] = nrc_top
    record["nrc_scores"] = {e: n for e, n in nrc_scores.items() if n}
    record["emotions_agree"] = (
        None if (nrc_top is None or record.get("llm_emotion") is None)
        else nrc_top == record["llm_emotion"]
    )


def run(per_class: int, resume: bool = True) -> list[dict]:
    rows = balanced_sample(per_class=per_class)
    done = load_checkpoint(per_class) if resume else {}
    started = time.time()

    if done:
        print(f"\nResuming: {len(done)} of {len(rows)} reviews already scored.")
        print("Delete results/.step6_partial*.json to force a clean run.")

    print(f"\nScoring {len(rows)} reviews against {MODEL} at {BASE_URL}")
    print(f"Timeout {REQUEST_TIMEOUT:.0f}s per call, {MAX_RETRIES} retries. "
          f"Ctrl+C is safe - progress is saved after every review.\n")

    out: list[dict] = []
    try:
        for i, record in enumerate(rows, 1):
            cached = done.get(record["row_index"])
            if cached is not None:
                out.append(cached)
                continue

            score_one(record)
            done[record["row_index"]] = record
            out.append(record)
            save_checkpoint(per_class, done)

            mark = {True: "ok", False: "MISS", None: "ERR"}[record["correct"]]
            print(
                f"  [{i:>3}/{len(rows)}] {mark:<5} {int(record['rating'])}* "
                f"truth={record['truth']:<8} pred={str(record['prediction']):<8} "
                f"llm={str(record['llm_emotion']):<12} nrc={str(record['nrc_emotion']):<12} "
                f"{str(record['title'])[:28]!r}"
            )
    except KeyboardInterrupt:
        save_checkpoint(per_class, done)
        print(f"\n\nStopped. {len(done)} of {len(rows)} reviews are saved.")
        print(f"Run the same command again to pick up from review {len(done) + 1}.")
        raise SystemExit(130)

    print(f"\nCompleted in {time.time() - started:.1f}s")
    return out



def metrics(rows: list[dict]) -> dict:
    scored = [r for r in rows if r["correct"] is not None]
    correct = sum(1 for r in scored if r["correct"])

    per_class = {}
    for label in CLASSES:
        subset = [r for r in scored if r["truth"] == label]
        hits = sum(1 for r in subset if r["correct"])
        per_class[label] = {
            "n": len(subset),
            "correct": hits,
            "accuracy": hits / len(subset) if subset else None,
        }

    confusion = {t: {p: 0 for p in CLASSES} for t in CLASSES}
    for r in scored:
        if r["prediction"] in CLASSES:
            confusion[r["truth"]][r["prediction"]] += 1

    truth_counts = Counter(r["truth"] for r in scored)
    majority = truth_counts.most_common(1)[0][1] / len(scored) if scored else None

    # Emotion comparison, only over rows where both methods produced an answer.
    comparable = [r for r in rows if r["emotions_agree"] is not None]
    agree = sum(1 for r in comparable if r["emotions_agree"])
    nrc_none = sum(1 for r in rows if r["nrc_emotion"] is None)

    llm_dist = Counter(r["llm_emotion"] for r in rows if r.get("llm_emotion"))
    nrc_dist = Counter(r["nrc_emotion"] for r in rows if r.get("nrc_emotion"))

    # Where they disagree, which pairs come up most.
    pairs = Counter(
        (r["llm_emotion"], r["nrc_emotion"])
        for r in comparable
        if not r["emotions_agree"]
    )

    # Which classes the unusable replies came from. This is not bookkeeping:
    # if failures concentrate in one class, that class is being quietly removed
    # from its own accuracy denominator and every figure below is flattered.
    failed = [r for r in rows if r["correct"] is None]
    failures_by_truth = {c: sum(1 for r in failed if r["truth"] == c) for c in CLASSES}
    sampled_by_truth = Counter(r["truth"] for r in rows)
    failure_rate_by_truth = {
        c: (failures_by_truth[c] / sampled_by_truth[c] if sampled_by_truth[c] else None)
        for c in CLASSES
    }

    # Amazon auto-fills "One Star" ... "Five Stars" as the title when the
    # reviewer leaves it blank, which puts the rating the model is not supposed
    # to see directly into the prompt. Count the exposure so it can be reported.
    placeholders = {"one star", "two stars", "three stars", "four stars", "five stars"}
    leaked = [r for r in rows if str(r.get("title", "")).strip().lower() in placeholders]
    leaked_scored = [r for r in leaked if r["correct"] is not None]

    return {
        "n_attempted": len(rows),
        "n_scored": len(scored),
        "n_failed": len(rows) - len(scored),
        "failures_by_truth": failures_by_truth,
        "failure_rate_by_truth": failure_rate_by_truth,
        "rating_leak": {
            "note": "reviews whose title is Amazon's auto-generated 'N Stars' placeholder, "
                    "which exposes the rating to a model that is not supposed to see it",
            "n": len(leaked),
            "share_of_sample": len(leaked) / len(rows) if rows else None,
            "by_truth": {c: sum(1 for r in leaked if r["truth"] == c) for c in CLASSES},
            "accuracy_on_leaked": (
                sum(1 for r in leaked_scored if r["correct"]) / len(leaked_scored)
                if leaked_scored else None
            ),
            "accuracy_on_clean": (
                lambda cl: sum(1 for r in cl if r["correct"]) / len(cl) if cl else None
            )([r for r in scored if r not in leaked]),
        },
        "agreement_with_rating": correct / len(scored) if scored else None,
        "majority_class_baseline": majority,
        "per_class": per_class,
        "confusion_truth_by_prediction": confusion,
        "rating_distribution": dict(
            sorted(Counter(int(r["rating"]) for r in rows).items(), reverse=True)
        ),
        "emotion": {
            "n_comparable": len(comparable),
            "n_agree": agree,
            "agreement_rate": agree / len(comparable) if comparable else None,
            "nrc_no_answer": nrc_none,
            "llm_distribution": dict(llm_dist.most_common()),
            "nrc_distribution": dict(nrc_dist.most_common()),
            "top_disagreements": [
                {"llm": llm, "nrc": nrc, "n": n} for (llm, nrc), n in pairs.most_common(10)
            ],
        },
    }


def report(rows: list[dict], m: dict) -> None:
    print("\n" + "=" * 66)
    print("STEPS 5 AND 6 RESULTS - three classes, balanced sample")
    print("=" * 66)

    print(f"\nScored {m['n_scored']} of {m['n_attempted']}"
          + (f" ({m['n_failed']} failed)" if m["n_failed"] else ""))

    if m["n_failed"]:
        print("  Failures by true class - check these are not concentrated:")
        for c in CLASSES:
            n, rate = m["failures_by_truth"][c], m["failure_rate_by_truth"][c]
            flag = "  <-- over-represented" if rate and rate > 1.5 * (m["n_failed"] / m["n_attempted"]) else ""
            print(f"    {c:<9} {n:>3} lost ({rate:.0%} of that class){flag}")
        print("  Any class losing more than its share is being dropped from its")
        print("  own denominator, which inflates the accuracy reported for it.")

    leak = m["rating_leak"]
    if leak["n"]:
        print(f"\nRating leak: {leak['n']} of {m['n_attempted']} sampled reviews "
              f"({leak['share_of_sample']:.0%}) have an auto-generated 'N Stars' title,")
        print("  which shows the model a rating it is not supposed to see.")
        if leak["accuracy_on_leaked"] is not None and leak["accuracy_on_clean"] is not None:
            print(f"    accuracy on those rows     : {leak['accuracy_on_leaked']:.1%}")
            print(f"    accuracy on all other rows : {leak['accuracy_on_clean']:.1%}")
            print("  If those two are close, the leak is not doing the work.")
    print(f"Agreement with the star rating : {m['agreement_with_rating']:.1%}")
    print(f"Majority-class baseline        : {m['majority_class_baseline']:.1%}")
    print("  On a balanced sample the baseline drops to roughly 1/3, so the")
    print("  accuracy figure finally has to stand on its own.")

    print("\nPer-class accuracy:")
    for label, stats in m["per_class"].items():
        if stats["n"]:
            print(f"  {label:<9} {stats['correct']:>3}/{stats['n']:<3} = {stats['accuracy']:.1%}")

    print("\nConfusion matrix (rows = truth, columns = prediction):")
    print(f"  {'':<10}" + "".join(f"{p:>10}" for p in CLASSES))
    for truth in CLASSES:
        cells = "".join(f"{m['confusion_truth_by_prediction'][truth][p]:>10}" for p in CLASSES)
        print(f"  {truth:<10}{cells}")

    neutral = m["confusion_truth_by_prediction"]["NEUTRAL"]
    total_neutral = sum(neutral.values())
    if total_neutral:
        print(f"\n  Where 3-star (NEUTRAL) reviews actually went:")
        for p in CLASSES:
            print(f"    called {p:<9} {neutral[p]:>3}  ({neutral[p]/total_neutral:.0%})")

    e = m["emotion"]
    print("\nEmotion, LLM versus NRC word list:")
    if e["agreement_rate"] is not None:
        print(f"  agree on {e['n_agree']}/{e['n_comparable']} comparable reviews = {e['agreement_rate']:.1%}")
    print(f"  NRC gave no answer on {e['nrc_no_answer']} reviews (no lexicon word matched, or a tie)")
    print(f"  LLM distribution : {e['llm_distribution']}")
    print(f"  NRC distribution : {e['nrc_distribution']}")
    if e["top_disagreements"]:
        print("  most common disagreements (llm -> nrc):")
        for d in e["top_disagreements"][:5]:
            print(f"    {d['llm']:<13} vs {d['nrc']:<13} {d['n']:>3}")

    misses = [r for r in rows if r["correct"] is False]
    print(f"\nMisclassified ({len(misses)}), first 15:")
    for r in misses[:15]:
        print(f"  row {r['row_index']:<8} {int(r['rating'])}* truth={r['truth']:<8} "
              f"pred={r['prediction']:<8} conf={r['confidence']}")
        print(f"      {str(r['title'])[:60]!r} / {str(r['text'])[:90]!r}")


def save(rows: list[dict], m: dict, per_class: int) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"step6_balanced{per_class}.json"
    payload = {
        "run": {
            "steps": [5, 6],
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "endpoint": BASE_URL,
            "model": MODEL,
            "sampling": f"reservoir-sampled {per_class} per class from the full file",
            "seed": SEED,
            "max_tokens": MAX_TOKENS,
            "classes": list(CLASSES),
            "emotions": list(EMOTIONS),
        },
        "metrics": m,
        "rows": rows,
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=PER_CLASS)
    parser.add_argument("--fresh", action="store_true",
                        help="ignore any saved checkpoint and score every review again")
    args = parser.parse_args()

    rows = run(args.per_class, resume=not args.fresh)
    m = metrics(rows)
    report(rows, m)
    path = save(rows, m, args.per_class)

    # The run finished, so the checkpoint has nothing left to protect.
    checkpoint_path(args.per_class).unlink(missing_ok=True)

    print(f"\nSaved to {path.relative_to(Path(__file__).parent)}")
    print("Every number above came from that file. Quote nothing you did not save.")


if __name__ == "__main__":
    main()
