"""
MBAX 6418 - Assignment 1, Step 5 (word-list half)

The second, independent take on a review's primary emotion. No model calls:
score each review's words against the NRC Word-Emotion Association Lexicon,
sum per emotion, take the highest.

Assignment wording: "A word list derives it - score each review's words against
an NRC emotion word list (a public list linking words to emotions: anger,
anticipation, disgust, fear, joy, sadness, surprise, trust), add the scores per
emotion, and take the highest as the answer. This needs no model calls and runs
over your existing predictions."

LICENSING - why the lexicon is not in this repo
-----------------------------------------------
The NRC Word-Emotion Association Lexicon (Mohammad & Turney) is free for
non-commercial research and educational use, but its terms state plainly:

    "Do not redistribute the data. Direct interested parties to the lexicon
     home page."

So the file is NOT committed here. Download it yourself from the official page
and drop it in this directory. It is gitignored.

    https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm

Expected format: tab-separated, three columns, one row per word-emotion pair.

    word    emotion    0-or-1
    abandon    anger    1
    abandon    anticipation    0

Run directly to check the lexicon loads:  python emotion.py
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent

# The eight emotions the assignment names. The NRC file also carries two
# sentiment rows (positive/negative) which are deliberately excluded here,
# because this method is meant to be an independent read on *emotion*.
EMOTIONS = (
    "anger",
    "anticipation",
    "disgust",
    "fear",
    "joy",
    "sadness",
    "surprise",
    "trust",
)

# Filenames the lexicon commonly ships under. Checked in order.
CANDIDATE_FILES = (
    "NRC-Emotion-Lexicon-Wordlevel-v0.92.txt",
    "NRC-emotion-lexicon-wordlevel-alphabetized-v0.92.txt",
    "NRC-Emotion-Lexicon-Wordlevel-v0.92.tsv",
    "nrc_emotion_lexicon.txt",
)

_TOKEN = re.compile(r"[a-z']+")

_lexicon: dict[str, frozenset[str]] | None = None


def lexicon_path() -> Path | None:
    for name in CANDIDATE_FILES:
        candidate = HERE / name
        if candidate.exists():
            return candidate
    return None


def load_lexicon(force: bool = False) -> dict[str, frozenset[str]]:
    """word -> frozenset of associated emotions. Cached after first load."""
    global _lexicon
    if _lexicon is not None and not force:
        return _lexicon

    path = lexicon_path()
    if path is None:
        raise FileNotFoundError(
            "NRC emotion lexicon not found in this directory.\n\n"
            "It is not committed to the repo because its licence forbids\n"
            "redistribution. Download it from the official page:\n\n"
            "    https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm\n\n"
            "Save the word-level file here as one of:\n"
            + "\n".join(f"    {n}" for n in CANDIDATE_FILES)
        )

    mapping: dict[str, set[str]] = {}
    skipped = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 3:
            skipped += 1
            continue
        word, emotion, flag = parts[0].strip().lower(), parts[1].strip().lower(), parts[2].strip()
        if emotion not in EMOTIONS or flag != "1":
            continue
        mapping.setdefault(word, set()).add(emotion)

    if not mapping:
        raise ValueError(
            f"Loaded {path.name} but found no usable word-emotion rows.\n"
            f"Expected tab-separated 'word<TAB>emotion<TAB>0|1'. "
            f"{skipped} lines did not have three tab-separated fields."
        )

    _lexicon = {w: frozenset(e) for w, e in mapping.items()}
    return _lexicon


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def emotion_scores(title: str, text: str) -> dict[str, int]:
    """Raw per-emotion counts across the review's words.

    Title and body are both scored. A word associated with several emotions
    contributes one to each, which is how the lexicon is built to be used.
    """
    lex = load_lexicon()
    counts = Counter({e: 0 for e in EMOTIONS})
    for token in tokenize(f"{title} {text}"):
        for emotion in lex.get(token, ()):
            counts[emotion] += 1
    return dict(counts)


def primary_emotion(title: str, text: str) -> tuple[str | None, dict[str, int]]:
    """Highest-scoring emotion, plus the full score vector.

    Returns (None, scores) when no lexicon word matched, or when the top score
    is a tie. Reporting a tie as "no answer" is more honest than silently
    taking whichever emotion happens to sort first, and the rate of ties is
    itself worth stating in the report.
    """
    scores = emotion_scores(title, text)
    top = max(scores.values())
    if top == 0:
        return None, scores
    winners = [e for e, n in scores.items() if n == top]
    if len(winners) > 1:
        return None, scores
    return winners[0], scores


def main() -> None:
    try:
        lex = load_lexicon()
    except FileNotFoundError as exc:
        print(exc)
        return

    print(f"Lexicon loaded: {lexicon_path().name}")
    print(f"  {len(lex):,} words carry at least one of the eight emotions")

    per_emotion = Counter()
    for emotions in lex.values():
        per_emotion.update(emotions)
    print("\nWords per emotion:")
    for emotion in EMOTIONS:
        print(f"  {emotion:<13} {per_emotion[emotion]:>6,}")

    print("\nSample scoring:")
    samples = [
        ("Perfect gift", "My sister loved it, wonderful surprise, arrived instantly"),
        ("Total waste", "Furious. The code never arrived and support ignored me."),
        ("Easy to use", "Very easy to use. I wish I knew about it earlier"),
        ("ok", "fine"),
    ]
    for title, text in samples:
        winner, scores = primary_emotion(title, text)
        hits = {e: n for e, n in scores.items() if n}
        print(f"  {title!r}")
        print(f"      primary: {winner}   scores: {hits or 'no lexicon words matched'}")


if __name__ == "__main__":
    main()
