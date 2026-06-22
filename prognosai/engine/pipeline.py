"""
engine/pipeline.py
Main orchestrator — single entry point called by Flask.

Runs the full PrognosAI pipeline:
  1. Build disease DAG (adjusted for patient habits + diagnosed conditions)
  2. Kahn's topological sort
  3. DAG DP — find worst-case cascade path
  4. 0/1 Knapsack + Greedy — find optimal intervention bundle
  5. Sensitivity analysis — rank habits by marginal impact
  6. Brute-force benchmark (small subgraph) for complexity demo

Returns one clean JSON-serializable result object.
"""

import time

from .dag import build_dag
from .topological import topological_sort
from .risk_engine import run_risk_dp, run_brute_force
from .knapsack import solve as knapsack_solve
from .sensitivity import analyze as sensitivity_analyze


def run(patient: dict) -> dict:
    """
    Execute the full PrognosAI pipeline for one patient.
    Returns a dict ready to be JSON-serialized and sent to the frontend.
    """
    t_total = time.perf_counter()

    habits = patient.get("habits", {})
    existing_conditions = patient.get("existingConditions", "none")
    budget = int(patient.get("budget", 20))
    budget = max(5, min(50, budget))  # clamp to safe range

    # Step 1: Build disease DAG
    dag = build_dag(habits, existing_conditions)
    graph_data = dag.to_serializable()

    # Step 2: Topological sort (Kahn's algorithm)
    topo_order = topological_sort(dag)

    # Step 3: DAG DP — risk propagation (Engine 1)
    risk_result = run_risk_dp(dag, topo_order)

    # Step 4: Knapsack optimizer (Engine 2)
    knapsack_result = knapsack_solve(budget, risk_result["worst_path"])

    # Step 5: Sensitivity analysis
    sensitivity_result = sensitivity_analyze(habits, risk_result["peak_risk"], existing_conditions)

    # Step 6: Brute-force benchmark (for complexity comparison chart)
    bf_result = run_brute_force(dag, max_nodes=18)

    # Annotate graph nodes with risk scores for visualization
    worst_path_set = set(risk_result["worst_path"])
    node_annotations = {}
    for node_id in dag.get_all_node_ids():
        node_annotations[node_id] = {
            "dp_score": round(risk_result["dp"].get(node_id, 0.0), 4),
            "on_worst_path": node_id in worst_path_set,
            "path_edge_risk": round(risk_result["node_risk"].get(node_id, 0.0), 4),
            "label": dag.get_node_label(node_id),
            "category": dag.get_node_category(node_id),
        }

    total_runtime_ms = round((time.perf_counter() - t_total) * 1000, 2)

    return {
        "graph": graph_data,
        "node_annotations": node_annotations,

        "engine1": {
            "topo_order": topo_order,
            "worst_path": risk_result["worst_path"],
            "worst_path_labels": [dag.get_node_label(n) for n in risk_result["worst_path"]],
            "peak_risk": risk_result["peak_risk"],
            "dp_scores": {k: round(v, 4) for k, v in risk_result["dp"].items()},
            "runtime_ms": risk_result["runtime_ms"],
            "no_risk": risk_result.get("no_risk", False),
        },

        "engine2": {
            "budget": budget,
            "dp": {
                "selected": knapsack_result["dp"]["selected"],
                "total_reduction": knapsack_result["dp"]["total_reduction"],
                "cost_used": knapsack_result["dp"]["cost_used"],
                "runtime_ms": knapsack_result["dp"]["runtime_ms"],
            },
            "greedy": {
                "selected": knapsack_result["greedy"]["selected"],
                "total_reduction": knapsack_result["greedy"]["total_reduction"],
                "cost_used": knapsack_result["greedy"]["cost_used"],
                "runtime_ms": knapsack_result["greedy"]["runtime_ms"],
            },
            "gap": knapsack_result["gap"],
            "greedy_is_optimal": knapsack_result["greedy_is_optimal"],
            "no_interventions": knapsack_result.get("no_interventions", False),
        },

        "sensitivity": sensitivity_result,

        "benchmarks": {
            "dp_runtime_ms": risk_result["runtime_ms"],
            "brute_force_runtime_ms": bf_result["runtime_ms"],
            "brute_force_paths_checked": bf_result["paths_checked"],
            "knapsack_dp_runtime_ms": knapsack_result["dp"]["runtime_ms"],
            "knapsack_greedy_runtime_ms": knapsack_result["greedy"]["runtime_ms"],
        },

        "patient": patient,
        "total_runtime_ms": total_runtime_ms,
    }