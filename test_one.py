"""
MBAX 6418 — Assignment 1, Step 1 spot check.

Dobolyi's Step 1 question: "does a quick spot-check on obviously positive and
negative reviews come out right?"

This answers it before any money or time goes into a 100-row run. Each case is
hand-written and hand-labeled. Several deliberately probe the edge cases the
prompt claims to handle, because a prompt that only works on easy cases is a
prompt that has not been tested.

Run:  python test_one.py
"""

from classify import classify_review_safe

# (title, text, expected_label, what this case is testing)
CASES = [
    (
        "Perfect gift",
        "Bought this for my sister's birthday and she loved it. Arrived instantly and worked exactly as described.",
        "POSITIVE",
        "obvious positive",
    ),
    (
        "Total waste of money",
        "The code never arrived. Customer service ignored three emails. Do not buy this.",
        "NEGATIVE",
        "obvious negative",
    ),
    (
        "Great",
        "",
        "POSITIVE",
        "terse positive, empty body",
    ),
    (
        "Nope",
        "Didn't work.",
        "NEGATIVE",
        "terse negative — brevity is not neutrality",
    ),
    (
        "Love it!!",
        "Honestly this was a nightmare. The card had a zero balance and I had to fight for a refund.",
        "NEGATIVE",
        "title and body disagree — prompt says weight the body",
    ),
    (
        "Had a problem at first",
        "The first code was invalid, but support sent a replacement within an hour. Ended up very happy.",
        "POSITIVE",
        "problem resolved to satisfaction",
    ),
    (
        "garbage",
        "absolute garbage do not bother",
        "NEGATIVE",
        "angry with no stated reason",
    ),
]


def main() -> None:
    passed = 0
    failed = []

    print(f"Running {len(CASES)} spot-check cases\n")

    for title, text, expected, why in CASES:
        result = classify_review_safe(title, text)

        if result is None:
            failed.append((title, why, "no usable reply"))
            print(f"  ERROR   {why:<45} (no usable reply)")
            continue

        ok = result.sentiment == expected
        passed += ok
        mark = "ok" if ok else "MISS"
        print(
            f"  {mark:<7} {why:<45} "
            f"expected {expected:<8} got {result.sentiment:<8} "
            f"conf {result.confidence:.2f}"
        )
        if not ok:
            failed.append((title, why, f"expected {expected}, got {result.sentiment}"))

    print(f"\n{passed}/{len(CASES)} correct")

    if failed:
        print("\nCases to look at before scaling to 100 rows:")
        for title, why, detail in failed:
            print(f"  - {why}: {detail}")
        print(
            "\nA miss here is information, not a bug. Decide whether the prompt's "
            "definition needs another exclusion bullet, or whether your own label "
            "was the debatable one."
        )
    else:
        print("\nAll cases pass. The prompt is ready for the Step 2 scoring run.")


if __name__ == "__main__":
    main()
