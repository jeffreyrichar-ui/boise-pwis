"""
tests/test_data_quality.py
===========================
Data contract tests — validate that the synthetic datasets conform to
the documented schema requirements for the utility pipe system.
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def load_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    assert path.exists(), f"Missing dataset: {name}"
    return pd.read_csv(path)


# ─── PIPE SEGMENTS ───────────────────────────────────────────────────────────

class TestPipeSegments:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("pipe_segments.csv")

    def test_not_empty(self):
        assert len(self.df) > 0

    def test_required_columns(self):
        required = [
            "segment_id", "system_type", "corridor_name", "district",
            "pipe_material", "diameter_inches", "length_ft", "condition_score",
            "breaks_last_5yr", "criticality_class", "estimated_replacement_cost_usd",
            "lat", "lon",
        ]
        for col in required:
            assert col in self.df.columns, f"Missing column: {col}"

    def test_unique_segment_ids(self):
        assert self.df["segment_id"].is_unique

    def test_system_types_valid(self):
        valid = {"Water", "Sewer", "Stormwater", "Pressurized Irrigation"}
        actual = set(self.df["system_type"].unique())
        assert actual.issubset(valid), f"Invalid system types: {actual - valid}"

    def test_condition_score_range(self):
        assert self.df["condition_score"].min() >= 1
        assert self.df["condition_score"].max() <= 100

    def test_breaks_non_negative(self):
        assert (self.df["breaks_last_5yr"] >= 0).all()

    def test_diameter_positive(self):
        assert (self.df["diameter_inches"] > 0).all()

    def test_length_positive(self):
        assert (self.df["length_ft"] > 0).all()

    def test_cost_positive(self):
        assert (self.df["estimated_replacement_cost_usd"] > 0).all()

    def test_districts_valid(self):
        valid = {"North End", "Downtown", "East Bench", "Southeast", "Southwest", "West Boise"}
        actual = set(self.df["district"].unique())
        assert actual.issubset(valid), f"Invalid districts: {actual - valid}"

    def test_lat_lon_boise_range(self):
        assert self.df["lat"].between(43.50, 43.75).all(), "Latitude outside Boise range"
        assert self.df["lon"].between(-116.40, -116.10).all(), "Longitude outside Boise range"

    def test_minimum_segment_count(self):
        assert len(self.df) >= 100, "Expected at least 100 pipe segments"

    def test_all_four_systems_present(self):
        systems = set(self.df["system_type"].unique())
        assert "Water" in systems
        assert "Sewer" in systems
        assert "Stormwater" in systems
        assert "Pressurized Irrigation" in systems


# ─── WORK ORDERS ──────────────────────────────────────────────────────────────

class TestWorkOrders:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("work_orders.csv")

    def test_not_empty(self):
        assert len(self.df) > 0

    def test_required_columns(self):
        required = ["work_order_id", "segment_id", "system_type", "work_order_type", "status"]
        for col in required:
            assert col in self.df.columns

    def test_unique_work_order_ids(self):
        assert self.df["work_order_id"].is_unique

    def test_segment_ids_reference_pipes(self):
        pipes = load_csv("pipe_segments.csv")
        valid_ids = set(pipes["segment_id"])
        wo_ids = set(self.df["segment_id"])
        orphans = wo_ids - valid_ids
        assert len(orphans) == 0, f"Orphan segment_ids in work orders: {list(orphans)[:5]}"


# ─── SERVICE REQUESTS ────────────────────────────────────────────────────────

class TestServiceRequests:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("service_requests.csv")

    def test_not_empty(self):
        assert len(self.df) > 0

    def test_required_columns(self):
        required = ["request_id", "segment_id", "system_type", "request_type", "severity"]
        for col in required:
            assert col in self.df.columns

    def test_unique_request_ids(self):
        assert self.df["request_id"].is_unique

    def test_severity_valid(self):
        valid = {"Critical", "High", "Medium", "Low"}
        actual = set(self.df["severity"].dropna().unique())
        assert actual.issubset(valid), f"Invalid severities: {actual - valid}"


# ─── FACILITIES ──────────────────────────────────────────────────────────────

class TestFacilities:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("facilities.csv")

    def test_not_empty(self):
        assert len(self.df) > 0

    def test_required_columns(self):
        required = ["facility_id", "facility_name", "facility_type", "capacity_mgd"]
        for col in required:
            assert col in self.df.columns

    def test_capacity_positive(self):
        assert (self.df["capacity_mgd"] > 0).all()


# ─── FLOW MONITORING ─────────────────────────────────────────────────────────

class TestFlowMonitoring:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("flow_monitoring.csv")

    def test_not_empty(self):
        assert len(self.df) > 0

    def test_required_columns(self):
        required = ["monitor_id", "segment_id", "system_type", "avg_flow_pct", "peak_flow_pct"]
        for col in required:
            assert col in self.df.columns

    def test_flow_percentages_in_range(self):
        assert self.df["avg_flow_pct"].between(0, 200).all(), "avg_flow_pct out of range"
        assert self.df["peak_flow_pct"].between(0, 300).all(), "peak_flow_pct out of range"

    def test_pi_seasonal_zero_in_winter(self):
        """PI flow should be zero in Jan/Feb/Dec (system is shut down)."""
        pi_flow = self.df[self.df["system_type"] == "Pressurized Irrigation"]
        if len(pi_flow) > 0:
            winter = pi_flow[pi_flow["month"].isin([1, 2, 12])]
            assert (winter["avg_flow_pct"] <= 5).all(), "PI should have near-zero flow in winter"


# ─── BUDGET CIP ──────────────────────────────────────────────────────────────

class TestBudgetCIP:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("budget_cip.csv")

    def test_not_empty(self):
        assert len(self.df) > 0

    def test_required_columns(self):
        required = ["fiscal_year", "district", "total_cip_budget_usd"]
        for col in required:
            assert col in self.df.columns

    def test_budget_positive(self):
        assert (self.df["total_cip_budget_usd"] > 0).all()

    def test_budget_system_splits_sum(self):
        """Water + sewer + stormwater + PI budget dollars should sum to ~total budget."""
        total_parts = (
            self.df["water_budget_usd"]
            + self.df["sewer_budget_usd"]
            + self.df["stormwater_budget_usd"]
            + self.df["pi_budget_usd"]
        )
        ratio = total_parts / self.df["total_cip_budget_usd"]
        assert ratio.between(0.95, 1.05).all(), "System budget splits don't sum to total"

    def test_budget_has_funding_source(self):
        """Each budget record should have a funding source."""
        valid_sources = {"Utility Rates", "Revenue Bonds", "SRF Loan", "EPA Grant", "General Fund"}
        assert self.df["funding_source"].isin(valid_sources).all()


# ─── WEATHER EVENTS ──────────────────────────────────────────────────────────

class TestWeatherEvents:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("weather_events.csv")

    def test_not_empty(self):
        assert len(self.df) > 0

    def test_has_date(self):
        assert "event_date" in self.df.columns or "date" in self.df.columns


# ─── CROSS-DATASET INTEGRITY ─────────────────────────────────────────────────

class TestCrossDatasetIntegrity:
    def test_service_requests_reference_valid_pipes(self):
        pipes = load_csv("pipe_segments.csv")
        srs = load_csv("service_requests.csv")
        valid_ids = set(pipes["segment_id"])
        sr_ids = set(srs["segment_id"].dropna())
        orphans = sr_ids - valid_ids
        assert len(orphans) == 0, f"Orphan segment_ids in service requests: {list(orphans)[:5]}"

    def test_flow_monitoring_references_valid_pipes(self):
        pipes = load_csv("pipe_segments.csv")
        flow = load_csv("flow_monitoring.csv")
        valid_ids = set(pipes["segment_id"])
        flow_ids = set(flow["segment_id"].dropna())
        orphans = flow_ids - valid_ids
        assert len(orphans) == 0, f"Orphan segment_ids in flow monitoring: {list(orphans)[:5]}"

    def test_all_districts_consistent(self):
        pipes = load_csv("pipe_segments.csv")
        budget = load_csv("budget_cip.csv")
        pipe_districts = set(pipes["district"].unique())
        budget_districts = set(budget["district"].unique())
        assert pipe_districts == budget_districts, (
            f"District mismatch: pipes={pipe_districts}, budget={budget_districts}"
        )
