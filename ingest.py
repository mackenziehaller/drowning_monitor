"""
Ingests PDFs from Azure Blob Storage and/or a local folder.
Joins each PDF to its SQL Server metadata record using filename as the case ID.
Stores everything in SQLite so the app works fully offline after this runs.

Run this first, then analyze_reports.py.
"""

import os
import sqlite3
import pdfplumber
import pyodbc
from pathlib import Path
from config import (
    AZURE_CONNECTION_STRING, AZURE_CONTAINER_NAME,
    LOCAL_PDF_FOLDER, SQL_SERVER_CONN, SQL_SERVER_TABLE,
    SQL_SERVER_ID_COLUMN, DOWNLOAD_CACHE, DB_PATH
)


# ── Database setup ────────────────────────────────────────────────

def setup_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id       TEXT UNIQUE,          -- filename without .pdf = SQL Server ID
            filename      TEXT,
            source        TEXT,                 -- 'azure' or 'local'
            raw_text      TEXT,
            analyzed      INTEGER DEFAULT 0,

            -- Fields pulled from SQL Server (add/remove to match your schema)
            sql_data      TEXT,                 -- full JSON snapshot of SQL Server row

            -- AI-extracted fields (populated by analyze_reports.py)
            swim_skill    TEXT,
            risk_score    INTEGER,
            risk_label    TEXT,
            risk_factors  TEXT,
            victim_age    INTEGER,
            victim_gender TEXT,
            water_type    TEXT,
            location      TEXT,
            incident_date TEXT,
            summary       TEXT
        )
    """)
    conn.commit()


# ── SQL Server sync ───────────────────────────────────────────────

def fetch_sql_server_row(case_id):
    """Pull metadata for a single case_id from SQL Server. Returns JSON string or None."""
    import json
    try:
        conn = pyodbc.connect(SQL_SERVER_CONN)
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM {SQL_SERVER_TABLE} WHERE {SQL_SERVER_ID_COLUMN} = ?",
            case_id
        )
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return json.dumps(dict(zip(columns, [str(v) if v is not None else None for v in row])))
        return None
    except Exception as e:
        print(f"  SQL Server lookup failed for {case_id}: {e}")
        return None


# ── PDF text extraction ───────────────────────────────────────────

def extract_text(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        print(f"  Could not extract text from {pdf_path}: {e}")
        return ""


# ── Azure ingest ──────────────────────────────────────────────────

def ingest_azure(conn):
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        print("azure-storage-blob not installed — skipping Azure. Run: pip install azure-storage-blob")
        return

    os.makedirs(DOWNLOAD_CACHE, exist_ok=True)
    client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container = client.get_container_client(AZURE_CONTAINER_NAME)

    blobs = [b for b in container.list_blobs() if b.name.lower().endswith(".pdf")]
    print(f"Azure: found {len(blobs)} PDFs")

    for blob in blobs:
        case_id = Path(blob.name).stem
        if conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
            continue

        print(f"  Azure → {blob.name}")
        local_path = Path(DOWNLOAD_CACHE) / blob.name.replace("/", "_")
        with open(local_path, "wb") as f:
            f.write(container.download_blob(blob.name).readall())

        text = extract_text(local_path)
        sql_data = fetch_sql_server_row(case_id)

        conn.execute(
            "INSERT OR IGNORE INTO cases (case_id, filename, source, raw_text, sql_data) VALUES (?,?,?,?,?)",
            (case_id, blob.name, "azure", text, sql_data)
        )
        conn.commit()


# ── Local folder ingest ───────────────────────────────────────────

def ingest_local(conn):
    folder = Path(LOCAL_PDF_FOLDER)
    if not folder.exists():
        print(f"Local folder not found: {LOCAL_PDF_FOLDER} — skipping")
        return

    pdfs = list(folder.glob("**/*.pdf"))
    print(f"Local: found {len(pdfs)} PDFs")

    for pdf_path in pdfs:
        case_id = pdf_path.stem
        if conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone():
            continue

        print(f"  Local → {pdf_path.name}")
        text = extract_text(pdf_path)
        sql_data = fetch_sql_server_row(case_id)

        conn.execute(
            "INSERT OR IGNORE INTO cases (case_id, filename, source, raw_text, sql_data) VALUES (?,?,?,?,?)",
            (case_id, pdf_path.name, "local", text, sql_data)
        )
        conn.commit()


# ── Main ──────────────────────────────────────────────────────────

def run():
    conn = sqlite3.connect(DB_PATH)
    setup_db(conn)

    total_before = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]

    ingest_azure(conn)
    ingest_local(conn)

    total_after = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    conn.close()

    print(f"\nIngest complete. {total_after - total_before} new cases added ({total_after} total).")


if __name__ == "__main__":
    run()
