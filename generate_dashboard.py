#!/usr/bin/env python3
"""
Generate a professional Boise PWIS Dashboard HTML file
Reads CSV data files and embeds them as JSON
"""

import csv
import json
import os
from pathlib import Path
from datetime import datetime

# Data directory
DATA_DIR = '/sessions/happy-wonderful-hawking/boise-pwis/data/'

def read_csv_to_list(filename):
    """Read CSV file and return list of dictionaries"""
    filepath = os.path.join(DATA_DIR, filename)
    data = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        print(f"✓ Loaded {filename}: {len(data)} rows")
        return data
    except Exception as e:
        print(f"✗ Error loading {filename}: {e}")
        return []

def main():
    print("Loading data files...")

    # Load all data
    priority_scores = read_csv_to_list('priority_scores.csv')
    budget_cip = read_csv_to_list('budget_cip.csv')
    work_orders = read_csv_to_list('work_orders.csv')
    service_requests = read_csv_to_list('service_requests.csv')
    facilities = read_csv_to_list('facilities.csv')

    # Convert to JSON
    priority_json = json.dumps(priority_scores)
    budget_json = json.dumps(budget_cip)
    work_json = json.dumps(work_orders)
    sr_json = json.dumps(service_requests)
    fac_json = json.dumps(facilities)

    print(f"✓ Data loaded: {len(priority_scores)} pipes, {len(budget_cip)} budget entries, "
          f"{len(work_orders)} work orders, {len(service_requests)} service requests, "
          f"{len(facilities)} facilities")

    # Generate HTML as string concatenation
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Boise Public Works Intelligence System (PWIS) - Dashboard</title>

    <!-- Chart.js 4.4.1 -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js"></script>

    <!-- Leaflet 1.9.4 -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>

    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --boise-blue: #003D6B;
            --wastewater: #6b4c9a;
            --geothermal: #dc2626;
            --pi: #059669;
            --critical: #dc2626;
            --high: #ea580c;
            --medium: #ca8a04;
            --low: #16a34a;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-300: #d1d5db;
            --gray-600: #4b5563;
            --gray-900: #111827;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--gray-50);
            color: var(--gray-900);
            line-height: 1.5;
        }

        /* HEADER */
        .header {
            background: white;
            border-bottom: 3px solid var(--boise-blue);
            padding: 20px 30px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .logo {
            height: 60px;
            width: auto;
        }

        .header-text h1 {
            font-size: 24px;
            font-weight: 700;
            color: var(--boise-blue);
            margin-bottom: 5px;
        }

        .header-text p {
            font-size: 13px;
            color: var(--gray-600);
            font-weight: 500;
        }

        .timestamp {
            font-size: 12px;
            color: var(--gray-600);
            text-align: right;
        }

        /* TABS */
        .tabs {
            background: white;
            border-bottom: 1px solid var(--gray-200);
            display: flex;
            padding: 0 30px;
            gap: 30px;
        }

        .tab-btn {
            padding: 16px 0;
            border: none;
            background: none;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            color: var(--gray-600);
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }

        .tab-btn:hover {
            color: var(--boise-blue);
        }

        .tab-btn.active {
            color: var(--boise-blue);
            border-bottom-color: var(--boise-blue);
        }

        /* FILTERS */
        .filter-bar {
            background: white;
            padding: 20px 30px;
            border-bottom: 1px solid var(--gray-200);
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            align-items: end;
        }

        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .filter-group label {
            font-size: 12px;
            font-weight: 600;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .filter-group select,
        .filter-group input {
            padding: 8px 12px;
            border: 1px solid var(--gray-300);
            border-radius: 4px;
            font-size: 13px;
            background: white;
            color: var(--gray-900);
        }

        .filter-group input[type="range"] {
            padding: 0;
            height: 6px;
        }

        .filter-display {
            grid-column: 1 / -1;
            font-size: 12px;
            color: var(--gray-600);
            font-weight: 500;
        }

        /* MAIN CONTENT */
        .container {
            padding: 30px;
            max-width: 100%;
            margin: 0 auto;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        /* KPI CARDS */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .kpi-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid var(--boise-blue);
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        .kpi-label {
            font-size: 12px;
            font-weight: 600;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }

        .kpi-value {
            font-size: 32px;
            font-weight: 700;
            color: var(--boise-blue);
            margin-bottom: 5px;
        }

        .kpi-subtitle {
            font-size: 12px;
            color: var(--gray-600);
        }

        /* CHART CONTAINER */
        .chart-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .chart-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        .chart-title {
            font-size: 14px;
            font-weight: 700;
            color: var(--gray-900);
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--gray-200);
        }

        .chart-wrapper {
            position: relative;
            height: 300px;
        }

        /* WEIGHT SLIDERS */
        .weight-sliders {
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            margin-bottom: 30px;
        }

        .weight-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .weight-header h3 {
            font-size: 14px;
            font-weight: 700;
            color: var(--gray-900);
        }

        .preset-buttons {
            display: flex;
            gap: 8px;
        }

        .preset-btn {
            padding: 6px 12px;
            border: 1px solid var(--gray-300);
            background: white;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }

        .preset-btn:hover {
            background: var(--gray-100);
            border-color: var(--boise-blue);
            color: var(--boise-blue);
        }

        .weight-slider-group {
            margin-bottom: 15px;
        }

        .weight-slider-label {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            font-weight: 600;
            color: var(--gray-600);
            margin-bottom: 8px;
        }

        .weight-slider-label span:last-child {
            color: var(--boise-blue);
            font-weight: 700;
        }

        .weight-slider-label input[type="range"] {
            flex: 1;
            margin: 0 10px;
        }

        /* TABLE */
        .table-container {
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            overflow: hidden;
        }

        .table-wrapper {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }

        thead {
            background: var(--gray-100);
            border-bottom: 2px solid var(--gray-300);
        }

        th {
            padding: 12px;
            text-align: left;
            font-weight: 700;
            color: var(--gray-900);
            cursor: pointer;
            user-select: none;
            white-space: nowrap;
        }

        th:hover {
            background: var(--gray-200);
        }

        td {
            padding: 12px;
            border-bottom: 1px solid var(--gray-200);
        }

        tbody tr:hover {
            background: var(--gray-50);
        }

        /* BADGES */
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            text-align: center;
        }

        .badge-critical {
            background: rgba(220, 38, 38, 0.1);
            color: var(--critical);
        }

        .badge-high {
            background: rgba(234, 88, 12, 0.1);
            color: var(--high);
        }

        .badge-medium {
            background: rgba(202, 138, 4, 0.1);
            color: var(--medium);
        }

        .badge-low {
            background: rgba(22, 163, 74, 0.1);
            color: var(--low);
        }

        /* MAP */
        #map {
            width: 100%;
            height: 600px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }

        /* LEAFLET POPUP CUSTOMIZATION */
        .leaflet-popup-content {
            font-size: 12px !important;
            width: auto !important;
        }

        .leaflet-popup-content p {
            margin: 4px 0;
        }

        /* RESPONSIVE */
        @media (max-width: 1024px) {
            .chart-grid {
                grid-template-columns: 1fr;
            }

            .kpi-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        @media (max-width: 768px) {
            .header {
                flex-direction: column;
                gap: 15px;
                text-align: center;
            }

            .header-left {
                justify-content: center;
                width: 100%;
            }

            .kpi-grid {
                grid-template-columns: 1fr;
            }

            .tabs {
                padding: 0;
                gap: 0;
            }

            .tab-btn {
                flex: 1;
                padding: 12px;
                border-bottom: 2px solid transparent;
            }

            .filter-bar {
                grid-template-columns: 1fr;
            }
        }

        /* UTILITY */
        .full-width {
            grid-column: 1 / -1;
        }

        .text-center {
            text-align: center;
        }

        .mt-20 {
            margin-top: 20px;
        }

        .no-data {
            text-align: center;
            padding: 40px;
            color: var(--gray-600);
        }
    </style>
</head>
<body>

<!-- HEADER -->
<div class="header">
    <div class="header-left">
        <img src="https://www.cityofboise.org/media/17072/citylogo_official.png" alt="City of Boise" class="logo">
        <div class="header-text">
            <h1>Boise PWIS Dashboard</h1>
            <p>Wastewater • Geothermal • Pressurized Irrigation — City of Boise Public Works</p>
        </div>
    </div>
    <div class="timestamp" id="timestamp"></div>
</div>

<!-- TABS -->
<div class="tabs">
    <button class="tab-btn active" onclick="switchTab('overview')">Overview</button>
    <button class="tab-btn" onclick="switchTab('map')">Infrastructure Map</button>
    <button class="tab-btn" onclick="switchTab('rankings')">Priority Rankings</button>
    <button class="tab-btn" onclick="switchTab('budget')">Budget & CIP</button>
    <button class="tab-btn" onclick="switchTab('operations')">Operations</button>
</div>

<!-- GLOBAL FILTERS -->
<div class="filter-bar">
    <div class="filter-group">
        <label>System</label>
        <select id="filterSystem" onchange="applyFilters()">
            <option value="">All Systems</option>
            <option value="Wastewater">Wastewater</option>
            <option value="Geothermal">Geothermal</option>
            <option value="Pressurized Irrigation">Pressurized Irrigation</option>
        </select>
    </div>

    <div class="filter-group">
        <label>District</label>
        <select id="filterDistrict" onchange="applyFilters()">
            <option value="">All Districts</option>
            <option value="Downtown">Downtown</option>
            <option value="North End">North End</option>
            <option value="East Bench">East Bench</option>
            <option value="Southeast">Southeast</option>
            <option value="Southwest">Southwest</option>
            <option value="West Boise">West Boise</option>
        </select>
    </div>

    <div class="filter-group">
        <label>Condition Min</label>
        <input type="range" id="filterConditionMin" min="0" max="100" value="0" onchange="applyFilters()">
    </div>

    <div class="filter-group">
        <label>Condition Max</label>
        <input type="range" id="filterConditionMax" min="0" max="100" value="100" onchange="applyFilters()">
    </div>

    <div class="filter-group">
        <label>Max Age (years)</label>
        <input type="range" id="filterMaxAge" min="0" max="120" value="120" onchange="applyFilters()">
    </div>

    <div class="filter-group">
        <label>Priority Tier</label>
        <select id="filterTier" onchange="applyFilters()">
            <option value="">All Tiers</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
        </select>
    </div>

    <div class="filter-display full-width" id="filterDisplay">0 pipes</div>
</div>

<!-- MAIN CONTENT -->
<div class="container">

<!-- OVERVIEW TAB -->
<div id="overview" class="tab-content active">
    <div class="weight-sliders">
        <div class="weight-header">
            <h3>Scoring Weights</h3>
            <div class="preset-buttons">
                <button class="preset-btn" onclick="applyPreset('balanced')">Balanced</button>
                <button class="preset-btn" onclick="applyPreset('condition')">Condition-First</button>
                <button class="preset-btn" onclick="applyPreset('breaks')">Break-Responsive</button>
                <button class="preset-btn" onclick="applyPreset('capacity')">Capacity-Focused</button>
            </div>
        </div>

        <div class="weight-slider-group">
            <div class="weight-slider-label">
                <span>Condition Severity</span>
                <span><input type="range" id="weightCondition" min="0" max="1" step="0.01" value="0.30" onchange="recalculateScores()"></span>
                <span id="weightConditionVal">0.30</span>
            </div>
        </div>

        <div class="weight-slider-group">
            <div class="weight-slider-label">
                <span>Break History</span>
                <span><input type="range" id="weightBreaks" min="0" max="1" step="0.01" value="0.20" onchange="recalculateScores()"></span>
                <span id="weightBreaksVal">0.20</span>
            </div>
        </div>

        <div class="weight-slider-group">
            <div class="weight-slider-label">
                <span>Capacity Stress</span>
                <span><input type="range" id="weightCapacity" min="0" max="1" step="0.01" value="0.15" onchange="recalculateScores()"></span>
                <span id="weightCapacityVal">0.15</span>
            </div>
        </div>

        <div class="weight-slider-group">
            <div class="weight-slider-label">
                <span>Criticality</span>
                <span><input type="range" id="weightCriticality" min="0" max="1" step="0.01" value="0.15" onchange="recalculateScores()"></span>
                <span id="weightCriticalityVal">0.15</span>
            </div>
        </div>

        <div class="weight-slider-group">
            <div class="weight-slider-label">
                <span>Material Risk</span>
                <span><input type="range" id="weightMaterial" min="0" max="1" step="0.01" value="0.12" onchange="recalculateScores()"></span>
                <span id="weightMaterialVal">0.12</span>
            </div>
        </div>

        <div class="weight-slider-group">
            <div class="weight-slider-label">
                <span>Age Factor</span>
                <span><input type="range" id="weightAge" min="0" max="1" step="0.01" value="0.08" onchange="recalculateScores()"></span>
                <span id="weightAgeVal">0.08</span>
            </div>
        </div>
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Total Pipes</div>
            <div class="kpi-value" id="kpiTotal">0</div>
            <div class="kpi-subtitle">segments in system</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">Critical Count</div>
            <div class="kpi-value" id="kpiCritical">0</div>
            <div class="kpi-subtitle">requiring replacement</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">Avg Condition</div>
            <div class="kpi-value" id="kpiAvgCondition">0</div>
            <div class="kpi-subtitle">scale 0-100</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">Total Breaks (5yr)</div>
            <div class="kpi-value" id="kpiBreaks">0</div>
            <div class="kpi-subtitle">documented failures</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">Est. Replacement Cost</div>
            <div class="kpi-value" id="kpiCost">$0M</div>
            <div class="kpi-subtitle">total infrastructure</div>
        </div>
    </div>

    <div class="chart-grid">
        <div class="chart-container">
            <div class="chart-title">Priority Tier Distribution</div>
            <div class="chart-wrapper">
                <canvas id="chartTierDist"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Pipes by System Type</div>
            <div class="chart-wrapper">
                <canvas id="chartSystemBar"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Condition by District</div>
            <div class="chart-wrapper">
                <canvas id="chartConditionDistrict"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Pipe Materials</div>
            <div class="chart-wrapper">
                <canvas id="chartMaterial"></canvas>
            </div>
        </div>
    </div>
</div>

<!-- MAP TAB -->
<div id="map" class="tab-content">
    <div id="mapContainer" style="margin-bottom: 20px;">
        <div id="map" style="background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);"></div>
    </div>
</div>

<!-- PRIORITY RANKINGS TAB -->
<div id="rankings" class="tab-content">
    <div class="table-container mt-20">
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">ID</th>
                        <th onclick="sortTable(1)">System</th>
                        <th onclick="sortTable(2)">Location</th>
                        <th onclick="sortTable(3)">District</th>
                        <th onclick="sortTable(4)">Material</th>
                        <th onclick="sortTable(5)">Diameter</th>
                        <th onclick="sortTable(6)">Condition</th>
                        <th onclick="sortTable(7)">Breaks (5yr)</th>
                        <th onclick="sortTable(8)">Age (yrs)</th>
                        <th onclick="sortTable(9)">Score</th>
                        <th>Tier</th>
                        <th>Action</th>
                        <th>Est. Cost</th>
                    </tr>
                </thead>
                <tbody id="rankingBody">
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- BUDGET & CIP TAB -->
<div id="budget" class="tab-content">
    <div style="margin-bottom: 20px;">
        <div class="filter-group">
            <label>Fiscal Year</label>
            <input type="range" id="budgetFY" min="2022" max="2026" value="2026" onchange="updateBudgetCharts()">
            <span id="budgetFYLabel">2026</span>
        </div>
    </div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Total Budget (FY)</div>
            <div class="kpi-value" id="kpiBudgetTotal">$0M</div>
            <div class="kpi-subtitle">authorized spending</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">Budget Spent</div>
            <div class="kpi-value" id="kpiBudgetSpent">$0M</div>
            <div class="kpi-subtitle">actual expenditure</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">Projects Planned</div>
            <div class="kpi-value" id="kpiProjectsPlanned">0</div>
            <div class="kpi-subtitle">CIP initiatives</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">Projects Completed</div>
            <div class="kpi-value" id="kpiProjectsCompleted">0</div>
            <div class="kpi-subtitle">delivered projects</div>
        </div>
    </div>

    <div class="chart-grid">
        <div class="chart-container">
            <div class="chart-title">Budget by System</div>
            <div class="chart-wrapper">
                <canvas id="chartBudgetSystem"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Budget by District</div>
            <div class="chart-wrapper">
                <canvas id="chartBudgetDistrict"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Funding Sources</div>
            <div class="chart-wrapper">
                <canvas id="chartFundingSources"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Budget vs Spent</div>
            <div class="chart-wrapper">
                <canvas id="chartBudgetComparison"></canvas>
            </div>
        </div>
    </div>
</div>

<!-- OPERATIONS TAB -->
<div id="operations" class="tab-content">
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Open Work Orders</div>
            <div class="kpi-value" id="kpiOpenWO">0</div>
            <div class="kpi-subtitle">active jobs</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">Emergency WOs</div>
            <div class="kpi-value" id="kpiEmergencyWO">0</div>
            <div class="kpi-subtitle">urgent priority</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">Total Service Requests</div>
            <div class="kpi-value" id="kpiTotalSR">0</div>
            <div class="kpi-subtitle">citizen reports</div>
        </div>

        <div class="kpi-card">
            <div class="kpi-label">Critical SRs</div>
            <div class="kpi-value" id="kpiCriticalSR">0</div>
            <div class="kpi-subtitle">high severity</div>
        </div>
    </div>

    <div class="chart-grid">
        <div class="chart-container">
            <div class="chart-title">Action Codes (Top Distribution)</div>
            <div class="chart-wrapper">
                <canvas id="chartActionCodes"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Work Order Status</div>
            <div class="chart-wrapper">
                <canvas id="chartWOStatus"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Service Request Severity</div>
            <div class="chart-wrapper">
                <canvas id="chartSRSeverity"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">Breaks by Top 20 Corridors</div>
            <div class="chart-wrapper">
                <canvas id="chartBreaksCorridor"></canvas>
            </div>
        </div>
    </div>
</div>

</div>

<!-- EMBEDDED DATA -->
<script>
const priorityScores = ''' + priority_json + ''';
const budgetCIP = ''' + budget_json + ''';
const workOrders = ''' + work_json + ''';
const serviceRequests = ''' + sr_json + ''';
const facilities = ''' + fac_json + ''';

console.log('Data loaded:');
console.log('  Priority Scores:', priorityScores.length);
console.log('  Budget CIP:', budgetCIP.length);
console.log('  Work Orders:', workOrders.length);
console.log('  Service Requests:', serviceRequests.length);
console.log('  Facilities:', facilities.length);

// STATE
let filteredData = [];
let currentSort = { col: 0, dir: 1 };
let mapInstance = null;
let mapMarkers = [];
let charts = {};
let weights = {
    condition: 0.30,
    breaks: 0.20,
    capacity: 0.15,
    criticality: 0.15,
    material: 0.12,
    age: 0.08
};

// Update weight display and apply changes
function updateWeightDisplay() {
    const fields = ['condition', 'breaks', 'capacity', 'criticality', 'material', 'age'];
    fields.forEach(f => {
        const el = document.getElementById('weight' + f.charAt(0).toUpperCase() + f.slice(1));
        const valEl = document.getElementById('weight' + f.charAt(0).toUpperCase() + f.slice(1) + 'Val');
        if (el) {
            weights[f] = parseFloat(el.value);
            valEl.textContent = parseFloat(el.value).toFixed(2);
        }
    });
}

// Apply scoring presets
function applyPreset(preset) {
    const presets = {
        balanced: { condition: 0.30, breaks: 0.20, capacity: 0.15, criticality: 0.15, material: 0.12, age: 0.08 },
        condition: { condition: 0.40, breaks: 0.15, capacity: 0.10, criticality: 0.15, material: 0.12, age: 0.08 },
        breaks: { condition: 0.25, breaks: 0.35, capacity: 0.10, criticality: 0.15, material: 0.10, age: 0.05 },
        capacity: { condition: 0.25, breaks: 0.15, capacity: 0.30, criticality: 0.15, material: 0.10, age: 0.05 }
    };

    if (presets[preset]) {
        Object.assign(weights, presets[preset]);
        // Update sliders
        document.getElementById('weightCondition').value = weights.condition;
        document.getElementById('weightBreaks').value = weights.breaks;
        document.getElementById('weightCapacity').value = weights.capacity;
        document.getElementById('weightCriticality').value = weights.criticality;
        document.getElementById('weightMaterial').value = weights.material;
        document.getElementById('weightAge').value = weights.age;
        updateWeightDisplay();
        recalculateScores();
    }
}

// Recalculate priority scores based on weights
function recalculateScores() {
    updateWeightDisplay();

    priorityScores.forEach(pipe => {
        const score = (
            (parseFloat(pipe.score_condition) || 0) * weights.condition +
            (parseFloat(pipe.score_breaks) || 0) * weights.breaks +
            (parseFloat(pipe.score_capacity) || 0) * weights.capacity +
            (parseFloat(pipe.score_criticality) || 0) * weights.criticality +
            (parseFloat(pipe.score_material) || 0) * weights.material +
            (parseFloat(pipe.score_age) || 0) * weights.age
        );

        pipe.priority_score = score;

        // Recalculate tier
        if (score >= 75) {
            pipe.priority_tier = 'Critical';
        } else if (score >= 55) {
            pipe.priority_tier = 'High';
        } else if (score >= 30) {
            pipe.priority_tier = 'Medium';
        } else {
            pipe.priority_tier = 'Low';
        }

        // Recalculate action code
        const condition = parseFloat(pipe.condition_score) || 0;
        if (pipe.priority_tier === 'Critical') {
            pipe.action_code = 'REPLACE';
            pipe.recommended_action = 'Full Replacement';
        } else if (pipe.priority_tier === 'High') {
            pipe.action_code = condition < 40 ? 'REHABILITATE' : 'LINE';
            pipe.recommended_action = condition < 40 ? 'Rehabilitation' : 'Lining';
        } else if (pipe.priority_tier === 'Medium') {
            pipe.action_code = 'REPAIR';
            pipe.recommended_action = 'Repairs & Maintenance';
        } else {
            pipe.action_code = condition < 80 ? 'MONITOR' : 'NO_ACTION';
            pipe.recommended_action = condition < 80 ? 'Monitor' : 'None';
        }
    });

    applyFilters();
}

// FILTER LOGIC
function applyFilters() {
    const system = document.getElementById('filterSystem').value;
    const district = document.getElementById('filterDistrict').value;
    const conditionMin = parseInt(document.getElementById('filterConditionMin').value);
    const conditionMax = parseInt(document.getElementById('filterConditionMax').value);
    const maxAge = parseInt(document.getElementById('filterMaxAge').value);
    const tier = document.getElementById('filterTier').value;

    filteredData = priorityScores.filter(pipe => {
        if (system && pipe.system_type !== system) return false;
        if (district && pipe.district !== district) return false;
        const cond = parseFloat(pipe.condition_score) || 0;
        if (cond < conditionMin || cond > conditionMax) return false;
        const age = parseFloat(pipe.asset_age_years) || 0;
        if (age > maxAge) return false;
        if (tier && pipe.priority_tier !== tier) return false;
        return true;
    });

    // Update filter display
    document.getElementById('filterDisplay').textContent = filteredData.length + ' pipes';

    // Refresh all content
    refresh();
}

// REFRESH ALL CONTENT
function refresh() {
    updateOverviewKPIs();
    updateOverviewCharts();
    updateRankingsTable();
    updateBudgetCharts();
    updateOperationsKPIs();
    updateOperationsCharts();
    updateMap();
}

// OVERVIEW TAB
function updateOverviewKPIs() {
    const total = filteredData.length;
    const critical = filteredData.filter(p => p.priority_tier === 'Critical').length;
    const avgCondition = total > 0 ? (filteredData.reduce((s, p) => s + (parseFloat(p.condition_score) || 0), 0) / total).toFixed(1) : 0;
    const totalBreaks = filteredData.reduce((s, p) => s + (parseInt(p.breaks_last_5yr) || 0), 0);
    const totalCost = filteredData.reduce((s, p) => s + (parseFloat(p.estimated_replacement_cost_usd) || 0), 0);

    document.getElementById('kpiTotal').textContent = total.toLocaleString();
    document.getElementById('kpiCritical').textContent = critical.toLocaleString();
    document.getElementById('kpiAvgCondition').textContent = avgCondition;
    document.getElementById('kpiBreaks').textContent = totalBreaks.toLocaleString();
    document.getElementById('kpiCost').textContent = '$' + (totalCost / 1000000).toFixed(1) + 'M';
}

function updateOverviewCharts() {
    // Tier Distribution
    const tierData = {
        Critical: filteredData.filter(p => p.priority_tier === 'Critical').length,
        High: filteredData.filter(p => p.priority_tier === 'High').length,
        Medium: filteredData.filter(p => p.priority_tier === 'Medium').length,
        Low: filteredData.filter(p => p.priority_tier === 'Low').length
    };

    updateChart('chartTierDist', 'doughnut', {
        labels: ['Critical', 'High', 'Medium', 'Low'],
        datasets: [{
            data: [tierData.Critical, tierData.High, tierData.Medium, tierData.Low],
            backgroundColor: ['#dc2626', '#ea580c', '#ca8a04', '#16a34a']
        }]
    });

    // System Type Bar
    const systemData = {
        Wastewater: filteredData.filter(p => p.system_type === 'Wastewater').length,
        Geothermal: filteredData.filter(p => p.system_type === 'Geothermal').length,
        'Pressurized Irrigation': filteredData.filter(p => p.system_type === 'Pressurized Irrigation').length
    };

    updateChart('chartSystemBar', 'bar', {
        labels: Object.keys(systemData),
        datasets: [{
            label: 'Pipe Segments',
            data: Object.values(systemData),
            backgroundColor: ['#6b4c9a', '#dc2626', '#059669']
        }]
    });

    // Condition by District
    const districts = [...new Set(filteredData.map(p => p.district))];
    const conditionByDistrict = districts.map(d => {
        const pipes = filteredData.filter(p => p.district === d);
        const avg = pipes.length > 0 ? (pipes.reduce((s, p) => s + (parseFloat(p.condition_score) || 0), 0) / pipes.length) : 0;
        return avg;
    });

    updateChart('chartConditionDistrict', 'bar', {
        labels: districts,
        datasets: [{
            label: 'Avg Condition Score',
            data: conditionByDistrict,
            backgroundColor: '#003D6B'
        }]
    }, true);

    // Materials Pie
    const materialCounts = {};
    filteredData.forEach(p => {
        materialCounts[p.pipe_material] = (materialCounts[p.pipe_material] || 0) + 1;
    });

    updateChart('chartMaterial', 'doughnut', {
        labels: Object.keys(materialCounts),
        datasets: [{
            data: Object.values(materialCounts),
            backgroundColor: ['#003D6B', '#6b4c9a', '#dc2626', '#059669', '#ea580c', '#ca8a04', '#16a34a', '#3b82f6']
        }]
    });
}

// RANKINGS TAB
function updateRankingsTable() {
    const sorted = [...filteredData].sort((a, b) => {
        let aVal = parseFloat(a.priority_score) || 0;
        let bVal = parseFloat(b.priority_score) || 0;
        return (bVal - aVal) * currentSort.dir;
    }).slice(0, 500);

    const tbody = document.getElementById('rankingBody');
    tbody.innerHTML = sorted.map(pipe => {
        const tierLower = pipe.priority_tier.toLowerCase();
        const dash = '-';
        const locName = pipe.location_name || dash;
        const diamStr = (pipe.diameter_inches || '0') + '"';
        const cost = ((parseFloat(pipe.estimated_replacement_cost_usd) || 0) / 1000).toFixed(0) + 'K';
        return '<tr><td>' + pipe.segment_id + '</td><td>' + pipe.system_type + '</td><td>' + locName +
               '</td><td>' + pipe.district + '</td><td>' + pipe.pipe_material + '</td><td>' + diamStr +
               '</td><td>' + parseFloat(pipe.condition_score).toFixed(1) + '</td><td>' + pipe.breaks_last_5yr +
               '</td><td>' + pipe.asset_age_years + '</td><td>' + parseFloat(pipe.priority_score).toFixed(1) +
               '</td><td><span class="badge badge-' + tierLower + '">' + pipe.priority_tier +
               '</span></td><td>' + pipe.action_code + '</td><td>$' + cost + '</td></tr>';
    }).join('');
}

function sortTable(col) {
    currentSort.col = col;
    currentSort.dir *= -1;
    updateRankingsTable();
}

// BUDGET & CIP TAB
function updateBudgetCharts() {
    const fy = parseInt(document.getElementById('budgetFY').value);
    document.getElementById('budgetFYLabel').textContent = fy;

    const fyData = budgetCIP.filter(b => parseInt(b.fiscal_year) === fy);
    const totalBudget = fyData.reduce((s, b) => s + parseFloat(b.total_cip_budget_usd || 0), 0);
    const totalSpent = fyData.reduce((s, b) => s + parseFloat(b.spent_budget_usd || 0), 0);
    const totalPlanned = fyData.reduce((s, b) => s + (parseInt(b.projects_planned) || 0), 0);
    const totalCompleted = fyData.reduce((s, b) => s + (parseInt(b.projects_completed) || 0), 0);

    document.getElementById('kpiBudgetTotal').textContent = '$' + (totalBudget / 1000000).toFixed(1) + 'M';
    document.getElementById('kpiBudgetSpent').textContent = '$' + (totalSpent / 1000000).toFixed(1) + 'M';
    document.getElementById('kpiProjectsPlanned').textContent = totalPlanned;
    document.getElementById('kpiProjectsCompleted').textContent = totalCompleted;

    // Budget by System
    const systemBudget = {
        Wastewater: fyData.reduce((s, b) => s + parseFloat(b.wastewater_budget_usd || 0), 0),
        Geothermal: fyData.reduce((s, b) => s + parseFloat(b.geothermal_budget_usd || 0), 0),
        'Pressurized Irrigation': fyData.reduce((s, b) => s + parseFloat(b.pi_budget_usd || 0), 0)
    };

    updateChart('chartBudgetSystem', 'doughnut', {
        labels: Object.keys(systemBudget),
        datasets: [{
            data: Object.values(systemBudget),
            backgroundColor: ['#6b4c9a', '#dc2626', '#059669']
        }]
    });

    // Budget by District
    const districtBudget = {};
    fyData.forEach(b => {
        districtBudget[b.district] = (districtBudget[b.district] || 0) + parseFloat(b.total_cip_budget_usd || 0);
    });

    updateChart('chartBudgetDistrict', 'bar', {
        labels: Object.keys(districtBudget),
        datasets: [{
            label: 'Budget (USD)',
            data: Object.values(districtBudget),
            backgroundColor: '#003D6B'
        }]
    }, true);

    // Funding Sources
    const fundingSources = {};
    fyData.forEach(b => {
        fundingSources[b.funding_source] = (fundingSources[b.funding_source] || 0) + parseFloat(b.total_cip_budget_usd || 0);
    });

    updateChart('chartFundingSources', 'pie', {
        labels: Object.keys(fundingSources),
        datasets: [{
            data: Object.values(fundingSources),
            backgroundColor: ['#003D6B', '#6b4c9a', '#dc2626', '#059669', '#ea580c', '#ca8a04']
        }]
    });

    // Budget vs Spent
    const districtsList = Object.keys(districtBudget);
    const spentByDistrict = {};
    fyData.forEach(b => {
        spentByDistrict[b.district] = (spentByDistrict[b.district] || 0) + parseFloat(b.spent_budget_usd || 0);
    });

    updateChart('chartBudgetComparison', 'bar', {
        labels: districtsList,
        datasets: [
            { label: 'Planned', data: districtsList.map(d => districtBudget[d]), backgroundColor: '#003D6B' },
            { label: 'Spent', data: districtsList.map(d => spentByDistrict[d] || 0), backgroundColor: '#ea580c' }
        ]
    }, true);
}

// OPERATIONS TAB
function updateOperationsKPIs() {
    const openWO = workOrders.filter(w => w.status !== 'Completed').length;
    const emergencyWO = workOrders.filter(w => w.priority === 'Urgent' || w.priority === 'Emergency').length;
    const totalSR = serviceRequests.length;
    const criticalSR = serviceRequests.filter(s => s.severity === 'High' || s.severity === 'Critical').length;

    document.getElementById('kpiOpenWO').textContent = openWO;
    document.getElementById('kpiEmergencyWO').textContent = emergencyWO;
    document.getElementById('kpiTotalSR').textContent = totalSR;
    document.getElementById('kpiCriticalSR').textContent = criticalSR;
}

function updateOperationsCharts() {
    // Action Codes
    const actionCodes = {};
    filteredData.forEach(p => {
        actionCodes[p.action_code] = (actionCodes[p.action_code] || 0) + 1;
    });

    updateChart('chartActionCodes', 'bar', {
        labels: Object.keys(actionCodes),
        datasets: [{
            label: 'Count',
            data: Object.values(actionCodes),
            backgroundColor: '#003D6B'
        }]
    }, true);

    // WO Status
    const woStatus = {};
    workOrders.forEach(w => {
        woStatus[w.status] = (woStatus[w.status] || 0) + 1;
    });

    updateChart('chartWOStatus', 'doughnut', {
        labels: Object.keys(woStatus),
        datasets: [{
            data: Object.values(woStatus),
            backgroundColor: ['#003D6B', '#ea580c', '#16a34a']
        }]
    });

    // SR Severity
    const srSeverity = {};
    serviceRequests.forEach(s => {
        srSeverity[s.severity] = (srSeverity[s.severity] || 0) + 1;
    });

    updateChart('chartSRSeverity', 'bar', {
        labels: Object.keys(srSeverity),
        datasets: [{
            label: 'Count',
            data: Object.values(srSeverity),
            backgroundColor: '#dc2626'
        }]
    });

    // Top 20 Corridors by Breaks
    const corridorBreaks = {};
    filteredData.forEach(p => {
        const corridor = p.location_name || p.segment_id;
        corridorBreaks[corridor] = (corridorBreaks[corridor] || 0) + parseInt(p.breaks_last_5yr || 0);
    });

    const topCorridors = Object.entries(corridorBreaks)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 20);

    updateChart('chartBreaksCorridor', 'bar', {
        labels: topCorridors.map(c => c[0]),
        datasets: [{
            label: 'Breaks (5yr)',
            data: topCorridors.map(c => c[1]),
            backgroundColor: '#ca8a04'
        }]
    }, true);
}

// MAP
function updateMap() {
    if (!mapInstance) {
        mapInstance = L.map('map').setView([43.615, -116.200], 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(mapInstance);
    }

    // Clear existing markers
    mapMarkers.forEach(m => mapInstance.removeLayer(m));
    mapMarkers = [];

    // Add pipe segment markers (sample max 2000)
    const sampled = filteredData.slice(0, 2000);
    sampled.forEach(pipe => {
        const lat = parseFloat(pipe.lat);
        const lon = parseFloat(pipe.lon);
        if (lat && lon) {
            const tierColors = { Critical: '#dc2626', High: '#ea580c', Medium: '#ca8a04', Low: '#16a34a' };
            const color = tierColors[pipe.priority_tier] || '#003D6B';

            const marker = L.circleMarker([lat, lon], {
                radius: 6,
                fillColor: color,
                color: '#fff',
                weight: 2,
                opacity: 0.8,
                fillOpacity: 0.7
            }).bindPopup(
                '<strong>' + pipe.segment_id + '</strong><br>' +
                'System: ' + pipe.system_type + '<br>' +
                'Material: ' + pipe.pipe_material + '<br>' +
                'Condition: ' + pipe.condition_score + '<br>' +
                'Age: ' + pipe.asset_age_years + ' yrs<br>' +
                'Tier: <strong>' + pipe.priority_tier + '</strong><br>' +
                'Action: ' + pipe.action_code
            ).addTo(mapInstance);

            mapMarkers.push(marker);
        }
    });

    // Add facility markers
    facilities.forEach(fac => {
        const lat = parseFloat(fac.lat);
        const lon = parseFloat(fac.lon);
        if (lat && lon) {
            const marker = L.circleMarker([lat, lon], {
                radius: 10,
                fillColor: '#1f2937',
                color: '#fff',
                weight: 3,
                opacity: 1,
                fillOpacity: 0.8
            }).bindPopup(
                '<strong>' + fac.facility_name + '</strong><br>' +
                'Type: ' + fac.facility_type + '<br>' +
                'System: ' + fac.system_type + '<br>' +
                'Capacity: ' + fac.capacity_mgd + ' MGD<br>' +
                'Condition: ' + fac.condition
            ).addTo(mapInstance);

            mapMarkers.push(marker);
        }
    });
}

// CHART MANAGEMENT
function updateChart(canvasId, type, config, horizontal = false) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    if (charts[canvasId]) {
        charts[canvasId].destroy();
    }

    const options = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: horizontal ? 'right' : 'bottom'
            }
        }
    };

    if (horizontal && (type === 'bar')) {
        options.indexAxis = 'y';
    }

    charts[canvasId] = new Chart(ctx, {
        type: type,
        data: config,
        options: options
    });
}

// TAB SWITCHING
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Deactivate all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(tabName).classList.add('active');
    event.target.classList.add('active');

    // Refresh map if switching to map tab
    if (tabName === 'map') {
        setTimeout(() => {
            if (mapInstance) mapInstance.invalidateSize();
        }, 100);
    }
}

// INIT
function init() {
    document.getElementById('timestamp').textContent = new Date().toLocaleString();

    // Trigger initial filter/refresh
    applyFilters();
}

// Run on load
window.addEventListener('load', init);
</script>

</body>
</html>'''

    # Write HTML file
    output_path = '/sessions/happy-wonderful-hawking/mnt/outputs/pwis-dashboard.html'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✓ Dashboard generated: {output_path}")
    file_size_mb = len(html_content) / 1024 / 1024
    print(f"✓ File size: {file_size_mb:.2f} MB")
    print(f"✓ Ready to open in browser")

if __name__ == '__main__':
    main()
