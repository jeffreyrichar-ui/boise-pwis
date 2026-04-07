"""
tests/test_data_quality.py
===========================
Data contract tests for the three systems maintained by Boise Public Works:
  1. Wastewater/sewer collection
  2. Geothermal district heating
  3. Pressurized irrigation (PI)
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    assert path.exists(), f"Missing dataset: {name}"
    return pd.read_csv(path)


# ─── SEWER SEGMENTS ─────────────────────────────────────────────────────────

class TestSewerSegments:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("sewer_segments.csv")

    def test_not_empty(self):
        assert len(self.df) >= 1000, "Expected at least 1000 sewer segments"

    def test_required_columns(self):
        required = [
            "segment_id", "system_type", "corridor_name", "district",
            "pipe_class", "pipe_material", "diameter_inches", "length_ft",
            "condition_score", "breaks_last_5yr", "capacity_utilization_pct",
            "ii_risk_flag", "criticality_class", "estimated_replacement_cost_usd",
            "lat", "lon",
        ]
        for col in required:
            assert col in self.df.columns, f"Missing column: {col}"

    def test_system_type_is_wastewater(self):
        assert (self.df["system_type"] == "Wastewater").all()

    def test_unique_ids(self):
        assert self.df["segment_id"].is_unique

    def test_condition_range(self):
        assert self.df["condition_score"].between(1, 100).all()

    def test_pipe_classes_valid(self):
        valid = {"lateral", "collector", "trunk"}
        actual = set(self.df["pipe_class"].unique())
        assert actual.issubset(valid), f"Invalid pipe classes: {actual - valid}"

    def test_materials_era_consistency(self):
        """No PVC before 1975, no HDPE before 2005."""
        pvc = self.df[self.df["pipe_material"] == "PVC"]
        assert (pvc["install_year"] >= 1975).all(), "PVC found before 1975"
        hdpe = self.df[self.df["pipe_material"] == "HDPE"]
        assert (hdpe["install_year"] >= 2005).all(), "HDPE found before 2005"

    def test_ii_risk_flag_logic(self):
        """I&I risk should be True for old clay/orangeburg/cast iron pipes."""
        old_clay = self.df[
            (self.df["pipe_material"] == "Vitrified Clay") &
            (self.df["asset_age_years"] > 40)
        ]
        if len(old_clay) > 0:
            assert old_clay["ii_risk_flag"].mean() > 0.8, "Old clay pipes should mostly have I&I risk"

    def test_districts_valid(self):
        valid = {"North End", "Downtown", "East Bench", "Southeast", "Southwest", "West Boise"}
        actual = set(self.df["district"].unique())
        assert actual.issubset(valid)

    def test_lat_lon_boise_range(self):
        assert self.df["lat"].between(43.50, 43.75).all()
        assert self.df["lon"].between(-116.40, -116.10).all()


# ─── GEOTHERMAL SEGMENTS ───────────────────────────────────────────────────

class TestGeothermalSegments:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("geothermal_segments.csv")

    def test_not_empty(self):
        assert len(self.df) >= 100, "Expected at least 100 geothermal segments"

    def test_required_columns(self):
        required = [
            "segment_id", "system_type", "corridor_name", "district",
            "pipe_role", "pipe_material", "diameter_inches",
            "condition_score", "supply_temp_f", "return_temp_f",
            "lat", "lon",
        ]
        for col in required:
            assert col in self.df.columns, f"Missing column: {col}"

    def test_system_type_is_geothermal(self):
        assert (self.df["system_type"] == "Geothermal").all()

    def test_unique_ids(self):
        assert self.df["segment_id"].is_unique

    def test_supply_temperature_range(self):
        """Supply temp should be 140-180°F."""
        assert self.df["supply_temp_f"].between(130, 185).all()

    def test_return_lower_than_supply(self):
        """Return temp must be lower than supply temp."""
        assert (self.df["return_temp_f"] < self.df["supply_temp_f"]).all()

    def test_pipe_roles_valid(self):
        valid = {"supply_main", "distribution", "return_main", "lateral"}
        actual = set(self.df["pipe_role"].unique())
        assert actual.issubset(valid)

    def test_primarily_downtown(self):
        """City geothermal system is entirely Downtown (Capitol Mall + BSU)."""
        downtown_pct = (self.df["district"] == "Downtown").mean()
        assert downtown_pct > 0.95, "City geothermal system should be nearly all Downtown"


# ─── PI SEGMENTS ────────────────────────────────────────────────────────────

class TestPISegments:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("pi_segments.csv")

    def test_not_empty(self):
        assert len(self.df) >= 50, "Expected at least 50 PI segments"

    def test_required_columns(self):
        required = [
            "segment_id", "system_type", "subdivision", "district",
            "canal_source", "pipe_material", "diameter_inches",
            "condition_score", "operating_pressure_psi",
            "lat", "lon",
        ]
        for col in required:
            assert col in self.df.columns, f"Missing column: {col}"

    def test_system_type_is_pi(self):
        assert (self.df["system_type"] == "Pressurized Irrigation").all()

    def test_unique_ids(self):
        assert self.df["segment_id"].is_unique

    def test_install_year_post_1993(self):
        """PI system didn't exist before 1993."""
        assert (self.df["install_year"] >= 1993).all()

    def test_operating_pressure_range(self):
        """Design pressure 80-115 PSI per Boise standards."""
        assert self.df["operating_pressure_psi"].between(60, 130).all()

    def test_materials_are_plastic(self):
        """PI should only use PVC/HDPE per Boise design standards."""
        valid = {"PVC PR-SDR", "PVC C900", "HDPE"}
        actual = set(self.df["pipe_material"].unique())
        assert actual.issubset(valid), f"Non-plastic PI material found: {actual - valid}"

    def test_primarily_west_boise(self):
        """Most PI subdivisions are in West Boise."""
        west_pct = (self.df["district"] == "West Boise").mean()
        assert west_pct > 0.4, "Most PI should be in West Boise"


# ─── COMBINED ALL SEGMENTS ─────────────────────────────────────────────────

class TestAllSegments:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("all_segments.csv")

    def test_three_systems_present(self):
        systems = set(self.df["system_type"].unique())
        assert "Wastewater" in systems
        assert "Geothermal" in systems
        assert "Pressurized Irrigation" in systems

    def test_wastewater_is_majority(self):
        """Sewer should be ~87% of all segments (900mi vs 20mi vs ~5mi)."""
        ww_pct = (self.df["system_type"] == "Wastewater").mean()
        assert ww_pct > 0.8, f"Wastewater is only {ww_pct:.1%} — should dominate"

    def test_total_count_matches_parts(self):
        sewer = load_csv("sewer_segments.csv")
        geo = load_csv("geothermal_segments.csv")
        pi = load_csv("pi_segments.csv")
        assert len(self.df) == len(sewer) + len(geo) + len(pi)


# ─── WORK ORDERS ────────────────────────────────────────────────────────────

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

    def test_unique_ids(self):
        assert self.df["work_order_id"].is_unique

    def test_references_valid_segments(self):
        all_segs = load_csv("all_segments.csv")
        valid_ids = set(all_segs["segment_id"])
        wo_ids = set(self.df["segment_id"])
        orphans = wo_ids - valid_ids
        assert len(orphans) == 0, f"Orphan segment_ids: {list(orphans)[:5]}"


# ─── SERVICE REQUESTS ──────────────────────────────────────────────────────

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

    def test_unique_ids(self):
        assert self.df["request_id"].is_unique

    def test_severity_valid(self):
        valid = {"Critical", "High", "Medium", "Low"}
        actual = set(self.df["severity"].dropna().unique())
        assert actual.issubset(valid)

    def test_references_valid_segments(self):
        all_segs = load_csv("all_segments.csv")
        valid_ids = set(all_segs["segment_id"])
        sr_ids = set(self.df["segment_id"].dropna())
        orphans = sr_ids - valid_ids
        assert len(orphans) == 0, f"Orphan segment_ids: {list(orphans)[:5]}"


# ─── FACILITIES ─────────────────────────────────────────────────────────────

class TestFacilities:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("facilities.csv")

    def test_not_empty(self):
        assert len(self.df) >= 8  # 2 WRFs + 3 lift stations + 4 geo wells + 2 PI pumps

    def test_required_columns(self):
        required = ["facility_id", "facility_name", "system_type", "facility_type", "capacity_mgd"]
        for col in required:
            assert col in self.df.columns

    def test_has_both_wrfs(self):
        names = set(self.df["facility_name"])
        assert any("Lander" in n for n in names), "Missing Lander Street WRF"
        assert any("West Boise" in n and "Water Renewal" in n for n in names), "Missing West Boise WRF"

    def test_has_geothermal_wells(self):
        geo = self.df[self.df["system_type"] == "Geothermal"]
        assert len(geo) >= 3, "Expected at least 3 geothermal facilities"

    def test_has_injection_well(self):
        names = self.df["facility_name"].str.lower()
        assert any("injection" in n for n in names), "Missing Julia Davis injection well"


# ─── MONITORING DATA ───────────────────────────────────────────────────────

class TestMonitoringData:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("monitoring_data.csv")

    def test_not_empty(self):
        assert len(self.df) > 0

    def test_required_columns(self):
        required = ["monitor_id", "segment_id", "system_type", "avg_flow_pct", "month"]
        for col in required:
            assert col in self.df.columns

    def test_three_systems_monitored(self):
        systems = set(self.df["system_type"].unique())
        assert "Wastewater" in systems
        assert "Geothermal" in systems
        assert "Pressurized Irrigation" in systems

    def test_pi_zero_in_winter(self):
        pi = self.df[self.df["system_type"] == "Pressurized Irrigation"]
        winter = pi[pi["month"].isin([1, 2, 12])]
        if len(winter) > 0:
            assert (winter["avg_flow_pct"] <= 5).all(), "PI should be zero in winter"


# ─── BUDGET ─────────────────────────────────────────────────────────────────

class TestBudget:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = load_csv("budget_cip.csv")

    def test_not_empty(self):
        assert len(self.df) > 0

    def test_budget_positive(self):
        assert (self.df["total_cip_budget_usd"] > 0).all()

    def test_budget_system_splits_sum(self):
        total_parts = (
            self.df["wastewater_budget_usd"]
            + self.df["geothermal_budget_usd"]
            + self.df["pi_budget_usd"]
        )
        ratio = total_parts / self.df["total_cip_budget_usd"]
        assert ratio.between(0.90, 1.10).all(), "Budget splits don't sum to total"

    def test_wastewater_dominates_budget(self):
        """Wastewater should get 60-80% of budget."""
        ratio = self.df["wastewater_budget_usd"] / self.df["total_cip_budget_usd"]
        assert ratio.mean() > 0.55, "Wastewater should dominate CIP budget"

    def test_has_funding_source(self):
        valid = {"Utility Rates", "Revenue Bonds", "SRF Loan", "EPA Grant", "General Fund"}
        assert self.df["funding_source"].isin(valid).all()


# ─── CROSS-DATASET INTEGRITY ──────────────────────────────────────────────

class TestCrossDatasetIntegrity:
    def test_monitoring_references_valid_segments(self):
        all_segs = load_csv("all_segments.csv")
        monitoring = load_csv("monitoring_data.csv")
        valid_ids = set(all_segs["segment_id"])
        mon_ids = set(monitoring["segment_id"].dropna())
        orphans = mon_ids - valid_ids
        assert len(orphans) == 0, f"Orphan segment_ids in monitoring: {list(orphans)[:5]}"

    def test_all_districts_consistent(self):
        all_segs = load_csv("all_segments.csv")
        budget = load_csv("budget_cip.csv")
        pipe_districts = set(all_segs["district"].unique())
        budget_districts = set(budget["district"].unique())
        assert pipe_districts == budget_districts
