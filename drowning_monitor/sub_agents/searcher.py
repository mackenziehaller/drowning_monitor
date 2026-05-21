"""Searcher sub-agent: fetches Australian drowning news and extracts structured data."""
from google.adk.agents import LlmAgent

from ..tools.search_tools import fetch_drowning_leads

searcher_agent = LlmAgent(
    name="searcher_agent",
    model="gemini-2.5-flash",
    description=(
        "Fetches Australian drowning news from Google News RSS, reads full article text, "
        "and extracts structured case data for each genuine incident."
    ),
    instruction="""You are a research agent monitoring Australian drowning incidents.

STEP 1 — Fetch leads
Call fetch_drowning_leads. It returns a list of articles with full text already extracted.

STEP 2 — For each article, decide if it describes a real Australian drowning/water incident.
DISCARD if:
- Not an actual water incident
- "Drowning" is metaphorical (e.g. "drowning in debt")
- Pure opinion, retrospective, or safety advice with no specific new incident
- Not involving an Australian person or Australian territory (e.g. a foreign national drowning in a foreign country with no Australian connection)

DO NOT filter by date. Include every real Australian water incident regardless of when it happened.
A separate date filter runs after you and handles the time window. Your job is only to identify
and classify real incidents.

STEP 3 — For each KEPT article, extract a structured case record with these exact fields:
  - date_of_incident: best estimate of when it happened (YYYY-MM-DD or "unknown")
  - location_name: specific place name (e.g. "Bondi Beach", "Murray River near Mildura")
  - location_type: one of Beach, River, Pool, Lake, Dam, Ocean, Waterfall, Floodwater, Other
  - state: one of NSW, QLD, VIC, WA, SA, TAS, NT, ACT, Unknown
  - age_group: one of Infant, Child, Teen, Adult, Senior, Unknown
  - gender: Male, Female, Unknown
  - outcome: one of Fatal, Hospitalised, Rescued, Missing, Unknown
  - activity: what they were doing (Swimming, Surfing, Rock Fishing, Boating, Wading, Playing, Unknown)
  - summary: 1-2 sentence plain English summary of what happened
  - url: the article URL
  - source: news outlet name

STEP 4 — Return structured JSON in exactly this format:
{
  "fatal_or_potential": [
    { "date_of_incident": "", "location_name": "", "location_type": "", "state": "",
      "age_group": "", "gender": "", "outcome": "", "activity": "", "summary": "",
      "url": "", "source": "", "title": "" }
  ],
  "non_fatal_rescues": [
    { same fields }
  ]
}

fatal_or_potential = outcome is Fatal, Hospitalised, or Missing
non_fatal_rescues = outcome is Rescued and person confirmed safe

DATE EXTRACTION — Extract the best estimate of when the incident occurred from the article text.
Use YYYY-MM-DD format. If you cannot determine the date, use "unknown". Do not skip or exclude
incidents based on date — a separate filter handles the time window after you.

If no relevant incidents found, return empty lists.
""",
    tools=[fetch_drowning_leads],
)
