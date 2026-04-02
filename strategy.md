# PWIS Strategy Document
## Boise Public Works Intelligence System

**Document Type:** Director-Level Strategy & Architecture
**Author:** Director of Analytics & Strategy
**Version:** 1.0 — Portfolio Baseline
**Date:** April 2026

---

## Executive Summary

This document records the strategic thinking behind the Boise Public Works Intelligence System — not just what was built, but why, what tradeoffs were made, and what would change in a production environment. It is written for an audience of executive peers: Public Works Director, City CIO, Finance Director, and Council staff.

The central argument of this system is simple: **infrastructure investment decisions made without data cost cities 3–5× more in the long run and undermine public trust when they appear arbitrary.** PWIS makes those decisions systematic, auditable, and defensible — without eliminating the human judgment that political governance requires.

---

## 1. What Was Built and Why

### The Core System

PWIS is a five-layer decision support platform:

| Layer | Component | What It Does |
|-------|-----------|--------------|
| Data | 7 synthetic datasets (300 segments, 800 complaints, 500 WOs) | Simulates the operational data landscape of a mid-size public works department |
| Model | Weighted prioritization scoring (5 components) | Converts fragmented data into a single, explainable priority score per segment |
| GIS | 4 Folium interactive maps | Gives spatial context to condition and priority data |
| Dashboard | Streamlit executive app | Puts the model in the hands of non-technical decision-makers |
| Scenarios | Budget + weight + deferral simulation engine | Answers "what if" questions that Council and Directors actually ask |

### Why These Tools

**Python over Power BI (for computation):** The scoring model requires iterative, adjustable logic. Python enables full control over algorithms, validation, and testing. Power BI is an excellent presentation layer but not a modeling layer.

**Streamlit over custom web app:** Streamlit is the fastest path from a working model to an interactive interface for a domain expert audience. It doesn't require a separate front-end developer. For a portfolio project, this is the right tradeoff. In production, a managed Power BI Embedded or ArcGIS Dashboard integration would be appropriate for enterprise IT governance.

**Folium over ArcGIS/QGIS:** Free, Python-native, embeds in both Streamlit and static HTML. The limitation is lack of enterprise GIS editing capability — acknowledged and appropriate for this use case.

**Synthetic data over real data:** Using real Boise data would require a data use agreement, introduce quality issues that obscure the architecture demonstration, and prevent public sharing. The synthetic data is structurally identical to real PASER inspection data, 311 exports, and Cityworks work order data — a drop-in replacement.

---

## 2. Tradeoffs Made

### 2.1 Speed vs. Scalability

| What Was Done (Fast) | What a Production System Would Do | Rationale |
|---------------------|----------------------------------|-----------|
| CSV flat files | PostgreSQL or Snowflake data warehouse | CSVs are readable, shareable, and require no infra. |
| In-memory pandas scoring | dbt models + SQL transformation layer | Pandas scales to 10K segments fine; dbt needed for 100K+ |
| Streamlit app | Power BI Embedded + REST API | Streamlit is single-user; Power BI handles concurrent government users |
| Single Git branch | Dev/Test/Prod pipeline (GitHub Actions) | CI/CD adds overhead that's unjustified for a prototype |
| Manual data generation | ETL from Cityworks, ESRI, 311, GIS | Real integration requires IT partnership and data governance agreements |

### 2.2 Data Quality vs. Usability

The data quality problem in public works is acute: inspection records are incomplete, complaint geolocation is imprecise, and maintenance cost data is inconsistently entered. The system was designed to **function with incomplete data** rather than fail. This required three explicit decisions:

1. **Confidence scoring:** Every priority score carries a `score_confidence` field (0–1) that reflects the completeness of its input data. A score of 0.6 means 60% of the key inputs were available. Scores below 0.6 are flagged in the dashboard.

2. **Graceful defaults:** Missing AADT defaults to road-type average. Missing repair cost defaults to a length-based estimate using APWA benchmarks. These defaults are documented and adjustable.

3. **Complaint normalization:** Rather than requiring exact GPS coordinates, complaints are matched to the nearest road segment within 50 meters. This reduces false nulls from imprecise 311 submissions.

### 2.3 Explainability vs. Precision

The model was deliberately designed to be explainable rather than precise. Alternative approaches considered:

**Random Forest / Gradient Boosting:**
- Would produce higher statistical accuracy in predicting infrastructure failure
- Requires 3+ years of labeled outcome data (failure = 1, no failure = 0)
- Cannot explain to a Council member why Segment A ranked above Segment B
- Rejected for the current phase; documented for Phase 2 enhancement

**IRI-Based Deterioration Model:**
- International Roughness Index provides a continuous, physics-based measure of pavement condition
- Would improve the Condition Severity score component significantly
- Requires specialized vehicle-mounted sensors or manual profilometer data
- Adopted as the production upgrade path in the Condition component

**Chosen approach — Weighted Sum:**
- Every score is fully decomposable: "Segment A scored 67 primarily because its Condition score is 82 (CI=28) and its Traffic score is 74 (AADT=24,000)"
- Weights are documented policy, not model parameters
- Can be audited by Finance, Council staff, or state DOT without ML expertise

### 2.4 Equity vs. Efficiency

The Equity Modifier (8% weight) represents a deliberate policy choice embedded in the model. The tradeoff:

- **Pure efficiency**: Maximize lane-miles treated per dollar. Tends to favor arterials in well-maintained districts because they have cheaper preventive treatments.
- **Pure equity**: Allocate budget proportionally by unmet need. Can result in spending heavily on low-traffic local streets while high-impact arterials deteriorate.
- **Balanced approach (chosen)**: A small equity correction that prevents systematic underinvestment without overriding condition-based priorities.

This is not a neutral technical choice. It reflects a governance value: equitable infrastructure access is a public commitment, and the analytics system should reflect it.

---

## 3. What Would Change in Production

### 3.1 Data Layer

| Current | Production |
|---------|-----------|
| 7 synthetic CSV files | Live integration: Cityworks (CMMS), ESRI ArcGIS, Salesforce 311, Oracle Financials |
| Manual condition data | Automated PASER-cycle import from field inspection tablets |
| Static lat/lon | PostGIS spatial database with segment geometries (linestrings, not points) |
| Annual snapshots | Event-driven CDC (Change Data Capture) with daily refresh |

### 3.2 Model Layer

| Current | Production |
|---------|-----------|
| Python script | Scheduled dbt job on Snowflake or BigQuery |
| Static weights | Governance-controlled weight configuration stored in a config table |
| No versioning | Model versioning via MLflow or dbt model versioning |
| No back-testing | Quarterly validation against actual work orders and failure events |

### 3.3 Dashboard Layer

| Current | Production |
|---------|-----------|
| Streamlit local server | Power BI Embedded in City of Boise intranet portal |
| No authentication | Azure AD SSO tied to City employee accounts |
| No Row-Level Security | RLS: District managers see only their district; executives see all |
| No notifications | Automated alerts when segment drops below CI threshold |

### 3.4 GIS Layer

| Current | Production |
|---------|-----------|
| Folium point markers | ESRI ArcGIS Online with segment polylines |
| Static condition data | Live field inspection updates via Collector for ArcGIS |
| No spatial analysis | Network analysis: identify segments where failure disrupts key corridors |

---

## 4. How a Team Would Operate This System

### Team Structure

PWIS is not a self-operating system. It requires active stewardship:

| Role | Responsibility | Time Allocation |
|------|---------------|-----------------|
| **Analytics Lead** (owner) | Model validation, weight governance, data quality oversight | 40% FTE |
| **GIS Analyst** | Spatial data maintenance, map layer updates, field data QA | 25% FTE |
| **Data Engineer** | ETL pipelines, database maintenance, CI/CD | 20% FTE |
| **Operations Liaison** | Translates model output into crew assignments; provides ground-truth feedback | 10% FTE |
| **Finance Analyst** | Budget scenario runs, CIP justification reports | 10% FTE |

### Operating Cadence

| Frequency | Activity |
|-----------|----------|
| **Daily** | Automated: data refresh, validation checks, alert monitoring |
| **Weekly** | Analyst: review new high-priority flags; share digest with Ops Manager |
| **Monthly** | Leadership: KPI dashboard review; complaint trend analysis |
| **Quarterly** | Model validation: compare predictions vs. actual work orders; adjust weights if needed |
| **Annually** | Full model governance review; weight recalibration; CIP prioritization run |

### Governance

Weight changes require:
1. Written request by a Division Manager or above
2. Analytics Lead impact analysis (how many segment rankings shift?)
3. Director of Public Works approval
4. Documented in the model version log with effective date

This process prevents weight gaming while allowing legitimate policy refinement.

---

## 5. IT and GIS Integration Strategy

### 5.1 Integration Architecture

```
Source Systems                  Integration Layer          Analytics Layer
───────────────                 ─────────────────          ───────────────
Cityworks (CMMS)  ──── API ──►  Data Pipeline (ETL)  ──►  PWIS Star Schema
ESRI ArcGIS       ── REST  ──►  (Airflow / dbt)      ──►  (Snowflake / PG)
Salesforce 311    ──── API ──►                        ──►  Power BI Semantic
Oracle Financials ── JDBC  ──►                        ──►  Streamlit API
```

### 5.2 IT Partnership Requirements

PWIS requires a formal partnership with the City IT department for:

1. **API access agreements** — Cityworks and ESRI both require service accounts with defined read-only access scopes
2. **Data residency** — All data must remain within City of Boise Azure tenant; no external cloud storage
3. **Security review** — Streamlit or Power BI deployment requires IT security approval
4. **Change management** — Any schema changes to Cityworks must be communicated to the Analytics team ≥30 days in advance

### 5.3 GIS Department Coordination

The GIS team is a critical partner, not just a data source:

- **Segment ID standardization** — PWIS uses the GIS department's official segment ID as the natural key. Any GIS re-segmentation must be reflected in PWIS with a migration plan.
- **Spatial enrichment** — GIS provides proximity data (near schools, hospitals, emergency routes) that feeds into future versions of the Traffic Impact score
- **Field data collection** — The GIS team manages ArcGIS Field Maps deployment for inspection crews; data flows from Field Maps into the PWIS pipeline

---

## 6. Business Case Summary

The investment in PWIS is justified on three grounds:

**Operational savings:** The model identified that the top 13 High-priority segments (the real worst segments) have a 200% deferral cost premium over 5 years. Acting now on $545K of work prevents $1.09M in additional cost — a 200% ROI on the intervention, not counting federal funding leverage.

**Grant competitiveness:** Federal IIJA infrastructure grants require condition-based project justification. Cities with documented prioritization frameworks consistently outperform those submitting narrative-only applications. Conservative estimate: 15% improvement in grant award rate on a $10M annual grant application pipeline = $1.5M/year.

**Public trust:** Residents who complain through 311 and see no response erode confidence in city government. PWIS provides a data-driven basis for explaining investment decisions publicly: "We funded X before Y because X serves 24,000 vehicles daily at a CI of 28 — Y serves 500 vehicles at CI of 52."

---

## 7. What This System Is, And What It Isn't

This system is a **director-level decision support tool**, not an automated allocation system. Every recommendation it makes is advisory. Human judgment remains the final decision authority because:

- Data quality in public infrastructure is imperfect
- Community context (upcoming development, political commitments) isn't captured in the model
- Emergency events can instantly change priorities in ways the model can't anticipate
- Public accountability requires a human to own every funding decision

The model's job is to make the human decision-maker better informed, faster, and more defensible — not to replace them.

---

*Strategy document version history is maintained in git. For model logic details see `docs/model_logic.md`. For operational procedures see `docs/knowledge_base.md`.*
