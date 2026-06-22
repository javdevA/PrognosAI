"""
engine/dag.py
Builds and manages the disease Directed Acyclic Graph.

Medical model — a cascade can only ORIGINATE from:
  1. An active lifestyle habit (smoking, poor diet, sedentary, etc.)
  2. A diagnosed existing condition (from the intake form)

Intermediate conditions, diseases, and severe outcomes are CONSEQUENCES.
They can only appear in a cascade if a path reaches them from a valid
origin. They are never spontaneous starting points.

A fully healthy patient with no diagnosed conditions therefore shows
near-zero risk — which is the medically correct result.
"""

import json
import os
from collections import defaultdict

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "diseases.json")

# Maps each lifestyle habit to the root node it controls
HABIT_NODE_MAP = {
    "smoking":  "smoking",
    "exercise": "sedentary",
    "diet":     "poor_diet",
    "alcohol":  "alcohol",
    "bmi":      "obesity",
    "sleep":    "sleep_apnea",
}

# Maps the "existing conditions" form value to the condition node(s)
# it activates as a diagnosed starting point.
EXISTING_CONDITION_MAP = {
    "none":             [],
    "hypertension":     ["hypertension"],
    "diabetes":         ["t2_diabetes"],
    "high-cholesterol": ["high_cholesterol"],
    "multiple":         ["hypertension", "high_cholesterol", "insulin_resist"],
}


class DiseaseDAG:
    def __init__(self):
        self.nodes = {}
        self.adjacency = defaultdict(list)
        self.reverse_adj = defaultdict(list)
        self.node_activation = {}
        # Tracks which nodes are LEGITIMATE cascade origins
        self.is_origin = {}
        self._raw_data = None
        self._load()

    def _load(self):
        with open(DATA_PATH, "r") as f:
            self._raw_data = json.load(f)
        for node in self._raw_data["nodes"]:
            self.nodes[node["id"]] = node
            self.node_activation[node["id"]] = 1.0
            self.is_origin[node["id"]] = False
        for edge in self._raw_data["edges"]:
            src, dst, prob = edge["from"], edge["to"], edge["base_prob"]
            self.adjacency[src].append([dst, prob])
            self.reverse_adj[dst].append(src)

    def apply_patient(self, habits: dict, existing_conditions: str = "none") -> None:
        """
        Configure the DAG for a specific patient.

        habits: dict of habit_key -> level (0.0 worst .. 1.0 healthy)
        existing_conditions: form value identifying diagnosed conditions
        """
        modifiers = self._raw_data.get("habit_edge_modifiers", {})

        # Reset
        self.adjacency = defaultdict(list)
        self.reverse_adj = defaultdict(list)
        self.node_activation = {n: 1.0 for n in self.nodes}
        self.is_origin = {n: False for n in self.nodes}

        # Load base edge probabilities
        edge_map = {}
        for edge in self._raw_data["edges"]:
            key = f"{edge['from']}->{edge['to']}"
            edge_map[key] = edge["base_prob"]

        # 1. Apply edge weight reductions from habit improvements
        for habit_key, level in habits.items():
            if habit_key not in modifiers or level <= 0.0:
                continue
            mod = modifiers[habit_key]
            factor = mod["reduction_factor"]
            for edge_key in mod["edges"]:
                if edge_key in edge_map:
                    base = edge_map[edge_key]
                    edge_map[edge_key] = base * (1.0 - level * (1.0 - factor))

        # 2. Habit root nodes: activation = how unhealthy the habit is.
        #    A habit slider at 1.0 (healthy) -> activation 0.0 (not an origin).
        #    A habit slider at 0.0 (worst)   -> activation 1.0 (strong origin).
        for habit_key, node_id in HABIT_NODE_MAP.items():
            level = habits.get(habit_key, 0.0)
            unhealthiness = max(0.0, 1.0 - level)
            self.node_activation[node_id] = unhealthiness
            # An active habit node is a legitimate cascade origin
            if unhealthiness > 0.05:
                self.is_origin[node_id] = True

        # 3. Diagnosed conditions: marked as legitimate origins at full strength
        diagnosed = EXISTING_CONDITION_MAP.get(existing_conditions, [])
        for node_id in diagnosed:
            if node_id in self.node_activation:
                self.node_activation[node_id] = 1.0
                self.is_origin[node_id] = True

        # 4. Rebuild adjacency with effective probabilities
        #    (edge weight × source node activation)
        for key, prob in edge_map.items():
            src, dst = key.split("->")
            activation = self.node_activation.get(src, 1.0)
            effective_prob = prob * activation
            self.adjacency[src].append([dst, effective_prob])
            self.reverse_adj[dst].append(src)

    def get_all_node_ids(self):
        return list(self.nodes.keys())

    def get_node_label(self, node_id):
        return self.nodes.get(node_id, {}).get("label", node_id)

    def get_node_category(self, node_id):
        return self.nodes.get(node_id, {}).get("category", "unknown")

    def neighbors(self, node_id):
        return self.adjacency.get(node_id, [])

    def in_degree(self, node_id):
        return len(self.reverse_adj.get(node_id, []))

    def to_serializable(self):
        nodes_out = []
        for nid, meta in self.nodes.items():
            nodes_out.append({
                "id": nid,
                "label": meta["label"],
                "category": meta["category"],
                "activation": round(self.node_activation.get(nid, 1.0), 3),
                "is_origin": self.is_origin.get(nid, False),
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


def build_dag(habits: dict = None, existing_conditions: str = "none") -> DiseaseDAG:
    dag = DiseaseDAG()
    if habits is not None:
        dag.apply_patient(habits, existing_conditions)
    return dag