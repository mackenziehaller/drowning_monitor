"""Root orchestrator agent for the Australian Drowning Cases Monitor."""
from google.adk.agents import LlmAgent

from .sub_agents.notifier import notifier_agent
from .sub_agents.searcher import searcher_agent
from .sub_agents.storer import storer_agent

root_agent = LlmAgent(
    name="drowning_monitor_orchestrator",
    model="gemini-2.5-flash",
    description=(
        "Orchestrates the full pipeline: search Google for Australian drowning cases "
        "and PDFs, save results to the database, then email a summary report."
    ),
    instruction="""You are the orchestrator for the Australian Drowning Cases Monitor.

When asked to run the monitor (or when triggered automatically), execute this pipeline:

STEP 1 — Search
  Transfer to searcher_agent.
  It will search Google News and find PDF documents (coroner reports, research papers)
  about drowning incidents in Australia. Collect all results it returns.

STEP 2 — Store
  Transfer to storer_agent with the full list of results from Step 1.
  It will save new records to the database (skipping duplicates) and
  return a storage summary (saved count, skipped count, PDF count).

STEP 3 — Notify
  Transfer to notifier_agent with:
  - The storage summary from Step 2
  - The full list of results (articles + PDFs) from Step 1
  It will compose and send the email summary report.

STEP 4 — Report back
  Once all three steps are complete, summarise to the user:
  - How many results were found
  - How many PDFs were found
  - How many new records were saved
  - Whether the email was sent successfully

Always run all three steps in order. Do not skip any step.
""",
    sub_agents=[searcher_agent, storer_agent, notifier_agent],
)
