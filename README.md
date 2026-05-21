# Drowning Monitor

Australian drowning fatality pipeline. Searches news articles and processes coroner PDFs, classifies cases using AI, and provides a Streamlit explorer app.

---

## Quick Start

### 1. Clone the repo
```
git clone https://github.com/mackenziehaller/drowning_monitor.git
cd drowning_monitor
```

### 2. Create a virtual environment
**Windows:**
```
python -m venv venv
venv\Scripts\activate
```
**Mac/Linux:**
```
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```
pip install -r requirements.txt
```

### 4. Create your .env file
**Windows:**
```
copy .env.example .env
```
**Mac/Linux:**
```
cp .env.example .env
```
Open `.env` and fill in your values — at minimum `APP_PASSWORD` and `GOOGLE_API_KEY`.

> `.env` is never committed to GitHub. You must create it yourself after every fresh clone.

### 5. Run the pipeline (search + classify + email)
```
python run_pipeline.py
```

### 6. Run the explorer app
```
streamlit run app.py
```
Open your browser to **http://localhost:8501**

---

## How It Works

```
Google News RSS + SerpAPI
        │
        ▼
  run_pipeline.py       ← searches, classifies, stores, emails summary
        │
        ▼
  drowning_cases.db     ← SQLite database of all cases
        │
   ┌────┴────┐
   │         │
ingest.py  embed_pdfs.py    ← load PDFs + build ChromaDB vector store
   │
analyze_reports.py          ← Ollama extracts risk score, swim skill etc.
        │
        ▼
    app.py                  ← Streamlit explorer (search, ask, insights)
```

---

## What Each File Does

| File | What it does |
|---|---|
| `run_pipeline.py` | Main pipeline — search news, classify, store, send email |
| `app.py` | Streamlit explorer UI |
| `ingest.py` | Pull PDFs from Azure Blob or local folder into SQLite |
| `analyze_reports.py` | Run Ollama on each case to extract risk/swim fields |
| `embed_pdfs.py` | Build ChromaDB vector store for RAG search |
| `train.py` | Train Vanna on schema + your field definitions |
| `rag_data.py` | Shared definitions — body of water, activity, sex categories |
| `rag_query.py` | RAG search layer using ChromaDB + Ollama |
| `config.py` | All settings read from `.env` |
| `correct.py` | Add/apply manual field corrections to pipeline output |

---

## APIs Needed

| API | Required | Where to get it |
|---|---|---|
| `GOOGLE_API_KEY` | ✅ Yes | console.cloud.google.com |
| `APP_PASSWORD` | ✅ Yes | Set any password you like |
| `SERPAPI_KEY` | Optional | serpapi.com (news search) |
| `EMAIL_TO` / SMTP settings | Optional | For email summary |
| `AZURE_CONNECTION_STRING` | Optional | Azure Portal |
| `SQL_SERVER_CONN` | Optional | Your SQL Server instance |

See `.env.example` for the full list.
