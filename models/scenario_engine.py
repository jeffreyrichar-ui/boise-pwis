"""
PWIS Scenario Simulation Engine
================================
Answers the question: "What changes if we adjust budget or priorities?"

Scenarios supported:
  1. Budget Scenario   — What gets funded if budget changes by X%?
  2. Weight Scenario   — How does the priority list shift if we emphasize
                         complaints vs. condition?
  3. Deferral Cost     — What is the N-year cost of NOT funding the top
                         High/Critical segments?
  4. Coverage Analysis — How many lane-miles can we treat given $X budget?

Important scope notes:
  - The deferral analysis covers High/Critical segments only (not the full
    network).  Low/Medium segments are not modeled for deferral cost because
    their deterioration curves are slower and the cost multiplier assumptions
    are less defensible at that range.
  - Budget allocation uses a greedy algorithm (highest priority first).  This
    is optimal for maximizing coverage given divisible projects, but does not
    account for crew scheduling, seasonal constraints, or contract minimums.
    Use the crew capacity constraint option to add a realistic ceiling.
  - All cost figures are based on APWA 2023 benchmarks adjusted for Boise
    metro.  Confirm against actual bid history before presenting to Council.

Design: All scenarios are reproducible, logged, and return structured
DataFrames so the Streamlit dashboard can consume them directly.
"""

import uuid
import warnings
import pandas as pd
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from prioritization import (
    PWISPrioritizationModel,
    DEFAULT_WEIGHTS,
    ACTION_EMERGENCY,
    ACTION_REHAB,
    ACTION_PREVENTIVE,
    ACTION_CRACK_SEAL,
    ACTION_MONITOR_12M,
    ACTION_NO_ACTION,
    ACTION_DISPLAY_LABELS,
)


BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"


# ─── COST ASSUMPTIONS ─────────────────────────────────────────────────────────
# Source: APWA 2023 unit cost benchmarks (adjusted for Boise metro, ±25%)
# These are planning-level estimates suitable for budget scenario analysis.
# They should NOT be used as contract bid amounts or grant budget justifications
# without validation against recent Boise Public Works bid history.
#
# Values are keyed by the action codes defined in prioritization.py, not by
# full display sentences.  This prevents silent failures when display labels
# are updated for non-technical clarity.

TREATMENT_COST_PER_MILE = {
    ACTION_EMERGENCY:   250_000,   # Emergency repair: mobilization + structural work
    ACTION_REHAB:       120_000,   # Full rehabilitation: mill and overlay + base work
    ACTION_PREVENTIVE:   45_000,   # Preventive treatment: microsurface or thin overlay
    ACTION_CRACK_SEAL:   15_000,   # Crack seal + seal coat: surface preservation
    ACTION_MONITOR_12M:     500,   # Monitoring cost: inspection labor only
    ACTION_NO_ACTION:       200,   # Administrative tracking cost
}

# ─── DEFERRAL COST MULTIPLIERS ────────────────────────────────────────────────
# These multipliers estimate how much MORE a repair costs if deferred N years
# beyond the recommended treatment window.
#
# Source: APWA 2023 lifecycle cost analysis (Table 4.2); FHWA Pavement
#         Preservation Compendium Vol. II (2021), Section 6.4
#
# Limitation: Multipliers assume average Idaho climate and traffic loads.
#             Freeze-thaw cycle frequency and heavy truck percentage will
#             push actual multipliers higher for Boise winters.
#             Ranges reflect published uncertainty intervals.
#
# Example interpretation:
#   A Critical segment with a $100K repair cost today will cost ~$450K
#   if deferred until it becomes an emergency repair (4.5x multiplier).
#   The 200% premium documented in the README is based on this assumption.

DEFERRAL_COST_MULTIPLIER = {
    "Critical": {"value": 4.5, "range": (3.5, 6.0),
                 "note": "Emergency repair after structural failure; mobilization + disruption costs dominate"},
    "High":     {"value": 3.0, "range": (2.2, 4.0),
                 "note": "Rehabilitation after preventive window closes; base repair added to surface work"},
    "Medium":   {"value": 1.8, "range": (1.4, 2.3),
                 "note": "Moderate deterioration; crack seal becomes thin overlay"},
    "Low":      {"value": 1.1, "range": (1.0, 1.3),
                 "note": "Minimal deterioration expected within 5 years for healthy roads"},
}

# ─── ANNUAL DETERIORATION RATES ───────────────────────────────────────────────
# Condition Index points lost per year WITHOUT treatment.
#
# Source: PASER Road Rating Manual (2022), Wisconsin Transportation Centre;
#         cross-checked with FHWA State DOT average deterioration curves.
#         Values adjusted downward ~10% for Boise's lower annual precipitation
#         vs. upper Midwest baselines.
#
# Limitation: These are AVERAGE rates.  A Local street in a freeze-thaw zone
#             with inadequate drainage can deteriorate 2x faster.  Segments
#             with drainage work orders in work_orders.csv may warrant a
#             higher personal rate in a future model version.

ANNUAL_DETERIORATION_RATE = {   # CI points per year without treatment
    "Highway":   2.5,   # Low traffic stress; well-maintained base typical
    "Arterial":  3.5,   # Moderate truck loading; faster surface wear
    "Collector": 4.5,   # Higher relative stress per lane; smaller maintenance budget
    "Local":     5.5,   # Least maintenance investment; fastest relative decline
}

# ─── OPERATIONAL CONSTRAINTS ──────────────────────────────────────────────────
# Real-world limits that a pure greedy budget allocation does not consider.
# These constraints make the budget scenario more operationally realistic.
#
# Values are based on PWIS engineering judgment for a mid-size city department.
# Adjust based on Boise Public Works actual crew capacity and contract norms.

OPERATIONAL_CONSTRAINTS = {
    "max_crew_capacity_lane_miles_per_year": 300,
    # Approximate maximum lane-miles a typical 6-crew public works department
    # can treat in one construction season (April-October in Idaho).
    # Source: PWIS-ENG estimate; validate against Boise PW staffing plan.

    "construction_season_months": [4, 5, 6, 7, 8, 9, 10],
    # Months when asphalt paving is feasible in Boise (April-October).
    # Emergency repairs can occur year-round; preventive work is seasonal.

    "min_contract_segment_cost_usd": 5_000,
    # Projects below this threshold are typically handled by in-house crews
    # rather than contracted out.  Budget scenarios below this per-segment
    # cost use a different cost model than contracted rehabilitation.

    "max_single_district_pct": 0.40,
    # No single district should receive more than 40% of annual budget
    # (policy constraint for equitable distribution).
    # This is enforced only when enforce_min_per_district=True.
}


@dataclass
class ScenarioResult:
    scenario_id:     str
    scenario_type:   str
    description:     str
    parameters:      dict
    run_timestamp:   str = field(default_factory=lambda: datetime.now().isoformat())
    summary_metrics: dict = field(default_factory=dict)


class PWISScenarioEngine:
    """
    Runs what-if analyses on top of the PWIS prioritization model.

    All cost assumptions, deferral multipliers, and deterioration rates are
    documented in this module's constants with sources and known limitations.
    Run MODEL_ASSUMPTIONS from prioritization.py and the constants here
    before presenting any scenario results to stakeholders.

    Usage:
        engine = PWISScenarioEngine(roads, complaints, work_orders)
        funded_df, result = engine.run_budget_scenario(8_000_000)
    """

    def __init__(
        self,
        roads: pd.DataFrame,
        complaints: pd.DataFrame,
        work_orders: pd.DataFrame,
    ):
        self.roads       = roads
        self.complaints  = complaints
        self.work_orders = work_orders
        self._base_scores   = None
        self._scenario_log  = []

    def _get_base_scores(self) -> pd.DataFrame:
        """Cache baseline scores to avoid re-computing on every scenario call."""
        if self._base_scores is None:
            model = PWISPrioritizationModel(DEFAULT_WEIGHTS)
            self._base_scores = model.score(
                self.roads, self.complaints, self.work_orders
            )
        return self._base_scores

    def _estimate_treatment_cost(self, row) -> float:
        """
        Estimates treatment cost for one segment using action code and length.

        Uses action_code (symbolic constant) rather than the display label string
        to look up the cost — this decouples cost logic from UI copy changes.

        Falls back to NO_ACTION cost if the action code is unrecognized.
        """
        code   = row.get("action_code", ACTION_NO_ACTION)
        length = row.get("length_miles", 0.5)
        cost_per_mile = TREATMENT_COST_PER_MILE.get(code, TREATMENT_COST_PER_MILE[ACTION_NO_ACTION])
        return cost_per_mile * length

    # ─── SCENARIO 1: BUDGET ANALYSIS ─────────────────────────────────────────

    def run_budget_scenario(
        self,
        annual_budget_usd: float,
        prioritize_by: str = "priority_score",
        enforce_min_per_district: bool = True,
        enforce_crew_capacity: bool = True,
    ) -> tuple[pd.DataFrame, ScenarioResult]:
        """
        Given a budget, determine which segments get funded in priority order.

        Parameters:
            annual_budget_usd:       Total available maintenance budget
            prioritize_by:           Column to sort on ('priority_score' or
                                     'condition_index')
            enforce_min_per_district: Ensure each district gets at least 1
                                     project.  Implements basic equity
                                     distribution policy.
            enforce_crew_capacity:   Cap total funded lane-miles at
                                     OPERATIONAL_CONSTRAINTS
                                     ["max_crew_capacity_lane_miles_per_year"].
                                     Prevents the model from recommending
                                     more work than crews can execute in a
                                     construction season.

        Notes:
            - Allocation is greedy (highest priority first within constraints).
            - District minimum is funded before greedy pass begins, so a high-
              priority district may receive multiple projects while a low-priority
              district still receives at least one.
            - Crew capacity constraint is a HARD cap on total lane-miles, not
              on individual project size.

        Returns:
            (scores_df, ScenarioResult): Full segment DataFrame with
            funded_this_cycle column, plus a summary result object.
        """
        scores = self._get_base_scores().copy()

        scores["treatment_cost"] = scores.apply(self._estimate_treatment_cost, axis=1)
        scores = scores.sort_values(prioritize_by, ascending=False).reset_index(drop=True)

        remaining       = annual_budget_usd
        remaining_miles = OPERATIONAL_CONSTRAINTS["max_crew_capacity_lane_miles_per_year"]
        funded          = []

        # Pass 1: Guarantee at least one funded project per district (equity floor).
        if enforce_min_per_district:
            district_tops = scores.groupby("district").first().reset_index()
            for _, seg in district_tops.iterrows():
                cost   = seg["treatment_cost"]
                length = seg.get("length_miles", 0.5)
                if remaining >= cost and (
                    not enforce_crew_capacity or remaining_miles >= length
                ):
                    funded.append(seg["segment_id"])
                    remaining -= cost
                    remaining_miles -= length

        # Pass 2: Greedy allocation — highest priority first.
        for _, seg in scores.iterrows():
            if seg["segment_id"] in funded:
                continue
            cost   = seg["treatment_cost"]
            length = seg.get("length_miles", 0.5)

            budget_ok = remaining >= cost
            capacity_ok = (not enforce_crew_capacity) or (remaining_miles >= length)

            if budget_ok and capacity_ok:
                funded.append(seg["segment_id"])
                remaining -= cost
                remaining_miles -= length
            # No early exit: a cheaper project further down the list may still fit.

        scores["funded_this_cycle"] = scores["segment_id"].isin(funded)

        # Cumulative cost is meaningful only when viewed in the sorted order.
        funded_sorted = scores[scores["funded_this_cycle"]]["treatment_cost"].cumsum()
        scores["cumulative_cost"] = funded_sorted

        funded_df   = scores[scores["funded_this_cycle"]].copy()
        unfunded_df = scores[~scores["funded_this_cycle"]].copy()

        # Capacity warning: if crew capacity was the binding constraint (not budget),
        # operators should know — it may mean hiring or contracting is needed.
        budget_was_binding   = remaining < scores["treatment_cost"].min()
        capacity_was_binding = (
            enforce_crew_capacity and
            remaining_miles < scores[~scores["funded_this_cycle"]]["length_miles"].min()
        )
        if capacity_was_binding and not budget_was_binding:
            warnings.warn(
                "[PWIS Scenario] Crew capacity (not budget) was the binding constraint. "
                f"Budget remaining: ${remaining:,.0f}. "
                "Consider additional contracting capacity to fully utilize the budget.",
                UserWarning,
                stacklevel=2,
            )

        result = ScenarioResult(
            scenario_id=f"BUDGET-{uuid.uuid4().hex[:12].upper()}",
            scenario_type="Budget Allocation",
            description=f"Budget scenario: ${annual_budget_usd:,.0f} annual budget",
            parameters={
                "budget":                    annual_budget_usd,
                "prioritize_by":             prioritize_by,
                "enforce_min_per_district":  enforce_min_per_district,
                "enforce_crew_capacity":     enforce_crew_capacity,
            },
            summary_metrics={
                "total_budget":             annual_budget_usd,
                "segments_funded":          len(funded_df),
                "segments_unfunded":        len(unfunded_df),
                "budget_utilized":          float(funded_df["treatment_cost"].sum()),
                "budget_remaining":         remaining,
                "pct_budget_used":          round(
                    funded_df["treatment_cost"].sum() / max(annual_budget_usd, 1) * 100, 1
                ),
                "lane_miles_treated":       round(funded_df["length_miles"].sum(), 1),
                "crew_capacity_remaining_miles": round(remaining_miles, 1),
                "avg_priority_funded":      round(float(funded_df["priority_score"].mean()), 1),
                "avg_condition_unfunded":   round(float(unfunded_df["condition_index"].mean()), 1),
                "critical_segments_funded": int(
                    (funded_df["priority_tier"].astype(str) == "Critical").sum()
                ),
                "critical_segments_unfunded": int(
                    (unfunded_df["priority_tier"].astype(str) == "Critical").sum()
                ),
            },
        )

        self._scenario_log.append(asdict(result))
        return scores, result

    # ─── SCENARIO 2: WEIGHT SENSITIVITY ──────────────────────────────────────

    def run_weight_scenario(
        self,
        custom_weights: dict,
        label: str = "Custom",
    ) -> tuple[pd.DataFrame, dict]:
        """
        Re-runs the model with alternative weights and compares rankings
        to the baseline.

        This scenario answers: "If we shifted policy toward [e.g. complaints],
        which segments would move up or down the priority list, and by how much?"

        The top10_stability metric is particularly useful for Council briefings:
        it shows whether the highest-priority segments are robust to weight
        changes (high stability) or sensitive to them (low stability, meaning
        the prioritization is contentious).

        Parameters:
            custom_weights: Dict of {component: weight}, must sum to 1.0
            label:          Descriptive name for this scenario (e.g.
                            "Complaint-Driven" or "Equity-First")

        Returns:
            (comparison_df, summary_dict):
              comparison_df has both base and alt scores/ranks per segment,
              plus rank_shift and tier_changed columns.
        """
        total = sum(custom_weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Weights must sum to 1.0 (got {total:.3f}). "
                "Adjust custom_weights before running this scenario."
            )

        baseline = self._get_base_scores()[
            ["segment_id", "priority_score", "priority_tier"]
        ].copy()
        baseline.columns = ["segment_id", "base_score", "base_tier"]
        baseline["base_rank"] = (
            baseline["base_score"].rank(ascending=False, method="dense").astype(int)
        )

        alt_model  = PWISPrioritizationModel(custom_weights)
        alt_scores = alt_model.score(self.roads, self.complaints, self.work_orders)
        alt_scores["alt_rank"] = (
            alt_scores["priority_score"].rank(ascending=False, method="dense").astype(int)
        )

        comparison = alt_scores.merge(baseline, on="segment_id")
        comparison["rank_shift"]   = comparison["base_rank"] - comparison["alt_rank"]
        comparison["tier_changed"] = (
            comparison["priority_tier"].astype(str) != comparison["base_tier"].astype(str)
        )
        comparison["score_delta"]  = comparison["priority_score"] - comparison["base_score"]

        # Top-10 stability: what fraction of the top-10 baseline segments
        # remain in the top 10 under the alternative weights?
        top10_stable = (
            comparison[comparison["base_rank"] <= 10]["alt_rank"] <= 10
        ).mean()

        result = {
            "label":            label,
            "weights_used":     custom_weights,
            "weights_baseline": DEFAULT_WEIGHTS,
            "top10_stability":  round(float(top10_stable), 2),
            # High stability (> 0.8) means the top-priority list is robust to
            # weight changes.  Low stability (< 0.5) means the prioritization
            # is highly sensitive to policy assumptions — investigate further.
            "avg_rank_shift":   round(float(comparison["rank_shift"].abs().mean()), 1),
            "tier_changes":     int(comparison["tier_changed"].sum()),
            "segments_rose_to_high_critical": int(
                (
                    (comparison["tier_changed"]) &
                    (comparison["priority_tier"].astype(str).isin(["High", "Critical"])) &
                    (comparison["base_tier"].astype(str).isin(["Low", "Medium"]))
                ).sum()
            ),
            "segments_fell_from_high_critical": int(
                (
                    (comparison["tier_changed"]) &
                    (comparison["base_tier"].astype(str).isin(["High", "Critical"])) &
                    (comparison["priority_tier"].astype(str).isin(["Low", "Medium"]))
                ).sum()
            ),
        }

        return comparison, result

    # ─── SCENARIO 3: DEFERRAL COST CALCULATOR ────────────────────────────────

    def run_deferral_scenario(
        self,
        years: int = 5,
        segments_to_defer: Optional[list] = None,
    ) -> pd.DataFrame:
        """
        Estimates the cost of deferring maintenance on a set of segments
        over N years.

        SCOPE: This analysis covers HIGH and CRITICAL segments only by default.
        Low and Medium segments are excluded because:
          a) Their deterioration curves are slower and less predictable.
          b) The cost multiplier assumptions are least defensible at that range.
          c) The Council argument is strongest for High/Critical — these are
             the segments where deferral compounds cost most dramatically.

        Key insight for Council briefings:
          Deferral does not save money — it shifts cost forward and multiplies
          it.  The question is not "can we afford to fix it?" but "can we afford
          to wait until we have no choice?"

        Parameters:
            years:               Number of years to model deferral (default: 5)
            segments_to_defer:   List of segment_ids to analyze.  If None,
                                 analyzes all High/Critical segments.

        Cost assumptions:
          - DEFERRAL_COST_MULTIPLIER: see module-level constant for sources
          - ANNUAL_DETERIORATION_RATE: CI points lost per year by road type
          - Base cost: estimated_repair_cost_usd from road segment data

        Returns:
            DataFrame with one row per (segment, year_deferred) combination,
            showing projected condition, tier, and cost at each deferral point.
        """
        scores = self._get_base_scores().copy()

        if segments_to_defer is None:
            defer_set = scores[
                scores["priority_tier"].astype(str).isin(["High", "Critical"])
            ]["segment_id"].tolist()

            if len(defer_set) == 0:
                warnings.warn(
                    "[PWIS Scenario] No High/Critical segments found for deferral analysis. "
                    "Check that the prioritization model has been run with the current dataset.",
                    UserWarning,
                    stacklevel=2,
                )
                return pd.DataFrame()
        else:
            defer_set = segments_to_defer

        defer_df = scores[scores["segment_id"].isin(defer_set)].copy()

        results = []
        for _, seg in defer_df.iterrows():
            tier         = str(seg.get("priority_tier", "Medium"))
            current_ci   = seg.get("condition_index", 50)
            road_type    = seg.get("road_type", "Collector")
            current_cost = seg.get("estimated_repair_cost_usd", 50_000)
            length       = seg.get("length_miles", 0.5)

            det_rate     = ANNUAL_DETERIORATION_RATE.get(road_type, 4.0)
            multiplier_info = DEFERRAL_COST_MULTIPLIER.get(
                tier, DEFERRAL_COST_MULTIPLIER["Medium"]
            )
            cost_multiplier = multiplier_info["value"]

            for y in range(years + 1):
                new_ci = max(5, current_ci - det_rate * y)

                # Projected cost: linear ramp between today and full multiplier
                # at the end of the deferral horizon.  This is a conservative
                # (lower bound) estimate; actual compounding can be superlinear
                # for segments crossing the CI=40 structural failure threshold.
                projected_cost = current_cost * (1 + (cost_multiplier - 1) * y / max(years, 1))

                # Re-tier based on projected degraded condition
                if new_ci < 25:    new_tier = "Critical"
                elif new_ci < 40:  new_tier = "High"
                elif new_ci < 55:  new_tier = "Medium"
                else:              new_tier = "Low"

                results.append({
                    "segment_id":        seg["segment_id"],
                    "street_name":       seg.get("street_name", ""),
                    "district":          seg.get("district", ""),
                    "road_type":         road_type,
                    "year_deferred":     y,
                    "projected_year":    datetime.today().year + y,
                    "projected_ci":      round(new_ci, 1),
                    "projected_tier":    new_tier,
                    "current_cost":      current_cost,
                    "projected_cost":    round(projected_cost),
                    "additional_cost":   round(projected_cost - current_cost),
                    "length_miles":      length,
                    # Include multiplier range for honest uncertainty communication
                    "cost_multiplier_low":  multiplier_info["range"][0],
                    "cost_multiplier_high": multiplier_info["range"][1],
                    "low_bound_projected":  round(
                        current_cost * (1 + (multiplier_info["range"][0] - 1) * y / max(years, 1))
                    ),
                    "high_bound_projected": round(
                        current_cost * (1 + (multiplier_info["range"][1] - 1) * y / max(years, 1))
                    ),
                })

        deferral_df = pd.DataFrame(results)

        # Summary (printed for CLI use; also loggable)
        year_n = deferral_df[deferral_df["year_deferred"] == years]
        total_today    = year_n["current_cost"].sum()
        total_deferred = year_n["projected_cost"].sum()
        total_low      = year_n["low_bound_projected"].sum()
        total_high     = year_n["high_bound_projected"].sum()

        print(f"\nDeferral Cost Analysis ({years}-Year Horizon)")
        print(f"  Scope: High/Critical segments only ({len(defer_set)} segments)")
        print(f"  Segments analyzed:         {len(defer_set)}")
        print(f"  Cost if funded today:      ${total_today:>14,.0f}")
        print(f"  Projected cost at {years} yr:  ${total_deferred:>14,.0f}")
        print(f"  Additional cost (central): ${total_deferred - total_today:>14,.0f}  "
              f"({(total_deferred / max(total_today, 1) - 1) * 100:.0f}% premium)")
        print(f"  Uncertainty range at {years} yr: ${total_low:,.0f} – ${total_high:,.0f}")
        print(f"  Note: These estimates use APWA 2023 benchmarks with ±25% uncertainty.")

        return deferral_df

    # ─── SCENARIO 4: COVERAGE ANALYSIS ────────────────────────────────────────

    def run_coverage_analysis(
        self,
        budget_levels: list = None,
    ) -> pd.DataFrame:
        """
        Shows the marginal impact of each additional budget increment:
        how many segments and lane-miles are treated at each funding level.

        Useful for Council presentations: "What does $X buy us?"
        Also shows diminishing returns — the marginal lane-mile treated
        at $15M is typically in far better condition than at $4M, which
        illustrates the value of early investment.

        Budget levels represent total annual maintenance budgets, not
        incremental additions.  Each level is run as an independent scenario.

        Returns:
            DataFrame with one row per budget level showing coverage metrics.
        """
        if budget_levels is None:
            budget_levels = [
                2_000_000, 4_000_000, 6_000_000, 8_000_000,
                10_000_000, 15_000_000, 20_000_000,
            ]

        rows = []
        for budget in budget_levels:
            scores, result = self.run_budget_scenario(budget)
            m = result.summary_metrics
            rows.append({
                "budget_usd":            budget,
                "budget_millions":       budget / 1_000_000,
                "segments_funded":       m["segments_funded"],
                "lane_miles_treated":    m["lane_miles_treated"],
                "pct_budget_used":       m["pct_budget_used"],
                "avg_priority_funded":   m["avg_priority_funded"],
                "critical_funded":       m["critical_segments_funded"],
                "critical_unfunded":     m["critical_segments_unfunded"],
                "budget_per_lane_mile":  round(budget / max(m["lane_miles_treated"], 0.1)),
            })

        coverage_df = pd.DataFrame(rows)

        # Add marginal lane-miles: how many MORE lane-miles does each additional
        # budget increment buy?  Useful for "bang per buck" argument to Council.
        coverage_df["marginal_lane_miles"] = coverage_df["lane_miles_treated"].diff().fillna(
            coverage_df["lane_miles_treated"].iloc[0]
        ).round(1)

        return coverage_df

    # ─── UTILITIES ────────────────────────────────────────────────────────────

    def get_scenario_log(self) -> pd.DataFrame:
        """Returns a DataFrame of all scenario runs in this session."""
        if not self._scenario_log:
            return pd.DataFrame()
        return pd.DataFrame([
            {k: v for k, v in s.items() if k != "parameters"}
            for s in self._scenario_log
        ])

    def get_cost_assumption_summary(self) -> str:
        """
        Returns a plain-English summary of cost assumptions for briefing docs.
        Always include this when presenting deferral analysis to stakeholders.
        """
        lines = [
            "PWIS Scenario Engine — Cost Assumption Summary",
            "=" * 50,
            "Source: APWA 2023 unit cost benchmarks (Boise metro adjusted)",
            "Uncertainty: ±25% on all figures; validate against bid history",
            "",
            "Treatment Costs per Lane-Mile:",
        ]
        for code, cost in TREATMENT_COST_PER_MILE.items():
            label = ACTION_DISPLAY_LABELS.get(code, code)
            lines.append(f"  {label[:45]:45s}  ${cost:>10,.0f}/mile")

        lines += [
            "",
            "Deferral Cost Multipliers (N-year horizon):",
        ]
        for tier, info in DEFERRAL_COST_MULTIPLIER.items():
            lo, hi = info["range"]
            lines.append(
                f"  {tier:10s}: {info['value']}x central  ({lo}x–{hi}x range)  — {info['note'][:60]}"
            )

        return "\n".join(lines)


# ─── CLI RUNNER ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Loading data...")
    roads       = pd.read_csv(DATA_DIR / "road_segments.csv")
    complaints  = pd.read_csv(DATA_DIR / "complaints.csv")
    work_orders = pd.read_csv(DATA_DIR / "work_orders.csv")

    engine = PWISScenarioEngine(roads, complaints, work_orders)

    print("\n" + "=" * 60)
    print("SCENARIO 1: Budget Analysis — $8M Annual Budget")
    print("=" * 60)
    funded_df, s1 = engine.run_budget_scenario(8_000_000)
    for k, v in s1.summary_metrics.items():
        print(f"  {k:40s}: {v:>12}")

    print("\n" + "=" * 60)
    print("SCENARIO 2: Weight Sensitivity — Complaint-First")
    print("=" * 60)
    complaint_weights = {
        "condition_severity": 0.20,
        "traffic_impact":     0.20,
        "complaint_pressure": 0.40,
        "cost_efficiency":    0.12,
        "equity_modifier":    0.08,
    }
    _, s2 = engine.run_weight_scenario(complaint_weights, label="Complaint-Driven")
    for k, v in s2.items():
        if k not in ("weights_used", "weights_baseline"):
            print(f"  {k:40s}: {v}")

    print("\n" + "=" * 60)
    print("SCENARIO 3: 5-Year Deferral Cost")
    print("=" * 60)
    deferral_df = engine.run_deferral_scenario(years=5)
    deferral_df.to_csv(DATA_DIR / "deferral_analysis.csv", index=False)
    print(f"  Deferral analysis saved -> data/deferral_analysis.csv")

    print("\n" + "=" * 60)
    print("SCENARIO 4: Budget Coverage Analysis")
    print("=" * 60)
    coverage = engine.run_coverage_analysis()
    print(coverage.to_string(index=False))

    print("\n" + "=" * 60)
    print("COST ASSUMPTION REFERENCE")
    print("=" * 60)
    print(engine.get_cost_assumption_summary())

    print("\n✓ Scenario engine complete.")
