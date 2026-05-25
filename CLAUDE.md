# Drowning Monitor — Full Project Reference

This document is the complete handoff guide for the Australian Drowning Monitor.
It covers every file, every environment variable, how to run everything, and how it all fits together.

---

## What This Project Does

A two-part system:

1. **Pipeline (`run_pipeline.py`)** — Searches Google News RSS for Australian drowning incidents every day, classifies each one using Gemini AI, saves to SQLite, and emails a formatted summary report with PDFs attached.

2. **Explorer app (`app.py`)** — A Streamlit web UI that sits on top of the database. Lets you search cases, ask natural language questions, do RAG search across report text, and view insights charts.

They share the same SQLite database (`drowning_cases.db`).

---

## Project Structure

```
drowning_monitor/
│
├── run_pipeline.py              ← MAIN ENTRY POINT — run this daily
├── app.py                       ← Streamlit explorer UI
│
├── drowning_monitor/            ← Google ADK agent package
│   ├── agent.py                 ← Root orchestrator agent
│   └── sub_agents/
│       ├── searcher.py          ← Searches Google News, extracts structured case data
│       ├── storer.py            ← Saves results to SQLite database
│       └── notifier.py         ← Sends email summary report
│   └── tools/
│       ├── search_tools.py      ← fetch_drowning_leads() — RSS feed fetcher
│       ├── database_tools.py    ← save_case(), check_duplicate() etc.
│       ├── email_tools.py       ← send_summary_email() via SMTP
│       ├── pdf_tools.py         ← fetch_article_as_pdf() — saves articles as PDFs
│       └── logger.py            ← Structured logging to logs/ folder
│
├── ingest.py                    ← Pull PDFs from Azure Blob or local folder into SQLite
├── analyze_reports.py           ← Run Ollama on each case to extract risk/swim fields
├── embed_pdfs.py                ← Build ChromaDB vector store for RAG search
├── train.py                     ← Train Vanna on schema + field definitions (run once)
├── vanna_setup.py               ← Vanna/Ollama setup for text-to-SQL
├── rag_data.py                  ← SHARED DEFINITIONS — body of water, activity, sex
├── rag_query.py                 ← RAG search layer using ChromaDB + Ollama
├── summarize.py                 ← AI narrative summary across all cases
├── blob_processor.py            ← Azure Blob PDF processor
├── config.py                    ← All settings read from .env
│
├── correct.py                   ← Add/apply manual field corrections to pipeline output
├── corrections.json             ← Saved corrections (committed — safe to version)
├── add_case.py                  ← Manually add a case to the database
├── validate.py                  ← Validation utilities
│
├── requirements.txt             ← All Python dependencies
├── .env.example                 ← Template — copy to .env and fill in
├── .gitignore
├── Dockerfile                   ← Docker deployment
├── README.md                    ← Quick start guide
└── CLAUDE.md                    ← This file
```

---

## Environment Variables — Complete Reference

Copy `.env.example` to `.env` and fill in every value before running.

**Windows:**
```
copy .env.example .env
```
**Mac/Linux:**
```
cp .env.example .env
```

> ⚠️ Never commit `.env` — it contains secrets. It is in `.gitignore`.

### Required — Pipeline will not run without these

| Variable | What it is | Where to get it |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini AI API key — powers the searcher and storer agents | https://aistudio.google.com/app/apikey — free |

### Required — Email will not send without these

| Variable | What it is | Example value |
|---|---|---|
| `SMTP_HOST` | Email server host | `smtp.gmail.com` |
| `SMTP_PORT` | Email server port | `587` |
| `SMTP_USERNAME` | Email account username | `yourname@gmail.com` |
| `SMTP_PASSWORD` | App password (NOT your login password) | 16-char app password from Google |
| `EMAIL_FROM` | Sender address | `yourname@gmail.com` |
| `EMAIL_TO` | Where the daily summary is sent | `recipient@rlssa.org.au` |

> For Gmail: go to myaccount.google.com → Security → 2-Step Verification → App Passwords → create one for "Mail".

### Optional — Explorer app

| Variable | What it is | Default |
|---|---|---|
| `APP_PASSWORD` | Login password for the Streamlit app | *(blank = no login gate)* |
| `OLLAMA_MODEL` | Which local Ollama model to use for analysis | `qwen2.5-coder:7b` |
| `DB_PATH` | Path to the SQLite database | `drowning_cases.db` |
| `BATCH_SIZE` | How many PDFs to analyze per run | `100` |

### Optional — PDF/Azure ingestion

| Variable | What it is |
|---|---|
| `LOCAL_PDF_FOLDER` | Local folder of PDFs to ingest (filename = case ID) |
| `AZURE_CONNECTION_STRING` | Azure Blob Storage connection string |
| `AZURE_CONTAINER_NAME` | Azure container name (default: `drowning-pdfs`) |
| `SQL_SERVER_CONN` | ODBC connection string for SQL Server metadata lookup |
| `SQL_SERVER_TABLE` | Table name in SQL Server (default: `cases`) |
| `SQL_SERVER_ID_COLUMN` | Column that matches the PDF filename (default: `case_id`) |
| `DOWNLOAD_CACHE` | Local folder to cache downloaded PDFs (default: `./pdf_cache`) |

### Optional — Google Custom Search (news search fallback)

| Variable | What it is | Where to get it |
|---|---|---|
| `GOOGLE_CSE_API_KEY` | Google Custom Search API key | https://developers.google.com/custom-search |
| `GOOGLE_CSE_ID` | Custom Search Engine ID | Same link above |

---

## How to Run

### First time setup

```
cd C:\Users\mhaller\drowning_monitor

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env
copy .env.example .env
# Open .env and fill in GOOGLE_API_KEY and SMTP settings

# Train Vanna on the schema and field definitions (run once, or after schema changes)
python train.py
```

### Run the daily pipeline

Searches Google News, classifies incidents, saves to DB, sends email:
```
python run_pipeline.py
```

Dry run (mock data, no network calls, no email sent):
```
python run_pipeline.py --dry-run
```

### Run the explorer app

```
streamlit run app.py
```

Opens at **http://localhost:8501** — log in with the password set in `APP_PASSWORD`.

### Ingest PDFs from Azure or local folder

```
python ingest.py
```

### Analyze ingested PDFs with Ollama (extracts risk score, swim skill etc.)

```
python analyze_reports.py
```

### Build/rebuild the RAG vector store (for Search by Content tab)

```
python embed_pdfs.py
```

---

## How the Pipeline Works (run_pipeline.py)

```
Step 1 — searcher_agent
  Calls fetch_drowning_leads() → fetches Google News RSS for Australian drowning keywords
  Gemini reads each article and extracts structured case data:
    date_of_incident, location_name, location_type, state, age_group,
    gender, outcome, activity, summary, url, source

Step 2 — Python filters (not AI)
  - Drop incidents older than 72 hours
  - Deduplicate by (date_of_incident, location_name)
  - Apply manual corrections from corrections.json
  - Sort newest-first

Step 3 — storer_agent
  Saves each incident to drowning_cases.db (skips duplicates)

Step 4 — PDF generation
  fetch_article_as_pdf() saves each article URL as a PDF attachment

Step 5 — Email
  send_summary_email() sends HTML + plain text summary with PDFs attached
  to EMAIL_TO via SMTP
```

---

## How the Explorer App Works (app.py)

Reads from `drowning_cases.db`. Five tabs:

| Tab | What it does |
|---|---|
| **Search** | Search by case ID, location or keyword. Click a row to see full case details including AI summary and risk score |
| **Ask a Question** | Plain English → SQL via Vanna. e.g. "How many high-risk beach cases involved children?" Uses your field definitions from rag_data.py |
| **Search by Content (RAG)** | Searches the raw text of PDF reports using ChromaDB + Ollama embeddings. Uses your body-of-water and activity definitions as context |
| **Insights** | Charts — swim skill breakdown, risk labels, water type distribution, daily intake |
| **Batch Status** | Shows analyzed vs pending vs failed counts with a progress bar |

---

## Shared Definitions (rag_data.py)

`rag_data.py` contains your official classification definitions for:
- **Body of water** (`water_type`) — Beach, River/Creek, Swimming Pool, Lake/Dam, Ocean/Harbour, Rocks, Bath/Spa, Other — with full definitions and aliases
- **Activity** — Swimming and Recreating, Boating, Rock Fishing, Swept In, Fall, etc.
- **Sex** — Male, Female, Unknown

These definitions are injected into:
1. **Vanna training** (`train.py`) — so "Ask a Question" maps plain English to correct SQL field values
2. **RAG search context** (`rag_query.py`) — so Ollama uses correct terminology when answering

If you update definitions in `rag_data.py`, re-run `python train.py` to retrain Vanna.

---

## Manual Corrections

If the pipeline gets a date or field wrong for a specific article, add a correction:

```
python correct.py add
```

It will ask for the article URL and which field to correct. Corrections are saved to `corrections.json` and applied automatically on every future pipeline run.

To see all saved corrections:
```
python correct.py list
```

---

## Common Issues

| Problem | Fix |
|---|---|
| `GOOGLE_API_KEY not set` | Add it to your `.env` file |
| Email not sending | Check `SMTP_USERNAME`, `SMTP_PASSWORD` (use app password not login), `EMAIL_TO` in `.env` |
| `streamlit: command not found` | Activate venv first: `venv\Scripts\activate` |
| App shows login but no password works | Check `APP_PASSWORD` in `.env` matches what you're typing |
| `vanna_setup` fails | Make sure Ollama is running: `ollama serve` |
| RAG search tab says "vector database not built" | Run `python embed_pdfs.py` first |
| New cases not showing in app | Run `python run_pipeline.py` or `python ingest.py` then `python analyze_reports.py` |

---

## Scheduled / Automated Running

To run the pipeline automatically every day, set up a scheduled task (Windows) or cron job (Linux/Mac):

**Windows Task Scheduler:**
- Action: `C:\Users\mhaller\drowning_monitor\venv\Scripts\python.exe`
- Arguments: `C:\Users\mhaller\drowning_monitor\run_pipeline.py`
- Trigger: Daily at desired time

**Linux/Mac cron (runs at 7am daily):**
```
0 7 * * * cd /path/to/drowning_monitor && venv/bin/python run_pipeline.py >> logs/cron.log 2>&1
```
