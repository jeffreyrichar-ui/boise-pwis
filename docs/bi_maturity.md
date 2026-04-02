# BI Maturity Layer
## Boise Public Works Intelligence System (PWIS)

**Document Type:** BI Architecture, Power BI Design, Governance
**Phase:** 9 — Enterprise BI Maturity
**Status:** v1.0 — Design Specification

---

## 1. BI Maturity Overview

PWIS is designed to operate at **Level 4 (Insight-Driven)** on the Gartner BI Maturity Model:

| Level | Name | Characteristics | PWIS Status |
|-------|------|----------------|-------------|
| 1 | Reporting | Static reports, manual Excel | Replaced |
| 2 | Analysis | Ad-hoc queries, basic dashboards | Baseline |
| 3 | Monitoring | KPIs, alerts, scheduled reports | Implemented |
| **4** | **Insight-Driven** | **Predictive scoring, scenario simulation, decision support** | **PWIS Target** |
| 5 | Optimized | Fully automated decisions, continuous learning | Phase 3 Roadmap |

This document specifies the components that make PWIS a Level 4 system: a reusable semantic model, governed DAX measures, Row-Level Security, and an enterprise-grade deployment pipeline.

---

## 2. Power BI Architecture

### 2.1 Semantic Model Design

The PWIS Power BI semantic model is built on the star schema defined in `docs/data_model.md`. The semantic model is the **single source of truth** — all reports, dashboards, and ad-hoc analyses connect to this model rather than raw data sources.

```
                    ┌─────────────────────┐
                    │  PWIS Semantic Model │
                    │  (Power BI Dataset)  │
                    └──────────┬──────────┘
                               │ Single shared model
          ┌────────────────────┼────────────────────┐
          │                    │                    │
   ┌──────┴──────┐    ┌────────┴───────┐    ┌──────┴──────┐
   │ Executive   │    │ Operations     │    │ Council     │
   │ Dashboard   │    │ Work Queue     │    │ Briefing    │
   │ (Published) │    │ (Published)    │    │ (PDF Export)│
   └─────────────┘    └────────────────┘    └─────────────┘
```

**Principle:** Build once, use many. Any analyst can create a new report by connecting to the shared dataset — they do not need to rebuild relationships, write transformations, or re-apply RLS.

### 2.2 Data Model Relationships

```
DIM_DATE ──────────────────────────────── FACT_WORK_ACTIVITY
    │                                            │
    │                                     FACT_CONDITION
    │                                            │
DIM_DISTRICT ◄── DIM_SEGMENT ──────────► FACT_COMPLAINT
                     │                          │
              DIM_WORK_TYPE              FACT_BUDGET
                                                │
                                         DIM_WEATHER
```

All relationships are **one-to-many** from dimensions to facts. No bidirectional cross-filtering except where explicitly required (documented below).

**Cross-filter exceptions:**
- `DIM_SEGMENT ↔ FACT_CONDITION`: Bidirectional to allow filtering segments by condition range
- All other relationships: Single-direction (dim → fact) for performance

### 2.3 Calculated Columns vs. Measures

**Rule:** All aggregations are DAX measures. Calculated columns are only used for static categorization (e.g., condition tier labeling, date attributes) that does not depend on filter context.

---

## 3. DAX Measures — Complete Library

### 3.1 Infrastructure Condition Measures

```dax
-- ─── CONDITION MEASURES ───────────────────────────────────────────────────────

-- Average condition index (respects all slicers)
[Avg Condition Index] =
AVERAGEX(
    FILTER(
        DIM_SEGMENT,
        DIM_SEGMENT[is_active] = TRUE()
    ),
    RELATED(FACT_CONDITION[condition_index])
)

-- % of network in poor condition (CI < 40)
[% Poor Condition] =
DIVIDE(
    CALCULATE(
        COUNTROWS(DIM_SEGMENT),
        FACT_CONDITION[condition_index] < 40
    ),
    CALCULATE(
        COUNTROWS(DIM_SEGMENT),
        DIM_SEGMENT[is_active] = TRUE()
    ),
    0
)

-- Lane miles in poor condition
[Poor Lane Miles] =
CALCULATE(
    SUMX(DIM_SEGMENT, DIM_SEGMENT[length_miles]),
    FACT_CONDITION[condition_index] < 40
)

-- Infrastructure Condition Index (ICI) — citywide composite
-- ICI = weighted avg of condition, weighted by lane-miles
[Infrastructure Condition Index] =
DIVIDE(
    SUMX(
        ADDCOLUMNS(
            DIM_SEGMENT,
            "WeightedCI",
            DIM_SEGMENT[length_miles] * RELATED(FACT_CONDITION[condition_index])
        ),
        [WeightedCI]
    ),
    SUM(DIM_SEGMENT[length_miles]),
    0
)

-- YoY condition change (requires date dimension with prior year)
[YoY Condition Change] =
VAR CurrentICI = [Infrastructure Condition Index]
VAR PriorYearICI =
    CALCULATE(
        [Infrastructure Condition Index],
        SAMEPERIODLASTYEAR(DIM_DATE[full_date])
    )
RETURN
    IF(
        NOT ISBLANK(PriorYearICI),
        CurrentICI - PriorYearICI,
        BLANK()
    )
```

### 3.2 Priority Score Measures

```dax
-- ─── PRIORITY SCORE MEASURES ─────────────────────────────────────────────────

-- Count of segments by tier (use as measure, not column, for RLS compliance)
[Critical Segment Count] =
CALCULATE(
    COUNTROWS(DIM_SEGMENT),
    FACT_CONDITION[priority_tier] = "Critical"
)

[High Segment Count] =
CALCULATE(
    COUNTROWS(DIM_SEGMENT),
    FACT_CONDITION[priority_tier] = "High"
)

-- High + Critical combined (most used in executive reporting)
[Urgent Segment Count] =
[Critical Segment Count] + [High Segment Count]

-- Average priority score (used for district comparisons)
[Avg Priority Score] =
AVERAGE(FACT_CONDITION[priority_score])

-- District Infrastructure Health Index (DIHI)
-- Composite: 50% condition + 30% complaint rate + 20% preventive maintenance ratio
[District Health Index] =
VAR AvgCI = [Avg Condition Index]
VAR ComplaintRate =
    DIVIDE(
        COUNTROWS(FACT_COMPLAINT),
        SUM(DIM_SEGMENT[length_miles]),
        0
    )
VAR NormComplaint = 1 - DIVIDE(ComplaintRate, 10, 0)   -- normalize; 10 = high-complaint benchmark
VAR PreventiveRatio =
    DIVIDE(
        CALCULATE(
            COUNTROWS(FACT_WORK_ACTIVITY),
            DIM_WORK_TYPE[is_preventive] = TRUE()
        ),
        COUNTROWS(FACT_WORK_ACTIVITY),
        0
    )
RETURN
    (AvgCI / 100 * 0.50)
    + (IFERROR(NormComplaint, 0) * 0.30)
    + (PreventiveRatio * 0.20)

-- Trend indicator: is health improving?
[Health Trend] =
VAR Current = [District Health Index]
VAR Prior =
    CALCULATE(
        [District Health Index],
        SAMEPERIODLASTYEAR(DIM_DATE[full_date])
    )
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(Prior), "—",
        Current > Prior + 0.02, "▲ Improving",
        Current < Prior - 0.02, "▼ Declining",
        "→ Stable"
    )
```

### 3.3 Maintenance & Work Order Measures

```dax
-- ─── MAINTENANCE MEASURES ────────────────────────────────────────────────────

-- Total maintenance spend (respects date slicer)
[Total Maintenance Spend] =
SUMX(
    FACT_WORK_ACTIVITY,
    FACT_WORK_ACTIVITY[actual_cost_usd]
)

-- Budget variance (positive = over budget)
[Budget Variance] =
[Total Maintenance Spend] - SUM(FACT_BUDGET[allocated_budget_usd])

-- Budget variance %
[Budget Variance %] =
DIVIDE(
    [Budget Variance],
    SUM(FACT_BUDGET[allocated_budget_usd]),
    0
)

-- Cost per lane mile maintained
[Cost Per Lane Mile] =
DIVIDE(
    [Total Maintenance Spend],
    CALCULATE(
        SUM(DIM_SEGMENT[length_miles]),
        FACT_WORK_ACTIVITY[work_order_status] = "Completed"
    ),
    0
)

-- Preventive vs Reactive ratio
[Preventive Maintenance %] =
DIVIDE(
    CALCULATE(
        [Total Maintenance Spend],
        DIM_WORK_TYPE[is_preventive] = TRUE()
    ),
    [Total Maintenance Spend],
    0
)

-- Average work order completion days
[Avg WO Completion Days] =
AVERAGEX(
    FILTER(
        FACT_WORK_ACTIVITY,
        FACT_WORK_ACTIVITY[work_order_status] = "Completed"
            && NOT ISBLANK(FACT_WORK_ACTIVITY[completed_date_key])
    ),
    FACT_WORK_ACTIVITY[completed_date_key]
    - FACT_WORK_ACTIVITY[created_date_key]
)

-- Work orders completed this period vs prior period
[WO Count] = COUNTROWS(FACT_WORK_ACTIVITY)

[WO Count Prior Period] =
CALCULATE(
    [WO Count],
    PREVIOUSMONTH(DIM_DATE[full_date])
)

[WO Count MoM Change] =
[WO Count] - [WO Count Prior Period]
```

### 3.4 Citizen Complaint Measures

```dax
-- ─── COMPLAINT MEASURES ──────────────────────────────────────────────────────

-- Total complaints in period
[Complaint Count] = COUNTROWS(FACT_COMPLAINT)

-- % resolved within SLA (target: 5 days)
[Complaint Resolution SLA %] =
DIVIDE(
    CALCULATE(
        COUNTROWS(FACT_COMPLAINT),
        FACT_COMPLAINT[resolution_days] <= 5,
        FACT_COMPLAINT[is_resolved] = TRUE()
    ),
    CALCULATE(
        COUNTROWS(FACT_COMPLAINT),
        FACT_COMPLAINT[is_resolved] = TRUE()
    ),
    0
)

-- Average resolution time
[Avg Resolution Days] =
AVERAGEX(
    FILTER(FACT_COMPLAINT, FACT_COMPLAINT[is_resolved] = TRUE()),
    FACT_COMPLAINT[resolution_days]
)

-- Complaint density (per lane mile — equity-normalized)
[Complaint Density] =
DIVIDE(
    [Complaint Count],
    SUM(DIM_SEGMENT[length_miles]),
    0
)

-- High/Critical complaint %
[High Severity Complaint %] =
DIVIDE(
    CALCULATE(
        COUNTROWS(FACT_COMPLAINT),
        FACT_COMPLAINT[severity_score] >= 3
    ),
    [Complaint Count],
    0
)
```

### 3.5 KPI Summary Card Measures

```dax
-- ─── EXECUTIVE KPI MEASURES ──────────────────────────────────────────────────

-- Estimated maintenance backlog ($) for High + Critical segments
[Maintenance Backlog $] =
CALCULATE(
    SUMX(DIM_SEGMENT, DIM_SEGMENT[estimated_repair_cost_usd]),
    FACT_CONDITION[priority_tier] IN {"Critical", "High"}
)

-- 5-year deferral cost premium (estimated)
-- Uses industry-standard 200% average premium for deferred High/Critical work
[5yr Deferral Premium] =
[Maintenance Backlog $] * 2.0

-- Network coverage: % of lane miles inspected within 24 months
[Inspection Currency %] =
DIVIDE(
    CALCULATE(
        SUM(DIM_SEGMENT[length_miles]),
        DATEDIFF(
            MAX(FACT_CONDITION[inspection_date_key]),
            TODAY(),
            DAY
        ) <= 730
    ),
    SUM(DIM_SEGMENT[length_miles]),
    0
)

-- Citizen satisfaction (from budget actuals table)
[Avg Citizen Satisfaction] =
AVERAGE(FACT_BUDGET[citizen_satisfaction])
```

---

## 4. Row-Level Security (RLS)

### 4.1 Security Model

PWIS uses **dynamic RLS** tied to user identity. Security is enforced at the semantic model level — no report-level filtering is required.

```
RLS Role          Who Gets It                  What They See
─────────────────────────────────────────────────────────────────────
pwis_exec         Director, Deputy Directors   All districts, all data
pwis_district_N   District N Manager           District N only
pwis_ops          Operations Manager           All districts, WOs only
pwis_finance      Finance Analyst              Budget + KPIs, no complaints
pwis_readonly     Council Staff, External      Aggregates only, no segment IDs
```

### 4.2 RLS DAX Implementation

```dax
-- ─── DYNAMIC RLS — DIM_DISTRICT TABLE ────────────────────────────────────────

-- Role: pwis_district_manager
-- Filter expression on DIM_DISTRICT table:
[district_name] = LOOKUPVALUE(
    PWIS_UserSecurity[district_name],
    PWIS_UserSecurity[user_email],
    USERPRINCIPALNAME()
)

-- Role: pwis_exec (no filter — sees everything)
-- Leave filter expression blank; dataset shows all rows.

-- Role: pwis_readonly
-- Filter on FACT_COMPLAINT to hide raw complaint data:
-- (Applied as table-level filter, not row filter)
-- Implemented by creating a separate "Complaint Aggregates" table
-- and restricting access to FACT_COMPLAINT in this role.
```

### 4.3 RLS Support Table: PWIS_UserSecurity

```sql
-- User-to-district mapping table (loaded from Azure AD group membership)
CREATE TABLE PWIS_UserSecurity (
    user_email    VARCHAR(100) NOT NULL,
    user_name     VARCHAR(100),
    role          VARCHAR(30) NOT NULL,   -- Maps to RLS role names above
    district_name VARCHAR(50),            -- NULL for exec/citywide roles
    effective_from DATE NOT NULL,
    effective_to   DATE                   -- NULL = currently active
);

-- Sample data
INSERT INTO PWIS_UserSecurity VALUES
  ('jsmith@cityofboise.org',     'John Smith',     'pwis_exec',          NULL,          '2026-01-01', NULL),
  ('mlopez@cityofboise.org',     'Maria Lopez',    'pwis_district_N',    'North End',   '2026-01-01', NULL),
  ('kwilliams@cityofboise.org',  'Kevin Williams', 'pwis_district_N',    'Downtown',    '2026-01-01', NULL),
  ('tchen@cityofboise.org',      'Tina Chen',      'pwis_finance',       NULL,          '2026-01-01', NULL),
  ('councilstaff@cityofboise.org','Council Staff', 'pwis_readonly',      NULL,          '2026-01-01', NULL);
```

### 4.4 RLS Testing Protocol

Before any production deployment, validate RLS by:

1. **Test as district manager:** Log in as `mlopez@cityofboise.org` → verify only North End segments appear
2. **Test as exec:** Log in as `jsmith@cityofboise.org` → verify all 6 districts visible
3. **Test as readonly:** Log in as council staff → verify no raw complaint IDs visible, only aggregated counts
4. **Test cross-district:** Attempt to URL-manipulate a district filter as a district manager → confirm denial
5. Document test results with screenshots in the deployment sign-off checklist

---

## 5. Governance Design

### 5.1 Environment Strategy

PWIS follows a three-tier environment model aligned with City of Boise IT change management policy:

```
┌─────────────┐    Promote    ┌─────────────┐    Promote    ┌─────────────┐
│     DEV     │  ──────────►  │    TEST     │  ──────────►  │    PROD     │
│─────────────│               │─────────────│               │─────────────│
│ Analyst     │               │ QA + UAT    │               │ Live users  │
│ workspace   │               │ environment │               │ production  │
│             │               │             │               │ environment │
│ Synthetic   │               │ Synthetic   │               │ Real data   │
│ data        │               │ + sample    │               │ (masked PII)│
│             │               │ real data   │               │             │
│ No RLS      │               │ Full RLS    │               │ Full RLS    │
│ No alerts   │               │ Test alerts │               │ Live alerts │
└─────────────┘               └─────────────┘               └─────────────┘
     Git branch: dev               Git branch: test             Git branch: main
```

**Environment-specific rules:**

| Rule | DEV | TEST | PROD |
|------|-----|------|------|
| Real citizen complaint data | ❌ Never | ❌ Never | ✅ (masked) |
| RLS enforced | ❌ | ✅ | ✅ |
| Automated refresh | Manual only | Daily | Every 4 hours |
| Who can publish | Any analyst | Analytics Lead | Analytics Lead + IT |
| Change approval required | None | Analytics Lead | Director + IT |

### 5.2 Semantic Model Reuse

The shared semantic model is the cornerstone of PWIS's BI governance:

**One dataset, many reports:**
```
PWIS Semantic Model (Power BI Dataset)
├── Executive Dashboard          ← Director, Deputy Directors
├── Operations Work Queue        ← Supervisors, Crew Leads
├── Council Briefing Report      ← Exported PDF, quarterly
├── Finance CIP Justification    ← Finance team, annual
├── District Condition Summary   ← District Managers
└── Ad-hoc Analysis Workspace    ← Analysts
```

**Benefits of semantic model reuse:**
- KPI definitions are consistent across all reports — "Avg Condition Index" means the same thing everywhere
- Security updates propagate to all reports automatically
- Data refresh happens once; all reports benefit
- New reports can be built by analysts without IT involvement

**Anti-pattern to avoid:** Creating report-specific datasets that duplicate transformation logic. This leads to metric drift — where two reports show different numbers for "the same" KPI because they were built independently.

### 5.3 CI/CD Approach

```
Developer Workflow:
─────────────────

1. Analyst makes model/report changes locally (Power BI Desktop)
   or pushes Python/SQL changes to Git

2. Pull request raised against `dev` branch
   → Automated checks run:
      a. DAX syntax validation (Tabular Editor CLI)
      b. Python unit tests (pytest models/)
      c. SQL lint (sqlfluff)
      d. Data quality checks (Great Expectations)

3. Analytics Lead reviews and approves PR
   → Merge to `dev`
   → Power BI dataset auto-published to DEV workspace via:
      `pbi-tools deploy --workspace PWIS-DEV`

4. UAT: QA analyst tests dashboard in TEST environment
   → Runs RLS test checklist
   → Validates KPI values against known data
   → Signs off in Jira ticket

5. Analytics Lead promotes to PROD:
   → GitHub Actions workflow triggers:
      a. dbt run (production SQL transforms)
      b. Power BI dataset refresh
      c. Power BI report publish
      d. Slack notification to #pwis-ops

6. Post-deploy monitoring (24 hours):
   → Azure Monitor checks for refresh failures
   → Automated KPI anomaly detection alerts

─────────────────────────────────────────────────────
CI/CD Tools Stack:
  Version control:    GitHub (City of Boise Azure DevOps)
  Python testing:     pytest + GitHub Actions
  SQL transforms:     dbt Core (open-source)
  SQL linting:        sqlfluff
  DAX validation:     Tabular Editor 2 CLI (open-source)
  Data quality:       Great Expectations
  Power BI deploy:    pbi-tools (open-source CLI)
  Notifications:      Azure Monitor → Email/Slack
```

### 5.4 Data Refresh Schedule

| Dataset | Refresh Frequency | Method | Failure Handling |
|---------|------------------|--------|-----------------|
| Road Segments | Weekly (Sunday 2am) | ESRI API → dbt → PBI | Alert to Analytics Lead |
| Work Orders | Daily (1am) | Cityworks API → dbt | Alert + fallback to last good |
| Complaints | Every 4 hours | 311 API → staging | Alert if >2 consecutive failures |
| Traffic Counts | Monthly | Manual CSV import | Analyst-triggered |
| Budget Actuals | Quarterly (manual) | Finance export | Analyst-triggered |
| Priority Scores | Daily (after WO refresh) | Python model → dbt | Re-runs automatically |

---

## 6. Data Quality Framework

### 6.1 Validation Rules (Great Expectations)

```python
# PWIS Data Quality Suite — implemented with Great Expectations
# Run as part of CI/CD pipeline and daily after data refresh

EXPECTATION_SUITE = {
    "road_segments": [
        # Completeness
        {"expectation": "expect_column_to_not_be_null",
         "column": "segment_id"},
        {"expectation": "expect_column_to_not_be_null",
         "column": "condition_index"},
        # Range validation
        {"expectation": "expect_column_values_to_be_between",
         "column": "condition_index",
         "min_value": 1, "max_value": 100},
        {"expectation": "expect_column_values_to_be_between",
         "column": "paser_rating",
         "min_value": 1, "max_value": 10},
        # Geographic bounds (Boise metro)
        {"expectation": "expect_column_values_to_be_between",
         "column": "lat",
         "min_value": 43.5, "max_value": 43.8},
        {"expectation": "expect_column_values_to_be_between",
         "column": "lon",
         "min_value": -116.4, "max_value": -116.0},
        # Uniqueness
        {"expectation": "expect_column_values_to_be_unique",
         "column": "segment_id"},
        # Domain values
        {"expectation": "expect_column_values_to_be_in_set",
         "column": "road_type",
         "value_set": ["Arterial", "Collector", "Local", "Highway"]},
        # Referential: district must match MDM canonical list
        {"expectation": "expect_column_values_to_be_in_set",
         "column": "district",
         "value_set": ["North End","Downtown","East Bench",
                        "Southeast","Southwest","West Boise"]},
    ],
    "work_orders": [
        {"expectation": "expect_column_to_not_be_null",
         "column": "work_order_id"},
        # Temporal integrity: completed_date >= created_date
        {"expectation": "expect_column_pair_values_A_to_be_greater_than_or_equal_to_B",
         "column_A": "completed_date",
         "column_B": "created_date",
         "filter_column": "status",
         "filter_value": "Completed"},
        # Business rule: actual_cost must be present when Completed
        {"expectation": "expect_column_values_to_not_be_null",
         "column": "actual_cost_usd",
         "filter": "status == 'Completed'"},
    ],
    "complaints": [
        {"expectation": "expect_column_values_to_be_in_set",
         "column": "severity_reported",
         "value_set": ["Low","Medium","High","Critical"]},
        # Resolution date cannot precede submission date
        {"expectation": "expect_column_pair_values_A_to_be_greater_than_or_equal_to_B",
         "column_A": "resolved_date",
         "column_B": "submitted_date",
         "filter": "resolution_status == 'Resolved'"},
    ],
}

# Alerting thresholds
QUALITY_THRESHOLDS = {
    "road_segments":  {"pass_rate": 0.98, "alert_below": 0.95},
    "work_orders":    {"pass_rate": 0.95, "alert_below": 0.90},
    "complaints":     {"pass_rate": 0.90, "alert_below": 0.85},
}
```

### 6.2 Master Data Management (MDM)

The PWIS MDM framework establishes canonical reference data that all source systems must conform to:

**Canonical Reference Tables:**

| Entity | Canonical Source | Managed By | Integration Method |
|--------|-----------------|-----------|-------------------|
| Road Segment IDs | GIS Dept (`segment_id`) | GIS Manager | ESRI REST API |
| District Names | City Clerk (official boundaries) | Analytics Lead | Config table |
| Work Order Types | Public Works Ops (Cityworks setup) | Ops Manager | Cityworks export |
| Complaint Categories | 311 Program Office | 311 Manager | Salesforce export |
| Fiscal Year Definition | Finance (Oct 1 – Sep 30) | Finance Analyst | Hardcoded DIM_DATE |

**MDM Change Control:**
Any change to a canonical identifier (e.g., a road segment re-alignment that changes `segment_id`) requires:
1. 30-day advance notice to Analytics team
2. Migration plan for historical data continuity
3. Parallel run period (old and new IDs coexist) of ≥30 days
4. Post-migration validation report

**Cross-system ID Mapping:**
Some source systems use internal IDs that differ from PWIS natural keys. The `PWIS_CrosswalkIDs` table maintains these mappings:

```sql
CREATE TABLE PWIS_CrosswalkIDs (
    pwis_segment_id    VARCHAR(12) NOT NULL,
    cityworks_asset_id VARCHAR(20),
    esri_objectid      INT,
    fhwa_bridge_id     VARCHAR(15),
    created_date       DATE NOT NULL,
    is_active          BOOLEAN DEFAULT TRUE
);
```

### 6.3 GIS Integration Standards

All spatial data in PWIS adheres to:

| Standard | Specification |
|----------|--------------|
| Coordinate system | WGS84 (EPSG:4326) for storage |
| Projection for analysis | NAD83 Idaho West (EPSG:8827) |
| Geometry type | Points (segment centroids) in current version; Linestrings in v2 |
| Coordinate precision | 6 decimal places (~10cm accuracy) |
| Complaint matching | GIS snap to nearest segment within 50m buffer |
| Spatial index | GIST index on all geometry columns in PostGIS |

**GIS Data Quality Checks:**
```sql
-- Detect segments outside Boise bounding box
SELECT segment_id, lat, lon
FROM road_segments
WHERE lat NOT BETWEEN 43.5 AND 43.8
   OR lon NOT BETWEEN -116.4 AND -116.0;

-- Detect duplicate coordinates (two segments at same point — likely data error)
SELECT lat, lon, COUNT(*) as dup_count
FROM road_segments
GROUP BY lat, lon
HAVING COUNT(*) > 1;

-- Detect complaints not matched to any segment (orphaned records)
SELECT complaint_id
FROM complaints
WHERE segment_id NOT IN (SELECT segment_id FROM road_segments);
```

---

## 7. Dashboard Design Specifications

### 7.1 Executive Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│  PWIS Executive Dashboard  │  City of Boise Public Works    │
│  [Date Slicer: FY2026 ▼]  │  [District Slicer: All ▼]      │
├─────────────┬──────────────┬──────────────┬─────────────────┤
│  ICI: 58.2  │ High/Crit:  │ Backlog:     │ Prevention %:   │
│  ▼ -1.3 YoY │  13 segs    │  $545K       │  38% ▲ +4pts   │
├─────────────┴──────────────┴──────────────┴─────────────────┤
│  [Condition by District — Box Plot]   [Priority Tier Donut] │
├─────────────────────────────────────────────────────────────┤
│  [GIS Priority Map — Embedded HTML iframe or ArcGIS tile]   │
├─────────────────────────────────────────────────────────────┤
│  [Top 10 Priority Segments Table — sortable, exportable]    │
├──────────────────────────┬──────────────────────────────────┤
│  [Spend by District Bar] │  [Complaint Volume Trend Line]   │
└──────────────────────────┴──────────────────────────────────┘
```

### 7.2 Design Principles

1. **One screen, one decision**: Each page answers a single question. The executive page answers "How is the network performing?" The operations page answers "What should crews work on?"

2. **Color consistency**: Critical = Red (#D62728), High = Orange (#FF7F0E), Medium = Yellow (#BCBD22), Low = Green (#2CA02C) — identical to the Python model and GIS maps. No exceptions.

3. **Context-first numbers**: Never show a number without its reference point. Not "58.2" but "ICI: 58.2 / 100 ▼ -1.3 vs prior year (target: 65)"

4. **Mobile-aware layout**: Council members review dashboards on phones. All KPI cards and key charts must be legible at 375px width.

5. **Export-ready**: Every table has a "Download CSV" button. Every chart has a "..." menu with export options. Council staff will always want the data behind the visual.

### 7.3 Accessibility

| Requirement | Implementation |
|-------------|---------------|
| Color-blind safe palette | Okabe-Ito palette (tested against Deuteranopia + Protanopia) |
| Alt text on all visuals | Set in Power BI Format pane → Title → Alt text |
| Screen reader support | Table visuals preferred over matrix; title hierarchy enforced |
| Minimum font size | 12pt for data labels, 14pt for titles |
| Contrast ratio | All text ≥ 4.5:1 against background (WCAG AA) |

---

## 8. Monitoring and Alerting

### 8.1 Automated Alerts

| Alert | Trigger | Recipients | Channel |
|-------|---------|-----------|---------|
| Segment drops to Critical tier | CI falls below 25 on refresh | Analytics Lead + Ops Manager | Email + Slack |
| Data refresh failure | Two consecutive failures | Data Engineer + Analytics Lead | PagerDuty |
| Budget utilization > 95% | Current-year spend / budget | Finance Director | Email |
| DQ check failure | Pass rate below threshold | Data Engineer | Slack #pwis-alerts |
| Complaint spike | >2x 7-day rolling avg in any district | District Manager + Ops | Email |

### 8.2 Performance SLAs

| Component | Target SLA | Measurement |
|-----------|-----------|-------------|
| Dashboard load time | < 3 seconds | Power BI Performance Analyzer |
| Data refresh completion | < 30 minutes | Power BI Refresh History |
| Priority model run | < 2 minutes | Python timing log |
| DQ validation suite | < 5 minutes | Great Expectations run log |

---

*This document is the authoritative BI architecture specification for PWIS. For model logic see `docs/model_logic.md`. For operational procedures see `docs/knowledge_base.md`.*
