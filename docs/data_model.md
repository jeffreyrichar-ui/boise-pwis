# Data Model Documentation
## Boise Public Works Intelligence System (PWIS)

**Document Type:** Technical Data Architecture
**Phase:** 2 — Data Design
**Status:** Baseline v1.0

---

## 1. Design Philosophy

The PWIS data layer is designed around three principles:

1. **Decision-readiness over completeness** — every table exists to answer a specific analytical question, not to replicate source system schemas
2. **Star-schema analytics layer** — the dimensional model separates facts from dimensions, enabling reusable Power BI semantic models and fast SQL aggregations
3. **Graceful degradation** — the system runs with partial data; missing fields produce confidence warnings, not failures

---

## 2. Dimensional Data Model (Star Schema)

The analytics layer is organized as a star schema centered on infrastructure investment decisions.

### 2.1 Schema Diagram

```
                        ┌─────────────────────┐
                        │   DIM_DATE          │
                        │─────────────────────│
                        │ date_key (PK)        │
                        │ full_date            │
                        │ year, quarter        │
                        │ month, month_name    │
                        │ fiscal_year          │
                        │ is_weekend           │
                        └──────────┬──────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────┴──────────┐  ┌──────────┴──────────┐  ┌────────┴───────────┐
│  DIM_SEGMENT       │  │  FACT_WORK_ACTIVITY  │  │  DIM_DISTRICT      │
│────────────────────│  │─────────────────────│  │────────────────────│
│ segment_key (PK)   │  │ activity_key (PK)   │  │ district_key (PK)  │
│ segment_id (NK)    │◄─┤ segment_key (FK)    ├─►│ district_id (NK)   │
│ street_name        │  │ date_key (FK)       │  │ district_name      │
│ district_key (FK)  │  │ district_key (FK)   │  │ population_2020    │
│ road_type          │  │ work_type_key (FK)  │  │ area_sq_miles      │
│ surface_type       │  │ condition_index     │  │ council_district    │
│ condition_index    │  │ aadt                │  └────────────────────┘
│ paser_rating       │  │ complaint_count     │
│ install_year       │  │ actual_cost_usd     │
│ length_miles       │  │ estimated_cost_usd  │
│ num_lanes          │  │ hours_spent         │
│ lat, lon           │  │ priority_score      │
│ is_active          │  │ work_order_status   │
└────────────────────┘  └──────────┬──────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────┴──────────┐  ┌──────────┴──────────┐  ┌────────┴───────────┐
│  DIM_WORK_TYPE     │  │  FACT_CONDITION      │  │  DIM_WEATHER       │
│────────────────────│  │─────────────────────│  │────────────────────│
│ work_type_key (PK) │  │ condition_key (PK)  │  │ weather_key (PK)   │
│ work_type_code     │  │ segment_key (FK)    │  │ event_type         │
│ work_category      │  │ date_key (FK)       │  │ severity_level     │
│ avg_cost_per_mile  │  │ weather_key (FK)    │  │ precip_inches      │
│ typical_duration   │  │ condition_index     │  │ min_temp_f         │
│ is_preventive      │  │ paser_rating        │  │ estimated_damage   │
└────────────────────┘  │ defect_type         │  └────────────────────┘
                        │ inspection_source   │
                        └─────────────────────┘
```

### 2.2 Grain Definitions

| Fact Table | Grain (One Row = ...) | Update Frequency |
|------------|----------------------|-----------------|
| `FACT_WORK_ACTIVITY` | One work order event per segment per date | Daily |
| `FACT_CONDITION` | One condition snapshot per segment per inspection date | Per inspection (~quarterly) |
| `FACT_COMPLAINT` | One citizen complaint per segment per date | Real-time (daily batch) |
| `FACT_BUDGET` | One budget allocation per district per fiscal year | Annual |

---

## 3. Source Tables (Operational Layer)

### 3.1 road_segments.csv

**Purpose:** Master asset registry for all road segments.
**Grain:** One row per road segment.

| Column | Type | Description | Constraints |
|--------|------|-------------|-------------|
| `segment_id` | VARCHAR(12) | Unique segment identifier (NK) | NOT NULL, UNIQUE |
| `street_name` | VARCHAR(100) | Street name and type | NOT NULL |
| `district` | VARCHAR(50) | City district | NOT NULL, FK to districts |
| `road_type` | VARCHAR(20) | Arterial/Collector/Local/Highway | NOT NULL |
| `surface_type` | VARCHAR(20) | Asphalt/Concrete/Chip Seal | NOT NULL |
| `condition_index` | INT | 1–100 (higher = better) | BETWEEN 1 AND 100 |
| `paser_rating` | INT | PASER scale 1–10 | BETWEEN 1 AND 10 |
| `install_year` | INT | Year of last major construction | BETWEEN 1900 AND 2026 |
| `asset_age_years` | INT | Computed: 2026 - install_year | >= 0 |
| `length_miles` | FLOAT | Segment length in miles | > 0 |
| `lane_width_ft` | INT | Lane width (feet) | IN (10, 11, 12) |
| `num_lanes` | INT | Number of travel lanes | BETWEEN 1 AND 8 |
| `daily_traffic_aadt` | INT | Annual average daily traffic | >= 0 |
| `lat` | FLOAT | Centroid latitude | BETWEEN 43.5 AND 43.8 |
| `lon` | FLOAT | Centroid longitude | BETWEEN -116.4 AND -116.0 |
| `last_inspection_date` | DATE | Most recent inspection date | NOT NULL |
| `last_treatment_year` | INT | Year of last maintenance treatment | <= 2026 |
| `estimated_repair_cost_usd` | INT | Current repair cost estimate | > 0 |

### 3.2 work_orders.csv

**Purpose:** Tracks all maintenance and repair activities.
**Grain:** One row per work order.

| Column | Type | Description |
|--------|------|-------------|
| `work_order_id` | VARCHAR(12) | Unique WO identifier |
| `segment_id` | VARCHAR(12) | FK to road_segments |
| `district` | VARCHAR(50) | Denormalized for query performance |
| `work_order_type` | VARCHAR(50) | Type of work performed |
| `status` | VARCHAR(20) | Open/In Progress/Completed/Deferred |
| `priority` | VARCHAR(10) | Critical/High/Medium/Low |
| `created_date` | DATE | Date WO was created |
| `completed_date` | DATE | Date WO was closed (NULL if not complete) |
| `crew_assigned` | VARCHAR(20) | Crew identifier |
| `estimated_hours` | FLOAT | Planned labor hours |
| `actual_hours` | FLOAT | Actual labor hours (NULL if not complete) |
| `estimated_cost_usd` | INT | Budget estimate |
| `actual_cost_usd` | INT | Final cost (NULL if not complete) |
| `source` | VARCHAR(30) | Inspection/311 Complaint/Crew Report/Scheduled PM |

### 3.3 complaints.csv

**Purpose:** Citizen 311 complaint intake records.
**Grain:** One row per complaint submission.

| Column | Type | Description |
|--------|------|-------------|
| `complaint_id` | VARCHAR(12) | Unique complaint ID |
| `segment_id` | VARCHAR(12) | Matched road segment (GIS-matched) |
| `district` | VARCHAR(50) | Resolved district |
| `complaint_type` | VARCHAR(30) | Pothole/Crack/Flooding/etc. |
| `submitted_date` | DATE | Date submitted |
| `resolved_date` | DATE | Date closed (NULL if pending) |
| `resolution_status` | VARCHAR(20) | Resolved/Pending/In Review |
| `severity_reported` | VARCHAR(10) | Low/Medium/High/Critical |
| `channel` | VARCHAR(20) | 311 App/Phone/Web Form/Email |

### 3.4 traffic_counts.csv

**Purpose:** Monthly traffic volume by segment.
**Grain:** One row per segment per month.

| Column | Type | Description |
|--------|------|-------------|
| `traffic_id` | VARCHAR | Composite key |
| `segment_id` | VARCHAR(12) | FK to road_segments |
| `year` | INT | Measurement year |
| `month` | INT | Measurement month (1–12) |
| `aadt` | INT | Average annual daily traffic |
| `heavy_vehicle_pct` | FLOAT | % heavy vehicles (trucks, buses) |
| `peak_hour_volume` | INT | Highest single-hour volume |
| `congestion_index` | FLOAT | 0.0 (free flow) to 1.0 (gridlock) |

### 3.5 weather_events.csv

**Purpose:** Records significant weather events affecting infrastructure.
**Grain:** One row per weather event.

| Column | Type | Description |
|--------|------|-------------|
| `weather_event_id` | VARCHAR | Unique event ID |
| `event_date` | DATE | Event date |
| `event_type` | VARCHAR | Rain/Snow/Ice Storm/Freeze-Thaw/etc. |
| `duration_hours` | FLOAT | Duration in hours |
| `precipitation_inches` | FLOAT | Total precipitation |
| `min_temp_f` | FLOAT | Minimum temperature |
| `district_affected` | VARCHAR | District or 'All' |
| `estimated_damage_usd` | INT | Estimated infrastructure damage |
| `work_orders_triggered` | INT | WOs created within 72 hours |

### 3.6 bridge_inspections.csv

**Purpose:** Bridge condition data (FHWA-aligned).
**Grain:** One row per bridge.

| Column | Type | Description |
|--------|------|-------------|
| `bridge_id` | VARCHAR | FHWA-style bridge identifier |
| `bridge_name` | VARCHAR | Descriptive name |
| `deck_condition` | VARCHAR | Good/Fair/Poor/Critical |
| `superstructure_condition` | VARCHAR | Good/Fair/Poor |
| `substructure_condition` | VARCHAR | Good/Fair/Poor |
| `sufficiency_rating` | FLOAT | FHWA sufficiency rating (0–100) |
| `estimated_repair_cost_usd` | INT | Current repair estimate |

---

## 4. SQL Implementation — Dimensional Model

```sql
-- ═══════════════════════════════════════════════════════════════════════
-- PWIS Star Schema DDL
-- Database: PostgreSQL 15+ (or SQLite for local development)
-- ═══════════════════════════════════════════════════════════════════════

-- ─── DIMENSIONS ─────────────────────────────────────────────────────────────

CREATE TABLE DIM_DATE (
    date_key        INT PRIMARY KEY,          -- YYYYMMDD integer key
    full_date       DATE NOT NULL,
    year            INT NOT NULL,
    quarter         INT NOT NULL,
    month           INT NOT NULL,
    month_name      VARCHAR(10) NOT NULL,
    week_of_year    INT NOT NULL,
    day_of_week     INT NOT NULL,
    day_name        VARCHAR(10) NOT NULL,
    fiscal_year     INT NOT NULL,             -- Boise FY: Oct 1 – Sep 30
    fiscal_quarter  INT NOT NULL,
    is_weekend      BOOLEAN NOT NULL,
    is_holiday      BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE DIM_DISTRICT (
    district_key    SERIAL PRIMARY KEY,
    district_id     VARCHAR(20) NOT NULL UNIQUE,
    district_name   VARCHAR(50) NOT NULL,
    population_2020 INT,
    area_sq_miles   FLOAT,
    council_district INT,
    region          VARCHAR(20),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE DIM_SEGMENT (
    segment_key     SERIAL PRIMARY KEY,
    segment_id      VARCHAR(12) NOT NULL UNIQUE,  -- Natural key
    street_name     VARCHAR(100) NOT NULL,
    district_key    INT REFERENCES DIM_DISTRICT(district_key),
    road_type       VARCHAR(20) NOT NULL,
    surface_type    VARCHAR(20) NOT NULL,
    install_year    INT,
    length_miles    FLOAT NOT NULL,
    lane_width_ft   INT,
    num_lanes       INT,
    lat             FLOAT,
    lon             FLOAT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from  DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to    DATE                            -- SCD Type 2 support
);

CREATE TABLE DIM_WORK_TYPE (
    work_type_key   SERIAL PRIMARY KEY,
    work_type_code  VARCHAR(30) NOT NULL UNIQUE,
    work_type_name  VARCHAR(100) NOT NULL,
    work_category   VARCHAR(30) NOT NULL,          -- Preventive/Reactive/Capital
    is_preventive   BOOLEAN NOT NULL,
    avg_cost_per_mile FLOAT,
    typical_duration_hrs FLOAT
);

CREATE TABLE DIM_WEATHER (
    weather_key     SERIAL PRIMARY KEY,
    event_type      VARCHAR(30) NOT NULL,
    severity_level  VARCHAR(10) NOT NULL,          -- Low/Medium/High/Extreme
    precip_inches   FLOAT,
    min_temp_f      FLOAT,
    estimated_damage_usd INT
);

-- ─── FACT TABLES ─────────────────────────────────────────────────────────────

CREATE TABLE FACT_WORK_ACTIVITY (
    activity_key        BIGSERIAL PRIMARY KEY,
    work_order_id       VARCHAR(12) NOT NULL UNIQUE,  -- Degenerate dimension
    segment_key         INT REFERENCES DIM_SEGMENT(segment_key),
    district_key        INT REFERENCES DIM_DISTRICT(district_key),
    created_date_key    INT REFERENCES DIM_DATE(date_key),
    completed_date_key  INT REFERENCES DIM_DATE(date_key),
    work_type_key       INT REFERENCES DIM_WORK_TYPE(work_type_key),
    -- Measures
    estimated_cost_usd  NUMERIC(12,2),
    actual_cost_usd     NUMERIC(12,2),
    cost_variance_usd   NUMERIC(12,2) GENERATED ALWAYS AS (actual_cost_usd - estimated_cost_usd) STORED,
    estimated_hours     FLOAT,
    actual_hours        FLOAT,
    priority_score      FLOAT,                     -- PWIS model score at time of WO creation
    work_order_status   VARCHAR(20) NOT NULL,
    source_system       VARCHAR(30)
);

CREATE TABLE FACT_CONDITION (
    condition_key       BIGSERIAL PRIMARY KEY,
    segment_key         INT REFERENCES DIM_SEGMENT(segment_key),
    inspection_date_key INT REFERENCES DIM_DATE(date_key),
    weather_key         INT REFERENCES DIM_WEATHER(weather_key),
    -- Measures
    condition_index     INT NOT NULL,              -- 1–100
    paser_rating        INT NOT NULL,              -- 1–10
    aadt                INT,
    heavy_vehicle_pct   FLOAT,
    inspection_source   VARCHAR(30),
    inspector_id        VARCHAR(20),
    notes               TEXT
);

CREATE TABLE FACT_COMPLAINT (
    complaint_key       BIGSERIAL PRIMARY KEY,
    complaint_id        VARCHAR(12) NOT NULL UNIQUE,
    segment_key         INT REFERENCES DIM_SEGMENT(segment_key),
    district_key        INT REFERENCES DIM_DISTRICT(district_key),
    submitted_date_key  INT REFERENCES DIM_DATE(date_key),
    resolved_date_key   INT REFERENCES DIM_DATE(date_key),
    -- Measures
    complaint_type      VARCHAR(30),
    severity_score      INT,                       -- 1=Low, 2=Med, 3=High, 4=Critical
    resolution_days     INT GENERATED ALWAYS AS (resolved_date_key - submitted_date_key) STORED,
    channel             VARCHAR(20),
    is_resolved         BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE FACT_BUDGET (
    budget_key          BIGSERIAL PRIMARY KEY,
    district_key        INT REFERENCES DIM_DISTRICT(district_key),
    fiscal_year         INT NOT NULL,
    -- Measures
    allocated_budget_usd    NUMERIC(14,2),
    spent_budget_usd        NUMERIC(14,2),
    variance_usd            NUMERIC(14,2) GENERATED ALWAYS AS (spent_budget_usd - allocated_budget_usd) STORED,
    preventive_pct          FLOAT,
    reactive_pct            FLOAT,
    capital_pct             FLOAT,
    projects_completed      INT,
    citizen_satisfaction    FLOAT
);

-- ─── INDEXES ─────────────────────────────────────────────────────────────────

CREATE INDEX idx_fact_work_segment      ON FACT_WORK_ACTIVITY(segment_key);
CREATE INDEX idx_fact_work_date         ON FACT_WORK_ACTIVITY(created_date_key);
CREATE INDEX idx_fact_work_district     ON FACT_WORK_ACTIVITY(district_key);
CREATE INDEX idx_fact_condition_segment ON FACT_CONDITION(segment_key);
CREATE INDEX idx_fact_complaint_segment ON FACT_COMPLAINT(segment_key);
CREATE INDEX idx_fact_complaint_date    ON FACT_COMPLAINT(submitted_date_key);
```

---

## 5. Key SQL Transformation Queries

### 5.1 Segment-Level KPI Rollup (Used by Prioritization Model)

```sql
-- PWIS Core Analytics View: Segment KPI Aggregation
-- Joins road condition, complaint volume, traffic, and maintenance history
-- Window functions compute rolling averages and district-relative rankings

CREATE OR REPLACE VIEW vw_segment_kpi AS
WITH complaint_summary AS (
    SELECT
        s.segment_id,
        COUNT(c.complaint_key)                          AS total_complaints_2yr,
        SUM(CASE WHEN c.severity_score >= 3 THEN 1 ELSE 0 END) AS high_severity_complaints,
        AVG(c.resolution_days)                          AS avg_resolution_days
    FROM DIM_SEGMENT s
    LEFT JOIN FACT_COMPLAINT c ON s.segment_key = c.segment_key
        AND c.submitted_date_key >= 20240101
    GROUP BY s.segment_id
),
work_order_summary AS (
    SELECT
        s.segment_id,
        COUNT(wa.activity_key)                          AS total_work_orders,
        SUM(wa.actual_cost_usd)                         AS total_spend_usd,
        MAX(wa.created_date_key)                        AS last_wo_date_key,
        SUM(CASE WHEN wt.is_preventive THEN 1 ELSE 0 END) AS preventive_wo_count,
        SUM(CASE WHEN NOT wt.is_preventive THEN 1 ELSE 0 END) AS reactive_wo_count
    FROM DIM_SEGMENT s
    LEFT JOIN FACT_WORK_ACTIVITY wa ON s.segment_key = wa.segment_key
    LEFT JOIN DIM_WORK_TYPE wt ON wa.work_type_key = wt.work_type_key
    GROUP BY s.segment_id
),
latest_condition AS (
    SELECT DISTINCT ON (s.segment_id)
        s.segment_id,
        fc.condition_index,
        fc.paser_rating,
        fc.aadt,
        d.full_date AS last_inspection_date
    FROM DIM_SEGMENT s
    JOIN FACT_CONDITION fc ON s.segment_key = fc.segment_key
    JOIN DIM_DATE d ON fc.inspection_date_key = d.date_key
    ORDER BY s.segment_id, fc.inspection_date_key DESC
)
SELECT
    s.segment_id,
    s.street_name,
    dd.district_name,
    s.road_type,
    s.length_miles,
    lc.condition_index,
    lc.paser_rating,
    lc.aadt,
    cs.total_complaints_2yr,
    cs.high_severity_complaints,
    cs.avg_resolution_days,
    ws.total_work_orders,
    ws.total_spend_usd,
    ws.preventive_wo_count,
    ws.reactive_wo_count,
    -- Window functions for district-relative ranking
    RANK() OVER (
        PARTITION BY dd.district_name
        ORDER BY lc.condition_index ASC
    )                                                   AS district_condition_rank,
    PERCENT_RANK() OVER (
        PARTITION BY s.road_type
        ORDER BY lc.condition_index DESC
    )                                                   AS road_type_percentile,
    -- Rolling 12-month complaint trend (normalized)
    AVG(cs.total_complaints_2yr) OVER (
        PARTITION BY dd.district_name
    )                                                   AS district_avg_complaints,
    -- Composite urgency flag
    CASE
        WHEN lc.condition_index < 25 AND lc.aadt > 10000 THEN 'CRITICAL'
        WHEN lc.condition_index < 40 AND lc.aadt > 5000  THEN 'HIGH'
        WHEN lc.condition_index < 55                      THEN 'MEDIUM'
        ELSE 'LOW'
    END                                                 AS urgency_flag
FROM DIM_SEGMENT s
JOIN DIM_DISTRICT dd ON s.district_key = dd.district_key
LEFT JOIN latest_condition lc   ON s.segment_id = lc.segment_id
LEFT JOIN complaint_summary cs  ON s.segment_id = cs.segment_id
LEFT JOIN work_order_summary ws ON s.segment_id = ws.segment_id;
```

### 5.2 KPI Query — District Infrastructure Health Index

```sql
-- District-level Infrastructure Health Index
-- Weighted composite of condition, complaints, and maintenance ratio

SELECT
    dd.district_name,
    COUNT(s.segment_key)                                AS total_segments,
    ROUND(AVG(fc.condition_index), 1)                   AS avg_condition_index,
    ROUND(
        (AVG(fc.condition_index) * 0.5
        + (100 - AVG(cp.complaints_per_mile)) * 0.3
        + (ws.preventive_pct) * 0.2), 1
    )                                                   AS infrastructure_health_index,
    SUM(s.length_miles)                                 AS total_lane_miles,
    SUM(CASE WHEN fc.condition_index < 40 THEN 1 ELSE 0 END) AS poor_segments,
    SUM(CASE WHEN fc.condition_index < 40 THEN s.length_miles ELSE 0 END) AS poor_lane_miles,
    ROUND(fb.allocated_budget_usd / SUM(s.length_miles), 0) AS budget_per_lane_mile
FROM DIM_DISTRICT dd
JOIN DIM_SEGMENT s          ON dd.district_key = s.district_key
JOIN FACT_CONDITION fc      ON s.segment_key = fc.segment_key
LEFT JOIN (
    SELECT segment_key,
           COUNT(*) / NULLIF(SUM(seg.length_miles),0) AS complaints_per_mile
    FROM FACT_COMPLAINT cp2
    JOIN DIM_SEGMENT seg ON cp2.segment_key = seg.segment_key
    GROUP BY segment_key
) cp ON s.segment_key = cp.segment_key
LEFT JOIN (
    SELECT district_key,
           AVG(preventive_pct) AS preventive_pct
    FROM FACT_BUDGET
    WHERE fiscal_year = 2025
    GROUP BY district_key
) ws ON dd.district_key = ws.district_key
LEFT JOIN (
    SELECT district_key, SUM(allocated_budget_usd) AS allocated_budget_usd
    FROM FACT_BUDGET WHERE fiscal_year = 2026 GROUP BY district_key
) fb ON dd.district_key = fb.district_key
GROUP BY dd.district_name, fb.allocated_budget_usd, ws.preventive_pct
ORDER BY infrastructure_health_index DESC;
```

---

## 6. Data Quality Rules

| Rule ID | Table | Column | Rule Type | Validation Logic |
|---------|-------|--------|-----------|-----------------|
| DQ-001 | road_segments | condition_index | Range | BETWEEN 1 AND 100 |
| DQ-002 | road_segments | lat/lon | Bounds | lat IN [43.5, 43.8], lon IN [-116.4, -116.0] |
| DQ-003 | road_segments | install_year | Range | BETWEEN 1900 AND CURRENT_YEAR |
| DQ-004 | work_orders | completed_date | Temporal | completed_date >= created_date |
| DQ-005 | work_orders | actual_cost_usd | Business | actual_cost NOT NULL when status = 'Completed' |
| DQ-006 | complaints | resolved_date | Temporal | resolved_date >= submitted_date |
| DQ-007 | traffic_counts | aadt | Range | aadt > 0 |
| DQ-008 | bridge_inspections | sufficiency_rating | Range | BETWEEN 0 AND 100 |
| DQ-009 | budget_actuals | preventive_pct + reactive_pct + capital_pct | Sum | SUM <= 100 |
| DQ-010 | road_segments | segment_id | Uniqueness | No duplicates in segment_id |

---

## 7. Master Data Management

### 7.1 Standardized Identifiers

| Entity | ID Format | Source Authority | Example |
|--------|-----------|-----------------|---------|
| Road Segment | `SEG-NNNN` | GIS Department | SEG-0042 |
| Work Order | `WO-NNNNN` | CMMS (Cityworks) | WO-00127 |
| Complaint | `CMP-NNNNN` | 311 CRM | CMP-00891 |
| Bridge | `BRG-NNN` | State Bridge Database | BRG-014 |
| Weather Event | `WX-NNNN` | National Weather Service | WX-0023 |

### 7.2 District Reference Table (MDM)

The `DIM_DISTRICT` table serves as the master reference for all geographic grouping. Any system feeding into PWIS must use the standard district name — no abbreviations, no variants.

**Canonical district names:**
```
North End | Downtown | East Bench | Southeast | Southwest | West Boise
```

### 7.3 GIS Integration

All point geometries (lat/lon) use **WGS84 (EPSG:4326)**. For spatial analysis requiring projected coordinates, the system transforms to **NAD83 / Idaho West (EPSG:8827)** for distance and area calculations.

Road segment centroids are computed from the segment midpoint in the GIS layer and stored in road_segments.csv. Complaint and work order coordinates are GPS-captured at the point of issue, then GIS-matched to the nearest segment within 50 meters.

---

## 8. Data Limitations and Assumptions

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| All data is synthetic | Cannot validate against real Boise conditions | Schema matches APWA/PASER standards; real data drop-in ready |
| No real-time data feeds | Condition data may be stale | Inspection date tracking; staleness flag if >180 days |
| Single condition snapshot per segment | Can't compute deterioration rate | Design supports multiple snapshots; Rate-of-deterioration model is Phase 2 enhancement |
| Traffic counts are monthly averages | Miss event-driven spikes | Peak hour volume field captures this partially |
| Complaint-to-segment matching is approximate | Some complaints mislabeled | GIS matching logic documented; 50m buffer is adjustable |
| No actual cost data for open WOs | Budget projection uncertainty | Monte Carlo simulation using historical cost distributions (Scenario Engine) |

---

*Data model designed to integrate directly with Power BI semantic layer. See `docs/bi_maturity.md` for DAX measures and Row-Level Security design.*
