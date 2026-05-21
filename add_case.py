"""Add a missed drowning case to the database.

Usage:
    python add_case.py <url>           # fetch, classify, confirm, save
    python add_case.py <url> --yes     # skip confirmation
    python add_case.py <url> --diagnose  # explain why pipeline missed it, don't save

Every run appends a row to miss_log.csv so you can track patterns over time.
"""
import argparse
import asyncio
import csv
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import trafilatura
from dotenv import load_dotenv

load_dotenv()

from drowning_monitor.tools.search_tools import score_text, _resolve_url, _HEADERS
from drowning_monitor.tools.database_tools import save_cases
from drowning_monitor.sub_agents.searcher import searcher_agent

MISS_LOG = Path("miss_log.csv")
LOG_DIR  = Path("logs")


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_article(url: str) -> tuple[str | None, str]:
    """Fetch full article text. Returns (text_or_None, resolved_url)."""
    try:
        real_url = _resolve_url(url)
        r = requests.get(real_url, headers=_HEADERS, timeout=15)
        text = trafilatura.extract(r.text) if r.status_code == 200 else None
        return text, real_url
    except Exception as e:
        print(f"  Fetch error: {e}")
        return None, url


# ---------------------------------------------------------------------------
# Diagnose — check today's log to explain the miss
# ---------------------------------------------------------------------------

_FILTER_REASONS = {
    "pubDate-too-old":        "RSS pub_date marked too old — Google News stamped it with a stale date.",
    "no-keyword-match-title": "Failed title keyword filter — no drowning keywords in the headline.",
    "no-keyword-match":       "Failed full-text keyword filter — keyword score too low.",
    "duplicate-link":         "Filtered as duplicate RSS link.",
    "duplicate-url":          "Filtered as duplicate — resolved URL already scraped.",
    "no-text":                "Could not scrape article text (paywall/JS) and no RSS blurb.",
    "no-text-used-blurb":     "Could not scrape full text — used RSS blurb only (may have reached LLM).",
}


def diagnose(url: str, real_url: str, text: str | None) -> list[str]:
    """Inspect today's log and return a list of plain-English reasons for the miss."""
    reasons = []
    today_log = LOG_DIR / f"{date.today().isoformat()}.log"

    if not today_log.exists():
        reasons.append("No log file for today — pipeline hasn't run yet.")
        return reasons

    log_text = today_log.read_text(encoding="utf-8", errors="ignore")

    # Check if either the original or resolved URL appears in the log
    def _slug(u):
        return u[-70:] if len(u) > 70 else u

    found_in_log = False
    for line in log_text.splitlines():
        if _slug(url) in line or _slug(real_url) in line:
            found_in_log = True
            for tag, explanation in _FILTER_REASONS.items():
                if f"[{tag}]" in line:
                    reasons.append(f"Pipeline saw this URL but filtered it: {explanation}")
                    break
            else:
                # URL in log but not in a FILTERED line — it passed to the LLM
                if "FILTERED" not in line:
                    reasons.append("URL passed all pre-filters and was sent to the LLM — LLM dropped or misclassified it.")

    if not found_in_log:
        reasons.append("URL never appeared in today's RSS feeds — not returned by any Google News query or direct feed.")
        if text:
            score, matches = score_text(text[:3000])
            if score >= 5:
                reasons.append(
                    f"Keyword score is {score} (would have passed the filter) — "
                    "a new RSS query is needed to surface this article."
                )
            else:
                reasons.append(
                    f"Keyword score is only {score} (below threshold 5) — "
                    "keyword rules would also need updating to catch this."
                )

    return reasons if reasons else ["Could not determine reason — check the log manually."]


# ---------------------------------------------------------------------------
# Classify via LLM
# ---------------------------------------------------------------------------

async def classify_article(url: str, title: str, text: str) -> tuple[dict | None, str | None]:
    """Run the searcher LLM on a single article. Returns (case_dict, category)."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    payload = json.dumps([{
        "title":    title,
        "url":      url,
        "pub_date": date.today().isoformat(),
        "text":     text[:5000],
        "source":   url.split("/")[2] if url.startswith("http") else url,
    }])

    prompt = (
        f"Today's date is {date.today().strftime('%A %d %B %Y')}. "
        f"Classify this single article. Extract all fields. Do not filter by date.\n\n"
        f"Articles: {payload}"
    )

    session_svc = InMemorySessionService()
    session     = await session_svc.create_session(app_name="add_case", user_id="manual")
    runner      = Runner(agent=searcher_agent, app_name="add_case", session_service=session_svc)
    msg         = Content(role="user", parts=[Part(text=prompt)])

    output = ""
    async for event in runner.run_async(user_id="manual", session_id=session.id, new_message=msg):
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    output += part.text

    for key in ("fatal_or_potential", "non_fatal_rescues"):
        m = re.search(rf'{key}["\s:]+(\[.*?\])', output, re.DOTALL | re.IGNORECASE)
        if m:
            try:
                incidents = json.loads(m.group(1))
                if incidents:
                    return incidents[0], key
            except Exception:
                pass
    return None, None


# ---------------------------------------------------------------------------
# Miss log
# ---------------------------------------------------------------------------

def append_miss_log(url: str, title: str, reasons: list[str]):
    write_header = not MISS_LOG.exists()
    with open(MISS_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["date", "url", "title", "reason"])
        writer.writerow([date.today().isoformat(), url, title[:120], " | ".join(reasons)])


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_case(case: dict):
    print()
    print(f"  Summary  : {case.get('summary', '')}")
    print(f"  Date     : {case.get('date_of_incident', 'unknown')}")
    print(f"  Location : {case.get('location_name', '')} ({case.get('state', '')})")
    print(f"  Type     : {case.get('location_type', '')}  |  Activity: {case.get('activity', '')}")
    print(f"  Person   : {case.get('age_group', '')} {case.get('gender', '')}  |  Outcome: {case.get('outcome', '')}")
    print(f"  Source   : {case.get('source', '')}")
    print(f"  URL      : {case.get('url', '')[:90]}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="Add a missed drowning case to the database.")
    parser.add_argument("url",        help="URL of the missed article")
    parser.add_argument("--yes", "-y",      action="store_true", help="Skip confirmation")
    parser.add_argument("--diagnose", "-d", action="store_true", help="Only diagnose, don't save")
    args = parser.parse_args()

    url = args.url
    print(f"\nFetching: {url}")
    text, real_url = fetch_article(url)
    if text:
        print(f"  Got {len(text)} chars of article text.")
    else:
        print("  Could not get article text (paywall or JS-rendered page).")

    # Always diagnose and log
    print("\n-- Why the pipeline missed this ------------------------------")
    reasons = diagnose(url, real_url, text)
    for r in reasons:
        print(f"  • {r}")

    title = real_url.rstrip("/").split("/")[-1].replace("-", " ").title()
    append_miss_log(url, title, reasons)
    print(f"\n  Logged to {MISS_LOG}")

    if args.diagnose:
        print("\n(--diagnose mode: not saving to database)\n")
        return

    if not text:
        print("\nNo article text — can't classify. Use `python correct.py add` to enter details manually.\n")
        return

    # Keyword score
    score, matches = score_text(text[:3000])
    print(f"\n-- Keyword score: {score} ({'PASS' if score >= 5 else 'FAIL - below threshold 5'}) --")
    if matches:
        print(f"  Signals: {', '.join(matches[:6])}")

    # Classify
    print("\nClassifying with LLM...")
    case, category = await classify_article(real_url, title, text)

    if not case:
        print("  LLM could not classify this as a water incident.")
        print("  If it clearly is one, use `python correct.py add` to enter it manually.\n")
        return

    label = "FATAL / POTENTIAL" if category == "fatal_or_potential" else "NON-FATAL RESCUE"
    print(f"\n-- Classified as: {label} ------------------------------------")
    print_case(case)

    if not args.yes:
        answer = input("Save to database? [Y/n]: ").strip().lower()
        if answer == "n":
            print("Skipped.\n")
            return

    result = save_cases([case])
    if result["saved"] > 0:
        print(f"Saved to database.\n")
    else:
        print(f"Already in database (duplicate — skipped).\n")


if __name__ == "__main__":
    asyncio.run(main())
