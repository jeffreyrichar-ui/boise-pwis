"""
PWIS Prioritization Model
=========================
Computes a composite infrastructure priority score for each road segment.

Design Philosophy:
  - Explainable over complex: every score component is visible and auditable
  - Adjustable weights: operators can tune without changing code
  - Documented tradeoffs: comments explain every major decision
  - Honest uncertainty: confidence scores flag data quality gaps

Priority Score Formula:
  P = (condition_severity * w1)
    + (traffic_impact * w2)
    + (complaint_pressure * w3)
    + (cost_efficiency * w4)
    + (equity_modifier * w5)

  Range: 0-100 (higher = higher priority for intervention)

Scoring is relative within a given dataset run.  Two separate runs with
different segment populations may assign the same raw CI a slightly different
score — this is expected and documented behavior.  Comparisons between runs
should use condition_index and tier labels, not raw priority_score values.
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
#   APWA-2023  = American Public Works Association 2023 Infrastructure Report
#   PASER-2022 = PASER Road Rating Manual, Wisconsin Transportation Centre 2022
#   FHWA-2021  = FHWA Pavement Preservation Compendium, Vol. II, 2021
#   PWIS-ENG   = PWIS engineering judgment (Boise-specific, to be validated
#                against actuals in Year 1 of live operation)
#   SYNTHETIC  = Applied to synthetic demo data only; replace with empirical
#                values before live deployment

MODEL_ASSUMPTIONS = {
    "road_type_multipliers": {
        "values": {"Arterial": 1.30, "Highway": 1.45, "Collector": 1.00, "Local": 0.70},
        "source": "FHWA-2021, Table 3-7: functional class economic impact factors",
        "rationale": (
            "Failure of arterial/highway segments disrupts freight movement, "
            "emergency response, and transit — economic impact scales non-linearly "
            "with traffic volume and connectivity.  Local streets are weighted lower "
            "because redundant routes exist in most residential grids."
        ),
        "limitation": (
            "Multipliers do not adjust for network criticality (bridge or sole-access "
            "segments).  A future version should flag sole-access corridors explicitly."
        ),
        "calibration_needed": False,
    },
    "max_aadt_normalization": {
        "value": 50_000,
        "source": "PWIS-ENG; consistent with FHWA urban principal arterial typical maximums",
        "rationale": (
            "Caps normalization to prevent a single ultra-high-volume segment from "
            "compressing all other traffic scores toward zero.  50,000 AADT represents "
            "a heavily-traveled urban arterial; highways above this threshold are still "
            "scored at 100 (maximum), not penalized."
        ),
        "limitation": "May need upward revision if I-84 ramp segments are included.",
        "calibration_needed": True,
    },
    "condition_exponential_threshold": {
        "value": 40,
        "source": "PASER-2022, Section 4.3; FHWA-2021 pavement distress cost curves",
        "rationale": (
            "Below CI=40 (PASER 4), pavement distress transitions from surface defects "
            "to structural failure.  Repair cost curves published by APWA show a "
            "3-5x cost inflection at this point.  The exponential boost ensures the "
            "model reflects this non-linearity rather than ranking a CI=39 road the "
            "same distance from a CI=41 road as two healthy roads 2 points apart."
        ),
        "limitation": (
            "The exponent (1.5) is an engineering judgment estimate.  "
            "Empirical calibration against Boise's historical repair cost data "
            "is recommended in Year 1."
        ),
        "calibration_needed": True,
    },
    "priority_tier_bins": {
        "values": {"Low": [0, 30], "Medium": [30, 55], "High": [55, 75], "Critical": [75, 100]},
        "source": "PWIS-ENG; adapted from PASER 1-10 tier framework",
        "rationale": (
            "Tier boundaries are set so that 'Critical' captures roughly the top 5-10% "
            "of segments — a workload that a typical mid-size city maintenance division "
            "can respond to within a single fiscal quarter.  'High' encompasses segments "
            "that should be addressed within the current CIP cycle."
        ),
        "limitation": (
            "Boundaries are population-relative.  In a dataset where all roads are in "
            "poor condition, 'Low' still appears as a tier — operators must read "
            "condition_index alongside tier labels."
        ),
        "calibration_needed": True,
    },
    "equity_modifier_weight": {
        "value": 0.08,
        "source": "PWIS-ENG; consistent with HUD/FHWA Title VI compliance frameworks",
        "rationale": (
            "An 8% equity weight is large enough to meaningfully shift borderline "
            "segments in historically under-maintained districts while being small "
            "enough to survive Council scrutiny.  The modifier corrects for "
            "structural underinvestment, not individual segment condition — it is "
            "applied at the district level, not the individual resident level."
        ),
        "limitation": (
            "Uses condition_index as a proxy for historical underinvestment.  "
            "A more rigorous implementation would use actual historical spending data "
            "by district (available in budget_actuals.csv) for calibration."
        ),
        "calibration_needed": True,
    },
    "score_confidence_staleness_threshold_days": {
        "value": 730,
        "source": "PWIS-ENG; PASER recommends annual re-inspection for roads below CI=60",
        "rationale": (
            "Inspection data older than 2 years is materially unreliable: "
            "a CI=55 reading from 2022 may represent a CI=40 road today given "
            "typical deterioration rates.  The staleness penalty signals to "
            "operators that a field re-inspection should precede any major spend decision."
        ),
        "limitation": "Threshold is uniform across road types; arterials should ideally be re-inspected annually.",
        "calibration_needed": False,
    },
}


# ─── DEFAULT WEIGHTS ──────────────────────────────────────────────────────────
# These weights represent the BASELINE policy position:
#   - Condition is the dominant driver (most defensible for federal reporting)
#   - Traffic impact reflects economic cost of road failure on commerce
#   - Complaints capture political/equity pressure
#   - Cost efficiency rewards "cheap wins" — high impact / low cost
#   - Equity modifier prevents wealthy/vocal districts from monopolizing fixes
#
# TRADEOFF DOCUMENTED: We weight condition heavily because it's the most
# objective, auditable measure.  A complaint-first weighting would be faster
# to demonstrate value to citizens but easier to game by district managers.

DEFAULT_WEIGHTS = {
    "condition_severity": 0.35,   # Infrastructure condition (1-100 scale inverted)
    "traffic_impact":     0.25,   # Daily traffic volume normalized
    "complaint_pressure": 0.20,   # Citizen complaint volume + severity
    "cost_efficiency":    0.12,   # Cost per traffic-mile served
    "equity_modifier":    0.08,   # District equity correction
}

# ─── THRESHOLDS ───────────────────────────────────────────────────────────────
# See MODEL_ASSUMPTIONS for sourcing and rationale on each value.
CRITICAL_CONDITION_THRESHOLD = 25   # Below this: structural failure, emergency response required
HIGH_CONDITION_THRESHOLD     = 40   # Below this: rehabilitation candidate
MAX_AADT_NORMALIZATION       = MODEL_ASSUMPTIONS["max_aadt_normalization"]["value"]
CONDITION_EXP_THRESHOLD      = MODEL_ASSUMPTIONS["condition_exponential_threshold"]["value"]
STALENESS_THRESHOLD_DAYS     = MODEL_ASSUMPTIONS["score_confidence_staleness_threshold_days"]["value"]

# ─── ROAD TYPE TRAFFIC MULTIPLIERS ────────────────────────────────────────────
# Source: FHWA-2021, Table 3-7. See MODEL_ASSUMPTIONS for full rationale.
ROAD_TYPE_MULTIPLIER = MODEL_ASSUMPTIONS["road_type_multipliers"]["values"]

# ─── ACTION CODES ─────────────────────────────────────────────────────────────
# Short codes used internally; mapped to display labels in _recommend_action().
# Keeping codes separate from display strings prevents brittle string-matching
# in downstream code (e.g., scenario_engine.py).
ACTION_EMERGENCY   = "EMERGENCY"
ACTION_REHAB       = "REHAB"
ACTION_PREVENTIVE  = "PREVENTIVE"
ACTION_CRACK_SEAL  = "CRACK_SEAL"
ACTION_MONITOR_12M = "MONITOR_12M"
ACTION_NO_ACTION   = "NO_ACTION"

ACTION_DISPLAY_LABELS = {
    ACTION_EMERGENCY:   "Emergency Repair — Schedule Within 2 Weeks",
    ACTION_REHAB:       "Full Rehabilitation — Current CIP Cycle",
    ACTION_PREVENTIVE:  "Preventive Treatment — Schedule This Quarter",
    ACTION_CRACK_SEAL:  "Crack Seal + Seal Coat — Next Maintenance Window",
    ACTION_MONITOR_12M: "Routine Monitoring — Inspect in 12 Months",
    ACTION_NO_ACTION:   "No Action Required — Monitor Annually",
}

# Estimated cost range and urgency framing per action code.
# Ranges sourced from APWA 2023 unit cost benchmarks, adjusted for Boise metro.
# Use these for Council presentations; confirm against actual bid history.
ACTION_COST_GUIDANCE = {
    ACTION_EMERGENCY:   {"cost_range": "$150K–$350K/mile", "urgency": "Within 2 weeks — safety critical"},
    ACTION_REHAB:       {"cost_range": "$80K–$175K/mile",  "urgency": "This fiscal year — structural failure imminent"},
    ACTION_PREVENTIVE:  {"cost_range": "$30K–$65K/mile",   "urgency": "This quarter — prevents rehabilitation need"},
    ACTION_CRACK_SEAL:  {"cost_range": "$10K–$22K/mile",   "urgency": "Next maintenance window — cost-effective preservation"},
    ACTION_MONITOR_12M: {"cost_range": "$500–$1,200/mile", "urgency": "Annual inspection — no immediate spend required"},
    ACTION_NO_ACTION:   {"cost_range": "$200–$500/mile",   "urgency": "Routine monitoring — road in acceptable condition"},
}


class PWISPrioritizationModel:
    """
    Computes PWIS infrastructure priority scores.

    Scores are relative within a given dataset run — a segment's score reflects
    its priority relative to other segments in the input data, not an absolute
    condition grade.  Use condition_index and priority_tier for cross-run
    comparisons; use priority_score for within-run ranking only.

    Usage:
        model = PWISPrioritizationModel(weights=DEFAULT_WEIGHTS)
        results = model.score(roads_df, complaints_df, work_orders_df)

    Accessing model assumptions:
        from models.prioritization import MODEL_ASSUMPTIONS
        print(MODEL_ASSUMPTIONS["road_type_multipliers"])
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

        Operators should investigate flagged segments before making large
        capital decisions based on their scores.
        """
        issues = []

        # Zero AADT on a high-capacity road type is almost certainly a data entry gap,
        # not a genuinely empty road.
        zero_aadt_arterials = df[
            (df["road_type"].isin(["Arterial", "Highway"])) &
            (df["daily_traffic_aadt"].fillna(0) == 0)
        ]
        if len(zero_aadt_arterials) > 0:
            ids = zero_aadt_arterials["segment_id"].tolist()[:5]
            issues.append(
                f"{len(zero_aadt_arterials)} Arterial/Highway segment(s) have AADT=0 "
                f"(first 5: {ids}). Traffic scores will be suppressed. "
                "Verify AADT data before finalizing prioritization."
            )

        # A CI > 90 on a road older than 30 years is physically implausible without
        # a recent major rehabilitation — flag for field verification.
        if "asset_age_years" in df.columns:
            implausible_condition = df[
                (df["asset_age_years"] > 30) &
                (df["condition_index"] > 90)
            ]
            if len(implausible_condition) > 0:
                ids = implausible_condition["segment_id"].tolist()[:3]
                issues.append(
                    f"{len(implausible_condition)} segment(s) report CI > 90 with asset age > 30 years "
                    f"(first 3: {ids}). Verify inspection data or confirm recent rehabilitation."
                )

        # Negative or extremely large repair costs suggest a data entry error.
        if "estimated_repair_cost_usd" in df.columns:
            extreme_costs = df[
                (df["estimated_repair_cost_usd"] < 0) |
                (df["estimated_repair_cost_usd"] > 50_000_000)
            ]
            if len(extreme_costs) > 0:
                ids = extreme_costs["segment_id"].tolist()[:3]
                issues.append(
                    f"{len(extreme_costs)} segment(s) have repair costs outside the expected range "
                    f"($0 – $50M) (first 3: {ids}). Cost efficiency scores may be unreliable."
                )

        # Segments with no district assignment will be excluded from equity calculation.
        missing_district = df["district"].isna().sum()
        if missing_district > 0:
            issues.append(
                f"{missing_district} segment(s) have no district assignment. "
                "Equity modifier will be set to 0 for these segments."
            )

        for issue in issues:
            warnings.warn(f"[PWIS Data Quality] {issue}", UserWarning, stacklevel=3)

    # ─── COMPONENT SCORERS ────────────────────────────────────────────────────

    def _score_condition_severity(self, df: pd.DataFrame) -> pd.Series:
        """
        Converts condition_index (1-100, higher=better) to severity score (0-100).

        Two-part formula:
          1. Linear inversion: 100 - CI (simple, auditable baseline)
          2. Exponential amplification below CI=40 (see MODEL_ASSUMPTIONS for source)

        The exponential term ensures that a segment at CI=20 scores materially
        higher than a linear model would predict.  This reflects the documented
        cost inflection at the PASER structural failure threshold: emergency
        repair costs 3-5x preventive maintenance costs.

        Normalization: percentile-robust (99th percentile cap) rather than
        raw maximum, so a single extreme outlier cannot compress all other
        scores toward zero.

        Design tradeoff documented: A linear inversion alone works well for
        a dataset where all roads are in moderate decline.  The exponential
        term is critical for a dataset with a mix of healthy and failing roads,
        which is the realistic condition for most city networks.
        """
        ci = df["condition_index"].clip(1, 100)
        linear = 100 - ci

        # Exponential amplification for structurally failing segments.
        # Formula: (threshold - CI)^1.5 / threshold
        # At CI=0: boost = 40^1.5 / 40 = 40^0.5 = 6.3 (additive to linear score)
        # At CI=39: boost = 1^1.5 / 40 = 0.025 (negligible)
        exp_boost = np.where(
            ci < CONDITION_EXP_THRESHOLD,
            (CONDITION_EXP_THRESHOLD - ci) ** 1.5 / CONDITION_EXP_THRESHOLD,
            0
        )
        raw = linear + exp_boost

        # Percentile-robust normalization: prevents a single extremely degraded
        # segment from compressing all healthy roads toward zero.
        p99 = raw.quantile(0.99)
        p01 = raw.quantile(0.01)
        denom = max(p99 - p01, 1.0)
        normalized = ((raw - p01) / denom * 100).clip(0, 100)
        return normalized

    def _score_traffic_impact(self, df: pd.DataFrame) -> pd.Series:
        """
        Normalizes AADT to 0-100 and applies road type multiplier.

        High-traffic arterials and highways receive a multiplier > 1.0
        because their failure has disproportionate network-wide economic impact:
        freight delay, emergency response disruption, and transit service gaps
        compound beyond the direct repair cost.

        Cap at MAX_AADT_NORMALIZATION (50,000): volumes above this threshold
        are treated equally — the model is not designed to differentiate
        between a 50,000 and 60,000 AADT highway segment.

        TRADEOFF: Could use VMT (volume x lane-miles) but AADT is more
        universally available in city asset management systems and easier to
        explain in a Council meeting.
        """
        aadt = df["daily_traffic_aadt"].clip(0, MAX_AADT_NORMALIZATION)
        normalized = aadt / MAX_AADT_NORMALIZATION * 100
        multiplier = df["road_type"].map(ROAD_TYPE_MULTIPLIER).fillna(1.0)
        return (normalized * multiplier).clip(0, 100)

    def _score_complaint_pressure(
        self, roads_df: pd.DataFrame, complaints_df: pd.DataFrame
    ) -> pd.Series:
        """
        Aggregates complaint volume and severity by segment.

        Severity weighting: Critical=4, High=3, Medium=2, Low=1
        These weights are ordinal proxies for citizen distress intensity.
        A Critical complaint indicates an immediate safety concern reported
        by the resident; a Low complaint indicates a cosmetic issue.

        EQUITY NOTE: We use complaint DENSITY (weighted complaints per lane-mile)
        rather than raw count.  Without density normalization, a 2-mile arterial
        in a dense district would naturally accumulate more complaints than a
        0.2-mile local street — not because it's proportionally worse, but
        because more people drive past it.  Density normalization removes this
        geographic bias.

        Outlier cap at 99th percentile: prevents a single segment with an
        unusually high complaint cluster from suppressing all other scores.
        """
        severity_map = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
        complaints_df = complaints_df.copy()
        complaints_df["severity_weight"] = (
            complaints_df["severity_reported"].map(severity_map).fillna(1)
        )

        agg = (
            complaints_df.groupby("segment_id")
            .agg(
                raw_complaint_count=("complaint_id", "count"),
                weighted_complaints=("severity_weight", "sum"),
            )
            .reset_index()
        )

        roads_df = roads_df.merge(agg, on="segment_id", how="left")
        roads_df["raw_complaint_count"]  = roads_df["raw_complaint_count"].fillna(0)
        roads_df["weighted_complaints"]  = roads_df["weighted_complaints"].fillna(0)

        # Normalize per lane-mile for equity
        roads_df["complaint_density"] = (
            roads_df["weighted_complaints"] / roads_df["length_miles"].clip(0.1)
        )

        # 99th percentile cap to handle outlier complaint clusters.
        # Segments above the cap still receive the maximum score (100);
        # they are not penalized.
        max_density = roads_df["complaint_density"].quantile(0.99)
        score = (roads_df["complaint_density"] / max(max_density, 1) * 100).clip(0, 100)

        # Store for explainability output
        self._complaint_data = roads_df[
            ["segment_id", "raw_complaint_count", "weighted_complaints"]
        ].copy()
        return score

    def _score_cost_efficiency(self, df: pd.DataFrame) -> pd.Series:
        """
        Rewards segments where the investment has high traffic return.
        Metric: 1 / (cost per daily vehicle served)

        A $50K repair on a 20,000-AADT arterial is more efficient than a
        $30K repair on a 500-AADT local street because more users benefit
        per dollar spent.  This component provides a counterbalance to pure
        condition severity — it prevents the model from always recommending
        expensive emergency repairs on low-traffic streets above cost-effective
        preventive maintenance on busy corridors.

        Normalization: 99th percentile cap (same rationale as complaint_pressure).
        """
        cost   = df["estimated_repair_cost_usd"].clip(1_000, 10_000_000)
        aadt   = df["daily_traffic_aadt"].clip(100, MAX_AADT_NORMALIZATION)
        length = df["length_miles"].clip(0.1)

        # Cost per 1M vehicle-miles served (lower = better investment)
        cost_per_vmt = cost / (aadt * length)

        # Invert: low cost_per_vmt gets a high efficiency score
        efficiency = 1 / cost_per_vmt
        p99 = efficiency.quantile(0.99)
        score = (efficiency / max(p99, 1e-9) * 100).clip(0, 100)
        return score

    def _score_equity_modifier(self, df: pd.DataFrame) -> pd.Series:
        """
        Applies a small equity boost to segments in historically
        under-maintained districts.

        Calculated as: districts with average condition_index below the
        citywide median receive a positive modifier.  Districts at or above
        the median receive zero modifier (no penalty for being well-maintained).

        This modifier is intentionally small (default 8% weight) to be
        defensible in a public setting.  It corrects systematic underinvestment —
        not individual preferences.  The modifier is documented and disclosed
        to all dashboard users.

        LIMITATION: Uses current condition_index as a proxy for historical
        underinvestment.  A more rigorous implementation would incorporate
        per-district historical spending from budget_actuals.csv.  This
        enhancement is recommended for Year 2 of live operation.

        See MODEL_ASSUMPTIONS["equity_modifier_weight"] for policy rationale.
        """
        citywide_median = df["condition_index"].median()
        district_avg    = df.groupby("district")["condition_index"].transform("mean")

        # Only below-median districts receive a boost; no district is penalized.
        equity_gap = (citywide_median - district_avg).clip(0)
        denom = max(equity_gap.max(), 1.0)
        score = (equity_gap / denom * 100).clip(0, 100)
        return score

    # ─── STALENESS PENALTY ────────────────────────────────────────────────────

    def _compute_score_confidence(self, df: pd.DataFrame) -> pd.Series:
        """
        Returns a confidence score (0.0 – 1.0) for each segment's priority score.

        Two factors reduce confidence:
          1. Missing required fields (condition_index, daily_traffic_aadt,
             estimated_repair_cost_usd) — each missing field reduces confidence
             by 1/3.
          2. Inspection data staleness — if last_inspection_date is more than
             STALENESS_THRESHOLD_DAYS (730) days old, confidence is reduced
             by 0.20.  A stale CI reading may not reflect current road condition.

        Operators should treat scores with confidence < 0.7 as indicative
        only and prioritize field re-inspection before committing capital.
        """
        required_fields = [
            "condition_index",
            "daily_traffic_aadt",
            "estimated_repair_cost_usd",
        ]
        field_confidence = (
            df[required_fields].notna().sum(axis=1) / len(required_fields)
        )

        # Staleness penalty
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
                # Non-critical: if date parsing fails, skip staleness penalty
                pass

        confidence = (field_confidence - staleness_penalty).clip(0.0, 1.0)
        return confidence.round(2)

    # ─── RECOMMENDATION ENGINE ────────────────────────────────────────────────

    def _recommend_action_code(self, row) -> str:
        """
        Returns an action code (not a display label) based on condition_index
        and priority_tier.  Keeping codes as symbolic constants prevents
        downstream code from doing string comparison against full sentences.

        Decision logic (in priority order):
          1. CI < 25: Structural failure — emergency response required regardless
             of tier.  No other factor overrides a failing road.
          2. CI < 40: Sub-threshold structural — rehabilitation in current
             capital cycle.  Deferral significantly increases cost (see
             scenario_engine deferral analysis).
          3. CI < 55 AND tier is High/Critical: Preventive treatment window —
             acting now avoids rehabilitation cost within 2-3 years.
          4. CI < 65: Crack seal / seal coat is cost-effective preservation.
          5. CI < 80: Routine monitoring; no immediate spend.
          6. Otherwise: No action; annual check.
        """
        ci   = row.get("condition_index", 50)
        tier = str(row.get("priority_tier", "Low"))

        if ci < 25:
            return ACTION_EMERGENCY
        elif ci < 40:
            return ACTION_REHAB
        elif ci < 55 and tier in ("High", "Critical"):
            return ACTION_PREVENTIVE
        elif ci < 65:
            return ACTION_CRACK_SEAL
        elif ci < 80:
            return ACTION_MONITOR_12M
        else:
            return ACTION_NO_ACTION

    def _recommend_action(self, row) -> str:
        """
        Returns the full display label for a segment's recommended action.
        For cost guidance and urgency framing, use ACTION_COST_GUIDANCE[code].
        """
        code = self._recommend_action_code(row)
        return ACTION_DISPLAY_LABELS[code]

    def _recommend_action_detail(self, row) -> dict:
        """
        Returns a structured dict with action, display label, cost range,
        and urgency window.  Used by the Streamlit dashboard for expanded
        segment detail views.

        Example output:
          {
            "action_code":   "REHAB",
            "action_label":  "Full Rehabilitation — Current CIP Cycle",
            "cost_range":    "$80K-$175K/mile",
            "urgency":       "This fiscal year — structural failure imminent",
          }
        """
        code = self._recommend_action_code(row)
        return {
            "action_code":  code,
            "action_label": ACTION_DISPLAY_LABELS[code],
            **ACTION_COST_GUIDANCE[code],
        }

    # ─── MAIN SCORER ──────────────────────────────────────────────────────────

    def score(
        self,
        roads_df: pd.DataFrame,
        complaints_df: pd.DataFrame,
        work_orders_df: pd.DataFrame = None,
    ) -> pd.DataFrame:
        """
        Computes composite priority scores for all road segments.

        Parameters:
            roads_df:       Road segment data (must include condition_index,
                            daily_traffic_aadt, estimated_repair_cost_usd,
                            length_miles, district, road_type)
            complaints_df:  Citizen complaints linked to segment_id
            work_orders_df: Maintenance work orders (reserved for future use;
                            currently not consumed by the scoring model)

        Returns:
            DataFrame with all input columns plus:
              - score_condition      (0-100, component score)
              - score_traffic        (0-100, component score)
              - score_complaints     (0-100, component score)
              - score_cost_eff       (0-100, component score)
              - score_equity         (0-100, component score)
              - priority_score       (0-100, weighted composite)
              - priority_tier        (Critical / High / Medium / Low)
              - score_confidence     (0.0-1.0, data completeness + staleness)
              - district_rank        (rank within district, 1 = highest priority)
              - recommended_action   (display label string)
              - action_code          (symbolic code for downstream logic)
              - raw_complaint_count  (for UI display)
              - weighted_complaints  (for UI display)

        Notes:
            Scores are relative — they reflect priority within this dataset.
            A segment's priority_score will shift if the input population
            changes significantly.  Use condition_index for cross-dataset
            comparisons.
        """
        df = roads_df.copy()

        # ── Pre-flight validation (warnings, not errors) ──
        self._validate_inputs(df)

        # ── Component scores ──
        df["score_condition"]  = self._score_condition_severity(df)
        df["score_traffic"]    = self._score_traffic_impact(df)
        df["score_complaints"] = self._score_complaint_pressure(df, complaints_df)
        df["score_cost_eff"]   = self._score_cost_efficiency(df)
        df["score_equity"]     = self._score_equity_modifier(df)

        # ── Weighted composite ──
        w = self.weights
        df["priority_score"] = (
            df["score_condition"]    * w["condition_severity"]
            + df["score_traffic"]    * w["traffic_impact"]
            + df["score_complaints"] * w["complaint_pressure"]
            + df["score_cost_eff"]   * w["cost_efficiency"]
            + df["score_equity"]     * w["equity_modifier"]
        ).round(2)

        # ── Priority tiers ──
        # Boundaries: Low [0,30), Medium [30,55), High [55,75), Critical [75,100]
        # See MODEL_ASSUMPTIONS["priority_tier_bins"] for sourcing.
        df["priority_tier"] = pd.cut(
            df["priority_score"],
            bins=[0, 30, 55, 75, 101],
            labels=["Low", "Medium", "High", "Critical"],
            right=False,
        )

        # ── Data quality confidence ──
        # Reflects both field completeness and inspection data freshness.
        # Scores below 0.7 should be treated as indicative only.
        df["score_confidence"] = self._compute_score_confidence(df)

        # ── Attach complaint counts for UI ──
        if hasattr(self, "_complaint_data"):
            df = df.merge(self._complaint_data, on="segment_id", how="left")

        # ── Rank within district ──
        df["district_rank"] = (
            df.groupby("district")["priority_score"]
            .rank(ascending=False, method="dense")
            .astype(int)
        )

        # ── Action recommendation ──
        df["action_code"]        = df.apply(self._recommend_action_code, axis=1)
        df["recommended_action"] = df["action_code"].map(ACTION_DISPLAY_LABELS)

        return df.sort_values("priority_score", ascending=False).reset_index(drop=True)

    # ─── UTILITIES ────────────────────────────────────────────────────────────

    def get_weight_summary(self) -> dict:
        """Returns current weights with the dominant factor identified."""
        return {
            "weights":          self.weights,
            "total":            sum(self.weights.values()),
            "dominant_factor":  max(self.weights, key=self.weights.get),
        }

    def get_assumption_summary(self) -> str:
        """
        Returns a plain-English summary of model assumptions for briefing docs.
        Suitable for inclusion in Council memos or audit reports.
        """
        lines = ["PWIS Model Assumptions Summary", "=" * 40]
        for key, data in MODEL_ASSUMPTIONS.items():
            source = data.get("source", "unspecified")
            needs_cal = data.get("calibration_needed", False)
            cal_flag = " [NEEDS CALIBRATION AGAINST BOISE DATA]" if needs_cal else ""
            lines.append(f"\n{key}{cal_flag}")
            lines.append(f"  Source: {source}")
            rationale = data.get("rationale", "")
            if rationale:
                # Wrap at ~80 chars for readability
                lines.append(f"  Rationale: {rationale[:120]}...")
        return "\n".join(lines)

    def export_scores(self, scored_df: pd.DataFrame, path: str):
        """Exports scored segments to CSV with all model output columns."""
        cols = [
            "segment_id", "street_name", "district", "road_type",
            "condition_index", "daily_traffic_aadt", "length_miles",
            "score_condition", "score_traffic", "score_complaints",
            "score_cost_eff", "score_equity", "priority_score",
            "priority_tier", "district_rank", "score_confidence",
            "action_code", "recommended_action", "estimated_repair_cost_usd",
        ]
        output_cols = [c for c in cols if c in scored_df.columns]
        scored_df[output_cols].to_csv(path, index=False)
        print(f"Scores exported to {path}")


# ─── CLI RUNNER ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    base = Path(__file__).parent.parent / "data"

    print("Loading data...")
    roads       = pd.read_csv(base / "road_segments.csv")
    complaints  = pd.read_csv(base / "complaints.csv")
    work_orders = pd.read_csv(base / "work_orders.csv")

    print(f"  {len(roads)} road segments")
    print(f"  {len(complaints)} complaints")
    print(f"  {len(work_orders)} work orders")

    model = PWISPrioritizationModel(weights=DEFAULT_WEIGHTS)

    print("\nRunning prioritization model...")
    results = model.score(roads, complaints, work_orders)

    # Save results
    output_path = base / "priority_scores.csv"
    model.export_scores(results, str(output_path))

    # Summary report
    print("\n" + "=" * 60)
    print("PWIS PRIORITIZATION SUMMARY")
    print("=" * 60)
    print(f"\nWeight configuration: {json.dumps(model.weights, indent=2)}")

    print(f"\nPriority Tier Distribution:")
    tier_counts = results["priority_tier"].value_counts()
    for tier in ["Critical", "High", "Medium", "Low"]:
        if tier in tier_counts:
            count = tier_counts[tier]
            pct   = count / len(results) * 100
            print(f"  {tier:10s}: {count:4d} segments ({pct:.1f}%)")

    # Confidence summary
    low_confidence = (results["score_confidence"] < 0.7).sum()
    if low_confidence > 0:
        print(f"\n  WARNING: {low_confidence} segment(s) have score_confidence < 0.7")
        print("  These scores are based on incomplete or stale data.")
        print("  Field re-inspection recommended before capital commitment.")

    print(f"\nTop 10 Priority Segments:")
    top10_cols = [
        "segment_id", "street_name", "district", "road_type",
        "condition_index", "priority_score", "priority_tier",
        "score_confidence", "recommended_action",
    ]
    top10_cols = [c for c in top10_cols if c in results.columns]
    print(results[top10_cols].head(10).to_string(index=False))

    print(f"\nTop Priority Segment — Action Detail:")
    top_seg = results.iloc[0]
    detail = model._recommend_action_detail(top_seg)
    print(f"  Segment:    {top_seg['segment_id']} — {top_seg.get('street_name', '')}")
    print(f"  Action:     {detail['action_label']}")
    print(f"  Cost range: {detail['cost_range']}")
    print(f"  Urgency:    {detail['urgency']}")

    print(f"\nDistrict Priority Summary:")
    district_summary = (
        results.groupby("district")
        .agg(
            avg_priority_score=("priority_score", "mean"),
            avg_condition=("condition_index", "mean"),
            critical_count=("priority_tier", lambda x: (x == "Critical").sum()),
            total_repair_cost=("estimated_repair_cost_usd", "sum"),
            low_confidence_segs=("score_confidence", lambda x: (x < 0.7).sum()),
        )
        .round(1)
        .sort_values("avg_priority_score", ascending=False)
    )
    print(district_summary.to_string())

    print(f"\n✓ Model complete. Results at: {output_path}")
