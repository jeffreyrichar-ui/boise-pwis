# Boise Public Works Intelligence System (PWIS)

**Executive analytics dashboard for Boise's three public pipe infrastructure systems.**

### [View Live Dashboard](https://jeffreyrichar-ui.github.io/boise-pwis/)

An end-to-end public-sector data analytics project: synthetic data generation, condition scoring model, interactive GIS mapping, and executive dashboards for Wastewater, Geothermal District Heating, and Pressurized Irrigation.

---

## Systems Modeled

| System | Segments | Miles | Description |
|---|---|---|---|
| **Wastewater Collection** | 4,200 | 1,068 | Sewer mains across 6 service districts — the big capital program |
| **Geothermal District Heating** | 350 | 31 | Downtown-only hot water loop (Capitol Mall 1983, BSU 2013) |
| **Pressurized Irrigation** | 280 | 36 | Seasonal system serving 14 West Boise subdivisions |

## Executive Dashboard

The [live dashboard](https://jeffreyrichar-ui.github.io/boise-pwis/) is a self-contained HTML file with:

- **Interactive map** with system layers (toggle wastewater/geothermal/PI), color-coded by condition
- **System-specific controls** — budget and replacement rate for sewer; pipe role for geothermal; subdivision and canal source for PI
- **Condition distribution** with fixed tiers: Critical (<30), Poor (30–49), Fair (50–69), Good (70+)
- **System-appropriate KPIs** — backlog cost and budget gap for sewer; supply/return temps for geothermal; operating pressure for PI
- **Canvas-based charts** — no external charting library, all drawn natively

Target: ~3% critical rate for wastewater (realistic for a well-maintained system), near-zero for the newer geothermal and PI systems.

---

## Condition Scoring Model

Each pipe segment gets a condition score (0–100) driven by material, age, and soil corrosivity:

```
condition = base_score - (age × annual_decay) - (age × 0.11 × soil_factor) + noise
```

Where `base_score` and `annual_decay` vary by material fail rate (high/medium/low), and `soil_factor` reflects district-level corrosivity for metallic and clay pipes.

Tier thresholds are fixed at industry-standard breakpoints: Critical [0,30), Poor [30,50), Fair [50,70), Good [70,100].

---

## Priority Score Model

```
P = (condition_severity × 0.30)
  + (break_history     × 0.20)
  + (capacity_stress   × 0.15)
  + (criticality       × 0.15)
  + (material_risk     × 0.12)
  + (age_factor        × 0.08)
```

Includes exponential amplification below condition 40, AWWA-based material risk factors, and EPA-CMOM criticality multipliers.

---

## Architecture

```
boise-pwis/
├── data/
│   ├── generate_data.py          # Generates all 3 systems + supporting tables
│   ├── sewer_segments.csv        # 4,200 wastewater pipe segments
│   ├── geothermal_segments.csv   # 350 geothermal pipe segments
│   ├── pi_segments.csv           # 280 pressurized irrigation segments
│   └── ...                       # work orders, service requests, monitoring, weather
├── models/
│   ├── prioritization.py         # 6-component weighted scoring model
│   └── scenario_engine.py        # Budget, weight sensitivity, deferral cost scenarios
├── build_exec_dashboard.py       # Generates self-contained HTML dashboard
├── docs/
│   └── index.html                # Live dashboard (GitHub Pages source)
├── tests/                        # 54 pytest tests
└── .github/workflows/            # CI/CD pipeline
```

---

## Quick Start

```bash
git clone https://github.com/jeffreyrichar-ui/boise-pwis.git
cd boise-pwis
pip install -e ".[dev,dashboard]"

# Regenerate data
python data/generate_data.py

# Rebuild dashboard
python build_exec_dashboard.py

# Run tests
pytest
```

---

## Real Boise Infrastructure Context

PWIS models actual City of Boise Public Works infrastructure:

**Wastewater** — ~900 miles of pipe, 28 lift stations, 2 Water Reclamation Facilities (Lander Street WRF undergoing $265M rebuild, West Boise WRF). Materials: Vitrified Clay, PVC, Concrete, Ductile Iron, HDPE, Orangeburg, Cast Iron.

**Geothermal** — 100% Downtown. One of the largest municipal geothermal systems in the US. 177°F water from 3 production wells in the NE foothills, serving ~90 downtown buildings. Materials: Steel, Pre-insulated Steel, HDPE. (Note: the Warm Springs Avenue system is operated by Boise Warm Springs Water District, not City PW.)

**Pressurized Irrigation** — 14 real subdivisions (Azure #1–3, Darien, Bradford, Graystone #1–2, Steamboat, Linshire, Whidby, Chaucer, Eronel, Palm Court, Ashbrook) in West Boise. Seasonal April 15–October 15. Water sourced from Boise River via Settlers Irrigation, Boise City Canal, and Ridenbaugh Canal. Materials: PVC PR-SDR, PVC C900, HDPE.

Drinking water is managed by Veolia (private utility); stormwater by ACHD.

---

## Technology

Python 3.10+ (pandas, numpy), Leaflet.js with CARTO tiles, canvas-based charts, pytest (54 tests). Single-file HTML output (~2.2MB) with embedded JSON data — no server required.

---

## License

MIT License. Portfolio project using synthetic data. Not affiliated with the City of Boise.
