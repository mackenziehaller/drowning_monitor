from vanna_setup import vn
from rag_data import RAG_KNOWLEDGE

# ── Schema ────────────────────────────────────────────────────────
vn.train(ddl="""
CREATE TABLE cases (
    id            INTEGER PRIMARY KEY,
    case_id       TEXT UNIQUE,
    filename      TEXT,
    source        TEXT,
    raw_text      TEXT,
    analyzed      INTEGER DEFAULT 0,
    sql_data      TEXT,
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

# ── General documentation ─────────────────────────────────────────
vn.train(documentation="""
The 'cases' table contains drowning fatality cases. Each row is one case linked to a PDF report.
- case_id: unique identifier matching the PDF filename (without .pdf) and the SQL Server record ID
- source: 'azure' or 'local' — where the PDF came from
- analyzed: 1=processed by AI, 0=pending, -1=failed
- swim_skill: AI-assessed swim ability — none, beginner, competent, strong, unknown
- risk_score: 1-10 (10 = highest risk), inferred by AI from report text
- risk_label: low / medium / high
- risk_factors: comma-separated contributing factors (e.g. unsupervised, alcohol, night-time)
- sql_data: JSON blob of the original SQL Server metadata record
- water_type: body of water category (see definitions below)
- victim_gender: Male, Female, Unknown
""")

# ── Body of water definitions ─────────────────────────────────────
bow_lines = ["The 'water_type' column uses these exact values — use them precisely in SQL:\n"]
for name, info in RAG_KNOWLEDGE["bow"].items():
    aliases = ", ".join(info.get("aliases", []))
    definition = info.get("definition", "").strip()
    bow_lines.append(f"  '{name}': {definition}")
    if aliases:
        bow_lines.append(f"    Also referred to as: {aliases}")

vn.train(documentation="\n".join(bow_lines))

# ── Activity definitions ──────────────────────────────────────────
act_lines = ["The 'activity' column (when present) uses these exact values:\n"]
for name, info in RAG_KNOWLEDGE["activity"].items():
    aliases = ", ".join(info.get("aliases", []))
    definition = info.get("definition", "").strip()
    act_lines.append(f"  '{name}': {definition}")
    if aliases:
        act_lines.append(f"    Also referred to as: {aliases}")

vn.train(documentation="\n".join(act_lines))

# ── Gender definitions ────────────────────────────────────────────
vn.train(documentation="""
The 'victim_gender' column uses: 'Male', 'Female', 'Unknown'.
Male aliases: man, boy, son, he. Female aliases: woman, girl, daughter, she.
""")

# ── Example queries ───────────────────────────────────────────────
vn.train(question="How many high-risk cases had no swim skills?",
         sql="SELECT COUNT(*) FROM cases WHERE risk_label='high' AND swim_skill='none'")

vn.train(question="Average risk score by swim skill level",
         sql="SELECT swim_skill, ROUND(AVG(risk_score),1) as avg_risk, COUNT(*) as total FROM cases WHERE analyzed=1 GROUP BY swim_skill ORDER BY avg_risk DESC")

vn.train(question="Most common risk factors",
         sql="SELECT risk_factors, COUNT(*) as count FROM cases WHERE risk_factors IS NOT NULL GROUP BY risk_factors ORDER BY count DESC LIMIT 10")

vn.train(question="How many cases involved children under 10?",
         sql="SELECT COUNT(*) FROM cases WHERE victim_age < 10")

vn.train(question="Risk breakdown by water type",
         sql="SELECT water_type, risk_label, COUNT(*) as count FROM cases WHERE analyzed=1 GROUP BY water_type, risk_label ORDER BY water_type")

vn.train(question="How many beach drownings were there?",
         sql="SELECT COUNT(*) FROM cases WHERE water_type='Beach'")

vn.train(question="How many cases happened in rivers or creeks?",
         sql="SELECT COUNT(*) FROM cases WHERE water_type='River/Creek'")

vn.train(question="How many cases involved swimming pools?",
         sql="SELECT COUNT(*) FROM cases WHERE water_type='Swimming Pool'")

vn.train(question="How many male vs female victims?",
         sql="SELECT victim_gender, COUNT(*) as count FROM cases WHERE analyzed=1 GROUP BY victim_gender ORDER BY count DESC")

vn.train(question="Which locations have the most cases?",
         sql="SELECT location, COUNT(*) as count FROM cases GROUP BY location ORDER BY count DESC LIMIT 15")

vn.train(question="How many cases are from Azure vs local?",
         sql="SELECT source, COUNT(*) as count FROM cases GROUP BY source")

vn.train(question="Show unanalyzed cases",
         sql="SELECT case_id, filename, source FROM cases WHERE analyzed=0 LIMIT 50")

print("Training complete.")
