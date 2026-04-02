"""
tests/test_prioritization.py
=============================
Unit tests for the PWIS utility prioritization model.
"""
import pytest
import warnings
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from models.prioritization import (
    PWISPrioritizationModel,
    DEFAULT_WEIGHTS,
    MODEL_ASSUMPTIONS,
    ACTION_REPLACE,
    ACTION_REHABILITATE,
    ACTION_LINE,
    ACTION_REPAIR,
    ACTION_MONITOR,
    ACTION_NO_ACTION,
    ACTION_DISPLAY_LABELS,
    ACTION_COST_GUIDANCE,
    MATERIAL_RISK,
    CRITICALITY_MULTIPLIER,
)


# ─── FIXTURES ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_pipes():
    return pd.DataFrame({
        "segment_id":        [f"PIPE-{i:04d}" for i in range(1, 11)],
        "system_type":       ["Water", "Sewer", "Stormwater", "Water", "Sewer",
                              "Water", "Sewer", "Stormwater", "Water", "Sewer"],
        "corridor_name":     [f"Test St {i}" for i in range(1, 11)],
        "district":          ["North End", "Downtown", "East Bench", "Southeast", "Southwest",
                              "West Boise", "North End", "Downtown", "East Bench", "Southeast"],
        "pipe_material":     ["Cast Iron", "Vitrified Clay", "PVC", "Ductile Iron", "HDPE",
                              "Asbestos Cement", "Concrete", "Corrugated Metal", "PVC", "Orangeburg"],
        "diameter_inches":   [8, 12, 24, 6, 36, 10, 15, 48, 8, 6],
        "length_ft":         [500, 1000, 750, 300, 1200, 800, 600, 900, 400, 350],
        "depth_ft":          [4, 8, 5, 3, 12, 6, 10, 4, 5, 7],
        "install_year":      [1955, 1940, 2010, 1990, 2015, 1965, 1980, 1970, 2005, 1950],
        "asset_age_years":   [71, 86, 16, 36, 11, 61, 46, 56, 21, 76],
        "condition_score":   [20, 15, 85, 60, 95, 30, 50, 25, 75, 10],
        "breaks_last_5yr":   [4, 5, 0, 1, 0, 3, 1, 3, 0, 6],
        "capacity_utilization_pct": [60, 90, 50, 70, 40, 85, 75, 95, 55, 88],
        "criticality_class": ["Distribution Main", "Trunk Sewer", "Collector",
                              "Service Line", "Interceptor", "Transmission Main",
                              "Collector", "Collector", "Lateral", "Lateral"],
        "estimated_replacement_cost_usd": [150_000, 300_000, 200_000, 50_000, 400_000,
                                            250_000, 180_000, 280_000, 100_000, 120_000],
        "last_inspection_date": pd.to_datetime([
            "2024-01-15", "2023-06-20", "2025-03-10", "2024-08-05", "2025-01-20",
            "2022-11-30", "2024-03-15", "2023-09-01", "2025-02-28", "2021-04-10",
        ]),
        "inspection_method": ["CCTV"] * 10,
        "lat":  [43.62 + i * 0.005 for i in range(10)],
        "lon":  [-116.20 - i * 0.005 for i in range(10)],
    })

@pytest.fixture
def sample_service_requests():
    return pd.DataFrame({
        "request_id": [f"SR-{i:04d}" for i in range(1, 6)],
        "segment_id": ["PIPE-0001", "PIPE-0001", "PIPE-0002", "PIPE-0005", "PIPE-0010"],
        "system_type": ["Water", "Water", "Sewer", "Sewer", "Sewer"],
        "district": ["North End", "North End", "Downtown", "Southwest", "Southeast"],
        "request_type": ["Main Break", "Low Pressure", "Sewer Backup", "Odor", "Sewer Backup"],
        "submitted_date": ["2025-01-01"] * 5,
        "severity": ["Critical", "Medium", "High", "Low", "Critical"],
        "lat": [43.62, 43.62, 43.625, 43.64, 43.665],
        "lon": [-116.20, -116.20, -116.205, -116.22, -116.245],
    })

@pytest.fixture
def sample_work_orders():
    return pd.DataFrame({
        "work_order_id": [f"WO-{i:04d}" for i in range(1, 4)],
        "segment_id": ["PIPE-0001", "PIPE-0002", "PIPE-0010"],
        "system_type": ["Water", "Sewer", "Sewer"],
        "district": ["North End", "Downtown", "Southeast"],
        "work_order_type": ["Emergency Repair", "Scheduled Rehab", "Emergency Repair"],
        "status": ["Completed", "In Progress", "Completed"],
        "priority": ["Critical", "High", "Critical"],
    })

@pytest.fixture
def model():
    return PWISPrioritizationModel(DEFAULT_WEIGHTS)


# ─── WEIGHT VALIDATION ──────────────────────────────────────────────────────

class TestWeightValidation:
    def test_default_weights_sum_to_one(self):
        assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.001

    def test_default_weights_six_components(self):
        assert len(DEFAULT_WEIGHTS) == 6

    def test_weights_not_summing_to_one_raises(self):
        bad = {k: 0.5 for k in DEFAULT_WEIGHTS}
        with pytest.raises(ValueError, match="sum to 1.0"):
            PWISPrioritizationModel(bad)

    def test_negative_weight_raises(self):
        bad = DEFAULT_WEIGHTS.copy()
        bad["condition_severity"] = -0.1
        # Adjust so they sum to 1.0, but one is negative
        bad["break_history"] = DEFAULT_WEIGHTS["break_history"] + DEFAULT_WEIGHTS["condition_severity"] + 0.1
        with pytest.raises(ValueError, match="non-negative"):
            PWISPrioritizationModel(bad)

    def test_custom_valid_weights(self):
        custom = {k: 1.0 / len(DEFAULT_WEIGHTS) for k in DEFAULT_WEIGHTS}
        # Adjust rounding
        total = sum(custom.values())
        custom["condition_severity"] += 1.0 - total
        model = PWISPrioritizationModel(custom)
        assert abs(sum(model.weights.values()) - 1.0) < 0.01


# ─── SCORING ─────────────────────────────────────────────────────────────────

class TestScoring:
    def test_score_returns_dataframe(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        assert isinstance(result, pd.DataFrame)

    def test_score_has_required_columns(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        required = [
            "priority_score", "priority_tier", "score_confidence",
            "score_condition", "score_breaks", "score_capacity",
            "score_criticality", "score_material", "score_age",
            "action_code", "recommended_action", "district_rank",
        ]
        for col in required:
            assert col in result.columns, f"Missing column: {col}"

    def test_priority_score_range(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        assert result["priority_score"].min() >= 0
        assert result["priority_score"].max() <= 100

    def test_scores_sorted_descending(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        scores = result["priority_score"].values
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    def test_priority_tiers_valid(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        valid_tiers = {"Critical", "High", "Medium", "Low"}
        actual = set(result["priority_tier"].astype(str).unique())
        assert actual.issubset(valid_tiers)

    def test_worse_condition_scores_higher(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        worst = result[result["condition_score"] == result["condition_score"].min()].iloc[0]
        best = result[result["condition_score"] == result["condition_score"].max()].iloc[0]
        assert worst["score_condition"] > best["score_condition"]

    def test_more_breaks_scores_higher(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        most_breaks = result[result["breaks_last_5yr"] == result["breaks_last_5yr"].max()].iloc[0]
        no_breaks = result[result["breaks_last_5yr"] == 0].iloc[0]
        assert most_breaks["score_breaks"] > no_breaks["score_breaks"]

    def test_higher_capacity_scores_higher(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        high_cap = result[result["capacity_utilization_pct"] == result["capacity_utilization_pct"].max()].iloc[0]
        low_cap = result[result["capacity_utilization_pct"] == result["capacity_utilization_pct"].min()].iloc[0]
        assert high_cap["score_capacity"] > low_cap["score_capacity"]

    def test_risky_material_scores_higher(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        orangeburg = result[result["pipe_material"] == "Orangeburg"].iloc[0]
        hdpe = result[result["pipe_material"] == "HDPE"].iloc[0]
        assert orangeburg["score_material"] > hdpe["score_material"]

    def test_confidence_range(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        assert result["score_confidence"].min() >= 0.0
        assert result["score_confidence"].max() <= 1.0

    def test_district_rank_starts_at_one(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        for district in result["district"].unique():
            district_data = result[result["district"] == district]
            assert district_data["district_rank"].min() == 1

    def test_all_segments_present(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        assert len(result) == len(sample_pipes)

    def test_component_scores_in_range(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        for col in ["score_condition", "score_breaks", "score_capacity",
                     "score_criticality", "score_material", "score_age"]:
            assert result[col].min() >= 0, f"{col} has values below 0"
            assert result[col].max() <= 100, f"{col} has values above 100"


# ─── ACTION RECOMMENDATIONS ─────────────────────────────────────────────────

class TestActionRecommendations:
    def test_critical_condition_gets_replace(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        critical = result[result["condition_score"] < 25]
        if len(critical) > 0:
            assert all(critical["action_code"] == ACTION_REPLACE)

    def test_good_condition_gets_monitor_or_no_action(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        good = result[result["condition_score"] >= 80]
        if len(good) > 0:
            assert all(good["action_code"].isin([ACTION_MONITOR, ACTION_NO_ACTION]))

    def test_action_labels_match_codes(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        for _, row in result.iterrows():
            expected_label = ACTION_DISPLAY_LABELS[row["action_code"]]
            assert row["recommended_action"] == expected_label

    def test_all_action_codes_valid(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        valid = {ACTION_REPLACE, ACTION_REHABILITATE, ACTION_LINE, ACTION_REPAIR, ACTION_MONITOR, ACTION_NO_ACTION}
        assert set(result["action_code"].unique()).issubset(valid)

    def test_action_detail_structure(self, model):
        row = {"condition_score": 15, "priority_tier": "Critical"}
        detail = model._recommend_action_detail(row)
        assert "action_code" in detail
        assert "action_label" in detail
        assert "cost_range" in detail
        assert "urgency" in detail

    def test_cost_guidance_covers_all_actions(self):
        for code in ACTION_DISPLAY_LABELS:
            assert code in ACTION_COST_GUIDANCE


# ─── DATA VALIDATION WARNINGS ───────────────────────────────────────────────

class TestDataValidation:
    def test_old_poor_pipe_zero_breaks_warning(self, model):
        pipes = pd.DataFrame({
            "segment_id": ["P1"], "system_type": ["Water"], "corridor_name": ["Test"],
            "district": ["Downtown"], "pipe_material": ["Cast Iron"],
            "diameter_inches": [8], "length_ft": [500], "depth_ft": [4],
            "install_year": [1950], "asset_age_years": [76],
            "condition_score": [15], "breaks_last_5yr": [0],
            "capacity_utilization_pct": [60], "criticality_class": ["Distribution Main"],
            "estimated_replacement_cost_usd": [200_000],
            "last_inspection_date": ["2024-01-01"],
            "lat": [43.62], "lon": [-116.20],
        })
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            model.score(pipes)
            quality_warnings = [x for x in w if "PWIS Data Quality" in str(x.message)]
            assert len(quality_warnings) >= 1

    def test_no_warning_for_good_data(self, model, sample_pipes, sample_service_requests, sample_work_orders):
        """Good data subset should not trigger excessive warnings."""
        good_pipes = sample_pipes[sample_pipes["condition_score"] > 50].copy()
        if len(good_pipes) > 0:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                model.score(good_pipes)
                # Should not have "zero breaks" warnings for healthy pipes
                break_warnings = [x for x in w if "zero breaks" in str(x.message)]
                assert len(break_warnings) == 0


# ─── MODEL ASSUMPTIONS ──────────────────────────────────────────────────────

class TestModelAssumptions:
    def test_assumptions_registry_populated(self):
        assert len(MODEL_ASSUMPTIONS) >= 5

    def test_assumptions_have_required_keys(self):
        for key, data in MODEL_ASSUMPTIONS.items():
            assert "source" in data, f"{key} missing source"
            assert "rationale" in data, f"{key} missing rationale"
            assert "limitation" in data, f"{key} missing limitation"

    def test_material_risk_covers_common_materials(self):
        for mat in ["Cast Iron", "PVC", "HDPE", "Ductile Iron", "Vitrified Clay"]:
            assert mat in MATERIAL_RISK

    def test_criticality_multipliers_cover_classes(self):
        for cls in ["Transmission Main", "Trunk Sewer", "Distribution Main", "Lateral"]:
            assert cls in CRITICALITY_MULTIPLIER

    def test_risky_materials_have_higher_factors(self):
        assert MATERIAL_RISK["Cast Iron"] > MATERIAL_RISK["PVC"]
        assert MATERIAL_RISK["Orangeburg"] > MATERIAL_RISK["HDPE"]

    def test_critical_infrastructure_has_higher_multiplier(self):
        assert CRITICALITY_MULTIPLIER["Transmission Main"] > CRITICALITY_MULTIPLIER["Lateral"]

    def test_assumption_summary_output(self, model):
        summary = model.get_assumption_summary()
        assert "PWIS" in summary
        assert "Source:" in summary

    def test_weight_summary(self, model):
        summary = model.get_weight_summary()
        assert "weights" in summary
        assert abs(summary["total"] - 1.0) < 0.001


# ─── EXPORT ──────────────────────────────────────────────────────────────────

class TestExport:
    def test_export_scores(self, model, sample_pipes, sample_service_requests, sample_work_orders, tmp_path):
        result = model.score(sample_pipes, sample_service_requests, sample_work_orders)
        output = tmp_path / "test_scores.csv"
        model.export_scores(result, str(output))
        assert output.exists()
        loaded = pd.read_csv(output)
        assert "priority_score" in loaded.columns
        assert len(loaded) == len(sample_pipes)


# ─── EDGE CASES ──────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_single_pipe(self, model):
        pipes = pd.DataFrame({
            "segment_id": ["P1"], "system_type": ["Water"], "corridor_name": ["Test"],
            "district": ["Downtown"], "pipe_material": ["PVC"],
            "diameter_inches": [8], "length_ft": [500], "depth_ft": [4],
            "install_year": [2010], "asset_age_years": [16],
            "condition_score": [85], "breaks_last_5yr": [0],
            "capacity_utilization_pct": [50], "criticality_class": ["Distribution Main"],
            "estimated_replacement_cost_usd": [100_000],
            "last_inspection_date": ["2025-01-01"],
            "lat": [43.62], "lon": [-116.20],
        })
        result = model.score(pipes)
        assert len(result) == 1

    def test_no_service_requests(self, model, sample_pipes):
        empty_sr = pd.DataFrame(columns=["request_id", "segment_id", "severity"])
        result = model.score(sample_pipes, empty_sr)
        assert len(result) == len(sample_pipes)

    def test_all_perfect_condition(self, model):
        pipes = pd.DataFrame({
            "segment_id": [f"P{i}" for i in range(5)],
            "system_type": ["Water"] * 5, "corridor_name": [f"St {i}" for i in range(5)],
            "district": ["Downtown"] * 5, "pipe_material": ["PVC"] * 5,
            "diameter_inches": [8] * 5, "length_ft": [500] * 5, "depth_ft": [4] * 5,
            "install_year": [2020] * 5, "asset_age_years": [6] * 5,
            "condition_score": [98, 97, 99, 96, 95], "breaks_last_5yr": [0] * 5,
            "capacity_utilization_pct": [30] * 5, "criticality_class": ["Distribution Main"] * 5,
            "estimated_replacement_cost_usd": [50_000] * 5,
            "last_inspection_date": ["2025-01-01"] * 5,
            "lat": [43.62] * 5, "lon": [-116.20] * 5,
        })
        result = model.score(pipes)
        assert all(result["action_code"] == ACTION_NO_ACTION)

    def test_all_critical_condition(self, model):
        pipes = pd.DataFrame({
            "segment_id": [f"P{i}" for i in range(5)],
            "system_type": ["Sewer"] * 5, "corridor_name": [f"St {i}" for i in range(5)],
            "district": ["Downtown"] * 5, "pipe_material": ["Vitrified Clay"] * 5,
            "diameter_inches": [12] * 5, "length_ft": [500] * 5, "depth_ft": [8] * 5,
            "install_year": [1940] * 5, "asset_age_years": [86] * 5,
            "condition_score": [5, 10, 8, 12, 3], "breaks_last_5yr": [5, 4, 6, 3, 7],
            "capacity_utilization_pct": [90] * 5, "criticality_class": ["Trunk Sewer"] * 5,
            "estimated_replacement_cost_usd": [300_000] * 5,
            "last_inspection_date": ["2024-06-01"] * 5,
            "lat": [43.62] * 5, "lon": [-116.20] * 5,
        })
        result = model.score(pipes)
        assert all(result["action_code"] == ACTION_REPLACE)
