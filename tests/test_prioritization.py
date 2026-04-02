"""
tests/test_prioritization.py
=============================
Unit tests for the PWIS prioritization model.

Test philosophy:
  - Test contracts, not implementation details
  - Verify mathematical properties (score ranges, weight invariants)
  - Verify behavioral correctness (worse condition → higher score)
  - Verify edge cases (missing data, single-segment datasets, all-same condition)
  - Tests should be readable as specification documents
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from models.prioritization import (
    DEFAULT_WEIGHTS,
    PWISPrioritizationModel,
)

# ─── FIXTURES ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def minimal_roads():
    """Minimal road segment DataFrame for fast unit tests."""
    return pd.DataFrame(
        {
            "segment_id": ["SEG-0001", "SEG-0002", "SEG-0003", "SEG-0004"],
            "street_name": ["Main St", "Oak Ave", "Elm Rd", "Park Blvd"],
            "district": ["Downtown", "North End", "Southeast", "Downtown"],
            "road_type": ["Arterial", "Local", "Collector", "Highway"],
            "surface_type": ["Asphalt", "Asphalt", "Concrete", "Asphalt"],
            "condition_index": [20, 80, 50, 40],
            "paser_rating": [2, 8, 5, 4],
            "install_year": [1995, 2010, 2000, 1988],
            "asset_age_years": [31, 16, 26, 38],
            "length_miles": [0.5, 0.3, 1.2, 0.8],
            "lane_width_ft": [12, 10, 11, 12],
            "num_lanes": [4, 2, 2, 6],
            "daily_traffic_aadt": [25000, 500, 8000, 40000],
            "lat": [43.62, 43.64, 43.60, 43.61],
            "lon": [-116.20, -116.18, -116.22, -116.21],
            "last_inspection_date": ["2025-06-01"] * 4,
            "last_treatment_year": [2018, 2022, 2019, 2015],
            "estimated_repair_cost_usd": [120000, 15000, 60000, 200000],
        }
    )


@pytest.fixture(scope="module")
def minimal_complaints():
    """Small complaint set with known distribution."""
    return pd.DataFrame(
        {
            "complaint_id": [f"CMP-{i:05d}" for i in range(10)],
            "segment_id": [
                "SEG-0001", "SEG-0001", "SEG-0001",   # 3 on worst segment
                "SEG-0002",                             # 1 on good segment
                "SEG-0003", "SEG-0003",                 # 2 on medium segment
                "SEG-0004", "SEG-0004", "SEG-0004", "SEG-0004",  # 4 on highway
            ],
            "district": [
                "Downtown", "Downtown", "Downtown",
                "North End",
                "Southeast", "Southeast",
                "Downtown", "Downtown", "Downtown", "Downtown",
            ],
            "complaint_type": ["Pothole"] * 10,
            "submitted_date": ["2025-01-15"] * 10,
            "resolved_date": [None] * 10,
            "resolution_status": ["Pending"] * 10,
            "severity_reported": [
                "Critical", "High", "Medium",
                "Low",
                "High", "Medium",
                "Critical", "High", "High", "Medium",
            ],
            "channel": ["311 App"] * 10,
            "lat": [43.62] * 10,
            "lon": [-116.20] * 10,
        }
    )


@pytest.fixture(scope="module")
def default_model():
    return PWISPrioritizationModel(DEFAULT_WEIGHTS)


@pytest.fixture(scope="module")
def scored_results(default_model, minimal_roads, minimal_complaints):
    return default_model.score(minimal_roads, minimal_complaints)


# ─── WEIGHT VALIDATION ────────────────────────────────────────────────────────


class TestWeightValidation:
    def test_default_weights_sum_to_one(self):
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Default weights sum to {total}, expected 1.0"

    def test_default_weights_all_positive(self):
        for k, v in DEFAULT_WEIGHTS.items():
            assert v > 0, f"Weight '{k}' must be positive, got {v}"

    def test_default_weights_have_all_five_components(self):
        expected = {
            "condition_severity",
            "traffic_impact",
            "complaint_pressure",
            "cost_efficiency",
            "equity_modifier",
        }
        assert set(DEFAULT_WEIGHTS.keys()) == expected

    def test_invalid_weights_raise_value_error(self):
        bad_weights = {
            "condition_severity": 0.50,
            "traffic_impact": 0.50,
            "complaint_pressure": 0.50,  # total = 1.50
            "cost_efficiency": 0.00,
            "equity_modifier": 0.00,
        }
        with pytest.raises(ValueError, match="sum to 1.0"):
            PWISPrioritizationModel(bad_weights)

    def test_custom_valid_weights_accepted(self):
        """Model should accept any weights that sum to 1.0."""
        custom = {
            "condition_severity": 0.50,
            "traffic_impact": 0.30,
            "complaint_pressure": 0.10,
            "cost_efficiency": 0.05,
            "equity_modifier": 0.05,
        }
        model = PWISPrioritizationModel(custom)
        assert abs(sum(model.weights.values()) - 1.0) < 1e-9


# ─── SCORE RANGE CONTRACTS ────────────────────────────────────────────────────


class TestScoreRanges:
    def test_priority_score_bounded_0_to_100(self, scored_results):
        scores = scored_results["priority_score"]
        assert scores.min() >= 0, f"Min score {scores.min()} is below 0"
        assert scores.max() <= 100, f"Max score {scores.max()} exceeds 100"

    def test_component_scores_all_bounded(self, scored_results):
        for col in [
            "score_condition",
            "score_traffic",
            "score_complaints",
            "score_cost_eff",
            "score_equity",
        ]:
            assert col in scored_results.columns, f"Missing component column: {col}"
            vals = scored_results[col]
            assert vals.min() >= 0, f"{col} has value below 0: {vals.min()}"
            assert vals.max() <= 100, f"{col} has value above 100: {vals.max()}"

    def test_no_null_scores(self, scored_results):
        assert scored_results["priority_score"].notna().all(), "Null priority scores found"

    def test_score_confidence_bounded_0_to_1(self, scored_results):
        conf = scored_results["score_confidence"]
        assert conf.min() >= 0
        assert conf.max() <= 1


# ─── BEHAVIORAL CORRECTNESS ───────────────────────────────────────────────────


class TestBehavioralCorrectness:
    """
    These tests verify the model behaves as intended for the key policy goals.
    A worse condition segment should score higher when all else is equal.
    """

    def test_worse_condition_scores_higher_ceteris_paribus(self):
        """
        Two identical segments differing only in condition_index.
        The worse (lower CI) segment must receive a higher priority score.
        """
        base = {
            "segment_id": ["SEG-GOOD", "SEG-BAD"],
            "street_name": ["Good Rd", "Bad Rd"],
            "district": ["Downtown", "Downtown"],
            "road_type": ["Arterial", "Arterial"],
            "surface_type": ["Asphalt", "Asphalt"],
            "condition_index": [80, 20],  # <─ only difference
            "paser_rating": [8, 2],
            "install_year": [2010, 2010],
            "asset_age_years": [16, 16],
            "length_miles": [1.0, 1.0],
            "lane_width_ft": [12, 12],
            "num_lanes": [4, 4],
            "daily_traffic_aadt": [15000, 15000],
            "lat": [43.62, 43.62],
            "lon": [-116.20, -116.20],
            "last_inspection_date": ["2025-01-01", "2025-01-01"],
            "last_treatment_year": [2020, 2020],
            "estimated_repair_cost_usd": [50000, 50000],
        }
        roads = pd.DataFrame(base)
        complaints = pd.DataFrame(
            columns=["complaint_id", "segment_id", "district", "complaint_type",
                     "submitted_date", "resolved_date", "resolution_status",
                     "severity_reported", "channel", "lat", "lon"]
        )
        model = PWISPrioritizationModel()
        results = model.score(roads, complaints)
        bad_score = results[results["segment_id"] == "SEG-BAD"]["priority_score"].iloc[0]
        good_score = results[results["segment_id"] == "SEG-GOOD"]["priority_score"].iloc[0]
        assert bad_score > good_score, (
            f"Worse condition segment scored {bad_score:.2f} ≤ "
            f"good condition segment {good_score:.2f}"
        )

    def test_higher_traffic_scores_higher_ceteris_paribus(self):
        """High-AADT segment must score higher than low-AADT at same condition."""
        base_row = {
            "street_name": ["High Traffic Rd", "Low Traffic Rd"],
            "district": ["Downtown", "Downtown"],
            "road_type": ["Arterial", "Arterial"],
            "surface_type": ["Asphalt", "Asphalt"],
            "condition_index": [50, 50],
            "paser_rating": [5, 5],
            "install_year": [2005, 2005],
            "asset_age_years": [21, 21],
            "length_miles": [1.0, 1.0],
            "lane_width_ft": [12, 12],
            "num_lanes": [4, 4],
            "daily_traffic_aadt": [40000, 500],  # <─ only difference
            "lat": [43.62, 43.62],
            "lon": [-116.20, -116.20],
            "last_inspection_date": ["2025-01-01", "2025-01-01"],
            "last_treatment_year": [2018, 2018],
            "estimated_repair_cost_usd": [80000, 80000],
        }
        roads = pd.DataFrame(
            {"segment_id": ["SEG-HI", "SEG-LO"], **base_row}
        )
        complaints = pd.DataFrame(
            columns=["complaint_id", "segment_id", "district", "complaint_type",
                     "submitted_date", "resolved_date", "resolution_status",
                     "severity_reported", "channel", "lat", "lon"]
        )
        model = PWISPrioritizationModel()
        results = model.score(roads, complaints)
        hi = results[results["segment_id"] == "SEG-HI"]["priority_score"].iloc[0]
        lo = results[results["segment_id"] == "SEG-LO"]["priority_score"].iloc[0]
        assert hi > lo, f"High-traffic segment scored {hi:.2f} ≤ low-traffic {lo:.2f}"

    def test_critical_segment_gets_emergency_recommendation(self):
        """Any segment with CI < 25 must receive an Emergency Repair recommendation."""
        roads = pd.DataFrame(
            {
                "segment_id": ["SEG-CRIT"],
                "street_name": ["Crisis Ave"],
                "district": ["Downtown"],
                "road_type": ["Arterial"],
                "surface_type": ["Asphalt"],
                "condition_index": [18],  # <─ below 25 threshold
                "paser_rating": [1],
                "install_year": [1985],
                "asset_age_years": [41],
                "length_miles": [0.5],
                "lane_width_ft": [12],
                "num_lanes": [4],
                "daily_traffic_aadt": [12000],
                "lat": [43.62],
                "lon": [-116.20],
                "last_inspection_date": ["2025-01-01"],
                "last_treatment_year": [2010],
                "estimated_repair_cost_usd": [85000],
            }
        )
        complaints = pd.DataFrame(
            columns=["complaint_id", "segment_id", "district", "complaint_type",
                     "submitted_date", "resolved_date", "resolution_status",
                     "severity_reported", "channel", "lat", "lon"]
        )
        model = PWISPrioritizationModel()
        result = model.score(roads, complaints)
        action = result.iloc[0]["recommended_action"]
        assert "Emergency" in action, f"Expected Emergency action, got: {action}"

    def test_priority_tiers_are_monotone(self, scored_results):
        """Segments in Critical tier must all have higher scores than High tier, etc."""
        tier_order = ["Critical", "High", "Medium", "Low"]
        for i in range(len(tier_order) - 1):
            upper_tier = tier_order[i]
            lower_tier = tier_order[i + 1]
            upper_scores = scored_results[
                scored_results["priority_tier"].astype(str) == upper_tier
            ]["priority_score"]
            lower_scores = scored_results[
                scored_results["priority_tier"].astype(str) == lower_tier
            ]["priority_score"]
            if len(upper_scores) > 0 and len(lower_scores) > 0:
                assert upper_scores.min() >= lower_scores.max() - 1e-9, (
                    f"Tier overlap: {upper_tier} min={upper_scores.min():.2f} "
                    f"< {lower_tier} max={lower_scores.max():.2f}"
                )


# ─── OUTPUT SCHEMA ────────────────────────────────────────────────────────────


class TestOutputSchema:
    REQUIRED_COLUMNS = [
        "segment_id",
        "priority_score",
        "priority_tier",
        "score_condition",
        "score_traffic",
        "score_complaints",
        "score_cost_eff",
        "score_equity",
        "score_confidence",
        "district_rank",
        "recommended_action",
    ]

    def test_all_required_columns_present(self, scored_results):
        missing = [c for c in self.REQUIRED_COLUMNS if c not in scored_results.columns]
        assert not missing, f"Missing output columns: {missing}"

    def test_row_count_matches_input(self, minimal_roads, scored_results):
        assert len(scored_results) == len(minimal_roads), (
            f"Output has {len(scored_results)} rows, expected {len(minimal_roads)}"
        )

    def test_output_sorted_descending_by_score(self, scored_results):
        scores = scored_results["priority_score"].values
        assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1)), (
            "Output is not sorted descending by priority_score"
        )

    def test_district_rank_starts_at_one_per_district(self, scored_results):
        for district, group in scored_results.groupby("district"):
            assert group["district_rank"].min() == 1, (
                f"District '{district}' district_rank does not start at 1"
            )


# ─── EDGE CASES ───────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_complaints_does_not_crash(self, minimal_roads):
        empty_complaints = pd.DataFrame(
            columns=["complaint_id", "segment_id", "district", "complaint_type",
                     "submitted_date", "resolved_date", "resolution_status",
                     "severity_reported", "channel", "lat", "lon"]
        )
        model = PWISPrioritizationModel()
        result = model.score(minimal_roads, empty_complaints)
        assert len(result) == len(minimal_roads)
        assert result["score_complaints"].sum() == 0.0

    def test_single_segment_dataset(self):
        single = pd.DataFrame(
            {
                "segment_id": ["SEG-SOLO"],
                "street_name": ["Only St"],
                "district": ["Downtown"],
                "road_type": ["Arterial"],
                "surface_type": ["Asphalt"],
                "condition_index": [45],
                "paser_rating": [4],
                "install_year": [2000],
                "asset_age_years": [26],
                "length_miles": [1.0],
                "lane_width_ft": [12],
                "num_lanes": [4],
                "daily_traffic_aadt": [15000],
                "lat": [43.62],
                "lon": [-116.20],
                "last_inspection_date": ["2025-01-01"],
                "last_treatment_year": [2018],
                "estimated_repair_cost_usd": [80000],
            }
        )
        complaints = pd.DataFrame(
            columns=["complaint_id", "segment_id", "district", "complaint_type",
                     "submitted_date", "resolved_date", "resolution_status",
                     "severity_reported", "channel", "lat", "lon"]
        )
        model = PWISPrioritizationModel()
        result = model.score(single, complaints)
        assert len(result) == 1
        assert 0 <= result.iloc[0]["priority_score"] <= 100

    def test_all_segments_same_condition_all_rank_1(self):
        """When all segments have identical condition, district_rank should all be 1."""
        n = 5
        roads = pd.DataFrame(
            {
                "segment_id": [f"SEG-{i:04d}" for i in range(n)],
                "street_name": [f"Street {i}" for i in range(n)],
                "district": ["Downtown"] * n,
                "road_type": ["Local"] * n,
                "surface_type": ["Asphalt"] * n,
                "condition_index": [60] * n,   # <─ all identical
                "paser_rating": [6] * n,
                "install_year": [2005] * n,
                "asset_age_years": [21] * n,
                "length_miles": [0.5] * n,
                "lane_width_ft": [12] * n,
                "num_lanes": [2] * n,
                "daily_traffic_aadt": [2000] * n,
                "lat": [43.62] * n,
                "lon": [-116.20] * n,
                "last_inspection_date": ["2025-01-01"] * n,
                "last_treatment_year": [2020] * n,
                "estimated_repair_cost_usd": [30000] * n,
            }
        )
        complaints = pd.DataFrame(
            columns=["complaint_id", "segment_id", "district", "complaint_type",
                     "submitted_date", "resolved_date", "resolution_status",
                     "severity_reported", "channel", "lat", "lon"]
        )
        model = PWISPrioritizationModel()
        result = model.score(roads, complaints)
        # All equal scores → dense rank → all should be 1
        assert (result["district_rank"] == 1).all()

    def test_segment_id_preserved_in_output(self, minimal_roads, scored_results):
        input_ids = set(minimal_roads["segment_id"])
        output_ids = set(scored_results["segment_id"])
        assert input_ids == output_ids, (
            f"Segment IDs changed. Added: {output_ids - input_ids}, "
            f"Removed: {input_ids - output_ids}"
        )


# ─── TEST: MODEL ASSUMPTIONS AND NEW FEATURES ─────────────────────────────────


class TestModelAssumptions:
    """
    Verify that MODEL_ASSUMPTIONS is correctly structured, that the
    action code registry is complete, and that new features added in
    the quality-improvement pass work as documented.
    """

    def test_model_assumptions_registry_has_required_keys(self):
        from models.prioritization import MODEL_ASSUMPTIONS
        required = [
            "road_type_multipliers",
            "max_aadt_normalization",
            "condition_exponential_threshold",
            "priority_tier_bins",
            "equity_modifier_weight",
            "score_confidence_staleness_threshold_days",
        ]
        for key in required:
            assert key in MODEL_ASSUMPTIONS, (
                f"MODEL_ASSUMPTIONS missing key '{key}'"
            )

    def test_model_assumptions_each_has_source_field(self):
        from models.prioritization import MODEL_ASSUMPTIONS
        for key, data in MODEL_ASSUMPTIONS.items():
            assert "source" in data, f"Assumption '{key}' missing 'source' field"

    def test_action_code_registry_covers_all_actions(self):
        from models.prioritization import (
            ACTION_DISPLAY_LABELS, ACTION_COST_GUIDANCE,
            ACTION_EMERGENCY, ACTION_REHAB, ACTION_PREVENTIVE,
            ACTION_CRACK_SEAL, ACTION_MONITOR_12M, ACTION_NO_ACTION,
        )
        all_codes = [
            ACTION_EMERGENCY, ACTION_REHAB, ACTION_PREVENTIVE,
            ACTION_CRACK_SEAL, ACTION_MONITOR_12M, ACTION_NO_ACTION,
        ]
        for code in all_codes:
            assert code in ACTION_DISPLAY_LABELS, f"Action code {code!r} not in ACTION_DISPLAY_LABELS"
            assert code in ACTION_COST_GUIDANCE,  f"Action code {code!r} not in ACTION_COST_GUIDANCE"

    def test_action_cost_guidance_has_required_keys(self):
        from models.prioritization import ACTION_COST_GUIDANCE
        for code, guidance in ACTION_COST_GUIDANCE.items():
            assert "cost_range" in guidance, f"{code}: missing 'cost_range'"
            assert "urgency"    in guidance, f"{code}: missing 'urgency'"

    def test_output_includes_action_code_column(self, minimal_roads, minimal_complaints):
        model = PWISPrioritizationModel()
        result = model.score(minimal_roads, minimal_complaints)
        assert "action_code" in result.columns, "action_code column must be present in output"
        from models.prioritization import ACTION_DISPLAY_LABELS
        assert result["action_code"].isin(ACTION_DISPLAY_LABELS.keys()).all(), (
            "All action_code values must be valid action codes"
        )

    def test_recommend_action_detail_returns_all_fields(self, minimal_roads, minimal_complaints):
        model = PWISPrioritizationModel()
        result = model.score(minimal_roads, minimal_complaints)
        row = result.iloc[0]
        detail = model._recommend_action_detail(row)
        assert "action_code"  in detail
        assert "action_label" in detail
        assert "cost_range"   in detail
        assert "urgency"      in detail

    def test_staleness_penalty_reduces_confidence(self):
        """Segments with old inspection dates should have lower confidence."""
        import pandas as pd

        fresh_roads = pd.DataFrame({
            "segment_id":               ["SEG-F001"],
            "district":                 ["Downtown"],
            "road_type":                ["Arterial"],
            "condition_index":          [60],
            "daily_traffic_aadt":       [15000],
            "length_miles":             [0.5],
            "last_inspection_date":     ["2025-12-01"],   # recent
            "estimated_repair_cost_usd":[50000],
        })
        stale_roads = pd.DataFrame({
            "segment_id":               ["SEG-S001"],
            "district":                 ["Downtown"],
            "road_type":                ["Arterial"],
            "condition_index":          [60],
            "daily_traffic_aadt":       [15000],
            "length_miles":             [0.5],
            "last_inspection_date":     ["2019-01-01"],   # >730 days old
            "estimated_repair_cost_usd":[50000],
        })
        empty_complaints = pd.DataFrame(
            columns=["complaint_id", "segment_id", "district", "complaint_type",
                     "submitted_date", "resolved_date", "resolution_status",
                     "severity_reported", "channel", "lat", "lon"]
        )
        model = PWISPrioritizationModel()
        fresh_result = model.score(fresh_roads,  empty_complaints)
        stale_result = model.score(stale_roads,  empty_complaints)

        fresh_conf = fresh_result["score_confidence"].iloc[0]
        stale_conf = stale_result["score_confidence"].iloc[0]

        assert stale_conf < fresh_conf, (
            f"Stale inspection ({stale_conf}) should have lower confidence than "
            f"fresh inspection ({fresh_conf})"
        )

    def test_input_validation_warns_on_zero_aadt_arterial(self):
        """Input validation should emit a UserWarning for Arterial with AADT=0."""
        import warnings
        roads = pd.DataFrame({
            "segment_id":               ["SEG-BAD"],
            "district":                 ["Downtown"],
            "road_type":                ["Arterial"],
            "condition_index":          [50],
            "daily_traffic_aadt":       [0],           # invalid for Arterial
            "length_miles":             [0.5],
            "last_inspection_date":     ["2025-01-01"],
            "estimated_repair_cost_usd":[50000],
        })
        empty_complaints = pd.DataFrame(
            columns=["complaint_id", "segment_id", "district", "complaint_type",
                     "submitted_date", "resolved_date", "resolution_status",
                     "severity_reported", "channel", "lat", "lon"]
        )
        model = PWISPrioritizationModel()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            model.score(roads, empty_complaints)
            pwis_warnings = [x for x in w if "PWIS Data Quality" in str(x.message)]
            assert len(pwis_warnings) > 0, (
                "Expected a PWIS Data Quality UserWarning for Arterial with AADT=0"
            )

    def test_get_assumption_summary_returns_string(self):
        model = PWISPrioritizationModel()
        summary = model.get_assumption_summary()
        assert isinstance(summary, str)
        assert "PWIS Model Assumptions" in summary
        assert "road_type_multipliers"  in summary
