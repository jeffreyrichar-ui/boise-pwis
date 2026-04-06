# PWIS Knowledge Base
## Boise Public Works Intelligence System

**Document Type:** Operational Knowledge Base
**Audience:** Analysts, Supervisors, IT Staff, New Users

---

## System Overview

PWIS is a utility infrastructure prioritization platform that scores pipe segments across Boise Public Works' three systems: wastewater/sewer collection (~900 miles, 4,200 segments), geothermal district heating (20+ miles, 350 segments), and pressurized irrigation/14 subdivisions (280 segments). It produces priority rankings, action recommendations, and budget scenario analyses to support capital investment planning.

## Frequently Asked Questions

### What does the priority score mean?
The priority score (0–100) represents how urgently a pipe segment needs attention relative to other pipes in the same system. Higher scores mean higher priority. The score combines six factors: physical condition, break history, capacity stress, system criticality, material risk, and age.

### How are the priority tiers defined?
- **Critical (75–100):** Structural failure risk. Schedule replacement in current CIP cycle → ACTION: REPLACE
- **High (55–75):** Major defects. Address within current fiscal year → ACTION: REHABILITATE or LINE
- **Medium (30–55):** Moderate issues. Plan for next CIP cycle → ACTION: REPAIR
- **Low (0–30):** Acceptable condition. Monitor per standard schedule → ACTION: MONITOR or NO_ACTION

### What is the confidence score?
The confidence score (0.0–1.0) reflects how reliable the priority score is based on data quality. Scores below 0.7 indicate incomplete inspection data or stale readings (>2 years old). Re-inspect these pipes before committing significant capital.

### How does the system filter work?
You can filter by Sewer, Geothermal, or PI to see prioritization within a single utility system. Each system has different failure modes, materials, cost structures, and operational constraints:
- **Sewer:** Responds to break history, inflow/infiltration, structural failure risk
- **Geothermal:** Responds to insulation condition, temperature stability, circulation efficiency
- **PI:** Responds to pressure integrity, seasonal stress, irrigation demand peaks

### What is the deferral cost analysis?
It estimates how much more expensive pipe replacement becomes if deferred N years. Critical-tier pipes have a 4.5x cost multiplier at 5 years — a $100K replacement today becomes $450K if deferred to emergency failure. This analysis covers High and Critical pipes only.

## Key Data Sources

| Source | Refresh Frequency | Quality Notes | Systems |
|---|---|---|---|
| CCTV Inspections | Quarterly campaigns | Gold standard for condition data | Sewer primarily |
| Pressure/Flow Testing | Semi-annual | Pipeline integrity assessment | PI, Geothermal |
| Thermal Imaging | Annual | Insulation and circulation condition | Geothermal |
| Work Order History | Daily from CMMS | 5-year rolling window | All systems |
| 311 Service Requests | Daily | Subject to reporting bias; backups, leaks, odors | Sewer, Geothermal, PI |
| Flow Monitoring | Monthly from SCADA | Real-time or historical logs | Sewer (I&I), Geothermal (circulation), PI (seasonal) |
| Temperature Monitoring | Continuous/daily | Geothermal system efficiency | Geothermal only |
| Well Depth & Performance Data | Annual | Production/injection well data | Geothermal (3 wells + injection) |
| CIP Budget | Annual at adoption | Confirmed funding only | All systems |

## Material Reference

### Sewer System Materials

| Material | Typical Service Life | Primary Failure Mode | Risk Factor |
|---|---|---|---|
| Cast Iron | 75–100 yr | Internal corrosion, graphitization (alkaline soil accelerates) | 0.90 |
| Vitrified Clay | 75–100 yr | Joint separation, root intrusion | 0.60 |
| Orangeburg | 30–50 yr | Deformation, collapse when saturated, root intrusion | 0.95 |
| Ductile Iron | 75–100 yr | External corrosion (if uncoated), H2S pitting | 0.30 |
| Concrete | 50–100 yr | H2S corrosion (sewer crown), spalling, infiltration | 0.45 |
| PVC | 75–100 yr | Joint separation, UV degradation (exposed sections) | 0.15 |
| HDPE | 100+ yr | Fusion joint failure (rare), root penetration | 0.10 |

### Geothermal System Materials

| Material | Typical Service Life | Primary Failure Mode | Risk Factor |
|---|---|---|---|
| Steel | 50–75 yr | External corrosion, internal scale buildup | 0.40 |
| Pre-insulated Steel | 75–100 yr | Insulation degradation, moisture infiltration | 0.20 |
| Transite (AC) | 40–60 yr | Brittle fracture, corrosion leaching | 0.50 |
| HDPE | 75–100+ yr | Thermal cycling stress, fusion joint failure | 0.10 |

### Pressurized Irrigation Materials

| Material | Typical Service Life | Primary Failure Mode | Risk Factor |
|---|---|---|---|
| PVC PR-SDR | 50–75 yr | Pressure fatigue, UV degradation, joint separation | 0.20 |
| PVC C900 | 60–80 yr | Pressure cycling, chlorine brittlement | 0.15 |
| HDPE | 75–100+ yr | Pressure rippling, slow-crack growth (rare) | 0.10 |

## Contact and Support

- Model assumptions: See `MODEL_ASSUMPTIONS` in `models/prioritization.py`
- Cost assumptions: See `REPLACEMENT_COST_PER_LF` in `models/scenario_engine.py`
- Data generation: See `data/generate_data.py` for synthetic data documentation
