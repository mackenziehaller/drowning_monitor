import json
import sqlite3
import ollama
import streamlit as st
import pandas as pd
import plotly.express as px
from vanna_setup import vn
from config import DB_PATH, OLLAMA_MODEL, APP_PASSWORD

# RAG is optional — app still works if chroma_db hasn't been built yet
try:
    from rag_query import ask as rag_ask, search as rag_search
    RAG_AVAILABLE = True
except Exception:
    RAG_AVAILABLE = False

st.set_page_config(page_title="Drowning Cases Explorer", layout="wide")

# ── Login gate ────────────────────────────────────────────────────
if APP_PASSWORD:
    if not st.session_state.get("authenticated"):
        st.title("Drowning Cases Explorer")
        st.markdown("---")
        with st.container(border=True):
            st.markdown("#### 🔒 Login required")
            label_col, badge_col = st.columns([4, 1])
            with label_col:
                pwd = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter app password",
                    help="Masked — your keystrokes are hidden and never displayed on screen.",
                    label_visibility="visible",
                )
            with badge_col:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    '<span title="Masked" style="background:#c0392b;color:white;'
                    'padding:4px 10px;border-radius:6px;font-size:0.8em;'
                    'font-weight:bold;letter-spacing:0.05em;">MASKED</span>',
                    unsafe_allow_html=True,
                )
            st.caption("The dots shown while typing are a **mask** — your password is never displayed in plain text.")
            if st.button("Login", use_container_width=True):
                if pwd == APP_PASSWORD:
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
        st.stop()

st.title("Drowning Cases Explorer")
st.caption("Fully offline — powered by Ollama + SQLite")

# ── Helpers ───────────────────────────────────────────────────────

def get_conn():
    return sqlite3.connect(DB_PATH)

def db_query(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


# ── Tabs ──────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Search", "Ask a Question", "Search by Content (RAG)", "Insights", "Batch Status"])


# ── Tab 1: Search by ID or name ───────────────────────────────────

with tab1:
    st.subheader("Search Cases")
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Case ID or keyword:", placeholder="e.g. 2023-FL-0042 or Lake Tahoe")
    with col2:
        search_btn = st.button("Search", use_container_width=True)

    if search_btn and query:
        results = db_query("""
            SELECT case_id, filename, source, risk_label, risk_score, swim_skill,
                   victim_age, victim_gender, water_type, location, incident_date, analyzed
            FROM cases
            WHERE case_id LIKE ? OR location LIKE ? OR summary LIKE ?
            ORDER BY incident_date DESC
            LIMIT 50
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))

        if results.empty:
            st.warning("No cases found.")
        else:
            st.write(f"{len(results)} result(s)")
            selected = st.dataframe(
                results,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun",
                key="search_results"
            )

            if selected and selected.selection.rows:
                row_idx = selected.selection.rows[0]
                case_id = results.iloc[row_idx]["case_id"]

                case = db_query("SELECT * FROM cases WHERE case_id=?", (case_id,))
                if not case.empty:
                    row = case.iloc[0]
                    st.divider()
                    c1, c2 = st.columns(2)

                    with c1:
                        st.markdown(f"### Case: {case_id}")
                        st.markdown(f"**Source:** {row.get('source', '—')}  |  **Date:** {row.get('incident_date', '—')}")
                        st.markdown(f"**Location:** {row.get('location', '—')}")
                        st.markdown(f"**Water type:** {row.get('water_type', '—')}")
                        st.markdown(f"**Victim:** {row.get('victim_age', '—')} y/o {row.get('victim_gender', '—')}")
                        st.markdown(f"**Swim skill:** {row.get('swim_skill', '—')}")
                        risk_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(str(row.get("risk_label", "")), "⚪")
                        st.markdown(f"**Risk:** {risk_color} {row.get('risk_label', '—')} (score: {row.get('risk_score', '—')})")
                        st.markdown(f"**Risk factors:** {row.get('risk_factors', '—')}")

                    with c2:
                        if row.get("summary"):
                            st.markdown("**AI Summary**")
                            st.info(row["summary"])

                        if row.get("sql_data"):
                            with st.expander("SQL Server record"):
                                try:
                                    st.json(json.loads(row["sql_data"]))
                                except Exception:
                                    st.text(row["sql_data"])

                    if row.get("analyzed") == 1 and st.button("Re-analyze this case with Ollama"):
                        with st.spinner("Re-analyzing..."):
                            from analyze_reports import PROMPT
                            text = row.get("raw_text", "")[:5000]
                            response = ollama.chat(
                                model=OLLAMA_MODEL,
                                messages=[{"role": "user", "content": PROMPT.format(text=text)}]
                            )
                            st.markdown(response["message"]["content"])


# ── Tab 2: Ask a Question ─────────────────────────────────────────

with tab2:
    st.subheader("Ask a Question")
    st.caption("Ask anything about the cases in plain English.")

    question = st.text_input(
        "Question:",
        placeholder="e.g. How many high-risk cases involved children under 10?"
    )

    if question:
        with st.spinner("Thinking..."):
            try:
                sql, df, fig = vn.ask(question, print_results=False)

                if df is not None and not df.empty:
                    st.dataframe(df, use_container_width=True)
                else:
                    st.warning("No results returned.")

                if fig is not None:
                    st.plotly_chart(fig, use_container_width=True)

                with st.expander("View generated SQL"):
                    st.code(sql, language="sql")

            except Exception as e:
                st.error(f"Could not generate answer: {e}")


# ── Tab 3: RAG — Search by Content ───────────────────────────────

with tab3:
    st.subheader("Search by Content")
    st.caption("Ask questions about what's written in the reports — no structured extraction needed.")

    if not RAG_AVAILABLE:
        st.warning("Vector database not built yet. Run `embed_pdfs.py` first.")
    else:
        rag_question = st.text_input(
            "Ask anything about the reports:",
            placeholder="e.g. Were any victims described as weak swimmers? Any cases involving alcohol?"
        )

        if rag_question:
            with st.spinner("Searching reports..."):
                try:
                    answer, sources = rag_ask(rag_question)
                    st.markdown(answer)
                    with st.expander(f"Source cases ({len(sources)})"):
                        for s in sources:
                            st.markdown(f"- `{s}`")
                except Exception as e:
                    st.error(f"RAG query failed: {e}")

        st.divider()
        st.markdown("**Semantic search** — find cases similar to a description")
        semantic_q = st.text_input("Describe what you're looking for:", placeholder="e.g. child fell into backyard pool unsupervised")
        if semantic_q:
            with st.spinner("Finding similar cases..."):
                try:
                    chunks = rag_search(semantic_q, n_results=5)
                    for chunk in chunks:
                        with st.expander(f"Case {chunk['case_id']} — {chunk['location']}"):
                            st.text(chunk["text"])
                except Exception as e:
                    st.error(f"Search failed: {e}")


# ── Tab 4: Insights ───────────────────────────────────────────────

with tab4:
    st.subheader("Insights")

    analyzed_count = db_query("SELECT COUNT(*) as n FROM cases WHERE analyzed=1").iloc[0]["n"]
    if analyzed_count == 0:
        st.warning("No analyzed cases yet. Run analyze_reports.py first.")
    else:
        st.caption(f"Based on {analyzed_count:,} analyzed cases")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Swim Skill Distribution**")
            skill_df = db_query("""
                SELECT swim_skill, COUNT(*) as count FROM cases
                WHERE analyzed=1 AND swim_skill IS NOT NULL
                GROUP BY swim_skill ORDER BY count DESC
            """)
            if not skill_df.empty:
                fig = px.pie(skill_df, names="swim_skill", values="count", hole=0.4)
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**Risk Label Distribution**")
            risk_df = db_query("""
                SELECT risk_label, COUNT(*) as count FROM cases
                WHERE analyzed=1 AND risk_label IS NOT NULL
                GROUP BY risk_label
            """)
            if not risk_df.empty:
                color_map = {"high": "#e74c3c", "medium": "#f39c12", "low": "#2ecc71"}
                fig = px.bar(risk_df, x="risk_label", y="count",
                             color="risk_label", color_discrete_map=color_map)
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Risk Score by Swim Skill**")
        combo_df = db_query("""
            SELECT swim_skill, ROUND(AVG(risk_score), 1) as avg_risk, COUNT(*) as count
            FROM cases WHERE analyzed=1 AND swim_skill IS NOT NULL
            GROUP BY swim_skill ORDER BY avg_risk DESC
        """)
        if not combo_df.empty:
            fig = px.bar(combo_df, x="swim_skill", y="avg_risk",
                         text="count", labels={"avg_risk": "Average Risk Score (1-10)"})
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Risk by Water Type**")
        water_df = db_query("""
            SELECT water_type, risk_label, COUNT(*) as count
            FROM cases WHERE analyzed=1 AND water_type IS NOT NULL
            GROUP BY water_type, risk_label
        """)
        if not water_df.empty:
            fig = px.bar(water_df, x="water_type", y="count", color="risk_label",
                         color_discrete_map={"high": "#e74c3c", "medium": "#f39c12", "low": "#2ecc71"},
                         barmode="stack")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("**AI Narrative Summary**")
        if st.button("Generate summary across all cases"):
            with st.spinner("Analyzing all cases..."):
                from summarize import run_summary
                st.markdown(run_summary())


# ── Tab 5: Batch Status ───────────────────────────────────────────

with tab5:
    st.subheader("Batch Processing Status")

    status_df = db_query("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN analyzed=1 THEN 1 ELSE 0 END) as done,
            SUM(CASE WHEN analyzed=0 THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN analyzed=-1 THEN 1 ELSE 0 END) as failed,
            SUM(CASE WHEN raw_text='' OR raw_text IS NULL THEN 1 ELSE 0 END) as no_text
        FROM cases
    """)

    row = status_df.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total cases", f"{int(row['total']):,}")
    c2.metric("Analyzed", f"{int(row['done']):,}")
    c3.metric("Pending", f"{int(row['pending']):,}")
    c4.metric("Failed / no text", f"{int(row['failed']) + int(row['no_text']):,}")

    if row["total"] > 0:
        pct = int(row["done"]) / int(row["total"])
        st.progress(pct, text=f"{pct:.0%} complete")

    st.markdown("**To process the next batch, run in your terminal:**")
    st.code("python analyze_reports.py", language="bash")

    source_df = db_query("""
        SELECT source, COUNT(*) as count FROM cases GROUP BY source
    """)
    if not source_df.empty:
        st.markdown("**Cases by source**")
        st.dataframe(source_df, use_container_width=True, hide_index=True)
