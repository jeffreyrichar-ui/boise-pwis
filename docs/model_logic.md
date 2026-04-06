# Prioritization Model Logic
## Boise Public Works Intelligence System (PWIS)

**Document Type:** Model Design & Tradeoff Documentation
**Domain:** Wastewater/Sewer Collection, Geothermal District Heating, Pressurized Irrigation

---

## Priority Score Formula

```
P = (condition_severity × 0.30)
  + (break_history     × 0.20)
  + (capacity_stress   × 0.15)
  + (criticality       × 0.15)
  + (material_risk     × 0.12)
  + (age_factor        × 0.08)
```

Each component is scored 0–100 and weighted. The composite priority_score ranges 0–100.

## Component Scoring

### Condition Severity (30%)
Inverts condition_score (high condition = low urgency). Applies exponential amplification below condition=40 (structural failure threshold) using `(40 - CI)^1.5 / 40`. Normalized with 99th percentile cap.

**Source:** NASSCO PACP grade mapping, AWWA pipe assessment guidance.

### Break History (20%)
Scores pipes by break count in trailing 5-year window. More breaks = higher score. Normalized to 99th percentile. Break history is the strongest empirical predictor of future failure per AWWA 2023 failure curve analysis.

### Capacity Stress (15%)
Scores based on hydraulic capacity utilization percentage. Non-linear amplification above 80% threshold reflects SSO risk (sewer), overflow risk (geothermal circulation), and pressure inadequacy (PI). Default 50% for pipes without flow data.

### Criticality (15%)
Maps criticality_class to multiplier (Transmission Main=1.50, Trunk Sewer=1.45, Lateral=0.70). Reflects systemic impact — transmission main failure affects thousands of customers vs. lateral affecting one property.

### Material Risk (12%)
Maps pipe_material to failure probability factor (Orangeburg=0.95, Cast Iron=0.90, HDPE=0.10). Based on AWWA 2023 material-specific failure data.

### Age Factor (8%)
Linear ramp from 0 (new) to 100 (100+ years). Supplementary factor when inspection data is sparse. Captures general degradation tendency.

## Priority Tiers

| Tier | Score Range | Interpretation |
|---|---|---|
| Critical | 75–100 | Structural failure risk; schedule in current CIP cycle → REPLACE |
| High | 55–75 | Major defects; address within current fiscal year → REHABILITATE/LINE |
| Medium | 30–55 | Moderate issues; plan for next CIP cycle → REPAIR |
| Low | 0–30 | Acceptable condition; monitor per schedule → MONITOR/NO_ACTION |

## Action Recommendations

| Action Code | Tier Trigger | Condition Trigger | Cost Range |
|---|---|---|---|
| REPLACE | Critical | condition < 25 | $150–$400/LF (Sewer); $200–$600/LF (Geothermal); $80–$250/LF (PI) |
| REHABILITATE | Critical–High | condition 25–40 | $80–$200/LF (Sewer); $150–$400/LF (Geothermal) |
| LINE | High | condition 40–55 + High tier | $40–$100/LF (Sewer); $50–$150/LF (Geothermal) |
| REPAIR | Medium | condition 55–65 | $5K–$25K/spot (Sewer); $10K–$40K (Geothermal/PI) |
| MONITOR | Medium–Low | condition 65–80 | $500–$2K/inspection (Sewer); $1K–$5K (Geothermal) |
| NO_ACTION | Low | condition >= 80 | $200–$500/record (annual monitoring) |

## Confidence Scoring

Each segment receives a confidence score (0.0–1.0) based on:
1. Field completeness (condition_score, breaks, replacement cost)
2. Inspection staleness (>730 days = 0.20 penalty)

Segments with confidence < 0.7 should be re-inspected before committing capital.

## Scenario Engine

The scenario engine provides four what-if analyses:
1. **CIP Budget Allocation** — greedy allocation by priority with equity floor and crew capacity constraints
2. **Weight Sensitivity** — compares alternative weight schemes with top-10 stability metric
3. **Deferral Cost** — projects replacement cost over N years using AWWA lifecycle multipliers (Critical=4.5x at 5yr)
4. **Budget Coverage** — marginal pipe-feet treated per budget increment

## Known Limitations

- Sewer: Condition scoring does not account for soil corrosivity (Boise's alkaline soils accelerate cast iron failure) or H2S corrosion in collection lines
- Geothermal: Model assumes constant temperature and flow profiles; seasonal variation not fully captured
- PI: Model assumes seasonal on/off status; performance during peak irrigation season not weighted independently
- Criticality multipliers do not consider network redundancy or alternate routing options
- Capacity stress uses static annual flow data; real-time SCADA integration would improve accuracy for all systems
- Material risk factors are national averages; local calibration recommended in Year 1 for system-specific failure histories
