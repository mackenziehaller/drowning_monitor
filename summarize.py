"""
Generates a narrative summary of swim skills and risk across all analyzed reports.
Can be called standalone or imported into app.py.
"""

import sqlite3
import ollama
from config import DB_PATH, OLLAMA_MODEL


def get_stats(conn):
    stats = {}

    stats["total"] = conn.execute("SELECT COUNT(*) FROM reports WHERE analyzed=1").fetchone()[0]

    rows = conn.execute("""
        SELECT swim_skill, COUNT(*) FROM reports
        WHERE analyzed=1 AND swim_skill IS NOT NULL
        GROUP BY swim_skill ORDER BY COUNT(*) DESC
    """).fetchall()
    stats["swim_skills"] = dict(rows)

    rows = conn.execute("""
        SELECT risk_label, COUNT(*) FROM reports
        WHERE analyzed=1 AND risk_label IS NOT NULL
        GROUP BY risk_label
    """).fetchall()
    stats["risk_labels"] = dict(rows)

    avg = conn.execute("SELECT AVG(risk_score) FROM reports WHERE analyzed=1").fetchone()[0]
    stats["avg_risk_score"] = round(avg, 1) if avg else None

    rows = conn.execute("""
        SELECT risk_factors FROM reports
        WHERE analyzed=1 AND risk_factors IS NOT NULL
    """).fetchall()
    all_factors = []
    for (rf,) in rows:
        all_factors.extend([f.strip() for f in rf.split(",")])
    from collections import Counter
    stats["top_risk_factors"] = Counter(all_factors).most_common(5)

    rows = conn.execute("""
        SELECT summary FROM reports
        WHERE analyzed=1 AND summary IS NOT NULL
        LIMIT 20
    """).fetchall()
    stats["sample_summaries"] = [r[0] for r in rows]

    return stats


def generate_narrative(stats):
    prompt = f"""You are a drowning prevention analyst. Based on the following statistics from {stats['total']} drowning fatality reports, write a clear, professional 3-4 paragraph summary covering:
1. Overall swim skill distribution and what it suggests
2. Risk profile of the cases (scores, labels, top factors)
3. Key patterns or concerns
4. Any recommendations for prevention

Statistics:
- Total reports analyzed: {stats['total']}
- Swim skill distribution: {stats['swim_skills']}
- Risk label distribution: {stats['risk_labels']}
- Average risk score (1-10): {stats['avg_risk_score']}
- Top risk factors: {stats['top_risk_factors']}

Sample case summaries:
{chr(10).join(f'- {s}' for s in stats['sample_summaries'][:10])}
"""
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"]


def run_summary():
    conn = sqlite3.connect(DB_PATH)
    stats = get_stats(conn)
    conn.close()

    if stats["total"] == 0:
        return "No analyzed reports found. Run analyze_reports.py first."

    return generate_narrative(stats)


if __name__ == "__main__":
    print(run_summary())
