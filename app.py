import sqlite3
import os
import subprocess
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "drowning_cases.db")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

st.set_page_config(page_title="Drowning Cases Monitor", layout="wide")

# ── Login gate ────────────────────────────────────────────────────
if APP_PASSWORD:
    if not st.session_state.get("authenticated"):
        st.title("Drowning Cases Monitor")
        st.markdown("---")
        pwd = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            if pwd == APP_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()

# ── DB helpers ────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_reviews_table():
    """Create reviews table if it doesn't exist."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                reviewer TEXT NOT NULL,
                approved INTEGER NOT NULL,
                notes TEXT,
                reviewed_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

def get_unreviewed(limit, offset, state_filter, outcome_filter, search_text):
    where = ["r.id IS NULL"]
    params = []
    if state_filter:
        where.append("c.state = ?")
        params.append(state_filter)
    if outcome_filter:
        where.append("c.outcome = ?")
        params.append(outcome_filter)
    if search_text:
        where.append("(c.location_name LIKE ? OR c.summary LIKE ?)")
        params += [f"%{search_text}%", f"%{search_text}%"]
    where_clause = " AND ".join(where)
    params += [limit, offset]
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT c.* FROM drowning_cases c
            LEFT JOIN reviews r ON r.case_id = c.id
            WHERE {where_clause}
            ORDER BY c.date_fetched DESC
            LIMIT ? OFFSET ?
        """, params).fetchall()

def count_unreviewed(state_filter, outcome_filter, search_text):
    where = ["r.id IS NULL"]
    params = []
    if state_filter:
        where.append("c.state = ?")
        params.append(state_filter)
    if outcome_filter:
        where.append("c.outcome = ?")
        params.append(outcome_filter)
    if search_text:
        where.append("(c.location_name LIKE ? OR c.summary LIKE ?)")
        params += [f"%{search_text}%", f"%{search_text}%"]
    where_clause = " AND ".join(where)
    with get_conn() as conn:
        return conn.execute(f"""
            SELECT COUNT(*) FROM drowning_cases c
            LEFT JOIN reviews r ON r.case_id = c.id
            WHERE {where_clause}
        """, params).fetchone()[0]

def save_review(case_id, reviewer, approved, notes):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reviews (case_id, reviewer, approved, notes) VALUES (?, ?, ?, ?)",
            (case_id, reviewer, 1 if approved else 0, notes)
        )
        conn.commit()

def db_query(sql, params=()):
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(sql, conn, params=params)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

init_reviews_table()

# ── Sidebar ───────────────────────────────────────────────────────
st.sidebar.title("🌊 Drowning Monitor")

# Run pipeline
st.sidebar.markdown("### Run Pipeline")
st.sidebar.caption("Search Google News for new cases from the past 72 hours.")
if st.sidebar.button("🔍 Search for New Cases", use_container_width=True, type="primary"):
    with st.sidebar:
        with st.spinner("Running pipeline... 1-2 minutes"):
            try:
                result = subprocess.run(
                    [sys.executable, "run_pipeline.py"],
                    capture_output=True, text=True,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                if result.returncode == 0:
                    st.success("Done! New cases loaded.")
                    st.rerun()
                else:
                    st.error("Pipeline failed.")
                    st.code(result.stderr[-2000:])
            except Exception as e:
                st.error(f"Error: {e}")

st.sidebar.markdown("---")

# Settings
st.sidebar.markdown("### Settings")
reviewer = st.sidebar.text_input("Reviewer initials", value="MH")
batch_size = st.sidebar.slider("Cases per page", 5, 50, 10)

st.sidebar.markdown("---")

# Filters
st.sidebar.markdown("### Filters")
state_filter = st.sidebar.selectbox("State", ["", "NSW", "QLD", "VIC", "WA", "SA", "TAS", "NT", "ACT", "Unknown"])
outcome_filter = st.sidebar.selectbox("Outcome", ["", "Fatal", "Hospitalised", "Rescued", "Missing", "Unknown"])
search_text = st.sidebar.text_input("Search keyword", "")

# Pagination
if "page" not in st.session_state:
    st.session_state.page = 0

total_unreviewed = count_unreviewed(state_filter or None, outcome_filter or None, search_text or None)
st.sidebar.markdown(f"**Unreviewed: {total_unreviewed}**")

max_page = max((total_unreviewed - 1) // batch_size, 0)
col1, col2, col3 = st.sidebar.columns(3)
if col1.button("⏮️"):
    st.session_state.page = 0
if col2.button("◀️") and st.session_state.page > 0:
    st.session_state.page -= 1
if col3.button("▶️") and st.session_state.page < max_page:
    st.session_state.page += 1

st.sidebar.caption(f"Page {st.session_state.page + 1} of {max_page + 1}")

# ── Main tabs ─────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📋 Review Cases", "📊 Insights"])

# ── Tab 1: Review ─────────────────────────────────────────────────
with tab1:
    st.title("Review Cases")

    offset = st.session_state.page * batch_size
    rows = get_unreviewed(
        batch_size, offset,
        state_filter or None,
        outcome_filter or None,
        search_text or None
    )

    if not rows:
        st.success("✅ All caught up — no unreviewed cases with current filters.")
    else:
        st.caption(f"Showing {len(rows)} of {total_unreviewed} unreviewed cases")

        for row in rows:
            outcome_icon = {"Fatal": "🔴", "Hospitalised": "🟡", "Rescued": "🟢", "Missing": "🟠"}.get(row["outcome"], "⚪")
            title = f"{outcome_icon} {row['date_of_incident']} — {row['location_name']} ({row['state']}) — {row['outcome']}"

            with st.expander(title, expanded=True):
                left, right = st.columns([2, 1])

                with left:
                    st.markdown(f"**Location:** {row['location_name']} ({row['location_type']}), {row['state']}")
                    st.markdown(f"**Date:** {row['date_of_incident']}")
                    st.markdown(f"**Victim:** {row['age_group']} · {row['gender']}")
                    st.markdown(f"**Activity:** {row['activity']}")
                    st.markdown(f"**Outcome:** {outcome_icon} {row['outcome']}")
                    st.markdown(f"**Source:** {row['source']}")
                    if row["url"]:
                        st.markdown(f"[Read full article ↗]({row['url']})")
                    if row["summary"]:
                        st.info(row["summary"])

                with right:
                    st.markdown("**Review**")
                    notes = st.text_input("Notes (optional)", key=f"notes_{row['id']}")
                    b1, b2 = st.columns(2)
                    if b1.button("✅ Approve", key=f"approve_{row['id']}", use_container_width=True):
                        save_review(row["id"], reviewer or "anon", True, notes or "approved")
                        st.success("Approved!")
                        st.rerun()
                    if b2.button("❌ Reject", key=f"reject_{row['id']}", use_container_width=True):
                        save_review(row["id"], reviewer or "anon", False, notes or "rejected")
                        st.warning("Rejected.")
                        st.rerun()


# ── Tab 2: Insights ───────────────────────────────────────────────
with tab2:
    st.title("Insights")

    total = db_query("SELECT COUNT(*) as n FROM drowning_cases").iloc[0]["n"] if not db_query("SELECT COUNT(*) as n FROM drowning_cases").empty else 0
    approved = db_query("SELECT COUNT(*) as n FROM reviews WHERE approved=1").iloc[0]["n"] if not db_query("SELECT COUNT(*) as n FROM reviews WHERE approved=1").empty else 0
    rejected = db_query("SELECT COUNT(*) as n FROM reviews WHERE approved=0").iloc[0]["n"] if not db_query("SELECT COUNT(*) as n FROM reviews WHERE approved=0").empty else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Cases", f"{total:,}")
    m2.metric("Approved", f"{approved:,}")
    m3.metric("Rejected", f"{rejected:,}")
    m4.metric("Pending Review", f"{total - approved - rejected:,}")

    if total > 0:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Cases by Outcome**")
            outcome_df = db_query("SELECT outcome, COUNT(*) as count FROM drowning_cases GROUP BY outcome ORDER BY count DESC")
            if not outcome_df.empty:
                color_map = {"Fatal": "#e74c3c", "Hospitalised": "#f39c12", "Rescued": "#2ecc71", "Missing": "#e67e22", "Unknown": "#95a5a6"}
                fig = px.bar(outcome_df, x="outcome", y="count", color="outcome", color_discrete_map=color_map)
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("**Cases by Location Type**")
            loc_df = db_query("SELECT location_type, COUNT(*) as count FROM drowning_cases GROUP BY location_type ORDER BY count DESC")
            if not loc_df.empty:
                fig = px.pie(loc_df, names="location_type", values="count", hole=0.4)
                st.plotly_chart(fig, use_container_width=True)

        col3, col4 = st.columns(2)

        with col3:
            st.markdown("**Cases by State**")
            state_df = db_query("SELECT state, COUNT(*) as count FROM drowning_cases GROUP BY state ORDER BY count DESC")
            if not state_df.empty:
                fig = px.bar(state_df, x="state", y="count")
                st.plotly_chart(fig, use_container_width=True)

        with col4:
            st.markdown("**Cases by Age Group**")
            age_df = db_query("SELECT age_group, COUNT(*) as count FROM drowning_cases GROUP BY age_group ORDER BY count DESC")
            if not age_df.empty:
                fig = px.pie(age_df, names="age_group", values="count", hole=0.4)
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Daily Intake (last 30 days)**")
        daily_df = db_query("""
            SELECT date(date_fetched) as day, COUNT(*) as count
            FROM drowning_cases
            WHERE date_fetched >= date('now', '-30 days')
            GROUP BY day ORDER BY day ASC
        """)
        if not daily_df.empty:
            fig = px.bar(daily_df, x="day", y="count")
            st.plotly_chart(fig, use_container_width=True)
