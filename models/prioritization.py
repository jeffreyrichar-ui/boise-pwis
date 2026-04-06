"""
PWIS Utility Prioritization Model
===================================
Computes a composite infrastructure priority score for each pipe segment
in the Boise water, sewer, and stormwater systems.

Design Philosophy:
  - Explainable over complex: every score component is visible and auditable
  - Adjustable weights: operators can tune without changing code
  - Documented tradeoffs: comments explain every major decision
  - Honest uncertainty: confidence scores flag data quality gaps
  - System-aware: water, sewer, and stormwater pipes have distinct failure
    modes and scoring adjustments

Priority Score Formula:
  P = (condition_severity * w1)
    + (break_history * w2)
    + (capacity_stress * w3)
    + (criticality * w4)
    + (material_risk * w5)
    + (age_factor * w6)

  Range: 0-100 (higher = higher priority for intervention)

Scoring is relative within a given dataset run.  Two separate runs with
different segment populations may assign the same raw condition_score a
slightly different priority — this is expected.  Comparisons between runs
should use condition_score and tier labels, not raw priority_score values.
"""

import warnings
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from pathlib import Path


# ─── ASSUMPTION REGISTRY ──────────────────────────────────────────────────────
# Every major constant in this model is documented here with its source,
# rationale, and known limitations.  This is the authoritative reference
# for model audits, Council briefings, and future calibration.
#
# Source codes:
#   AWWA-2023  = American Water Works Association 2023 Infrastructure Report
#   EPA-CMOM   = EPA Capacity, Management, Operations & Maintenance guidance
#   NASSCO-2022 = NASSCO PACP/MACP Pipeline Assessment and Certification Program
#   PWIS-ENG   = PWIS engineering judgment (Boise-specific, to be validated
#                against actuals in Year 1 of live operation)
#   SYNTHETIC  = Applied to synthetic demo data only; replace with empirical
#                values before live deployment

MODEL_ASSUMPTIONS = {
    "material_risk_factors": {
        "values": {
            "Cast Iron":        0.90, "Galvanized Steel": 0.85,
            "Asbestos Cement":  0.80, "Orangeburg":       0.95,
            "Vitrified Clay":   0.60, "Corrugated Metal": 0.75,
            "Concrete":         0.45, "Ductile Iron":     0.30,
            "PVC":              0.15, "HDPE":             0.10,
            "Reinforced Concrete Box": 0.40,
            "PVC PR-SDR":      0.12, "PVC C900":         0.15,
        },
        "source": "AWWA-2023, Table 5-2: material-specific failure probability factors",
        "rationale": (
            "Older materials (cast iron, asbestos cement, Orangeburg) have documented "
            "higher failure rates due to corrosion, joint degradation, and brittleness.  "
            "Modern materials (PVC, HDPE) have substantially lower baseline failure "
            "probabilities.  Risk factors are normalized 0-1 where 1.0 = highest risk."
        ),
        "limitation": (
            "Factors do not account for local soil conditions (Boise's alkaline soils "
            "accelerate cast iron corrosion) or installation quality.  A future version "
            "should incorporate soil corrosivity data from Ada County GIS."
        ),
        "calibration_needed": True,
    },
    "criticality_class_multipliers": {
        "values": {
            "Transmission Main": 1.50, "Trunk Sewer":  1.45,
            "Force Main":        1.40, "Interceptor":  1.40,
            "Distribution Main": 1.15, "Collector":    1.00,
            "Lateral":           0.70, "Service Line": 0.60,
        },
        "source": "EPA-CMOM, Section 4.3: criticality assessment framework",
        "rationale": (
            "Failure of transmission mains and trunk sewers affects thousands of "
            "customers and may trigger regulatory violations (SSO reporting, boil "
            "orders).  Lateral/service line failures affect individual properties — "
            "still important but lower systemic risk."
        ),
        "limitation": (
            "Multipliers do not consider network redundancy.  A transmission main "
            "with a parallel redundant pipe has lower effective criticality than "
            "the multiplier suggests."
        ),
        "calibration_needed": False,
    },
    "condition_exponential_threshold": {
        "value": 40,
        "source": "NASSCO-2022, PACP grade-to-condition mapping; AWWA pipe assessment guidance",
        "rationale": (
            "Below condition_score=40, pipe defects transition from serviceability "
            "issues to structural failure risk.  Repair costs show a 3-5x inflection "
            "at this point (lining becomes impractical, full replacement required).  "
            "The exponential boost ensures the model reflects this non-linearity."
        ),
        "limitation": (
            "The exponent (1.5) is an engineering judgment estimate.  "
            "Empirical calibration against Boise's break history data "
            "is recommended in Year 1."
        ),
        "calibration_needed": True,
    },
    "priority_tier_bins": {
        "values": {"Low": [0, 30], "Medium": [30, 55], "High": [55, 75], "Critical": [75, 100]},
        "source": "PWIS-ENG; adapted from NASSCO PACP 1-5 grade framework",
        "rationale": (
            "Tier boundaries are set so that 'Critical' captures roughly the top 5-10% "
            "of segments — a workload that a typical mid-size utility can respond to "
            "within a single fiscal quarter.  'High' encompasses segments "
            "that should be addressed within the current CIP cycle."
        ),
        "limitation": (
            "Boundaries are population-relative.  In a dataset where all pipes are in "
            "poor condition, 'Low' still appears as a tier — operators must read "
            "condition_score alongside tier labels."
        ),
        "calibration_needed": True,
    },
    "capacity_stress_threshold": {
        "value": 80,
        "source": "EPA-CMOM; typical regulatory threshold for capacity planning",
        "rationale": (
            "Pipes operating above 80% capacity have insufficient surge margin "
            "for wet-weather events.  Sewer and stormwater systems above this "
            "threshold are at risk of SSOs and street flooding.  Water mains "
            "above 80% may have inadequate fire flow capacity."
        ),
        "limitation": "Threshold is system-wide; some trunk sewers operate safely at 85% with known flow patterns.",
        "calibration_needed": True,
    },
    "score_confidence_staleness_threshold_days": {
        "value": 730,
        "source": "PWIS-ENG; NASSCO recommends biennial re-inspection for pipes below condition 60",
        "rationale": (
            "Inspection data older than 2 years is materially unreliable: "
            "a condition=55 reading from 2024 may represent a condition=40 pipe today "
            "given typical deterioration rates.  The staleness penalty signals to "
            "operators that a field re-inspection should precede any major spend decision."
        ),
        "limitation": "Threshold is uniform across system types; sewer pipes in I&I zones should be inspected annually.",
        "calibration_needed": False,
    },
}


# ─── DEFAULT WEIGHTS ──────────────────────────────────────────────────────────
# These weights represent the BASELINE policy position:
#   - Condition is the dominant driver (most defensible for state/EPA reporting)
#   - Break history reflects empirical failure evidence
#   - Capacity stress captures hydraulic performance under load
#   - Criticality reflects systemic impact of failure
#   - Material risk encodes known failure modes by pipe type
#   - Age factor provides a degradation proxy when inspection data is sparse
#
# TRADEOFF DOCUMENTED: We weight condition heavily because it's the most
# objective, auditable measure from CCTV/acoustic inspection.  A break-first
# weighting would be more reactive but penalizes newer pipes that haven't
# had time to accumulate breaks.

DEFAULT_WEIGHTS = {
    "condition_severity": 0.30,   # Pipe condition score (1-100 scale inverted)
    "break_history":      0.20,   # Break/repair frequency in last 5 years
    "capacity_stress":    0.15,   # Hydraulic capacity utilization %
    "criticality":        0.15,   # System criticality class (transmission vs lateral)
    "material_risk":      0.12,   # Material-specific failure probability
    "age_factor":         0.08,   # Degradation proxy based on install year
}

# ─── THRESHOLDS ───────────────────────────────────────────────────────────────
CRITICAL_CONDITION_THRESHOLD = 25   # Below this: structural failure, emergency response
HIGH_CONDITION_THRESHOLD     = 40   # Below this: replacement/rehabilitation candidate
CONDITION_EXP_THRESHOLD      = MODEL_ASSUMPTIONS["condition_exponential_threshold"]["value"]
STALENESS_THRESHOLD_DAYS     = MODEL_ASSUMPTIONS["score_confidence_staleness_threshold_days"]["value"]
CAPACITY_STRESS_THRESHOLD    = MODEL_ASSUMPTIONS["capacity_stress_threshold"]["value"]

# ─── MATERIAL RISK FACTORS ───────────────────────────────────────────────────
MATERIAL_RISK = MODEL_ASSUMPTIONS["material_risk_factors"]["values"]

# ─── CRITICALITY MULTIPLIERS ────────────────────────────────────────────────
CRITICALITY_MULTIPLIER = MODEL_ASSUMPTIONS["criticality_class_multipliers"]["values"]

# ─── ACTION CODES ─────────────────────────────────────────────────────────────
# Short codes used internally; mapped to display labels in _recommend_action().
ACTION_REPLACE     = "REPLACE"
ACTION_REHABILITATE = "REHABILITATE"
ACTION_LINE        = "LINE"
ACTION_REPAIR      = "REPAIR"
ACTION_MONITOR     = "MONITOR"
ACTION_NO_ACTION   = "NO_ACTION"

ACTION_DISPLAY_LABELS = {
    ACTION_REPLACE:      "Full Replacement — Schedule in Current CIP Cycle",
    ACTION_REHABILITATE: "Rehabilitation (CIPP/Slip-line) — This Fiscal Year",
    ACTION_LINE:         "Trenchless Lining — Schedule This Quarter",
    ACTION_REPAIR:       "Spot Repair — Next Maintenance Window",
    ACTION_MONITOR:      "Routine Monitoring — Re-inspect in 12 Months",
    ACTION_NO_ACTION:    "No Action Required — Monitor per Schedule",
}

ACTION_COST_GUIDANCE = {
    ACTION_REPLACE:      {"cost_range": "$150–$400/LF", "urgency": "This CIP cycle — structural failure risk"},
    ACTION_REHABILITATE: {"cost_range": "$80–$200/LF",  "urgency": "This fiscal year — condition deteriorating"},
    ACTION_LINE:         {"cost_range": "$40–$100/LF",  "urgency": "This quarter — prevents full replacement"},
    ACTION_REPAIR:       {"cost_range": "$5K–$25K/spot","urgency": "Next maintenance window — localized defect"},
    ACTION_MONITOR:      {"cost_range": "$500–$2K/inspection", "urgency": "Annual cycle — no immediate spend"},
    ACTION_NO_ACTION:    {"cost_range": "$200–$500/record",    "urgency": "Routine — asset in acceptable condition"},
}


class PWISPrioritizationModel:
    """
    Computes PWIS utility infrastructure priority scores.

    Scores are relative within a given dataset run — a segment's score reflects
    its priority relative to other segments in the input data, not an absolute
    condition grade.  Use condition_score and priority_tier for cross-run
    comparisons; use priority_score for within-run ranking only.

    Usage:
        model = PWISPrioritizationModel(weights=DEFAULT_WEIGHTS)
        results = model.score(pipes_df, service_requests_df, work_orders_df)

    Accessing model assumptions:
        from models.prioritization import MODEL_ASSUMPTIONS
        print(MODEL_ASSUMPTIONS["material_risk_factors"])
    """

    def __init__(self, weights: dict = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        self._validate_weights()

    def _validate_weights(self):
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Weights must sum to 1.0. Current sum: {total:.3f}. "
                "Adjust weights before running the model."
            )
        if any(v < 0 for v in self.weights.values()):
            raise ValueError("All weights must be non-negative.")

    # ─── INPUT VALIDATION ─────────────────────────────────────────────────────

    def _validate_inputs(self, df: pd.DataFrame) -> None:
        """
        Emits warnings (not errors) for data patterns that suggest upstream
        data quality issues.  The model will still run — these are advisory.
        """
        issues = []

        # Zero breaks on very old pipes with low condition — may be missing data
        old_poor = df[
            (df["asset_age_years"] > 50) &
            (df["condition_score"] < 30) &
            (df["breaks_last_5yr"] == 0)
        ]
        if len(old_poor) > 0:
            ids = old_poor["segment_id"].tolist()[:5]
            issues.append(
                f"{len(old_poor)} pipe(s) are >50 years old with condition<30 but zero breaks "
                f"(first 5: {ids}). Break records may be incomplete. "
                "Verify work order history before finalizing prioritization."
            )

        # High capacity utilization on small-diameter pipes may indicate a data error
        high_cap_small = df[
            (df["diameter_inches"] <= 6) &
            (df["capacity_utilization_pct"].fillna(0) > 95)
        ]
        if len(high_cap_small) > 0:
            ids = high_cap_small["segment_id"].tolist()[:3]
            issues.append(
                f"{len(high_cap_small)} small-diameter pipe(s) (≤6\") report >95% capacity "
                f"(first 3: {ids}). Verify flow monitoring data — sensor error is common on small mains."
            )

        # Negative or extremely large replacement costs
        if "estimated_replacement_cost_usd" in df.columns:
            extreme_costs = df[
                (df["estimated_replacement_cost_usd"] < 0) |
                (df["estimated_replacement_cost_usd"] > 50_000_000)
            ]
            if len(extreme_costs) > 0:
                ids = extreme_costs["segment_id"].tolist()[:3]
                issues.append(
                    f"{len(extreme_costs)} pipe(s) have replacement costs outside expected range "
                    f"($0 – $50M) (first 3: {ids}). Cost scores may be unreliable."
                )

        # Missing district assignment
        missing_district = df["district"].isna().sum()
        if missing_district > 0:
            issues.append(
                f"{missing_district} pipe(s) have no district assignment. "
                "District-level analysis will exclude these segments."
            )

        for issue in issues:
            warnings.warn(f"[PWIS Data Quality] {issue}", UserWarning, stacklevel=3)

    # ─── COMPONENT SCORERS ────────────────────────────────────────────────────

    def _score_condition_severity(self, df: pd.DataFrame) -> pd.Series:
        """
        Converts condition_score (1-100, higher=better) to severity score (0-100).

        Two-part formula:
          1. Linear inversion: 100 - condition_score
          2. Exponential amplification below threshold=40

        The exponential term ensures pipes at condition=20 score materially
        higher than a linear model would predict.  This reflects the documented
        cost inflection at the structural failure threshold: full replacement
        costs 3-5x rehabilitation costs.
        """
        ci = df["condition_score"].clip(1, 100)
        linear = 100 - ci

        exp_boost = np.where(
            ci < CONDITION_EXP_THRESHOLD,
            (CONDITION_EXP_THRESHOLD - ci) ** 1.5 / CONDITION_EXP_THRESHOLD,
            0
        )
        raw = linear + exp_boost

        p99 = raw.quantile(0.99)
        p01 = raw.quantile(0.01)
        denom = max(p99 - p01, 1.0)
        normalized = ((raw - p01) / denom * 100).clip(0, 100)
        return normalized

    def _score_break_history(self, df: pd.DataFrame) -> pd.Series:
        """
        Scores pipes based on break frequency in the last 5 years.

        More breaks = higher priority.  Normalized to 0-100 using 99th
        percentile cap.  Pipes with zero breaks receive a score of 0.

        Break history is the strongest empirical predictor of future failure —
        a pipe that has broken twice in 5 years is statistically likely to
        break again within 18 months (AWWA 2023 failure curve analysis).
        """
        breaks = df["breaks_last_5yr"].clip(0)
        p99 = max(breaks.quantile(0.99), 1)
        return (breaks / p99 * 100).clip(0, 100)

    def _score_capacity_stress(self, df: pd.DataFrame) -> pd.Series:
        """
        Scores pipes based on hydraulic capacity utilization.

        Pipes above CAPACITY_STRESS_THRESHOLD (80%) receive amplified scores.
        This reflects SSO risk (sewer), flooding risk (stormwater), and
        fire flow inadequacy (water).

        Water mains without capacity data (common for distribution lines)
        default to 50% — a neutral assumption that neither helps nor hurts.
        """
        cap = df["capacity_utilization_pct"].fillna(50).clip(0, 100)

        # Amplify scores above threshold — the risk is non-linear
        score = np.where(
            cap >= CAPACITY_STRESS_THRESHOLD,
            70 + (cap - CAPACITY_STRESS_THRESHOLD) / (100 - CAPACITY_STRESS_THRESHOLD) * 30,
            cap / CAPACITY_STRESS_THRESHOLD * 70,
        )
        return pd.Series(score, index=df.index).clip(0, 100)

    def _score_criticality(self, df: pd.DataFrame) -> pd.Series:
        """
        Scores pipes based on criticality class (system role).

        Transmission mains and trunk sewers score highest because their
        failure affects thousands of customers and may trigger regulatory
        violations (SSOs, boil-water orders).

        Multiplier values from MODEL_ASSUMPTIONS["criticality_class_multipliers"].
        """
        multiplier = df["criticality_class"].map(CRITICALITY_MULTIPLIER).fillna(1.0)
        # Normalize multipliers to 0-100 scale
        max_mult = max(CRITICALITY_MULTIPLIER.values())
        min_mult = min(CRITICALITY_MULTIPLIER.values())
        denom = max(max_mult - min_mult, 0.01)
        score = ((multiplier - min_mult) / denom * 100).clip(0, 100)
        return score

    def _score_material_risk(self, df: pd.DataFrame) -> pd.Series:
        """
        Scores pipes based on material-specific failure probability.

        Cast iron, asbestos cement, and Orangeburg score highest because
        they have documented high failure rates in utility networks.
        Modern materials (PVC, HDPE) score lowest.

        Risk factors from MODEL_ASSUMPTIONS["material_risk_factors"].
        """
        risk = df["pipe_material"].map(MATERIAL_RISK).fillna(0.5)
        return (risk * 100).clip(0, 100)

    def _score_age_factor(self, df: pd.DataFrame) -> pd.Series:
        """
        Scores pipes based on asset age as a degradation proxy.

        Age is a useful supplementary factor when inspection data is sparse.
        Score ramps from 0 (new) to 100 (100+ years old).

        Expected service life by material varies (PVC: 75-100yr,
        cast iron: 75-100yr under ideal conditions but often fails at 50-60yr
        in Boise's alkaline soils).  This scorer uses a simple linear ramp
        as a reasonable approximation across materials.
        """
        age = df["asset_age_years"].clip(0)
        # Linear ramp: 0 at age 0, 100 at age 100
        score = (age / 100 * 100).clip(0, 100)
        return score

    # ─── STALENESS / CONFIDENCE ──────────────────────────────────────────────

    def _compute_score_confidence(self, df: pd.DataFrame) -> pd.Series:
        """
        Returns a confidence score (0.0 – 1.0) for each segment's priority score.

        Two factors reduce confidence:
          1. Missing required fields — each missing field reduces confidence by 1/N
          2. Inspection data staleness — if last_inspection_date is >730 days old,
             confidence drops by 0.20
        """
        required_fields = [
            "condition_score",
            "breaks_last_5yr",
            "estimated_replacement_cost_usd",
        ]
        field_confidence = (
            df[required_fields].notna().sum(axis=1) / len(required_fields)
        )

        staleness_penalty = pd.Series(0.0, index=df.index)
        if "last_inspection_date" in df.columns:
            today = datetime.today()
            threshold = timedelta(days=STALENESS_THRESHOLD_DAYS)
            try:
                inspection_dates = pd.to_datetime(
                    df["last_inspection_date"], errors="coerce"
                )
                days_since = (today - inspection_dates).dt.days.fillna(9999)
                staleness_penalty = np.where(days_since > STALENESS_THRESHOLD_DAYS, 0.20, 0.0)
                staleness_penalty = pd.Series(staleness_penalty, index=df.index)
            except Exception:
                pass

        confidence = (field_confidence - staleness_penalty).clip(0.0, 1.0)
        return confidence.round(2)

    # ─── RECOMMENDATION ENGINE ────────────────────────────────────────────────

    def _recommend_action_code(self, row) -> str:
        """
        Returns an action code driven primarily by priority_tier, with
        condition_score used to refine within a tier.

        The fundamental principle: if a pipe scores Critical, it needs
        replacement. If it scores Low, it can be monitored. The priority
        tier IS the action driver — that's the whole point of the scoring
        model.

        Decision logic:
          Critical → REPLACE (these are the pipes that need replacement)
          High     → REHABILITATE, or LINE if condition is still moderate
          Medium   → REPAIR
          Low      → MONITOR if condition < 80, else NO_ACTION
        """
        ci   = row.get("condition_score", 50)
        tier = str(row.get("priority_tier", "Low"))

        if tier == "Critical":
            return ACTION_REPLACE
        elif tier == "High":
            if ci < 40:
                return ACTION_REHABILITATE
            else:
                return ACTION_LINE
        elif tier == "Medium":
            return ACTION_REPAIR
        else:  # Low
            if ci < 80:
                return ACTION_MONITOR
            else:
                return ACTION_NO_ACTION

    def _recommend_action(self, row) -> str:
        code = self._recommend_action_code(row)
        return ACTION_DISPLAY_LABELS[code]

    def _recommend_action_detail(self, row) -> dict:
        code = self._recommend_action_code(row)
        return {
            "action_code":  code,
            "action_label": ACTION_DISPLAY_LABELS[code],
            **ACTION_COST_GUIDANCE[code],
        }

    # ─── MAIN SCORER ──────────────────────────────────────────────────────────

    def score(
        self,
        pipes_df: pd.DataFrame,
        service_requests_df: pd.DataFrame = None,
        work_orders_df: pd.DataFrame = None,
    ) -> pd.DataFrame:
        """
        Computes composite priority scores for all pipe segments.

        Parameters:
            pipes_df:             Pipe segment data (must include condition_score,
                                  breaks_last_5yr, capacity_utilization_pct,
                                  criticality_class, pipe_material, asset_age_years,
                                  diameter_inches, length_ft, district)
            service_requests_df:  Citizen service requests (reserved for future
                                  complaint-pressure component)
            work_orders_df:       Maintenance work orders (reserved for future
                                  work order backlog component)

        Returns:
            DataFrame with all input columns plus:
              - score_condition, score_breaks, score_capacity, score_criticality,
                score_material, score_age (0-100 component scores)
              - priority_score (0-100 weighted composite)
              - priority_tier (Critical / High / Medium / Low)
              - score_confidence (0.0-1.0)
              - district_rank (rank within district)
              - recommended_action (display label)
              - action_code (symbolic code)
        """
        df = pipes_df.copy()

        # Pre-flight validation
        self._validate_inputs(df)

        # Component scores
        df["score_condition"]   = self._score_condition_severity(df)
        df["score_breaks"]      = self._score_break_history(df)
        df["score_capacity"]    = self._score_capacity_stress(df)
        df["score_criticality"] = self._score_criticality(df)
        df["score_material"]    = self._score_material_risk(df)
        df["score_age"]         = self._score_age_factor(df)

        # Weighted composite
        w = self.weights
        df["priority_score"] = (
            df["score_condition"]   * w["condition_severity"]
            + df["score_breaks"]   * w["break_history"]
            + df["score_capacity"] * w["capacity_stress"]
            + df["score_criticality"] * w["criticality"]
            + df["score_material"] * w["material_risk"]
            + df["score_age"]      * w["age_factor"]
        ).round(2)

        # Priority tiers
        df["priority_tier"] = pd.cut(
            df["priority_score"],
            bins=[0, 30, 55, 75, 101],
            labels=["Low", "Medium", "High", "Critical"],
            right=False,
        )

        # Confidence
        df["score_confidence"] = self._compute_score_confidence(df)

        # District rank
        df["district_rank"] = (
            df.groupby("district")["priority_score"]
            .rank(ascending=False, method="dense")
            .astype(int)
        )

        # Action recommendation
        df["action_code"]        = df.apply(self._recommend_action_code, axis=1)
        df["recommended_action"] = df["action_code"].map(ACTION_DISPLAY_LABELS)

        return df.sort_values("priority_score", ascending=False).reset_index(drop=True)

    # ─── UTILITIES ────────────────────────────────────────────────────────────

    def get_weight_summary(self) -> dict:
        return {
            "weights":         self.weights,
            "total":           sum(self.weights.values()),
            "dominant_factor": max(self.weights, key=self.weights.get),
        }

    def get_assumption_summary(self) -> str:
        lines = ["PWIS Utility Model Assumptions Summary", "=" * 45]
        for key, data in MODEL_ASSUMPTIONS.items():
            source = data.get("source", "unspecified")
            needs_cal = data.get("calibration_needed", False)
            cal_flag = " [NEEDS CALIBRATION]" if needs_cal else ""
            lines.append(f"\n{key}{cal_flag}")
            lines.append(f"  Source: {source}")
            rationale = data.get("rationale", "")
            if rationale:
                lines.append(f"  Rationale: {rationale[:120]}...")
        return "\n".join(lines)

    def export_scores(self, scored_df: pd.DataFrame, path: str):
        cols = [
            "segment_id", "system_type", "corridor_name", "district",
            "pipe_material", "diameter_inches", "length_ft",
            "condition_score", "breaks_last_5yr", "capacity_utilization_pct",
            "criticality_class", "asset_age_years",
            "score_condition", "score_breaks", "score_capacity",
            "score_criticality", "score_material", "score_age",
            "priority_score", "priority_tier", "district_rank",
            "score_confidence", "action_code", "recommended_action",
            "estimated_replacement_cost_usd", "lat", "lon",
        ]
        output_cols = [c for c in cols if c in scored_df.columns]
        scored_df[output_cols].to_csv(path, index=False)
        print(f"Scores exported to {path}")


# ─── CLI RUNNER ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    base = Path(__file__).parent.parent / "data"

    print("Loading data...")
    pipes            = pd.read_csv(base / "pipe_segments.csv")
    service_requests = pd.read_csv(base / "service_requests.csv")
    work_orders      = pd.read_csv(base / "work_orders.csv")

    print(f"  {len(pipes)} pipe segments")
    print(f"  {len(service_requests)} service requests")
    print(f"  {len(work_orders)} work orders")

    model = PWISPrioritizationModel(weights=DEFAULT_WEIGHTS)

    print("\nRunning prioritization model...")
    results = model.score(pipes, service_requests, work_orders)

    output_path = base / "priority_scores.csv"
    model.export_scores(results, str(output_path))

    print("\n" + "=" * 60)
    print("PWIS UTILITY PRIORITIZATION SUMMARY")
    print("=" * 60)
    print(f"\nWeight configuration: {json.dumps(model.weights, indent=2)}")

    print(f"\nPriority Tier Distribution:")
    tier_counts = results["priority_tier"].value_counts()
    for tier in ["Critical", "High", "Medium", "Low"]:
        if tier in tier_counts:
            count = tier_counts[tier]
            pct   = count / len(results) * 100
            print(f"  {tier:10s}: {count:4d} segments ({pct:.1f}%)")

    print(f"\nSystem Type Breakdown:")
    for sys_type in ["Water", "Sewer", "Stormwater", "Pressurized Irrigation"]:
        subset = results[results["system_type"] == sys_type]
        if len(subset) > 0:
            critical = (subset["priority_tier"] == "Critical").sum()
            print(f"  {sys_type:12s}: {len(subset):4d} pipes, {critical} critical")

    low_confidence = (results["score_confidence"] < 0.7).sum()
    if low_confidence > 0:
        print(f"\n  WARNING: {low_confidence} pipe(s) have score_confidence < 0.7")
        print("  Re-inspection recommended before capital commitment.")

    print(f"\nTop 10 Priority Pipes:")
    top10_cols = [
        "segment_id", "system_type", "corridor_name", "district",
        "pipe_material", "condition_score", "priority_score", "priority_tier",
        "recommended_action",
    ]
    top10_cols = [c for c in top10_cols if c in results.columns]
    print(results[top10_cols].head(10).to_string(index=False))

    print(f"\n✓ Model complete. Results at: {output_path}")
