"""
dashboard.py — Module 5: Dashboard & Visualization (Streamlit)

Real-time security dashboard reading directly from the SOAR case store and
the ML-scored queue: live alert feed, TI summary, ML anomaly visualization,
and SOAR playbook status with drill-down into any case.

Run:
    streamlit run dashboard.py
"""
import json
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from common import load_config, resolve_path, read_jsonl

cfg = load_config()

st.set_page_config(
    page_title=cfg["dashboard"]["title"],
    page_icon=cfg["dashboard"]["page_icon"],
    layout="wide",
)


@st.cache_data(ttl=cfg["dashboard"]["refresh_seconds"])
def load_data():
    cases_path = resolve_path(cfg, "cases_db")
    scored_path = resolve_path(cfg, "scored_queue")
    cases = json.loads(cases_path.read_text()) if cases_path.exists() else []
    scored = read_jsonl(scored_path)
    return cases, scored


def main():
    st.title(f"{cfg['dashboard']['page_icon']} {cfg['dashboard']['title']}")
    st.caption("Data Ingestion → Threat Intel → ML Detection → SOAR → Dashboard")

    cases, scored = load_data()
    cases_df = pd.DataFrame(cases)
    scored_df = pd.json_normalize(scored) if scored else pd.DataFrame()

    # --- KPI row ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Events processed", len(scored))
    c2.metric("Cases opened", len(cases))
    n_auto = len(cases_df[cases_df.get("tier") == "high"]) if not cases_df.empty else 0
    n_review = len(cases_df[cases_df.get("tier") == "medium"]) if not cases_df.empty else 0
    c3.metric("Auto-contained (high)", n_auto)
    c4.metric("Pending analyst review", n_review)

    st.divider()
    left, right = st.columns([3, 2])

    # --- Live alert feed / case management ---
    with left:
        st.subheader("🚨 Live Alert Feed / Case Queue")
        if cases_df.empty:
            st.info("No cases yet — run `python platform.py --mode full` to generate data.")
        else:
            status_filter = st.multiselect(
                "Filter by status", options=sorted(cases_df["status"].unique()),
                default=list(cases_df["status"].unique()),
            )
            filtered = cases_df[cases_df["status"].isin(status_filter)].sort_values(
                "created_at", ascending=False
            )
            st.dataframe(
                filtered[["case_id", "created_at", "indicator", "tier", "confidence", "status"]],
                use_container_width=True, hide_index=True,
            )
            case_ids = filtered["case_id"].tolist()
            if case_ids:
                pick = st.selectbox("Drill into case", case_ids)
                detail = filtered[filtered["case_id"] == pick].iloc[0].to_dict()
                st.json(detail)

    # --- SOAR playbook status ---
    with right:
        st.subheader("⚙️ SOAR Playbook Status")
        if not cases_df.empty:
            status_counts = cases_df["tier"].value_counts().reset_index()
            status_counts.columns = ["tier", "count"]
            fig = px.pie(status_counts, names="tier", values="count", hole=0.45,
                         color="tier",
                         color_discrete_map={"high": "#d62728", "medium": "#ff7f0e", "low": "#2ca02c"})
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    bottom_left, bottom_right = st.columns(2)

    # --- Threat intel summary ---
    with bottom_left:
        st.subheader("🌐 Threat Intelligence Summary")
        if not scored_df.empty and "threat_intel.risk_score" in scored_df.columns:
            fig_ti = px.histogram(scored_df, x="threat_intel.risk_score", nbins=20,
                                  title="TI Risk Score Distribution")
            st.plotly_chart(fig_ti, use_container_width=True)
            top_indicators = (
                scored_df.groupby("threat_intel.indicator")["threat_intel.risk_score"]
                .max().sort_values(ascending=False).head(10)
            )
            st.write("Highest-risk indicators seen:")
            st.dataframe(top_indicators.rename("risk_score"))

    # --- ML anomaly visualization ---
    with bottom_right:
        st.subheader("🤖 ML Anomaly Detection")
        if not scored_df.empty and "ml_detection.anomaly_score" in scored_df.columns:
            fig_ml = px.histogram(
                scored_df, x="ml_detection.anomaly_score", color="ml_detection.is_anomaly",
                nbins=30, title="Isolation Forest Anomaly Scores",
                color_discrete_map={True: "#d62728", False: "#1f77b4"},
            )
            st.plotly_chart(fig_ml, use_container_width=True)

    st.caption(f"Auto-refreshing every {cfg['dashboard']['refresh_seconds']}s • "
               f"Last loaded {time.strftime('%H:%M:%S')}")


if __name__ == "__main__":
    main()
