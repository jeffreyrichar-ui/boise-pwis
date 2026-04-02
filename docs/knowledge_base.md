# PWIS Knowledge Base
## Boise Public Works Intelligence System

**Document Type:** Operational Knowledge Base
**Audience:** Analysts, Supervisors, IT Staff, New Users
**Maintained by:** Director of Analytics & Strategy

---

## 1. Onboarding Guide — New Analysts

### Week 1: Understand the System

Before touching any data, read these documents in order:
1. `docs/problem_definition.md` — Why this system exists
2. `strategy.md` — What tradeoffs were made and why
3. This document — How to operate it day-to-day
4. `docs/model_logic.md` — How the scores are computed

### Accessing the Dashboard

**Local Development:**
```bash
# 1. Clone the repository
git clone https://github.com/[your-org]/boise-pwis.git
cd boise-pwis

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate data (first time only)
python data/generate_data.py
python models/prioritization.py

# 4. Launch the dashboard
streamlit run app/streamlit_app.py
```

**Production (when deployed):**
Access via City intranet portal at `https://analytics.cityofboise.org/pwis`
Use your City of Boise Azure AD credentials.

### First-Day Checklist
- [ ] Can you open the dashboard and see KPI cards?
- [ ] Can you filter by district and see the priority table change?
- [ ] Can you run the $8M budget scenario and see funded/unfunded segments?
- [ ] Can you load the GIS map and toggle between views?
- [ ] Do you understand why the top-ranked segment has the score it does?

---

## 2. Interpreting the Dashboard

### 2.1 KPI Cards (Top Row)

| KPI | What It Means | When to Be Concerned |
|-----|--------------|---------------------|
| **Total Segments** | Number of road segments in the active dataset | Drop from previous week = data pipeline issue |
| **Avg Condition Index** | Network health on 0–100 scale | Below 55 = systemic underinvestment |
| **High/Critical Segments** | Segments needing immediate or near-term action | >15% of network = budget crisis territory |
| **Poor Condition (<40 CI)** | Segments in the worst condition band | Growing trend = deterioration outpacing maintenance |
| **High-Priority Backlog** | Estimated cost to address Critical + High segments | Grows yearly without funding → use in CIP justification |
| **Budget Coverage** | % of annual budget utilized in current scenario | <70% may indicate budget overallocation; >100% = unfunded backlog |

### 2.2 Reading a Priority Score

**Example: Segment SEG-0237, Emerald Dr, Downtown — Score: 66.97, Tier: High**

This means:
- Condition severity contributed ~35% of the score (condition_index = 38)
- Traffic impact contributed ~25% (AADT = 42,696 for a Highway)
- Complaint pressure contributed ~20% (higher complaint density than district average)
- Cost efficiency contributed ~12% (relatively cost-efficient given traffic volume)
- Equity modifier contributed ~8% (Downtown is slightly below median condition)

To verify: look at the "Score Component Breakdown" chart on the Priority Table tab. Each bar shows exactly what drove the score.

### 2.3 Confidence Scores

A `score_confidence` of 0.75 means 75% of the required data fields were present. Scores below 0.6 should be interpreted cautiously and flagged for field inspection verification. The dashboard displays confidence as a percentage in the priority table.

### 2.4 Recommended Actions

| Action | Trigger Condition | Typical Cost/Mile |
|--------|------------------|------------------|
| Emergency Repair | CI < 25 | $250,000 |
| Full Rehabilitation | CI 25–39 | $120,000 |
| Preventive Treatment | CI 40–54, High/Critical tier | $45,000 |
| Crack Seal + Seal Coat | CI 55–64 | $15,000 |
| Routine Monitoring | CI 65–79 | $500 |
| No Action | CI 80+ | $200 |

These actions are recommendations, not mandates. Field supervisors always have authority to adjust based on conditions not captured in the data.

---

## 3. Data Definitions

### Condition Index (CI)

The Condition Index is the primary infrastructure health measure.

**Scale:** 1 (failed) to 100 (perfect)
**Source:** Field inspection using PASER methodology
**Frequency:** Typically once every 2–3 years per segment; arterials annually
**Note:** The CI in PWIS is a simplified composite. It maps approximately to PASER:

| PASER Rating | PASER Description | PWIS Condition Index | PWIS Category |
|-------------|------------------|---------------------|---------------|
| 10 | Excellent | 90–100 | Excellent |
| 8–9 | Very Good / Good | 70–89 | Good |
| 6–7 | Fair | 50–69 | Fair |
| 4–5 | Poor | 30–49 | Poor |
| 1–3 | Very Poor / Failed | 1–29 | Critical |

### AADT (Annual Average Daily Traffic)

The total number of vehicles traveling a segment averaged over a year.

**Why it matters:** A pothole on a 30,000 AADT arterial affects 30,000 daily commuters. The same defect on a 300 AADT local street affects 300 residents. PWIS weights these proportionally.

**Data source:** Traffic counts from ACHD and Boise Public Works (updated annually)
**Limitation:** Not all segments have recent counts. The model uses road-type averages as defaults.

### Priority Score

The composite 0–100 score computed by the PWIS model. Higher = more urgent.

**Not a rank:** Two segments can have the same score. Use `district_rank` for within-district comparisons.
**Not permanent:** Scores update with every data refresh. A score from 3 months ago is stale if new inspections have been completed.
**Policy-dependent:** The score reflects the current weight configuration. When weights change, all scores change.

### Priority Tier

| Tier | Score Range | Count (current dataset) |
|------|------------|------------------------|
| Critical | 75–100 | Updated per model run |
| High | 55–74 | Updated per model run |
| Medium | 30–54 | Updated per model run |
| Low | 0–29 | Updated per model run |

---

## 4. Common Workflows

### Workflow 1: Preparing a CIP Project List

1. Open dashboard → Priority Table tab
2. Filter tier to "Critical" and "High"
3. Export the filtered table to CSV (download button in Streamlit)
4. Sort by `district_rank` to find the top priority per district (ensures geographic balance)
5. Cross-reference with current-year work orders to avoid duplicating active projects
6. Use `recommended_action` and `estimated_repair_cost_usd` to build the CIP project list
7. Run the Budget Scenario to confirm affordability at the proposed budget level

**Typical output:** A ranked project list with estimated costs, supporting the CIP submission

### Workflow 2: Responding to a Council Member's Question

Council: *"Why aren't we fixing [Street X] in my district? My constituents are calling constantly."*

1. Search for the street in the Priority Table tab
2. Note its `priority_score`, `priority_tier`, and `score_confidence`
3. Check `score_condition` vs. `score_complaints` — if condition is good but complaints are high, the model reflects that but doesn't override condition data
4. Check `district_rank` — where does it rank among all segments in that district?
5. If the segment isn't in the funded set, run the Budget Scenario and show what budget level funds it

**Key message:** "The segment scored X because its condition is Y and traffic volume is Z. It ranks #N in the district. To fund it in the current cycle, we'd need to either increase the budget by $X or move it above [segment] which has a lower CI and higher traffic."

### Workflow 3: Pre-Winter Maintenance Planning

1. Filter Priority Table: Tier = Medium + High, Road Type = Arterial + Collector
2. Filter by district (coordinate with district supervisors)
3. Sort by `score_condition` descending
4. Look for segments with CI in the 45–60 range (crack seal candidates before freeze-thaw)
5. Cross-reference with weather events data — segments in freeze-thaw-prone areas get a priority bump
6. Export list for crew assignment in Cityworks

### Workflow 4: Updating the Model After New Inspections

1. Export new inspection data from the field tablets or ESRI Field Maps
2. Update `data/road_segments.csv` with the new `condition_index`, `paser_rating`, and `last_inspection_date`
3. Re-run: `python models/prioritization.py`
4. Compare the new top-10 with the previous run — unexpected changes indicate data anomalies
5. Refresh the GIS maps: `python gis/map.py`
6. Notify Operations Manager if any segment moved to Critical tier

---

## 5. Frequently Asked Questions

**Q: Why did [Segment X] rank higher than [Segment Y] even though Y has a worse condition?**
A: The score is a composite. Y may have lower traffic volume or fewer complaints, which reduces its score even if its condition is worse. Use the Score Component Breakdown chart to see exactly why.

**Q: Can I adjust the weights myself to favor complaint-driven prioritization?**
A: The sidebar sliders let you explore different weights, but any weights used for official decision-making must go through the weight governance process documented in `strategy.md`. What you see in the dashboard reflects the current approved configuration.

**Q: Why does the deferral cost seem so high?**
A: The model uses industry-standard cost multipliers from APWA benchmarks. Emergency repairs on deteriorated pavement can genuinely cost 4–5× a preventive treatment. The numbers are not inflated — they're used routinely to justify bond measures and grant applications.

**Q: The complaint count for my district seems low. Is the 311 data complete?**
A: 311 data has known coverage gaps — lower-income neighborhoods tend to underreport. The equity modifier is designed partly to compensate for this. If you believe your district's complaint data is systematically low, raise it with the 311 program manager and work with IT to audit the data pipeline.

**Q: How often should I re-run the model?**
A: Re-run whenever (a) new inspection data is available, (b) the CIP planning cycle begins, or (c) a major weather event has triggered new work orders. Routine monthly re-runs are sufficient in steady state.

**Q: What happens if the model is wrong?**
A: The model is advisory. If field crews find conditions significantly different from what the model reflects, that's a data quality issue — update the inspection record and re-run. Never override the data silently; always document the discrepancy.

---

## 6. Data Governance Reference

### Data Stewardship

| Dataset | Primary Owner | PWIS Point of Contact |
|---------|-------------|----------------------|
| Road Segments | GIS Department | Analytics Lead |
| Work Orders | Public Works Operations | Operations Manager |
| Citizen Complaints | 311 Program Office | Analytics Lead |
| Traffic Counts | ACHD / City Traffic Eng. | GIS Analyst |
| Weather Events | National Weather Service | Data Engineer |
| Budget Actuals | Finance Department | Finance Analyst |

### Retention Policy

| Data Type | Retention Period | Archive Location |
|-----------|-----------------|-----------------|
| Raw inspection records | 10 years | City Document Management |
| Priority scores (snapshot) | 5 years | PWIS database |
| Scenario runs | 3 years | PWIS database |
| Dashboard access logs | 2 years | Azure Monitor |

### Data Request Process

External requests (media, research, public records) for PWIS data should be directed to the City Clerk's office. The Analytics Lead will provide de-identified exports as appropriate. Raw complaint data with citizen contact information is never shared externally.

---

## 7. Troubleshooting

| Issue | Likely Cause | Resolution |
|-------|-------------|-----------|
| Dashboard won't load | Streamlit version mismatch | Run `pip install -r requirements.txt` |
| Priority scores all zero | Model failed to run | Check `python models/prioritization.py` for error output |
| Map shows no markers | Lat/lon columns missing from CSV | Verify `road_segments.csv` has `lat` and `lon` columns |
| Budget scenario shows 0 funded | Treatment costs exceed budget | Lower budget input to realistic level; check cost estimates |
| Weights slider won't go to 1.0 | Rounding in Streamlit sliders | Use the normalize button or enter values manually |
| Score confidence is 0 for all segments | Missing data columns | Check that `condition_index`, `daily_traffic_aadt`, and `estimated_repair_cost_usd` are all present |

---

*For issues not covered here, contact the Analytics Lead. For model logic questions, see `docs/model_logic.md`.*
