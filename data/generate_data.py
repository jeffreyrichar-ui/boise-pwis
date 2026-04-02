"""
PWIS Synthetic Data Generator
==============================
Generates realistic synthetic datasets for the Boise Public Works Intelligence System.

Geography: Real Boise, Idaho streets anchored to their actual locations.
  - Street names match real Boise roads
  - Districts reflect Boise's actual neighborhood geography
  - Road types match ACHD (Ada County Highway District) functional classifications
  - Coordinates are derived from each street's real lat/lon corridor with
    per-block random offsets (±0.002 deg ~ ±200m) to simulate individual segments

District bounding boxes (approximate WGS-84):
  North End     : 43.626–43.680 N, 116.230–116.170 W  (foothills, historic tree-lined streets)
  Downtown      : 43.600–43.626 N, 116.220–116.175 W  (grid, Capitol area, mixed arterial/local)
  East Bench    : 43.580–43.626 N, 116.175–116.100 W  (bench above river, Warm Springs corridor)
  Southeast     : 43.540–43.595 N, 116.200–116.100 W  (Vista corridor, airport approach)
  Southwest     : 43.540–43.600 N, 116.330–116.200 W  (Five Mile / Cole / Overland suburbs)
  West Boise    : 43.600–43.655 N, 116.360–116.230 W  (Fairview/Ustick/Chinden west corridors)

Sources:
  ACHD Master Street Map 2018 (cityofboise.org)
  City of Boise GIS Open Data Portal (opendata.cityofboise.org)
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from pathlib import Path

np.random.seed(42)
random.seed(42)

BASE_DIR = Path(__file__).parent

# ─── REAL BOISE STREET CATALOG ────────────────────────────────────────────────
# Each entry: (street_name, road_type, district, anchor_lat, anchor_lon,
#              orientation, base_aadt_low, base_aadt_high)
# orientation: 'EW' = east-west (lat fixed, lon varies per segment)
#              'NS' = north-south (lon fixed, lat varies per segment)
#              'DIAG' = diagonal/curved (both vary)
# AADT ranges sourced from ACHD traffic counts and KTVB Boise traffic data

STREET_CATALOG = [
    # ── HIGHWAYS ──────────────────────────────────────────────────────────────
    # I-84 runs E-W through south Boise / Southeast / Southwest
    ("I-84 EB",         "Highway", "Southeast",  43.543, -116.175, "EW",  45000, 68000),
    ("I-84 WB",         "Highway", "Southwest",  43.543, -116.260, "EW",  45000, 68000),
    ("I-184 (Connector)","Highway","Downtown",   43.609, -116.214, "EW",  22000, 38000),
    ("State St / Hwy 44","Highway","West Boise",  43.637, -116.280, "EW",  18000, 32000),
    ("Chinden Blvd / Hwy 20", "Highway", "West Boise", 43.653, -116.310, "EW", 20000, 42000),

    # ── MAJOR E-W ARTERIALS ───────────────────────────────────────────────────
    # Chinden (east of Eagle Rd, entering Garden City / North End)
    ("Chinden Blvd",    "Arterial","North End",   43.653, -116.210, "EW",  14000, 28000),
    # McMillan – West Boise suburban corridor
    ("McMillan Rd",     "Arterial","West Boise",  43.643, -116.310, "EW",  10000, 22000),
    # Ustick – major cross-town arterial
    ("Ustick Rd",       "Arterial","West Boise",  43.633, -116.300, "EW",  12000, 26000),
    # Fairview – busiest cross-town arterial
    ("Fairview Ave",    "Arterial","West Boise",  43.616, -116.295, "EW",  18000, 38000),
    ("Fairview Ave",    "Arterial","Downtown",    43.616, -116.200, "EW",  16000, 34000),
    # Franklin – mid-Boise E-W
    ("Franklin Rd",     "Arterial","West Boise",  43.607, -116.290, "EW",   9000, 20000),
    ("Franklin Rd",     "Arterial","Southwest",   43.607, -116.245, "EW",   8000, 18000),
    # Overland – south Boise cross-town
    ("Overland Rd",     "Arterial","Southwest",   43.588, -116.270, "EW",  14000, 30000),
    ("Overland Rd",     "Arterial","Southeast",   43.588, -116.195, "EW",  12000, 26000),
    # Victory – suburban south corridor
    ("Victory Rd",      "Arterial","Southwest",   43.570, -116.280, "EW",   7000, 16000),
    ("Victory Rd",      "Arterial","Southeast",   43.570, -116.195, "EW",   6000, 14000),
    # Amity – far south Boise
    ("Amity Rd",        "Arterial","Southwest",   43.553, -116.275, "EW",   5000, 12000),
    # Warm Springs – East Bench signature road
    ("Warm Springs Ave","Arterial","East Bench",  43.608, -116.165, "EW",   9000, 18000),
    # Federal Way – East Bench / Southeast connector
    ("Federal Way",     "Arterial","East Bench",  43.597, -116.158, "EW",   8000, 16000),
    # Emerald – inner Boise collector/arterial
    ("Emerald St",      "Arterial","Downtown",    43.614, -116.202, "EW",   7000, 15000),
    ("Emerald St",      "Arterial","Southeast",   43.614, -116.190, "EW",   6000, 13000),
    # Gowen – southeast / airport area
    ("Gowen Rd",        "Arterial","Southeast",   43.543, -116.158, "EW",   5000, 11000),

    # ── MAJOR N-S ARTERIALS ───────────────────────────────────────────────────
    # Eagle Rd – far west
    ("Eagle Rd",        "Arterial","West Boise",  43.625, -116.354, "NS",  16000, 32000),
    # Cloverdale – west Boise N-S
    ("Cloverdale Rd",   "Arterial","West Boise",  43.620, -116.336, "NS",  12000, 24000),
    # Ten Mile – suburban west
    ("Ten Mile Rd",     "Arterial","West Boise",  43.615, -116.316, "NS",  10000, 22000),
    # Five Mile – SW/West Boise corridor
    ("Five Mile Rd",    "Arterial","West Boise",  43.618, -116.295, "NS",  11000, 23000),
    ("Five Mile Rd",    "Arterial","Southwest",   43.575, -116.295, "NS",   9000, 19000),
    # Maple Grove – inner west
    ("Maple Grove Rd",  "Arterial","West Boise",  43.620, -116.276, "NS",  10000, 21000),
    ("Maple Grove Rd",  "Arterial","Southwest",   43.575, -116.276, "NS",   8000, 17000),
    # Cole Rd – central N-S spine
    ("Cole Rd",         "Arterial","West Boise",  43.625, -116.256, "NS",  14000, 28000),
    ("Cole Rd",         "Arterial","Southwest",   43.572, -116.256, "NS",  11000, 22000),
    # Orchard St – inner SE/SW
    ("Orchard St",      "Arterial","Southwest",   43.585, -116.232, "NS",   9000, 18000),
    ("Orchard St",      "Arterial","Southeast",   43.565, -116.232, "NS",   7000, 15000),
    # Vista Ave – SE signature arterial
    ("Vista Ave",       "Arterial","Southeast",   43.575, -116.207, "NS",  10000, 20000),
    # Broadway Ave – east Downtown / SE
    ("Broadway Ave",    "Arterial","Downtown",    43.612, -116.188, "NS",  12000, 24000),
    ("Broadway Ave",    "Arterial","Southeast",   43.568, -116.188, "NS",  10000, 20000),
    # Curtis Rd – collector-level N-S
    ("Curtis Rd",       "Collector","Southwest",  43.580, -116.222, "NS",   5000, 11000),
    # Milwaukee St – SE collector
    ("Milwaukee St",    "Collector","Southeast",  43.565, -116.210, "NS",   4000,  9000),

    # ── COLLECTORS: NORTH END ─────────────────────────────────────────────────
    ("Harrison Blvd",   "Collector","North End",  43.643, -116.200, "NS",   4000,  9000),
    ("Hill Rd",         "Collector","North End",  43.660, -116.215, "EW",   3000,  7000),
    ("Bogus Basin Rd",  "Collector","North End",  43.665, -116.195, "DIAG", 2000,  5000),

    # ── COLLECTORS: DOWNTOWN ──────────────────────────────────────────────────
    ("Capitol Blvd",    "Collector","Downtown",   43.611, -116.201, "NS",   6000, 12000),
    ("Front St",        "Arterial", "Downtown",   43.606, -116.205, "EW",  10000, 20000),
    ("Myrtle St",       "Collector","Downtown",   43.607, -116.200, "EW",   5000, 10000),
    ("Bannock St",      "Collector","Downtown",   43.613, -116.200, "EW",   4000,  8000),
    ("Jefferson St",    "Collector","Downtown",   43.616, -116.201, "EW",   3500,  7000),
    ("Main St",         "Collector","Downtown",   43.615, -116.200, "EW",   5000, 10000),

    # ── LOCAL: NORTH END ──────────────────────────────────────────────────────
    ("Fort St",         "Local",    "North End",  43.638, -116.205, "EW",    800,  2500),
    ("Eastman St",      "Local",    "North End",  43.641, -116.203, "EW",    600,  2000),
    ("15th St",         "Local",    "North End",  43.645, -116.208, "NS",    500,  1800),
    ("Lemp St",         "Local",    "North End",  43.648, -116.202, "EW",    400,  1500),
    ("Northview St",    "Local",    "North End",  43.650, -116.198, "EW",    300,  1200),

    # ── LOCAL: DOWNTOWN ───────────────────────────────────────────────────────
    ("Idaho St",        "Local",    "Downtown",   43.614, -116.202, "EW",   2000,  5000),
    ("8th St",          "Local",    "Downtown",   43.613, -116.197, "NS",   1500,  4000),
    ("9th St",          "Local",    "Downtown",   43.613, -116.199, "NS",   1500,  4000),
    ("11th St",         "Local",    "Downtown",   43.613, -116.202, "NS",   1200,  3500),

    # ── LOCAL: EAST BENCH ─────────────────────────────────────────────────────
    ("Parkcenter Blvd", "Collector","East Bench", 43.597, -116.178, "NS",   4000,  9000),
    ("Shaw Mountain Rd","Collector","East Bench", 43.605, -116.155, "DIAG", 2000,  5000),
    ("Boise Ave",       "Collector","East Bench", 43.600, -116.172, "EW",   3000,  7000),
    ("Cassia St",       "Local",    "East Bench", 43.603, -116.168, "EW",    800,  2500),
    ("Latah St",        "Local",    "East Bench", 43.598, -116.165, "EW",    600,  2000),

    # ── LOCAL: SOUTHEAST ──────────────────────────────────────────────────────
    ("Protest Rd",      "Local",    "Southeast",  43.555, -116.178, "NS",    400,  1500),
    ("Gekeler Ln",      "Local",    "Southeast",  43.558, -116.193, "NS",    500,  1800),
    ("Rose Hill St",    "Local",    "Southeast",  43.562, -116.185, "EW",    400,  1400),
    ("Eisenman Rd",     "Collector","Southeast",  43.550, -116.170, "NS",   2000,  5000),

    # ── LOCAL: SOUTHWEST ──────────────────────────────────────────────────────
    ("Linden St",       "Local",    "Southwest",  43.578, -116.252, "EW",    400,  1500),
    ("Targee St",       "Local",    "Southwest",  43.572, -116.246, "EW",    350,  1300),
    ("Hillcrest Ave",   "Local",    "Southwest",  43.583, -116.238, "EW",    500,  1800),

    # ── LOCAL: WEST BOISE ─────────────────────────────────────────────────────
    ("Lake Harbour Ln", "Local",    "West Boise", 43.635, -116.285, "EW",    400,  1500),
    ("Bergeson St",     "Local",    "West Boise", 43.628, -116.270, "EW",    300,  1200),
    ("Biscayne Dr",     "Local",    "West Boise", 43.622, -116.315, "EW",    350,  1300),
]

# ACHD functional class → typical PASER condition distribution
ROAD_CONDITION_PROFILE = {
    "Highway":   {"mean": 72, "std": 14},
    "Arterial":  {"mean": 62, "std": 18},
    "Collector": {"mean": 54, "std": 20},
    "Local":     {"mean": 46, "std": 22},
}

SURFACE_BY_TYPE = {
    "Highway":   ["Asphalt", "Concrete", "Asphalt"],      # Concrete rare on highways
    "Arterial":  ["Asphalt", "Asphalt", "Concrete"],
    "Collector": ["Asphalt", "Asphalt", "Chip Seal"],
    "Local":     ["Asphalt", "Chip Seal", "Chip Seal"],
}

COMPLAINT_TYPES  = ["Pothole", "Crack", "Flooding", "Sign Damage", "Debris",
                    "Pavement Failure", "Sidewalk"]
WO_STATUSES      = ["Open", "In Progress", "Completed", "Deferred"]
WO_TYPES         = ["Pothole Repair", "Crack Seal", "Resurfacing", "Emergency Repair",
                    "Striping", "Drainage Repair", "Sign Replacement"]
WEATHER_EVENTS   = ["Light Rain", "Heavy Rain", "Snow", "Ice Storm", "Freeze-Thaw"]
DISTRICTS        = ["North End", "Downtown", "East Bench", "Southeast", "Southwest", "West Boise"]

# District bounding boxes: (lat_min, lat_max, lon_min, lon_max)
DISTRICT_BOUNDS = {
    "North End":  (43.626, 43.680, -116.230, -116.170),
    "Downtown":   (43.600, 43.626, -116.220, -116.175),
    "East Bench": (43.580, 43.626, -116.175, -116.100),
    "Southeast":  (43.540, 43.595, -116.200, -116.100),
    "Southwest":  (43.540, 43.600, -116.330, -116.200),
    "West Boise": (43.600, 43.655, -116.360, -116.230),
}


# ─── 1. ROAD SEGMENTS ─────────────────────────────────────────────────────────
def generate_road_segments(n=300):
    """
    Generate synthetic road segments using real Boise street anchors.
    Each entry in STREET_CATALOG can produce multiple segments (blocks).
    Coordinates are offset from the street's anchor lat/lon to simulate
    individual block-level segments along the corridor.
    """
    segments = []
    seg_id = 1

    # Distribute n segments across catalog entries proportionally
    weights = []
    for entry in STREET_CATALOG:
        rt = entry[1]
        # Highways and arterials get more segments (longer roads)
        w = {"Highway": 5, "Arterial": 4, "Collector": 2, "Local": 1}[rt]
        weights.append(w)
    total_w = sum(weights)
    counts = [max(1, round(n * w / total_w)) for w in weights]

    # Trim/pad to exactly n
    while sum(counts) > n:
        counts[counts.index(max(counts))] -= 1
    while sum(counts) < n:
        counts[counts.index(min(counts))] += 1

    for entry, count in zip(STREET_CATALOG, counts):
        street_name, road_type, district, anchor_lat, anchor_lon, orientation, aadt_lo, aadt_hi = entry
        profile = ROAD_CONDITION_PROFILE[road_type]

        for _ in range(count):
            # Offset lat/lon along the street's corridor
            if orientation == "EW":
                lat = anchor_lat + random.uniform(-0.003, 0.003)
                lon = anchor_lon + random.uniform(-0.040, 0.040)
            elif orientation == "NS":
                lat = anchor_lat + random.uniform(-0.040, 0.040)
                lon = anchor_lon + random.uniform(-0.003, 0.003)
            else:  # DIAG
                lat = anchor_lat + random.uniform(-0.020, 0.020)
                lon = anchor_lon + random.uniform(-0.020, 0.020)

            # Clip to district bounds
            db = DISTRICT_BOUNDS[district]
            lat = float(np.clip(lat, db[0], db[1]))
            lon = float(np.clip(lon, db[2], db[3]))

            condition = int(np.clip(np.random.normal(profile["mean"], profile["std"]), 5, 100))
            install_year = random.randint(1970, 2022)
            age = 2026 - install_year
            length_miles = {
                "Highway":   round(random.uniform(0.5, 3.0), 2),
                "Arterial":  round(random.uniform(0.3, 2.0), 2),
                "Collector": round(random.uniform(0.2, 1.2), 2),
                "Local":     round(random.uniform(0.1, 0.6), 2),
            }[road_type]

            daily_traffic = random.randint(aadt_lo, aadt_hi)
            num_lanes = {
                "Highway":   random.choice([4, 6, 8]),
                "Arterial":  random.choice([4, 6]),
                "Collector": random.choice([2, 4]),
                "Local":     2,
            }[road_type]

            cost_per_mile = {
                "Highway":   random.uniform(80000, 200000),
                "Arterial":  random.uniform(50000, 120000),
                "Collector": random.uniform(25000, 70000),
                "Local":     random.uniform(10000, 40000),
            }[road_type]

            segments.append({
                "segment_id":                f"SEG-{str(seg_id).zfill(4)}",
                "street_name":               street_name,
                "district":                  district,
                "road_type":                 road_type,
                "surface_type":              random.choice(SURFACE_BY_TYPE[road_type]),
                "condition_index":           condition,
                "paser_rating":              max(1, min(10, round(condition / 10))),
                "install_year":              install_year,
                "asset_age_years":           age,
                "length_miles":              length_miles,
                "lane_width_ft":             random.choice([11, 12]),
                "num_lanes":                 num_lanes,
                "daily_traffic_aadt":        daily_traffic,
                "lat":                       round(lat, 6),
                "lon":                       round(lon, 6),
                "last_inspection_date":      (
                    datetime(2026, 1, 1) - timedelta(days=random.randint(30, 900))
                ).strftime("%Y-%m-%d"),
                "last_treatment_year":       random.randint(2014, 2025),
                "estimated_repair_cost_usd": int(length_miles * cost_per_mile),
            })
            seg_id += 1

    return pd.DataFrame(segments).head(n)


# ─── 2. WORK ORDERS ───────────────────────────────────────────────────────────
def generate_work_orders(segments_df, n=500):
    wos = []
    for i in range(n):
        seg = segments_df.sample(1).iloc[0]
        created = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 730))
        status = random.choice(WO_STATUSES)
        completed_date = None
        actual_hours = None
        actual_cost = None
        if status == "Completed":
            completed_date = (created + timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d")
            actual_hours = round(random.uniform(2, 90), 1)
            actual_cost = random.randint(400, 110000)

        wos.append({
            "work_order_id":       f"WO-{str(i+1).zfill(5)}",
            "segment_id":          seg["segment_id"],
            "district":            seg["district"],
            "work_order_type":     random.choice(WO_TYPES),
            "status":              status,
            "priority":            random.choice(["Critical", "High", "Medium", "Low"]),
            "created_date":        created.strftime("%Y-%m-%d"),
            "completed_date":      completed_date,
            "crew_assigned":       f"Crew-{random.randint(1, 8)}",
            "estimated_hours":     round(random.uniform(2, 80), 1),
            "actual_hours":        actual_hours,
            "estimated_cost_usd":  random.randint(500, 95000),
            "actual_cost_usd":     actual_cost,
            "source":              random.choice(["Inspection", "311 Complaint",
                                                   "Crew Report", "Scheduled PM"]),
            "lat":                 seg["lat"] + random.uniform(-0.001, 0.001),
            "lon":                 seg["lon"] + random.uniform(-0.001, 0.001),
        })
    return pd.DataFrame(wos)


# ─── 3. CITIZEN COMPLAINTS ────────────────────────────────────────────────────
def generate_complaints(segments_df, n=800):
    complaints = []
    for i in range(n):
        # 60% of complaints come from segments in poor condition
        if random.random() < 0.6:
            pool = segments_df[segments_df["condition_index"] < 50]
            seg = pool.sample(1).iloc[0] if len(pool) > 0 else segments_df.sample(1).iloc[0]
        else:
            seg = segments_df.sample(1).iloc[0]

        submitted = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 730))
        resolved_date = None
        if random.random() > 0.4:
            resolved_date = (submitted + timedelta(days=random.randint(1, 60))).strftime("%Y-%m-%d")

        complaints.append({
            "complaint_id":        f"CMP-{str(i+1).zfill(5)}",
            "segment_id":          seg["segment_id"],
            "district":            seg["district"],
            "complaint_type":      random.choice(COMPLAINT_TYPES),
            "submitted_date":      submitted.strftime("%Y-%m-%d"),
            "resolved_date":       resolved_date,
            "resolution_status":   random.choice(["Resolved", "Pending", "In Review"]),
            "severity_reported":   random.choice(["Low", "Medium", "High", "Critical"]),
            "channel":             random.choice(["311 App", "Phone", "Web Form", "Email"]),
            "lat":                 seg["lat"] + random.uniform(-0.002, 0.002),
            "lon":                 seg["lon"] + random.uniform(-0.002, 0.002),
        })
    return pd.DataFrame(complaints)


# ─── 4. TRAFFIC COUNTS ────────────────────────────────────────────────────────
def generate_traffic(segments_df):
    records = []
    for _, seg in segments_df.iterrows():
        for month in range(1, 13):
            # Boise traffic peaks in summer; winter dip from weather
            seasonal = 1.0 + 0.15 * np.sin((month - 7) * np.pi / 6)
            aadt = int(seg["daily_traffic_aadt"] * seasonal * random.uniform(0.92, 1.08))
            records.append({
                "traffic_id":         f"TRF-{seg['segment_id']}-2025-{str(month).zfill(2)}",
                "segment_id":         seg["segment_id"],
                "year":               2025,
                "month":              month,
                "aadt":               aadt,
                "heavy_vehicle_pct":  round(random.uniform(3, 25), 1),
                "peak_hour_volume":   int(aadt * random.uniform(0.08, 0.12)),
                "congestion_index":   round(random.uniform(0.1, 0.9), 2),
            })
    return pd.DataFrame(records)


# ─── 5. WEATHER EVENTS ────────────────────────────────────────────────────────
def generate_weather(n=150):
    events = []
    for i in range(n):
        event_date = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 1095))
        event_type = random.choice(WEATHER_EVENTS)
        is_frozen = event_type in ("Ice Storm", "Snow", "Freeze-Thaw")
        events.append({
            "weather_event_id":       f"WX-{str(i+1).zfill(4)}",
            "event_date":             event_date.strftime("%Y-%m-%d"),
            "event_type":             event_type,
            "duration_hours":         round(random.uniform(1, 72), 1),
            "precipitation_inches":   round(random.uniform(0.1, 4.5), 2)
                                       if ("Rain" in event_type or "Snow" in event_type) else 0,
            "min_temp_f":             round(random.uniform(10, 32), 1)
                                       if is_frozen else round(random.uniform(32, 65), 1),
            "district_affected":      random.choice(DISTRICTS + ["All"]),
            "estimated_damage_usd":   random.randint(0, 250000),
            "work_orders_triggered":  random.randint(0, 45),
        })
    return pd.DataFrame(events)


# ─── 6. BRIDGE INSPECTIONS ────────────────────────────────────────────────────
# Real Boise-area bridges crossing the Boise River and major drainages
BOISE_BRIDGES = [
    ("Broadway Bridge",      "Downtown",  43.604, -116.188),
    ("Capitol Blvd Bridge",  "Downtown",  43.604, -116.201),
    ("Americana Blvd Bridge","Downtown",  43.604, -116.212),
    ("Veterans Memorial Br", "West Boise",43.604, -116.225),
    ("Glenwood Bridge",      "West Boise",43.635, -116.233),
    ("Eagle Road Bridge",    "West Boise",43.604, -116.354),
    ("Cole Rd Bridge",       "Southwest", 43.585, -116.256),
    ("Orchard St Bridge",    "Southeast", 43.580, -116.232),
    ("Warm Springs Bridge",  "East Bench",43.604, -116.153),
    ("Federal Way Bridge",   "East Bench",43.590, -116.160),
    ("Milwaukee St Bridge",  "Southeast", 43.568, -116.210),
    ("Five Mile Crossing",   "Southwest", 43.580, -116.295),
    ("Maple Grove Crossing", "Southwest", 43.575, -116.276),
    ("Cloverdale Overpass",  "West Boise",43.615, -116.336),
    ("Ustick Rd Overpass",   "West Boise",43.633, -116.310),
]

def generate_bridges():
    bridges = []
    for i, (name, district, lat, lon) in enumerate(BOISE_BRIDGES):
        bridges.append({
            "bridge_id":                  f"BRG-{str(i+1).zfill(3)}",
            "bridge_name":                name,
            "district":                   district,
            "built_year":                 random.randint(1955, 2018),
            "deck_condition":             random.choice(["Good", "Fair", "Poor", "Critical"]),
            "superstructure_condition":   random.choice(["Good", "Fair", "Poor"]),
            "substructure_condition":     random.choice(["Good", "Fair", "Poor"]),
            "sufficiency_rating":         round(random.uniform(20, 100), 1),
            "daily_traffic_aadt":         random.randint(500, 45000),
            "last_inspection_date":       (
                datetime(2026, 1, 1) - timedelta(days=random.randint(30, 730))
            ).strftime("%Y-%m-%d"),
            "estimated_repair_cost_usd":  random.randint(50000, 5000000),
            "lat":                        round(lat + random.uniform(-0.001, 0.001), 6),
            "lon":                        round(lon + random.uniform(-0.001, 0.001), 6),
        })
    return pd.DataFrame(bridges)


# ─── 7. BUDGET / FISCAL TABLE ─────────────────────────────────────────────────
def generate_budget():
    records = []
    for year in [2022, 2023, 2024, 2025, 2026]:
        for district in DISTRICTS:
            raw = np.array([
                random.uniform(0.30, 0.55),
                random.uniform(0.30, 0.50),
                random.uniform(0.05, 0.20),
            ])
            pcts = [round(x, 1) for x in (raw / raw.sum() * 100)]
            records.append({
                "fiscal_year":              year,
                "district":                 district,
                "allocated_budget_usd":     random.randint(800000, 4500000),
                "spent_budget_usd":         random.randint(600000, 4200000),
                "preventive_pct":           pcts[0],
                "reactive_pct":             pcts[1],
                "capital_pct":              pcts[2],
                "num_projects_completed":   random.randint(5, 40),
                "citizen_satisfaction_score": round(random.uniform(2.5, 4.8), 1),
            })
    return pd.DataFrame(records)


# ─── GENERATE ALL & SAVE ──────────────────────────────────────────────────────
print("Generating road segments...")
roads = generate_road_segments(300)
roads.to_csv(BASE_DIR / "road_segments.csv", index=False)
print(f"  → {len(roads)} road segments saved")
print(f"  Districts: {roads['district'].value_counts().to_dict()}")
print(f"  Road types: {roads['road_type'].value_counts().to_dict()}")

print("Generating work orders...")
work_orders = generate_work_orders(roads, 500)
work_orders.to_csv(BASE_DIR / "work_orders.csv", index=False)
print(f"  → {len(work_orders)} work orders saved")

print("Generating complaints...")
complaints = generate_complaints(roads, 800)
complaints.to_csv(BASE_DIR / "complaints.csv", index=False)
print(f"  → {len(complaints)} complaints saved")

print("Generating traffic counts...")
traffic = generate_traffic(roads)
traffic.to_csv(BASE_DIR / "traffic_counts.csv", index=False)
print(f"  → {len(traffic)} traffic records saved")

print("Generating weather events...")
weather = generate_weather(150)
weather.to_csv(BASE_DIR / "weather_events.csv", index=False)
print(f"  → {len(weather)} weather events saved")

print("Generating bridge inspections...")
bridges = generate_bridges()
bridges.to_csv(BASE_DIR / "bridge_inspections.csv", index=False)
print(f"  → {len(bridges)} bridges saved")

print("Generating budget data...")
budget = generate_budget()
budget.to_csv(BASE_DIR / "budget_actuals.csv", index=False)
print(f"  → {len(budget)} budget records saved")

print("\n✓ All datasets generated successfully.")
print("\nSample — Road Segments:")
print(roads[["segment_id","street_name","district","road_type",
             "condition_index","daily_traffic_aadt","lat","lon"]].head(10).to_string(index=False))

