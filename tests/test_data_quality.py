"""
tests/test_data_quality.py
===========================
Data contract tests — validate that the synthetic datasets and
any real data drop-ins conform to the documented schema requirements.

These tests serve a dual purpose:
  1. CI gate: catch regressions in the data generator
  2. Production onboarding: when real data is substituted, these tests
     will surface schema mismatches before they corrupt model outputs
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def roads():
    return pd.read_csv(DATA_DIR / "road_segments.csv")


@pytest.fixture(scope="module")
def work_orders():
    return pd.read_csv(DATA_DIR / "work_orders.csv")


@pytest.fixture(scope="module")
def complaints():
    return pd.read_csv(DATA_DIR / "complaints.csv")


@pytest.fixture(scope="module")
def budget():
    return pd.read_csv(DATA_DIR / "budget_actuals.csv")


@pytest.fixture(scope="module")
def bridges():
    return pd.read_csv(DATA_DIR / "bridge_inspections.csv")


@pytest.fixture(scope="module")
def traffic():
    return pd.read_csv(DATA_DIR / "traffic_counts.csv")


# ─── ROAD SEGMENTS ────────────────────────────────────────────────────────────


class TestRoadSegments:
    REQUIRED_COLUMNS = [
        "segment_id", "street_name", "district", "road_type", "surface_type",
        "condition_index", "paser_rating", "install_year", "asset_age_years",
        "length_miles", "num_lanes", "daily_traffic_aadt", "lat", "lon",
        "last_inspection_date", "estimated_repair_cost_usd",
    ]
    VALID_ROAD_TYPES     = {"Arterial", "Collector", "Local", "Highway"}
    VALID_SURFACE_TYPES  = {"Asphalt", "Concrete", "Chip Seal"}
    VALID_DISTRICTS      = {
        "North End", "Downtown", "East Bench", "Southeast", "Southwest", "West Boise"
    }

    def test_all_required_columns_present(self, roads):
        missing = [c for c in self.REQUIRED_COLUMNS if c not in roads.columns]
        assert not missing, f"Missing columns: {missing}"

    def test_segment_ids_are_unique(self, roads):
        dupes = roads[roads["segment_id"].duplicated()]["segment_id"].tolist()
        assert not dupes, f"Duplicate segment_ids: {dupes[:5]}"

    def test_segment_ids_not_null(self, roads):
        assert roads["segment_id"].notna().all()

    def test_condition_index_in_valid_range(self, roads):
        bad = roads[~roads["condition_index"].between(1, 100)]
        assert len(bad) == 0, (
            f"{len(bad)} segments have condition_index outside [1, 100]: "
            f"{bad['condition_index'].describe()}"
        )

    def test_paser_rating_in_valid_range(self, roads):
        bad = roads[~roads["paser_rating"].between(1, 10)]
        assert len(bad) == 0

    def test_road_types_are_canonical(self, roads):
        bad = set(roads["road_type"].unique()) - self.VALID_ROAD_TYPES
        assert not bad, f"Non-canonical road types found: {bad}"

    def test_surface_types_are_canonical(self, roads):
        bad = set(roads["surface_type"].unique()) - self.VALID_SURFACE_TYPES
        assert not bad, f"Non-canonical surface types: {bad}"

    def test_districts_are_canonical(self, roads):
        bad = set(roads["district"].unique()) - self.VALID_DISTRICTS
        assert not bad, f"Non-canonical districts: {bad}"

    def test_lat_within_boise_bounds(self, roads):
        bad = roads[~roads["lat"].between(43.5, 43.8)]
        assert len(bad) == 0, f"{len(bad)} segments have lat outside Boise bounds"

    def test_lon_within_boise_bounds(self, roads):
        bad = roads[~roads["lon"].between(-116.4, -116.0)]
        assert len(bad) == 0, f"{len(bad)} segments have lon outside Boise bounds"

    def test_length_miles_positive(self, roads):
        assert (roads["length_miles"] > 0).all()

    def test_aadt_non_negative(self, roads):
        assert (roads["daily_traffic_aadt"] >= 0).all()

    def test_install_year_plausible(self, roads):
        bad = roads[~roads["install_year"].between(1900, 2026)]
        assert len(bad) == 0

    def test_repair_cost_positive(self, roads):
        assert (roads["estimated_repair_cost_usd"] > 0).all()

    def test_minimum_expected_row_count(self, roads):
        assert len(roads) >= 50, f"Only {len(roads)} segments; expected at least 50"

    def test_all_districts_represented(self, roads):
        """Every canonical district must have at least one segment."""
        present = set(roads["district"].unique())
        missing = self.VALID_DISTRICTS - present
        assert not missing, f"Districts with no segments: {missing}"


# ─── WORK ORDERS ──────────────────────────────────────────────────────────────


class TestWorkOrders:
    VALID_STATUSES    = {"Open", "In Progress", "Completed", "Deferred"}
    VALID_PRIORITIES  = {"Critical", "High", "Medium", "Low"}

    def test_work_order_ids_unique(self, work_orders):
        dupes = work_orders[work_orders["work_order_id"].duplicated()]
        assert len(dupes) == 0, f"Duplicate work_order_ids: {len(dupes)}"

    def test_statuses_are_canonical(self, work_orders):
        bad = set(work_orders["status"].unique()) - self.VALID_STATUSES
        assert not bad, f"Non-canonical statuses: {bad}"

    def test_priorities_are_canonical(self, work_orders):
        bad = set(work_orders["priority"].unique()) - self.VALID_PRIORITIES
        assert not bad, f"Non-canonical priorities: {bad}"

    def test_completed_date_after_created_date(self, work_orders):
        """Completed work orders must have completed_date >= created_date."""
        completed = work_orders[work_orders["status"] == "Completed"].copy()
        completed["created_date"]   = pd.to_datetime(completed["created_date"])
        completed["completed_date"] = pd.to_datetime(completed["completed_date"])
        bad = completed[completed["completed_date"] < completed["created_date"]]
        assert len(bad) == 0, (
            f"{len(bad)} work orders have completed_date before created_date"
        )

    def test_segment_ids_reference_valid_segments(self, work_orders, roads):
        valid_segs = set(roads["segment_id"])
        orphaned = set(work_orders["segment_id"]) - valid_segs
        assert not orphaned, (
            f"Work orders reference {len(orphaned)} unknown segment_ids: "
            f"{list(orphaned)[:5]}"
        )


# ─── COMPLAINTS ───────────────────────────────────────────────────────────────


class TestComplaints:
    VALID_SEVERITIES = {"Low", "Medium", "High", "Critical"}
    VALID_STATUSES   = {"Resolved", "Pending", "In Review"}

    def test_complaint_ids_unique(self, complaints):
        dupes = complaints[complaints["complaint_id"].duplicated()]
        assert len(dupes) == 0

    def test_severity_values_canonical(self, complaints):
        bad = set(complaints["severity_reported"].unique()) - self.VALID_SEVERITIES
        assert not bad, f"Non-canonical severities: {bad}"

    def test_resolution_status_canonical(self, complaints):
        bad = set(complaints["resolution_status"].unique()) - self.VALID_STATUSES
        assert not bad, f"Non-canonical resolution statuses: {bad}"

    def test_resolved_date_after_submitted(self, complaints):
        resolved = complaints[complaints["resolution_status"] == "Resolved"].copy()
        resolved = resolved.dropna(subset=["resolved_date"])
        resolved["submitted_date"] = pd.to_datetime(resolved["submitted_date"])
        resolved["resolved_date"]  = pd.to_datetime(resolved["resolved_date"])
        bad = resolved[resolved["resolved_date"] < resolved["submitted_date"]]
        assert len(bad) == 0, (
            f"{len(bad)} complaints have resolved_date before submitted_date"
        )

    def test_segment_ids_reference_valid_segments(self, complaints, roads):
        valid_segs = set(roads["segment_id"])
        orphaned = set(complaints["segment_id"]) - valid_segs
        assert not orphaned, (
            f"Complaints reference {len(orphaned)} unknown segment_ids"
        )


# ─── BUDGET ───────────────────────────────────────────────────────────────────


class TestBudget:
    def test_budget_pct_columns_sum_to_100_or_less(self, budget):
        pct_sum = budget["preventive_pct"] + budget["reactive_pct"] + budget["capital_pct"]
        bad = budget[pct_sum > 101]  # 1% tolerance for rounding
        assert len(bad) == 0, (
            f"{len(bad)} rows have pct columns summing > 100%: {pct_sum[pct_sum > 101].values}"
        )

    def test_satisfaction_score_in_range(self, budget):
        bad = budget[~budget["citizen_satisfaction_score"].between(0, 5)]
        assert len(bad) == 0

    def test_allocated_budget_positive(self, budget):
        assert (budget["allocated_budget_usd"] > 0).all()


# ─── BRIDGES ──────────────────────────────────────────────────────────────────


class TestBridges:
    VALID_CONDITIONS = {"Good", "Fair", "Poor", "Critical"}

    def test_bridge_ids_unique(self, bridges):
        assert not bridges["bridge_id"].duplicated().any()

    def test_deck_condition_canonical(self, bridges):
        bad = set(bridges["deck_condition"].unique()) - self.VALID_CONDITIONS
        assert not bad, f"Non-canonical deck conditions: {bad}"

    def test_sufficiency_rating_in_range(self, bridges):
        bad = bridges[~bridges["sufficiency_rating"].between(0, 100)]
        assert len(bad) == 0


# ─── TRAFFIC ──────────────────────────────────────────────────────────────────


class TestTraffic:
    def test_month_in_valid_range(self, traffic):
        bad = traffic[~traffic["month"].between(1, 12)]
        assert len(bad) == 0

    def test_aadt_positive(self, traffic):
        assert (traffic["aadt"] > 0).all()

    def test_congestion_index_bounded(self, traffic):
        bad = traffic[~traffic["congestion_index"].between(0, 1)]
        assert len(bad) == 0
