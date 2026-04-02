"""
tests/test_scenario_engine.py
==============================
Unit tests for the PWIS scenario simulation engine.

Tests verify:
  - Budget allocation greedy correctness (never overspends)
  - Weight sensitivity produces valid comparison DataFrames
  - Deferral cost is always >= current cost (cost increases with time)
  - Coverage analysis is monotonically increasing with budget
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from models.scenario_engine import PWISScenarioEngine


# ─── SHARED FIXTURES ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def sample_roads():
    """20-segment test dataset with controlled properties."""
    import numpy as np

    rng = np.random.default_rng(seed=99)
    n = 20
    return pd.DataFrame(
        {
            "segment_id": [f"SEG-{i:04d}" for i in range(n)],
            "street_name": [f"Road {i}" for i in range(n)],
            "district": (["Downtown"] * 7 + ["North End"] * 7 + ["Southeast"] * 6),
            "road_type": (
                ["Arterial"] * 5 + ["Highway"] * 3 + ["Collector"] * 6 + ["Local"] * 6
            ),
            "surface_type": ["Asphalt"] * n,
            "condition_index": rng.integers(15, 90, n).tolist(),
            "paser_rating": rng.integers(1, 10, n).tolist(),
            "install_year": rng.integers(1980, 2020, n).tolist(),
            "asset_age_years": rng.integers(5, 45, n).tolist(),
            "length_miles": rng.uniform(0.2, 2.5, n).round(2).tolist(),
            "lane_width_ft": [12] * n,
            "num_lanes": rng.integers(2, 6, n).tolist(),
            "daily_traffic_aadt": rng.integers(500, 40000, n).tolist(),
            "lat": rng.uniform(43.56, 43.68, n).round(6).tolist(),
            "lon": rng.uniform(-116.32, -116.10, n).round(6).tolist(),
            "last_inspection_date": ["2025-03-01"] * n,
            "last_treatment_year": rng.integers(2010, 2024, n).tolist(),
            "estimated_repair_cost_usd": rng.integers(10_000, 300_000, n).tolist(),
        }
    )


@pytest.fixture(scope="module")
def sample_complaints(sample_roads):
    """30 complaints distributed across test segments."""
    import numpy as np

    rng = np.random.default_rng(seed=42)
    segs = sample_roads["segment_id"].tolist()
    districts = dict(zip(sample_roads["segment_id"], sample_roads["district"]))
    n = 30
    chosen = rng.choice(segs, size=n)
    return pd.DataFrame(
        {
            "complaint_id": [f"CMP-{i:05d}" for i in range(n)],
            "segment_id": chosen,
            "district": [districts[s] for s in chosen],
            "complaint_type": ["Pothole"] * n,
            "submitted_date": ["2025-01-01"] * n,
            "resolved_date": [None] * n,
            "resolution_status": ["Pending"] * n,
            "severity_reported": rng.choice(
                ["Low", "Medium", "High", "Critical"], n
            ).tolist(),
            "channel": ["311 App"] * n,
            "lat": rng.uniform(43.56, 43.68, n).round(6).tolist(),
            "lon": rng.uniform(-116.32, -116.10, n).round(6).tolist(),
        }
    )


@pytest.fixture(scope="module")
def sample_work_orders(sample_roads):
    """Minimal work orders DataFrame (engine doesn't require it but accepts it)."""
    return pd.DataFrame(
        {
            "work_order_id": ["WO-00001"],
            "segment_id": [sample_roads.iloc[0]["segment_id"]],
            "district": [sample_roads.iloc[0]["district"]],
            "work_order_type": ["Pothole Repair"],
            "status": ["Completed"],
            "priority": ["High"],
            "created_date": ["2025-01-10"],
            "completed_date": ["2025-01-15"],
            "crew_assigned": ["Crew-1"],
            "estimated_hours": [8.0],
            "actual_hours": [9.5],
            "estimated_cost_usd": [5000],
            "actual_cost_usd": [5500],
            "source": ["Inspection"],
            "lat": [43.62],
            "lon": [-116.20],
        }
    )


@pytest.fixture(scope="module")
def engine(sample_roads, sample_complaints, sample_work_orders):
    return PWISScenarioEngine(sample_roads, sample_complaints, sample_work_orders)


# ─── BUDGET SCENARIO TESTS ────────────────────────────────────────────────────


class TestBudgetScenario:
    def test_never_overspends_budget(self, engine, sample_roads):
        budget = 500_000
        funded_df, result = engine.run_budget_scenario(budget)
        total_spent = funded_df[funded_df["funded_this_cycle"]]["treatment_cost"].sum()
        assert total_spent <= budget + 1e-2, (
            f"Spent ${total_spent:,.0f} exceeds budget ${budget:,.0f}"
        )

    def test_segments_funded_increases_with_budget(self, engine, sample_roads):
        _, r_small = engine.run_budget_scenario(200_000)
        _, r_large = engine.run_budget_scenario(2_000_000)
        assert r_large.summary_metrics["segments_funded"] >= r_small.summary_metrics["segments_funded"]

    def test_zero_budget_funds_nothing(self, engine):
        _, result = engine.run_budget_scenario(0)
        assert result.summary_metrics["segments_funded"] == 0

    def test_very_large_budget_funds_all_or_most(self, engine, sample_roads):
        """At 100× total network cost, all segments should be fundable."""
        huge_budget = 50_000_000
        _, result = engine.run_budget_scenario(huge_budget)
        # At least 90% of segments should be funded with a huge budget
        pct_funded = result.summary_metrics["segments_funded"] / len(sample_roads)
        assert pct_funded >= 0.9, f"Only {pct_funded:.0%} funded with huge budget"

    def test_result_has_required_summary_metrics(self, engine):
        _, result = engine.run_budget_scenario(1_000_000)
        required = [
            "total_budget",
            "segments_funded",
            "segments_unfunded",
            "budget_utilized",
            "budget_remaining",
            "pct_budget_used",
            "lane_miles_treated",
        ]
        for key in required:
            assert key in result.summary_metrics, (
                f"Missing summary metric: '{key}'"
            )

    def test_funded_plus_unfunded_equals_total(self, engine, sample_roads):
        _, result = engine.run_budget_scenario(1_000_000)
        m = result.summary_metrics
        assert m["segments_funded"] + m["segments_unfunded"] == len(sample_roads)

    def test_scenario_id_is_unique_per_run(self, engine):
        _, r1 = engine.run_budget_scenario(500_000)
        _, r2 = engine.run_budget_scenario(500_000)
        assert r1.scenario_id != r2.scenario_id, "Scenario IDs should be unique per run"


# ─── WEIGHT SENSITIVITY TESTS ─────────────────────────────────────────────────


class TestWeightSensitivity:
    COMPLAINT_FIRST = {
        "condition_severity": 0.20,
        "traffic_impact":     0.20,
        "complaint_pressure": 0.40,
        "cost_efficiency":    0.12,
        "equity_modifier":    0.08,
    }

    def test_returns_comparison_dataframe(self, engine):
        comparison, _ = engine.run_weight_scenario(self.COMPLAINT_FIRST)
        assert isinstance(comparison, pd.DataFrame)
        assert len(comparison) > 0

    def test_comparison_has_rank_shift_column(self, engine):
        comparison, _ = engine.run_weight_scenario(self.COMPLAINT_FIRST)
        assert "rank_shift" in comparison.columns

    def test_top10_stability_between_0_and_1(self, engine):
        _, stats = engine.run_weight_scenario(self.COMPLAINT_FIRST)
        assert 0.0 <= stats["top10_stability"] <= 1.0

    def test_invalid_weights_raise_error(self, engine):
        bad = {
            "condition_severity": 0.50,
            "traffic_impact": 0.50,
            "complaint_pressure": 0.50,
            "cost_efficiency": 0.00,
            "equity_modifier": 0.00,
        }
        with pytest.raises(ValueError):
            engine.run_weight_scenario(bad)

    def test_same_weights_as_baseline_gives_100_stability(self, engine):
        """Baseline weights vs. themselves → top-10 stability should be 1.0."""
        from models.prioritization import DEFAULT_WEIGHTS

        _, stats = engine.run_weight_scenario(DEFAULT_WEIGHTS, label="Baseline-Copy")
        assert stats["top10_stability"] == 1.0, (
            f"Expected 1.0 stability for identical weights, got {stats['top10_stability']}"
        )


# ─── DEFERRAL COST TESTS ──────────────────────────────────────────────────────


class TestDeferralCost:
    def test_projected_cost_never_less_than_current(self, engine):
        deferral_df = engine.run_deferral_scenario(years=5)
        grouped = deferral_df.groupby("segment_id")
        for seg_id, group in grouped:
            current = group[group["year_deferred"] == 0]["current_cost"].iloc[0]
            future = group[group["year_deferred"] == group["year_deferred"].max()]
            max_future = future["projected_cost"].iloc[0]
            assert max_future >= current, (
                f"Segment {seg_id}: deferred cost ({max_future}) < current cost ({current})"
            )

    def test_deferral_df_has_correct_year_range(self, engine):
        years = 5
        deferral_df = engine.run_deferral_scenario(years=years)
        assert deferral_df["year_deferred"].min() == 0
        assert deferral_df["year_deferred"].max() == years

    def test_condition_degrades_over_time(self, engine):
        """Projected condition index should not increase over deferral period."""
        deferral_df = engine.run_deferral_scenario(years=5)
        for seg_id, group in deferral_df.groupby("segment_id"):
            cis = group.sort_values("year_deferred")["projected_ci"].values
            for i in range(len(cis) - 1):
                assert cis[i] >= cis[i + 1] - 1e-9, (
                    f"Segment {seg_id}: CI increased from year {i} ({cis[i]}) "
                    f"to year {i+1} ({cis[i+1]})"
                )

    def test_one_year_deferral_works(self, engine):
        df = engine.run_deferral_scenario(years=1)
        assert df["year_deferred"].max() == 1


# ─── COVERAGE ANALYSIS TESTS ──────────────────────────────────────────────────


class TestCoverageAnalysis:
    def test_lane_miles_monotonically_increases_with_budget(self, engine):
        coverage = engine.run_coverage_analysis(
            budget_levels=[500_000, 1_000_000, 2_000_000, 5_000_000]
        )
        miles = coverage["lane_miles_treated"].values
        for i in range(len(miles) - 1):
            assert miles[i] <= miles[i + 1], (
                f"Lane miles non-monotone at index {i}: {miles[i]} > {miles[i+1]}"
            )

    def test_coverage_returns_dataframe_with_required_columns(self, engine):
        coverage = engine.run_coverage_analysis(budget_levels=[1_000_000])
        required = ["budget_usd", "segments_funded", "lane_miles_treated"]
        for col in required:
            assert col in coverage.columns

    def test_coverage_row_count_matches_budget_levels(self, engine):
        levels = [1_000_000, 2_000_000, 5_000_000]
        coverage = engine.run_coverage_analysis(budget_levels=levels)
        assert len(coverage) == len(levels)
