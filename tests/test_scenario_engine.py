"""
tests/test_scenario_engine.py
==============================
Unit tests for the PWIS utility scenario simulation engine.
"""
import pytest
import warnings
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from models.scenario_engine import (
    PWISScenarioEngine,
    REPLACEMENT_COST_PER_LF,
    DEFERRAL_COST_MULTIPLIER,
    ANNUAL_DETERIORATION_RATE,
    OPERATIONAL_CONSTRAINTS,
    ScenarioResult,
)
from models.prioritization import DEFAULT_WEIGHTS


# ─── FIXTURES ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_pipes():
    np.random.seed(42)
    n = 20
    return pd.DataFrame({
        "segment_id":        [f"PIPE-{i:04d}" for i in range(1, n + 1)],
        "system_type":       np.random.choice(["Water", "Sewer", "Stormwater"], n),
        "corridor_name":     [f"Test Corridor {i}" for i in range(1, n + 1)],
        "district":          np.random.choice(["North End", "Downtown", "Southeast", "West Boise"], n),
        "pipe_material":     np.random.choice(["Cast Iron", "PVC", "Ductile Iron", "Vitrified Clay"], n),
        "diameter_inches":   np.random.choice([6, 8, 12, 24, 36], n),
        "length_ft":         np.random.randint(200, 2000, n),
        "depth_ft":          np.random.randint(3, 15, n),
        "install_year":      np.random.randint(1940, 2020, n),
        "asset_age_years":   np.random.randint(5, 85, n),
        "condition_score":   np.random.randint(5, 98, n),
        "breaks_last_5yr":   np.random.randint(0, 6, n),
        "capacity_utilization_pct": np.random.randint(20, 98, n),
        "criticality_class": np.random.choice(["Distribution Main", "Trunk Sewer", "Collector", "Lateral"], n),
        "estimated_replacement_cost_usd": np.random.randint(50_000, 500_000, n),
        "last_inspection_date": pd.to_datetime("2024-06-01"),
        "lat":  43.615 + np.random.uniform(-0.03, 0.03, n),
        "lon":  -116.200 + np.random.uniform(-0.04, 0.04, n),
    })

@pytest.fixture
def sample_service_requests():
    return pd.DataFrame({
        "request_id": [f"SR-{i}" for i in range(1, 6)],
        "segment_id": [f"PIPE-{i:04d}" for i in range(1, 6)],
        "system_type": ["Water", "Sewer", "Water", "Sewer", "Stormwater"],
        "district": ["Downtown"] * 5,
        "request_type": ["Main Break"] * 5,
        "submitted_date": ["2025-01-01"] * 5,
        "severity": ["High"] * 5,
        "lat": [43.62] * 5, "lon": [-116.20] * 5,
    })

@pytest.fixture
def sample_work_orders():
    return pd.DataFrame({
        "work_order_id": [f"WO-{i}" for i in range(1, 4)],
        "segment_id": ["PIPE-0001", "PIPE-0002", "PIPE-0003"],
        "system_type": ["Water", "Sewer", "Water"],
        "district": ["Downtown"] * 3,
        "work_order_type": ["Emergency Repair"] * 3,
        "status": ["Completed"] * 3,
        "priority": ["Critical"] * 3,
    })

@pytest.fixture
def engine(sample_pipes, sample_service_requests, sample_work_orders):
    return PWISScenarioEngine(sample_pipes, sample_service_requests, sample_work_orders)


# ─── COST CONSTANTS ──────────────────────────────────────────────────────────

class TestCostConstants:
    def test_replacement_costs_positive(self):
        for code, cost in REPLACEMENT_COST_PER_LF.items():
            assert cost >= 0, f"{code} has negative cost"

    def test_replacement_costs_ordered(self):
        from models.prioritization import ACTION_REPLACE, ACTION_REHABILITATE, ACTION_LINE
        assert REPLACEMENT_COST_PER_LF[ACTION_REPLACE] > REPLACEMENT_COST_PER_LF[ACTION_REHABILITATE]
        assert REPLACEMENT_COST_PER_LF[ACTION_REHABILITATE] > REPLACEMENT_COST_PER_LF[ACTION_LINE]

    def test_deferral_multipliers_increase_with_severity(self):
        assert DEFERRAL_COST_MULTIPLIER["Critical"]["value"] > DEFERRAL_COST_MULTIPLIER["High"]["value"]
        assert DEFERRAL_COST_MULTIPLIER["High"]["value"] > DEFERRAL_COST_MULTIPLIER["Medium"]["value"]

    def test_deferral_multipliers_have_ranges(self):
        for tier, info in DEFERRAL_COST_MULTIPLIER.items():
            lo, hi = info["range"]
            assert lo < info["value"] < hi or lo <= info["value"] <= hi

    def test_deterioration_rates_positive(self):
        for mat, rate in ANNUAL_DETERIORATION_RATE.items():
            assert rate > 0, f"{mat} has non-positive deterioration rate"

    def test_operational_constraints_populated(self):
        assert "max_crew_capacity_pipe_feet_per_year" in OPERATIONAL_CONSTRAINTS
        assert "construction_season_months" in OPERATIONAL_CONSTRAINTS


# ─── BUDGET SCENARIO ─────────────────────────────────────────────────────────

class TestBudgetScenario:
    def test_budget_returns_tuple(self, engine):
        scores, result = engine.run_budget_scenario(10_000_000)
        assert isinstance(scores, pd.DataFrame)
        assert isinstance(result, ScenarioResult)

    def test_funded_column_exists(self, engine):
        scores, _ = engine.run_budget_scenario(10_000_000)
        assert "funded_this_cycle" in scores.columns

    def test_some_segments_funded(self, engine):
        scores, result = engine.run_budget_scenario(10_000_000)
        assert result.summary_metrics["segments_funded"] > 0

    def test_budget_not_exceeded(self, engine):
        budget = 5_000_000
        scores, result = engine.run_budget_scenario(budget)
        assert result.summary_metrics["budget_utilized"] <= budget + 1  # float tolerance

    def test_zero_budget_funds_nothing(self, engine):
        scores, result = engine.run_budget_scenario(0)
        assert result.summary_metrics["segments_funded"] == 0

    def test_huge_budget_funds_all(self, engine):
        scores, result = engine.run_budget_scenario(999_999_999)
        total_pipes = len(scores)
        assert result.summary_metrics["segments_funded"] == total_pipes

    def test_system_filter(self, engine):
        scores, result = engine.run_budget_scenario(10_000_000, system_filter="Water")
        if len(scores) > 0:
            assert all(scores["system_type"] == "Water")

    def test_summary_metrics_present(self, engine):
        _, result = engine.run_budget_scenario(10_000_000)
        expected_keys = [
            "total_budget", "segments_funded", "segments_unfunded",
            "budget_utilized", "budget_remaining", "pct_budget_used",
            "pipe_feet_treated",
        ]
        for key in expected_keys:
            assert key in result.summary_metrics, f"Missing metric: {key}"

    def test_scenario_result_type(self, engine):
        _, result = engine.run_budget_scenario(10_000_000)
        assert result.scenario_type == "CIP Budget Allocation"
        assert result.scenario_id.startswith("BUDGET-")


# ─── WEIGHT SCENARIO ─────────────────────────────────────────────────────────

class TestWeightScenario:
    def test_weight_scenario_returns_comparison(self, engine):
        custom = {
            "condition_severity": 0.20, "break_history": 0.35,
            "capacity_stress": 0.15, "criticality": 0.15,
            "material_risk": 0.10, "age_factor": 0.05,
        }
        comparison, summary = engine.run_weight_scenario(custom, "Break-First")
        assert isinstance(comparison, pd.DataFrame)
        assert isinstance(summary, dict)

    def test_weight_scenario_has_rank_shift(self, engine):
        custom = {
            "condition_severity": 0.10, "break_history": 0.10,
            "capacity_stress": 0.10, "criticality": 0.10,
            "material_risk": 0.50, "age_factor": 0.10,
        }
        comparison, _ = engine.run_weight_scenario(custom)
        assert "rank_shift" in comparison.columns
        assert "tier_changed" in comparison.columns

    def test_weight_scenario_stability_metric(self, engine):
        custom = DEFAULT_WEIGHTS.copy()
        _, summary = engine.run_weight_scenario(custom, "Same as baseline")
        assert "top10_stability" in summary
        # Same weights should give perfect stability
        assert summary["top10_stability"] == 1.0

    def test_invalid_weights_raise(self, engine):
        bad = {k: 0.5 for k in DEFAULT_WEIGHTS}
        with pytest.raises(ValueError):
            engine.run_weight_scenario(bad)


# ─── DEFERRAL SCENARIO ──────────────────────────────────────────────────────

class TestDeferralScenario:
    def test_deferral_returns_dataframe(self, engine):
        result = engine.run_deferral_scenario(years=3)
        assert isinstance(result, pd.DataFrame)

    def test_deferral_years_column(self, engine):
        result = engine.run_deferral_scenario(years=5)
        if len(result) > 0:
            assert "year_deferred" in result.columns
            assert result["year_deferred"].max() == 5
            assert result["year_deferred"].min() == 0

    def test_deferral_cost_increases(self, engine):
        result = engine.run_deferral_scenario(years=5)
        if len(result) > 0:
            seg = result[result["segment_id"] == result["segment_id"].iloc[0]]
            year0_cost = seg[seg["year_deferred"] == 0]["projected_cost"].iloc[0]
            year5_cost = seg[seg["year_deferred"] == 5]["projected_cost"].iloc[0]
            assert year5_cost >= year0_cost

    def test_deferral_condition_degrades(self, engine):
        result = engine.run_deferral_scenario(years=5)
        if len(result) > 0:
            seg = result[result["segment_id"] == result["segment_id"].iloc[0]]
            year0_cond = seg[seg["year_deferred"] == 0]["projected_condition"].iloc[0]
            year5_cond = seg[seg["year_deferred"] == 5]["projected_condition"].iloc[0]
            assert year5_cond <= year0_cond

    def test_deferral_has_uncertainty_bounds(self, engine):
        result = engine.run_deferral_scenario(years=3)
        if len(result) > 0:
            assert "low_bound_projected" in result.columns
            assert "high_bound_projected" in result.columns

    def test_specific_segments_deferral(self, engine, sample_pipes):
        seg_ids = sample_pipes["segment_id"].tolist()[:3]
        result = engine.run_deferral_scenario(years=3, segments_to_defer=seg_ids)
        if len(result) > 0:
            assert set(result["segment_id"].unique()).issubset(set(seg_ids))


# ─── COVERAGE ANALYSIS ──────────────────────────────────────────────────────

class TestCoverageAnalysis:
    def test_coverage_returns_dataframe(self, engine):
        result = engine.run_coverage_analysis()
        assert isinstance(result, pd.DataFrame)

    def test_coverage_has_columns(self, engine):
        result = engine.run_coverage_analysis()
        expected = ["budget_usd", "segments_funded", "pipe_feet_treated"]
        for col in expected:
            assert col in result.columns

    def test_coverage_increases_with_budget(self, engine):
        result = engine.run_coverage_analysis(budget_levels=[1_000_000, 5_000_000, 20_000_000])
        feet = result["pipe_feet_treated"].values
        assert all(feet[i] <= feet[i + 1] for i in range(len(feet) - 1))

    def test_custom_budget_levels(self, engine):
        levels = [2_000_000, 4_000_000]
        result = engine.run_coverage_analysis(budget_levels=levels)
        assert len(result) == len(levels)


# ─── SCENARIO LOG ────────────────────────────────────────────────────────────

class TestScenarioLog:
    def test_log_initially_empty(self, engine):
        log = engine.get_scenario_log()
        assert len(log) == 0

    def test_log_records_budget_scenarios(self, engine):
        engine.run_budget_scenario(5_000_000)
        engine.run_budget_scenario(10_000_000)
        log = engine.get_scenario_log()
        assert len(log) == 2

    def test_cost_assumption_summary(self, engine):
        summary = engine.get_cost_assumption_summary()
        assert "AWWA" in summary
        assert "LF" in summary
