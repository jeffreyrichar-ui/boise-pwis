"""
PWIS GIS Visualization Layer
==============================
Generates interactive Folium maps for the Boise Public Works Intelligence System.

Maps produced:
  1. Infrastructure Condition Map — heatmap by condition index
  2. Priority Score Map — color-coded by PWIS priority tier
  3. Complaint Density Map — heatmap of citizen complaint clusters
  4. Combined Executive Map — all layers, toggle-able

Design decisions:
  - Folium over ArcGIS/QGIS: free, Python-native, embeds in Streamlit and HTML
  - CircleMarkers over Choropleth: no polygon boundary data available for segments;
    point representation is accurate and fast
  - Color-blind accessible palette: Okabe-Ito safe colors for tier classification
"""

import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap, MarkerCluster, MiniMap, Fullscreen
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ─── PATHS ────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent.parent
DATA_DIR  = BASE_DIR / "data"
DOCS_DIR  = BASE_DIR / "docs"
DOCS_DIR.mkdir(exist_ok=True)

# ─── BOISE CENTER ─────────────────────────────────────────────────────────────
BOISE_CENTER = [43.615, -116.202]
DEFAULT_ZOOM = 12

# ─── COLOR PALETTES (Color-blind accessible) ──────────────────────────────────
CONDITION_COLORS = {
    "critical":  "#D62728",   # Red
    "poor":      "#FF7F0E",   # Orange
    "fair":      "#BCBD22",   # Yellow-green
    "good":      "#2CA02C",   # Green
    "excellent": "#1F77B4",   # Blue
}

TIER_COLORS = {
    "Critical": "#D62728",
    "High":     "#FF7F0E",
    "Medium":   "#BCBD22",
    "Low":      "#2CA02C",
}

DISTRICT_COLORS = {
    "North End":   "#1F77B4",
    "Downtown":    "#FF7F0E",
    "East Bench":  "#2CA02C",
    "Southeast":   "#D62728",
    "Southwest":   "#9467BD",
    "West Boise":  "#8C564B",
}


def condition_to_color(ci: float) -> str:
    if ci < 25:   return CONDITION_COLORS["critical"]
    elif ci < 45: return CONDITION_COLORS["poor"]
    elif ci < 60: return CONDITION_COLORS["fair"]
    elif ci < 80: return CONDITION_COLORS["good"]
    else:         return CONDITION_COLORS["excellent"]


def tier_to_color(tier: str) -> str:
    return TIER_COLORS.get(str(tier), "#999999")


def condition_to_radius(ci: float) -> int:
    """Worse condition → larger marker (more visible urgency)"""
    if ci < 25:   return 12
    elif ci < 45: return 9
    elif ci < 60: return 7
    elif ci < 80: return 5
    else:         return 4


# ─── TOOLTIP BUILDERS ─────────────────────────────────────────────────────────

def segment_tooltip(row) -> str:
    return f"""
    <div style='font-family: Arial; font-size: 13px; min-width: 220px;'>
        <b style='font-size:14px'>{row.get('street_name','Unknown')}</b><br>
        <hr style='margin:4px 0'>
        <b>Segment:</b> {row.get('segment_id','—')}<br>
        <b>District:</b> {row.get('district','—')}<br>
        <b>Road Type:</b> {row.get('road_type','—')}<br>
        <b>Condition Index:</b> {row.get('condition_index','—')}/100<br>
        <b>PASER Rating:</b> {row.get('paser_rating','—')}/10<br>
        <b>Daily Traffic:</b> {int(row.get('daily_traffic_aadt',0)):,} AADT<br>
        <b>Repair Cost:</b> ${int(row.get('estimated_repair_cost_usd',0)):,}<br>
    </div>
    """


def priority_tooltip(row) -> str:
    return f"""
    <div style='font-family: Arial; font-size: 13px; min-width: 260px;'>
        <b style='font-size:14px'>{row.get('street_name','Unknown')}</b><br>
        <hr style='margin:4px 0'>
        <b>Priority Score:</b> {row.get('priority_score','—')}/100<br>
        <b>Tier:</b> <span style='color:{tier_to_color(str(row.get("priority_tier","Low")))}'><b>{row.get('priority_tier','—')}</b></span><br>
        <b>District Rank:</b> #{int(row.get('district_rank',0))} in {row.get('district','—')}<br>
        <b>Condition:</b> {row.get('condition_index','—')}/100<br>
        <b>Complaints (2yr):</b> {int(row.get('raw_complaint_count',0))}<br>
        <b>Recommended Action:</b><br>
        <i>{row.get('recommended_action','—')}</i><br>
        <b>Confidence:</b> {int(float(row.get('score_confidence',0))*100)}%<br>
    </div>
    """


# ─── MAP 1: CONDITION MAP ─────────────────────────────────────────────────────

def build_condition_map(roads: pd.DataFrame) -> folium.Map:
    m = folium.Map(
        location=BOISE_CENTER,
        zoom_start=DEFAULT_ZOOM,
        tiles="CartoDB positron",
    )
    Fullscreen().add_to(m)
    MiniMap(toggle_display=True).add_to(m)

    # Add legend
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
         background: white; padding: 12px; border-radius: 8px;
         border: 2px solid #ccc; font-family: Arial; font-size: 13px;">
        <b>Road Condition Index</b><br>
        <i class="fa fa-circle" style="color:#D62728"></i> Critical (0–24)<br>
        <i class="fa fa-circle" style="color:#FF7F0E"></i> Poor (25–44)<br>
        <i class="fa fa-circle" style="color:#BCBD22"></i> Fair (45–59)<br>
        <i class="fa fa-circle" style="color:#2CA02C"></i> Good (60–79)<br>
        <i class="fa fa-circle" style="color:#1F77B4"></i> Excellent (80–100)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    for _, row in roads.iterrows():
        if pd.isna(row["lat"]) or pd.isna(row["lon"]):
            continue
        ci = row["condition_index"]
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=condition_to_radius(ci),
            color=condition_to_color(ci),
            fill=True,
            fill_color=condition_to_color(ci),
            fill_opacity=0.75,
            tooltip=folium.Tooltip(segment_tooltip(row), max_width=300),
        ).add_to(m)

    return m


# ─── MAP 2: PRIORITY SCORE MAP ────────────────────────────────────────────────

def build_priority_map(priority_scores: pd.DataFrame) -> folium.Map:
    m = folium.Map(
        location=BOISE_CENTER,
        zoom_start=DEFAULT_ZOOM,
        tiles="CartoDB dark_matter",
    )
    Fullscreen().add_to(m)
    MiniMap(toggle_display=True, tile_layer="CartoDB positron")

    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
         background: rgba(30,30,30,0.9); color: white; padding: 12px;
         border-radius: 8px; border: 1px solid #555;
         font-family: Arial; font-size: 13px;">
        <b>PWIS Priority Tier</b><br>
        <span style="color:#D62728">●</span> Critical<br>
        <span style="color:#FF7F0E">●</span> High<br>
        <span style="color:#BCBD22">●</span> Medium<br>
        <span style="color:#2CA02C">●</span> Low
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    for _, row in priority_scores.iterrows():
        if pd.isna(row["lat"]) or pd.isna(row["lon"]):
            continue
        tier = str(row.get("priority_tier", "Low"))
        score = float(row.get("priority_score", 0))
        radius = max(5, min(15, score / 7))

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=radius,
            color=tier_to_color(tier),
            fill=True,
            fill_color=tier_to_color(tier),
            fill_opacity=0.8,
            tooltip=folium.Tooltip(priority_tooltip(row), max_width=320),
        ).add_to(m)

    return m


# ─── MAP 3: COMPLAINT HEATMAP ─────────────────────────────────────────────────

def build_complaint_heatmap(complaints: pd.DataFrame) -> folium.Map:
    m = folium.Map(
        location=BOISE_CENTER,
        zoom_start=DEFAULT_ZOOM,
        tiles="CartoDB positron",
    )
    Fullscreen().add_to(m)

    severity_weights = {"Critical": 1.0, "High": 0.75, "Medium": 0.5, "Low": 0.25}
    heat_data = []
    for _, row in complaints.dropna(subset=["lat", "lon"]).iterrows():
        w = severity_weights.get(row.get("severity_reported", "Low"), 0.25)
        heat_data.append([row["lat"], row["lon"], w])

    HeatMap(
        heat_data,
        name="Complaint Density",
        min_opacity=0.3,
        radius=18,
        blur=15,
        gradient={"0.2": "#1F77B4", "0.5": "#BCBD22", "0.8": "#FF7F0E", "1.0": "#D62728"},
    ).add_to(m)

    title_html = """
    <div style="position: fixed; top: 80px; left: 50px; z-index: 1000;
         background: white; padding: 10px; border-radius: 8px;
         border: 2px solid #ccc; font-family: Arial; font-size: 14px;">
        <b>Citizen Complaint Heatmap</b><br>
        <small>Weighted by reported severity</small>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))
    return m


# ─── MAP 4: COMBINED EXECUTIVE MAP ────────────────────────────────────────────

def build_executive_map(
    roads: pd.DataFrame,
    priority_scores: pd.DataFrame,
    complaints: pd.DataFrame,
) -> folium.Map:
    """
    Multi-layer executive map with toggleable layers.
    Designed for Director-level briefings and Council presentations.
    """
    m = folium.Map(
        location=BOISE_CENTER,
        zoom_start=12,
        tiles=None,
    )

    # Basemaps
    folium.TileLayer("CartoDB positron", name="Light Basemap", control=True).add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Dark Basemap", control=True).add_to(m)
    folium.TileLayer("OpenStreetMap", name="Street Map", control=True).add_to(m)

    Fullscreen().add_to(m)
    MiniMap(toggle_display=True).add_to(m)

    # ── Layer 1: Condition (toggle off by default) ──
    condition_layer = folium.FeatureGroup(name="Road Condition Index", show=False)
    for _, row in roads.iterrows():
        if pd.isna(row["lat"]) or pd.isna(row["lon"]):
            continue
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=condition_to_radius(row["condition_index"]),
            color=condition_to_color(row["condition_index"]),
            fill=True, fill_color=condition_to_color(row["condition_index"]),
            fill_opacity=0.7,
            tooltip=folium.Tooltip(segment_tooltip(row), max_width=300),
        ).add_to(condition_layer)
    condition_layer.add_to(m)

    # ── Layer 2: Priority Scores (show by default) ──
    priority_layer = folium.FeatureGroup(name="Priority Scores (PWIS Model)", show=True)
    for _, row in priority_scores.iterrows():
        if pd.isna(row["lat"]) or pd.isna(row["lon"]):
            continue
        tier = str(row.get("priority_tier", "Low"))
        score = float(row.get("priority_score", 0))
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=max(5, min(14, score / 7)),
            color=tier_to_color(tier),
            fill=True, fill_color=tier_to_color(tier),
            fill_opacity=0.8,
            tooltip=folium.Tooltip(priority_tooltip(row), max_width=320),
        ).add_to(priority_layer)
    priority_layer.add_to(m)

    # ── Layer 3: Complaint Heatmap ──
    complaint_layer = folium.FeatureGroup(name="Complaint Heatmap", show=False)
    severity_weights = {"Critical": 1.0, "High": 0.75, "Medium": 0.5, "Low": 0.25}
    heat_data = [
        [r["lat"], r["lon"], severity_weights.get(r.get("severity_reported", "Low"), 0.25)]
        for _, r in complaints.dropna(subset=["lat", "lon"]).iterrows()
    ]
    HeatMap(heat_data, min_opacity=0.3, radius=18, blur=15).add_to(complaint_layer)
    complaint_layer.add_to(m)

    # ── Layer 4: High-Priority Clusters ──
    high_priority = priority_scores[
        priority_scores["priority_tier"].astype(str).isin(["Critical", "High"])
    ]
    cluster_layer = folium.FeatureGroup(name="High-Priority Cluster View", show=False)
    cluster = MarkerCluster().add_to(cluster_layer)
    for _, row in high_priority.iterrows():
        if pd.isna(row["lat"]) or pd.isna(row["lon"]):
            continue
        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=folium.Popup(priority_tooltip(row), max_width=320),
            icon=folium.Icon(
                color="red" if str(row.get("priority_tier")) == "Critical" else "orange",
                icon="exclamation-sign",
            ),
        ).add_to(cluster)
    cluster_layer.add_to(m)

    # Layer control
    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    # Title card
    title_html = """
    <div style="position: fixed; top: 80px; left: 50px; z-index: 1000;
         background: rgba(255,255,255,0.95); padding: 14px 18px;
         border-radius: 10px; border: 2px solid #1F77B4;
         font-family: Arial; max-width: 280px; box-shadow: 2px 2px 8px rgba(0,0,0,0.2);">
        <b style="font-size:16px; color:#1F77B4">PWIS Executive Map</b><br>
        <small>City of Boise — Public Works<br>
        Infrastructure Priority Intelligence<br>
        <i>Toggle layers using control (top right)</i></small>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    return m


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Loading datasets...")
    roads      = pd.read_csv(DATA_DIR / "road_segments.csv")
    complaints = pd.read_csv(DATA_DIR / "complaints.csv")

    if (DATA_DIR / "priority_scores.csv").exists():
        priority_scores = pd.read_csv(DATA_DIR / "priority_scores.csv")
        # Merge lat/lon back in if not present
        if "lat" not in priority_scores.columns:
            priority_scores = priority_scores.merge(
                roads[["segment_id", "lat", "lon"]], on="segment_id", how="left"
            )
    else:
        print("Warning: priority_scores.csv not found. Run models/prioritization.py first.")
        priority_scores = roads.copy()

    print("Building maps...")

    m1 = build_condition_map(roads)
    m1.save(str(DOCS_DIR / "map_condition.html"))
    print("  ✓ Condition map → docs/map_condition.html")

    m2 = build_priority_map(priority_scores)
    m2.save(str(DOCS_DIR / "map_priority.html"))
    print("  ✓ Priority map  → docs/map_priority.html")

    m3 = build_complaint_heatmap(complaints)
    m3.save(str(DOCS_DIR / "map_complaints.html"))
    print("  ✓ Complaint map → docs/map_complaints.html")

    m4 = build_executive_map(roads, priority_scores, complaints)
    m4.save(str(DOCS_DIR / "map_executive.html"))
    print("  ✓ Executive map → docs/map_executive.html")

    print("\n✓ All GIS maps generated. Open HTML files in browser to view.")
    print("\nMap inventory:")
    for f in ["map_condition.html", "map_priority.html",
              "map_complaints.html", "map_executive.html"]:
        path = DOCS_DIR / f
        size_kb = path.stat().st_size // 1024
        print(f"  {f}: {size_kb} KB")
