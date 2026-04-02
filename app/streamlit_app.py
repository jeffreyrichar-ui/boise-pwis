"""
PWIS Utility Executive Dashboard
==================================
Streamlit application for the Boise water/sewer/stormwater intelligence system.

To run:
    cd boise-pwis
    streamlit run app/streamlit_app.py

Architecture:
  - Single-file app for portability
  - All heavy computation deferred to models/ modules
  - Folium maps embedded via st.components.v1.html
  - Session state for scenario parameter persistence
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
    build_service_request_heatmap, build_executive_map,
)

# ─── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PWIS — Boise Utility Intelligence",
    page_icon="🔧",
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
    "Water":    "#1F77B4",
    "Sewer":    "#8C564B",
    "Stormwater": "#17BECF",
}

# ─── POLICY PRESETS ───────────────────────────────────────────────────────────
POLICY_PRESETS = {
    "Balanced (Default)": {
        "weights": DEFAULT_WEIGHTS,
        "description": (
            "Standard PWIS baseline: condition drives most decisions, with break "
            "history, capacity stress, criticality, material risk, and age as "
            "secondary factors. Recommended for routine CIP planning."
        ),
    },
    "Condition-First (Engineering)": {
        "weights": {
            "condition_severity": 0.45,
            "break_history":      0.15,
            "capacity_stress":    0.12,
            "criticality":        0.12,
            "material_risk":      0.10,
            "age_factor":         0.06,
        },
        "description": (
            "Maximizes weight on physical pipe condition from CCTV/acoustic inspection. "
            "Use when the primary goal is reducing structural failures and meeting "
            "EPA/DEQ compliance requirements."
        ),
    },
    "Break-History-Responsive (Reactive)": {
        "weights": {
            "condition_severity": 0.20,
            "break_history":      0.35,
            "capacity_stress":    0.15,
            "criticality":        0.15,
            "material_risk":      0.10,
            "age_factor":         0.05,
        },
        "description": (
            "Prioritizes pipes with recent break history. Use when the goal is "
            "reducing emergency repair costs and repeat failures. May prioritize "
            "older pipes with documented breaks over newer pipes in poor condition."
        ),
    },
    "Capacity-Focused (Hydraulic)": {
        "weights": {
            "condition_severity": 0.20,
            "break_history":      0.15,
            "capacity_stress":    0.30,
            "criticality":        0.15,
            "material_risk":      0.10,
            "age_factor":         0.10,
        },
        "description": (
            "Emphasizes hydraulic capacity for wet-weather resilience. "
            "Use when SSO reduction, stormwater flooding, or fire flow "
            "adequacy is the strategic priority."
        ),
    },
    "Custom": {
        "weights": DEFAULT_WEIGHTS,
        "description": "Manually adjust each weight using the sliders below.",
    },
}

# ─── KPI BENCHMARKS ──────────────────────────────────────────────────────────
KPI_BENCHMARKS = {
    "avg_condition": {"target": 60, "unit": "/100", "label": "Avg Pipe Condition"},
    "critical_pct":  {"target": 5,  "unit": "%",    "label": "Critical Pipes"},
    "avg_age":       {"target": 40, "unit": "yr",   "label": "Avg Asset Age"},
    "break_rate":    {"target": 1.0,"unit": "/yr",  "label": "Avg Breaks (5yr)"},
}


# ─── DATA LOADING ────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    pipes            = pd.read_csv(DATA_DIR / "pipe_segments.csv")
    service_requests = pd.read_csv(DATA_DIR / "service_requests.csv")
    work_orders      = pd.read_csv(DATA_DIR / "work_orders.csv")
    facilities       = pd.read_csv(DATA_DIR / "facilities.csv")
    flow_monitoring  = pd.read_csv(DATA_DIR / "flow_monitoring.csv")
    budget_cip       = pd.read_csv(DATA_DIR / "budget_cip.csv")
    weather          = pd.read_csv(DATA_DIR / "weather_events.csv")
    return pipes, service_requests, work_orders, facilities, flow_monitoring, budget_cip, weather

@st.cache_data
def run_model(weights_tuple):
    weights = dict(zip(
        ["condition_severity", "break_history", "capacity_stress",
         "criticality", "material_risk", "age_factor"],
        weights_tuple
    ))
    pipes, service_requests, work_orders, _, _, _, _ = load_data()
    model = PWISPrioritizationModel(weights)
    return model.score(pipes, service_requests, work_orders)


# ─── CONFIDENCE BANNER ───────────────────────────────────────────────────────
def render_confidence_banner(scores: pd.DataFrame):
    low_conf = (scores["score_confidence"] < 0.7).sum()
    total = len(scores)
    pct = low_conf / total * 100

    if pct > 20:
        st.warning(
            f"**Data Quality Alert:** {low_conf} of {total} pipes ({pct:.0f}%) have "
            f"score confidence below 70%. Scores for these pipes are based on "
            f"incomplete or stale inspection data. Re-inspection recommended "
            f"before committing capital to these segments."
        )
    elif pct > 5:
        st.info(
            f"{low_conf} pipes ({pct:.0f}%) have reduced confidence scores. "
            f"Check the 'Confidence' column in the priority table for details."
        )


# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
def render_sidebar():
    st.sidebar.title("🔧 PWIS Controls")
    st.sidebar.caption("Boise Utility Infrastructure Intelligence")

    # System filter
    st.sidebar.header("System Filter")
    system_filter = st.sidebar.multiselect(
        "Show system types",
        options=["Water", "Sewer", "Stormwater"],
        default=["Water", "Sewer", "Stormwater"],
    )

    # Policy preset
    st.sidebar.header("Prioritization Policy")
    preset_name = st.sidebar.selectbox(
        "Select a policy preset",
        options=list(POLICY_PRESETS.keys()),
        index=0,
    )

    preset = POLICY_PRESETS[preset_name]
    st.sidebar.info(preset["description"])
    preset_weights = preset["weights"]

    show_sliders = (preset_name == "Custom") or st.sidebar.checkbox(
        "Manually override weights", value=False
    )

    if show_sliders:
        st.sidebar.markdown("**Adjust individual weights** (must sum to 1.0):")
        w_condition   = st.sidebar.slider("Condition Severity", 0.0, 1.0, preset_weights["condition_severity"], 0.01)
        w_breaks      = st.sidebar.slider("Break History",      0.0, 1.0, preset_weights["break_history"],      0.01)
        w_capacity    = st.sidebar.slider("Capacity Stress",    0.0, 1.0, preset_weights["capacity_stress"],    0.01)
        w_criticality = st.sidebar.slider("Criticality",        0.0, 1.0, preset_weights["criticality"],        0.01)
        w_material    = st.sidebar.slider("Material Risk",      0.0, 1.0, preset_weights["material_risk"],      0.01)
        w_age         = st.sidebar.slider("Age Factor",         0.0, 1.0, preset_weights["age_factor"],         0.01)

        total = w_condition + w_breaks + w_capacity + w_criticality + w_material + w_age
        if abs(total - 1.0) > 0.02:
            st.sidebar.error(f"Weights sum to {total:.2f} — must equal 1.0")

        weights_tuple = (w_condition, w_breaks, w_capacity, w_criticality, w_material, w_age)
    else:
        weights_tuple = tuple(preset_weights.values())

    return weights_tuple, system_filter


# ─── TAB 1: KPI OVERVIEW ────────────────────────────────────────────────────
def render_kpi_tab(scores: pd.DataFrame, pipes: pd.DataFrame):
    st.header("Utility Infrastructure KPIs")
    render_confidence_banner(scores)

    col1, col2, col3, col4 = st.columns(4)

    avg_cond = scores["condition_score"].mean()
    critical_pct = (scores["priority_tier"].astype(str) == "Critical").mean() * 100
    avg_age = scores["asset_age_years"].mean()
    avg_breaks = scores["breaks_last_5yr"].mean()

    with col1:
        delta = avg_cond - KPI_BENCHMARKS["avg_condition"]["target"]
        st.metric("Avg Pipe Condition", f"{avg_cond:.0f}/100",
                  delta=f"{delta:+.0f} vs target {KPI_BENCHMARKS['avg_condition']['target']}")
    with col2:
        delta = critical_pct - KPI_BENCHMARKS["critical_pct"]["target"]
        st.metric("Critical Pipes", f"{critical_pct:.1f}%",
                  delta=f"{delta:+.1f}% vs target {KPI_BENCHMARKS['critical_pct']['target']}%",
                  delta_color="inverse")
    with col3:
        delta = avg_age - KPI_BENCHMARKS["avg_age"]["target"]
        st.metric("Avg Asset Age", f"{avg_age:.0f} yr",
                  delta=f"{delta:+.0f} yr vs target {KPI_BENCHMARKS['avg_age']['target']}yr",
                  delta_color="inverse")
    with col4:
        st.metric("Avg Breaks (5yr)", f"{avg_breaks:.1f}",
                  delta=f"{avg_breaks - KPI_BENCHMARKS['break_rate']['target']:+.1f} vs target",
                  delta_color="inverse")

    st.divider()

    # System type breakdown
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Priority Tier Distribution")
        tier_counts = scores["priority_tier"].value_counts().reindex(
            ["Critical", "High", "Medium", "Low"]
        ).fillna(0)
        fig = px.bar(
            x=tier_counts.index, y=tier_counts.values,
            color=tier_counts.index,
            color_discrete_map=COLORS,
            labels={"x": "Priority Tier", "y": "Pipe Count"},
        )
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("System Type Breakdown")
        sys_counts = scores["system_type"].value_counts()
        fig = px.pie(
            values=sys_counts.values, names=sys_counts.index,
            color=sys_counts.index,
            color_discrete_map=COLORS,
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    # District summary
    st.subheader("District Summary")
    district_summary = (
        scores.groupby("district")
        .agg(
            pipes=("segment_id", "count"),
            avg_condition=("condition_score", "mean"),
            critical=("priority_tier", lambda x: (x.astype(str) == "Critical").sum()),
            avg_priority=("priority_score", "mean"),
            total_replacement_cost=("estimated_replacement_cost_usd", "sum"),
        )
        .round(1)
        .sort_values("avg_priority", ascending=False)
    )
    district_summary["total_replacement_cost"] = district_summary["total_replacement_cost"].apply(
        lambda x: f"${x:,.0f}"
    )
    st.dataframe(district_summary, use_container_width=True)


# ─── TAB 2: PRIORITY TABLE ──────────────────────────────────────────────────
def render_priority_tab(scores: pd.DataFrame):
    st.header("Pipe Priority Rankings")

    col1, col2, col3 = st.columns(3)
    with col1:
        tier_filter = st.multiselect("Filter by tier", ["Critical", "High", "Medium", "Low"],
                                     default=["Critical", "High"])
    with col2:
        district_filter = st.multiselect("Filter by district", scores["district"].unique().tolist())
    with col3:
        material_filter = st.multiselect("Filter by material", scores["pipe_material"].unique().tolist())

    filtered = scores.copy()
    if tier_filter:
        filtered = filtered[filtered["priority_tier"].astype(str).isin(tier_filter)]
    if district_filter:
        filtered = filtered[filtered["district"].isin(district_filter)]
    if material_filter:
        filtered = filtered[filtered["pipe_material"].isin(material_filter)]

    display_cols = [
        "segment_id", "system_type", "corridor_name", "district",
        "pipe_material", "diameter_inches", "condition_score",
        "breaks_last_5yr", "priority_score", "priority_tier",
        "score_confidence", "recommended_action",
    ]
    display_cols = [c for c in display_cols if c in filtered.columns]

    st.dataframe(
        filtered[display_cols].head(100),
        use_container_width=True,
        height=500,
    )
    st.caption(f"Showing {min(100, len(filtered))} of {len(filtered)} filtered pipes")


# ─── TAB 3: GIS MAP ─────────────────────────────────────────────────────────
def render_map_tab(scores: pd.DataFrame, pipes: pd.DataFrame, service_requests: pd.DataFrame):
    st.header("Infrastructure Map")

    map_type = st.radio(
        "Select map view",
        ["Executive (Multi-Layer)", "Pipe Condition", "Priority Scores", "Service Request Heatmap"],
        horizontal=True,
    )

    if map_type == "Executive (Multi-Layer)":
        m = build_executive_map(pipes, scores, service_requests)
    elif map_type == "Pipe Condition":
        m = build_condition_map(pipes)
    elif map_type == "Priority Scores":
        m = build_priority_map(scores)
    else:
        m = build_service_request_heatmap(service_requests)

    st_folium(m, width=None, height=600, returned_objects=[])


# ─── TAB 4: SCENARIOS ───────────────────────────────────────────────────────
def render_scenario_tab(pipes, service_requests, work_orders):
    st.header("What-If Scenario Analysis")

    scenario_type = st.selectbox(
        "Select scenario",
        ["CIP Budget Allocation", "Deferral Cost Analysis", "Budget Coverage Curve"],
    )

    engine = PWISScenarioEngine(pipes, service_requests, work_orders)

    if scenario_type == "CIP Budget Allocation":
        col1, col2 = st.columns(2)
        with col1:
            budget = st.slider("Annual CIP Budget ($M)", 5, 100, 15, 5) * 1_000_000
        with col2:
            sys_filter = st.selectbox("System Filter", ["All", "Water", "Sewer", "Stormwater"])

        sys_val = None if sys_filter == "All" else sys_filter
        funded_df, result = engine.run_budget_scenario(budget, system_filter=sys_val)

        m = result.summary_metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Segments Funded", m["segments_funded"])
        col2.metric("Budget Utilized", f"${m['budget_utilized']:,.0f}")
        col3.metric("Pipe Feet Treated", f"{m['pipe_feet_treated']:,}")
        col4.metric("Critical Unfunded", m["critical_segments_unfunded"])

        funded_only = funded_df[funded_df["funded_this_cycle"]].copy()
        if len(funded_only) > 0:
            fig = px.bar(
                funded_only.head(30),
                x="segment_id", y="treatment_cost",
                color="priority_tier",
                color_discrete_map=COLORS,
                title="Top 30 Funded Segments by Treatment Cost",
            )
            st.plotly_chart(fig, use_container_width=True)

    elif scenario_type == "Deferral Cost Analysis":
        years = st.slider("Deferral Horizon (years)", 1, 10, 5)
        deferral_df = engine.run_deferral_scenario(years=years)

        if len(deferral_df) > 0:
            year_summary = (
                deferral_df.groupby("year_deferred")
                .agg(
                    total_projected_cost=("projected_cost", "sum"),
                    total_additional_cost=("additional_cost", "sum"),
                    pipes_critical=("projected_tier", lambda x: (x == "Critical").sum()),
                )
                .reset_index()
            )

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=year_summary["year_deferred"],
                y=year_summary["total_projected_cost"],
                mode="lines+markers",
                name="Projected Total Cost",
                line=dict(color=COLORS["Critical"], width=3),
            ))
            fig.update_layout(
                title=f"Deferral Cost Curve ({years}-Year Horizon)",
                xaxis_title="Years Deferred",
                yaxis_title="Projected Cost ($)",
                yaxis_tickformat="$,.0f",
            )
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Cost Summary")
            year_n = deferral_df[deferral_df["year_deferred"] == years]
            col1, col2, col3 = st.columns(3)
            col1.metric("Cost if Funded Today", f"${year_n['current_cost'].sum():,.0f}")
            col2.metric(f"Cost at Year {years}", f"${year_n['projected_cost'].sum():,.0f}")
            col3.metric("Additional Cost", f"${year_n['additional_cost'].sum():,.0f}")

    elif scenario_type == "Budget Coverage Curve":
        coverage = engine.run_coverage_analysis()

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=coverage["budget_millions"],
            y=coverage["pipe_feet_treated"],
            mode="lines+markers",
            name="Pipe Feet Treated",
            line=dict(color=COLORS["primary"], width=3),
        ))
        fig.update_layout(
            title="Budget Coverage Curve: What Does $X Buy?",
            xaxis_title="Annual CIP Budget ($M)",
            yaxis_title="Pipe Feet Treated",
            yaxis_tickformat=",",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(coverage, use_container_width=True)


# ─── TAB 5: RAW DATA ────────────────────────────────────────────────────────
def render_data_tab():
    st.header("Raw Data Explorer")

    pipes, service_requests, work_orders, facilities, flow_monitoring, budget_cip, weather = load_data()

    dataset = st.selectbox("Select dataset", [
        "Pipe Segments", "Service Requests", "Work Orders",
        "Facilities", "Flow Monitoring", "CIP Budget", "Weather Events",
    ])

    data_map = {
        "Pipe Segments":     pipes,
        "Service Requests":  service_requests,
        "Work Orders":       work_orders,
        "Facilities":        facilities,
        "Flow Monitoring":   flow_monitoring,
        "CIP Budget":        budget_cip,
        "Weather Events":    weather,
    }

    df = data_map[dataset]
    st.write(f"**{len(df)} rows, {len(df.columns)} columns**")
    st.dataframe(df, use_container_width=True, height=500)

    csv = df.to_csv(index=False)
    st.download_button(
        f"Download {dataset} CSV",
        csv, f"{dataset.lower().replace(' ', '_')}.csv",
        "text/csv",
    )


# ─── MAIN APP ────────────────────────────────────────────────────────────────
def main():
    weights_tuple, system_filter = render_sidebar()
    scores = run_model(weights_tuple)

    # Apply system filter
    if system_filter and len(system_filter) < 3:
        scores = scores[scores["system_type"].isin(system_filter)].copy()

    pipes, service_requests, work_orders, _, _, _, _ = load_data()

    if system_filter and len(system_filter) < 3:
        pipes = pipes[pipes["system_type"].isin(system_filter)].copy()
        service_requests = service_requests[service_requests["system_type"].isin(system_filter)].copy()

    st.title("Boise Utility Infrastructure Intelligence")
    st.caption("Water | Sewer | Stormwater — Public Works Intelligence System (PWIS)")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 KPI Overview", "📋 Priority Table", "🗺️ Infrastructure Map",
        "🔮 Scenarios", "📁 Raw Data",
    ])

    with tab1:
        render_kpi_tab(scores, pipes)
    with tab2:
        render_priority_tab(scores)
    with tab3:
        render_map_tab(scores, pipes, service_requests)
    with tab4:
        render_scenario_tab(pipes, service_requests, work_orders)
    with tab5:
        render_data_tab()


if __name__ == "__main__":
    main()
