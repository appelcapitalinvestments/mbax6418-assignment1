"""
MBAX 6418 — Assignment 1
Loading the Amazon Reviews '23 Gift Cards data.

Source: Amazon Reviews '23, collected by the McAuley Lab at UC San Diego.
  Dataset site : https://amazon-reviews-2023.github.io
  File         : https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/
                 raw/review_categories/Gift_Cards.jsonl.gz

Gzipped JSON Lines: one review per line. Fields per the assignment spec:
  rating            float in {1,2,3,4,5}
  title             short review title
  text              review body
  verified_purchase bool
  helpful_vote      int
  timestamp         Unix milliseconds
  images            list
  asin              product
  parent_asin       product family
  user_id           reviewer

The file is large and re-downloadable, so it is gitignored (`*.jsonl.gz`)
rather than committed. The assignment says as much: "think about whether the
data file (which is large and re-downloadable) ... belong[s] in the repo —
generally they don't."

Run directly to download and inspect:  python data.py
"""

from __future__ import annotations

import gzip
import json
import urllib.request
from pathlib import Path
from typing import Iterator

DATA_URL = (
    "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/"
    "raw/review_categories/Gift_Cards.jsonl.gz"
)
DATA_PATH = Path(__file__).parent / "Gift_Cards.jsonl.gz"

# Fields worth keeping. Dropping the rest keeps saved output readable and small.
KEEP = ("rating", "title", "text", "verified_purchase", "helpful_vote", "asin")


def download_if_missing(path: Path = DATA_PATH, url: str = DATA_URL) -> Path:
    """Fetch the dataset once. Skips if already on disk."""
    if path.exists():
        print(f"Data already present: {path.name} ({path.stat().st_size / 1e6:.1f} MB)")
        return path

    print(f"Downloading {url}\n  -> {path.name}")
    urllib.request.urlretrieve(url, path)
    print(f"Done: {path.stat().st_size / 1e6:.1f} MB")
    return path


def iter_reviews(path: Path = DATA_PATH, limit: int | None = None) -> Iterator[dict]:
    """Stream reviews one at a time.

    Streaming rather than loading the whole file keeps memory flat and makes
    the "first N rows" reading in Step 2 explicit.
    """
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for i, line in enumerate(handle):
            if limit is not None and i >= limit:
                return
            row = json.loads(line)
            row["row_index"] = i
            yield row


def slim(row: dict) -> dict:
    """Keep the fields we use, plus the row index."""
    out = {k: row.get(k) for k in KEEP}
    out["row_index"] = row.get("row_index")
    return out


def main() -> None:
    """Confirm the file reads before anything is built on top of it.

    The assignment is explicit: "Before building anything, confirm you can
    actually read the file."
    """
    download_if_missing()

    print("\nFirst 3 rows:")
    ratings: list[float] = []
    for row in iter_reviews(limit=3):
        print(f"  [{row['row_index']}] {row['rating']} stars | {row['title']!r}")
        print(f"      {str(row['text'])[:90]!r}")

    print("\nRating distribution over the first 1000 rows:")
    for row in iter_reviews(limit=1000):
        ratings.append(row["rating"])

    total = len(ratings)
    for star in (5.0, 4.0, 3.0, 2.0, 1.0):
        n = ratings.count(star)
        bar = "#" * round(40 * n / total)
        print(f"  {int(star)} star  {n:>4}  {n / total:>6.1%}  {bar}")

    high = sum(1 for r in ratings if r >= 4)
    print(
        f"\n  {high / total:.1%} of the first {total} rows are 4 or 5 stars.\n"
        "  This is the skew the assignment warns about: a model that guessed\n"
        "  POSITIVE every time would look strong on an imbalanced sample.\n"
        "  Step 6 fixes it with balanced sampling."
    )


if __name__ == "__main__":
    main()
