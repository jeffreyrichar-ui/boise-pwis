# PWIS Knowledge Base
## Boise Public Works Intelligence System

**Document Type:** Operational Knowledge Base
**Audience:** Analysts, Supervisors, IT Staff, New Users

---

## System Overview

PWIS is a utility infrastructure prioritization platform that scores pipe segments across Boise's water, sewer, and stormwater systems. It produces priority rankings, action recommendations, and budget scenario analyses.

## Frequently Asked Questions

### What does the priority score mean?
The priority score (0–100) represents how urgently a pipe segment needs attention relative to other pipes in the system. Higher scores mean higher priority. The score combines six factors: physical condition, break history, hydraulic capacity stress, system criticality, material risk, and age.

### How are the priority tiers defined?
- **Critical (75–100):** Structural failure risk. Schedule replacement in current CIP cycle.
- **High (55–74):** Major defects. Address within current fiscal year.
- **Medium (30–54):** Moderate issues. Plan for next CIP cycle.
- **Low (0–29):** Acceptable condition. Monitor per standard schedule.

### What is the confidence score?
The confidence score (0.0–1.0) reflects how reliable the priority score is based on data quality. Scores below 0.7 indicate incomplete inspection data or stale readings (>2 years old). Re-inspect these pipes before committing significant capital.

### How does the system filter work?
You can filter by Water, Sewer, or Stormwater to see prioritization within a single utility system. Each system has different failure modes, materials, and cost structures.

### What is the deferral cost analysis?
It estimates how much more expensive pipe replacement becomes if deferred N years. Critical-tier pipes have a 4.5x cost multiplier at 5 years — a $100K replacement today becomes $450K if deferred to emergency failure. This analysis covers High and Critical pipes only.

## Key Data Sources

| Source | Refresh Frequency | Quality Notes |
|---|---|---|
| CCTV Inspections | Quarterly campaigns | Gold standard for condition data |
| Acoustic Monitoring | Annual | Good for water mains |
| Work Order History | Daily from CMMS | 5-year rolling window |
| 311 Service Requests | Daily | Subject to reporting bias |
| Flow Monitoring | Monthly from SCADA | Sewer/stormwater pipes only |
| CIP Budget | Annual at adoption | Confirmed funding only |

## Material Reference

| Material | Typical Service Life | Primary Failure Mode |
|---|---|---|
| Cast Iron | 75–100 yr | Internal corrosion, graphitization |
| Asbestos Cement | 50–70 yr | Brittle fracture, leaching |
| Vitrified Clay | 75–100 yr | Joint separation, root intrusion |
| Orangeburg | 30–50 yr | Deformation, collapse when saturated |
| Ductile Iron | 75–100 yr | External corrosion (if uncoated) |
| PVC | 75–100 yr | Joint separation, UV degradation |
| HDPE | 100+ yr | Fusion joint failure (rare) |
| Corrugated Metal | 25–50 yr | Invert corrosion |
| Concrete | 50–100 yr | H2S corrosion (sewer), spalling |

## Contact and Support

- Model assumptions: See `MODEL_ASSUMPTIONS` in `models/prioritization.py`
- Cost assumptions: See `REPLACEMENT_COST_PER_LF` in `models/scenario_engine.py`
- Data generation: See `data/generate_data.py` for synthetic data documentation
