"""
Downloads PDFs from Azure Blob Storage, extracts text, and stores in SQLite.
Run this to sync new blobs from Azure.
"""

import os
import sqlite3
import pdfplumber
from pathlib import Path
from azure.storage.blob import BlobServiceClient
from config import AZURE_CONNECTION_STRING, AZURE_CONTAINER_NAME, DOWNLOAD_CACHE, DB_PATH


def setup_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blob_id TEXT UNIQUE,
            filename TEXT,
            raw_text TEXT,
            analyzed INTEGER DEFAULT 0
        )
    """)
    conn.commit()


def extract_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def sync_blobs():
    os.makedirs(DOWNLOAD_CACHE, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    setup_db(conn)

    client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    container = client.get_container_client(AZURE_CONTAINER_NAME)

    blobs = list(container.list_blobs())
    print(f"Found {len(blobs)} blobs in container")

    for blob in blobs:
        blob_id = blob.name

        already = conn.execute("SELECT 1 FROM reports WHERE blob_id=?", (blob_id,)).fetchone()
        if already:
            print(f"Skipping (already downloaded): {blob_id}")
            continue

        if not blob_id.lower().endswith(".pdf"):
            print(f"Skipping non-PDF: {blob_id}")
            continue

        print(f"Downloading: {blob_id}")
        local_path = Path(DOWNLOAD_CACHE) / blob_id.replace("/", "_")

        with open(local_path, "wb") as f:
            data = container.download_blob(blob_id).readall()
            f.write(data)

        try:
            text = extract_text(local_path)
        except Exception as e:
            print(f"  Could not extract text: {e}")
            text = ""

        conn.execute(
            "INSERT OR IGNORE INTO reports (blob_id, filename, raw_text) VALUES (?, ?, ?)",
            (blob_id, Path(blob_id).name, text)
        )
        conn.commit()
        print(f"  Stored: {blob_id}")

    conn.close()
    print("Sync complete.")


if __name__ == "__main__":
    sync_blobs()
