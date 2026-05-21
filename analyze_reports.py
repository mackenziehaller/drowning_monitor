"""
Runs Ollama inference on each unanalyzed case to extract structured fields.
Safe to stop and restart — skips already-analyzed cases.
With 6000 PDFs expect this to run over multiple sessions.
"""

import sqlite3
import json
import ollama
from config import DB_PATH, OLLAMA_MODEL, BATCH_SIZE


PROMPT = """You are analyzing a police or incident report about a drowning fatality.
Extract the following and return ONLY valid JSON — no explanation, no markdown fences.

{
  "swim_skill": "none | beginner | competent | strong | unknown",
  "risk_score": <integer 1-10, where 10 is highest risk>,
  "risk_label": "low | medium | high",
  "risk_factors": "<comma-separated list e.g. unsupervised, alcohol, unfamiliar water, night-time, no lifeguard>",
  "victim_age": <integer or null>,
  "victim_gender": "male | female | unknown",
  "water_type": "pool | ocean | river | lake | pond | bathtub | other | unknown",
  "location": "<city and state/country, or null>",
  "incident_date": "<YYYY-MM-DD or null>",
  "summary": "<2-3 sentence factual narrative of what happened>"
}

Risk score guidelines:
- 1-3 (low): single risk factor, adult, supervised, competent swimmer
- 4-6 (medium): 2-3 risk factors, partial supervision
- 7-10 (high): child, multiple risk factors, no swim skills, unsupervised, intoxication

Report text:
{text}
"""


def analyze_batch():
    conn = sqlite3.connect(DB_PATH)

    pending = conn.execute("""
        SELECT id, case_id, raw_text FROM cases
        WHERE analyzed = 0 AND raw_text != '' AND raw_text IS NOT NULL
        LIMIT ?
    """, (BATCH_SIZE,)).fetchall()

    total_pending = conn.execute("""
        SELECT COUNT(*) FROM cases
        WHERE analyzed = 0 AND raw_text != '' AND raw_text IS NOT NULL
    """).fetchone()[0]

    print(f"Analyzing {len(pending)} cases (of {total_pending} remaining)...")

    for row_id, case_id, raw_text in pending:
        print(f"  [{case_id}] analyzing...", end=" ", flush=True)
        try:
            prompt = PROMPT.format(text=raw_text[:5000])
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response["message"]["content"].strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)

            conn.execute("""
                UPDATE cases SET
                    swim_skill=?, risk_score=?, risk_label=?, risk_factors=?,
                    victim_age=?, victim_gender=?, water_type=?, location=?,
                    incident_date=?, summary=?, analyzed=1
                WHERE id=?
            """, (
                data.get("swim_skill"),
                data.get("risk_score"),
                data.get("risk_label"),
                data.get("risk_factors"),
                data.get("victim_age"),
                data.get("victim_gender"),
                data.get("water_type"),
                data.get("location"),
                data.get("incident_date"),
                data.get("summary"),
                row_id
            ))
            conn.commit()
            print(f"swim={data.get('swim_skill')}  risk={data.get('risk_label')}({data.get('risk_score')})")

        except Exception as e:
            print(f"FAILED: {e}")
            # Mark as attempted so we don't get stuck in a loop on a bad PDF
            conn.execute("UPDATE cases SET analyzed=-1 WHERE id=?", (row_id,))
            conn.commit()

    remaining = conn.execute(
        "SELECT COUNT(*) FROM cases WHERE analyzed=0"
    ).fetchone()[0]
    conn.close()

    print(f"\nBatch done. {remaining} cases still pending.")
    if remaining > 0:
        print("Run again to continue processing.")


if __name__ == "__main__":
    analyze_batch()
