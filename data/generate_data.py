"""
PWIS Synthetic Data Generator — Water / Sewer / Stormwater
============================================================
Generates realistic synthetic datasets for the Boise Public Works
Water & Sewer Intelligence System (WSIS).

Grounded in real Boise infrastructure:
  - 900+ miles of water distribution pipe (83 active wells, 2 WTPs)
  - 1,000+ miles of sanitary sewer pipe (2 water renewal facilities)
  - Stormwater collection across 6 drainage basins
  - Pipe materials: ductile iron, PVC, cast iron, HDPE, asbestos cement,
    concrete, vitrified clay, corrugated metal
  - Service districts: West Boise, Bench, Northwest, Downtown/Central,
    North End, Southeast

Sources:
  City of Boise Public Works — Water / Sewer / Stormwater divisions
  Boise Open Data Portal (opendata.cityofboise.org)
  West Boise Water Renewal Facility capacity planning (2024)
  Lander Street Facility Improvement Plan ($265M, 2024-2029)
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
    "Concrete":        {"era": (1940, 2010), "pct": 0.35, "fail_rate": "medium"},
    "PVC":             {"era": (1985, 2026), "pct": 0.20, "fail_rate": "low"},
    "HDPE":            {"era": (2000, 2026), "pct": 0.10, "fail_rate": "low"},
    "Reinforced Concrete Box": {"era": (1960, 2020), "pct": 0.10, "fail_rate": "medium"},
}

# Pipe diameters by system (inches)
WATER_DIAMETERS   = [4, 6, 8, 10, 12, 16, 20, 24, 30, 36]
SEWER_DIAMETERS   = [6, 8, 10, 12, 15, 18, 21, 24, 30, 36, 42, 48]
STORM_DIAMETERS   = [12, 15, 18, 24, 30, 36, 42, 48, 60, 72]

# ─── REAL BOISE CORRIDOR CATALOG ─────────────────────────────────────────────
# Each corridor represents a real Boise street where pipe infrastructure
# runs.  Water, sewer, and stormwater are co-located along these corridors.
# (corridor_name, district, anchor_lat, anchor_lon, orientation,
#  has_water, has_sewer, has_storm, corridor_age_era)

CORRIDOR_CATALOG = [
    # ── DOWNTOWN (oldest infrastructure, 1920s-1960s) ────────────────────────
    ("Main St",          "Downtown",  43.615, -116.200, "EW",  True, True, True,  "old"),
    ("Capitol Blvd",     "Downtown",  43.611, -116.201, "NS",  True, True, True,  "old"),
    ("Front St",         "Downtown",  43.606, -116.205, "EW",  True, True, True,  "old"),
    ("Bannock St",       "Downtown",  43.613, -116.200, "EW",  True, True, True,  "old"),
    ("Idaho St",         "Downtown",  43.614, -116.202, "EW",  True, True, False, "old"),
    ("Myrtle St",        "Downtown",  43.607, -116.200, "EW",  True, True, True,  "old"),
    ("8th St",           "Downtown",  43.613, -116.197, "NS",  True, True, False, "old"),
    ("9th St",           "Downtown",  43.613, -116.199, "NS",  True, True, False, "old"),
    ("Jefferson St",     "Downtown",  43.616, -116.201, "EW",  True, True, True,  "old"),
    ("Fairview Ave",     "Downtown",  43.616, -116.200, "EW",  True, True, True,  "mid"),
    ("Broadway Ave",     "Downtown",  43.612, -116.188, "NS",  True, True, True,  "mid"),
    ("I-184 Corridor",   "Downtown",  43.609, -116.214, "EW",  False,False,True,  "mid"),

    # ── NORTH END (historic, mix of old and mid-era) ─────────────────────────
    ("Harrison Blvd",    "North End", 43.643, -116.200, "NS",  True, True, True,  "old"),
    ("Fort St",          "North End", 43.638, -116.205, "EW",  True, True, False, "old"),
    ("Hill Rd",          "North End", 43.660, -116.215, "EW",  True, True, True,  "old"),
    ("15th St",          "North End", 43.645, -116.208, "NS",  True, True, False, "old"),
    ("Bogus Basin Rd",   "North End", 43.665, -116.195, "DIAG",True, True, False, "mid"),
    ("Eastman St",       "North End", 43.641, -116.203, "EW",  True, True, False, "old"),

    # ── EAST BENCH (mid-era, bench above river) ──────────────────────────────
    ("Warm Springs Ave", "East Bench",43.608, -116.165, "EW",  True, True, True,  "old"),
    ("Federal Way",      "East Bench",43.597, -116.158, "EW",  True, True, True,  "mid"),
    ("Parkcenter Blvd",  "East Bench",43.597, -116.178, "NS",  True, True, True,  "mid"),
    ("Boise Ave",        "East Bench",43.600, -116.172, "EW",  True, True, True,  "mid"),
    ("Shaw Mountain Rd", "East Bench",43.605, -116.155, "DIAG",True, True, False, "mid"),

    # ── SOUTHEAST (Vista/Broadway corridor, mixed era) ───────────────────────
    ("Vista Ave",        "Southeast", 43.575, -116.207, "NS",  True, True, True,  "mid"),
    ("Broadway Ave",     "Southeast", 43.568, -116.188, "NS",  True, True, True,  "mid"),
    ("Overland Rd",      "Southeast", 43.588, -116.195, "EW",  True, True, True,  "mid"),
    ("Milwaukee St",     "Southeast", 43.565, -116.210, "NS",  True, True, True,  "mid"),
    ("Gowen Rd",         "Southeast", 43.543, -116.158, "EW",  True, True, True,  "new"),
    ("Eisenman Rd",      "Southeast", 43.550, -116.170, "NS",  True, True, True,  "new"),
    ("Victory Rd",       "Southeast", 43.570, -116.195, "EW",  True, True, True,  "mid"),

    # ── SOUTHWEST (suburban, mostly mid-to-new) ──────────────────────────────
    ("Five Mile Rd",     "Southwest", 43.575, -116.295, "NS",  True, True, True,  "mid"),
    ("Maple Grove Rd",   "Southwest", 43.575, -116.276, "NS",  True, True, True,  "mid"),
    ("Cole Rd",          "Southwest", 43.572, -116.256, "NS",  True, True, True,  "mid"),
    ("Overland Rd",      "Southwest", 43.588, -116.270, "EW",  True, True, True,  "mid"),
    ("Orchard St",       "Southwest", 43.585, -116.232, "NS",  True, True, True,  "mid"),
    ("Curtis Rd",        "Southwest", 43.580, -116.222, "NS",  True, True, False, "mid"),
    ("Victory Rd",       "Southwest", 43.570, -116.280, "EW",  True, True, True,  "mid"),
    ("Amity Rd",         "Southwest", 43.553, -116.275, "EW",  True, True, True,  "new"),

    # ── WEST BOISE (newest growth, mostly new) ───────────────────────────────
    ("Fairview Ave",     "West Boise",43.616, -116.295, "EW",  True, True, True,  "mid"),
    ("Ustick Rd",        "West Boise",43.633, -116.300, "EW",  True, True, True,  "mid"),
    ("McMillan Rd",      "West Boise",43.643, -116.310, "EW",  True, True, True,  "new"),
    ("Chinden Blvd",     "West Boise",43.653, -116.310, "EW",  True, True, True,  "mid"),
    ("State St",         "West Boise",43.637, -116.280, "EW",  True, True, True,  "mid"),
    ("Eagle Rd",         "West Boise",43.625, -116.354, "NS",  True, True, True,  "new"),
    ("Cloverdale Rd",    "West Boise",43.620, -116.336, "NS",  True, True, True,  "new"),
    ("Ten Mile Rd",      "West Boise",43.615, -116.316, "NS",  True, True, True,  "new"),
    ("Cole Rd",          "West Boise",43.625, -116.256, "NS",  True, True, True,  "mid"),
    ("Franklin Rd",      "West Boise",43.607, -116.290, "EW",  True, True, True,  "mid"),
]

ERA_INSTALL_RANGE = {
    "old": (1925, 1970),
    "mid": (1965, 2000),
    "new": (1995, 2022),
}


def _pick_material(materials_dict, install_year):
    """Pick a pipe material consistent with the install year."""
    eligible = [
        (m, d) for m, d in materials_dict.items()
        if d["era"][0] <= install_year <= d["era"][1]
    ]
    if not eligible:
        eligible = list(materials_dict.items())
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


def _condition_from_material_and_age(material, materials_dict, age):
    fail_rate = materials_dict.get(material, {}).get("fail_rate", "medium")
    base = {"high": 38, "medium": 55, "low": 72}[fail_rate]
    age_penalty = age * {"high": 0.6, "medium": 0.35, "low": 0.15}[fail_rate]
    ci = int(np.clip(np.random.normal(base - age_penalty * 0.3, 15), 5, 100))
    return ci


# ─── 1. PIPE SEGMENTS ────────────────────────────────────────────────────────
def generate_pipe_segments(n=500):
    """Generate water, sewer, and stormwater pipe segments along real Boise corridors."""
    segments = []
    seg_id = 1

    # Target mix: ~40% water, ~40% sewer, ~20% stormwater
    system_weights = {"Water": 0.40, "Sewer": 0.40, "Stormwater": 0.20}

    for _ in range(n):
        # Pick system type
        system = np.random.choice(list(system_weights.keys()),
                                   p=list(system_weights.values()))

        # Pick corridor that has this system
        valid = [c for c in CORRIDOR_CATALOG if
                 (system == "Water" and c[5]) or
                 (system == "Sewer" and c[6]) or
                 (system == "Stormwater" and c[7])]
        corridor = random.choice(valid)
        name, district, a_lat, a_lon, orient, _, _, _, era = corridor

        # Install year from era
        yr_lo, yr_hi = ERA_INSTALL_RANGE[era]
        install_year = random.randint(yr_lo, yr_hi)
        age = 2026 - install_year

        # Material
        mat_dict = {"Water": WATER_MATERIALS, "Sewer": SEWER_MATERIALS,
                    "Stormwater": STORMWATER_MATERIALS}[system]
        material = _pick_material(mat_dict, install_year)

        # Diameter
        diam_list = {"Water": WATER_DIAMETERS, "Sewer": SEWER_DIAMETERS,
                     "Stormwater": STORM_DIAMETERS}[system]
        diameter = random.choice(diam_list)

        # Length
        length_ft = random.randint(200, 2500)

        # Condition
        condition = _condition_from_material_and_age(material, mat_dict, age)

        # Coordinates
        lat, lon = _coord_offset(a_lat, a_lon, orient, district)

        # Depth
        depth_ft = {"Water": round(random.uniform(3, 7), 1),
                    "Sewer": round(random.uniform(5, 25), 1),
                    "Stormwater": round(random.uniform(3, 15), 1)}[system]

        # Estimated replacement cost
        cost_per_ft = {
            "Water":      random.uniform(80, 350),
            "Sewer":      random.uniform(100, 500),
            "Stormwater": random.uniform(60, 250),
        }[system]
        # Larger diameter = more expensive
        diam_mult = 1.0 + (diameter - 12) * 0.03
        replacement_cost = int(length_ft * cost_per_ft * max(diam_mult, 0.5))

        # Break / failure history (higher for old high-fail materials)
        fail_rate = mat_dict.get(material, {}).get("fail_rate", "medium")
        break_base = {"high": 3.5, "medium": 1.2, "low": 0.3}[fail_rate]
        breaks_5yr = max(0, int(np.random.poisson(break_base * (age / 50))))

        # Capacity utilization (sewer/storm only)
        if system in ("Sewer", "Stormwater"):
            capacity_pct = round(np.clip(np.random.normal(
                {"old": 78, "mid": 60, "new": 40}[era], 18), 5, 100), 1)
        else:
            capacity_pct = None

        # Criticality: proximity to hospital, school, major intersection
        criticality = random.choice(["Critical", "High", "Medium", "Low"])
        if system == "Water" and diameter >= 16:
            criticality = random.choice(["Critical", "Critical", "High"])
        if system == "Sewer" and diameter >= 24:
            criticality = random.choice(["Critical", "High", "High"])

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
            "capacity_utilization_pct": capacity_pct,
            "criticality_class":        criticality,
            "estimated_replacement_cost_usd": replacement_cost,
            "last_inspection_date":     (
                datetime(2026, 1, 1) - timedelta(days=random.randint(30, 1200))
            ).strftime("%Y-%m-%d"),
            "inspection_method":        random.choice(
                {"Water": ["Acoustic Leak Detection", "Visual", "Pressure Test", "Ultrasonic"],
                 "Sewer": ["CCTV", "Smoke Test", "Manhole Inspection", "Flow Monitoring"],
                 "Stormwater": ["CCTV", "Visual", "Flow Monitoring", "Dye Test"]}[system]),
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
    ])


# ─── 5. FLOW MONITORING ──────────────────────────────────────────────────────
def generate_flow_data(segments_df):
    """Monthly flow/pressure monitoring for a subset of instrumented pipes."""
    instrumented = segments_df[
        segments_df["system_type"].isin(["Sewer", "Stormwater"])
    ].sample(min(80, len(segments_df)), random_state=42)

    records = []
    for _, seg in instrumented.iterrows():
        for month in range(1, 13):
            # Sewer flow is higher in winter (less evaporation, more infiltration)
            # Stormwater peaks in spring (snowmelt) and fall (rain)
            if seg["system_type"] == "Sewer":
                seasonal = 1.0 + 0.12 * np.cos((month - 1) * np.pi / 6)
            else:
                seasonal = 1.0 + 0.3 * (1 if month in (3,4,5,10,11) else 0)
            cap = seg["capacity_utilization_pct"] or 50
            flow_pct = round(cap * seasonal * random.uniform(0.85, 1.15), 1)
            records.append({
                "monitor_id":   f"MON-{seg['segment_id']}-2025-{str(month).zfill(2)}",
                "segment_id":   seg["segment_id"],
                "system_type":  seg["system_type"],
                "year":         2025,
                "month":        month,
                "avg_flow_pct": round(min(flow_pct, 120), 1),
                "peak_flow_pct":round(min(flow_pct * random.uniform(1.2, 1.8), 150), 1),
                "inflow_infiltration_flag": flow_pct > 85,
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
def generate_budget():
    records = []
    for year in [2022, 2023, 2024, 2025, 2026]:
        for district in DISTRICTS:
            # Water, sewer, stormwater budget split
            total_budget = random.randint(1_200_000, 6_500_000)
            water_pct  = round(random.uniform(0.30, 0.45), 2)
            sewer_pct  = round(random.uniform(0.30, 0.45), 2)
            storm_pct  = round(1 - water_pct - sewer_pct, 2)

            records.append({
                "fiscal_year":              year,
                "district":                 district,
                "total_cip_budget_usd":     total_budget,
                "water_budget_pct":         round(water_pct * 100, 1),
                "sewer_budget_pct":         round(sewer_pct * 100, 1),
                "stormwater_budget_pct":    round(storm_pct * 100, 1),
                "spent_budget_usd":         random.randint(int(total_budget * 0.6),
                                                           int(total_budget * 1.05)),
                "projects_completed":       random.randint(3, 30),
                "pipe_miles_replaced":      round(random.uniform(0.2, 4.5), 1),
                "citizen_satisfaction":     round(random.uniform(2.5, 4.8), 1),
            })
    return pd.DataFrame(records)


# ─── GENERATE ALL & SAVE ──────────────────────────────────────────────────────
print("Generating pipe segments (water / sewer / stormwater)...")
pipes = generate_pipe_segments(500)
pipes.to_csv(BASE_DIR / "pipe_segments.csv", index=False)
print(f"  -> {len(pipes)} pipe segments saved")
print(f"  Systems: {pipes['system_type'].value_counts().to_dict()}")
print(f"  Districts: {pipes['district'].value_counts().to_dict()}")

print("Generating work orders...")
work_orders = generate_work_orders(pipes, 600)
work_orders.to_csv(BASE_DIR / "work_orders.csv", index=False)
print(f"  -> {len(work_orders)} work orders saved")

print("Generating service requests...")
requests = generate_service_requests(pipes, 900)
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
weather = generate_weather(150)
weather.to_csv(BASE_DIR / "weather_events.csv", index=False)
print(f"  -> {len(weather)} weather events saved")

print("Generating CIP budget data...")
budget = generate_budget()
budget.to_csv(BASE_DIR / "budget_cip.csv", index=False)
print(f"  -> {len(budget)} budget records saved")

print("\n✓ All datasets generated successfully.")
print("\nSample — Pipe Segments:")
print(pipes[["segment_id","system_type","corridor_name","district",
             "pipe_material","diameter_inches","condition_score",
             "breaks_last_5yr","estimated_replacement_cost_usd"]].head(10).to_string(index=False))

