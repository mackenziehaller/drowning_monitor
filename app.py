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

st.set_page_config(page_title="Drowning Cases Explorer", layout="wide")

# ── Login gate ────────────────────────────────────────────────────
if APP_PASSWORD:
    if not st.session_state.get("authenticated"):
        st.title("Drowning Cases Explorer")
        st.markdown("---")
        pwd = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            if pwd == APP_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()

st.title("🌊 Drowning Cases Explorer")
st.caption("Australian drowning incident monitor — powered by Google Gemini + SQLite")

# ── Run Pipeline button ───────────────────────────────────────────
with st.sidebar:
    st.header("Pipeline")
    st.caption("Search Google News for new Australian drowning cases from the past 72 hours.")
    if st.button("🔍 Run Pipeline Now", use_container_width=True, type="primary"):
        with st.spinner("Searching Google News and classifying cases... this takes 1-2 minutes."):
            try:
                result = subprocess.run(
                    [sys.executable, "run_pipeline.py"],
                    capture_output=True,
                    text=True,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                if result.returncode == 0:
                    st.success("Pipeline complete! Refresh the page to see new cases.")
                    st.code(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
                else:
                    st.error("Pipeline failed.")
                    st.code(result.stderr[-3000:] if len(result.stderr) > 3000 else result.stderr)
            except Exception as e:
                st.error(f"Could not run pipeline: {e}")
    st.markdown("---")

# ── Helpers ───────────────────────────────────────────────────────

def get_conn():
    return sqlite3.connect(DB_PATH)

def db_query(sql, params=()):
    try:
        conn = get_conn()
        df = pd.read_sql_query(sql, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

def total_cases():
    try:
        conn = get_conn()
        n = conn.execute("SELECT COUNT(*) FROM drowning_cases").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0

# ── Top metrics ───────────────────────────────────────────────────
total = total_cases()

if total == 0:
    st.warning("No cases in database yet. Run `python run_pipeline.py` to fetch cases.")
else:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Cases", f"{total:,}")

    fatal = db_query("SELECT COUNT(*) as n FROM drowning_cases WHERE outcome='Fatal'")
    m2.metric("Fatal", f"{fatal.iloc[0]['n']:,}" if not fatal.empty else "—")

    rescued = db_query("SELECT COUNT(*) as n FROM drowning_cases WHERE outcome='Rescued'")
    m3.metric("Rescued", f"{rescued.iloc[0]['n']:,}" if not rescued.empty else "—")

    recent = db_query("SELECT COUNT(*) as n FROM drowning_cases WHERE date(date_fetched) = date('now')")
    m4.metric("Added Today", f"{recent.iloc[0]['n']:,}" if not recent.empty else "—")

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🔍 Search Cases", "📊 Insights", "📋 Recent Cases"])


# ── Tab 1: Search ─────────────────────────────────────────────────
with tab1:
    st.subheader("Search Cases")

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        keyword = st.text_input("Search by location, summary or keyword:", placeholder="e.g. Bondi Beach, river, child")
    with col2:
        state_filter = st.selectbox("State", ["All", "NSW", "QLD", "VIC", "WA", "SA", "TAS", "NT", "ACT", "Unknown"])
    with col3:
        outcome_filter = st.selectbox("Outcome", ["All", "Fatal", "Hospitalised", "Rescued", "Missing", "Unknown"])

    where = []
    params = []

    if keyword:
        where.append("(location_name LIKE ? OR summary LIKE ? OR activity LIKE ?)")
        params += [f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"]
    if state_filter != "All":
        where.append("state = ?")
        params.append(state_filter)
    if outcome_filter != "All":
        where.append("outcome = ?")
        params.append(outcome_filter)

    where_clause = "WHERE " + " AND ".join(where) if where else ""

    results = db_query(f"""
        SELECT id, date_of_incident, location_name, location_type, state,
               age_group, gender, outcome, activity, source, summary, url
        FROM drowning_cases
        {where_clause}
        ORDER BY date_fetched DESC
        LIMIT 100
    """, params)

    if results.empty:
        st.info("No results found.")
    else:
        st.caption(f"{len(results)} result(s)")
        selected = st.dataframe(
            results.drop(columns=["summary", "url"]),
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
            key="search_results"
        )

        if selected and selected.selection.rows:
            row = results.iloc[selected.selection.rows[0]]
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"### {row['location_name']}")
                st.markdown(f"**Date:** {row['date_of_incident']}  |  **State:** {row['state']}")
                st.markdown(f"**Location type:** {row['location_type']}")
                st.markdown(f"**Victim:** {row['age_group']} · {row['gender']}")
                st.markdown(f"**Activity:** {row['activity']}")
                outcome_icon = {"Fatal": "🔴", "Hospitalised": "🟡", "Rescued": "🟢", "Missing": "🟠"}.get(row['outcome'], "⚪")
                st.markdown(f"**Outcome:** {outcome_icon} {row['outcome']}")
                st.markdown(f"**Source:** {row['source']}")
                if row['url']:
                    st.markdown(f"[Read article]({row['url']})")
            with c2:
                if row['summary']:
                    st.markdown("**Summary**")
                    st.info(row['summary'])


# ── Tab 2: Insights ───────────────────────────────────────────────
with tab2:
    st.subheader("Insights")

    if total == 0:
        st.warning("No data yet.")
    else:
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

        st.markdown("**Cases by Activity**")
        act_df = db_query("SELECT activity, COUNT(*) as count FROM drowning_cases WHERE activity IS NOT NULL GROUP BY activity ORDER BY count DESC LIMIT 15")
        if not act_df.empty:
            fig = px.bar(act_df, x="activity", y="count")
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


# ── Tab 3: Recent Cases ───────────────────────────────────────────
with tab3:
    st.subheader("Most Recently Added Cases")

    recent_df = db_query("""
        SELECT date_fetched, date_of_incident, location_name, state,
               location_type, age_group, gender, outcome, activity, source, url
        FROM drowning_cases
        ORDER BY date_fetched DESC
        LIMIT 50
    """)

    if recent_df.empty:
        st.info("No cases yet.")
    else:
        st.caption(f"Showing {len(recent_df)} most recent cases")
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
