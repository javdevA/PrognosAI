"""
engine/knapsack.py
Intervention optimizer — Engine 2.

Two solvers:
  1. Greedy : O(n log n) — sort by risk_reduction/cost ratio, pick greedily.
              Fast but provably suboptimal for 0/1 knapsack in general.
  2. DP     : O(n * W)  — exact 0/1 knapsack DP. Always finds true optimum.

CANDIDATE FILTERING:
  Only interventions whose targets overlap with edges on the patient's
  cascade path are eligible. This ensures every recommendation is
  clinically relevant to THIS patient's specific disease chain.
"""

import json
import os
import time

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "interventions.json")

EPSILON = 1e-9  # floating point tolerance for DP backtracking


def load_interventions() -> list:
    with open(DATA_PATH, "r") as f:
        return json.load(f)["interventions"]


def path_to_edges(worst_path: list) -> set:
    """
    Convert a node path [a, b, c, d] to edge strings {"a->b", "b->c", "c->d"}.
    """
    edges = set()
    for i in range(len(worst_path) - 1):
        edges.add(f"{worst_path[i]}->{worst_path[i + 1]}")
    return edges


def filter_relevant_interventions(interventions: list, path_edges: set) -> list:
    """
    Return interventions whose targets overlap with cascade path edges.
    Also include any required prerequisites of relevant items transitively.
    Deduplicates results.
    """
    id_map = {item["id"]: item for item in interventions}
    relevant_ids = set()

    # First pass: direct relevance
    for item in interventions:
        targets = set(item.get("targets", []))
        if targets & path_edges:
            relevant_ids.add(item["id"])

    # Second pass: pull in all prerequisites transitively
    changed = True
    while changed:
        changed = False
        for rid in list(relevant_ids):
            item = id_map.get(rid, {})
            for req in item.get("requires", []):
                if req not in relevant_ids and req in id_map:
                    relevant_ids.add(req)
                    changed = True

    # Return in original order, deduplicated
    seen = set()
    result = []
    for item in interventions:
        if item["id"] in relevant_ids and item["id"] not in seen:
            result.append(item)
            seen.add(item["id"])
    return result


def _empty_result(budget: int) -> dict:
    """Standard empty result when no interventions apply."""
    return {
        "greedy": {
            "selected": [], "selected_ids": [],
            "total_reduction": 0.0, "cost_used": 0, "runtime_ms": 0.0,
        },
        "dp": {
            "selected": [], "selected_ids": [],
            "total_reduction": 0.0, "cost_used": 0,
            "runtime_ms": 0.0, "dp_table_sample": [],
        },
        "gap": 0.0,
        "greedy_is_optimal": True,
        "budget": budget,
        "candidate_count": 0,
        "no_interventions": True,
    }


def greedy_solve(interventions: list, budget: int) -> dict:
    """
    Greedy 0/1 knapsack.
    Sort by risk_reduction / cost (density), pick highest-density items first.
    Respects dependency constraints.
    Complexity: O(n log n)
    """
    t_start = time.perf_counter()

    sorted_items = sorted(
        interventions,
        key=lambda x: x["risk_reduction"] / x["cost"],
        reverse=True
    )

    selected = []
    selected_ids = []
    remaining = budget

    for item in sorted_items:
        if item["cost"] <= remaining:
            reqs_ok = all(req in selected_ids for req in item.get("requires", []))
            if reqs_ok:
                selected.append(item)
                selected_ids.append(item["id"])
                remaining -= item["cost"]

    total_reduction = sum(i["risk_reduction"] for i in selected)
    runtime_ms = (time.perf_counter() - t_start) * 1000

    return {
        "selected": selected,
        "selected_ids": selected_ids,
        "total_reduction": round(total_reduction, 4),
        "cost_used": budget - remaining,
        "runtime_ms": round(runtime_ms, 4),
    }


def dp_solve(interventions: list, budget: int) -> dict:
    """
    Exact 0/1 Knapsack DP.
    dp[i][w] = maximum risk reduction using first i interventions within budget w.
    Complexity: O(n * W)

    Uses epsilon comparison in backtracking to avoid floating point errors.
    Dependency constraints enforced after backtracking.
    """
    t_start = time.perf_counter()

    n = len(interventions)
    W = budget

    # Build DP table
    dp_table = [[0.0] * (W + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        cost  = interventions[i - 1]["cost"]
        value = interventions[i - 1]["risk_reduction"]
        for w in range(W + 1):
            dp_table[i][w] = dp_table[i - 1][w]
            if cost <= w:
                candidate = dp_table[i - 1][w - cost] + value
                if candidate > dp_table[i][w] + EPSILON:
                    dp_table[i][w] = candidate

    # Backtrack with epsilon tolerance
    selected_ids = []
    w = W
    for i in range(n, 0, -1):
        if dp_table[i][w] > dp_table[i - 1][w] + EPSILON:
            selected_ids.append(interventions[i - 1]["id"])
            w -= interventions[i - 1]["cost"]
    selected_ids.reverse()

    # Enforce dependency ordering
    id_map = {item["id"]: item for item in interventions}
    valid_selected = []
    confirmed_ids = []
    for sid in selected_ids:
        if sid not in id_map:
            continue
        item = id_map[sid]
        reqs_ok = all(req in confirmed_ids for req in item.get("requires", []))
        if reqs_ok:
            valid_selected.append(item)
            confirmed_ids.append(sid)

    total_reduction = sum(i["risk_reduction"] for i in valid_selected)
    cost_used = sum(i["cost"] for i in valid_selected)
    runtime_ms = (time.perf_counter() - t_start) * 1000

    dp_sample = [
        [round(v, 3) for v in row[:min(15, W + 1)]]
        for row in dp_table[:min(6, n + 1)]
    ]

    return {
        "selected": valid_selected,
        "selected_ids": confirmed_ids,
        "total_reduction": round(total_reduction, 4),
        "cost_used": cost_used,
        "dp_table_sample": dp_sample,
        "runtime_ms": round(runtime_ms, 4),
    }


def solve(budget: int, worst_path: list) -> dict:
    """
    Engine 2 entry point.

    1. Convert cascade path to directed edge set.
    2. Filter interventions to those relevant to those edges.
    3. Run greedy and exact DP.
    4. Return both results with the gap for comparison.
    """
    if not worst_path or len(worst_path) < 2:
        return _empty_result(budget)

    interventions = load_interventions()
    path_edges = path_to_edges(worst_path)

    relevant = filter_relevant_interventions(interventions, path_edges)

    if not relevant:
        return _empty_result(budget)

    greedy_result = greedy_solve(relevant, budget)
    dp_result     = dp_solve(relevant, budget)

    gap = round(dp_result["total_reduction"] - greedy_result["total_reduction"], 4)
    greedy_is_optimal = abs(gap) <= 0.001

    return {
        "greedy": greedy_result,
        "dp":     dp_result,
        "gap":    gap,
        "greedy_is_optimal": greedy_is_optimal,
        "budget": budget,
        "candidate_count": len(relevant),
        "no_interventions": False,
    }