"""
engine/pipeline.py
Main orchestrator — single entry point called by Flask.

Full PrognosAI pipeline:
  1. Build disease DAG adjusted for patient habits + diagnosed conditions
  2. Kahn's topological sort  — O(V+E)
  3. DAG DP heaviest path     — O(V+E)  [Engine 1]
  4. 0/1 Knapsack + Greedy   — O(n*W)  [Engine 2]
  5. Sensitivity analysis     — O(k*(V+E))
  6. Brute-force benchmark    — O(2^V subset, limited to 18 nodes)

Returns one fully-safe JSON-serializable result dict.
"""

import time

from .dag import build_dag
from .topological import topological_sort
from .risk_engine import run_risk_dp, run_brute_force
from .knapsack import solve as knapsack_solve
from .sensitivity import analyze as sensitivity_analyze


def run(patient: dict) -> dict:
    t_total = time.perf_counter()

    # ── Parse patient input safely ────────────────────────────────────────────
    raw_habits = patient.get("habits", {})
    habits = {}
    for key in ["smoking", "exercise", "diet", "alcohol", "bmi", "sleep"]:
        val = float(raw_habits.get(key, 0.0))
        habits[key] = max(0.0, min(1.0, val))

    existing_conditions = str(patient.get("existingConditions", "none")).strip().lower()
    budget = int(patient.get("budget", 15))
    budget = max(3, min(50, budget))

    # ── Step 1: Build DAG ─────────────────────────────────────────────────────
    dag = build_dag(habits, existing_conditions)
    graph_data = dag.to_serializable()

    # ── Step 2: Topological sort ──────────────────────────────────────────────
    topo_order = topological_sort(dag)

    # ── Step 3: DAG DP (Engine 1) ─────────────────────────────────────────────
    risk_result = run_risk_dp(dag, topo_order)
    worst_path  = risk_result["worst_path"]
    peak_risk   = risk_result["peak_risk"]
    no_risk     = risk_result.get("no_risk", False)

    # ── Step 4: Knapsack (Engine 2) ───────────────────────────────────────────
    knapsack_result = knapsack_solve(budget, worst_path)

    kn_dp     = knapsack_result["dp"]
    kn_greedy = knapsack_result["greedy"]

    # ── Step 5: Sensitivity analysis ──────────────────────────────────────────
    sensitivity_result = sensitivity_analyze(habits, peak_risk, existing_conditions)

    # ── Step 6: Brute-force benchmark ─────────────────────────────────────────
    bf_result = run_brute_force(dag, max_nodes=18)

    # ── Annotate every node for D3 visualization ──────────────────────────────
    worst_path_set = set(worst_path)
    node_annotations = {}
    for node_id in dag.get_all_node_ids():
        node_annotations[node_id] = {
            "dp_score":       round(risk_result["dp"].get(node_id, 0.0), 4),
            "on_worst_path":  node_id in worst_path_set,
            "path_edge_risk": round(risk_result["node_risk"].get(node_id, 0.0), 4),
            "label":          dag.get_node_label(node_id),
            "category":       dag.get_node_category(node_id),
            "is_origin":      dag.is_origin.get(node_id, False),
        }

    total_runtime_ms = round((time.perf_counter() - t_total) * 1000, 2)

    return {
        "graph":            graph_data,
        "node_annotations": node_annotations,

        "engine1": {
            "topo_order":        topo_order,
            "worst_path":        worst_path,
            "worst_path_labels": [dag.get_node_label(n) for n in worst_path],
            "peak_risk":         peak_risk,
            "dp_scores":         {k: round(v, 4) for k, v in risk_result["dp"].items()},
            "runtime_ms":        risk_result["runtime_ms"],
            "no_risk":           no_risk,
        },

        "engine2": {
            "budget":            budget,
            "no_interventions":  knapsack_result.get("no_interventions", False),
            "candidate_count":   knapsack_result.get("candidate_count", 0),
            "gap":               knapsack_result["gap"],
            "greedy_is_optimal": knapsack_result["greedy_is_optimal"],
            "dp": {
                "selected":        kn_dp["selected"],
                "total_reduction": kn_dp["total_reduction"],
                "cost_used":       kn_dp["cost_used"],
                "runtime_ms":      kn_dp["runtime_ms"],
            },
            "greedy": {
                "selected":        kn_greedy["selected"],
                "total_reduction": kn_greedy["total_reduction"],
                "cost_used":       kn_greedy["cost_used"],
                "runtime_ms":      kn_greedy["runtime_ms"],
            },
        },

        "sensitivity": sensitivity_result,

        "benchmarks": {
            "dp_runtime_ms":              risk_result["runtime_ms"],
            "brute_force_runtime_ms":     bf_result["runtime_ms"],
            "brute_force_paths_checked":  bf_result["paths_checked"],
            "knapsack_dp_runtime_ms":     kn_dp["runtime_ms"],
            "knapsack_greedy_runtime_ms": kn_greedy["runtime_ms"],
        },

        "patient":          patient,
        "total_runtime_ms": total_runtime_ms,
    }