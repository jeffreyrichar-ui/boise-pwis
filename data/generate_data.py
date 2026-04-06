"""
PWIS Synthetic Data Generator — Water / Sewer / Stormwater / Pressurized Irrigation
=====================================================================================
Generates realistic synthetic datasets for the Boise Public Works
Intelligence System (PWIS).

Grounded in real Boise infrastructure:
  - 900+ miles of water distribution pipe (83 active wells, 2 WTPs)
  - 1,000+ miles of sanitary sewer pipe (2 water renewal facilities)
  - Stormwater collection across 6 drainage basins
  - Pressurized irrigation system (non-potable Boise River water for
    landscape irrigation, adopted 1997 for new development)
  - Pipe materials: ductile iron, PVC, cast iron, HDPE, asbestos cement,
    concrete, vitrified clay, corrugated metal, PVC PR-SDR (irrigation)
  - Service districts: West Boise, East Bench, Downtown, North End,
    Southeast, Southwest

Sources:
  City of Boise Public Works — Water / Sewer / Stormwater / PI divisions
  Boise Open Data Portal (opendata.cityofboise.org)
  West Boise Water Renewal Facility capacity planning (2024)
  Lander Street Facility Improvement Plan ($265M, 2024-2029)
  Boise Pressure Irrigation Design Standards (cityofboise.org)
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
# Mapped to real sewer/water service boundaries
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
# Based on Boise geology: alluvial river soils downtown/north, bench gravels
# east, former agricultural clay/loam west and south.
# Scale: 0.0 (non-corrosive) to 1.0 (highly corrosive)
# Affects metallic pipe degradation (cast iron, ductile iron, galv. steel)
SOIL_CORROSIVITY = {
    "North End":   0.72,  # Alluvial, high moisture near river/canal system
    "Downtown":    0.78,  # Oldest soils, river-adjacent, disturbed fill
    "East Bench":  0.45,  # Bench gravels, well-drained, alkaline
    "Southeast":   0.55,  # Mixed clay/gravel, moderate moisture
    "Southwest":   0.60,  # Former ag land, irrigation-affected clay soils
    "West Boise":  0.50,  # Former farmland, mixed but less moisture
}

# Which materials are affected by soil corrosivity
METALLIC_MATERIALS = {"Cast Iron", "Ductile Iron", "Galvanized Steel",
                      "Corrugated Metal"}

# ─── PIPE MATERIALS BY SYSTEM AND ERA ────────────────────────────────────────
# Based on real Boise utility materials documented by City of Boise PW
WATER_MATERIALS = {
    "Cast Iron":       {"era": (1920, 1970), "pct": 0.15, "fail_rate": "high"},
    "Ductile Iron":    {"era": (1965, 2010), "pct": 0.35, "fail_rate": "medium"},
    "PVC":             {"era": (1975, 2026), "pct": 0.30, "fail_rate": "low"},
    "HDPE":            {"era": (2000, 2026), "pct": 0.10, "fail_rate": "low"},
    "Asbestos Cement": {"era": (1950, 1980), "pct": 0.08, "fail_rate": "high"},
    "Galvanized Steel":{"era": (1930, 1965), "pct": 0.02, "fail_rate": "high"},
}

SEWER_MATERIALS = {
    "Vitrified Clay":  {"era": (1920, 1975), "pct": 0.20, "fail_rate": "high"},
    "PVC":             {"era": (1975, 2026), "pct": 0.35, "fail_rate": "low"},
    "Concrete":        {"era": (1940, 1990), "pct": 0.20, "fail_rate": "medium"},
    "Ductile Iron":    {"era": (1970, 2010), "pct": 0.15, "fail_rate": "medium"},
    "HDPE":            {"era": (2005, 2026), "pct": 0.05, "fail_rate": "low"},
    "Orangeburg":      {"era": (1945, 1972), "pct": 0.05, "fail_rate": "high"},
}

STORMWATER_MATERIALS = {
    "Corrugated Metal":{"era": (1950, 1990), "pct": 0.25, "fail_rate": "high"},
    "Concrete":        {"era": (1920, 2010), "pct": 0.35, "fail_rate": "medium"},  # storm drains predate concrete sewer pipe
    "PVC":             {"era": (1985, 2026), "pct": 0.20, "fail_rate": "low"},
    "HDPE":            {"era": (2000, 2026), "pct": 0.10, "fail_rate": "low"},
    "Reinforced Concrete Box": {"era": (1960, 2020), "pct": 0.10, "fail_rate": "medium"},
}

# Pressurized Irrigation — Boise adopted PI requirement 1997 for new subdivisions.
# Per Boise Pressure Irrigation Design Standards:
#   - Mainline: PVC 1120, Class 200, SDR 21 (ASTM D2241), gasketed
#   - Lateral/sleeve: 160 PSI PR-SDR PVC pipe
#   - Some newer installs use HDPE for directional drills
# Oldest PI dates to early 1990s pilot; bulk of system is post-1997.
PI_MATERIALS = {
    "PVC PR-SDR":     {"era": (1993, 2026), "pct": 0.75, "fail_rate": "low"},
    "PVC C900":       {"era": (1997, 2026), "pct": 0.15, "fail_rate": "low"},
    "HDPE":           {"era": (2005, 2026), "pct": 0.10, "fail_rate": "low"},
}

# Pipe diameters by system (inches)
# Water: 4" service lines exist but distribution mains are 6-36"
WATER_DIAMETERS   = [4, 6, 8, 10, 12, 16, 20, 24, 30, 36]
SEWER_DIAMETERS   = [6, 8, 10, 12, 15, 18, 21, 24, 30, 36, 42, 48]
STORM_DIAMETERS   = [12, 15, 18, 24, 30, 36, 42, 48, 60, 72]
# PI mainlines are typically 4-12", per Boise design standards
PI_DIAMETERS      = [4, 6, 8, 10, 12]

# ─── REAL BOISE CORRIDOR CATALOG ─────────────────────────────────────────────
# Each corridor represents a real Boise street where pipe infrastructure
# runs.  Water, sewer, and stormwater are co-located along these corridors.
# Pressurized irrigation (PI) was adopted in 1997 — only present in newer
# subdivisions (primarily West Boise, newer Southwest, newer Southeast).
# (corridor_name, district, anchor_lat, anchor_lon, orientation,
#  has_water, has_sewer, has_storm, has_pi, corridor_age_era)

CORRIDOR_CATALOG = [
    # ── DOWNTOWN (oldest infrastructure, 1860s-1950s) ────────────────────────
    # Boise's original townsite platted 1863; centralized water 1890
    # No PI — pre-dates the program, fully built-out urban core
    ("Main St",          "Downtown",  43.615, -116.200, "EW",  True, True, True,  False, "old"),
    ("Capitol Blvd",     "Downtown",  43.611, -116.201, "NS",  True, True, True,  False, "old"),
    ("Front St",         "Downtown",  43.606, -116.205, "EW",  True, True, True,  False, "old"),
    ("Bannock St",       "Downtown",  43.613, -116.200, "EW",  True, True, True,  False, "old"),
    ("Idaho St",         "Downtown",  43.614, -116.202, "EW",  True, True, False, False, "old"),
    ("Myrtle St",        "Downtown",  43.607, -116.200, "EW",  True, True, True,  False, "old"),
    ("8th St",           "Downtown",  43.613, -116.197, "NS",  True, True, False, False, "old"),
    ("9th St",           "Downtown",  43.613, -116.199, "NS",  True, True, False, False, "old"),
    ("Jefferson St",     "Downtown",  43.616, -116.201, "EW",  True, True, True,  False, "old"),
    ("Fairview Ave",     "Downtown",  43.616, -116.200, "EW",  True, True, True,  False, "old"),
    ("Broadway Ave",     "Downtown",  43.612, -116.188, "NS",  True, True, True,  False, "mid"),
    ("I-184 Corridor",   "Downtown",  43.609, -116.214, "EW",  False,False,True,  False, "mid"),

    # ── NORTH END (1878-1950s, Boise's first residential neighborhood) ──────
    # Platted 1878; building boom 1891-1916; historic district
    # No PI — historic neighborhood, established before PI program
    ("Harrison Blvd",    "North End", 43.643, -116.200, "NS",  True, True, True,  False, "old"),
    ("Fort St",          "North End", 43.638, -116.205, "EW",  True, True, False, False, "old"),
    ("Hill Rd",          "North End", 43.660, -116.215, "EW",  True, True, True,  False, "old"),
    ("15th St",          "North End", 43.645, -116.208, "NS",  True, True, False, False, "old"),
    ("Bogus Basin Rd",   "North End", 43.665, -116.195, "DIAG",True, True, False, False, "old"),
    ("Eastman St",       "North End", 43.641, -116.203, "EW",  True, True, False, False, "old"),

    # ── EAST BENCH (1930s-1960s, post-WWII boom on the bench) ───────────────
    # Ridenbaugh Canal enabled development; major growth 1950s-1960s
    # No PI — developed before 1997 requirement
    ("Warm Springs Ave", "East Bench",43.608, -116.165, "EW",  True, True, True,  False, "old"),
    ("Federal Way",      "East Bench",43.597, -116.158, "EW",  True, True, True,  False, "mid"),
    ("Parkcenter Blvd",  "East Bench",43.597, -116.178, "NS",  True, True, True,  False, "mid"),
    ("Boise Ave",        "East Bench",43.600, -116.172, "EW",  True, True, True,  False, "mid"),
    ("Shaw Mountain Rd", "East Bench",43.605, -116.155, "DIAG",True, True, False, False, "mid"),

    # ── SOUTHEAST (1890s original S. Boise + 1960s-1970s expansion) ─────────
    # Original South Boise platted 1890; annexed 1913; bulk development 1970s
    # PI only in newest subdivisions near Gowen/Eisenman (post-2000 growth)
    ("Vista Ave",        "Southeast", 43.575, -116.207, "NS",  True, True, True,  False, "mid"),
    ("Broadway Ave",     "Southeast", 43.568, -116.188, "NS",  True, True, True,  False, "mid"),
    ("Overland Rd",      "Southeast", 43.588, -116.195, "EW",  True, True, True,  False, "mid"),
    ("Milwaukee St",     "Southeast", 43.565, -116.210, "NS",  True, True, True,  False, "mid"),
    ("Gowen Rd",         "Southeast", 43.543, -116.158, "EW",  True, True, True,  True,  "new"),
    ("Eisenman Rd",      "Southeast", 43.550, -116.170, "NS",  True, True, True,  True,  "new"),
    ("Victory Rd",       "Southeast", 43.570, -116.195, "EW",  True, True, True,  False, "mid"),

    # ── SOUTHWEST (1960s-1980s suburban expansion + newer infill) ────────────
    # Scattered development 1960s-1970s; ranch homes; moratorium in 1980s
    # PI in newer infill areas (Amity corridor, newer Five Mile subdivisions)
    ("Five Mile Rd",     "Southwest", 43.575, -116.295, "NS",  True, True, True,  False, "mid"),
    ("Maple Grove Rd",   "Southwest", 43.575, -116.276, "NS",  True, True, True,  False, "mid"),
    ("Cole Rd",          "Southwest", 43.572, -116.256, "NS",  True, True, True,  False, "mid"),
    ("Overland Rd",      "Southwest", 43.588, -116.270, "EW",  True, True, True,  False, "mid"),
    ("Orchard St",       "Southwest", 43.585, -116.232, "NS",  True, True, True,  False, "mid"),
    ("Curtis Rd",        "Southwest", 43.580, -116.222, "NS",  True, True, False, False, "mid"),
    ("Victory Rd",       "Southwest", 43.570, -116.280, "EW",  True, True, True,  False, "mid"),
    ("Amity Rd",         "Southwest", 43.553, -116.275, "EW",  True, True, True,  True,  "new"),

    # ── WEST BOISE (1970s-present, newest growth area) ───────────────────────
    # Primarily 1970s ranch homes; Ten Mile master-planned 2006; rapid growth
    # PI in all post-1997 subdivisions — the core of Boise's PI network
    ("Fairview Ave",     "West Boise",43.616, -116.295, "EW",  True, True, True,  True,  "new"),
    ("Ustick Rd",        "West Boise",43.633, -116.300, "EW",  True, True, True,  True,  "new"),
    ("McMillan Rd",      "West Boise",43.643, -116.310, "EW",  True, True, True,  True,  "new"),
    ("Chinden Blvd",     "West Boise",43.653, -116.310, "EW",  True, True, True,  True,  "new"),
    ("State St",         "West Boise",43.637, -116.280, "EW",  True, True, True,  True,  "new"),
    ("Eagle Rd",         "West Boise",43.625, -116.354, "NS",  True, True, True,  True,  "new"),
    ("Cloverdale Rd",    "West Boise",43.620, -116.336, "NS",  True, True, True,  True,  "new"),
    ("Ten Mile Rd",      "West Boise",43.615, -116.316, "NS",  True, True, True,  True,  "new"),
    ("Cole Rd",          "West Boise",43.625, -116.256, "NS",  True, True, True,  False, "new"),
    ("Franklin Rd",      "West Boise",43.607, -116.290, "EW",  True, True, True,  True,  "new"),
]

# Era-to-install-year ranges matching real Boise development history
ERA_INSTALL_RANGE = {
    "old": (1925, 1965),   # Downtown core + North End (pre-WWII through early postwar)
    "mid": (1955, 1990),   # East Bench, Southeast, Southwest (postwar suburban expansion)
    "new": (1985, 2022),   # West Boise, far Southeast (modern growth)
}


def _pick_material(materials_dict, install_year):
    """Pick a pipe material consistent with the install year.

    Strictly enforces era constraints — never assigns a material outside
    its manufacturing/installation era (e.g. no PVC before 1975).
    """
    eligible = [
        (m, d) for m, d in materials_dict.items()
        if d["era"][0] <= install_year <= d["era"][1]
    ]
    if not eligible:
        # Find the material whose era is closest to install_year
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
    """Compute condition score driven primarily by install date (age) and material,
    with soil corrosivity as a modifier for metallic pipes.

    The formula:
      condition = base_for_material - age_degradation - soil_penalty + noise
    where:
      - base_for_material: starting condition based on material durability
      - age_degradation:   age * material-specific decay rate (the dominant factor)
      - soil_penalty:      extra degradation for metallic pipes in corrosive soil
    """
    fail_rate = materials_dict.get(material, {}).get("fail_rate", "medium")

    # Material sets the baseline and degradation rate
    # High-fail materials start lower AND degrade faster per year
    base = {"high": 85, "medium": 90, "low": 95}[fail_rate]
    annual_decay = {"high": 0.90, "medium": 0.50, "low": 0.25}[fail_rate]

    # Age is the primary driver: older pipe = worse condition
    age_penalty = age * annual_decay

    # Soil corrosivity adds extra degradation for metallic pipes
    soil_penalty = 0.0
    if material in METALLIC_MATERIALS:
        soil_factor = SOIL_CORROSIVITY.get(district, 0.5)
        # Up to 15 additional points of degradation in highly corrosive soil
        soil_penalty = age * 0.20 * soil_factor

    condition = base - age_penalty - soil_penalty
    # Add some noise (±10 points) for real-world variability
    condition += np.random.normal(0, 8)
    return int(np.clip(condition, 5, 100))


# ─── 1. PIPE SEGMENTS ────────────────────────────────────────────────────────
def generate_pipe_segments(n=500):
    """Generate water, sewer, stormwater, and pressurized irrigation pipe segments
    along real Boise corridors."""
    segments = []
    seg_id = 1

    # Target mix: ~35% water, ~35% sewer, ~17% stormwater, ~13% pressurized irrigation
    # PI is smaller because it only exists in post-1997 subdivisions
    system_weights = {"Water": 0.35, "Sewer": 0.35, "Stormwater": 0.17,
                      "Pressurized Irrigation": 0.13}

    for _ in range(n):
        # Pick system type
        system = np.random.choice(list(system_weights.keys()),
                                   p=list(system_weights.values()))

        # Pick corridor that has this system
        valid = [c for c in CORRIDOR_CATALOG if
                 (system == "Water" and c[5]) or
                 (system == "Sewer" and c[6]) or
                 (system == "Stormwater" and c[7]) or
                 (system == "Pressurized Irrigation" and c[8])]
        corridor = random.choice(valid)
        name, district, a_lat, a_lon, orient, _, _, _, _, era = corridor

        # Install year from era
        yr_lo, yr_hi = ERA_INSTALL_RANGE[era]
        # PI system didn't exist before 1993 (pilot) / 1997 (mandate)
        if system == "Pressurized Irrigation":
            yr_lo = max(yr_lo, 1993)
        install_year = random.randint(yr_lo, yr_hi)
        age = 2026 - install_year

        # Material
        mat_dict = {"Water": WATER_MATERIALS, "Sewer": SEWER_MATERIALS,
                    "Stormwater": STORMWATER_MATERIALS,
                    "Pressurized Irrigation": PI_MATERIALS}[system]
        material = _pick_material(mat_dict, install_year)

        # Diameter
        diam_list = {"Water": WATER_DIAMETERS, "Sewer": SEWER_DIAMETERS,
                     "Stormwater": STORM_DIAMETERS,
                     "Pressurized Irrigation": PI_DIAMETERS}[system]
        diameter = random.choice(diam_list)

        # Length
        length_ft = random.randint(200, 2500)

        # Condition — driven by install date (age), material, and soil
        condition = _condition_from_material_age_soil(material, mat_dict, age, district)

        # Coordinates
        lat, lon = _coord_offset(a_lat, a_lon, orient, district)

        # Soil corrosivity for this district
        soil_corrosivity = SOIL_CORROSIVITY[district]

        # Depth — PI is shallow (3-5ft), sewer deepest (gravity flow)
        depth_ft = {"Water": round(random.uniform(3, 7), 1),
                    "Sewer": round(random.uniform(5, 25), 1),
                    "Stormwater": round(random.uniform(3, 15), 1),
                    "Pressurized Irrigation": round(random.uniform(2.5, 5), 1)}[system]

        # Estimated replacement cost — PI is cheapest (simpler pipe, no potable reqs)
        cost_per_ft = {
            "Water":      random.uniform(80, 350),
            "Sewer":      random.uniform(100, 500),
            "Stormwater": random.uniform(60, 250),
            "Pressurized Irrigation": random.uniform(40, 150),
        }[system]
        # Larger diameter = more expensive
        diam_mult = 1.0 + (diameter - 12) * 0.03
        replacement_cost = int(length_ft * cost_per_ft * max(diam_mult, 0.5))

        # Break / failure history — driven by age, material, and soil
        # The same factors that drive condition also drive breaks
        fail_rate = mat_dict.get(material, {}).get("fail_rate", "medium")
        break_base = {"high": 3.0, "medium": 1.0, "low": 0.2}[fail_rate]
        # Age is the primary multiplier
        age_mult = age / 50.0
        # Soil adds extra break risk for metallic pipes
        soil_mult = 1.0
        if material in METALLIC_MATERIALS:
            soil_mult = 1.0 + soil_corrosivity * 0.5  # up to 1.4x in worst soil
        breaks_5yr = max(0, int(np.random.poisson(break_base * age_mult * soil_mult)))
        # Very poor condition (< 20) should have at least 1 break
        if condition < 20 and breaks_5yr == 0:
            breaks_5yr = random.randint(1, 3)
        # Excellent condition (> 85) shouldn't have many breaks
        if condition > 85 and breaks_5yr > 2:
            breaks_5yr = random.randint(0, 1)

        # Capacity utilization
        # Sewer/storm: older = more stressed; PI: seasonal (high summer demand)
        if system in ("Sewer", "Stormwater"):
            capacity_pct = round(np.clip(np.random.normal(
                {"old": 78, "mid": 60, "new": 40}[era], 18), 5, 100), 1)
        elif system == "Pressurized Irrigation":
            # PI usage is highly seasonal: ~80-100% capacity in July-Aug,
            # near-zero in winter; annual average ~45-65%
            capacity_pct = round(np.clip(np.random.normal(55, 15), 10, 95), 1)
        else:
            capacity_pct = None

        # Criticality: based on diameter, location, and system
        # Realistic distribution: ~8% Critical, ~18% High, ~40% Medium, ~34% Low
        crit_roll = random.random()
        if crit_roll < 0.08:
            criticality = "Critical"
        elif crit_roll < 0.26:
            criticality = "High"
        elif crit_roll < 0.66:
            criticality = "Medium"
        else:
            criticality = "Low"
        # Large-diameter transmission/trunk mains bump up one tier
        bump = {"Low": "Medium", "Medium": "High", "High": "Critical", "Critical": "Critical"}
        if system == "Water" and diameter >= 20:
            criticality = bump[criticality]
        if system == "Sewer" and diameter >= 30:
            criticality = bump[criticality]
        if system == "Stormwater" and diameter >= 48:
            criticality = bump[criticality]
        # PI: 12" mainlines serve entire subdivisions
        if system == "Pressurized Irrigation" and diameter >= 12:
            criticality = bump[criticality]

        segments.append({
            "segment_id":               f"PIPE-{str(seg_id).zfill(4)}",
            "system_type":              system,
            "corridor_name":            name,
            "district":                 district,
            "pipe_material":            material,
            "diameter_inches":          diameter,
            "length_ft":                length_ft,
            "depth_ft":                 depth_ft,
            "install_year":             install_year,
            "asset_age_years":          age,
            "condition_score":          condition,
            "breaks_last_5yr":          breaks_5yr,
            "soil_corrosivity":         soil_corrosivity,
            "capacity_utilization_pct": capacity_pct,
            "criticality_class":        criticality,
            "estimated_replacement_cost_usd": replacement_cost,
            "last_inspection_date":     (
                datetime(2026, 1, 1) - timedelta(days=random.randint(30, 1200))
            ).strftime("%Y-%m-%d"),
            "inspection_method":        random.choice(
                {"Water": ["Acoustic Leak Detection", "Visual", "Pressure Test", "Ultrasonic"],
                 "Sewer": ["CCTV", "Smoke Test", "Manhole Inspection", "Flow Monitoring"],
                 "Stormwater": ["CCTV", "Visual", "Flow Monitoring", "Dye Test"],
                 "Pressurized Irrigation": ["Pressure Test", "Visual", "Flow Monitoring", "Valve Inspection"]}[system]),
            "lat":                      lat,
            "lon":                      lon,
        })
        seg_id += 1

    return pd.DataFrame(segments)


# ─── 2. WORK ORDERS ───────────────────────────────────────────────────────────
WO_TYPES_BY_SYSTEM = {
    "Water": ["Main Break Repair", "Valve Replacement", "Hydrant Repair",
              "Service Line Repair", "Leak Repair", "Main Flush"],
    "Sewer": ["Line Clearing", "Root Removal", "Manhole Repair",
              "CCTV Inspection", "Pipe Lining (CIPP)", "Bypass Pumping"],
    "Stormwater": ["Catch Basin Cleaning", "Pipe Repair", "Culvert Clearing",
                   "Detention Pond Maintenance", "Outfall Repair"],
    "Pressurized Irrigation": ["Valve Repair", "Lateral Leak Repair", "Main Leak Repair",
                               "Pressure Regulator Replacement", "Seasonal Startup",
                               "Seasonal Shutdown", "Backflow Preventer Inspection"],
}

def generate_work_orders(segments_df, n=600):
    wos = []
    for i in range(n):
        seg = segments_df.sample(1).iloc[0]
        system = seg["system_type"]
        created = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 730))
        status = random.choice(["Open", "In Progress", "Completed", "Deferred"])
        completed_date = None
        actual_hours = None
        actual_cost = None
        if status == "Completed":
            completed_date = (created + timedelta(days=random.randint(1, 120))).strftime("%Y-%m-%d")
            actual_hours = round(random.uniform(2, 120), 1)
            actual_cost = random.randint(500, 250000)

        wos.append({
            "work_order_id":       f"WO-{str(i+1).zfill(5)}",
            "segment_id":          seg["segment_id"],
            "system_type":         system,
            "district":            seg["district"],
            "work_order_type":     random.choice(WO_TYPES_BY_SYSTEM[system]),
            "status":              status,
            "priority":            random.choice(["Emergency", "Urgent", "Routine", "Scheduled"]),
            "created_date":        created.strftime("%Y-%m-%d"),
            "completed_date":      completed_date,
            "crew_assigned":       f"Crew-{system[0]}{random.randint(1, 6)}",
            "estimated_hours":     round(random.uniform(2, 100), 1),
            "actual_hours":        actual_hours,
            "estimated_cost_usd":  random.randint(500, 200000),
            "actual_cost_usd":     actual_cost,
            "source":              random.choice(["SCADA Alert", "Inspection", "Citizen Report",
                                                   "Scheduled PM", "Emergency Call"]),
            "lat":                 seg["lat"] + random.uniform(-0.001, 0.001),
            "lon":                 seg["lon"] + random.uniform(-0.001, 0.001),
        })
    return pd.DataFrame(wos)


# ─── 3. SERVICE REQUESTS (replaces complaints) ───────────────────────────────
REQUEST_TYPES = {
    "Water": ["Low Pressure", "Discolored Water", "Water Main Break",
              "Leak Report", "Hydrant Issue", "No Water"],
    "Sewer": ["Sewer Backup", "Manhole Overflow", "Odor Complaint",
              "Slow Drain", "Root Intrusion Report"],
    "Stormwater": ["Street Flooding", "Clogged Drain", "Erosion Report",
                   "Standing Water", "Culvert Blockage"],
    "Pressurized Irrigation": ["No Irrigation Pressure", "PI Leak Report",
                                "Sprinkler Supply Issue", "Scheduled Watering Conflict",
                                "Backflow Device Issue", "Brown Lawn / No Flow"],
}

def generate_service_requests(segments_df, n=900):
    requests = []
    for i in range(n):
        # Weight toward worse-condition segments
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
            "request_id":          f"SR-{str(i+1).zfill(5)}",
            "segment_id":          seg["segment_id"],
            "system_type":         system,
            "district":            seg["district"],
            "request_type":        random.choice(REQUEST_TYPES[system]),
            "submitted_date":      submitted.strftime("%Y-%m-%d"),
            "resolved_date":       resolved_date,
            "resolution_status":   random.choice(["Resolved", "Pending", "In Review"]),
            "severity":            random.choice(["Low", "Medium", "High", "Critical"]),
            "channel":             random.choice(["311 App", "Phone", "Web Form", "SCADA"]),
            "lat":                 seg["lat"] + random.uniform(-0.002, 0.002),
            "lon":                 seg["lon"] + random.uniform(-0.002, 0.002),
        })
    return pd.DataFrame(requests)


# ─── 4. TREATMENT FACILITIES ─────────────────────────────────────────────────
def generate_facilities():
    """Real Boise water/sewer treatment facilities with actual capacity data."""
    return pd.DataFrame([
        {"facility_id": "FAC-001", "facility_name": "Marden Water Treatment Plant",
         "facility_type": "Water Treatment", "district": "North End",
         "capacity_mgd": 36.0, "avg_flow_mgd": 22.5, "built_year": 1962,
         "last_upgrade_year": 2018,
         "condition": "Fair", "lat": 43.648, "lon": -116.198},
        {"facility_id": "FAC-002", "facility_name": "Columbia Water Treatment Plant",
         "facility_type": "Water Treatment", "district": "East Bench",
         "capacity_mgd": 6.0, "avg_flow_mgd": 4.2, "built_year": 2005,
         "last_upgrade_year": 2024,
         "condition": "Good", "lat": 43.595, "lon": -116.148},
        {"facility_id": "FAC-003", "facility_name": "Lander Street Water Renewal Facility",
         "facility_type": "Wastewater Treatment", "district": "Downtown",
         "capacity_mgd": 15.0, "avg_flow_mgd": 12.5, "built_year": 1950,
         "last_upgrade_year": 2024,
         "condition": "Poor", "lat": 43.601, "lon": -116.224},
        {"facility_id": "FAC-004", "facility_name": "West Boise Water Renewal Facility",
         "facility_type": "Wastewater Treatment", "district": "West Boise",
         "capacity_mgd": 40.0, "avg_flow_mgd": 18.0, "built_year": 1978,
         "last_upgrade_year": 2022,
         "condition": "Fair", "lat": 43.610, "lon": -116.310},
        {"facility_id": "FAC-005", "facility_name": "Southeast Pump Station",
         "facility_type": "Pump Station", "district": "Southeast",
         "capacity_mgd": 8.0, "avg_flow_mgd": 5.5, "built_year": 1988,
         "last_upgrade_year": 2020,
         "condition": "Fair", "lat": 43.555, "lon": -116.180},
        {"facility_id": "FAC-006", "facility_name": "North End Pressure Zone Station",
         "facility_type": "Pump Station", "district": "North End",
         "capacity_mgd": 4.0, "avg_flow_mgd": 2.8, "built_year": 1975,
         "last_upgrade_year": 2019,
         "condition": "Fair", "lat": 43.658, "lon": -116.205},
        # Pressurized Irrigation — Boise diverts from the Boise River via
        # the New York Canal and city canals into PI pump stations
        {"facility_id": "FAC-007", "facility_name": "West Boise PI Pump Station",
         "facility_type": "PI Pump Station", "district": "West Boise",
         "capacity_mgd": 8.0, "avg_flow_mgd": 5.0, "built_year": 2001,
         "last_upgrade_year": 2020,
         "condition": "Good", "lat": 43.620, "lon": -116.310},
        {"facility_id": "FAC-008", "facility_name": "Southwest PI Diversion",
         "facility_type": "PI Pump Station", "district": "Southwest",
         "capacity_mgd": 3.5, "avg_flow_mgd": 2.0, "built_year": 2005,
         "last_upgrade_year": 2022,
         "condition": "Good", "lat": 43.560, "lon": -116.275},
    ])


# ─── 5. FLOW MONITORING ──────────────────────────────────────────────────────
def generate_flow_data(segments_df):
    """Monthly flow/pressure monitoring for a subset of instrumented pipes.
    Includes sewer, stormwater, and pressurized irrigation (PI has strong
    seasonal patterns — high summer, zero winter)."""
    # Scale instrumented count with dataset size (~5% of non-water pipes)
    monitored_systems = segments_df[
        segments_df["system_type"].isin(["Sewer", "Stormwater", "Pressurized Irrigation"])
    ]
    sample_n = min(int(len(monitored_systems) * 0.15), len(monitored_systems))
    instrumented = monitored_systems.sample(sample_n, random_state=42)

    records = []
    for _, seg in instrumented.iterrows():
        for month in range(1, 13):
            # Sewer flow is higher in winter (less evaporation, more infiltration)
            # Stormwater peaks in spring (snowmelt) and fall (rain)
            # PI is highly seasonal: off Nov-Mar, ramps up Apr-May, peaks Jun-Sep
            if seg["system_type"] == "Sewer":
                seasonal = 1.0 + 0.12 * np.cos((month - 1) * np.pi / 6)
            elif seg["system_type"] == "Pressurized Irrigation":
                # PI season: Apr 15 - Oct 15 in Boise; peak Jun-Aug
                pi_seasonal = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.3, 5: 0.7,
                               6: 1.0, 7: 1.2, 8: 1.1, 9: 0.7, 10: 0.3,
                               11: 0.0, 12: 0.0}
                seasonal = pi_seasonal[month]
            else:  # Stormwater
                seasonal = 1.0 + 0.3 * (1 if month in (3,4,5,10,11) else 0)
            cap = seg["capacity_utilization_pct"] or 50
            flow_pct = round(cap * seasonal * random.uniform(0.85, 1.15), 1)
            records.append({
                "monitor_id":   f"MON-{seg['segment_id']}-2025-{str(month).zfill(2)}",
                "segment_id":   seg["segment_id"],
                "system_type":  seg["system_type"],
                "year":         2025,
                "month":        month,
                "avg_flow_pct": round(min(max(flow_pct, 0), 120), 1),
                "peak_flow_pct":round(min(max(flow_pct * random.uniform(1.2, 1.8), 0), 200), 1),
                "inflow_infiltration_flag": flow_pct > 85 if seg["system_type"] != "Pressurized Irrigation" else False,
            })
    return pd.DataFrame(records)


# ─── 6. WEATHER EVENTS ────────────────────────────────────────────────────────
def generate_weather(n=150):
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
            "estimated_damage_usd":   random.randint(0, 500000),
            "sewer_overflows_reported": random.randint(0, 12) if event_type in ("Heavy Rain", "Thunderstorm", "Rapid Snowmelt") else 0,
            "water_main_breaks":      random.randint(0, 5) if is_frozen else 0,
        })
    return pd.DataFrame(events)


# ─── 7. CIP BUDGET ───────────────────────────────────────────────────────────
FUNDING_SOURCES = ["Utility Rates", "Revenue Bonds", "SRF Loan", "EPA Grant", "General Fund"]
CIP_PROJECT_TYPES = {
    "Water": ["Water Main Replacement", "Transmission Main Upgrade", "Pressure Zone Expansion",
              "Well Rehabilitation", "Meter Replacement Program", "Lead Service Line Replacement"],
    "Sewer": ["Sewer Main Replacement", "I&I Reduction Program", "CIPP Rehabilitation",
              "Trunk Sewer Upsizing", "Lift Station Upgrade", "WRF Capacity Improvement"],
    "Stormwater": ["Storm Drain Replacement", "Detention Basin Construction",
                   "Outfall Rehabilitation", "Green Infrastructure Retrofit",
                   "Culvert Replacement"],
    "Pressurized Irrigation": ["PI Main Extension", "PI Pump Station Upgrade",
                                "PI Valve Replacement Program", "Canal Diversion Upgrade",
                                "Backflow Prevention Program"],
}

def generate_budget():
    records = []
    for year in [2022, 2023, 2024, 2025, 2026]:
        for district in DISTRICTS:
            # Water, sewer, stormwater, and PI budget split
            total_budget = random.randint(1_200_000, 6_500_000)
            water_pct  = round(random.uniform(0.28, 0.40), 2)
            sewer_pct  = round(random.uniform(0.28, 0.40), 2)
            pi_pct     = round(random.uniform(0.05, 0.12), 2)
            storm_pct  = round(1 - water_pct - sewer_pct - pi_pct, 2)
            # Ensure no negative
            if storm_pct < 0.05:
                storm_pct = 0.05
                pi_pct = round(1 - water_pct - sewer_pct - storm_pct, 2)

            records.append({
                "fiscal_year":              year,
                "district":                 district,
                "total_cip_budget_usd":     total_budget,
                "water_budget_usd":         int(total_budget * water_pct),
                "sewer_budget_usd":         int(total_budget * sewer_pct),
                "stormwater_budget_usd":    int(total_budget * storm_pct),
                "pi_budget_usd":            int(total_budget * pi_pct),
                "funding_source":           random.choice(FUNDING_SOURCES),
                "spent_budget_usd":         random.randint(int(total_budget * 0.6),
                                                           int(total_budget * 1.05)),
                "budget_variance_pct":      None,  # filled below
                "projects_planned":         random.randint(3, 15),
                "projects_completed":       None,  # filled below
                "pipe_feet_replaced":       random.randint(1_000, 25_000),
                "citizen_satisfaction":     round(random.uniform(2.5, 4.8), 1),
            })
            # Calculate derived fields
            rec = records[-1]
            rec["budget_variance_pct"] = round(
                (rec["spent_budget_usd"] - rec["total_cip_budget_usd"]) / rec["total_cip_budget_usd"] * 100, 1)
            rec["projects_completed"] = min(rec["projects_planned"],
                                            max(1, rec["projects_planned"] - random.randint(0, 3)))

    return pd.DataFrame(records)


def generate_cip_projects(segments_df, budget_df):
    """Generate individual CIP project line items tied to pipe segments and budgets."""
    projects = []
    proj_id = 1
    for _, budget_row in budget_df.iterrows():
        year = budget_row["fiscal_year"]
        district = budget_row["district"]
        n_projects = budget_row["projects_planned"]
        remaining_budget = budget_row["total_cip_budget_usd"]

        # Pick worst-condition segments in this district
        district_pipes = segments_df[segments_df["district"] == district].sort_values("condition_score")

        for i in range(n_projects):
            if i < len(district_pipes):
                pipe = district_pipes.iloc[i]
                seg_id = pipe["segment_id"]
                system = pipe["system_type"]
            else:
                seg_id = None
                system = random.choice(["Water", "Sewer", "Stormwater", "Pressurized Irrigation"])

            project_cost = random.randint(50_000, min(remaining_budget, 1_500_000)) if remaining_budget > 50_000 else 0
            remaining_budget -= project_cost

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
                "estimated_cost_usd": project_cost,
                "actual_cost_usd":    int(project_cost * random.uniform(0.85, 1.25)) if status == "Completed" else None,
                "funding_source":     random.choice(FUNDING_SOURCES),
                "status":             status,
                "start_date":         f"{year}-{random.randint(1,12):02d}-01",
                "pipe_feet_addressed":random.randint(200, 5_000) if seg_id else 0,
            })
            proj_id += 1

    return pd.DataFrame(projects)


# ─── GENERATE ALL & SAVE ──────────────────────────────────────────────────────
print("Generating pipe segments (water / sewer / stormwater / pressurized irrigation)...")
pipes = generate_pipe_segments(4847)
pipes.to_csv(BASE_DIR / "pipe_segments.csv", index=False)
print(f"  -> {len(pipes)} pipe segments saved")
print(f"  Systems: {pipes['system_type'].value_counts().to_dict()}")
print(f"  Districts: {pipes['district'].value_counts().to_dict()}")

print("Generating work orders...")
work_orders = generate_work_orders(pipes, 5800)
work_orders.to_csv(BASE_DIR / "work_orders.csv", index=False)
print(f"  -> {len(work_orders)} work orders saved")

print("Generating service requests...")
requests = generate_service_requests(pipes, 8700)
requests.to_csv(BASE_DIR / "service_requests.csv", index=False)
print(f"  -> {len(requests)} service requests saved")

print("Generating treatment facilities...")
facilities = generate_facilities()
facilities.to_csv(BASE_DIR / "facilities.csv", index=False)
print(f"  -> {len(facilities)} facilities saved")

print("Generating flow monitoring data...")
flow = generate_flow_data(pipes)
flow.to_csv(BASE_DIR / "flow_monitoring.csv", index=False)
print(f"  -> {len(flow)} flow records saved")

print("Generating weather events...")
weather = generate_weather(300)
weather.to_csv(BASE_DIR / "weather_events.csv", index=False)
print(f"  -> {len(weather)} weather events saved")

print("Generating CIP budget data...")
budget = generate_budget()
budget.to_csv(BASE_DIR / "budget_cip.csv", index=False)
print(f"  -> {len(budget)} budget records saved")

print("Generating CIP project line items...")
cip_projects = generate_cip_projects(pipes, budget)
cip_projects.to_csv(BASE_DIR / "cip_projects.csv", index=False)
print(f"  -> {len(cip_projects)} CIP projects saved")
print(f"  Funding sources: {cip_projects['funding_source'].value_counts().to_dict()}")
print(f"  Statuses: {cip_projects['status'].value_counts().to_dict()}")

print("\n✓ All datasets generated successfully.")
print("\nSample — Pipe Segments:")
print(pipes[["segment_id","system_type","corridor_name","district",
             "pipe_material","diameter_inches","condition_score",
             "breaks_last_5yr","estimated_replacement_cost_usd"]].head(10).to_string(index=False))

