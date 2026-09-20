"""
dashboard.py — Module 5: Dashboard & Visualization (Streamlit)

Real-time security dashboard reading directly from the SOAR case store and
the ML-scored queue: live alert feed, TI summary, ML anomaly visualization,
and SOAR playbook status with drill-down into any case.

Styling: bright theme (see .streamlit/config.toml), a custom Google Font,
colorful interactive KPI cards, and a scroll-reveal animation (sections
softly fade/slide in as you scroll to them) injected via custom CSS + JS.

Run:
    streamlit run dashboard.py
"""
import json
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from common import load_config, resolve_path, read_jsonl

cfg = load_config()

st.set_page_config(
    page_title=cfg["dashboard"]["title"],
    page_icon=cfg["dashboard"]["page_icon"],
    layout="wide",
)

PALETTE = {
    "purple": "#7C5CFC", "purple_dark": "#5B3FE0",
    "pink": "#FF6FA5", "orange": "#FF9F5A", "green": "#22C596",
    "red": "#FF5D73", "blue": "#4FB6FF", "bg_card": "#FFFFFF",
    "text": "#1E1B2E", "muted": "#6B6684",
}
TIER_COLORS = {"high": PALETTE["red"], "medium": PALETTE["orange"], "low": PALETTE["green"]}
PLOTLY_TEMPLATE = "plotly_white"


def inject_theme():
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');

      html, body, [class*="css"] {{
        font-family: 'Poppins', sans-serif !important;
      }}

      .stApp {{
        background: radial-gradient(1200px 600px at 10% -10%, #F4F1FF 0%, #FFFFFF 45%),
                    radial-gradient(1000px 500px at 100% 0%, #FFF3F8 0%, #FFFFFF 40%);
      }}

      /* Hero header */
      .hero {{
        background: linear-gradient(120deg, {PALETTE['purple']} 0%, {PALETTE['pink']} 100%);
        border-radius: 20px;
        padding: 28px 32px;
        margin-bottom: 28px;
        box-shadow: 0 12px 30px rgba(124, 92, 252, 0.25);
      }}
      .hero h1 {{
        color: white; font-weight: 800; font-size: 2.1rem; margin: 0 0 4px 0;
      }}
      .hero p {{
        color: rgba(255,255,255,0.9); font-weight: 500; margin: 0; font-size: 0.95rem;
      }}

      /* KPI cards */
      .kpi-card {{
        background: {PALETTE['bg_card']};
        border-radius: 16px;
        padding: 20px 22px;
        border: 1px solid #EFEAFE;
        box-shadow: 0 4px 14px rgba(30, 27, 46, 0.06);
        transition: transform 0.25s ease, box-shadow 0.25s ease;
      }}
      .kpi-card:hover {{
        transform: translateY(-6px) scale(1.015);
        box-shadow: 0 14px 28px rgba(124, 92, 252, 0.22);
      }}
      .kpi-label {{ color: {PALETTE['muted']}; font-size: 0.82rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; }}
      .kpi-value {{ font-size: 2.1rem; font-weight: 800; margin-top: 6px; }}
      .kpi-bar {{ height: 4px; border-radius: 4px; margin-top: 14px; }}

      /* Section headers */
      .section-title {{
        font-weight: 700; font-size: 1.15rem; color: {PALETTE['text']};
        margin: 6px 0 14px 0; display: flex; align-items: center; gap: 8px;
      }}

      /* Dataframe / widget polish */
      div[data-testid="stDataFrame"] {{
        border-radius: 14px; overflow: hidden; border: 1px solid #EFEAFE;
      }}
      div[data-testid="stMetric"] {{ display: none; }}  /* replaced by custom KPI cards */

      /* Scroll-reveal base state */
      .reveal-target {{
        opacity: 0;
        transform: translateY(26px);
        transition: opacity 0.7s cubic-bezier(.2,.7,.3,1), transform 0.7s cubic-bezier(.2,.7,.3,1);
      }}
      .reveal-target.is-visible {{ opacity: 1; transform: translateY(0); }}
    </style>
    """, unsafe_allow_html=True)


def inject_scroll_reveal():
    """Fades/slides each top-level Streamlit block in as it scrolls into view.
    Runs inside an invisible components.html iframe, reaching into the
    parent document (same-origin) since Streamlit's own st.markdown can't
    execute <script> tags directly."""
    components.html("""
    <script>
      const doc = window.parent.document;
      function applyReveal() {
        const targets = doc.querySelectorAll(
          '[data-testid="stVerticalBlockBorderWrapper"], [data-testid="element-container"]'
        );
        targets.forEach(el => { if (!el.classList.contains('reveal-target')) el.classList.add('reveal-target'); });
        if (!window.__revealObserver) {
          window.__revealObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
              if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                window.__revealObserver.unobserve(entry.target);
              }
            });
          }, { threshold: 0.08 });
        }
        targets.forEach(el => {
          if (!el.classList.contains('is-visible')) window.__revealObserver.observe(el);
        });
      }
      let tries = 0;
      const iv = setInterval(() => { applyReveal(); if (++tries > 12) clearInterval(iv); }, 400);
    </script>
    """, height=0)


def kpi_card(col, label, value, color, icon):
    col.markdown(f"""
      <div class="kpi-card">
        <div class="kpi-label">{icon} &nbsp;{label}</div>
        <div class="kpi-value" style="color:{color};">{value}</div>
        <div class="kpi-bar" style="background:{color};"></div>
      </div>
    """, unsafe_allow_html=True)


@st.cache_data(ttl=cfg["dashboard"]["refresh_seconds"])
def load_data():
    cases_path = resolve_path(cfg, "cases_db")
    scored_path = resolve_path(cfg, "scored_queue")
    cases = json.loads(cases_path.read_text()) if cases_path.exists() else []
    scored = read_jsonl(scored_path)
    return cases, scored


def main():
    inject_theme()

    st.markdown(f"""
      <div class="hero">
        <h1>{cfg['dashboard']['page_icon']} {cfg['dashboard']['title']}</h1>
        <p>Data Ingestion &nbsp;→&nbsp; Threat Intel &nbsp;→&nbsp; ML Detection &nbsp;→&nbsp; SOAR &nbsp;→&nbsp; Dashboard</p>
      </div>
    """, unsafe_allow_html=True)

    cases, scored = load_data()
    cases_df = pd.DataFrame(cases)
    scored_df = pd.json_normalize(scored) if scored else pd.DataFrame()

    # --- KPI row (custom interactive cards) ---
    n_auto = len(cases_df[cases_df.get("tier") == "high"]) if not cases_df.empty else 0
    n_review = len(cases_df[cases_df.get("tier") == "medium"]) if not cases_df.empty else 0
    k1, k2, k3, k4 = st.columns(4)
    kpi_card(k1, "Events processed", len(scored), PALETTE["purple"], "📊")
    kpi_card(k2, "Cases opened", len(cases), PALETTE["blue"], "🗂️")
    kpi_card(k3, "Auto-contained (high)", n_auto, PALETTE["red"], "🛡️")
    kpi_card(k4, "Pending analyst review", n_review, PALETTE["orange"], "⏳")

    st.write("")
    left, right = st.columns([3, 2])

    # --- Live alert feed / case management ---
    with left:
        st.markdown('<div class="section-title">🚨 Live Alert Feed / Case Queue</div>', unsafe_allow_html=True)
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
        st.markdown('<div class="section-title">⚙️ SOAR Playbook Status</div>', unsafe_allow_html=True)
        if not cases_df.empty:
            status_counts = cases_df["tier"].value_counts().reset_index()
            status_counts.columns = ["tier", "count"]
            fig = px.pie(status_counts, names="tier", values="count", hole=0.5,
                         color="tier", color_discrete_map=TIER_COLORS, template=PLOTLY_TEMPLATE)
            fig.update_traces(textfont_size=13, marker=dict(line=dict(color="#FFFFFF", width=2)))
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)

    st.write("")
    bottom_left, bottom_right = st.columns(2)

    # --- Threat intel summary ---
    with bottom_left:
        st.markdown('<div class="section-title">🌐 Threat Intelligence Summary</div>', unsafe_allow_html=True)
        if not scored_df.empty and "threat_intel.risk_score" in scored_df.columns:
            fig_ti = px.histogram(scored_df, x="threat_intel.risk_score", nbins=20,
                                  template=PLOTLY_TEMPLATE,
                                  color_discrete_sequence=[PALETTE["purple"]])
            fig_ti.update_layout(margin=dict(t=10, b=10, l=10, r=10), bargap=0.08,
                                 xaxis_title="TI risk score", yaxis_title="events")
            st.plotly_chart(fig_ti, use_container_width=True)
            top_indicators = (
                scored_df.groupby("threat_intel.indicator")["threat_intel.risk_score"]
                .max().sort_values(ascending=False).head(10)
            )
            st.caption("Highest-risk indicators seen")
            st.dataframe(top_indicators.rename("risk_score"), use_container_width=True)

    # --- ML anomaly visualization ---
    with bottom_right:
        st.markdown('<div class="section-title">🤖 ML Anomaly Detection</div>', unsafe_allow_html=True)
        if not scored_df.empty and "ml_detection.anomaly_score" in scored_df.columns:
            fig_ml = px.histogram(
                scored_df, x="ml_detection.anomaly_score", color="ml_detection.is_anomaly",
                nbins=30, template=PLOTLY_TEMPLATE,
                color_discrete_map={True: PALETTE["red"], False: PALETTE["blue"]},
            )
            fig_ml.update_layout(margin=dict(t=10, b=10, l=10, r=10), bargap=0.08,
                                 xaxis_title="anomaly score (lower = more anomalous)",
                                 yaxis_title="events", legend_title_text="is anomaly")
            st.plotly_chart(fig_ml, use_container_width=True)

    st.caption(f"Auto-refreshing every {cfg['dashboard']['refresh_seconds']}s • "
               f"Last loaded {time.strftime('%H:%M:%S')}")

    inject_scroll_reveal()


if __name__ == "__main__":
    main()
