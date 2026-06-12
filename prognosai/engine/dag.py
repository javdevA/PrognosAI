"""
engine/dag.py
Builds and manages the disease Directed Acyclic Graph.
Loads disease nodes and edges from data/diseases.json.
Adjusts edge weights based on the patient's habit improvement inputs.
"""

import json
import os
from collections import defaultdict


DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "diseases.json")


class DiseaseDAG:
    """
    Represents the disease network as a weighted directed acyclic graph.

    Attributes:
        nodes       : dict  {node_id: node_metadata}
        adjacency   : dict  {from_id: [(to_id, probability)]}
        reverse_adj : dict  {to_id: [from_id]}  — used by Kahn's algorithm
    """

    def __init__(self):
        self.nodes = {}
        self.adjacency = defaultdict(list)     # from -> [(to, prob)]
        self.reverse_adj = defaultdict(list)   # to   -> [from]
        self._raw_data = None
        self._load()

    def _load(self):
        with open(DATA_PATH, "r") as f:
            self._raw_data = json.load(f)

        for node in self._raw_data["nodes"]:
            self.nodes[node["id"]] = node

        for edge in self._raw_data["edges"]:
            src, dst, prob = edge["from"], edge["to"], edge["base_prob"]
            self.adjacency[src].append([dst, prob])
            self.reverse_adj[dst].append(src)

    def apply_habit_modifiers(self, habits: dict) -> None:
        """
        Reduce edge weights based on the patient's habit improvement levels.

        habits: dict mapping habit keys to improvement levels (0.0 = no change, 1.0 = full improvement)
          keys: "smoking", "exercise", "diet", "alcohol", "bmi", "sleep"

        For each habit, the edges it affects are scaled down proportionally.
        The reduction formula:
            new_prob = base_prob * (1 - level * (1 - reduction_factor))
        where reduction_factor is defined per habit in diseases.json.
        """
        modifiers = self._raw_data.get("habit_edge_modifiers", {})

        # Rebuild adjacency from base to allow repeated calls
        self.adjacency = defaultdict(list)
        self.reverse_adj = defaultdict(list)

        # Load base edges
        edge_map = {}  # "from->to" -> current probability
        for edge in self._raw_data["edges"]:
            key = f"{edge['from']}->{edge['to']}"
            edge_map[key] = edge["base_prob"]

        # Apply modifiers
        for habit_key, level in habits.items():
            if habit_key not in modifiers or level <= 0.0:
                continue
            mod = modifiers[habit_key]
            factor = mod["reduction_factor"]
            for edge_key in mod["edges"]:
                if edge_key in edge_map:
                    base = edge_map[edge_key]
                    # Reduction scales linearly with improvement level
                    edge_map[edge_key] = base * (1.0 - level * (1.0 - factor))

        # Rebuild adjacency with modified probabilities
        for key, prob in edge_map.items():
            src, dst = key.split("->")
            self.adjacency[src].append([dst, prob])
            self.reverse_adj[dst].append(src)

    def get_all_node_ids(self) -> list:
        return list(self.nodes.keys())

    def get_node_label(self, node_id: str) -> str:
        return self.nodes.get(node_id, {}).get("label", node_id)

    def get_node_category(self, node_id: str) -> str:
        return self.nodes.get(node_id, {}).get("category", "unknown")

    def neighbors(self, node_id: str) -> list:
        """Returns list of (neighbor_id, probability) tuples."""
        return self.adjacency.get(node_id, [])

    def in_degree(self, node_id: str) -> int:
        return len(self.reverse_adj.get(node_id, []))

    def to_serializable(self) -> dict:
        """Returns a JSON-serializable representation for the frontend."""
        nodes_out = []
        for nid, meta in self.nodes.items():
            nodes_out.append({
                "id": nid,
                "label": meta["label"],
                "category": meta["category"],
            })

        edges_out = []
        for src, neighbors in self.adjacency.items():
            for dst, prob in neighbors:
                edges_out.append({
                    "from": src,
                    "to": dst,
                    "probability": round(prob, 4),
                })

        return {"nodes": nodes_out, "edges": edges_out}


def build_dag(habits: dict = None) -> DiseaseDAG:
    """
    Factory function. Builds a DAG and optionally applies habit modifiers.
    habits: dict of {habit_key: improvement_level (0-1)}
    """
    dag = DiseaseDAG()
    if habits:
        dag.apply_habit_modifiers(habits)
    return dag
