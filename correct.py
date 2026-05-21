"""
Corrections manager — view, add, and apply manual corrections to incident data.

Usage:
    python correct.py list                          # show all saved corrections
    python correct.py add                           # interactive: add a new correction
    python correct.py add --url URL --field date_of_incident --value 2026-04-19 --reason "was Saturday"
    python correct.py test "phillip island"         # preview which incidents would be corrected
"""

import json
import sys
import os

CORRECTIONS_FILE = os.path.join(os.path.dirname(__file__), "corrections.json")

CORRECTABLE_FIELDS = [
    "date_of_incident",
    "location_name",
    "location_type",
    "state",
    "age_group",
    "gender",
    "outcome",
    "activity",
    "summary",
    "source",
]


# ---------------------------------------------------------------------------
# CORE: load / save / apply
# ---------------------------------------------------------------------------

def load_corrections() -> list:
    with open(CORRECTIONS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return [c for c in data.get("corrections", []) if not c.get("_comment")]


def save_corrections(corrections: list):
    try:
        with open(CORRECTIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data["corrections"] = corrections
    with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _incident_matches(inc: dict, correction: dict) -> bool:
    """Return True if this incident matches this correction rule."""
    url = inc.get("url", "").strip().lower()
    match_url = correction.get("match_url", "").strip().lower()
    if match_url and match_url != "https://example.com/article":
        return match_url in url or url in match_url

    # Fallback: date|location substring match
    fallback = correction.get("match_fallback", "").strip().lower()
    if fallback:
        date_part, _, loc_part = fallback.partition("|")
        inc_date = inc.get("date_of_incident", "").strip().lower()
        inc_loc  = inc.get("location_name", "").strip().lower()
        date_ok  = not date_part or date_part in inc_date or inc_date in date_part
        loc_ok   = not loc_part  or loc_part  in inc_loc  or inc_loc  in loc_part
        return date_ok and loc_ok

    return False


def apply_corrections(incidents: list) -> tuple[list, int]:
    """
    Apply all corrections to a list of incidents in-place.
    Returns (corrected_list, number_of_corrections_applied).
    """
    corrections = load_corrections()
    applied = 0
    for inc in incidents:
        for correction in corrections:
            if _incident_matches(inc, correction):
                for field, value in correction.get("fields", {}).items():
                    old = inc.get(field, "")
                    if old != value:
                        print(f"  [CORRECTION] {field}: '{old}' -> '{value}'  ({correction.get('reason','')})")
                        inc[field] = value
                        applied += 1
    return incidents, applied


# ---------------------------------------------------------------------------
# DATE SORT HELPER (used in run_pipeline.py)
# ---------------------------------------------------------------------------

def sort_by_date(incidents: list, newest_first: bool = True) -> list:
    """Sort incidents by date_of_incident. Unknown dates go last."""
    from datetime import datetime

    def _parse(inc):
        raw = inc.get("date_of_incident", "").strip()
        for fmt in ("%Y-%m-%d", "%d %B %Y", "%d/%m/%Y", "%B %d, %Y", "%d %b %Y"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return datetime.min  # unknown dates sort last

    return sorted(incidents, key=_parse, reverse=newest_first)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_list():
    corrections = load_corrections()
    if not corrections:
        print("  No corrections saved yet.")
        return
    print(f"\n  {len(corrections)} correction(s) on file:\n")
    for i, c in enumerate(corrections, 1):
        print(f"  [{i}] URL match:      {c.get('match_url', '(none)')}")
        print(f"       Fallback match: {c.get('match_fallback', '(none)')}")
        print(f"       Fields:         {c.get('fields', {})}")
        print(f"       Reason:         {c.get('reason', '')}")
        print()


def cmd_add(args):
    """Add a correction — either interactively or via flags."""
    correction = {}

    if "--url" in args:
        correction["match_url"] = args[args.index("--url") + 1]
    if "--fallback" in args:
        correction["match_fallback"] = args[args.index("--fallback") + 1]
    if "--reason" in args:
        correction["reason"] = args[args.index("--reason") + 1]

    # Collect field overrides from --field / --value pairs
    fields = {}
    if "--field" in args and "--value" in args:
        i = 0
        while i < len(args):
            if args[i] == "--field" and i + 1 < len(args):
                field = args[i + 1]
                if "--value" in args[i:]:
                    vi = args.index("--value", i)
                    fields[field] = args[vi + 1]
            i += 1
    correction["fields"] = fields

    # Interactive mode if required info is missing
    if not correction.get("match_url") and not correction.get("match_fallback"):
        print("\n  Add a correction")
        print("  ----------------")
        url = input("  Article URL (or press Enter to use date|location fallback): ").strip()
        if url:
            correction["match_url"] = url
        else:
            date_part = input("  Incident date to match (YYYY-MM-DD, or blank): ").strip()
            loc_part  = input("  Location name to match (or blank): ").strip()
            correction["match_fallback"] = f"{date_part}|{loc_part}".lower()

    if not correction.get("fields"):
        print(f"\n  Available fields: {', '.join(CORRECTABLE_FIELDS)}")
        while True:
            field = input("  Field to correct (or Enter to finish): ").strip()
            if not field:
                break
            if field not in CORRECTABLE_FIELDS:
                print(f"  Unknown field '{field}'. Choose from: {CORRECTABLE_FIELDS}")
                continue
            value = input(f"  Correct value for '{field}': ").strip()
            correction["fields"][field] = value

    if not correction.get("reason"):
        correction["reason"] = input("  Reason (optional note): ").strip()

    if not correction.get("fields"):
        print("  No fields specified — nothing saved.")
        return

    corrections = load_corrections()
    corrections.append(correction)
    save_corrections(corrections)
    print(f"\n  Saved. Total corrections on file: {len(corrections)}")
    print(f"  It will be applied automatically on the next pipeline run.")


def cmd_test(search_term: str):
    """Show which future incidents would be corrected by a given correction."""
    corrections = load_corrections()
    matched = [c for c in corrections if
               search_term.lower() in c.get("match_url", "").lower() or
               search_term.lower() in c.get("match_fallback", "").lower() or
               search_term.lower() in str(c.get("fields", {})).lower()]
    if not matched:
        print(f"  No corrections matching '{search_term}'")
    else:
        print(f"  {len(matched)} correction(s) would apply to incidents matching '{search_term}':")
        for c in matched:
            print(f"    {c}")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "list":
        cmd_list()
    elif args[0] == "add":
        cmd_add(args[1:])
    elif args[0] == "test" and len(args) > 1:
        cmd_test(args[1])
    else:
        print(__doc__)
