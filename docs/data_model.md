# Data Model Documentation
## Boise Public Works Intelligence System (PWIS)

**Document Type:** Technical Data Architecture
**Domain:** Water / Sewer / Stormwater Utility Infrastructure

---

## Overview

The PWIS data model supports prioritization and scenario analysis for Boise's utility infrastructure across three systems (water distribution, sanitary sewer, stormwater collection) and six service districts.

## Core Tables

### pipe_segments (Central Fact Table — 500 records)

The primary asset inventory table. Each row represents one pipe segment in the network.

| Column | Type | Description |
|---|---|---|
| segment_id | VARCHAR | Primary key (PIPE-XXXX) |
| system_type | VARCHAR | Water, Sewer, or Stormwater |
| corridor_name | VARCHAR | Street/corridor name (real Boise geography) |
| district | VARCHAR | Service district (6 districts) |
| pipe_material | VARCHAR | Material type (11 materials by era) |
| diameter_inches | INT | Pipe diameter (4"–72") |
| length_ft | INT | Segment length in linear feet |
| depth_ft | FLOAT | Burial depth |
| install_year | INT | Year installed (1920–2024) |
| asset_age_years | INT | Current age in years |
| condition_score | INT | 1-100 scale (100=excellent) from CCTV/inspection |
| breaks_last_5yr | INT | Break count in trailing 5-year window |
| capacity_utilization_pct | FLOAT | Hydraulic capacity utilization % |
| criticality_class | VARCHAR | System role (Transmission Main, Trunk Sewer, etc.) |
| estimated_replacement_cost_usd | INT | Planning-level replacement cost |
| last_inspection_date | DATE | Most recent inspection date |
| inspection_method | VARCHAR | CCTV, Acoustic, Visual, Smoke Test |
| lat, lon | FLOAT | Segment midpoint coordinates |

### work_orders (600 records)
Maintenance and repair work order history linked to pipe segments.

### service_requests (900 records)
Citizen-reported service requests (311 system) — main breaks, sewer backups, flooding, odor complaints.

### facilities (6 records)
Treatment plants and pump stations: Marden WTP (36 MGD), Columbia WTP (6 MGD), Lander Street WRF, West Boise WRF, Columbia Lift Station, Capitol Park Pump Station.

### flow_monitoring (960 records)
Monthly hydraulic flow data by segment — average flow %, peak flow %, inflow/infiltration flagging.

### budget_cip (30 records)
Capital Improvement Program budget allocation by fiscal year, district, and system type split (water/sewer/stormwater percentages).

### weather_events (150 records)
Precipitation events for wet-weather I&I correlation analysis.

## Relationships

```
pipe_segments (segment_id) ─┬─ work_orders (segment_id)
                            ├─ service_requests (segment_id)
                            └─ flow_monitoring (segment_id)

pipe_segments (district) ───── budget_cip (district)

facilities ─────────────────── standalone dimension
weather_events ─────────────── standalone dimension (joins on date)
```

## Material Types by Era

| Material | Era | System | Risk Factor |
|---|---|---|---|
| Cast Iron | Pre-1960 | Water | 0.90 |
| Asbestos Cement | 1950s–1980s | Water | 0.80 |
| Vitrified Clay | Pre-1970 | Sewer | 0.60 |
| Orangeburg | 1940s–1970s | Sewer | 0.95 |
| Ductile Iron | 1965+ | Water | 0.30 |
| PVC | 1970+ | All | 0.15 |
| HDPE | 1990+ | All | 0.10 |
| Corrugated Metal | 1950s–1990s | Stormwater | 0.75 |
| Concrete | All eras | Sewer/Storm | 0.45 |
| Reinforced Concrete Box | 1960+ | Stormwater | 0.40 |

## Service Districts

North End, Downtown, East Bench, Southeast, Southwest, West Boise — each with distinct infrastructure age profiles and material mixes reflecting Boise's development history.
