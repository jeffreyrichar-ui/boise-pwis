# Data Model Documentation
## Boise Public Works Intelligence System (PWIS)

**Document Type:** Technical Data Architecture
**Domain:** Wastewater/Sewer, Geothermal District Heating, Pressurized Irrigation

---

## Overview

The PWIS data model supports prioritization and scenario analysis for Boise's three utility systems: wastewater/sewer collection, geothermal district heating, and pressurized irrigation (PI), distributed across six service districts (North End, Downtown, East Bench, Southeast, Southwest, West Boise).

## Core Tables

### Segment Inventory Tables (Combined 4,830 records)

Three separate inventories, combined in `all_segments.csv`:

#### sewer_segments (4,200 records)
Primary table for wastewater/sewer collection system asset inventory.

| Column | Type | Description |
|---|---|---|
| segment_id | VARCHAR | Primary key (SEW-XXXX) |
| system_type | VARCHAR | "Sewer" |
| corridor_name | VARCHAR | Street/corridor name (real Boise geography) |
| district | VARCHAR | Service district (6 districts) |
| pipe_material | VARCHAR | Vitrified Clay, PVC, Concrete, Ductile Iron, HDPE, Orangeburg, Cast Iron |
| diameter_inches | INT | Pipe diameter (4"–72") |
| length_ft | INT | Segment length in linear feet |
| depth_ft | FLOAT | Burial depth |
| install_year | INT | Year installed (1920–2024) |
| asset_age_years | INT | Current age in years |
| condition_score | INT | 1-100 scale (100=excellent) from CCTV/inspection |
| breaks_last_5yr | INT | Break count in trailing 5-year window |
| capacity_utilization_pct | FLOAT | Hydraulic capacity utilization % |
| criticality_class | VARCHAR | System role (Transmission Main, Trunk Sewer, Lateral, etc.) |
| estimated_replacement_cost_usd | INT | Planning-level replacement cost |
| last_inspection_date | DATE | Most recent inspection date |
| inspection_method | VARCHAR | CCTV, Acoustic, Visual, Smoke Test |
| lat, lon | FLOAT | Segment midpoint coordinates |

#### geothermal_segments (350 records)
District heating system pipeline inventory.

| Column | Type | Description |
|---|---|---|
| segment_id | VARCHAR | Primary key (GEO-XXXX) |
| system_type | VARCHAR | "Geothermal" |
| corridor_name | VARCHAR | Downtown Boise corridors |
| district | VARCHAR | Primarily Downtown, East Bench |
| pipe_material | VARCHAR | Steel, Pre-insulated Steel, Transite, HDPE |
| diameter_inches | INT | Pipe diameter (2"–8") |
| length_ft | INT | Segment length in linear feet |
| depth_ft | FLOAT | Burial depth |
| install_year | INT | Year installed (1980–2024) |
| asset_age_years | INT | Current age in years |
| condition_score | INT | 1-100 scale (from visual/thermal inspection) |
| temperature_f | FLOAT | Circulating water temperature (177°F nominal) |
| insulation_condition | VARCHAR | Excellent, Good, Fair, Poor |
| capacity_utilization_pct | FLOAT | Flow utilization % (seasonal variation) |
| criticality_class | VARCHAR | Downtown Main Loop, Branch, etc. |
| estimated_replacement_cost_usd | INT | Planning-level replacement cost |
| last_inspection_date | DATE | Most recent inspection date |
| lat, lon | FLOAT | Segment midpoint coordinates |

#### pi_segments (280 records)
Pressurized irrigation system pipeline inventory.

| Column | Type | Description |
|---|---|---|
| segment_id | VARCHAR | Primary key (PI-XXXX) |
| system_type | VARCHAR | "PI" (Pressurized Irrigation) |
| subdivision_name | VARCHAR | One of 14 served subdivisions |
| district | VARCHAR | Service district (multiple districts) |
| pipe_material | VARCHAR | PVC PR-SDR, PVC C900, HDPE |
| diameter_inches | INT | Pipe diameter (2"–12") |
| length_ft | INT | Segment length in linear feet |
| depth_ft | FLOAT | Burial depth |
| install_year | INT | Year installed (1990–2020) |
| asset_age_years | INT | Current age in years |
| condition_score | INT | 1-100 scale (from visual/pressure tests) |
| pressure_rating_psi | FLOAT | Design operating pressure |
| seasonal_status | VARCHAR | Active (Apr 15–Oct 15) / Inactive |
| capacity_utilization_pct | FLOAT | Flow utilization % (seasonal) |
| criticality_class | VARCHAR | Main Feed, District Line, Lateral, etc. |
| estimated_replacement_cost_usd | INT | Planning-level replacement cost |
| last_inspection_date | DATE | Most recent inspection date |
| lat, lon | FLOAT | Segment midpoint coordinates |

#### all_segments (4,830 records)
Combined view of all segments with union of fields above.

### work_orders (600 records)
Maintenance and repair work order history linked to pipe segments across all systems.

| Column | Type | Description |
|---|---|---|
| work_order_id | VARCHAR | Primary key (WO-XXXX) |
| segment_id | VARCHAR | Foreign key to segment tables |
| system_type | VARCHAR | Sewer, Geothermal, PI |
| work_order_type | VARCHAR | Repair, Rehabilitation, Replacement, Inspection, Maintenance |
| priority | VARCHAR | Critical, High, Medium, Low |
| crew_assigned | VARCHAR | Crew ID or contractor name |
| cost_usd | INT | Actual or estimated cost |
| scheduled_date | DATE | Work scheduled date |
| completion_date | DATE | Actual completion date (or null if pending) |
| notes | TEXT | Description of work performed |

### service_requests (900 records)
Citizen-reported service requests (311 system) by system.

| Column | Type | Description |
|---|---|---|
| request_id | VARCHAR | Primary key (SR-XXXX) |
| segment_id | VARCHAR | Associated segment (if applicable) |
| system_type | VARCHAR | Sewer, Geothermal, PI, or General |
| request_type | VARCHAR | Backup/overflow, Leak, Low pressure, Odor, Service outage, etc. |
| severity | VARCHAR | Critical, High, Medium, Low |
| report_date | DATE | Date reported |
| resolution_date | DATE | Date resolved (or null) |
| resolution_status | VARCHAR | Resolved, Pending, In-Progress |
| description | TEXT | Complainant description |

### facilities (11 records)
Treatment plants, pump stations, geothermal wells, and PI infrastructure.

| Column | Type | Description |
|---|---|---|
| facility_id | VARCHAR | Primary key (FAC-XXXX) |
| facility_name | VARCHAR | Lander Street WRF, West Boise WRF, Lift Station #5, Geo Well #1, PI Pump #3, etc. |
| system_type | VARCHAR | Sewer, Geothermal, PI |
| facility_type | VARCHAR | WRF, Lift Station, Production Well, Injection Well, Pump Station |
| location | VARCHAR | Address/coordinates |
| capacity | FLOAT | Design capacity (MGD, GPM, gpm, etc. by system) |
| commissioning_year | INT | Year constructed |
| condition_rating | VARCHAR | Excellent, Good, Fair, Poor |
| last_maintenance | DATE | Most recent maintenance date |
| depth_ft | FLOAT | For wells — drilling depth |
| temperature_f | FLOAT | For geothermal — water temperature |

### monitoring_data (1,440+ records)
Monthly flow, pressure, and temperature monitoring data by segment.

| Column | Type | Description |
|---|---|---|
| monitoring_id | VARCHAR | Primary key |
| segment_id | VARCHAR | Foreign key to segment tables |
| system_type | VARCHAR | Sewer, Geothermal, PI |
| month_year | DATE | Date of measurement (first of month) |
| avg_flow_pct | FLOAT | Average capacity utilization (Sewer/PI) |
| peak_flow_pct | FLOAT | Peak capacity utilization (Sewer/PI) |
| temperature_f | FLOAT | Water temperature (Geothermal/Sewer) |
| pressure_psi | FLOAT | Operating pressure (PI, Geothermal) |
| i_and_i_flag | BOOLEAN | Inflow/Infiltration indicator (Sewer) |
| notes | TEXT | Quality flags or issues |

### budget_cip (30 records)
Capital Improvement Program budget allocation by fiscal year, district, and system type.

| Column | Type | Description |
|---|---|---|
| budget_id | VARCHAR | Primary key |
| fiscal_year | INT | Budget fiscal year |
| district | VARCHAR | Service district |
| system_type | VARCHAR | Sewer, Geothermal, PI, or Total |
| budgeted_amount_usd | INT | Planned CIP allocation |
| percent_of_total | FLOAT | % of total utility budget |
| notes | TEXT | Planning notes |

### weather_events (150 records)
Precipitation and weather events for correlation analysis.

| Column | Type | Description |
|---|---|---|
| event_id | VARCHAR | Primary key |
| event_date | DATE | Date of precipitation event |
| precipitation_inches | FLOAT | Rainfall depth |
| event_type | VARCHAR | Thunderstorm, Rain, Snowmelt, etc. |
| peak_intensity_in_per_hr | FLOAT | Peak rainfall rate |
| duration_hours | INT | Duration of event |
| notes | TEXT | Observed impacts (flooding, SSOs, etc.) |

## Relationships

```
sewer_segments (segment_id)   ─┬─ work_orders (segment_id)
geothermal_segments (seg_id)  ─┤  service_requests (segment_id)
pi_segments (segment_id)      ─┼─ monitoring_data (segment_id)
                              │
all_segments (union)          ─┼─ budget_cip (district)
                              │
facilities ────────────────────  (standalone dimension by system_type)
weather_events ───────────────  (standalone dimension, joins on date for correlation)
```

## Material Types by System

### Sewer System Materials

| Material | Era | Risk Factor |
|---|---|---|
| Vitrified Clay | Pre-1970 | 0.60 |
| Orangeburg | 1940s–1970s | 0.95 |
| Cast Iron | Pre-1960 | 0.90 |
| Ductile Iron | 1965+ | 0.30 |
| Concrete | All eras | 0.45 |
| PVC | 1970+ | 0.15 |
| HDPE | 1990+ | 0.10 |

### Geothermal System Materials

| Material | Era | Risk Factor |
|---|---|---|
| Steel | 1980–2000 | 0.40 |
| Pre-insulated Steel | 2000+ | 0.20 |
| Transite | 1980–1995 | 0.50 |
| HDPE | 2000+ | 0.10 |

### Pressurized Irrigation Materials

| Material | Era | Risk Factor |
|---|---|---|
| PVC PR-SDR | 1990–2010 | 0.20 |
| PVC C900 | 2000+ | 0.15 |
| HDPE | 2005+ | 0.10 |

## Service Districts

North End, Downtown, East Bench, Southeast, Southwest, West Boise — each with distinct infrastructure age profiles and material mixes reflecting Boise's development history.
