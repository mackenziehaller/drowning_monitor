"""Run the full drowning monitor pipeline end-to-end.

Usage:
    python run_pipeline.py            # live run (free, uses Google News RSS)
    python run_pipeline.py --dry-run  # mock data, no network calls
"""
from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
import os
import re
import sys
import tempfile
from datetime import date

# Set DRY_RUN env var before any imports that read it
if "--dry-run" in sys.argv:
    os.environ["DRY_RUN"] = "true"

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from drowning_monitor.sub_agents.searcher import searcher_agent
from drowning_monitor.sub_agents.storer import storer_agent
from drowning_monitor.tools.pdf_tools import fetch_article_as_pdf
from drowning_monitor.tools.email_tools import send_summary_email
from drowning_monitor.tools.logger import get_logger, log_pipeline_summary
from correct import apply_corrections, sort_by_date


async def run_agent(agent, message):
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="pipeline", user_id="run")
    runner = Runner(agent=agent, app_name="pipeline", session_service=session_service)
    msg = Content(role="user", parts=[Part(text=message)])
    final_text = ""
    async for event in runner.run_async(user_id="run", session_id=session.id, new_message=msg):
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text += part.text
    return final_text


def extract_incidents(searcher_output: str) -> tuple[list, list]:
    """Parse fatal and non-fatal incident lists from searcher output."""
    # Try to find JSON blocks
    fatal, rescued = [], []

    fatal_match = re.search(
        r'fatal_or_potential["\s:]+(\[.*?\])', searcher_output, re.DOTALL | re.IGNORECASE
    )
    rescued_match = re.search(
        r'non_fatal_rescues["\s:]+(\[.*?\])', searcher_output, re.DOTALL | re.IGNORECASE
    )

    def safe_parse(m):
        if not m:
            return []
        try:
            return json.loads(m.group(1))
        except Exception:
            return []

    fatal = safe_parse(fatal_match)
    rescued = safe_parse(rescued_match)
    return fatal, rescued


def build_email(fatal: list, rescued: list, today: str) -> tuple[str, str]:
    """Build plain-text and HTML email bodies with structured case data."""
    no_results = not fatal and not rescued

    def fmt_incident(inc: dict) -> str:
        return (
            f"  {inc.get('summary', inc.get('title', ''))}\n"
            f"  Date: {inc.get('date_of_incident', 'unknown')}  |  "
            f"Location: {inc.get('location_name', '')} ({inc.get('state', '')})\n"
            f"  Type: {inc.get('location_type', '')}  |  "
            f"Activity: {inc.get('activity', '')}  |  "
            f"Age: {inc.get('age_group', '')}  |  Gender: {inc.get('gender', '')}\n"
            f"  Outcome: {inc.get('outcome', '')}  |  Source: {inc.get('source', '')}\n"
            f"  URL: {inc.get('url', '')}\n"
        )

    def fmt_incident_html(inc: dict) -> str:
        url = inc.get("url", "")
        summary = inc.get("summary", inc.get("title", ""))
        return (
            f"<li style='margin-bottom:12px'>"
            f"<strong><a href='{url}'>{summary}</a></strong><br>"
            f"<span style='color:#555'>"
            f"📅 {inc.get('date_of_incident','unknown')} &nbsp;|&nbsp; "
            f"📍 {inc.get('location_name','')} ({inc.get('state','')})"
            f"</span><br>"
            f"<span style='color:#555'>"
            f"🏊 {inc.get('activity','')} &nbsp;|&nbsp; "
            f"🌊 {inc.get('location_type','')} &nbsp;|&nbsp; "
            f"👤 {inc.get('age_group','')} {inc.get('gender','')}"
            f"</span><br>"
            f"<em>Outcome: <strong>{inc.get('outcome','')}</strong></em> — {inc.get('source','')}"
            f"</li>"
        )

    # Plain text
    txt = f"Australian Drowning Cases Monitor — {today}\n{'='*50}\n"
    txt += f"Ordered by incident date (newest first) | Past 72 hours\n{'='*50}\n\n"
    if no_results:
        txt += "No Australian drowning incidents found in the past 72 hours.\n\n"
    else:
        txt += f"FATAL / POTENTIAL FATALITIES ({len(fatal)})\n{'-'*40}\n"
        txt += ("\n".join(fmt_incident(i) for i in fatal) if fatal else "  None found.\n") + "\n"
        txt += f"NON-FATAL RESCUES ({len(rescued)})\n{'-'*40}\n"
        txt += ("\n".join(fmt_incident(i) for i in rescued) if rescued else "  None found.\n") + "\n"
    txt += "Data saved to database for pipeline processing.\n"
    txt += "To correct a date or field: python correct.py add"

    # HTML
    html = (
        f"<div style='font-family:Arial,sans-serif;max-width:700px'>"
        f"<h2 style='color:#1a1a2e'>Australian Drowning Cases Monitor — {today}</h2>"
        f"<p style='color:#888;font-size:12px;margin-top:-8px'>Ordered by incident date (newest first) | Past 72 hours</p>"
    )
    if no_results:
        html += "<p><em>No Australian drowning incidents found in the past 72 hours.</em></p>"
    else:
        html += f"<h3 style='color:#c0392b'>Fatal / Potential Fatalities ({len(fatal)})</h3>"
        html += ("<ul>" + "".join(fmt_incident_html(i) for i in fatal) + "</ul>") if fatal else "<p>None found.</p>"
        html += f"<h3 style='color:#e67e22'>Non-Fatal Rescues ({len(rescued)})</h3>"
        html += ("<ul>" + "".join(fmt_incident_html(i) for i in rescued) + "</ul>") if rescued else "<p>None found.</p>"
    html += "<p style='color:#888;font-size:12px'><em>Data saved to database. To correct a field: python correct.py add</em></p></div>"

    return txt, html


async def main():
    logger = get_logger()
    dry = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")
    today = date.today().strftime("%d %B %Y")
    print(f"=== Drowning Monitor — {today}{' [DRY RUN]' if dry else ''} ===\n")
    logger.info(f"Pipeline started — {'DRY RUN' if dry else 'LIVE'}")

    # Step 1: Search + classify
    print("Step 1: Searching Google News...")
    from datetime import date as date_cls, datetime as dt_cls, timedelta, timezone
    today_dt   = dt_cls.now(timezone.utc)
    cutoff_dt  = today_dt - timedelta(hours=72)
    cutoff_date = cutoff_dt.date()

    search_results = await run_agent(
        searcher_agent,
        f"Today's date is {today_dt.strftime('%A %d %B %Y')}. "
        f"Search for Australian drowning incidents. Classify all real incidents you find. "
        f"Extract the best date estimate for each. Do not filter by date."
    )
    print(f"  Done.\n")

    # Parse the structured output
    fatal, rescued = extract_incidents(search_results)

    # --- HARD DATE FILTER (Python-level, does not rely on the LLM) ---
    # The LLM hint above helps but is unreliable. This is the authoritative filter.
    def _within_72h(inc: dict) -> bool:
        raw = inc.get("date_of_incident", "").strip()
        if not raw or raw.lower() == "unknown":
            return True   # can't determine date → include (better to over-report than miss)
        for fmt in ("%Y-%m-%d", "%d %B %Y", "%d/%m/%Y", "%B %d, %Y", "%d %b %Y"):
            try:
                parsed = dt_cls.strptime(raw, fmt).date()
                return parsed >= cutoff_dt.date()  # date-only: don't penalise for UTC hour offset
            except ValueError:
                continue
        return True  # unparseable format → include

    before_filter = len(fatal) + len(rescued)
    fatal   = [i for i in fatal   if _within_72h(i)]
    rescued = [i for i in rescued if _within_72h(i)]
    dropped = before_filter - len(fatal) - len(rescued)
    if dropped:
        print(f"  [date filter] Dropped {dropped} incident(s) older than 72 hours.\n")

    # Deduplicate by (date_of_incident, location_name) — same incident from
    # multiple outlets should only generate one PDF and one email entry.
    # Preferred sources are tried first so they win when duplicates are merged.
    _PREFERRED = ("abc.net.au",)

    def _source_rank(inc: dict) -> int:
        url = inc.get("url", "").lower()
        for i, domain in enumerate(_PREFERRED):
            if domain in url:
                return i
        return len(_PREFERRED)

    def _dedup(incidents: list) -> list:
        sorted_incs = sorted(incidents, key=_source_rank)
        seen = set()
        out = []
        for inc in sorted_incs:
            key = (
                inc.get("date_of_incident", "").strip().lower(),
                inc.get("location_name", "").strip().lower(),
            )
            if key not in seen:
                seen.add(key)
                out.append(inc)
        return out

    fatal   = _dedup(fatal)
    rescued = _dedup(rescued)

    # Apply manual corrections (from corrections.json) then sort newest-first
    all_for_correction = fatal + rescued
    all_for_correction, n_corrected = apply_corrections(all_for_correction)
    if n_corrected:
        print(f"  [corrections] Applied {n_corrected} field correction(s).\n")
    fatal   = sort_by_date([i for i in all_for_correction if i in fatal])
    rescued = sort_by_date([i for i in all_for_correction if i in rescued])

    print(f"  Fatal/potential: {len(fatal)}")
    print(f"  Rescues:         {len(rescued)}\n")

    # Step 2: Store all incidents
    all_incidents = fatal + rescued
    if all_incidents:
        print("Step 2: Storing...")
        store_summary = await run_agent(
            storer_agent,
            f"Save these results to the database:\n{search_results}"
        )
        print(f"  {store_summary[:150]}\n")
    else:
        print("Step 2: Nothing to store.\n")

    # Step 3: Generate PDFs for each incident
    print("Step 3: Generating PDFs...")
    tmp_dir = tempfile.mkdtemp()
    pdf_paths = []
    for i, inc in enumerate(all_incidents):
        url = inc.get("url", "")
        if not url:
            continue
        category = "fatal" if inc in fatal else "rescue"
        out_path = os.path.join(tmp_dir, f"{category}_{i+1}.pdf")
        result = fetch_article_as_pdf(url, out_path)
        if result["success"]:
            pdf_paths.append(out_path)
            print(f"  [{category}] {inc.get('source', url[:40])} -> PDF OK")
        else:
            print(f"  [{category}] {inc.get('source', url[:40])} -> {result['message']}")
    print()

    # Step 4: Send email
    print("Step 4: Sending email...")
    body_text, body_html = build_email(fatal, rescued, today)
    result = send_summary_email(
        subject=f"Australian Drowning Cases Monitor — {today}",
        body_text=body_text,
        body_html=body_html,
        attachment_paths=pdf_paths,
    )
    if result["success"]:
        print(f"  Email sent to {os.getenv('EMAIL_TO')} with {len(pdf_paths)} PDF(s) attached.")
    else:
        print(f"  Email FAILED: {result['message']}")

    log_pipeline_summary(logger, fatal, rescued, len(pdf_paths), result["success"])
    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
