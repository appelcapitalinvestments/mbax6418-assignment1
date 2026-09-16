"""
MBAX 6418 - Assignment 1, reproducibility check

The assignment requires that "results must be repeatable via a fixed seed and
fixed settings." `temperature=0.0` and `seed=6418` are both set, so in
principle every run should return the same answers.

They do not. Two consecutive runs of score3.py on Sep 13 produced different
predictions for the same reviews - one 3-star review came back NEUTRAL in the
first run and NEGATIVE in the second, and several reviews changed their
primary emotion. This script measures how often that happens instead of
leaving it as an anecdote.

Why it happens: a vLLM server batches concurrent requests together, and the
composition of a batch changes the order of floating-point reductions in the
attention and MLP kernels. Different summation order gives slightly different
logits, and near a decision boundary a tiny logit difference flips the argmax
even at temperature 0. The seed controls sampling; it cannot control batch
composition, which depends on what other traffic hits the server at that
moment. On a shared class endpoint, that traffic is other students.

This is worth reporting rather than hiding. "Deterministic settings did not
produce deterministic output, here is the measured rate" is a real finding
about serving LLMs in production, which is what the course is about.

Run:  python check_determinism.py             # 20 reviews, twice
      python check_determinism.py --n 40
"""

from __future__ import annotations

import argparse
from collections import Counter

from classify import MODEL, SEED, TEMPERATURE, classify_review_safe
from sample import balanced_sample


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20,
                        help="reviews to classify twice (default 20 = 40 calls)")
    args = parser.parse_args()

    rows = balanced_sample(per_class=max(1, args.n // 3))[: args.n]
    print(f"\nClassifying the same {len(rows)} reviews twice.")
    print(f"model={MODEL}  temperature={TEMPERATURE}  seed={SEED}")
    print("Identical inputs, identical settings. Any difference is the server.\n")

    first = [classify_review_safe(r["title"], r["text"]) for r in rows]
    second = [classify_review_safe(r["title"], r["text"]) for r in rows]

    sent_diff, emo_diff, conf_diff, unusable = [], [], [], 0

    for row, a, b in zip(rows, first, second):
        if a is None or b is None:
            unusable += 1
            continue
        if a.sentiment != b.sentiment:
            sent_diff.append((row, a.sentiment, b.sentiment))
        if a.primary_emotion != b.primary_emotion:
            emo_diff.append((row, a.primary_emotion, b.primary_emotion))
        if a.confidence != b.confidence:
            conf_diff.append((row, a.confidence, b.confidence))

    comparable = len(rows) - unusable
    if not comparable:
        print("Both passes failed on every review. Nothing to compare.")
        return

    print("=" * 62)
    print(f"Compared {comparable} reviews ({unusable} unusable in one pass or both)\n")
    print(f"  sentiment changed : {len(sent_diff):>3} / {comparable}  "
          f"({len(sent_diff)/comparable:.1%})")
    print(f"  emotion changed   : {len(emo_diff):>3} / {comparable}  "
          f"({len(emo_diff)/comparable:.1%})")
    print(f"  confidence changed: {len(conf_diff):>3} / {comparable}  "
          f"({len(conf_diff)/comparable:.1%})")

    if sent_diff:
        print("\nSentiment flips:")
        for row, a, b in sent_diff:
            print(f"  {int(row['rating'])}* truth={row['truth']:<8} {a} -> {b}"
                  f"   {str(row['title'])[:40]!r}")
        flips = Counter((a, b) for _, a, b in sent_diff)
        print("\n  flip directions:", dict(flips))
        print("  Check whether flips cluster on one class. If they land mostly on")
        print("  NEUTRAL, the instability and the model's weakest class are the")
        print("  same phenomenon: reviews sitting on a decision boundary.")

    if emo_diff and len(emo_diff) <= 15:
        print("\nEmotion changes:")
        for row, a, b in emo_diff:
            print(f"  {a:<13} -> {b:<13}  {str(row['title'])[:40]!r}")

    print("\n" + "=" * 62)
    if not (sent_diff or emo_diff or conf_diff):
        print("No differences. Output was reproducible on this run - but a single")
        print("clean comparison does not prove determinism, it only failed to")
        print("catch it. Report the sample size alongside the result.")
    else:
        print("Output is NOT reproducible under fixed settings. Report the rate")
        print("above and say what it means: any single accuracy figure from this")
        print("endpoint carries run-to-run noise on top of sampling noise, so")
        print("small differences between configurations are not interpretable.")


if __name__ == "__main__":
    main()
