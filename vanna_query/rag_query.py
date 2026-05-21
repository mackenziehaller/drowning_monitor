"""
RAG query layer — finds relevant PDF chunks and answers using Ollama.
Used by app.py for the Search tab and freeform case questions.

Loads shared classification definitions from rag_data.py so Ollama
uses the same body-of-water, activity, and sex definitions as the
pdf_scraper_tomato pipeline.
"""

import chromadb
import ollama
from chromadb.utils import embedding_functions
from config import OLLAMA_MODEL
from rag_data import RAG_KNOWLEDGE

CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "drowning_cases"


def build_definitions_block() -> str:
    """Format RAG_KNOWLEDGE into a readable reference block for prompts."""
    lines = ["=== CLASSIFICATION DEFINITIONS ===\n"]

    for category, entries in RAG_KNOWLEDGE.items():
        if category == "rules":
            lines.append("RULES:")
            for rule in entries:
                lines.append(f"  - {rule}")
            lines.append("")
            continue

        lines.append(f"{category.upper()} CATEGORIES:")
        for name, info in entries.items():
            lines.append(f"  {name}:")
            if "definition" in info:
                lines.append(f"    Definition: {info['definition'].strip()}")
            if "aliases" in info:
                lines.append(f"    Also known as: {', '.join(info['aliases'])}")
            if "notes" in info:
                for note in info["notes"]:
                    lines.append(f"    Note: {note}")
        lines.append("")

    return "\n".join(lines)


DEFINITIONS = build_definitions_block()


def get_collection():
    chroma = chromadb.PersistentClient(path=CHROMA_PATH)
    embed_fn = embedding_functions.OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings",
        model_name="nomic-embed-text"
    )
    return chroma.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn
    )


def search(question, n_results=8):
    """Return the most relevant chunks for a question."""
    collection = get_collection()
    results = collection.query(
        query_texts=[question],
        n_results=n_results
    )
    chunks = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        chunks.append({"text": doc, "case_id": meta.get("case_id"), "location": meta.get("location")})
    return chunks


def ask(question):
    """Find relevant chunks, then ask Ollama to answer using report excerpts
    and the shared classification definitions."""
    chunks = search(question)
    context = "\n\n---\n\n".join(
        f"[Case {c['case_id']} | {c['location']}]\n{c['text']}"
        for c in chunks
    )
    prompt = f"""You are an analyst reviewing Australian drowning fatality reports.
Use the classification definitions below to understand terms like body of water type and activity.
Answer the question using ONLY the report excerpts provided.
If the answer isn't in the excerpts, say so.

{DEFINITIONS}

Question: {question}

Report excerpts:
{context}
"""
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    sources = list({c["case_id"] for c in chunks})
    return response["message"]["content"], sources
