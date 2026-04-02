# Prioritization Model Logic
## Boise Public Works Intelligence System (PWIS)

**Document Type:** Model Design & Tradeoff Documentation
**Phase:** 3 — Prioritization Model
**Status:** v1.0 Baseline

---

## 1. Model Purpose

The PWIS Prioritization Model answers one question:

> **"Given limited maintenance budget, which road segments should we address first?"**

This is not a prediction model. It is a **decision support tool** — a structured, weighted, explainable scoring framework that synthesizes four types of evidence into a single actionable number.

---

## 2. The Formula

```
Priority Score (0–100) =
    (Condition Severity Score  × 0.35)
  + (Traffic Impact Score      × 0.25)
  + (Complaint Pressure Score  × 0.20)
  + (Cost Efficiency Score     × 0.12)
  + (Equity Modifier Score     × 0.08)
```

Each component is independently normalized to 0–100 before weighting. This ensures no single data source can dominate due to scale differences.

---

## 3. Component Descriptions

### 3.1 Condition Severity (Weight: 35%)

**What it measures:** How deteriorated is the infrastructure?
**Data source:** Pavement condition inspection (`condition_index`, 1–100)
**Method:**

- Inverts the condition index: a CI of 20 → severity score of ~90
- Applies exponential amplification below CI=40 to reflect that deterioration accelerates non-linearly and emergency repair costs 3–5× preventive treatment

```
severity = (100 - CI) + exponential_boost(CI < 40)
```

**Why highest weight (35%):** Condition is the most objective, defensible input. Federal reporting (FHWA), state DOT grants, and bond rating agencies all use condition-based infrastructure assessments. This is the pillar of any credible investment justification.

**Quick win vs. production:**
- *Quick win:* Linear inversion (100 - CI) works immediately
- *Production:* Full deterioration curve model using IRI (International Roughness Index) data and pavement lifecycle curves

---

### 3.2 Traffic Impact (Weight: 25%)

**What it measures:** What is the economic impact if this segment fails?
**Data source:** Annual Average Daily Traffic (AADT)
**Method:**

- Normalizes AADT against citywide maximum (50,000 vehicles/day)
- Applies road-type multiplier: Highways get 1.45×, Arterials 1.30×, Collectors 1.00×, Local 0.70×

```
traffic_score = (AADT / 50,000) × road_type_multiplier × 100
```

**Why 25% weight:** A pothole on a 30,000-AADT arterial creates traffic disruption affecting thousands of commuters and potentially triggers liability claims. The same condition on a 200-AADT local street affects a handful of residents. Weighting by traffic matches investment to economic impact.

**TRADEOFF:** We chose AADT over Vehicle Miles Traveled (VMT = AADT × length) because AADT is more universally reported and directly comparable. VMT would favor longer segments over condition severity — which could distort priorities toward suburban corridors over urban arterials. Documented for stakeholder review.

---

### 3.3 Complaint Pressure (Weight: 20%)

**What it measures:** What is the political and service impact?
**Data source:** 311 citizen complaints, filtered to last 24 months
**Method:**

- Weights complaints by severity: Critical=4, High=3, Medium=2, Low=1
- Normalizes by segment length (complaints per lane-mile) to ensure equity
- Caps at 99th percentile to prevent outlier segments from dominating

```
complaint_score = weighted_complaints / length_miles  (normalized to 0–100)
```

**Why 20% weight:** Complaints are imperfect infrastructure intelligence — they're biased toward vocal, connected communities. But they are real signal: a surge of complaints about a specific segment often precedes formal inspection findings. 20% weight acknowledges this signal without letting it override condition data.

**EQUITY DESIGN DECISION:** Using complaint *density* (per lane-mile) rather than raw count ensures that larger districts don't dominate simply because they have more residents filing complaints. This protects lower-income neighborhoods that may underreport.

---

### 3.4 Cost Efficiency (Weight: 12%)

**What it measures:** What is the return on investment for this intervention?
**Data source:** Estimated repair cost + AADT + segment length
**Method:**

- Computes cost per vehicle-mile served: lower cost-per-VMT = better investment
- Inverts and normalizes: high-efficiency = high score

```
cost_per_vmt = repair_cost / (AADT × length_miles)
efficiency_score = invert(cost_per_vmt) normalized to 0–100
```

**Why 12% weight:** Stewardship of public funds is a core responsibility — but cost efficiency alone would lead to cherry-picking easy, cheap fixes while deferring expensive but critical work. At 12%, it functions as a tiebreaker between otherwise similar-scoring segments rather than a dominant driver.

**EXAMPLE:** Two segments with identical condition (CI=40):
- Segment A: $20K repair, 15,000 AADT → high efficiency score → small priority boost
- Segment B: $120K repair, 8,000 AADT → lower efficiency score → small priority reduction
- The condition score (35% weight) still dominates the decision

---

### 3.5 Equity Modifier (Weight: 8%)

**What it measures:** Are we correcting for systematic underinvestment?
**Data source:** District-level average condition index vs. citywide median
**Method:**

- Districts with average condition below citywide median receive a proportional boost
- Boost is applied at the segment level based on district membership

**Why 8% weight:** This is a policy value embedded in the model. It reflects the documented tendency for lower-income neighborhoods to receive deferred maintenance. The 8% weight is intentionally modest — enough to correct systematic bias over time, not enough to override legitimate condition-based priorities.

**Stakeholder note:** This modifier should be disclosed to all users. When presenting scores to district managers, explain: "Segments in historically under-maintained districts receive a small score adjustment to ensure equitable attention across the city."

---

## 4. Priority Tiers

| Tier | Score Range | Interpretation | Recommended Cadence |
|------|------------|----------------|---------------------|
| **Critical** | 75–100 | Immediate risk; failure imminent or has occurred | Within 2 weeks |
| **High** | 55–74 | Significant deterioration with high traffic/complaint burden | Current CIP cycle |
| **Medium** | 30–54 | Moderate condition; good candidate for preventive treatment | Next 12–18 months |
| **Low** | 0–29 | Good condition; routine monitoring sufficient | Annual review |

---

## 5. Action Recommendations

The model maps condition index + priority tier to a recommended action:

| Condition Index | Priority Tier | Recommended Action |
|----------------|--------------|-------------------|
| < 25 | Any | Emergency Repair — Within 2 Weeks |
| 25–39 | Any | Full Rehabilitation — Current CIP Cycle |
| 40–54 | High/Critical | Preventive Treatment — This Quarter |
| 55–64 | Medium | Crack Seal + Seal Coat — Next Window |
| 65–79 | Any | Routine Monitoring — 12 Months |
| 80–100 | Low | No Action — Annual Review |

---

## 6. What the Model Does NOT Do

| Excluded Factor | Reason | Future Consideration |
|----------------|--------|---------------------|
| ML deterioration prediction | Requires multi-year condition time series; not yet available | Phase 2 enhancement with 3+ years of inspection data |
| Structural capacity (bridges) | Separate FHWA inspection protocol | Bridge model is parallel track |
| Weather risk prediction | Requires IoT sensor data | Phase 3 smart infrastructure integration |
| Lifecycle cost modeling | Requires unit cost databases by surface type | CIP planning enhancement |
| Crew availability constraints | Operational, not strategic | Integrate with CMMS scheduling module |

---

## 7. Documented Tradeoffs

| Decision | Option Chosen | Option Rejected | Rationale |
|----------|--------------|-----------------|-----------|
| Scoring methodology | Weighted sum | ML (Random Forest) | Explainability to non-technical stakeholders; no black boxes in public budgeting |
| Complaint normalization | Per lane-mile | Raw count | Equity; population-dense districts would otherwise dominate |
| Condition amplification | Exponential curve | Linear | Reflects real-world cost acceleration below CI=40 |
| Traffic metric | AADT | VMT | Wider data availability; not biased toward long suburban segments |
| Equity mechanism | Weight modifier | Hard quota by district | Avoids gaming; continuous, not binary |
| Score range | 0–100 | Raw index | Intuitive for non-technical stakeholders; easier to tier |

---

## 8. Model Governance

### Who controls the weights?

Default weights are set by the Director of Analytics with input from:
- Public Works Director (operational priorities)
- Finance Director (budget efficiency emphasis)
- Equity Officer (equity modifier calibration)

Weights should be reviewed annually and when a new CIP cycle begins.

### How are weight changes documented?

All weight configurations are stored with a timestamp and author in the scenario engine. Any score run produces a reproducible audit log. This matters because:

- Council members may ask "why did you fund Project X over Project Y?"
- The answer must be: "Because at the weights approved in [date], X scored [Y] and Y scored [Z], driven primarily by [condition/traffic/complaints]."

### Can district managers request weight changes?

No. Weight changes are a policy decision, not an operational one. District managers may submit evidence to justify re-inspection of specific segments (which updates the input data), but they do not control scoring parameters.

---

## 9. Validation Approach

### 9.1 Face Validity

Before trusting any score, ask: "Do the top 10 segments match what experienced crew supervisors would pick?" In initial validation (synthetic data), the model correctly surfaces:

- High-AADT highways with CI < 45 → top of Critical/High tier ✓
- Local streets with low traffic and good condition → bottom of Low tier ✓
- Districts with documented underinvestment → equity modifier functioning ✓

### 9.2 Sensitivity Analysis

The scenario engine (Phase 6) tests: "If we shift condition weight from 35% to 50%, how much does the top-10 list change?" If >70% of the top-10 remains stable, the model is robust. If rankings flip dramatically, the weighting needs review.

### 9.3 Back-Testing (Production Version)

With 3+ years of historical data, validate: "Did segments that scored High in Year N require emergency repair in Year N+2 at higher rates than Low-scoring segments?" This converts the model from an advisory tool into a statistically validated decision instrument.

---

*See `models/scenario_engine.py` for weight adjustment and scenario simulation.*
*See `docs/bi_maturity.md` for the Power BI DAX implementation of this scoring logic.*
