"""
graph.py - loads data/graph.json and answers simple road questions.

The JSON holds every number the planner uses (distances, drive times,
landslide-risk assumptions, cost weights), so nothing is hard-coded here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_GRAPH = Path(__file__).parent / "data" / "graph.json"


@dataclass(frozen=True)
class Edge:
    """One road stretch. Roads are two-way, so each JSON edge is stored in both directions."""
    src: str
    dst: str
    km: float
    hours: float      # base driving time (approximate)
    risk: float       # ASSUMED daily probability of a blockage
    note: str = ""


class RoadGraph:
    def __init__(self, path: str | Path = DEFAULT_GRAPH):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.meta: dict = raw["_meta"]
        self.coords: dict[str, tuple[float, float]] = {
            n: (v["lon"], v["lat"]) for n, v in raw["nodes"].items()}
        self.nodes: list[str] = list(raw["nodes"])
        self.dhams: dict[str, dict] = raw["dhams"]                       # dham name -> info
        self.dham_nodes: dict[str, str] = {d["node"]: name for name, d in self.dhams.items()}
        self.visit_extra_days: dict[str, int] = {
            d["node"]: int(d["visit_extra_days"]) for d in self.dhams.values()}
        self.season: dict[int, float] = {
            int(k): float(v) for k, v in raw["season_risk_multiplier"].items() if k.isdigit()}
        self.cost_model: dict[str, float] = {
            k: v for k, v in raw["cost_model"].items() if not k.startswith("_")}

        self.adj: dict[str, list[Edge]] = {n: [] for n in self.nodes}
        self.edges: list[Edge] = []
        for e in raw["edges"]:
            fwd = Edge(e["from"], e["to"], e["km"], e["hours"], e["risk"], e.get("note", ""))
            back = Edge(e["to"], e["from"], e["km"], e["hours"], e["risk"], e.get("note", ""))
            self.edges.append(fwd)
            self.adj[fwd.src].append(fwd)
            self.adj[back.src].append(back)

        self._all_pairs()

    def _all_pairs(self) -> None:
        """Floyd-Warshall on BASE driving hours (22 nodes, so this is instant).

        dist[a][b] = fewest base driving hours from a to b.
        nxt[a][b]  = first town on that fastest road (used by the naive baseline).
        """
        inf = float("inf")
        self.dist = {a: {b: (0.0 if a == b else inf) for b in self.nodes} for a in self.nodes}
        self.nxt: dict[str, dict[str, str | None]] = {
            a: {b: None for b in self.nodes} for a in self.nodes}
        for a in self.nodes:
            for e in self.adj[a]:
                if e.hours < self.dist[a][e.dst]:
                    self.dist[a][e.dst] = e.hours
                    self.nxt[a][e.dst] = e.dst
        for k in self.nodes:
            for i in self.nodes:
                dik = self.dist[i][k]
                if dik == inf:
                    continue
                for j in self.nodes:
                    if dik + self.dist[k][j] < self.dist[i][j]:
                        self.dist[i][j] = dik + self.dist[k][j]
                        self.nxt[i][j] = self.nxt[i][k]

    def edge(self, a: str, b: str) -> Edge:
        """The direct road a -> b (raises if the towns are not neighbours)."""
        for e in self.adj[a]:
            if e.dst == b:
                return e
        raise KeyError(f"No direct road {a} -> {b}")

    def shortest_road(self, a: str, b: str) -> list[str]:
        """Town-by-town fastest road from a to b on base hours."""
        path = [a]
        while a != b:
            a = self.nxt[a][b]
            path.append(a)
        return path
