"""
Chunks all PDF text from SQLite and embeds into ChromaDB vector database.
Uses Ollama for embeddings — no cloud, fully offline.
Run once after ingest.py, then re-run anytime new PDFs are added.
Takes ~30-60 min for 6000 PDFs.
"""

import sqlite3
import chromadb
from chromadb.utils import embedding_functions
from config import DB_PATH, OLLAMA_MODEL

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "drowning_cases"
CHUNK_SIZE = 800       # characters per chunk
CHUNK_OVERLAP = 100    # overlap between chunks


def chunk_text(text, case_id):
    """Split text into overlapping chunks, each tagged with the case_id."""
    chunks = []
    start = 0
    i = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            chunks.append({
                "id": f"{case_id}_chunk_{i}",
                "text": chunk,
                "case_id": case_id
            })
        start += CHUNK_SIZE - CHUNK_OVERLAP
        i += 1
    return chunks


def build_vector_db():
    # ChromaDB with Ollama embeddings — fully local
    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    embed_fn = embedding_functions.OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings",
        model_name="nomic-embed-text"   # fast embedding model, see note below
    )
    collection = chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn
    )

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT case_id, raw_text, location, incident_date, source
        FROM cases
        WHERE raw_text IS NOT NULL AND raw_text != ''
    """).fetchall()
    conn.close()

    print(f"Embedding {len(rows)} cases...")

    existing_ids = set(collection.get()["ids"])

    for i, (case_id, raw_text, location, incident_date, source) in enumerate(rows):
        chunks = chunk_text(raw_text, case_id)

        # Skip if all chunks for this case are already embedded
        if all(c["id"] in existing_ids for c in chunks):
            continue

        new_chunks = [c for c in chunks if c["id"] not in existing_ids]

        collection.add(
            ids=[c["id"] for c in new_chunks],
            documents=[c["text"] for c in new_chunks],
            metadatas=[{
                "case_id": case_id,
                "location": location or "",
                "incident_date": incident_date or "",
                "source": source or ""
            } for c in new_chunks]
        )

        if i % 100 == 0:
            print(f"  {i}/{len(rows)} cases embedded...")

    print(f"Done. Collection has {collection.count()} chunks.")


if __name__ == "__main__":
    build_vector_db()
