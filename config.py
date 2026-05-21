"""
Central config — all settings read from .env file.
Copy .env.example to .env and fill in your values before running.
"""
import os
from dotenv import load_dotenv
load_dotenv()

# ── App password ──────────────────────────────────────────────────
# Set APP_PASSWORD in .env — leave blank to disable login gate (dev mode)
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

# ── Azure Blob Storage ────────────────────────────────────────────
AZURE_CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING", "")
AZURE_CONTAINER_NAME    = os.getenv("AZURE_CONTAINER_NAME", "drowning-pdfs")

# ── Local PDF folder ──────────────────────────────────────────────
LOCAL_PDF_FOLDER = os.getenv("LOCAL_PDF_FOLDER", "./pdfs")

# ── SQL Server ────────────────────────────────────────────────────
SQL_SERVER_CONN = os.getenv("SQL_SERVER_CONN", (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=YOUR_SERVER;"
    "DATABASE=YOUR_DATABASE;"
    "Trusted_Connection=yes;"
))
SQL_SERVER_TABLE     = os.getenv("SQL_SERVER_TABLE", "cases")
SQL_SERVER_ID_COLUMN = os.getenv("SQL_SERVER_ID_COLUMN", "case_id")

# ── Local cache & database ────────────────────────────────────────
DOWNLOAD_CACHE = os.getenv("DOWNLOAD_CACHE", "./pdf_cache")
DB_PATH        = os.getenv("DB_PATH", "drowning_cases.db")

# ── Ollama ────────────────────────────────────────────────────────
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")

# ── Batch processing ──────────────────────────────────────────────
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
