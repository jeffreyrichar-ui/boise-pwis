# Boise Public Works Intelligence System (PWIS)

**A flagship public-sector data analytics portfolio project.**
End-to-end utility infrastructure investment prioritization platform for a mid-size city government — from synthetic data generation through a scored prioritization model, interactive GIS maps, executive Streamlit dashboard, and scenario simulation engine.

> *"Utility infrastructure investment decisions made without data cost cities 3–5x more in the long run. A water main that could be rehabilitated for $80/ft today becomes a $275/ft emergency replacement tomorrow. PWIS makes those decisions systematic, auditable, and defensible."*

---

## What This System Does

PWIS prioritizes capital investment across Boise's **water distribution**, **sanitary sewer**, and **stormwater collection** systems using a weighted multi-criteria scoring model.

For every pipe segment in the network, PWIS produces:
- A **priority score** (0–100) based on condition, break history, capacity stress, criticality, material risk, and age
- A **priority tier** (Critical / High / Medium / Low)
- A **recommended action** (Replace, Rehabilitate, Line, Repair, Monitor, or No Action)
- A **confidence score** reflecting data completeness and inspection freshness

---

## Architecture

```
boise-pwis/
├── data/                    # Synthetic utility datasets (7 tables)
│   ├── generate_data.py     # Data generator — 500 pipe segments + supporting tables
│   ├── pipe_segments.csv    # Water/sewer/stormwater pipe inventory
│   ├── work_orders.csv      # Maintenance work order history
│   ├── service_requests.csv # Citizen service requests (311)
│   ├── facilities.csv       # Treatment plants and pump stations
│   ├── flow_monitoring.csv  # Hydraulic flow monitoring data
│   ├── budget_cip.csv       # CIP budget by district and system
│   └── weather_events.csv   # Precipitation events for I&I analysis
├── models/
│   ├── prioritization.py    # 6-component weighted scoring model
│   └── scenario_engine.py   # What-if: budget, weight, deferral, coverage
├── app/
│   └── streamlit_app.py     # 5-tab executive dashboard
├── gis/
│   └── map.py               # Folium interactive maps (4 views)
├── tests/                   # 107 pytest tests (78%+ coverage)
├── docs/                    # Data model, model logic, GIS maps
├── .github/workflows/       # CI/CD pipeline
└── pyproject.toml           # Project configuration
```

---

## Priority Score Model

```
P = (condition_severity × 0.30)   — Pipe condition from CCTV/acoustic inspection
  + (break_history     × 0.20)   — Break frequency in last 5 years
  + (capacity_stress   × 0.15)   — Hydraulic capacity utilization
  + (criticality       × 0.15)   — System role (transmission main vs. lateral)
  + (material_risk     × 0.12)   — Material-specific failure probability
  + (age_factor        × 0.08)   — Asset age degradation proxy
```

The model includes:
- **Exponential amplification** below condition=40 (structural failure threshold)
- **Material risk factors** from AWWA 2023 data (Orangeburg=0.95, HDPE=0.10)
- **Criticality multipliers** from EPA-CMOM (Transmission Main=1.50, Lateral=0.70)
- **Confidence scoring** based on inspection data freshness and completeness
- **Data quality warnings** for implausible patterns (old pipe + low condition + zero breaks)

---

## Scenario Engine

Four what-if analyses for Council and budget planning:

| Scenario | Question Answered |
|---|---|
| **CIP Budget Allocation** | What gets funded given $X million across water/sewer/stormwater? |
| **Weight Sensitivity** | How does the priority list shift if we emphasize break history over condition? |
| **Deferral Cost** | What is the 5-year cost of NOT replacing the top High/Critical pipes? |
| **Budget Coverage** | How many pipe-feet can we treat at each budget level? |

---

## Data Model

Seven synthetic datasets based on real Boise geography:

| Dataset | Records | Key Fields |
|---|---|---|
| **pipe_segments** | 500 | system_type, pipe_material, condition_score, breaks, capacity |
| **work_orders** | 600 | work_order_type, priority, crew_assigned, cost |
| **service_requests** | 900 | request_type, severity, resolution_status |
| **facilities** | 6 | Real Boise plants (Marden WTP, Lander WRF, etc.) |
| **flow_monitoring** | 960 | avg_flow_pct, peak_flow_pct, I&I flagging |
| **budget_cip** | 30 | CIP allocation by district and system type |
| **weather_events** | 150 | Precipitation events for wet-weather analysis |

Geographic accuracy: 50+ real Boise corridors (State St, Capitol Blvd, Warm Springs Ave, etc.) with correct district assignments and coordinate ranges.

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/jeffreyrichar-ui/boise-pwis.git
cd boise-pwis
pip install -e ".[dev,dashboard]"

# Generate data
python data/generate_data.py

# Run prioritization model
python models/prioritization.py

# Run scenario engine
python models/scenario_engine.py

# Generate GIS maps
python gis/map.py

# Launch dashboard
streamlit run app/streamlit_app.py

# Run tests
pytest
```

---

## Real Boise Infrastructure Context

This system is modeled on actual Boise utility infrastructure:

- **Water Distribution:** 900+ miles of pipe, served by Marden WTP (36 MGD) and Columbia WTP (6 MGD)
- **Sanitary Sewer:** 1,000+ miles of pipe, treated at Lander Street WRF (built 1950, $265M renovation) and West Boise WRF (40 MGD)
- **Stormwater:** Collection system draining to Boise River, managed under MS4 permit
- **Pipe Materials:** Era-appropriate selection — cast iron (pre-1960), asbestos cement (1950s–1980s), ductile iron (1965+), PVC (1970+), HDPE (1990+)
- **Service Districts:** North End, Downtown, East Bench, Southeast, Southwest, West Boise

---

## Technology Stack

- **Python 3.10+** — pandas, numpy, folium, plotly
- **Streamlit** — Interactive executive dashboard
- **Folium** — GIS map visualization with color-blind accessible palettes
- **pytest** — 107 tests across prioritization, scenarios, and data quality
- **GitHub Actions** — CI/CD with lint, test, and coverage gates

---

## License

MIT License. This is a portfolio project using synthetic data. Not affiliated with the City of Boise.
