"""
PWIS Utility Scenario Simulation Engine
=========================================
Answers the question: "What changes if we adjust the CIP budget or priorities?"

Scenarios supported:
  1. CIP Budget Scenario — What gets funded across water/sewer/stormwater
                           if budget changes by X%?
  2. Weight Scenario     — How does the priority list shift if we emphasize
                           break history vs. condition?
  3. Deferral Cost       — What is the N-year cost of NOT replacing the top
                           High/Critical pipes?
  4. Coverage Analysis   — How many pipe-miles can we replace given $X budget?

Important scope notes:
  - Deferral analysis covers High/Critical segments only.  Low/Medium pipes
    are excluded because their deterioration curves are slower and the cost
    multiplier assumptions are less defensible at that range.
  - Budget allocation uses a greedy algorithm (highest priority first).
    This does not account for excavation crew scheduling, seasonal constraints,
    or permitting lead times.  Use crew capacity constraint for realism.
  - All cost figures are based on AWWA 2023 benchmarks adjusted for Boise
    metro.  Confirm against actual bid history before presenting to Council.
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
    ACTION_REPLACE,
    ACTION_REHABILITATE,
    ACTION_LINE,
    ACTION_REPAIR,
    ACTION_MONITOR,
    ACTION_NO_ACTION,
    ACTION_DISPLAY_LABELS,
)


BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"


# ─── COST ASSUMPTIONS ─────────────────────────────────────────────────────────
# Source: AWWA 2023 unit cost benchmarks (adjusted for Boise metro, ±25%)
# Values are per linear foot, keyed by action codes from prioritization.py.

REPLACEMENT_COST_PER_LF = {
    ACTION_REPLACE:      275,     # Full replacement: open-cut excavation + backfill
    ACTION_REHABILITATE: 140,     # Rehabilitation: CIPP or slip-lining
    ACTION_LINE:          70,     # Trenchless lining: spray/fold-and-form
    ACTION_REPAIR:        35,     # Spot repair: average per LF amortized
    ACTION_MONITOR:        1,     # Inspection labor per LF
    ACTION_NO_ACTION:      0.50,  # Administrative tracking per LF
}

# ─── DEFERRAL COST MULTIPLIERS ────────────────────────────────────────────────
# How much MORE a replacement costs if deferred N years beyond recommended window.
#
# Source: AWWA 2023 lifecycle cost analysis; EPA CMOM economic guidance
#
# Limitation: Multipliers assume average Boise soil conditions.  Areas with
#             high groundwater or expansive clay soils may see higher multipliers.

DEFERRAL_COST_MULTIPLIER = {
    "Critical": {"value": 4.5, "range": (3.5, 6.0),
                 "note": "Emergency repair after failure; emergency mobilization + environmental cleanup costs dominate"},
    "High":     {"value": 3.0, "range": (2.2, 4.0),
                 "note": "Replacement after lining window closes; excavation in degraded trench conditions"},
    "Medium":   {"value": 1.8, "range": (1.4, 2.3),
                 "note": "Moderate deterioration; spot repair becomes full rehabilitation"},
    "Low":      {"value": 1.1, "range": (1.0, 1.3),
                 "note": "Minimal deterioration expected within 5 years for healthy pipes"},
}

# ─── ANNUAL DETERIORATION RATES ───────────────────────────────────────────────
# Condition points lost per year WITHOUT intervention, by material category.
#
# Source: AWWA 2023 pipe deterioration curves; NASSCO PACP grade regression

ANNUAL_DETERIORATION_RATE = {
    "Cast Iron":        3.5,   # Corrosion-driven; accelerated in Boise's alkaline soil
    "Galvanized Steel": 4.0,   # Highest corrosion rate of any material
    "Asbestos Cement":  2.5,   # Brittle fracture risk; less gradual than corrosion
    "Orangeburg":       5.0,   # Fiber-based; degrades rapidly when saturated
    "Vitrified Clay":   2.0,   # Joint degradation; pipe body is durable
    "Corrugated Metal": 3.0,   # Corrosion at invert; accelerated in stormwater
    "Concrete":         1.5,   # Slow if not exposed to H2S (sewer environments worse)
    "Ductile Iron":     1.5,   # Modern coatings slow corrosion significantly
    "PVC":              0.8,   # Chemical-resistant; joint separation is primary failure mode
    "HDPE":             0.5,   # Fusion joints; lowest deterioration rate
    "Reinforced Concrete Box": 1.8,  # Large structures; spalling drives failure
}

# ─── OPERATIONAL CONSTRAINTS ──────────────────────────────────────────────────

OPERATIONAL_CONSTRAINTS = {
    "max_crew_capacity_pipe_feet_per_year": 250_000,
    # Approximate maximum linear feet a 4-crew utility department can
    # replace/rehabilitate in one construction season (April-October in Idaho).
    # Source: PWIS-ENG estimate; validate against Boise PW staffing plan.

    "construction_season_months": [4, 5, 6, 7, 8, 9, 10],
    # Months when open-cut excavation is feasible in Boise (April-October).
    # CIPP lining can occur year-round in heated pipes.

    "min_contract_segment_cost_usd": 10_000,
    # Projects below this threshold are typically handled by in-house crews.

    "max_single_district_pct": 0.40,
    # No single district should receive more than 40% of annual CIP budget
    # (policy constraint for equitable distribution).
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
    Runs what-if analyses on top of the PWIS utility prioritization model.

    Usage:
        engine = PWISScenarioEngine(pipes, service_requests, work_orders)
        funded_df, result = engine.run_budget_scenario(15_000_000)
    """

    def __init__(
        self,
        pipes: pd.DataFrame,
        service_requests: pd.DataFrame,
        work_orders: pd.DataFrame,
    ):
        self.pipes            = pipes
        self.service_requests = service_requests
        self.work_orders      = work_orders
        self._base_scores     = None
        self._scenario_log    = []

    def _get_base_scores(self) -> pd.DataFrame:
        if self._base_scores is None:
            model = PWISPrioritizationModel(DEFAULT_WEIGHTS)
            self._base_scores = model.score(
                self.pipes, self.service_requests, self.work_orders
            )
        return self._base_scores

    def _estimate_treatment_cost(self, row) -> float:
        """Estimates treatment cost using action code and pipe length."""
        code      = row.get("action_code", ACTION_NO_ACTION)
        length_ft = row.get("length_ft", 500)
        cost_per_lf = REPLACEMENT_COST_PER_LF.get(code, REPLACEMENT_COST_PER_LF[ACTION_NO_ACTION])
        return cost_per_lf * length_ft

    # ─── SCENARIO 1: CIP BUDGET ANALYSIS ─────────────────────────────────────

    def run_budget_scenario(
        self,
        annual_budget_usd: float,
        prioritize_by: str = "priority_score",
        system_filter: str = None,
        enforce_min_per_district: bool = True,
        enforce_crew_capacity: bool = True,
    ) -> tuple[pd.DataFrame, ScenarioResult]:
        """
        Given a CIP budget, determine which pipe segments get funded.

        Parameters:
            annual_budget_usd:       Total available CIP budget
            prioritize_by:           Column to sort on
            system_filter:           Optional: "Water", "Sewer", or "Stormwater"
            enforce_min_per_district: Ensure each district gets at least 1 project
            enforce_crew_capacity:   Cap total funded pipe-feet at crew capacity
        """
        scores = self._get_base_scores().copy()

        if system_filter:
            scores = scores[scores["system_type"] == system_filter].copy()

        scores["treatment_cost"] = scores.apply(self._estimate_treatment_cost, axis=1)
        scores = scores.sort_values(prioritize_by, ascending=False).reset_index(drop=True)

        remaining       = annual_budget_usd
        remaining_ft    = OPERATIONAL_CONSTRAINTS["max_crew_capacity_pipe_feet_per_year"]
        funded          = []

        # Pass 1: Equity floor — at least one project per district
        if enforce_min_per_district:
            district_tops = scores.groupby("district").first().reset_index()
            for _, seg in district_tops.iterrows():
                cost      = seg["treatment_cost"]
                length_ft = seg.get("length_ft", 500)
                if remaining >= cost and (
                    not enforce_crew_capacity or remaining_ft >= length_ft
                ):
                    funded.append(seg["segment_id"])
                    remaining -= cost
                    remaining_ft -= length_ft

        # Pass 2: Greedy allocation
        for _, seg in scores.iterrows():
            if seg["segment_id"] in funded:
                continue
            cost      = seg["treatment_cost"]
            length_ft = seg.get("length_ft", 500)

            budget_ok   = remaining >= cost
            capacity_ok = (not enforce_crew_capacity) or (remaining_ft >= length_ft)

            if budget_ok and capacity_ok:
                funded.append(seg["segment_id"])
                remaining -= cost
                remaining_ft -= length_ft

        scores["funded_this_cycle"] = scores["segment_id"].isin(funded)

        funded_sorted = scores[scores["funded_this_cycle"]]["treatment_cost"].cumsum()
        scores["cumulative_cost"] = funded_sorted

        funded_df   = scores[scores["funded_this_cycle"]].copy()
        unfunded_df = scores[~scores["funded_this_cycle"]].copy()

        # Capacity warning
        budget_was_binding = remaining < scores["treatment_cost"].min() if len(scores) > 0 else False
        capacity_was_binding = (
            enforce_crew_capacity and len(unfunded_df) > 0 and
            remaining_ft < unfunded_df["length_ft"].min()
        )
        if capacity_was_binding and not budget_was_binding:
            warnings.warn(
                "[PWIS Scenario] Crew capacity (not budget) was the binding constraint. "
                f"Budget remaining: ${remaining:,.0f}. "
                "Consider additional contracting capacity.",
                UserWarning,
                stacklevel=2,
            )

        result = ScenarioResult(
            scenario_id=f"BUDGET-{uuid.uuid4().hex[:12].upper()}",
            scenario_type="CIP Budget Allocation",
            description=f"CIP budget scenario: ${annual_budget_usd:,.0f}",
            parameters={
                "budget":                   annual_budget_usd,
                "prioritize_by":            prioritize_by,
                "system_filter":            system_filter,
                "enforce_min_per_district": enforce_min_per_district,
                "enforce_crew_capacity":    enforce_crew_capacity,
            },
            summary_metrics={
                "total_budget":             annual_budget_usd,
                "segments_funded":          len(funded_df),
                "segments_unfunded":        len(unfunded_df),
                "budget_utilized":          float(funded_df["treatment_cost"].sum()) if len(funded_df) > 0 else 0,
                "budget_remaining":         remaining,
                "pct_budget_used":          round(
                    funded_df["treatment_cost"].sum() / max(annual_budget_usd, 1) * 100, 1
                ) if len(funded_df) > 0 else 0,
                "pipe_feet_treated":        int(funded_df["length_ft"].sum()) if len(funded_df) > 0 else 0,
                "crew_capacity_remaining_ft": int(remaining_ft),
                "avg_priority_funded":      round(float(funded_df["priority_score"].mean()), 1) if len(funded_df) > 0 else 0,
                "avg_condition_unfunded":   round(float(unfunded_df["condition_score"].mean()), 1) if len(unfunded_df) > 0 else 0,
                "critical_segments_funded":   int((funded_df["priority_tier"].astype(str) == "Critical").sum()) if len(funded_df) > 0 else 0,
                "critical_segments_unfunded": int((unfunded_df["priority_tier"].astype(str) == "Critical").sum()) if len(unfunded_df) > 0 else 0,
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
        Re-runs the model with alternative weights and compares rankings.

        Answers: "If we shifted policy toward [e.g. break history],
        which pipes would move up or down the priority list?"
        """
        total = sum(custom_weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Weights must sum to 1.0 (got {total:.3f})."
            )

        baseline = self._get_base_scores()[
            ["segment_id", "priority_score", "priority_tier"]
        ].copy()
        baseline.columns = ["segment_id", "base_score", "base_tier"]
        baseline["base_rank"] = (
            baseline["base_score"].rank(ascending=False, method="dense").astype(int)
        )

        alt_model  = PWISPrioritizationModel(custom_weights)
        alt_scores = alt_model.score(self.pipes, self.service_requests, self.work_orders)
        alt_scores["alt_rank"] = (
            alt_scores["priority_score"].rank(ascending=False, method="dense").astype(int)
        )

        comparison = alt_scores.merge(baseline, on="segment_id")
        comparison["rank_shift"]   = comparison["base_rank"] - comparison["alt_rank"]
        comparison["tier_changed"] = (
            comparison["priority_tier"].astype(str) != comparison["base_tier"].astype(str)
        )
        comparison["score_delta"] = comparison["priority_score"] - comparison["base_score"]

        top10_stable = (
            comparison[comparison["base_rank"] <= 10]["alt_rank"] <= 10
        ).mean()

        result = {
            "label":            label,
            "weights_used":     custom_weights,
            "weights_baseline": DEFAULT_WEIGHTS,
            "top10_stability":  round(float(top10_stable), 2),
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
        Estimates cost of deferring pipe replacement over N years.

        SCOPE: High and Critical pipes only by default.
        """
        scores = self._get_base_scores().copy()

        if segments_to_defer is None:
            defer_set = scores[
                scores["priority_tier"].astype(str).isin(["High", "Critical"])
            ]["segment_id"].tolist()

            if len(defer_set) == 0:
                warnings.warn(
                    "[PWIS Scenario] No High/Critical pipes found for deferral analysis.",
                    UserWarning,
                    stacklevel=2,
                )
                return pd.DataFrame()
        else:
            defer_set = segments_to_defer

        defer_df = scores[scores["segment_id"].isin(defer_set)].copy()

        results = []
        for _, seg in defer_df.iterrows():
            tier          = str(seg.get("priority_tier", "Medium"))
            current_cond  = seg.get("condition_score", 50)
            material      = seg.get("pipe_material", "PVC")
            current_cost  = seg.get("estimated_replacement_cost_usd", 100_000)
            length_ft     = seg.get("length_ft", 500)

            det_rate     = ANNUAL_DETERIORATION_RATE.get(material, 2.0)
            multiplier_info = DEFERRAL_COST_MULTIPLIER.get(
                tier, DEFERRAL_COST_MULTIPLIER["Medium"]
            )
            cost_multiplier = multiplier_info["value"]

            for y in range(years + 1):
                new_cond = max(5, current_cond - det_rate * y)

                projected_cost = current_cost * (1 + (cost_multiplier - 1) * y / max(years, 1))

                if new_cond < 25:    new_tier = "Critical"
                elif new_cond < 40:  new_tier = "High"
                elif new_cond < 55:  new_tier = "Medium"
                else:                new_tier = "Low"

                results.append({
                    "segment_id":        seg["segment_id"],
                    "system_type":       seg.get("system_type", ""),
                    "corridor_name":     seg.get("corridor_name", ""),
                    "district":          seg.get("district", ""),
                    "pipe_material":     material,
                    "year_deferred":     y,
                    "projected_year":    datetime.today().year + y,
                    "projected_condition": round(new_cond, 1),
                    "projected_tier":    new_tier,
                    "current_cost":      current_cost,
                    "projected_cost":    round(projected_cost),
                    "additional_cost":   round(projected_cost - current_cost),
                    "length_ft":         length_ft,
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

        year_n = deferral_df[deferral_df["year_deferred"] == years]
        total_today    = year_n["current_cost"].sum()
        total_deferred = year_n["projected_cost"].sum()
        total_low      = year_n["low_bound_projected"].sum()
        total_high     = year_n["high_bound_projected"].sum()

        print(f"\nDeferral Cost Analysis ({years}-Year Horizon)")
        print(f"  Scope: High/Critical pipes only ({len(defer_set)} pipes)")
        print(f"  Cost if funded today:      ${total_today:>14,.0f}")
        print(f"  Projected cost at {years} yr:  ${total_deferred:>14,.0f}")
        print(f"  Additional cost (central): ${total_deferred - total_today:>14,.0f}  "
              f"({(total_deferred / max(total_today, 1) - 1) * 100:.0f}% premium)")
        print(f"  Uncertainty range at {years} yr: ${total_low:,.0f} – ${total_high:,.0f}")

        return deferral_df

    # ─── SCENARIO 4: COVERAGE ANALYSIS ────────────────────────────────────────

    def run_coverage_analysis(
        self,
        budget_levels: list = None,
    ) -> pd.DataFrame:
        """
        Shows marginal impact of each budget increment:
        how many pipe segments and linear feet are treated at each funding level.
        """
        if budget_levels is None:
            budget_levels = [
                5_000_000, 10_000_000, 15_000_000, 20_000_000,
                30_000_000, 50_000_000, 75_000_000,
            ]

        rows = []
        for budget in budget_levels:
            scores, result = self.run_budget_scenario(budget)
            m = result.summary_metrics
            rows.append({
                "budget_usd":          budget,
                "budget_millions":     budget / 1_000_000,
                "segments_funded":     m["segments_funded"],
                "pipe_feet_treated":   m["pipe_feet_treated"],
                "pct_budget_used":     m["pct_budget_used"],
                "avg_priority_funded": m["avg_priority_funded"],
                "critical_funded":     m["critical_segments_funded"],
                "critical_unfunded":   m["critical_segments_unfunded"],
                "budget_per_pipe_foot": round(budget / max(m["pipe_feet_treated"], 1)),
            })

        coverage_df = pd.DataFrame(rows)
        coverage_df["marginal_pipe_feet"] = coverage_df["pipe_feet_treated"].diff().fillna(
            coverage_df["pipe_feet_treated"].iloc[0]
        ).round(0).astype(int)

        return coverage_df

    # ─── UTILITIES ────────────────────────────────────────────────────────────

    def get_scenario_log(self) -> pd.DataFrame:
        if not self._scenario_log:
            return pd.DataFrame()
        return pd.DataFrame([
            {k: v for k, v in s.items() if k != "parameters"}
            for s in self._scenario_log
        ])

    def get_cost_assumption_summary(self) -> str:
        lines = [
            "PWIS Utility Scenario Engine — Cost Assumption Summary",
            "=" * 55,
            "Source: AWWA 2023 unit cost benchmarks (Boise metro adjusted)",
            "Uncertainty: ±25% on all figures; validate against bid history",
            "",
            "Replacement/Rehabilitation Costs per Linear Foot:",
        ]
        for code, cost in REPLACEMENT_COST_PER_LF.items():
            label = ACTION_DISPLAY_LABELS.get(code, code)
            lines.append(f"  {label[:50]:50s}  ${cost:>8,.2f}/LF")

        lines += [
            "",
            "Deferral Cost Multipliers (N-year horizon):",
        ]
        for tier, info in DEFERRAL_COST_MULTIPLIER.items():
            lo, hi = info["range"]
            lines.append(
                f"  {tier:10s}: {info['value']}x central  ({lo}x–{hi}x range)  — {info['note'][:55]}"
            )

        return "\n".join(lines)


# ─── CLI RUNNER ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Loading data...")
    pipes            = pd.read_csv(DATA_DIR / "pipe_segments.csv")
    service_requests = pd.read_csv(DATA_DIR / "service_requests.csv")
    work_orders      = pd.read_csv(DATA_DIR / "work_orders.csv")

    engine = PWISScenarioEngine(pipes, service_requests, work_orders)

    print("\n" + "=" * 60)
    print("SCENARIO 1: CIP Budget Analysis — $15M Annual Budget")
    print("=" * 60)
    funded_df, s1 = engine.run_budget_scenario(15_000_000)
    for k, v in s1.summary_metrics.items():
        print(f"  {k:40s}: {v:>12}")

    print("\n" + "=" * 60)
    print("SCENARIO 2: Weight Sensitivity — Break-History-First")
    print("=" * 60)
    break_weights = {
        "condition_severity": 0.20,
        "break_history":      0.35,
        "capacity_stress":    0.15,
        "criticality":        0.15,
        "material_risk":      0.10,
        "age_factor":         0.05,
    }
    _, s2 = engine.run_weight_scenario(break_weights, label="Break-History-Driven")
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
