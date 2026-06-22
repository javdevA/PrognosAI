"""
engine/risk_engine.py
DAG Dynamic Programming — finds the maximum cumulative risk cascade path.

Cascade origin selection rule:
  A node can ONLY start a cascade if dag.is_origin[node] is True.
  Origins are either active lifestyle habits or diagnosed conditions.
  This prevents healthy patients from showing phantom cascades.

If no origins exist (perfectly healthy patient, no diagnoses),
the result is an empty cascade with risk 0.0 — medically correct.

Complexity: O(V + E)
"""

import time


def run_risk_dp(dag, topo_order: list) -> dict:
    t_start = time.perf_counter()
    all_nodes = dag.get_all_node_ids()

    dp = {node: 0.0 for node in all_nodes}
    predecessor = {node: None for node in all_nodes}

    # DP in reverse topological order
    for u in reversed(topo_order):
        best_score = 0.0
        best_next = None
        for v, prob in dag.neighbors(u):
            candidate = prob + dp[v]
            if candidate > best_score:
                best_score = candidate
                best_next = v
        dp[u] = best_score
        predecessor[u] = best_next

    # Cascade can only originate from legitimate origin nodes
    origin_nodes = [n for n in all_nodes if dag.is_origin.get(n, False)]

    # Healthy patient with no origins -> no cascade
    if not origin_nodes:
        runtime_ms = (time.perf_counter() - t_start) * 1000
        return {
            "dp": dp,
            "predecessors": predecessor,
            "node_risk": {},
            "worst_path": [],
            "peak_risk": 0.0,
            "runtime_ms": round(runtime_ms, 4),
            "no_risk": True,
        }

    def node_score(n):
        activation = dag.node_activation.get(n, 1.0)
        return dp[n] * activation

    peak_node = max(origin_nodes, key=node_score)
    peak_risk = round(dp[peak_node] * dag.node_activation.get(peak_node, 1.0), 4)

    # Reconstruct path
    worst_path = []
    current = peak_node
    visited = set()
    while current is not None and current not in visited:
        worst_path.append(current)
        visited.add(current)
        current = predecessor[current]

    node_risk = {}
    for i in range(len(worst_path)):
        if i == 0:
            node_risk[worst_path[i]] = 0.0
        else:
            prev = worst_path[i - 1]
            curr = worst_path[i]
            for neighbor, prob in dag.neighbors(prev):
                if neighbor == curr:
                    node_risk[curr] = prob
                    break

    runtime_ms = (time.perf_counter() - t_start) * 1000

    return {
        "dp": dp,
        "predecessors": predecessor,
        "node_risk": node_risk,
        "worst_path": worst_path,
        "peak_risk": peak_risk,
        "runtime_ms": round(runtime_ms, 4),
        "no_risk": False,
    }


def run_brute_force(dag, max_nodes: int = 20) -> dict:
    t_start = time.perf_counter()
    all_nodes = dag.get_all_node_ids()[:max_nodes]
    node_set = set(all_nodes)

    local_adj = {}
    for n in all_nodes:
        local_adj[n] = [(v, p) for v, p in dag.neighbors(n) if v in node_set]

    best_risk = 0.0
    paths_checked = [0]

    def dfs(node, current_risk, visited):
        paths_checked[0] += 1
        best = current_risk
        for neighbor, prob in local_adj.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                result = dfs(neighbor, current_risk + prob, visited)
                best = max(best, result)
                visited.discard(neighbor)
        return best

    for start in all_nodes:
        if dag.is_origin.get(start, False):
            r = dfs(start, 0.0, {start})
            best_risk = max(best_risk, r)

    runtime_ms = (time.perf_counter() - t_start) * 1000
    return {
        "best_risk": round(best_risk, 4),
        "paths_checked": paths_checked[0],
        "runtime_ms": round(runtime_ms, 4),
    }