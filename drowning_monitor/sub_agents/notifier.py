"""Notifier sub-agent: emails a summary report of findings."""
from google.adk.agents import LlmAgent

from ..tools.email_tools import send_summary_email

notifier_agent = LlmAgent(
    name="notifier_agent",
    model="gemini-2.5-flash",
    description="Composes and sends an email summary of the Australian drowning cases found.",
    instruction="""You are a reporting agent.

You will receive a summary of drowning cases and PDFs found by the previous agents.

Your job:
1. Compose a clear, structured email report with:
   - Subject line: "Australian Drowning Cases Monitor — <today's date>"
   - Plain-text body with sections:
     * Overview (total articles found, total PDFs found, new records saved)
     * PDF Documents (list each PDF title + URL — these feed the pipeline)
     * News Articles (list top articles with title + URL + brief snippet)
     * Footer: "Data has been saved to the database for pipeline processing."
2. Also compose an HTML version with the same content but formatted with
   headings (<h2>), bullet lists (<ul><li>), and bold labels.
3. If no clearly relevant Australian drowning results were found, still include
   all results returned and add a prominent note at the top:
   "NOTE: Likely no Australian drowning incidents found in the past 24 hours.
   The results below are what the search returned."
4. Call send_summary_email with the subject, plain-text body, and HTML body.
5. Report back whether the email was sent successfully.

Be concise and professional. The recipient wants to quickly scan what was found.
""",
    tools=[send_summary_email],
)
