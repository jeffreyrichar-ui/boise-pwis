# Boise Public Works Intelligence System (PWIS)

**A flagship public-sector data analytics portfolio project.**
End-to-end utility infrastructure investment prioritization platform for a mid-size city government — from synthetic data generation through a scored prioritization model, interactive GIS maps, executive Streamlit dashboard, and scenario simulation engine.

> *"Utility infrastructure investment decisions made without data cost cities 3–5x more in the long run. A sewer main that could be rehabilitated for $80/ft today becomes a $275/ft emergency replacement tomorrow. PWIS makes those decisions systematic, auditable, and defensible."*

---

## What This System Does

PWIS prioritizes capital investment across Boise's **wastewater/sewer collection**, **geothermal district heating**, and **pressurized irrigation (PI)** systems using a weighted multi-criteria scoring model.

For every pipe segment in the network, PWIS produces:
- A **priority score** (0–100) based on condition, break history, capacity stress, criticality, material risk, and age
- A **priority tier** (Critical / High / Medium / Low)
- A **recommended action** (Replace, Rehabilitate, Line, Repair, Monitor, or No Action)
- A **confidence score** reflecting data completeness and inspection freshness

---

## Architecture

```
boise-pwis/
├── data/                    # Synthetic utility datasets
│   ├── generate_data.py     # Data generator — 4830 pipe segments + supporting tables
│   ├── sewer_segments.csv   # Wastewater/sewer collection pipe inventory (4200 segments)
│   ├── geothermal_segments.csv # Geothermal district heating pipeline (350 segments)
│   ├── pi_segments.csv      # Pressurized irrigation system (280 segments)
│   ├── all_segments.csv     # Combined inventory across all systems
│   ├── work_orders.csv      # Maintenance work order history
│   ├── service_requests.csv # Citizen service requests (311)
│   ├── facilities.csv       # WRFs, lift stations, geothermal wells, PI pumps
│   ├── monitoring_data.csv  # Flow/pressure/temperature monitoring data
│   ├── budget_cip.csv       # CIP budget by district and system
│   └── weather_events.csv   # Precipitation events for I&I analysis
├── models/
│   ├── prioritization.py    # 6-component weighted scoring model
│   └── scenario_engine.py   # What-if: budget, weight, deferral, coverage
├── app/
│   └── streamlit_app.py     # 5-tab executive dashboard
├── gis/
│   └── map.py               # Folium interactive maps (4 views)
├── dashboard/
│   └── generate_dashboard.py # Interactive HTML dashboard generator
├── tests/                   # 54 pytest tests (78%+ coverage)
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
| **CIP Budget Allocation** | What gets funded given $X million across sewer/geothermal/PI systems? |
| **Weight Sensitivity** | How does the priority list shift if we emphasize break history over condition? |
| **Deferral Cost** | What is the 5-year cost of NOT replacing the top High/Critical pipes? |
| **Budget Coverage** | How many pipe-feet can we treat at each budget level? |

---

## Data Model

Synthetic datasets based on real Boise geography:

| Dataset | Records | Key Fields |
|---|---|---|
| **sewer_segments** | 4,200 | system_type, pipe_material, condition_score, breaks, capacity, depth |
| **geothermal_segments** | 350 | system_type, pipe_material, temperature, flow_rate, age |
| **pi_segments** | 280 | system_type, pipe_material, pressure_rating, seasonal_status |
| **all_segments** | 4,830 | Combined inventory across all systems |
| **work_orders** | 600 | work_order_type, priority, crew_assigned, cost, system |
| **service_requests** | 900 | request_type, severity, resolution_status, system |
| **facilities** | 11 | Real Boise infrastructure (2 WRFs, 28 lift stations, 3 geothermal wells, PI pumps) |
| **monitoring_data** | 1,440+ | Flow/pressure/temperature monitoring by segment and month |
| **budget_cip** | 30 | CIP allocation by district and system type |
| **weather_events** | 150 | Precipitation events for I&I correlation analysis |

Geographic accuracy: 50+ real Boise corridors (State St, Capitol Blvd, Warm Springs Ave, etc.) across six service districts (North End, Downtown, East Bench, Southeast, Southwest, West Boise) with correct district assignments and coordinate ranges.

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

PWIS models actual Boise Public Works infrastructure across three systems:

**Wastewater/Sewer Collection:**
- ~900 miles of pipe
- 28 lift stations
- 2 Water Reclamation Facilities: Lander Street WRF (built 1950, undergoing $265M rebuild) and West Boise WRF on Joplin Rd

**Geothermal District Heating:**
- 20+ miles of pre-insulated steel pipeline
- 177°F water circulation
- ~90 downtown buildings connected
- One of the largest municipal geothermal systems in the US
- 3 production wells in NE foothills (400–800 ft depth)
- Injection well at Julia Davis Park (3,213 ft depth, 1999)

**Pressurized Irrigation (PI):**
- 14 subdivisions served
- Seasonal operation: April 15–October 15
- Water source: Boise River via canal system

**Note:** Drinking water is managed by Veolia (private utility); stormwater is managed by ACHD (Ada County Highway District).

**Pipe Materials:**
- Sewer: Vitrified Clay, PVC, Concrete, Ductile Iron, HDPE, Orangeburg, Cast Iron
- Geothermal: Steel, Pre-insulated Steel, Transite, HDPE
- PI: PVC PR-SDR, PVC C900, HDPE

**Service Districts:** North End, Downtown, East Bench, Southeast, Southwest, West Boise

---

## Technology Stack

- **Python 3.10+** — pandas, numpy, folium, plotly
- **Streamlit** — Interactive executive dashboard
- **Folium** — GIS map visualization with color-blind accessible palettes
- **pytest** — 54 tests across prioritization, scenarios, and data quality
- **GitHub Actions** — CI/CD with lint, test, and coverage gates

---

## License

MIT License. This is a portfolio project using synthetic data. Not affiliated with the City of Boise.
