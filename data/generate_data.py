"""
PWIS Synthetic Data Generator
Generates realistic synthetic datasets for the Boise Public Works Intelligence System.
All coordinates are within the Boise, Idaho metro area (approx 43.6°N, 116.2°W).
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

np.random.seed(42)
random.seed(42)

# ─── CONSTANTS ────────────────────────────────────────────────────────────────
BOISE_LAT_MIN, BOISE_LAT_MAX = 43.56, 43.68
BOISE_LON_MIN, BOISE_LON_MAX = -116.32, -116.10

ROAD_TYPES       = ['Arterial', 'Collector', 'Local', 'Highway']
DISTRICTS        = ['North End', 'Downtown', 'East Bench', 'Southeast', 'Southwest', 'West Boise']
SURFACE_TYPES    = ['Asphalt', 'Concrete', 'Chip Seal']
COMPLAINT_TYPES  = ['Pothole', 'Crack', 'Flooding', 'Sign Damage', 'Debris', 'Pavement Failure', 'Sidewalk']
WO_STATUSES      = ['Open', 'In Progress', 'Completed', 'Deferred']
WO_TYPES         = ['Pothole Repair', 'Crack Seal', 'Resurfacing', 'Emergency Repair',
                    'Striping', 'Drainage Repair', 'Sign Replacement']
WEATHER_EVENTS   = ['None', 'Light Rain', 'Heavy Rain', 'Snow', 'Ice Storm', 'Freeze-Thaw']

# ─── 1. ROAD SEGMENTS ─────────────────────────────────────────────────────────
def generate_road_segments(n=300):
    segments = []
    for i in range(n):
        district = random.choice(DISTRICTS)
        road_type = random.choice(ROAD_TYPES)
        # Condition index 1–100; lower = worse
        # Arterials maintained better on average
        base_condition = {'Arterial': 65, 'Collector': 55, 'Local': 45, 'Highway': 75}[road_type]
        condition = int(np.clip(np.random.normal(base_condition, 18), 5, 100))
        install_year = random.randint(1975, 2022)
        age = 2026 - install_year
        lat = round(random.uniform(BOISE_LAT_MIN, BOISE_LAT_MAX), 6)
        lon = round(random.uniform(BOISE_LON_MIN, BOISE_LON_MAX), 6)
        length_miles = round(random.uniform(0.1, 2.5), 2)
        daily_traffic = {
            'Arterial': random.randint(8000, 35000),
            'Collector': random.randint(2000, 10000),
            'Local': random.randint(100, 2500),
            'Highway': random.randint(15000, 60000)
        }[road_type]

        segments.append({
            'segment_id': f'SEG-{str(i+1).zfill(4)}',
            'street_name': f'{random.choice(["Ustick","Overland","Fairview","State","Chinden","Federal Way","Broadway","Vista","Cole","Orchard","Five Mile","Ten Mile","Meridian","Curtis","Milwaukee","Cloverdale","Eagle","Maple Grove","Lake Harbour","Emerald"])} {random.choice(["Rd","Ave","Blvd","St","Dr","Way","Ln"])}',
            'district': district,
            'road_type': road_type,
            'surface_type': random.choice(SURFACE_TYPES),
            'condition_index': condition,
            'paser_rating': max(1, min(10, round(condition / 10))),
            'install_year': install_year,
            'asset_age_years': age,
            'length_miles': length_miles,
            'lane_width_ft': random.choice([10, 11, 12]),
            'num_lanes': {'Arterial': random.choice([4,6]), 'Collector': random.choice([2,4]),
                          'Local': 2, 'Highway': random.choice([4,6,8])}[road_type],
            'daily_traffic_aadt': daily_traffic,
            'lat': lat,
            'lon': lon,
            'last_inspection_date': (datetime(2026,1,1) - timedelta(days=random.randint(30, 900))).strftime('%Y-%m-%d'),
            'last_treatment_year': random.randint(2015, 2025),
            'estimated_repair_cost_usd': int(length_miles * random.uniform(15000, 85000)),
        })
    return pd.DataFrame(segments)

# ─── 2. WORK ORDERS ───────────────────────────────────────────────────────────
def generate_work_orders(segments_df, n=500):
    wos = []
    for i in range(n):
        seg = segments_df.sample(1).iloc[0]
        created = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 730))
        wo_type = random.choice(WO_TYPES)
        status = random.choice(WO_STATUSES)
        # Completed work orders have closed dates
        if status == 'Completed':
            closed = created + timedelta(days=random.randint(1, 90))
            completed_date = closed.strftime('%Y-%m-%d')
        else:
            completed_date = None

        wos.append({
            'work_order_id': f'WO-{str(i+1).zfill(5)}',
            'segment_id': seg['segment_id'],
            'district': seg['district'],
            'work_order_type': wo_type,
            'status': status,
            'priority': random.choice(['Critical', 'High', 'Medium', 'Low']),
            'created_date': created.strftime('%Y-%m-%d'),
            'completed_date': completed_date,
            'crew_assigned': f'Crew-{random.randint(1,8)}',
            'estimated_hours': round(random.uniform(2, 80), 1),
            'actual_hours': round(random.uniform(2, 90), 1) if status == 'Completed' else None,
            'estimated_cost_usd': random.randint(500, 95000),
            'actual_cost_usd': random.randint(400, 110000) if status == 'Completed' else None,
            'source': random.choice(['Inspection', '311 Complaint', 'Crew Report', 'Scheduled PM']),
            'lat': seg['lat'] + random.uniform(-0.001, 0.001),
            'lon': seg['lon'] + random.uniform(-0.001, 0.001),
        })
    return pd.DataFrame(wos)

# ─── 3. CITIZEN COMPLAINTS ────────────────────────────────────────────────────
def generate_complaints(segments_df, n=800):
    complaints = []
    for i in range(n):
        seg = segments_df.sample(1).iloc[0]
        # Complaints correlate with bad condition — weight toward lower CI
        if random.random() < 0.6:
            seg = segments_df[segments_df['condition_index'] < 50].sample(1).iloc[0]
        submitted = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 730))
        complaints.append({
            'complaint_id': f'CMP-{str(i+1).zfill(5)}',
            'segment_id': seg['segment_id'],
            'district': seg['district'],
            'complaint_type': random.choice(COMPLAINT_TYPES),
            'submitted_date': submitted.strftime('%Y-%m-%d'),
            'resolved_date': (submitted + timedelta(days=random.randint(1,60))).strftime('%Y-%m-%d') if random.random() > 0.4 else None,
            'resolution_status': random.choice(['Resolved', 'Pending', 'In Review']),
            'severity_reported': random.choice(['Low', 'Medium', 'High', 'Critical']),
            'channel': random.choice(['311 App', 'Phone', 'Web Form', 'Email']),
            'lat': seg['lat'] + random.uniform(-0.002, 0.002),
            'lon': seg['lon'] + random.uniform(-0.002, 0.002),
        })
    return pd.DataFrame(complaints)

# ─── 4. TRAFFIC COUNTS ────────────────────────────────────────────────────────
def generate_traffic(segments_df):
    records = []
    for _, seg in segments_df.iterrows():
        for month in range(1, 13):
            seasonal = 1.0 + 0.15 * np.sin((month - 7) * np.pi / 6)  # Summer peak
            aadt = int(seg['daily_traffic_aadt'] * seasonal * random.uniform(0.92, 1.08))
            records.append({
                'traffic_id': f'TRF-{seg["segment_id"]}-2025-{str(month).zfill(2)}',
                'segment_id': seg['segment_id'],
                'year': 2025,
                'month': month,
                'aadt': aadt,
                'heavy_vehicle_pct': round(random.uniform(3, 25), 1),
                'peak_hour_volume': int(aadt * random.uniform(0.08, 0.12)),
                'congestion_index': round(random.uniform(0.1, 0.9), 2),
            })
    return pd.DataFrame(records)

# ─── 5. WEATHER EVENTS ────────────────────────────────────────────────────────
def generate_weather(n=150):
    events = []
    for i in range(n):
        event_date = datetime(2023, 1, 1) + timedelta(days=random.randint(0, 1095))
        event_type = random.choice(WEATHER_EVENTS[1:])  # Exclude 'None'
        events.append({
            'weather_event_id': f'WX-{str(i+1).zfill(4)}',
            'event_date': event_date.strftime('%Y-%m-%d'),
            'event_type': event_type,
            'duration_hours': round(random.uniform(1, 72), 1),
            'precipitation_inches': round(random.uniform(0.1, 4.5), 2) if 'Rain' in event_type or 'Snow' in event_type else 0,
            'min_temp_f': round(random.uniform(10, 45), 1) if 'Ice' in event_type or 'Snow' in event_type or 'Freeze' in event_type else round(random.uniform(32, 65), 1),
            'district_affected': random.choice(DISTRICTS + ['All']),
            'estimated_damage_usd': random.randint(0, 250000),
            'work_orders_triggered': random.randint(0, 45),
        })
    return pd.DataFrame(events)

# ─── 6. BRIDGE INSPECTIONS ────────────────────────────────────────────────────
def generate_bridges(n=47):
    bridges = []
    for i in range(n):
        bridges.append({
            'bridge_id': f'BRG-{str(i+1).zfill(3)}',
            'bridge_name': f'Bridge at {random.choice(["Chinden","Ustick","Overland","State","Fairview","Orchard","Milwaukee","Cole","Eagle","Meridian"])} & {random.choice(["Boise River","Five Mile Creek","Dry Creek","Hulls Gulch","Jackson Slough"])}',
            'district': random.choice(DISTRICTS),
            'built_year': random.randint(1955, 2018),
            'deck_condition': random.choice(['Good', 'Fair', 'Poor', 'Critical']),
            'superstructure_condition': random.choice(['Good', 'Fair', 'Poor']),
            'substructure_condition': random.choice(['Good', 'Fair', 'Poor']),
            'sufficiency_rating': round(random.uniform(20, 100), 1),
            'daily_traffic_aadt': random.randint(500, 45000),
            'last_inspection_date': (datetime(2026,1,1) - timedelta(days=random.randint(30,730))).strftime('%Y-%m-%d'),
            'estimated_repair_cost_usd': random.randint(50000, 5000000),
            'lat': round(random.uniform(BOISE_LAT_MIN, BOISE_LAT_MAX), 6),
            'lon': round(random.uniform(BOISE_LON_MIN, BOISE_LON_MAX), 6),
        })
    return pd.DataFrame(bridges)

# ─── 7. BUDGET / FISCAL TABLE ─────────────────────────────────────────────────
def generate_budget():
    records = []
    for year in [2022, 2023, 2024, 2025, 2026]:
        for district in DISTRICTS:
            records.append({
                'fiscal_year': year,
                'district': district,
                'allocated_budget_usd': random.randint(800000, 4500000),
                'spent_budget_usd': random.randint(600000, 4200000),
                # Proportions normalized to sum to 100% via Dirichlet-style draw
                **{k: v for k, v in zip(
                    ['preventive_pct', 'reactive_pct', 'capital_pct'],
                    [round(x, 1) for x in (
                        lambda raw: raw / raw.sum() * 100
                    )(np.array([
                        random.uniform(0.30, 0.55),
                        random.uniform(0.30, 0.50),
                        random.uniform(0.05, 0.20),
                    ]))]
                )},
                'num_projects_completed': random.randint(5, 40),
                'citizen_satisfaction_score': round(random.uniform(2.5, 4.8), 1),
            })
    return pd.DataFrame(records)

# ─── GENERATE ALL & SAVE ──────────────────────────────────────────────────────
print("Generating road segments...")
roads = generate_road_segments(300)
roads.to_csv('/sessions/happy-wonderful-hawking/boise-pwis/data/road_segments.csv', index=False)
print(f"  → {len(roads)} road segments saved")

print("Generating work orders...")
work_orders = generate_work_orders(roads, 500)
work_orders.to_csv('/sessions/happy-wonderful-hawking/boise-pwis/data/work_orders.csv', index=False)
print(f"  → {len(work_orders)} work orders saved")

print("Generating complaints...")
complaints = generate_complaints(roads, 800)
complaints.to_csv('/sessions/happy-wonderful-hawking/boise-pwis/data/complaints.csv', index=False)
print(f"  → {len(complaints)} complaints saved")

print("Generating traffic counts...")
traffic = generate_traffic(roads)
traffic.to_csv('/sessions/happy-wonderful-hawking/boise-pwis/data/traffic_counts.csv', index=False)
print(f"  → {len(traffic)} traffic records saved")

print("Generating weather events...")
weather = generate_weather(150)
weather.to_csv('/sessions/happy-wonderful-hawking/boise-pwis/data/weather_events.csv', index=False)
print(f"  → {len(weather)} weather events saved")

print("Generating bridge inspections...")
bridges = generate_bridges(47)
bridges.to_csv('/sessions/happy-wonderful-hawking/boise-pwis/data/bridge_inspections.csv', index=False)
print(f"  → {len(bridges)} bridges saved")

print("Generating budget data...")
budget = generate_budget()
budget.to_csv('/sessions/happy-wonderful-hawking/boise-pwis/data/budget_actuals.csv', index=False)
print(f"  → {len(budget)} budget records saved")

print("\n✓ All datasets generated successfully.")
print("\nSample — Road Segments:")
print(roads[['segment_id','district','road_type','condition_index','daily_traffic_aadt','estimated_repair_cost_usd']].head(5).to_string(index=False))
