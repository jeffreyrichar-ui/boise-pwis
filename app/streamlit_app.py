"""
PWIS Executive Dashboard
========================
Streamlit application for the Boise Public Works Intelligence System.

To run:
    cd boise-pwis
    streamlit run app/streamlit_app.py

Architecture:
  - Single-file app for portability
  - All heavy computation deferred to models/ modules
  - Folium maps embedded via st.components.v1.html
  - Session state for scenario parameter persistence

Non-technical stakeholder notes:
  - All weight sliders include plain-English descriptions of what each
    factor means in plain terms, not model terminology.
  - Policy presets let directors apply named strategies without adjusting
    individual sliders.
  - Score confidence warnings appear automatically when data quality is low.
  - KPI cards include target benchmarks so raw numbers have context.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import folium
from streamlit_folium import st_folium

from models.prioritization import PWISPrioritizationModel, DEFAULT_WEIGHTS
from models.scenario_engine import PWISScenarioEngine
from gis.map import (
    build_condition_map, build_priority_map,
    build_complaint_heatmap, build_executive_map,
)

# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PWIS — Boise Public Works Intelligence",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# ─── THEME COLORS ─────────────────────────────────────────────────────────────
COLORS = {
    "Critical": "#D62728",
    "High":     "#FF7F0E",
    "Medium":   "#BCBD22",
    "Low":      "#2CA02C",
    "primary":  "#1F77B4",
}

# ─── POLICY PRESETS ───────────────────────────────────────────────────────────
# Named weight configurations aligned to recognizable policy positions.
# Each preset includes a plain-English description and a use-case note
# so non-technical users understand what they are choosing.

POLICY_PRESETS = {
    "Balanced (Default)": {
        "weights": DEFAULT_WEIGHTS,
        "description": (
            "Standard PWIS baseline: condition drives most decisions, with traffic, "
            "complaints, cost, and equity as secondary factors. "
            "Recommended for routine annual capital planning."
        ),
    },
    "Condition-First (Engineering)": {
        "weights": {
            "condition_severity": 0.50,
            "traffic_impact":     0.20,
            "complaint_pressure": 0.10,
            "cost_efficiency":    0.12,
            "equity_modifier":    0.08,
        },
        "description": (
            "Maximizes weight on physical road condition. "
            "Use when the primary goal is reducing structural failures and "
            "meeting FHWA condition reporting requirements. "
            "Least sensitive to public complaint patterns."
        ),
    },
    "Complaint-Responsive (Community)": {
        "weights": {
            "condition_severity": 0.25,
            "traffic_impact":     0.20,
            "complaint_pressure": 0.35,
            "cost_efficiency":    0.12,
            "equity_modifier":    0.08,
        },
        "description": (
            "Elevates citizen complaint data in the priority score. "
            "Use when the goal is improving public-facing responsiveness and "
            "demonstrating that 311 feedback drives decisions. "
            "May prioritize high-visibility corridors over structurally worse but "
            "quieter roads."
        ),
    },
    "Budget-Efficient (Fiscal)": {
        "weights": {
            "condition_severity": 0.30,
            "traffic_impact":     0.25,
            "complaint_pressure": 0.10,
            "cost_efficiency":    0.28,
            "equity_modifier":    0.07,
        },
        "description": (
            "Maximizes the maintenance value per dollar spent. "
            "Use when operating under budget pressure and the goal is to treat "
            "the most lane-miles possible within available funding. "
            "May defer expensive rehabilitation in favor of lower-cost preservation."
        ),
    },
    "Equity-Focused (Title VI)": {
        "weights": {
            "condition_severity": 0.30,
            "traffic_impact":     0.20,
            "complaint_pressure": 0.15,
            "cost_efficiency":    0.10,
            "equity_modifier":    0.25,
        },
        "description": (
            "Strengthens the equity modifier to address historically under-maintained "
            "districts. Use when preparing for HUD/FHWA Title VI reviews or when "
            "the Director has identified equity as a strategic priority. "
            "Will shift more budget toward lower-income districts."
        ),
    },
    "Custom": {
        "weights": DEFAULT_WEIGHTS,
        "description": "Manually adjust each weight using the sliders below.",
    },
}

# ─── DATA LOADING (cached) ────────────────────────────────────────────────────
@st.cache_data
def load_data():
    roads       = pd.read_csv(DATA_DIR / "road_segments.csv")
    complaints  = pd.read_csv(DATA_DIR / "complaints.csv")
    work_orders = pd.read_csv(DATA_DIR / "work_orders.csv")
    budget      = pd.read_csv(DATA_DIR / "budget_actuals.csv")
    weather     = pd.read_csv(DATA_DIR / "weather_events.csv")
    bridges     = pd.read_csv(DATA_DIR / "bridge_inspections.csv")
    return roads, complaints, work_orders, budget, weather, bridges

@st.cache_data
def run_model(weights_tuple):
    weights = dict(zip(
        ["condition_severity", "traffic_impact", "complaint_pressure",
         "cost_efficiency", "equity_modifier"],
        weights_tuple
    ))
    roads, complaints, work_orders, _, _, _ = load_data()
    model = PWISPrioritizationModel(weights)
    return model.score(roads, complaints, work_orders)

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
def render_sidebar():
    st.sidebar.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Boise_Idaho_City_Seal.svg/200px-Boise_Idaho_City_Seal.svg.png",
        width=80
    )
    st.sidebar.title("🏗️ PWIS Controls")
    st.sidebar.caption("Boise Public Works Intelligence System")

    # ── Policy Preset Selector ──────────────────────────────────────────────
    st.sidebar.header("🎛️ Prioritization Policy")
    preset_name = st.sidebar.selectbox(
        "Select a policy preset",
        options=list(POLICY_PRESETS.keys()),
        index=0,
        help="Presets reflect different policy priorities. Switch between them to see how rankings shift.",
    )

    preset = POLICY_PRESETS[preset_name]
    st.sidebar.info(preset["description"])

    preset_weights = preset["weights"]

    # ── Weight Sliders (visible for Custom, collapsed for presets) ──────────
    show_sliders = (preset_name == "Custom") or st.sidebar.checkbox(
        "Manually override weights", value=False
    )

    if show_sliders:
        st.sidebar.markdown("**Adjust individual weights** (must sum to 1.0):")
        st.sidebar.caption(
            "Each weight controls how much that factor influences the priority score. "
            "Higher weight = that factor matters more in the ranking."
        )

        w1 = st.sidebar.slider(
            "Road Condition (physical state of pavement)",
            0.05, 0.60, float(preset_weights["condition_severity"]), 0.05,
            help="How heavily should the physical condition of the road drive priority? "
                 "Higher values prioritize the worst-condition roads regardless of traffic or complaints.",
        )
        w2 = st.sidebar.slider(
            "Traffic Volume (how many people use this road)",
            0.05, 0.50, float(preset_weights["traffic_impact"]), 0.05,
            help="How much should daily traffic count influence priority? "
                 "Higher values prioritize busy arterials and highways over quiet local streets.",
        )
        w3 = st.sidebar.slider(
            "Citizen Complaints (311 reports and severity)",
            0.05, 0.50, float(preset_weights["complaint_pressure"]), 0.05,
            help="How much should resident complaints influence the score? "
                 "Higher values prioritize roads where residents are actively reporting problems.",
        )
        w4 = st.sidebar.slider(
            "Cost Efficiency (maintenance value per dollar)",
            0.02, 0.30, float(preset_weights["cost_efficiency"]), 0.02,
            help="How much should we prioritize repairs that give the most lane-miles "
                 "of improvement per budget dollar? Higher values favor cost-effective preservation.",
        )
        w5 = st.sidebar.slider(
            "Equity (correcting historical underinvestment)",
            0.02, 0.20, float(preset_weights["equity_modifier"]), 0.02,
            help="A small boost for districts whose roads are below the citywide average. "
                 "This corrects for systematic underinvestment — it is documented and disclosed.",
        )

        total = w1 + w2 + w3 + w4 + w5
        if abs(total - 1.0) > 0.01:
            st.sidebar.warning(
                f"⚠️ Weights sum to {total:.2f} — must equal 1.0. "
                "Normalizing automatically."
            )
            norm = total
            w1, w2, w3, w4, w5 = w1/norm, w2/norm, w3/norm, w4/norm, w5/norm
        else:
            st.sidebar.success(f"✓ Weights sum to {total:.2f}")
    else:
        # Use preset values directly
        w1 = float(preset_weights["condition_severity"])
        w2 = float(preset_weights["traffic_impact"])
        w3 = float(preset_weights["complaint_pressure"])
        w4 = float(preset_weights["cost_efficiency"])
        w5 = float(preset_weights["equity_modifier"])

    # Display active weight summary for transparency
    with st.sidebar.expander("Active weights (for audit / reporting)", expanded=False):
        st.sidebar.write({
            "Road Condition":     f"{w1:.0%}",
            "Traffic Volume":     f"{w2:.0%}",
            "Citizen Complaints": f"{w3:.0%}",
            "Cost Efficiency":    f"{w4:.0%}",
            "Equity Modifier":    f"{w5:.0%}",
        })

    # ── Budget Control ───────────────────────────────────────────────────────
    st.sidebar.header("💰 Budget Scenario")
    budget = st.sidebar.number_input(
        "Annual Maintenance Budget ($)",
        min_value=500_000, max_value=30_000_000,
        value=8_000_000, step=500_000, format="%d",
        help="Total annual road maintenance budget. Adjust to see which segments "
             "get funded and what percentage of the network is covered.",
    )

    # ── Spatial Filters ──────────────────────────────────────────────────────
    st.sidebar.header("🗺️ Filters")
    roads, _, _, _, _, _ = load_data()
    districts = ["All"] + sorted(roads["district"].unique().tolist())
    selected_district = st.sidebar.selectbox(
        "District",
        districts,
        help="Filter to a specific district or view the full network.",
    )
    road_types = ["All"] + sorted(roads["road_type"].unique().tolist())
    selected_road_type = st.sidebar.selectbox(
        "Road Type",
        road_types,
        help="Filter by functional class: Arterial, Collector, Local, or Highway.",
    )

    return (w1, w2, w3, w4, w5), budget, selected_district, selected_road_type, preset_name


# ─── DATA QUALITY BANNER ─────────────────────────────────────────────────────
def render_confidence_banner(scores: pd.DataFrame):
    """
    Displays a warning if average score confidence is low.
    Low confidence signals that inspection data is stale or fields are missing —
    operators should re-inspect before making large capital commitments.
    """
    if "score_confidence" not in scores.columns:
        return

    avg_confidence = scores["score_confidence"].mean()
    low_conf_count = (scores["score_confidence"] < 0.7).sum()
    stale_count    = (scores["score_confidence"] < 0.8).sum()

    if avg_confidence < 0.70:
        st.error(
            f"⚠️ **Data Quality Alert:** {low_conf_count} segments ({low_conf_count/len(scores)*100:.0f}%) "
            f"have low score confidence (< 0.70). "
            "This typically indicates missing fields or inspection data older than 2 years. "
            "**Scores for these segments are indicative only.** "
            "Field re-inspection is recommended before committing capital."
        )
    elif avg_confidence < 0.85:
        st.warning(
            f"📋 **Data Quality Note:** {stale_count} segments ({stale_count/len(scores)*100:.0f}%) "
            f"have score confidence below 0.80 (average: {avg_confidence:.2f}). "
            "Some inspection data may be stale. Consider scheduling re-inspections "
            "for the highest-priority segments before finalizing the capital plan."
        )


# ─── KPI CARDS ────────────────────────────────────────────────────────────────
def render_kpi_cards(scores: pd.DataFrame, budget: float):
    """
    Key Performance Indicators with benchmark context.

    Each metric includes a target or reference value so operators understand
    whether the number is good, acceptable, or requires action — without
    needing to know the model internals.
    """
    tier_counts = scores["priority_tier"].value_counts()

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric(
            "Total Segments",
            len(scores),
            help="Total road segments in the current analysis.",
        )

    with col2:
        avg_ci = scores["condition_index"].mean()
        delta_vs_target = avg_ci - 65  # Target: citywide average CI >= 65 (APWA benchmark)
        st.metric(
            "Avg Condition Index",
            f"{avg_ci:.0f} / 100",
            delta=f"{delta_vs_target:+.0f} vs. target (65)",
            delta_color="normal",
            help=(
                "Average road condition across the network. "
                "Target: 65+ (APWA benchmark for well-maintained mid-size cities). "
                "Below 60 indicates a network entering reactive maintenance mode."
            ),
        )

    with col3:
        critical = tier_counts.get("Critical", 0) + tier_counts.get("High", 0)
        critical_pct = critical / len(scores) * 100
        # Benchmark: High/Critical should be < 15% of the network (PWIS-ENG)
        st.metric(
            "High/Critical Segments",
            f"{critical} ({critical_pct:.0f}%)",
            delta=f"{'⚠️ Above' if critical_pct > 15 else '✓ Within'} 15% benchmark",
            delta_color="inverse" if critical_pct > 15 else "off",
            help=(
                "Count and share of segments in High or Critical priority tiers. "
                "Benchmark: < 15% of network (typical well-funded city). "
                "Above 15% signals deferred maintenance backlog."
            ),
        )

    with col4:
        poor = (scores["condition_index"] < 40).sum()
        poor_miles = scores[scores["condition_index"] < 40]["length_miles"].sum()
        st.metric(
            "Structurally Poor (<40 CI)",
            f"{poor} segs",
            delta=f"{poor_miles:.1f} lane-miles",
            delta_color="inverse",
            help=(
                "Segments below CI=40 are at or past the structural failure threshold "
                "(PASER standard). These require rehabilitation, not just surface treatment. "
                "Each year of deferral increases repair cost 3-5x."
            ),
        )

    with col5:
        total_backlog = scores[
            scores["priority_tier"].astype(str).isin(["Critical", "High"])
        ]["estimated_repair_cost_usd"].sum()
        st.metric(
            "High-Priority Backlog",
            f"${total_backlog/1e6:.1f}M",
            help=(
                "Estimated cost of all Critical + High priority segments. "
                "This is the minimum investment required to address structural failures "
                "and prevent further network deterioration. Source: APWA 2023 unit costs."
            ),
        )

    with col6:
        roads, complaints, work_orders, _, _, _ = load_data()
        engine = PWISScenarioEngine(roads, complaints, work_orders)
        _, s1 = engine.run_budget_scenario(budget)
        funded_pct = s1.summary_metrics["pct_budget_used"]
        segments_funded = s1.summary_metrics["segments_funded"]
        st.metric(
            "Budget Utilization",
            f"{funded_pct:.0f}%",
            delta=f"{segments_funded} of {len(scores)} segments funded",
            help=(
                "Percentage of the annual budget committed to funded segments. "
                "< 90% may indicate the available budget cannot address all priority segments. "
                "= 100% means the budget is the binding constraint, not crew capacity."
            ),
        )


# ─── TAB: OVERVIEW ────────────────────────────────────────────────────────────
def render_overview(scores: pd.DataFrame, budget_df: pd.DataFrame):
    st.header("📊 Network Overview")

    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.subheader("Condition Distribution by District")
        st.caption(
            "Each box shows the range of condition scores in that district. "
            "The red dashed line (CI=40) marks the structural failure threshold — "
            "segments below this line need rehabilitation, not just surface treatment."
        )
        fig = px.box(
            scores, x="district", y="condition_index",
            color="road_type",
            color_discrete_sequence=px.colors.qualitative.Set2,
            labels={"condition_index": "Condition Index (0-100, higher=better)", "district": "District"},
        )
        fig.update_layout(
            height=400, legend_title="Road Type",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        fig.add_hline(
            y=40, line_dash="dash", line_color="red",
            annotation_text="Structural failure threshold (CI=40)",
            annotation_position="top right",
        )
        fig.add_hline(
            y=65, line_dash="dot", line_color="green",
            annotation_text="Network health target (CI=65)",
            annotation_position="bottom right",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Priority Tier Distribution")
        st.caption(
            "Critical and High segments require action in the current or next budget cycle. "
            "Medium segments can be addressed through preventive maintenance. "
            "Low segments need only routine monitoring."
        )
        tier_data = scores["priority_tier"].value_counts().reset_index()
        tier_data.columns = ["Tier", "Count"]
        tier_order = ["Critical", "High", "Medium", "Low"]
        tier_data["Tier"] = pd.Categorical(tier_data["Tier"], categories=tier_order, ordered=True)
        tier_data = tier_data.sort_values("Tier")

        fig2 = px.bar(
            tier_data, x="Tier", y="Count",
            color="Tier",
            color_discrete_map=COLORS,
            text="Count",
        )
        fig2.update_traces(textposition="outside")
        fig2.update_layout(
            height=400, showlegend=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # District health matrix
    st.subheader("District Infrastructure Health Matrix")
    st.caption(
        "Red = below the structural failure threshold (CI < 40). "
        "Orange = at risk (CI 40-65). Green = meets or exceeds the network health target (CI >= 65)."
    )
    district_summary = (
        scores.groupby("district")
        .agg(
            avg_condition=("condition_index",  "mean"),
            avg_priority=("priority_score",    "mean"),
            poor_count=("condition_index",     lambda x: (x < 40).sum()),
            total_segments=("segment_id",      "count"),
            total_lane_miles=("length_miles",  "sum"),
            total_backlog=("estimated_repair_cost_usd", "sum"),
            avg_confidence=("score_confidence", "mean"),
        )
        .round(2)
        .reset_index()
    )
    district_summary["pct_poor"]  = (
        district_summary["poor_count"] / district_summary["total_segments"] * 100
    ).round(1)
    district_summary["backlog_M"] = (district_summary["total_backlog"] / 1e6).round(2)

    def color_condition(val):
        if val < 40:   return "color: red; font-weight: bold"
        elif val < 65: return "color: orange"
        else:          return "color: green"

    def color_confidence(val):
        if val < 0.70:  return "color: red"
        elif val < 0.85: return "color: orange"
        else:            return "color: green"

    display = district_summary[[
        "district", "avg_condition", "avg_priority", "pct_poor",
        "total_lane_miles", "backlog_M", "avg_confidence",
    ]].copy()
    display.columns = [
        "District", "Avg CI", "Avg Priority Score", "% Structurally Poor",
        "Lane Miles", "Backlog ($M)", "Data Confidence",
    ]

    st.dataframe(
        display.style
        .format({
            "Avg CI":              "{:.1f}",
            "Avg Priority Score":  "{:.1f}",
            "% Structurally Poor": "{:.1f}%",
            "Lane Miles":          "{:.1f}",
            "Backlog ($M)":        "${:.2f}M",
            "Data Confidence":     "{:.2f}",
        })
        .applymap(color_condition,  subset=["Avg CI"])
        .applymap(color_confidence, subset=["Data Confidence"]),
        use_container_width=True, hide_index=True,
    )
    st.caption(
        "Data Confidence: 1.0 = all required fields present and inspected within 2 years. "
        "Below 0.70 = scores are indicative only; field re-inspection recommended."
    )


# ─── TAB: PRIORITIZATION TABLE ───────────────────────────────────────────────
def render_priority_table(scores: pd.DataFrame, district_filter: str, type_filter: str):
    st.header("🎯 Prioritized Segments")

    filtered = scores.copy()
    if district_filter != "All":
        filtered = filtered[filtered["district"] == district_filter]
    if type_filter != "All":
        filtered = filtered[filtered["road_type"] == type_filter]

    col1, col2 = st.columns([2, 1])
    with col1:
        tier_filter = st.multiselect(
            "Filter by Tier",
            options=["Critical", "High", "Medium", "Low"],
            default=["Critical", "High"],
            help="Critical = immediate action required. High = address this budget cycle. "
                 "Medium = preventive treatment window open. Low = routine monitoring only.",
        )
    with col2:
        top_n = st.slider(
            "Show top N segments", 10, len(filtered), min(50, len(filtered))
        )

    if tier_filter:
        filtered = filtered[filtered["priority_tier"].astype(str).isin(tier_filter)]

    # Low confidence rows get a visual flag
    if "score_confidence" in filtered.columns:
        low_conf_count = (filtered["score_confidence"] < 0.7).sum()
        if low_conf_count > 0:
            st.warning(
                f"⚠️ {low_conf_count} segment(s) in this view have data confidence < 0.70. "
                "Check the 'Data Confidence' column — these scores are based on stale or "
                "incomplete inspection data."
            )

    display_cols = [
        "segment_id", "street_name", "district", "road_type",
        "condition_index", "daily_traffic_aadt", "priority_score",
        "priority_tier", "district_rank", "score_confidence",
        "raw_complaint_count", "recommended_action", "estimated_repair_cost_usd",
    ]
    display_cols = [c for c in display_cols if c in filtered.columns]
    display = filtered[display_cols].head(top_n).copy()

    display["estimated_repair_cost_usd"] = display["estimated_repair_cost_usd"].apply(
        lambda x: f"${int(x):,}" if pd.notna(x) else "-"
    )
    display["daily_traffic_aadt"] = display["daily_traffic_aadt"].apply(
        lambda x: f"{int(x):,}" if pd.notna(x) else "-"
    )

    def color_tier(val):
        colors_map = {
            "Critical": "background-color:#ffcccc",
            "High":     "background-color:#ffe5cc",
            "Medium":   "background-color:#fffacc",
            "Low":      "background-color:#ccffcc",
        }
        return colors_map.get(str(val), "")

    def color_confidence(val):
        try:
            v = float(val)
            if v < 0.70:   return "color: red; font-weight: bold"
            elif v < 0.85: return "color: orange"
            return ""
        except (ValueError, TypeError):
            return ""

    style = display.style.applymap(color_tier, subset=["priority_tier"])
    if "score_confidence" in display.columns:
        style = style.applymap(color_confidence, subset=["score_confidence"])

    st.dataframe(style, use_container_width=True, hide_index=True)
    st.caption(
        f"Showing {len(display)} of {len(filtered)} filtered segments  |  "
        "Confidence: 0.70+ = reliable  |  < 0.70 = re-inspect before committing capital"
    )

    # Score component breakdown
    if len(filtered) > 0:
        st.subheader("Score Component Breakdown — Top 20")
        st.caption(
            "Stacked bars show which factors are driving each segment's priority score. "
            "A segment dominated by 'Condition' has poor pavement — objective and hard to dispute. "
            "A segment dominated by 'Complaints' has high citizen pressure — may reflect equity or visibility."
        )
        top20 = filtered.head(20)
        component_cols = [
            c for c in [
                "score_condition", "score_traffic", "score_complaints",
                "score_cost_eff", "score_equity",
            ]
            if c in top20.columns
        ]
        component_labels = {
            "score_condition":  "Road Condition",
            "score_traffic":    "Traffic Volume",
            "score_complaints": "Citizen Complaints",
            "score_cost_eff":   "Cost Efficiency",
            "score_equity":     "Equity Modifier",
        }
        if component_cols:
            melt = top20[["street_name"] + component_cols].melt(
                id_vars="street_name", var_name="Component", value_name="Score"
            )
            melt["Component"] = melt["Component"].map(component_labels).fillna(melt["Component"])
            fig = px.bar(
                melt, x="Score", y="street_name", color="Component",
                orientation="h", barmode="stack",
                color_discrete_sequence=px.colors.qualitative.Set1,
                labels={"street_name": "Segment", "Score": "Component Score (0-100)"},
            )
            fig.update_layout(
                height=520,
                yaxis={"categoryorder": "total ascending"},
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)


# ─── TAB: GIS MAP ────────────────────────────────────────────────────────────
def render_map_tab(scores: pd.DataFrame, roads: pd.DataFrame, complaints: pd.DataFrame):
    st.header("🗺️ GIS Infrastructure Map")
    st.caption(
        "Interactive map of the Boise road network. "
        "Click any segment marker for detailed condition and priority information. "
        "Use the map type selector to switch between views."
    )
    map_type = st.radio(
        "Select Map View",
        ["Priority Scores", "Condition Index", "Complaint Heatmap"],
        horizontal=True,
        help=(
            "Priority Scores: overall model output. "
            "Condition Index: raw physical condition only. "
            "Complaint Heatmap: density of 311 complaints by location."
        ),
    )

    if "lat" not in scores.columns:
        scores = scores.merge(roads[["segment_id", "lat", "lon"]], on="segment_id", how="left")

    with st.spinner("Rendering map..."):
        if map_type == "Priority Scores":
            m = build_priority_map(scores)
        elif map_type == "Condition Index":
            m = build_condition_map(roads)
        else:
            m = build_complaint_heatmap(complaints)

    st_folium(m, width=None, height=550, returned_objects=[])


# ─── TAB: SCENARIO SIMULATION ────────────────────────────────────────────────
def render_scenarios(scores: pd.DataFrame, budget: float, weights_tuple: tuple):
    st.header("⚙️ Scenario Simulation")
    st.caption(
        "Scenario analysis answers 'what if' questions about budget, policy weights, "
        "and the cost of deferring maintenance. All cost figures are APWA 2023 benchmarks "
        "adjusted for Boise metro (±25%). Confirm against bid history before presenting to Council."
    )

    roads, complaints, work_orders, _, _, _ = load_data()
    engine = PWISScenarioEngine(roads, complaints, work_orders)

    tab_a, tab_b, tab_c = st.tabs([
        "💰 Budget Coverage", "⚖️ Weight Sensitivity", "📈 Deferral Cost"
    ])

    with tab_a:
        st.subheader("What does each budget level actually buy?")
        st.caption(
            "Each bar shows how many segments would be funded at that annual budget level. "
            "The chart also shows diminishing returns: the last million dollars buys fewer "
            "lane-miles than the first million because the highest-priority segments are "
            "addressed first."
        )
        coverage = engine.run_coverage_analysis(
            budget_levels=[2e6, 4e6, 6e6, 8e6, 10e6, 12e6, 15e6, 20e6]
        )

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                coverage, x="budget_millions", y="segments_funded",
                labels={"budget_millions": "Annual Budget ($M)", "segments_funded": "Segments Funded"},
                color="segments_funded", color_continuous_scale="Blues",
                text="segments_funded",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                title="Segments Funded by Budget Level",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig2 = px.line(
                coverage, x="budget_millions", y="lane_miles_treated",
                markers=True,
                labels={
                    "budget_millions":    "Annual Budget ($M)",
                    "lane_miles_treated": "Lane Miles Treated",
                },
            )
            fig2.update_layout(
                title="Lane Miles Treated vs. Budget",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig2, use_container_width=True)

        display_cols = [
            "budget_millions", "segments_funded", "critical_funded", "critical_unfunded",
            "lane_miles_treated", "marginal_lane_miles", "pct_budget_used", "budget_per_lane_mile",
        ]
        display_cols = [c for c in display_cols if c in coverage.columns]
        st.dataframe(
            coverage[display_cols].style.format({
                "budget_millions":       "${:.1f}M",
                "lane_miles_treated":    "{:.1f}",
                "marginal_lane_miles":   "{:.1f}",
                "pct_budget_used":       "{:.1f}%",
                "budget_per_lane_mile":  "${:,.0f}",
            }),
            use_container_width=True, hide_index=True,
        )
        st.caption(
            "'Marginal Lane Miles' = additional lane-miles gained by each budget increment. "
            "Declining marginal returns indicate the high-priority backlog is being addressed."
        )

    with tab_b:
        st.subheader("How sensitive are the rankings to policy weight choices?")
        st.caption(
            "This analysis re-runs the model with your current weight configuration and "
            "compares rankings to the Balanced (Default) baseline. "
            "High top-10 stability (> 80%) means the most critical segments are consistently "
            "identified regardless of weight assumptions — a strong result for Council defensibility."
        )

        current_weights = dict(zip(
            ["condition_severity", "traffic_impact", "complaint_pressure",
             "cost_efficiency", "equity_modifier"],
            weights_tuple,
        ))

        try:
            comparison_df, stats = engine.run_weight_scenario(current_weights, "Your Config")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric(
                "Top-10 Stability",
                f"{stats['top10_stability'] * 100:.0f}%",
                help=(
                    "Percentage of baseline top-10 segments that remain in the top 10 "
                    "under your weight configuration. "
                    "80%+ = rankings are robust to weight assumptions."
                ),
            )
            col2.metric(
                "Avg Rank Shift",
                stats["avg_rank_shift"],
                help="Average number of positions each segment moves relative to the baseline.",
            )
            col3.metric(
                "Tier Changes",
                stats["tier_changes"],
                help="Segments that moved to a different priority tier (e.g., Medium to High).",
            )
            col4.metric(
                "Rose to High/Critical",
                stats.get("segments_rose_to_high_critical", 0),
                help="Segments that moved UP from Low/Medium to High/Critical with your weights.",
            )

            st.subheader("Biggest Rank Movers")
            st.caption(
                "Segments with the largest rank shifts indicate where your weight choices "
                "most diverge from the baseline. Investigate these segments — if they are "
                "moving up due to complaints but have high condition scores, that is worth discussing."
            )
            top_movers = comparison_df.nlargest(15, "rank_shift")[
                ["segment_id", "street_name", "district", "base_score",
                 "priority_score", "base_rank", "alt_rank", "rank_shift", "tier_changed"]
            ].copy()
            top_movers.columns = [
                "ID", "Street", "District", "Baseline Score",
                "New Score", "Baseline Rank", "New Rank", "Rank Shift", "Tier Changed",
            ]
            st.dataframe(top_movers, use_container_width=True, hide_index=True)

        except ValueError as e:
            st.error(f"Cannot run weight sensitivity: {e}")

    with tab_c:
        st.subheader("What does it cost to defer maintenance on the highest-priority segments?")
        st.caption(
            "Each year of deferral increases repair costs — not because prices rise, but because "
            "deterioration accelerates and surface treatment becomes rehabilitation becomes emergency repair. "
            "This analysis covers High and Critical segments only (the strongest case for immediate action)."
        )

        deferral_years = st.slider(
            "Deferral horizon (years)", 1, 10, 5,
            help="How many years to model deferral. Longer horizons show greater cost compounding.",
        )

        deferral_df = engine.run_deferral_scenario(years=deferral_years)

        if len(deferral_df) > 0:
            today  = deferral_df[deferral_df["year_deferred"] == 0]
            future = deferral_df[deferral_df["year_deferred"] == deferral_years]

            col1, col2, col3, col4 = st.columns(4)
            total_today    = today["current_cost"].sum()
            total_deferred = future["projected_cost"].sum()
            premium_pct    = (total_deferred / max(total_today, 1) - 1) * 100
            total_low      = future["low_bound_projected"].sum() if "low_bound_projected" in future.columns else total_deferred
            total_high     = future["high_bound_projected"].sum() if "high_bound_projected" in future.columns else total_deferred

            col1.metric(
                "Estimated Cost Today",
                f"${total_today:,.0f}",
                help="Sum of current estimated repair costs for all High/Critical segments.",
            )
            col2.metric(
                f"Projected Cost at Year {deferral_years}",
                f"${total_deferred:,.0f}",
                help=f"Projected cost if all High/Critical repairs are deferred {deferral_years} years.",
            )
            col3.metric(
                "Deferral Premium",
                f"+{premium_pct:.0f}%",
                delta_color="inverse",
                help="Percentage cost increase from deferral. Source: APWA 2023 lifecycle cost curves.",
            )
            col4.metric(
                "Uncertainty Range",
                f"${total_low:,.0f} – ${total_high:,.0f}",
                help=(
                    "Low and high bounds based on published APWA deferral cost multiplier ranges. "
                    "Central estimate uses midpoint values."
                ),
            )

            st.info(
                f"**Interpretation:** Deferring maintenance on the {today['segment_id'].nunique()} "
                f"High/Critical segments for {deferral_years} years is estimated to cost "
                f"${total_deferred - total_today:,.0f} MORE than acting now — "
                f"a {premium_pct:.0f}% cost premium. "
                "This is the core financial argument for proactive infrastructure investment."
            )

            # Cost trajectory chart
            trajectory = deferral_df.groupby("projected_year").agg(
                total_cost=("projected_cost", "sum"),
                low_cost=("low_bound_projected", "sum") if "low_bound_projected" in deferral_df.columns else ("projected_cost", "sum"),
                high_cost=("high_bound_projected", "sum") if "high_bound_projected" in deferral_df.columns else ("projected_cost", "sum"),
            ).reset_index()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trajectory["projected_year"], y=trajectory["high_cost"],
                fill=None, mode="lines", line_color="rgba(214, 39, 40, 0.2)",
                name="Upper bound",
            ))
            fig.add_trace(go.Scatter(
                x=trajectory["projected_year"], y=trajectory["low_cost"],
                fill="tonexty", mode="lines",
                fillcolor="rgba(214, 39, 40, 0.1)",
                line_color="rgba(214, 39, 40, 0.2)",
                name="Lower bound",
            ))
            fig.add_trace(go.Scatter(
                x=trajectory["projected_year"], y=trajectory["total_cost"],
                mode="lines+markers", line_color="#D62728",
                name="Central estimate",
            ))
            fig.update_layout(
                title="Projected Repair Cost if Maintenance is Deferred (High/Critical Segments Only)",
                xaxis_title="Year",
                yaxis_title="Estimated Repair Cost ($)",
                yaxis_tickformat="$,.0f",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                height=380,
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Shaded band = uncertainty range based on APWA published deferral cost multiplier intervals. "
                "Central line = midpoint estimate. Source: APWA 2023, FHWA Pavement Preservation Compendium Vol. II."
            )
        else:
            st.info("No High/Critical segments found for deferral analysis.")


# ─── MAIN APP ─────────────────────────────────────────────────────────────────
def main():
    weights_tuple, budget, district_filter, type_filter, preset_name = render_sidebar()

    st.title("🏗️ Boise Public Works Intelligence System")
    st.caption(
        "Director of Analytics & Strategy | City of Boise | "
        "Infrastructure Investment Prioritization Platform"
    )

    # Active policy label
    if preset_name != "Custom":
        st.info(
            f"**Active policy preset: {preset_name}** — "
            f"{POLICY_PRESETS[preset_name]['description'][:120]}..."
        )

    # Normalize weights
    total = sum(weights_tuple)
    if total > 0:
        weights_tuple = tuple(w / total for w in weights_tuple)

    # Load data
    roads, complaints, work_orders, budget_df, weather, bridges = load_data()

    # Run model
    with st.spinner("Running prioritization model..."):
        scores = run_model(weights_tuple)

    # Merge lat/lon if needed
    if "lat" not in scores.columns:
        scores = scores.merge(roads[["segment_id", "lat", "lon"]], on="segment_id", how="left")

    # Data quality banner (appears before KPIs if confidence is low)
    render_confidence_banner(scores)

    # KPIs
    st.subheader("Key Performance Indicators")
    render_kpi_cards(scores, budget)

    st.divider()

    # Main tabs
    tab_overview, tab_priority, tab_map, tab_scenario, tab_raw = st.tabs([
        "📊 Overview", "🎯 Priority Table", "🗺️ GIS Map",
        "⚙️ Scenarios", "📂 Raw Data",
    ])

    with tab_overview:
        render_overview(scores, budget_df)

    with tab_priority:
        render_priority_table(scores, district_filter, type_filter)

    with tab_map:
        render_map_tab(scores, roads, complaints)

    with tab_scenario:
        render_scenarios(scores, budget, weights_tuple)

    with tab_raw:
        st.header("📂 Raw Data Explorer")
        st.caption("Direct access to all underlying datasets for audit and verification.")
        dataset = st.selectbox("Dataset", [
            "Road Segments", "Work Orders", "Complaints",
            "Budget Actuals", "Weather Events", "Bridges", "Priority Scores",
        ])
        data_map = {
            "Road Segments":   roads,
            "Work Orders":     work_orders,
            "Complaints":      complaints,
            "Budget Actuals":  budget_df,
            "Weather Events":  weather,
            "Bridges":         bridges,
            "Priority Scores": scores,
        }
        df_show = data_map[dataset]
        st.dataframe(df_show, use_container_width=True, hide_index=True)
        st.caption(f"{len(df_show):,} records  |  {len(df_show.columns)} columns")

    # Footer
    st.divider()
    st.caption(
        "PWIS v1.0 | City of Boise Public Works | "
        "Data: Synthetic (production-ready schema) | "
        "Model: PWIS Weighted Prioritization v1.0 | "
        "Cost benchmarks: APWA 2023 (Boise metro adjusted) | "
        "All scores are advisory — final decisions remain with the Director."
    )


if __name__ == "__main__":
    main()
