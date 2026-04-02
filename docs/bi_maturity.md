# BI Maturity Layer
## Boise Public Works Intelligence System (PWIS)

**Document Type:** BI Architecture, Power BI Design, Governance
**Domain:** Water / Sewer / Stormwater Utility Infrastructure

---

## Power BI Semantic Model

### Star Schema Design

**Fact Table:** pipe_segments (with priority scoring output)

**Dimensions:**
- dim_district (6 service districts)
- dim_system_type (Water, Sewer, Stormwater)
- dim_material (11 pipe materials with era and risk factors)
- dim_criticality (8 criticality classes with multipliers)
- dim_action (6 action codes with cost ranges and urgency)

### Key DAX Measures

```dax
// Weighted Average Condition
Avg Condition = AVERAGE(pipe_segments[condition_score])

// Critical Pipe Percentage
Critical % = DIVIDE(
    COUNTROWS(FILTER(pipe_segments, pipe_segments[priority_tier] = "Critical")),
    COUNTROWS(pipe_segments)
) * 100

// Total Replacement Backlog
Replacement Backlog = SUMX(
    FILTER(pipe_segments, pipe_segments[priority_tier] IN {"Critical", "High"}),
    pipe_segments[estimated_replacement_cost_usd]
)

// Pipe Miles by System
Pipe Miles = DIVIDE(SUM(pipe_segments[length_ft]), 5280)
```

### Row-Level Security

RLS implementation by district:
- District Supervisors see only their assigned district
- Directors and Analysts see all districts
- Council members see city-wide aggregates only

## Data Refresh

- Pipe condition data: refreshed after each CCTV inspection campaign (quarterly)
- Work orders: daily refresh from CMMS
- Service requests: daily refresh from 311 system
- Flow monitoring: monthly aggregation from SCADA
- Budget: annual refresh at CIP adoption

## Governance

- Model assumptions documented in MODEL_ASSUMPTIONS registry (prioritization.py)
- All cost assumptions sourced from AWWA 2023 benchmarks
- Confidence scoring flags stale or incomplete data
- Scenario engine produces audit trail (scenario_id, timestamp, parameters)
