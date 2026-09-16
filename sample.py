"""
MBAX 6418 - Assignment 1, Step 6 (sampling half)
Balanced sampling across the whole file, on a fixed seed.

The assignment's reasoning: "Because reading the first N rows in order
under-represents the rarer classes, instead pull a balanced group from the
whole file - a roughly equal number from each class, picked with a fixed random
seed so the same set comes up every time - around 50 per class."

Step 2 proved the point empirically. The first 100 rows held 93 POSITIVE and
7 NEGATIVE, so a model answering POSITIVE unconditionally would have scored
92.9%. Any accuracy figure from that sample is nearly meaningless.

Reservoir sampling is used so the whole file is considered without holding it
in memory. Each class gets its own reservoir, so rare classes are drawn from
every row that exists rather than from whatever appears early.

Run directly to inspect a sample without calling the model:
    python sample.py
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from data import DATA_PATH, download_if_missing, iter_reviews, slim
from prompt import rating_to_label

SEED = 6418
PER_CLASS = 50
CLASSES = ("POSITIVE", "NEUTRAL", "NEGATIVE")


def balanced_sample(
    per_class: int = PER_CLASS,
    seed: int = SEED,
    path: Path = DATA_PATH,
) -> list[dict]:
    """Draw `per_class` reviews from each sentiment class across the whole file.

    Reservoir sampling: every row in the file has an equal chance of ending up
    in its class's sample, regardless of where it sits in the file. Seeded, so
    the same rows come back every run.
    """
    download_if_missing(path)
    rng = random.Random(seed)

    reservoirs: dict[str, list[dict]] = {c: [] for c in CLASSES}
    seen: Counter[str] = Counter()

    for row in iter_reviews(path):
        label = rating_to_label(row["rating"])
        seen[label] += 1
        pool = reservoirs[label]

        if len(pool) < per_class:
            pool.append(row)
        else:
            # Standard reservoir step: the nth item replaces a random slot
            # with probability per_class/n.
            j = rng.randrange(seen[label])
            if j < per_class:
                pool[j] = row

    sample = [slim(r) for c in CLASSES for r in reservoirs[c]]
    for record in sample:
        record["truth"] = rating_to_label(record["rating"])

    # Shuffle so the run does not process all POSITIVEs first. Any per-class
    # drift in the endpoint over time would otherwise land on one class.
    rng.shuffle(sample)

    print(f"Population scanned: {sum(seen.values()):,} reviews")
    for c in CLASSES:
        print(f"  {c:<9} {seen[c]:>8,} in file  ->  {len(reservoirs[c]):>3} sampled")

    return sample


def main() -> None:
    sample = balanced_sample()

    print(f"\nSample size: {len(sample)}")
    print("Class balance in the sample:", dict(Counter(r["truth"] for r in sample)))
    print("Star distribution in the sample:",
          dict(sorted(Counter(int(r["rating"]) for r in sample).items(), reverse=True)))

    print("\nDeterminism check - redrawing with the same seed:")
    again = balanced_sample()
    same = [a["row_index"] for a in sample] == [b["row_index"] for b in again]
    print(f"  identical row set and order: {same}")
    if not same:
        print("  WARNING: sampling is not reproducible. Any published number would be unverifiable.")

    print("\nFirst 5 sampled reviews:")
    for record in sample[:5]:
        print(f"  row {record['row_index']:<8} {int(record['rating'])}* {record['truth']:<9} "
              f"{str(record['title'])[:50]!r}")


if __name__ == "__main__":
    main()
