"""
PWIS Synthetic Data Generator — Boise Public Works
====================================================
Generates realistic synthetic datasets for the three pipe systems
actually maintained by City of Boise Public Works:

  1. WASTEWATER/SEWER COLLECTION — ~900 miles of gravity sewer and
     force mains, 28 lift stations, 2 water renewal facilities.
     Materials: vitrified clay (oldest), PVC, concrete, ductile iron.
     Serves Boise, Garden City, Eagle (~250,000 people).

  2. GEOTHERMAL DISTRICT HEATING — 20+ miles of closed-loop pipeline
     delivering 177°F water from 3 foothills wells to ~90 downtown
     buildings. Steel and Transite (concrete) pipe. Injection well
     at Julia Davis Park returns spent water to aquifer.

  3. PRESSURIZED IRRIGATION (PI) — Small non-potable system diverting
     Boise River water to 14 subdivisions via canals. PVC PR-SDR pipe,
     4-12 inch. Seasonal: April 15 – October 15.

NOTE: Boise PW does NOT manage:
  - Drinking water distribution (operated by Veolia, a private utility)
  - Street stormwater drainage (managed by ACHD — Ada County Highway District)
  - Large-scale agricultural irrigation (managed by Boise Project Board of Control)

Sources:
  City of Boise Public Works — Sewer / Geothermal / Pressure Irrigation
  West Boise Water Renewal Facility planning docs
  Lander Street Facility Improvement Plan ($265M, 2023-2029)
  Boise Pressure Irrigation Design Standards (cityofboise.org)
  City of Boise Geothermal Walking Tour brochure
  Idaho Dept of Water Resources — geothermal management area
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from pathlib import Path

np.random.seed(42)
random.seed(42)

BASE_DIR = Path(__file__).parent

# ─── BOISE SERVICE DISTRICTS ─────────────────────────────────────────────────
# Mapped to real sewer/utility service boundaries
# (lat_min, lat_max, lon_min, lon_max)
SERVICE_DISTRICTS = {
    "North End":   (43.626, 43.680, -116.230, -116.170),
    "Downtown":    (43.600, 43.626, -116.220, -116.175),
    "East Bench":  (43.580, 43.626, -116.175, -116.100),
    "Southeast":   (43.540, 43.595, -116.200, -116.100),
    "Southwest":   (43.540, 43.600, -116.330, -116.200),
    "West Boise":  (43.600, 43.655, -116.360, -116.230),
}
DISTRICTS = list(SERVICE_DISTRICTS.keys())

# ─── SOIL CORROSIVITY BY DISTRICT ───────────────────────────────────────────
# Affects metallic and clay pipe degradation rates
SOIL_CORROSIVITY = {
    "North End":   0.72,  # Alluvial, high moisture near river/canal
    "Downtown":    0.78,  # Oldest soils, river-adjacent, disturbed fill
    "East Bench":  0.45,  # Bench gravels, well-drained
    "Southeast":   0.55,  # Mixed clay/gravel
    "Southwest":   0.60,  # Former ag land, irrigation-affected clay
    "West Boise":  0.50,  # Former farmland, mixed
}

METALLIC_MATERIALS = {"Cast Iron", "Ductile Iron", "Galvanized Steel", "Steel"}


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM 1: WASTEWATER / SEWER COLLECTION
# ═══════════════════════════════════════════════════════════════════════════════
# ~900 miles of pipe, 28 lift stations, serves ~250k people
# Gravity collection → lift stations → trunk/interceptor → WRF

SEWER_MATERIALS = {
    "Vitrified Clay":  {"era": (1920, 1975), "pct": 0.25, "fail_rate": "high"},
    "PVC":             {"era": (1975, 2026), "pct": 0.30, "fail_rate": "low"},
    "Concrete":        {"era": (1940, 1995), "pct": 0.18, "fail_rate": "medium"},
    "Ductile Iron":    {"era": (1965, 2010), "pct": 0.15, "fail_rate": "medium"},
    "HDPE":            {"era": (2005, 2026), "pct": 0.05, "fail_rate": "low"},
    "Orangeburg":      {"era": (1945, 1972), "pct": 0.04, "fail_rate": "high"},
    "Cast Iron":       {"era": (1920, 1965), "pct": 0.03, "fail_rate": "high"},
}

# Sewer pipe diameters: 6" laterals through 48" trunk/interceptors
SEWER_DIAMETERS = [6, 8, 10, 12, 15, 18, 21, 24, 30, 36, 42, 48]
# Weight toward smaller pipes (most of the network is 8-12")
SEWER_DIAM_WEIGHTS = [0.05, 0.25, 0.15, 0.20, 0.10, 0.08, 0.05, 0.04, 0.03, 0.02, 0.02, 0.01]

# Real Boise sewer corridors with documented infrastructure
# (name, district, lat, lon, orientation, era, pipe_class)
# pipe_class: "lateral" (6-12"), "collector" (12-24"), "trunk" (24-48")
SEWER_CORRIDORS = [
    # ── DOWNTOWN (1860s-1950s, oldest sewer infrastructure) ──────────────
    ("Main St",          "Downtown",  43.615, -116.200, "EW",  "old",  "collector"),
    ("Capitol Blvd",     "Downtown",  43.611, -116.201, "NS",  "old",  "trunk"),  # major trunk sewer
    ("Front St",         "Downtown",  43.606, -116.205, "EW",  "old",  "collector"),
    ("Bannock St",       "Downtown",  43.613, -116.200, "EW",  "old",  "lateral"),
    ("Idaho St",         "Downtown",  43.614, -116.202, "EW",  "old",  "lateral"),
    ("Myrtle St",        "Downtown",  43.607, -116.200, "EW",  "old",  "collector"),
    ("8th St",           "Downtown",  43.613, -116.197, "NS",  "old",  "lateral"),
    ("9th St",           "Downtown",  43.613, -116.199, "NS",  "old",  "lateral"),
    ("Jefferson St",     "Downtown",  43.616, -116.201, "EW",  "old",  "collector"),
    ("Lander St",        "Downtown",  43.601, -116.224, "EW",  "old",  "trunk"),  # near Lander WRF
    ("Broadway Ave",     "Downtown",  43.612, -116.188, "NS",  "mid",  "trunk"),

    # ── NORTH END (1878-1950s, first residential neighborhood) ──────────
    # Documented: oldest clay/cast iron laterals, heavy root intrusion
    ("Harrison Blvd",    "North End", 43.643, -116.200, "NS",  "old",  "collector"),
    ("Fort St",          "North End", 43.638, -116.205, "EW",  "old",  "lateral"),
    ("Hill Rd",          "North End", 43.660, -116.215, "EW",  "old",  "collector"),
    ("15th St",          "North End", 43.645, -116.208, "NS",  "old",  "lateral"),
    ("Bogus Basin Rd",   "North End", 43.665, -116.195, "DIAG","old",  "lateral"),
    ("Eastman St",       "North End", 43.641, -116.203, "EW",  "old",  "lateral"),
    ("28th St",          "North End", 43.650, -116.215, "NS",  "old",  "lateral"),
    ("Resseguie St",     "North End", 43.637, -116.202, "EW",  "old",  "lateral"),

    # ── EAST BENCH (1930s-1960s, 1950s sewer system replaced septics) ──
    # Documented: 95 miles of 8-36" pipe installed in 1950s
    ("Warm Springs Ave", "East Bench",43.608, -116.165, "EW",  "old",  "collector"),
    ("Federal Way",      "East Bench",43.597, -116.158, "EW",  "mid",  "collector"),
    ("Parkcenter Blvd",  "East Bench",43.597, -116.178, "NS",  "mid",  "trunk"),
    ("Boise Ave",        "East Bench",43.600, -116.172, "EW",  "mid",  "collector"),
    ("Shaw Mountain Rd", "East Bench",43.605, -116.155, "DIAG","mid",  "lateral"),

    # ── SOUTHEAST (1960s-1970s bulk development) ────────────────────────
    ("Vista Ave",        "Southeast", 43.575, -116.207, "NS",  "mid",  "collector"),
    ("Broadway Ave",     "Southeast", 43.568, -116.188, "NS",  "mid",  "trunk"),
    ("Overland Rd",      "Southeast", 43.588, -116.195, "EW",  "mid",  "collector"),
    ("Milwaukee St",     "Southeast", 43.565, -116.210, "NS",  "mid",  "lateral"),
    ("Gowen Rd",         "Southeast", 43.543, -116.158, "EW",  "new",  "lateral"),
    ("Eisenman Rd",      "Southeast", 43.550, -116.170, "NS",  "new",  "collector"),
    ("Victory Rd",       "Southeast", 43.570, -116.195, "EW",  "mid",  "collector"),
    ("Orchard St",       "Southeast", 43.583, -116.232, "NS",  "mid",  "collector"),  # documented upgrade project

    # ── SOUTHWEST (1960s-1980s) ─────────────────────────────────────────
    ("Five Mile Rd",     "Southwest", 43.575, -116.295, "NS",  "mid",  "collector"),
    ("Maple Grove Rd",   "Southwest", 43.575, -116.276, "NS",  "mid",  "collector"),
    ("Cole Rd",          "Southwest", 43.572, -116.256, "NS",  "mid",  "collector"),
    ("Overland Rd",      "Southwest", 43.588, -116.270, "EW",  "mid",  "trunk"),
    ("Curtis Rd",        "Southwest", 43.580, -116.222, "NS",  "mid",  "lateral"),
    ("Victory Rd",       "Southwest", 43.570, -116.280, "EW",  "mid",  "collector"),
    ("Amity Rd",         "Southwest", 43.553, -116.275, "EW",  "new",  "collector"),

    # ── WEST BOISE (1970s-present, newest growth) ───────────────────────
    ("Fairview Ave",     "West Boise",43.616, -116.295, "EW",  "new",  "trunk"),
    ("Ustick Rd",        "West Boise",43.633, -116.300, "EW",  "new",  "collector"),
    ("McMillan Rd",      "West Boise",43.643, -116.310, "EW",  "new",  "collector"),
    ("Chinden Blvd",     "West Boise",43.653, -116.310, "EW",  "new",  "collector"),
    ("State St",         "West Boise",43.637, -116.280, "EW",  "new",  "collector"),
    ("Eagle Rd",         "West Boise",43.625, -116.354, "NS",  "new",  "trunk"),
    ("Cloverdale Rd",    "West Boise",43.620, -116.336, "NS",  "new",  "collector"),
    ("Ten Mile Rd",      "West Boise",43.615, -116.316, "NS",  "new",  "collector"),
    ("Joplin Rd",        "West Boise",43.610, -116.310, "NS",  "new",  "trunk"),  # near West Boise WRF
    ("Franklin Rd",      "West Boise",43.607, -116.290, "EW",  "new",  "collector"),
]

# Sewer-specific work order types
SEWER_WO_TYPES = [
    "Line Clearing", "Root Removal", "Manhole Repair",
    "CCTV Inspection", "Pipe Lining (CIPP)", "Bypass Pumping",
    "Lift Station Repair", "Grease Trap Inspection",
    "Lateral Repair", "Force Main Repair",
]

SEWER_SR_TYPES = [
    "Sewer Backup", "Manhole Overflow", "Odor Complaint",
    "Slow Drain", "Root Intrusion Report", "Lift Station Alarm",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM 2: GEOTHERMAL DISTRICT HEATING
# ═══════════════════════════════════════════════════════════════════════════════
# 20+ miles of closed-loop pipeline, 177°F supply, ~90 buildings
# 3 production wells (NE foothills) → downtown distribution → injection well (Julia Davis Park)

GEOTHERMAL_MATERIALS = {
    "Steel":           {"era": (1983, 2026), "pct": 0.55, "fail_rate": "medium"},
    "Pre-insulated Steel": {"era": (2000, 2026), "pct": 0.25, "fail_rate": "low"},
    "Transite":        {"era": (1970, 1995), "pct": 0.15, "fail_rate": "high"},  # concrete pipe, Warm Springs system
    "HDPE":            {"era": (2010, 2026), "pct": 0.05, "fail_rate": "low"},
}

# Geothermal diameters: 4-16" (supply/return mains, building laterals)
GEO_DIAMETERS = [4, 6, 8, 10, 12, 16]
GEO_DIAM_WEIGHTS = [0.20, 0.25, 0.20, 0.15, 0.12, 0.08]

# Geothermal pipe corridors — based on documented system routes
# System 1: Warm Springs Avenue (1890s, ~300 homes)
# System 2: Downtown/Capitol Mall (1983, ~90 commercial buildings)
# System 3: BSU campus (2013-present, 11 buildings)
GEOTHERMAL_CORRIDORS = [
    # ── WARM SPRINGS AVENUE SYSTEM (1892, residential) ──────────────────
    # 12" Transite mainline from foothills wells down Warm Springs Ave
    ("Warm Springs Ave",      "East Bench",43.608, -116.165, "EW",  "old",  "supply_main"),
    ("Warm Springs Ave (W)",  "Downtown",  43.608, -116.185, "EW",  "old",  "supply_main"),
    ("Avenue B",              "East Bench",43.610, -116.178, "NS",  "old",  "lateral"),
    ("Walnut St",             "East Bench",43.606, -116.170, "EW",  "old",  "lateral"),
    ("Crescent Rim Dr",       "East Bench",43.604, -116.175, "EW",  "old",  "lateral"),

    # ── DOWNTOWN SYSTEM (1983, commercial district) ─────────────────────
    # Pipeline from foothills wells through downtown streets
    ("Capitol Blvd",          "Downtown",  43.611, -116.201, "NS",  "mid",  "supply_main"),
    ("Myrtle St",             "Downtown",  43.607, -116.200, "EW",  "mid",  "distribution"),
    ("Main St",               "Downtown",  43.615, -116.200, "EW",  "mid",  "distribution"),
    ("8th St",                "Downtown",  43.613, -116.197, "NS",  "mid",  "lateral"),
    ("6th St",                "Downtown",  43.613, -116.194, "NS",  "mid",  "lateral"),
    ("Idaho St",              "Downtown",  43.614, -116.202, "EW",  "mid",  "distribution"),
    ("Front St",              "Downtown",  43.606, -116.205, "EW",  "mid",  "distribution"),
    ("Bannock St",            "Downtown",  43.613, -116.200, "EW",  "mid",  "lateral"),
    ("Jefferson St",          "Downtown",  43.616, -116.201, "EW",  "mid",  "lateral"),
    ("9th St",                "Downtown",  43.613, -116.199, "NS",  "mid",  "lateral"),

    # ── CAPITOL MALL / STATE BUILDINGS ──────────────────────────────────
    ("Capitol Mall",          "Downtown",  43.618, -116.200, "NS",  "mid",  "supply_main"),

    # ── JULIA DAVIS PARK (injection well return line) ───────────────────
    ("Julia Davis Dr",        "Downtown",  43.604, -116.195, "EW",  "new",  "return_main"),

    # ── BSU CAMPUS (2013-present expansion) ─────────────────────────────
    ("University Dr",         "Downtown",  43.603, -116.198, "EW",  "new",  "distribution"),
    ("Lincoln Ave",           "Downtown",  43.602, -116.194, "EW",  "new",  "lateral"),
    ("Campus Ln",             "Downtown",  43.601, -116.200, "NS",  "new",  "lateral"),
    ("Brady St",              "Downtown",  43.605, -116.190, "EW",  "new",  "lateral"),
]

GEOTHERMAL_WO_TYPES = [
    "Pipe Insulation Repair", "Valve Replacement", "Leak Repair",
    "Heat Exchanger Service", "Well Pump Maintenance", "Pressure Test",
    "Injection Well Service", "Building Connection Repair",
    "Seasonal Startup Check", "Temperature Sensor Calibration",
]

GEOTHERMAL_SR_TYPES = [
    "Low Heat Output", "No Geothermal Flow", "Leak Report",
    "Building Temperature Issue", "Unusual Noise from Pipes",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM 3: PRESSURIZED IRRIGATION (PI)
# ═══════════════════════════════════════════════════════════════════════════════
# 14 subdivisions, non-potable Boise River water via canal diversions
# PVC PR-SDR pipe per Boise Design Standards, seasonal Apr 15 – Oct 15

PI_MATERIALS = {
    "PVC PR-SDR":  {"era": (1993, 2026), "pct": 0.75, "fail_rate": "low"},
    "PVC C900":    {"era": (1997, 2026), "pct": 0.15, "fail_rate": "low"},
    "HDPE":        {"era": (2005, 2026), "pct": 0.10, "fail_rate": "low"},
}

PI_DIAMETERS = [4, 6, 8, 10, 12]
PI_DIAM_WEIGHTS = [0.15, 0.30, 0.25, 0.20, 0.10]

# Documented and inferred PI subdivisions — primarily post-1997 West Boise
# Canal sources: Boise City Canal, Ustick Ditch, McMillan Lateral, Ridenbaugh Canal
PI_SUBDIVISIONS = [
    # (subdivision_name, district, lat, lon, approx_year, canal_source, n_lots)
    ("Bradford",            "West Boise",  43.635, -116.320, 1999, "McMillan Lateral", 85),
    ("Graystone Phase 1",  "West Boise",  43.640, -116.330, 2001, "McMillan Lateral", 60),
    ("Graystone Phase 2",  "West Boise",  43.642, -116.332, 2003, "McMillan Lateral", 72),
    ("Hickories East",     "West Boise",  43.630, -116.310, 2000, "McMillan Lateral", 55),
    ("Paramount",          "West Boise",  43.648, -116.340, 2005, "Ustick Ditch", 120),
    ("Spurwing Greens",    "West Boise",  43.650, -116.350, 2006, "Ustick Ditch", 95),
    ("Spring Creek",       "West Boise",  43.625, -116.345, 2004, "Boise City Canal", 78),
    ("BanBury",            "West Boise",  43.618, -116.338, 2002, "Boise City Canal", 65),
    ("Heritage Commons",   "Southwest",   43.555, -116.280, 2007, "Ridenbaugh Canal", 50),
    ("Millbrook",          "Southwest",   43.560, -116.290, 2008, "Ridenbaugh Canal", 45),
    ("Valley Creek",       "Southwest",   43.558, -116.275, 2010, "Ridenbaugh Canal", 40),
    ("South Creek Ranch",  "Southeast",   43.548, -116.168, 2009, "New York Canal", 55),
    ("Eisenman Station",   "Southeast",   43.552, -116.172, 2012, "New York Canal", 48),
    ("Gateway East",       "Southeast",   43.545, -116.160, 2015, "New York Canal", 35),
]

PI_WO_TYPES = [
    "Valve Repair", "Lateral Leak Repair", "Main Leak Repair",
    "Pressure Regulator Replacement", "Seasonal Startup",
    "Seasonal Shutdown", "Backflow Preventer Inspection",
    "Canal Intake Cleaning", "Pump Station Service",
]

PI_SR_TYPES = [
    "No Irrigation Pressure", "PI Leak Report",
    "Sprinkler Supply Issue", "Scheduled Watering Conflict",
    "Backflow Device Issue", "Brown Lawn / No Flow",
]


# ─── ERA TO INSTALL YEAR RANGES ────────────────────────────────────────────
ERA_INSTALL_RANGE = {
    "old": (1925, 1965),  # Downtown + North End (pre-WWII through early postwar)
    "mid": (1955, 1995),  # East Bench, Southeast, Southwest, downtown geothermal
    "new": (1990, 2024),  # West Boise, far Southeast, BSU geothermal
}


# ─── SHARED UTILITIES ──────────────────────────────────────────────────────

def _pick_material(materials_dict, install_year):
    """Pick a pipe material consistent with the install year."""
    eligible = [
        (m, d) for m, d in materials_dict.items()
        if d["era"][0] <= install_year <= d["era"][1]
    ]
    if not eligible:
        closest = min(materials_dict.items(),
                      key=lambda x: min(abs(install_year - x[1]["era"][0]),
                                        abs(install_year - x[1]["era"][1])))
        return closest[0]
    weights = [d["pct"] for _, d in eligible]
    total = sum(weights)
    weights = [w / total for w in weights]
    idx = np.random.choice(len(eligible), p=weights)
    return eligible[idx][0]


def _coord_offset(anchor_lat, anchor_lon, orientation, district):
    if orientation == "EW":
        lat = anchor_lat + random.uniform(-0.003, 0.003)
        lon = anchor_lon + random.uniform(-0.040, 0.040)
    elif orientation == "NS":
        lat = anchor_lat + random.uniform(-0.040, 0.040)
        lon = anchor_lon + random.uniform(-0.003, 0.003)
    else:
        lat = anchor_lat + random.uniform(-0.020, 0.020)
        lon = anchor_lon + random.uniform(-0.020, 0.020)
    db = SERVICE_DISTRICTS[district]
    lat = float(np.clip(lat, db[0], db[1]))
    lon = float(np.clip(lon, db[2], db[3]))
    return round(lat, 6), round(lon, 6)


def _condition_from_material_age_soil(material, materials_dict, age, district):
    """Condition score driven by age + material, with soil corrosivity for metallic/clay."""
    fail_rate = materials_dict.get(material, {}).get("fail_rate", "medium")
    base = {"high": 85, "medium": 90, "low": 95}[fail_rate]
    annual_decay = {"high": 0.90, "medium": 0.50, "low": 0.25}[fail_rate]
    age_penalty = age * annual_decay

    soil_penalty = 0.0
    if material in METALLIC_MATERIALS or material in ("Vitrified Clay", "Transite"):
        soil_factor = SOIL_CORROSIVITY.get(district, 0.5)
        soil_penalty = age * 0.20 * soil_factor

    condition = base - age_penalty - soil_penalty + np.random.normal(0, 8)
    return int(np.clip(condition, 5, 100))


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_sewer_segments(n=4200):
    """Generate ~4200 sewer pipe segments (~900 miles of collection system)."""
    segments = []
    for seg_id in range(1, n + 1):
        corridor = random.choice(SEWER_CORRIDORS)
        name, district, a_lat, a_lon, orient, era, pipe_class = corridor

        yr_lo, yr_hi = ERA_INSTALL_RANGE[era]
        install_year = random.randint(yr_lo, yr_hi)
        age = 2026 - install_year

        material = _pick_material(SEWER_MATERIALS, install_year)

        # Diameter depends on pipe class
        if pipe_class == "trunk":
            diameter = random.choice([24, 30, 36, 42, 48])
        elif pipe_class == "collector":
            diameter = random.choice([12, 15, 18, 21, 24])
        else:  # lateral
            diameter = np.random.choice(SEWER_DIAMETERS, p=SEWER_DIAM_WEIGHTS)

        length_ft = random.randint(200, 2500)
        condition = _condition_from_material_age_soil(material, SEWER_MATERIALS, age, district)

        # Breaks
        fail_rate = SEWER_MATERIALS.get(material, {}).get("fail_rate", "medium")
        break_base = {"high": 3.0, "medium": 1.0, "low": 0.2}[fail_rate]
        soil_mult = 1.0
        if material in METALLIC_MATERIALS or material == "Vitrified Clay":
            soil_mult = 1.0 + SOIL_CORROSIVITY.get(district, 0.5) * 0.5
        breaks_5yr = max(0, int(np.random.poisson(break_base * (age / 50.0) * soil_mult)))
        if condition < 20 and breaks_5yr == 0:
            breaks_5yr = random.randint(1, 3)
        if condition > 85 and breaks_5yr > 2:
            breaks_5yr = random.randint(0, 1)

        # Capacity utilization — older systems more stressed, gravity sewers fill up
        capacity_pct = round(np.clip(np.random.normal(
            {"old": 78, "mid": 60, "new": 40}[era], 18), 5, 100), 1)

        # I&I flag — inflow/infiltration is the #1 issue in old clay sewers
        ii_risk = material in ("Vitrified Clay", "Orangeburg", "Cast Iron") and age > 40

        lat, lon = _coord_offset(a_lat, a_lon, orient, district)
        depth_ft = round(random.uniform(5, 25), 1)
        cost_per_ft = random.uniform(100, 500)
        diam_mult = 1.0 + (diameter - 12) * 0.03
        replacement_cost = int(length_ft * cost_per_ft * max(diam_mult, 0.5))

        # Criticality
        crit_roll = random.random()
        if crit_roll < 0.08:
            criticality = "Critical"
        elif crit_roll < 0.26:
            criticality = "High"
        elif crit_roll < 0.66:
            criticality = "Medium"
        else:
            criticality = "Low"
        if pipe_class == "trunk" or diameter >= 30:
            criticality = {"Low": "Medium", "Medium": "High", "High": "Critical", "Critical": "Critical"}[criticality]

        segments.append({
            "segment_id":       f"SEW-{str(seg_id).zfill(5)}",
            "system_type":      "Wastewater",
            "corridor_name":    name,
            "district":         district,
            "pipe_class":       pipe_class,
            "pipe_material":    material,
            "diameter_inches":  int(diameter),
            "length_ft":        length_ft,
            "depth_ft":         depth_ft,
            "install_year":     install_year,
            "asset_age_years":  age,
            "condition_score":  condition,
            "breaks_last_5yr":  breaks_5yr,
            "soil_corrosivity": SOIL_CORROSIVITY[district],
            "capacity_utilization_pct": capacity_pct,
            "ii_risk_flag":     ii_risk,
            "criticality_class": criticality,
            "estimated_replacement_cost_usd": replacement_cost,
            "last_inspection_date": (
                datetime(2026, 1, 1) - timedelta(days=random.randint(30, 1200))
            ).strftime("%Y-%m-%d"),
            "inspection_method": random.choice(
                ["CCTV", "Smoke Test", "Manhole Inspection", "Flow Monitoring", "Dye Test"]),
            "lat": lat, "lon": lon,
        })
    return pd.DataFrame(segments)


def generate_geothermal_segments(n=350):
    """Generate ~350 geothermal pipe segments (~20 miles of pipeline)."""
    segments = []
    for seg_id in range(1, n + 1):
        corridor = random.choice(GEOTHERMAL_CORRIDORS)
        name, district, a_lat, a_lon, orient, era, pipe_role = corridor

        yr_lo, yr_hi = ERA_INSTALL_RANGE[era]
        install_year = random.randint(yr_lo, yr_hi)
        age = 2026 - install_year

        material = _pick_material(GEOTHERMAL_MATERIALS, install_year)

        if pipe_role == "supply_main":
            diameter = random.choice([10, 12, 16])
        elif pipe_role in ("distribution", "return_main"):
            diameter = random.choice([8, 10, 12])
        else:  # lateral
            diameter = np.random.choice(GEO_DIAMETERS, p=GEO_DIAM_WEIGHTS)

        length_ft = random.randint(100, 800)  # shorter runs, dense downtown grid
        condition = _condition_from_material_age_soil(material, GEOTHERMAL_MATERIALS, age, district)

        # Geothermal breaks are less about pipe failure, more about
        # insulation degradation, joint leaks, and heat loss
        fail_rate = GEOTHERMAL_MATERIALS.get(material, {}).get("fail_rate", "medium")
        break_base = {"high": 1.5, "medium": 0.5, "low": 0.1}[fail_rate]
        breaks_5yr = max(0, int(np.random.poisson(break_base * (age / 40.0))))
        if condition < 20 and breaks_5yr == 0:
            breaks_5yr = random.randint(1, 2)

        # Supply temperature — degrades with pipe condition (insulation loss)
        supply_temp_f = round(177 - (100 - condition) * 0.3 + np.random.normal(0, 2), 1)
        supply_temp_f = max(140, min(180, supply_temp_f))

        # Return temperature — should be significantly cooler
        return_temp_f = round(supply_temp_f - random.uniform(40, 80), 1)

        lat, lon = _coord_offset(a_lat, a_lon, orient, district)
        depth_ft = round(random.uniform(3, 8), 1)
        cost_per_ft = random.uniform(200, 800)  # expensive — insulated steel in downtown streets
        diam_mult = 1.0 + (diameter - 8) * 0.04
        replacement_cost = int(length_ft * cost_per_ft * max(diam_mult, 0.5))

        # Criticality — supply mains are critical, laterals less so
        if pipe_role in ("supply_main", "return_main"):
            criticality = "Critical" if random.random() < 0.4 else "High"
        elif pipe_role == "distribution":
            criticality = random.choice(["High", "Medium", "Medium"])
        else:
            criticality = random.choice(["Medium", "Low", "Low"])

        segments.append({
            "segment_id":       f"GEO-{str(seg_id).zfill(4)}",
            "system_type":      "Geothermal",
            "corridor_name":    name,
            "district":         district,
            "pipe_role":        pipe_role,
            "pipe_material":    material,
            "diameter_inches":  int(diameter),
            "length_ft":        length_ft,
            "depth_ft":         depth_ft,
            "install_year":     install_year,
            "asset_age_years":  age,
            "condition_score":  condition,
            "breaks_last_5yr":  breaks_5yr,
            "supply_temp_f":    supply_temp_f,
            "return_temp_f":    return_temp_f,
            "capacity_utilization_pct": round(np.clip(np.random.normal(65, 20), 10, 100), 1),
            "criticality_class": criticality,
            "estimated_replacement_cost_usd": replacement_cost,
            "last_inspection_date": (
                datetime(2026, 1, 1) - timedelta(days=random.randint(30, 730))
            ).strftime("%Y-%m-%d"),
            "inspection_method": random.choice(
                ["Thermal Imaging", "Pressure Test", "Visual", "Ultrasonic Thickness"]),
            "lat": lat, "lon": lon,
        })
    return pd.DataFrame(segments)


def generate_pi_segments(n=280):
    """Generate ~280 pressurized irrigation pipe segments across 14 subdivisions."""
    segments = []
    seg_id = 1
    for _ in range(n):
        sub = random.choices(PI_SUBDIVISIONS, weights=[s[6] for s in PI_SUBDIVISIONS], k=1)[0]
        sub_name, district, a_lat, a_lon, sub_year, canal, n_lots = sub

        install_year = sub_year + random.randint(-1, 3)
        install_year = max(1993, min(install_year, 2024))
        age = 2026 - install_year

        material = _pick_material(PI_MATERIALS, install_year)
        diameter = np.random.choice(PI_DIAMETERS, p=PI_DIAM_WEIGHTS)
        length_ft = random.randint(150, 1200)

        condition = _condition_from_material_age_soil(material, PI_MATERIALS, age, district)

        fail_rate = PI_MATERIALS.get(material, {}).get("fail_rate", "low")
        break_base = {"low": 0.1, "medium": 0.5, "high": 1.0}[fail_rate]
        breaks_5yr = max(0, int(np.random.poisson(break_base * (age / 30.0))))

        # PI capacity is seasonal — annual average 45-65%
        capacity_pct = round(np.clip(np.random.normal(55, 15), 10, 95), 1)

        lat = a_lat + random.uniform(-0.008, 0.008)
        lon = a_lon + random.uniform(-0.008, 0.008)
        db = SERVICE_DISTRICTS[district]
        lat = round(float(np.clip(lat, db[0], db[1])), 6)
        lon = round(float(np.clip(lon, db[2], db[3])), 6)

        depth_ft = round(random.uniform(2.5, 5), 1)
        cost_per_ft = random.uniform(40, 150)
        replacement_cost = int(length_ft * cost_per_ft)

        # Criticality — PI is generally lower priority
        if diameter >= 12:
            criticality = random.choice(["Medium", "High"])
        else:
            criticality = random.choice(["Low", "Low", "Medium"])

        segments.append({
            "segment_id":       f"PI-{str(seg_id).zfill(4)}",
            "system_type":      "Pressurized Irrigation",
            "subdivision":      sub_name,
            "district":         district,
            "canal_source":     canal,
            "pipe_material":    material,
            "diameter_inches":  int(diameter),
            "length_ft":        length_ft,
            "depth_ft":         depth_ft,
            "install_year":     install_year,
            "asset_age_years":  age,
            "condition_score":  condition,
            "breaks_last_5yr":  breaks_5yr,
            "capacity_utilization_pct": capacity_pct,
            "operating_pressure_psi": round(random.uniform(80, 115), 0),
            "criticality_class": criticality,
            "estimated_replacement_cost_usd": replacement_cost,
            "last_inspection_date": (
                datetime(2026, 1, 1) - timedelta(days=random.randint(30, 1200))
            ).strftime("%Y-%m-%d"),
            "inspection_method": random.choice(
                ["Pressure Test", "Visual", "Flow Monitoring", "Valve Inspection"]),
            "lat": lat, "lon": lon,
        })
        seg_id += 1
    return pd.DataFrame(segments)


# ─── WORK ORDERS ────────────────────────────────────────────────────────────

def generate_work_orders(segments_df, n):
    """Generate work orders tied to actual segments."""
    wo_types = {
        "Wastewater": SEWER_WO_TYPES,
        "Geothermal": GEOTHERMAL_WO_TYPES,
        "Pressurized Irrigation": PI_WO_TYPES,
    }
    wos = []
    for i in range(n):
        seg = segments_df.sample(1).iloc[0]
        system = seg["system_type"]
        created = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 730))
        status = random.choice(["Open", "In Progress", "Completed", "Deferred"])
        completed_date = actual_hours = actual_cost = None
        if status == "Completed":
            completed_date = (created + timedelta(days=random.randint(1, 120))).strftime("%Y-%m-%d")
            actual_hours = round(random.uniform(2, 120), 1)
            actual_cost = random.randint(500, 250000)

        wos.append({
            "work_order_id":   f"WO-{str(i+1).zfill(5)}",
            "segment_id":      seg["segment_id"],
            "system_type":     system,
            "district":        seg["district"],
            "work_order_type": random.choice(wo_types[system]),
            "status":          status,
            "priority":        random.choice(["Emergency", "Urgent", "Routine", "Scheduled"]),
            "created_date":    created.strftime("%Y-%m-%d"),
            "completed_date":  completed_date,
            "crew_assigned":   f"Crew-{system[0]}{random.randint(1, 8)}",
            "estimated_hours": round(random.uniform(2, 100), 1),
            "actual_hours":    actual_hours,
            "estimated_cost_usd": random.randint(500, 200000),
            "actual_cost_usd": actual_cost,
            "source":          random.choice(["SCADA Alert", "Inspection", "Citizen Report",
                                               "Scheduled PM", "Emergency Call"]),
            "lat": seg["lat"] + random.uniform(-0.001, 0.001),
            "lon": seg["lon"] + random.uniform(-0.001, 0.001),
        })
    return pd.DataFrame(wos)


# ─── SERVICE REQUESTS ───────────────────────────────────────────────────────

def generate_service_requests(segments_df, n):
    sr_types = {
        "Wastewater": SEWER_SR_TYPES,
        "Geothermal": GEOTHERMAL_SR_TYPES,
        "Pressurized Irrigation": PI_SR_TYPES,
    }
    requests = []
    for i in range(n):
        if random.random() < 0.6:
            pool = segments_df[segments_df["condition_score"] < 50]
            seg = pool.sample(1).iloc[0] if len(pool) > 0 else segments_df.sample(1).iloc[0]
        else:
            seg = segments_df.sample(1).iloc[0]

        system = seg["system_type"]
        submitted = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 730))
        resolved_date = None
        if random.random() > 0.35:
            resolved_date = (submitted + timedelta(days=random.randint(1, 45))).strftime("%Y-%m-%d")

        requests.append({
            "request_id":      f"SR-{str(i+1).zfill(5)}",
            "segment_id":      seg["segment_id"],
            "system_type":     system,
            "district":        seg["district"],
            "request_type":    random.choice(sr_types[system]),
            "submitted_date":  submitted.strftime("%Y-%m-%d"),
            "resolved_date":   resolved_date,
            "resolution_status": random.choice(["Resolved", "Pending", "In Review"]),
            "severity":        random.choice(["Low", "Medium", "High", "Critical"]),
            "channel":         random.choice(["311 App", "Phone", "Web Form", "SCADA"]),
            "lat": seg["lat"] + random.uniform(-0.002, 0.002),
            "lon": seg["lon"] + random.uniform(-0.002, 0.002),
        })
    return pd.DataFrame(requests)


# ─── FACILITIES ─────────────────────────────────────────────────────────────

def generate_facilities():
    """Real Boise PW facilities — 2 WRFs, lift stations, geothermal wells, PI pump stations."""
    return pd.DataFrame([
        # Wastewater renewal facilities
        {"facility_id": "FAC-001", "facility_name": "Lander Street Water Renewal Facility",
         "system_type": "Wastewater", "facility_type": "Water Renewal Facility",
         "district": "Downtown", "capacity_mgd": 17.0, "avg_flow_mgd": 12.5,
         "built_year": 1950, "last_upgrade_year": 2024,
         "condition": "Poor — $265M rebuild underway (2023-2029)",
         "lat": 43.601, "lon": -116.224},
        {"facility_id": "FAC-002", "facility_name": "West Boise Water Renewal Facility",
         "system_type": "Wastewater", "facility_type": "Water Renewal Facility",
         "district": "West Boise", "capacity_mgd": 20.0, "avg_flow_mgd": 18.0,
         "built_year": 1978, "last_upgrade_year": 2022,
         "condition": "Fair",
         "lat": 43.610, "lon": -116.310},
        # Major lift stations (representative sample of the 28)
        {"facility_id": "FAC-003", "facility_name": "Southeast Lift Station",
         "system_type": "Wastewater", "facility_type": "Lift Station",
         "district": "Southeast", "capacity_mgd": 5.0, "avg_flow_mgd": 3.5,
         "built_year": 1988, "last_upgrade_year": 2020,
         "condition": "Fair", "lat": 43.555, "lon": -116.180},
        {"facility_id": "FAC-004", "facility_name": "Eagle Road Lift Station",
         "system_type": "Wastewater", "facility_type": "Lift Station",
         "district": "West Boise", "capacity_mgd": 3.0, "avg_flow_mgd": 2.1,
         "built_year": 2005, "last_upgrade_year": 2022,
         "condition": "Good", "lat": 43.625, "lon": -116.354},
        {"facility_id": "FAC-005", "facility_name": "Amity Lift Station",
         "system_type": "Wastewater", "facility_type": "Lift Station",
         "district": "Southwest", "capacity_mgd": 2.5, "avg_flow_mgd": 1.8,
         "built_year": 2000, "last_upgrade_year": 2019,
         "condition": "Fair", "lat": 43.553, "lon": -116.275},
        # Geothermal wells and facilities
        {"facility_id": "FAC-006", "facility_name": "Geothermal Production Well #1",
         "system_type": "Geothermal", "facility_type": "Production Well",
         "district": "North End", "capacity_mgd": 1.8, "avg_flow_mgd": 1.2,
         "built_year": 1983, "last_upgrade_year": 2018,
         "condition": "Fair — 400ft depth, 177°F",
         "lat": 43.625, "lon": -116.192},
        {"facility_id": "FAC-007", "facility_name": "Geothermal Production Well #2",
         "system_type": "Geothermal", "facility_type": "Production Well",
         "district": "North End", "capacity_mgd": 1.8, "avg_flow_mgd": 1.0,
         "built_year": 1983, "last_upgrade_year": 2020,
         "condition": "Fair — 600ft depth, 175°F",
         "lat": 43.626, "lon": -116.190},
        {"facility_id": "FAC-008", "facility_name": "Geothermal Production Well #3 (VA)",
         "system_type": "Geothermal", "facility_type": "Production Well",
         "district": "North End", "capacity_mgd": 1.8, "avg_flow_mgd": 0.8,
         "built_year": 1983, "last_upgrade_year": 2015,
         "condition": "Fair — 800ft depth, 161°F",
         "lat": 43.624, "lon": -116.188},
        {"facility_id": "FAC-009", "facility_name": "Julia Davis Park Injection Well",
         "system_type": "Geothermal", "facility_type": "Injection Well",
         "district": "Downtown", "capacity_mgd": 3.0, "avg_flow_mgd": 2.5,
         "built_year": 1999, "last_upgrade_year": 2021,
         "condition": "Good — 3,213ft depth, returns water to aquifer",
         "lat": 43.604, "lon": -116.195},
        # PI pump stations
        {"facility_id": "FAC-010", "facility_name": "West Boise PI Pump Station",
         "system_type": "Pressurized Irrigation", "facility_type": "PI Pump Station",
         "district": "West Boise", "capacity_mgd": 2.0, "avg_flow_mgd": 1.2,
         "built_year": 2001, "last_upgrade_year": 2020,
         "condition": "Good", "lat": 43.635, "lon": -116.320},
        {"facility_id": "FAC-011", "facility_name": "Southwest PI Diversion",
         "system_type": "Pressurized Irrigation", "facility_type": "PI Pump Station",
         "district": "Southwest", "capacity_mgd": 1.0, "avg_flow_mgd": 0.6,
         "built_year": 2007, "last_upgrade_year": 2022,
         "condition": "Good", "lat": 43.558, "lon": -116.280},
    ])


# ─── FLOW / MONITORING DATA ────────────────────────────────────────────────

def generate_monitoring_data(sewer_df, geo_df, pi_df):
    """Monthly monitoring data for instrumented pipes across all 3 systems."""
    records = []

    # Sewer: flow monitoring (~15% of pipes)
    sewer_sample = sewer_df.sample(min(int(len(sewer_df) * 0.15), len(sewer_df)), random_state=42)
    for _, seg in sewer_sample.iterrows():
        for month in range(1, 13):
            seasonal = 1.0 + 0.12 * np.cos((month - 1) * np.pi / 6)  # higher in winter (I&I)
            cap = seg["capacity_utilization_pct"]
            flow_pct = round(cap * seasonal * random.uniform(0.85, 1.15), 1)
            records.append({
                "monitor_id": f"MON-{seg['segment_id']}-2025-{str(month).zfill(2)}",
                "segment_id": seg["segment_id"], "system_type": "Wastewater",
                "year": 2025, "month": month,
                "avg_flow_pct": round(min(max(flow_pct, 0), 120), 1),
                "peak_flow_pct": round(min(flow_pct * random.uniform(1.2, 1.8), 150), 1),
                "measurement_type": "Flow",
            })

    # Geothermal: temperature monitoring (~30% of pipes)
    geo_sample = geo_df.sample(min(int(len(geo_df) * 0.30), len(geo_df)), random_state=42)
    for _, seg in geo_sample.iterrows():
        for month in range(1, 13):
            # Higher demand in winter → more heat extracted
            heating_seasonal = {1:1.3, 2:1.2, 3:1.0, 4:0.6, 5:0.3, 6:0.1,
                                7:0.05, 8:0.05, 9:0.2, 10:0.5, 11:0.9, 12:1.3}
            demand = heating_seasonal[month]
            temp = seg.get("supply_temp_f", 170) - demand * random.uniform(3, 8)
            records.append({
                "monitor_id": f"MON-{seg['segment_id']}-2025-{str(month).zfill(2)}",
                "segment_id": seg["segment_id"], "system_type": "Geothermal",
                "year": 2025, "month": month,
                "avg_flow_pct": round(demand * 80, 1),  # % of peak capacity
                "peak_flow_pct": round(min(demand * 100, 120), 1),
                "measurement_type": "Temperature",
            })

    # PI: flow monitoring (~20% of pipes), seasonal
    pi_sample = pi_df.sample(min(int(len(pi_df) * 0.20), len(pi_df)), random_state=42)
    for _, seg in pi_sample.iterrows():
        for month in range(1, 13):
            pi_seasonal = {1:0, 2:0, 3:0, 4:0.3, 5:0.7, 6:1.0, 7:1.2, 8:1.1,
                           9:0.7, 10:0.3, 11:0, 12:0}
            cap = seg["capacity_utilization_pct"]
            flow_pct = round(cap * pi_seasonal[month] * random.uniform(0.85, 1.15), 1)
            records.append({
                "monitor_id": f"MON-{seg['segment_id']}-2025-{str(month).zfill(2)}",
                "segment_id": seg["segment_id"], "system_type": "Pressurized Irrigation",
                "year": 2025, "month": month,
                "avg_flow_pct": round(max(flow_pct, 0), 1),
                "peak_flow_pct": round(max(flow_pct * random.uniform(1.2, 1.5), 0), 1),
                "measurement_type": "Flow",
            })

    return pd.DataFrame(records)


# ─── WEATHER EVENTS ─────────────────────────────────────────────────────────

def generate_weather(n=300):
    events = []
    for i in range(n):
        event_date = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 1095))
        event_type = random.choice(["Heavy Rain", "Snow", "Freeze-Thaw",
                                     "Ice Storm", "Thunderstorm", "Rapid Snowmelt"])
        is_frozen = event_type in ("Ice Storm", "Snow", "Freeze-Thaw")
        events.append({
            "weather_event_id":       f"WX-{str(i+1).zfill(4)}",
            "event_date":             event_date.strftime("%Y-%m-%d"),
            "event_type":             event_type,
            "duration_hours":         round(random.uniform(1, 72), 1),
            "precipitation_inches":   round(random.uniform(0.1, 4.5), 2)
                                       if event_type in ("Heavy Rain", "Snow", "Thunderstorm", "Rapid Snowmelt") else 0,
            "min_temp_f":             round(random.uniform(5, 28), 1)
                                       if is_frozen else round(random.uniform(32, 65), 1),
            "district_affected":      random.choice(DISTRICTS + ["All"]),
            "sewer_overflows_reported": random.randint(0, 5) if event_type in ("Heavy Rain", "Thunderstorm", "Rapid Snowmelt") else 0,
        })
    return pd.DataFrame(events)


# ─── CIP BUDGET ─────────────────────────────────────────────────────────────

FUNDING_SOURCES = ["Utility Rates", "Revenue Bonds", "SRF Loan", "EPA Grant", "General Fund"]

CIP_PROJECT_TYPES = {
    "Wastewater": ["Sewer Main Replacement", "I&I Reduction Program", "CIPP Rehabilitation",
                    "Trunk Sewer Upsizing", "Lift Station Upgrade", "WRF Capacity Improvement",
                    "Manhole Rehabilitation", "Force Main Replacement"],
    "Geothermal": ["Pipeline Replacement", "Well Rehabilitation", "Injection Well Maintenance",
                    "Building Connection Extension", "Insulation Upgrade", "BSU Campus Expansion"],
    "Pressurized Irrigation": ["PI Main Extension", "PI Pump Station Upgrade",
                                "PI Valve Replacement", "Canal Diversion Upgrade",
                                "Backflow Prevention Program"],
}

def generate_budget():
    records = []
    for year in [2022, 2023, 2024, 2025, 2026]:
        for district in DISTRICTS:
            total_budget = random.randint(1_200_000, 6_500_000)
            ww_pct  = round(random.uniform(0.60, 0.80), 2)  # sewer is the big system
            geo_pct = round(random.uniform(0.08, 0.20), 2)
            pi_pct  = round(max(1 - ww_pct - geo_pct, 0.03), 2)

            records.append({
                "fiscal_year":              year,
                "district":                 district,
                "total_cip_budget_usd":     total_budget,
                "wastewater_budget_usd":    int(total_budget * ww_pct),
                "geothermal_budget_usd":    int(total_budget * geo_pct),
                "pi_budget_usd":            int(total_budget * pi_pct),
                "funding_source":           random.choice(FUNDING_SOURCES),
                "spent_budget_usd":         random.randint(int(total_budget * 0.6),
                                                           int(total_budget * 1.05)),
                "budget_variance_pct":      None,
                "projects_planned":         random.randint(3, 15),
                "projects_completed":       None,
                "pipe_feet_replaced":       random.randint(1_000, 25_000),
                "citizen_satisfaction":     round(random.uniform(2.5, 4.8), 1),
            })
            rec = records[-1]
            rec["budget_variance_pct"] = round(
                (rec["spent_budget_usd"] - rec["total_cip_budget_usd"]) / rec["total_cip_budget_usd"] * 100, 1)
            rec["projects_completed"] = min(rec["projects_planned"],
                                            max(1, rec["projects_planned"] - random.randint(0, 3)))
    return pd.DataFrame(records)


def generate_cip_projects(all_segments_df, budget_df):
    """CIP project line items tied to worst-condition segments."""
    projects = []
    proj_id = 1
    for _, brow in budget_df.iterrows():
        year = brow["fiscal_year"]
        district = brow["district"]
        n_projects = brow["projects_planned"]
        remaining = brow["total_cip_budget_usd"]

        dist_pipes = all_segments_df[all_segments_df["district"] == district].sort_values("condition_score")

        for i in range(n_projects):
            if i < len(dist_pipes):
                pipe = dist_pipes.iloc[i]
                seg_id = pipe["segment_id"]
                system = pipe["system_type"]
            else:
                seg_id = None
                system = random.choices(
                    ["Wastewater", "Geothermal", "Pressurized Irrigation"],
                    weights=[0.75, 0.15, 0.10], k=1)[0]

            cost = random.randint(50_000, min(remaining, 1_500_000)) if remaining > 50_000 else 0
            remaining -= cost

            status = "Completed" if year < 2026 else random.choice(["In Design", "Under Construction", "Bid Phase", "Planned"])
            if year == 2025 and random.random() < 0.5:
                status = "Completed"

            projects.append({
                "project_id":         f"CIP-{str(proj_id).zfill(4)}",
                "fiscal_year":        year,
                "district":           district,
                "system_type":        system,
                "project_type":       random.choice(CIP_PROJECT_TYPES[system]),
                "segment_id":         seg_id,
                "estimated_cost_usd": cost,
                "actual_cost_usd":    int(cost * random.uniform(0.85, 1.25)) if status == "Completed" else None,
                "funding_source":     random.choice(FUNDING_SOURCES),
                "status":             status,
                "start_date":         f"{year}-{random.randint(1,12):02d}-01",
                "pipe_feet_addressed":random.randint(200, 5_000) if seg_id else 0,
            })
            proj_id += 1
    return pd.DataFrame(projects)


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATE ALL & SAVE
# ═══════════════════════════════════════════════════════════════════════════════

print("=" * 60)
print("BOISE PWIS — Generating Synthetic Data")
print("Systems: Wastewater | Geothermal | Pressurized Irrigation")
print("=" * 60)

print("\n1. Generating wastewater/sewer collection segments...")
sewer = generate_sewer_segments(4200)
sewer.to_csv(BASE_DIR / "sewer_segments.csv", index=False)
print(f"   -> {len(sewer)} sewer segments saved")
print(f"   Districts: {sewer['district'].value_counts().to_dict()}")
print(f"   Pipe classes: {sewer['pipe_class'].value_counts().to_dict()}")

print("\n2. Generating geothermal district heating segments...")
geo = generate_geothermal_segments(350)
geo.to_csv(BASE_DIR / "geothermal_segments.csv", index=False)
print(f"   -> {len(geo)} geothermal segments saved")
print(f"   Pipe roles: {geo['pipe_role'].value_counts().to_dict()}")

print("\n3. Generating pressurized irrigation segments...")
pi = generate_pi_segments(280)
pi.to_csv(BASE_DIR / "pi_segments.csv", index=False)
print(f"   -> {len(pi)} PI segments saved")
print(f"   Subdivisions: {pi['subdivision'].value_counts().to_dict()}")

# Combined segments for cross-system analysis
# Normalize columns across systems
sewer_norm = sewer.rename(columns={"corridor_name": "location_name"}).copy()
sewer_norm["location_name"] = sewer_norm["location_name"]
geo_norm = geo.rename(columns={"corridor_name": "location_name"}).copy()
pi_norm = pi.rename(columns={"subdivision": "location_name"}).copy()

# Common columns
common_cols = [
    "segment_id", "system_type", "location_name", "district",
    "pipe_material", "diameter_inches", "length_ft", "install_year",
    "asset_age_years", "condition_score", "breaks_last_5yr",
    "capacity_utilization_pct", "criticality_class",
    "estimated_replacement_cost_usd",
    "last_inspection_date", "inspection_method", "lat", "lon",
]
all_segments = pd.concat([
    sewer_norm[[c for c in common_cols if c in sewer_norm.columns]],
    geo_norm[[c for c in common_cols if c in geo_norm.columns]],
    pi_norm[[c for c in common_cols if c in pi_norm.columns]],
], ignore_index=True)
all_segments.to_csv(BASE_DIR / "all_segments.csv", index=False)
print(f"\n   -> {len(all_segments)} total segments (combined)")

print("\n4. Generating work orders...")
work_orders = generate_work_orders(all_segments, 5800)
work_orders.to_csv(BASE_DIR / "work_orders.csv", index=False)
print(f"   -> {len(work_orders)} work orders saved")

print("\n5. Generating service requests...")
requests = generate_service_requests(all_segments, 8700)
requests.to_csv(BASE_DIR / "service_requests.csv", index=False)
print(f"   -> {len(requests)} service requests saved")

print("\n6. Generating facilities...")
facilities = generate_facilities()
facilities.to_csv(BASE_DIR / "facilities.csv", index=False)
print(f"   -> {len(facilities)} facilities saved")

print("\n7. Generating monitoring data...")
monitoring = generate_monitoring_data(sewer, geo, pi)
monitoring.to_csv(BASE_DIR / "monitoring_data.csv", index=False)
print(f"   -> {len(monitoring)} monitoring records saved")

print("\n8. Generating weather events...")
weather = generate_weather(300)
weather.to_csv(BASE_DIR / "weather_events.csv", index=False)
print(f"   -> {len(weather)} weather events saved")

print("\n9. Generating CIP budget data...")
budget = generate_budget()
budget.to_csv(BASE_DIR / "budget_cip.csv", index=False)
print(f"   -> {len(budget)} budget records saved")

print("\n10. Generating CIP project line items...")
cip = generate_cip_projects(all_segments, budget)
cip.to_csv(BASE_DIR / "cip_projects.csv", index=False)
print(f"   -> {len(cip)} CIP projects saved")

print("\n" + "=" * 60)
print("✓ All datasets generated successfully.")
print(f"  Wastewater: {len(sewer)} segments | Geothermal: {len(geo)} | PI: {len(pi)}")
print(f"  Total: {len(all_segments)} segments across 3 systems")
print("=" * 60)
