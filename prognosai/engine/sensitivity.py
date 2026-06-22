"""
engine/sensitivity.py
Sensitivity analysis — reruns Engine 1 for each habit to measure marginal impact.

Complexity: O(k * (V + E))
  k = number of habits (~6)
  Each rerun is O(V+E) DAG DP.

Returns habits ranked by how much a full improvement reduces the peak risk score.
"""

from .dag import build_dag
from .topological import topological_sort
from .risk_engine import run_risk_dp


HABITS = {
    "smoking":  "Quit Smoking",
    "exercise": "Regular Exercise",
    "diet":     "Healthy Diet",
    "alcohol":  "Reduce Alcohol",
    "bmi":      "Lose Weight",
    "sleep":    "Improve Sleep",
}


def analyze(base_habits: dict, base_peak_risk: float, existing_conditions: str = "none") -> list:
    """
    For each habit key, simulate full improvement (level=1.0) and rerun DP.
    Measures the drop in peak_risk compared to the baseline.
    """
    results = []

    for habit_key, habit_label in HABITS.items():
        baseline_level = base_habits.get(habit_key, 0.0)

        improved_habits = dict(base_habits)
        improved_habits[habit_key] = 1.0

        dag = build_dag(improved_habits, existing_conditions)
        topo_order = topological_sort(dag)
        dp_result = run_risk_dp(dag, topo_order)

        new_risk = dp_result["peak_risk"]
        marginal_reduction = round(base_peak_risk - new_risk, 4)
        pct_improvement = round(
            (marginal_reduction / base_peak_risk * 100) if base_peak_risk > 0 else 0.0,
            1
        )

        results.append({
            "habit_key": habit_key,
            "label": habit_label,
            "baseline_level": baseline_level,
            "new_risk": new_risk,
            "marginal_reduction": marginal_reduction,
            "pct_improvement": pct_improvement,
        })

    results.sort(key=lambda x: -x["marginal_reduction"])
    return results