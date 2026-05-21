"""
Keyword validation & A/B comparison framework.

Usage:
    python validate.py                        # score current system vs golden dataset
    python validate.py --compare              # current vs baseline (old simple list)
    python validate.py --diagnose "headline"  # why did this get missed? what would fix it?
    python validate.py --add "headline" yes   # append a new case to golden_dataset.csv
    python validate.py --add "headline" no    # append a negative case

The golden dataset lives in golden_dataset.csv — edit it directly or use --add.
Any headline the pipeline missed in real life should go in there with expected=yes.
"""

import csv
import sys
import os

# ---------------------------------------------------------------------------
# BASELINE SYSTEM — the original simple keyword list before compound rules
# Used only for A/B comparison to show what the new system gains/loses.
# ---------------------------------------------------------------------------
_BASELINE_KEYWORDS = [
    "drown", "drowning", "drowned",
    "pulled from water", "submerged", "submersion",
    "body found", "body recovered", "body retrieved",
    "water rescue", "rescued from water",
    "missing swimmer", "search swimmer",
    "near-drowning", "near drowning",
    "swept off", "swept into", "swept away", "washed off rocks", "washed into",
    "fell into water", "fell into the water", "fell overboard",
    "overboard", "rock fishing", "missing fisherman",
    "search and rescue", "marine rescue", "coast guard",
]

def _baseline_match(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _BASELINE_KEYWORDS)


# ---------------------------------------------------------------------------
# CURRENT SYSTEM — imported live so changes to search_tools.py are reflected
# ---------------------------------------------------------------------------
from drowning_monitor.tools.search_tools import (
    _has_keyword, KEYWORDS, COMPOUND_KEYWORDS, _WATER_BODIES, _WATER_PEOPLE
)

DATASET_PATH = os.path.join(os.path.dirname(__file__), "golden_dataset.csv")


# ---------------------------------------------------------------------------
# DIAGNOSTIC ENGINE
# ---------------------------------------------------------------------------

def _explain(text: str) -> str:
    """Return a human-readable explanation of WHY a text matched (or didn't)."""
    lower = text.lower()
    matched_strong = [kw for kw in KEYWORDS if kw in lower]
    if matched_strong:
        return f"MATCH  -- strong keyword: {matched_strong}"
    for i, (group_a, group_b) in enumerate(COMPOUND_KEYWORDS):
        matched_a = [a for a in group_a if a in lower]
        matched_b = [b for b in group_b if b in lower]
        if matched_a and matched_b:
            return f"MATCH  -- compound rule #{i+1}: '{matched_a[0]}' + '{matched_b[0]}'"
    return "NO MATCH"


def _diagnose(text: str):
    """
    For a headline that was NOT matched, show:
    - Which words in the text appear in Group A or Group B of each rule
    - What's missing to complete a match
    - Suggested fix (smallest addition that would make it match)
    """
    lower = text.lower()
    words = lower.split()

    print(f"\n  Input:  \"{text}\"")
    print(f"  Result: {_explain(text)}")
    print()

    if _has_keyword(text):
        print("  (Already matches — no fix needed.)")
        return

    print("  --- WHY IT MISSED ---")

    # Check near-misses for strong keywords
    near_strong = []
    for kw in KEYWORDS:
        kw_words = kw.split()
        overlap = [w for w in kw_words if any(w in word for word in words)]
        if overlap and kw not in lower:
            near_strong.append((kw, overlap))
    if near_strong:
        print(f"  Near-miss strong keywords (partial word overlap):")
        for kw, overlaps in near_strong[:5]:
            print(f"    '{kw}'  (text has: {overlaps})")

    # Check each compound rule for partial matches
    print()
    print("  Compound rule analysis:")
    for i, (group_a, group_b) in enumerate(COMPOUND_KEYWORDS):
        matched_a = [a for a in group_a if a in lower]
        matched_b = [b for b in group_b if b in lower]
        has_a = bool(matched_a)
        has_b = bool(matched_b)

        if has_a and not has_b:
            print(f"  Rule #{i+1}: Has Group A ('{matched_a[0]}') but NO Group B match.")
            print(f"    --> Add one of these to Group B or to the text's coverage: {group_b[:8]}...")
        elif has_b and not has_a:
            print(f"  Rule #{i+1}: Has Group B ('{matched_b[0]}') but NO Group A match.")
            print(f"    --> Add one of these to Group A or to the text's coverage: {group_a[:5]}...")
        elif not has_a and not has_b:
            pass  # no relevance, skip

    # Suggest what to add
    print()
    print("  --- SUGGESTED FIX ---")
    # Find any words in the text that look like they could be water-related action verbs
    action_clues = ["found", "located", "spotted", "seen", "discovered", "reported",
                    "jumped", "fell", "slipped", "entered", "went into", "went under",
                    "struck", "hit", "trapped", "stranded"]
    found_clues = [c for c in action_clues if c in lower]

    water_clues = [w for w in _WATER_BODIES if w in lower]
    people_clues = [w for w in _WATER_PEOPLE if w in lower]

    if found_clues and water_clues:
        print(f"  Text contains action words {found_clues} + water body {water_clues}")
        print(f"  --> Consider adding '{found_clues[0]}' to a compound rule Group A")
    elif water_clues:
        print(f"  Text contains water body words: {water_clues}")
        print(f"  --> Text has water context but no action/outcome trigger — add an action word to a Group A")
    elif people_clues:
        print(f"  Text contains water-person words: {people_clues}")
        print(f"  --> Text has person context but no water body — check if this is truly a water incident")
    else:
        print(f"  No obvious water-related words found in this text.")
        print(f"  --> This may require a new strong keyword. What's the key phrase that signals danger?")
    print()


# ---------------------------------------------------------------------------
# SCORING
# ---------------------------------------------------------------------------

def _load_dataset():
    cases = []
    with open(DATASET_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["headline"].strip().startswith("#"):
                continue
            cases.append({
                "headline": row["headline"].strip(),
                "expected": row["expected"].strip().lower() in ("yes", "true", "1"),
                "notes": row.get("notes", "").strip(),
            })
    return cases


def _score(cases, match_fn, label):
    tp = fp = tn = fn = 0
    false_negatives = []
    false_positives = []

    for c in cases:
        result = match_fn(c["headline"])
        expected = c["expected"]
        if result and expected:
            tp += 1
        elif result and not expected:
            fp += 1
            false_positives.append(c)
        elif not result and expected:
            fn += 1
            false_negatives.append(c)
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0
    recall    = tp / (tp + fn) if (tp + fn) else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

    return {
        "label": label,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "false_negatives": false_negatives,
        "false_positives": false_positives,
    }


def _print_score(s, verbose=True):
    total = s["tp"] + s["fp"] + s["tn"] + s["fn"]
    print(f"\n{'='*65}")
    print(f"  {s['label']}")
    print(f"  {total} test cases")
    print(f"{'='*65}")
    print(f"  True  positives (correctly caught):   {s['tp']}")
    print(f"  True  negatives (correctly ignored):  {s['tn']}")
    print(f"  False positives (noise let through):  {s['fp']}")
    print(f"  False negatives (MISSED incidents):   {s['fn']}")
    print(f"  ---")
    print(f"  Precision (low FP):  {s['precision']:.0%}  (of what we flagged, how much was real?)")
    print(f"  Recall    (low FN):  {s['recall']:.0%}  (of real incidents, how many did we catch?)")
    print(f"  F1 score:            {s['f1']:.0%}")

    if verbose and s["false_negatives"]:
        print(f"\n  MISSED (false negatives) -- these need fixing:")
        for c in s["false_negatives"]:
            print(f"    - \"{c['headline']}\"")
            if c["notes"]:
                print(f"      notes: {c['notes']}")

    if verbose and s["false_positives"]:
        print(f"\n  NOISE (false positives) -- these shouldn't have matched:")
        for c in s["false_positives"]:
            print(f"    + \"{c['headline']}\"")
            print(f"      {_explain(c['headline'])}")
            if c["notes"]:
                print(f"      notes: {c['notes']}")


# ---------------------------------------------------------------------------
# COMPARE MODE
# ---------------------------------------------------------------------------

def _print_comparison(baseline, current):
    print(f"\n{'='*65}")
    print(f"  A/B COMPARISON: Baseline vs Current")
    print(f"{'='*65}")

    # What the new system catches that the baseline missed
    newly_caught = [
        c for c in baseline["false_negatives"]
        if c not in current["false_negatives"]
    ]
    newly_missed = [
        c for c in current["false_negatives"]
        if c not in baseline["false_negatives"]
    ]
    noise_added = [
        c for c in current["false_positives"]
        if c not in baseline["false_positives"]
    ]
    noise_removed = [
        c for c in baseline["false_positives"]
        if c not in current["false_positives"]
    ]

    print(f"\n  Recall:    {baseline['recall']:.0%} --> {current['recall']:.0%}  "
          f"({'improved' if current['recall'] >= baseline['recall'] else 'WORSE'})")
    print(f"  Precision: {baseline['precision']:.0%} --> {current['precision']:.0%}  "
          f"({'improved' if current['precision'] >= baseline['precision'] else 'WORSE'})")
    print(f"  F1:        {baseline['f1']:.0%} --> {current['f1']:.0%}")

    if newly_caught:
        print(f"\n  NEW catches (current catches these, baseline missed):")
        for c in newly_caught:
            print(f"    + \"{c['headline']}\"")
            print(f"      {_explain(c['headline'])}")

    if newly_missed:
        print(f"\n  REGRESSIONS (baseline caught these, current missed):")
        for c in newly_missed:
            print(f"    - \"{c['headline']}\"")

    if noise_added:
        print(f"\n  EXTRA NOISE (current lets through, baseline didn't):")
        for c in noise_added:
            print(f"    ~ \"{c['headline']}\"")

    if noise_removed:
        print(f"\n  NOISE REMOVED (baseline let through, current doesn't):")
        for c in noise_removed:
            print(f"    ~ \"{c['headline']}\"")

    if not newly_caught and not newly_missed and not noise_added and not noise_removed:
        print(f"\n  No difference on this dataset between baseline and current.")


# ---------------------------------------------------------------------------
# ADD MODE
# ---------------------------------------------------------------------------

def _add_case(headline: str, expected: str, notes: str = ""):
    expected_norm = "yes" if expected.lower() in ("yes", "y", "true", "1") else "no"
    with open(DATASET_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([headline, expected_norm, notes])
    match = _has_keyword(headline)
    expected_bool = expected_norm == "yes"
    status = "PASS" if match == expected_bool else "FAIL -- needs a keyword fix"
    print(f"\n  Added: \"{headline}\" (expected={expected_norm})")
    print(f"  Current system: {'MATCH' if match else 'NO MATCH'}  [{status}]")
    if not match and expected_bool:
        print(f"\n  Running diagnosis...")
        _diagnose(headline)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--diagnose" in args:
        idx = args.index("--diagnose")
        text = args[idx + 1] if idx + 1 < len(args) else ""
        if not text:
            print("Usage: python validate.py --diagnose \"your headline here\"")
        else:
            print(f"\n{'='*65}")
            print(f"  DIAGNOSTIC MODE")
            print(f"{'='*65}")
            _diagnose(text)

    elif "--add" in args:
        idx = args.index("--add")
        headline = args[idx + 1] if idx + 1 < len(args) else ""
        expected = args[idx + 2] if idx + 2 < len(args) else "yes"
        notes = args[idx + 3] if idx + 3 < len(args) else ""
        if not headline:
            print("Usage: python validate.py --add \"headline\" yes/no \"optional notes\"")
        else:
            _add_case(headline, expected, notes)

    elif "--compare" in args:
        cases = _load_dataset()
        baseline = _score(cases, _baseline_match, "BASELINE (original simple keyword list)")
        current  = _score(cases, _has_keyword,    "CURRENT  (compound rule system)")
        _print_score(baseline, verbose=False)
        _print_score(current,  verbose=False)
        _print_comparison(baseline, current)

    else:
        # Default: score current system with full detail
        cases = _load_dataset()
        result = _score(cases, _has_keyword, f"CURRENT SYSTEM  ({len(KEYWORDS)} strong keywords, {len(COMPOUND_KEYWORDS)} compound rules)")
        _print_score(result, verbose=True)

        print(f"\n  Run 'python validate.py --compare' to see gains vs the old system.")
        print(f"  Run 'python validate.py --diagnose \"headline\"' to debug a miss.")
        print(f"  Run 'python validate.py --add \"headline\" yes' to log a real missed case.")
        print()
