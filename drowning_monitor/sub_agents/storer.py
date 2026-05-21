"""Storer sub-agent: saves drowning case results to the database."""
from google.adk.agents import LlmAgent

from ..tools.database_tools import get_recent_cases, save_cases

storer_agent = LlmAgent(
    name="storer_agent",
    model="gemini-2.5-flash",
    description=(
        "Stores drowning case records (articles and PDFs) into the database "
        "and retrieves recent records for downstream pipeline consumption."
    ),
    instruction="""You are a data storage agent.

You will receive a list of drowning case records from the searcher agent.

Your job:
1. Call save_cases with the full list of records to persist them to the database.
   - Duplicates (same URL) are automatically skipped.
2. Call get_recent_cases to retrieve the freshly saved records.
3. Return a summary: how many were saved, how many were skipped, and
   how many PDFs are in the recent results.

The raw_json field on each record stores the complete data so the downstream
pipeline can ingest it without any information loss.
""",
    tools=[save_cases, get_recent_cases],
)
