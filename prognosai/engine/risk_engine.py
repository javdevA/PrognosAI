"""
engine/risk_engine.py
DAG Dynamic Programming — finds the highest-risk cascade path.

Complexity: O(V + E)
  Processes each node exactly once (in topological order),
  and examines each edge exactly once during relaxation.

Compared to brute-force path enumeration: O(2^V) — exponential.
"""

import time


def run_risk_dp(dag, topo_order: list) -> dict:
    """
    Runs DP on the disease DAG to find the maximum cumulative risk path.

    For each node u (processed in topological order):
        dp[u] = max over all outgoing edges (u -> v):
                    edge_prob(u, v) + dp[v]

    Predecessor tracking enables full path reconstruction.

    Args:
        dag        : DiseaseDAG instance
        topo_order : list of node IDs in topological order

    Returns dict with:
        dp           : {node_id: max_risk_score}
        predecessors : {node_id: best_predecessor_id or None}
        node_risk    : {node_id: own risk contribution}
        worst_path   : list of node IDs on the highest-risk cascade
        peak_risk    : float, total risk score of worst path
        runtime_ms   : float
    """
    t_start = time.perf_counter()

    all_nodes = dag.get_all_node_ids()

    # Initialize DP table and predecessor map
    dp = {node: 0.0 for node in all_nodes}
    predecessor = {node: None for node in all_nodes}

    # Process nodes in REVERSE topological order
    # (so when we process u, all nodes reachable from u are already solved)
    for u in reversed(topo_order):
        best_next_score = 0.0
        best_next_node = None

        for v, prob in dag.neighbors(u):
            candidate = prob + dp[v]
            if candidate > best_next_score:
                best_next_score = candidate
                best_next_node = v

        dp[u] = best_next_score
        predecessor[u] = best_next_node

    # Find the starting node with the highest dp score
    # (among nodes that are habit/risk sources)
    source_categories = {"habit_risk", "condition"}
    source_nodes = [
        n for n in all_nodes
        if dag.get_node_category(n) in source_categories
    ]

    peak_node = max(source_nodes, key=lambda n: dp[n])
    peak_risk = dp[peak_node]

    # Reconstruct worst path by following predecessor chain
    worst_path = []
    current = peak_node
    visited = set()
    while current is not None and current not in visited:
        worst_path.append(current)
        visited.add(current)
        current = predecessor[current]

    # Per-node risk contribution = the edge probability leading into it
    # (useful for coloring nodes in the visualization)
    node_risk = {}
    for i in range(len(worst_path)):
        if i == 0:
            node_risk[worst_path[i]] = 0.0  # source has no incoming edge on path
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
        "peak_risk": round(peak_risk, 4),
        "runtime_ms": round(runtime_ms, 4),
    }


def run_brute_force(dag, max_nodes: int = 20) -> dict:
    """
    Brute-force path enumeration for complexity comparison demo.
    Only runs on a subgraph of up to max_nodes to keep it feasible.

    Complexity: O(2^V) — exponential. Used only for benchmarking.
    Returns: best_risk (float), paths_checked (int), runtime_ms (float)
    """
    t_start = time.perf_counter()
    all_nodes = dag.get_all_node_ids()[:max_nodes]
    node_set = set(all_nodes)

    # Build local adjacency restricted to subset
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
        r = dfs(start, 0.0, {start})
        best_risk = max(best_risk, r)

    runtime_ms = (time.perf_counter() - t_start) * 1000

    return {
        "best_risk": round(best_risk, 4),
        "paths_checked": paths_checked[0],
        "runtime_ms": round(runtime_ms, 4),
    }
