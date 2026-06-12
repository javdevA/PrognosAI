"""
engine/knapsack.py
Intervention optimizer — Engine 2.

Two solvers:
  1. Greedy  : O(n log n) — sorts by value/cost ratio, picks greedily.
               Fast but provably suboptimal for 0/1 knapsack.
  2. DP      : O(n * W)  — exact 0/1 knapsack DP, finds true optimum.

The greedy counterexample is deliberately constructable with our data:
a high-ratio but low-absolute-value item can block budget needed for
a higher-value combination that DP correctly identifies.
"""

import json
import os
import time
from copy import deepcopy

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "interventions.json")


def load_interventions() -> list:
    with open(DATA_PATH, "r") as f:
        return json.load(f)["interventions"]


def validate_dependencies(selected_ids: list, all_interventions: list) -> bool:
    """
    Checks that all required prerequisites are satisfied in selected_ids.
    Returns True if valid, False if a dependency is missing.
    """
    selected_set = set(selected_ids)
    id_map = {item["id"]: item for item in all_interventions}
    for sid in selected_ids:
        item = id_map.get(sid, {})
        for req in item.get("requires", []):
            if req not in selected_set:
                return False
    return True


def filter_valid_candidates(interventions: list) -> list:
    """
    Returns only interventions whose dependencies can be satisfied
    (i.e., their required items exist in the catalog).
    """
    all_ids = {item["id"] for item in interventions}
    valid = []
    for item in interventions:
        if all(req in all_ids for req in item.get("requires", [])):
            valid.append(item)
    return valid


def greedy_solve(interventions: list, budget: int, worst_path: list) -> dict:
    """
    Greedy 0/1 knapsack: sort by risk_reduction/cost, pick greedily.

    Complexity: O(n log n) for sorting + O(n) for selection = O(n log n)

    Returns dict with selected interventions, total risk reduction, runtime.
    """
    t_start = time.perf_counter()

    # Score interventions by path relevance + density
    path_set = set(worst_path)
    scored = []
    for item in interventions:
        # Boost score if intervention targets edges on the worst cascade path
        path_relevance = sum(
            1 for t in item.get("targets", [])
            if any(n in t for n in path_set)
        )
        density = (item["risk_reduction"] + 0.1 * path_relevance) / item["cost"]
        scored.append((density, item))

    scored.sort(key=lambda x: -x[0])

    selected = []
    remaining_budget = budget
    selected_ids = []

    for density, item in scored:
        if item["cost"] <= remaining_budget:
            # Check dependency requirements
            all_reqs_met = all(req in selected_ids for req in item.get("requires", []))
            if all_reqs_met:
                selected.append(item)
                selected_ids.append(item["id"])
                remaining_budget -= item["cost"]

    total_reduction = sum(item["risk_reduction"] for item in selected)
    runtime_ms = (time.perf_counter() - t_start) * 1000

    return {
        "selected": selected,
        "selected_ids": selected_ids,
        "total_reduction": round(total_reduction, 4),
        "cost_used": budget - remaining_budget,
        "runtime_ms": round(runtime_ms, 4),
    }


def dp_solve(interventions: list, budget: int, worst_path: list) -> dict:
    """
    Exact 0/1 knapsack DP.

    dp[i][w] = max risk_reduction achievable using first i items with budget w.

    Complexity: O(n * W)
      n = number of interventions (~20)
      W = budget (e.g. 20-50 effort units)

    Returns dict with selected interventions, total risk reduction, DP table, runtime.
    """
    t_start = time.perf_counter()

    n = len(interventions)
    W = budget

    # Build DP table: (n+1) x (W+1)
    dp_table = [[0.0] * (W + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        item = interventions[i - 1]
        cost = item["cost"]
        value = item["risk_reduction"]

        for w in range(W + 1):
            # Option A: skip item i
            dp_table[i][w] = dp_table[i - 1][w]

            # Option B: take item i (if it fits)
            if cost <= w:
                candidate = dp_table[i - 1][w - cost] + value
                if candidate > dp_table[i][w]:
                    dp_table[i][w] = candidate

    # Backtrack to find selected items
    selected_ids = []
    w = W
    for i in range(n, 0, -1):
        if dp_table[i][w] != dp_table[i - 1][w]:
            selected_ids.append(interventions[i - 1]["id"])
            w -= interventions[i - 1]["cost"]

    selected_ids.reverse()

    # Validate dependency constraints — remove violators
    id_map = {item["id"]: item for item in interventions}
    valid_selected = []
    confirmed_ids = []
    for sid in selected_ids:
        item = id_map[sid]
        if all(req in confirmed_ids for req in item.get("requires", [])):
            valid_selected.append(item)
            confirmed_ids.append(sid)

    total_reduction = sum(item["risk_reduction"] for item in valid_selected)
    cost_used = sum(item["cost"] for item in valid_selected)
    runtime_ms = (time.perf_counter() - t_start) * 1000

    # Serialize DP table sample (first 5 rows x first 15 cols) for visualization
    dp_sample = [row[:min(15, W + 1)] for row in dp_table[:min(6, n + 1)]]

    return {
        "selected": valid_selected,
        "selected_ids": confirmed_ids,
        "total_reduction": round(total_reduction, 4),
        "cost_used": cost_used,
        "dp_table_sample": [[round(v, 3) for v in row] for row in dp_sample],
        "runtime_ms": round(runtime_ms, 4),
    }


def solve(budget: int, worst_path: list) -> dict:
    """
    Main entry point for Engine 2.
    Runs both greedy and DP, returns comparison.
    """
    interventions = load_interventions()
    valid = filter_valid_candidates(interventions)

    greedy_result = greedy_solve(valid, budget, worst_path)
    dp_result = dp_solve(valid, budget, worst_path)

    # Compute difference to highlight where greedy suboptimal
    gap = round(dp_result["total_reduction"] - greedy_result["total_reduction"], 4)
    greedy_optimal = gap <= 0.001

    return {
        "greedy": greedy_result,
        "dp": dp_result,
        "gap": gap,
        "greedy_is_optimal": greedy_optimal,
        "budget": budget,
        "all_interventions": valid,
    }
