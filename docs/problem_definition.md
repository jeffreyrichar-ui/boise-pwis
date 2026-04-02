# Problem Definition
## Boise Public Works Intelligence System (PWIS)

**Document Type:** Strategic Problem Framing
**Author:** Director of Analytics & Strategy, City of Boise Public Works
**Date:** April 2026
**Status:** Approved — Phase 1 Baseline

---

## 1. Executive Summary

The City of Boise Public Works department manages over 1,200 lane-miles of roadway, 47 bridges, 85,000 stormwater assets, and a fleet of 200+ vehicles — serving a city that has grown 26% in population since 2010. Infrastructure demand is accelerating faster than budget allocations. Decisions about where to invest, when to act, and how to justify those choices are currently made through a combination of institutional knowledge, reactive complaints, and legacy inspection cycles.

This system — the **Public Works Intelligence System (PWIS)** — is designed to change that. It replaces intuition-driven triage with data-driven prioritization, GIS-enabled visibility, and scenario planning tools that connect operational decisions to strategic outcomes.

---

## 2. The Problem Space

### 2.1 Core Problem Statement

> **Public Works leaders cannot efficiently prioritize infrastructure investments because condition data, cost data, citizen impact data, and operational data live in disconnected systems — and no unified decision framework exists.**

This creates four compounding failures:

| Failure | Description | Consequence |
|--------|-------------|-------------|
| **Reactive maintenance** | Work orders triggered by failure, not condition | 3–5× higher cost vs. preventive action |
| **Equity blindness** | Complaints-driven prioritization skews toward vocal neighborhoods | Underserved areas receive deferred maintenance |
| **Budget justification gaps** | No quantitative link between project selection and outcomes | Council funding requests are narratively weak |
| **Operational fragmentation** | Inspection, GIS, CRM, and finance data never joined | No single source of truth for any asset |

### 2.2 Why Now

- Boise's infrastructure investment backlog exceeds $280M (estimated, 2024)
- FHWA and state DOT reporting requirements are increasing
- Citizen 311 complaint volume has grown 40% in 3 years
- Federal infrastructure funds (IIJA) require condition-based project justification
- A new City of Boise Strategic Plan calls for data-driven governance by FY2027

---

## 3. Stakeholder Map

### 3.1 Primary Stakeholders

| Stakeholder | Role | Primary Question | Pain Point |
|-------------|------|-----------------|------------|
| **Public Works Director** | Executive decision-maker | "What should we fund this cycle?" | No unified prioritization framework |
| **City Council / Mayor** | Budget approvers | "Why this project and not that one?" | Can't audit investment rationale |
| **Operations Manager** | Day-to-day execution | "What's the crew assignment this week?" | Work orders not tied to condition data |
| **Finance Director** | Budget steward | "What's the 5-year cost trajectory?" | No lifecycle cost modeling |
| **GIS/IT Team** | Data infrastructure | "How do systems integrate?" | Siloed data with no shared schema |

### 3.2 Secondary Stakeholders

| Stakeholder | Engagement Mode |
|-------------|----------------|
| **Citizens** | Indirect — satisfaction measured through 311 complaints and survey |
| **State DOT** | Reporting compliance — PASER ratings, bridge inspection data |
| **FHWA** | Federal compliance — asset inventory and investment justification |
| **Neighborhood Associations** | Political input — equity considerations in prioritization |

---

## 4. Decisions This System Supports

PWIS is not a reporting tool. It is a **decision support system**. Each component is designed to answer a specific, real-world question:

### Decision Tier 1: Strategic (Annual / Biennial)
- Which capital projects should be funded in the next CIP cycle?
- How does the infrastructure condition index change under different budget scenarios?
- What is the 5-year cost of deferral for high-priority assets?

### Decision Tier 2: Operational (Quarterly / Monthly)
- Which road segments require preventive treatment before winter?
- Which work orders should be escalated based on condition + complaint volume?
- How should limited crew capacity be allocated across competing maintenance needs?

### Decision Tier 3: Real-Time / Reactive (Weekly)
- Which newly reported complaints are likely tied to known deteriorating assets?
- Are there patterns in complaints that indicate an unreported infrastructure failure?

---

## 5. What This System Is NOT

Clarity about scope is a strategic discipline. PWIS explicitly does not:

- Replace field inspection judgment (it informs it)
- Serve as a citizen-facing application (311 integration is read-only)
- Automate work order assignment (it recommends, humans decide)
- Provide real-time sensor or IoT feeds (future phase)
- Replace the City's ERP or asset management system (PWIS sits above it)

---

## 6. Success Metrics

### Operational KPIs (Measurable within 12 months)

| Metric | Baseline (Estimated) | Target |
|--------|---------------------|--------|
| % of maintenance decisions backed by condition data | ~20% | >80% |
| Time to generate capital project justification | 3–5 days | <4 hours |
| % of high-risk assets with scheduled intervention | ~35% | >70% |
| Complaint-to-inspection turnaround time | 14 days | <5 days |

### Strategic KPIs (18–36 months)

| Metric | Target |
|--------|--------|
| Infrastructure Condition Index (ICI) improvement | +5 points (0–100 scale) |
| Ratio of preventive to reactive maintenance spend | Shift from 40/60 to 60/40 |
| Federal grant application win rate | +15% YoY |
| Council budget request approval rate | Baseline + 20% |

---

## 7. Tradeoffs Acknowledged at Problem Framing Stage

| Tradeoff | Decision Made | Rationale |
|----------|--------------|-----------|
| Comprehensive vs. Fast | Build fast with simulated data, design for real data integration | Portfolio + internal proof-of-concept needs speed |
| Prescriptive vs. Explainable | Prioritize explainable scoring over ML black boxes | Director-level tool must be auditable |
| All assets vs. Roads-first | Roads first (highest complaint volume + inspection data availability) | Scope creep kills momentum; roads are 80% of budget pressure |
| Custom build vs. COTS | Custom analytics layer over standard tools (Power BI, Folium, Streamlit) | Demonstrates capability; COTS tools can wrap the model later |

---

## 8. Architecture Philosophy

PWIS is designed as a **layered analytics stack**:

```
Layer 5: Decisions & Actions        [Council, Directors, Operations]
Layer 4: Dashboard & Visualization  [Streamlit, Power BI, GIS Maps]
Layer 3: Analytics & Scoring        [Prioritization Model, Scenario Engine]
Layer 2: Data Integration           [Star Schema, SQL Transforms, Data Quality]
Layer 1: Source Systems             [Inspection DB, 311, GIS, Work Orders, Finance]
```

Each layer is independently replaceable. The analytics logic (Layer 3) does not depend on the dashboard choice. The data model (Layer 2) does not depend on the source system format.

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Data quality is worse than expected | High | High | Validation rules built in; system degrades gracefully with partial data |
| Stakeholder adoption resistance | Medium | High | Executive sponsorship required; pilot with one district first |
| Model scores misused without context | Medium | High | All scores display confidence and data completeness indicators |
| IT integration delays (real data) | High | Medium | System designed to run entirely on synthetic/manual data in interim |
| Score gaming by district managers | Low | Medium | Audit log of score inputs; score components always visible |

---

## 10. Phase Roadmap Summary

| Phase | Deliverable | Timeframe (Portfolio) |
|-------|------------|----------------------|
| 1 | Problem Definition | Week 1 |
| 2 | Data Layer + Schema | Week 1 |
| 3 | Prioritization Model | Week 2 |
| 4 | GIS Layer | Week 2 |
| 5 | Executive Dashboard | Week 3 |
| 6 | Scenario Simulation | Week 3 |
| 7 | Strategy Document | Week 4 |
| 8 | Knowledge Base | Week 4 |
| 9 | README + BI Maturity Layer | Week 4 |

---

*This document is the authoritative problem framing for PWIS. All subsequent design decisions should be evaluated against the decision framework, stakeholder map, and success metrics defined here.*
