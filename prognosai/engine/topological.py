"""
engine/topological.py
Kahn's algorithm for topological sorting of the disease DAG.

Complexity: O(V + E)
  - V = number of disease nodes (25)
  - E = number of directed edges (~54)

Raises CycleDetectedError if the graph contains a cycle
(would mean a disease can cause itself — invalid for our model).
"""

from collections import deque


class CycleDetectedError(Exception):
    """Raised when Kahn's algorithm detects a cycle in the DAG."""
    pass


def topological_sort(dag) -> list:
    """
    Performs Kahn's topological sort on a DiseaseDAG.

    Algorithm:
      1. Compute in-degree for every node.
      2. Enqueue all nodes with in-degree == 0 (no prerequisites).
      3. While queue is not empty:
           - Dequeue node u, add to sorted order.
           - For each neighbor v of u:
               Decrease in-degree of v by 1.
               If in-degree of v reaches 0, enqueue v.
      4. If sorted order length < total nodes → cycle detected.

    Returns:
        List of node IDs in topological order.
    """
    all_nodes = dag.get_all_node_ids()

    # Step 1: compute in-degree for every node
    in_degree = {node: dag.in_degree(node) for node in all_nodes}

    # Step 2: seed the queue with all zero-in-degree nodes
    queue = deque([node for node in all_nodes if in_degree[node] == 0])

    sorted_order = []

    # Step 3: process
    while queue:
        u = queue.popleft()
        sorted_order.append(u)

        for v, _ in dag.neighbors(u):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    # Step 4: cycle check
    if len(sorted_order) != len(all_nodes):
        cycle_nodes = [n for n in all_nodes if n not in sorted_order]
        raise CycleDetectedError(
            f"Cycle detected in disease DAG — invalid graph. "
            f"Nodes involved: {cycle_nodes}"
        )

    return sorted_order
