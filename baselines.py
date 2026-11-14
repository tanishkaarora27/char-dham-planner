"""
baselines.py - the algorithms A* is compared against.

dijkstra   same search as A* but with h = 0 (uniform-cost search). It finds the
           same optimal plan, but has no sense of direction, so it expands more.
bfs        breadth-first search: fewest ACTIONS, ignoring cost. Shows why an
           uninformed, cost-blind search gives a poor plan.
naive      what most people do: go to the nearest dham next, always on the
           fastest road, drive as far as the day allows, keep no buffer days.
"""
from __future__ import annotations

import time
from collections import deque

from a_star import SearchResult, a_star, reconstruct
from planner import YatraPlanner


def run_a_star(p: YatraPlanner) -> SearchResult:
    return a_star(p.start_state(), p.is_goal, p.successors, p.heuristic, "A*")


def run_dijkstra(p: YatraPlanner) -> SearchResult:
    return a_star(p.start_state(), p.is_goal, p.successors, lambda s: 0.0, "Dijkstra")


def run_bfs(p: YatraPlanner) -> SearchResult:
    """Breadth-first search over the same states (first plan with the fewest actions)."""
    t0 = time.perf_counter()
    start = p.start_state()
    parent = {start: None}
    queue = deque([start])
    expanded = 0
    while queue:
        s = queue.popleft()
        if p.is_goal(s):
            actions, states = reconstruct(parent, s)
            return SearchResult(True, sum(a.cost for a in actions), actions, states,
                                expanded, (time.perf_counter() - t0) * 1000, "BFS")
        expanded += 1
        for nxt, _, action in p.successors(s):
            if nxt not in parent:
                parent[nxt] = (s, action)
                queue.append(nxt)
    return SearchResult(False, nodes_expanded=expanded,
                        runtime_ms=(time.perf_counter() - t0) * 1000, algorithm="BFS")


def run_naive(p: YatraPlanner) -> SearchResult:
    """Nearest-neighbour order on the fastest roads, no buffer days.

    It is not a search, so "nodes expanded" is just the number of steps it took.
    It is scored with exactly the same cost function as A*.
    """
    t0 = time.perf_counter()
    s = p.start_state()
    actions, states = [], [s]

    def go(target: str) -> bool:
        nonlocal s
        road = p.g.shortest_road(s[0], target)
        for a, b in zip(road, road[1:]):
            step = p.drive(s, p.g.edge(a, b), buffered=False)
            if step is None:                       # day is full: halt, then try again
                night = p.halt(s)
                if night is None:
                    return False
                s = night[0]; actions.append(night[2]); states.append(s)
                step = p.drive(s, p.g.edge(a, b), buffered=False)
                if step is None:
                    return False
            s = step[0]; actions.append(step[2]); states.append(s)
        return True

    ok = True
    while ok and s[1] != p.all_dhams:
        nearest = min(p.all_dhams - s[1], key=lambda d: p.g.dist[s[0]][d])
        ok = go(nearest)
    if ok and p.round_trip:
        ok = go(p.home)
    return SearchResult(ok, sum(a.cost for a in actions) if ok else float("inf"),
                        actions, states, len(actions),
                        (time.perf_counter() - t0) * 1000, "Naive shortest-road")


ALL = {"A*": run_a_star, "Dijkstra": run_dijkstra, "BFS": run_bfs, "Naive shortest-road": run_naive}


def compare(p: YatraPlanner, names: list[str] | None = None) -> dict[str, dict]:
    """Run the chosen algorithms and return one metrics row per algorithm."""
    out = {}
    for name in names or list(ALL):
        r = ALL[name](p)
        row = {"found": r.found, "nodes_expanded": r.nodes_expanded,
               "runtime_ms": round(r.runtime_ms, 1), "result": r}
        if r.found:
            row.update(p.metrics(r.actions, r.states[-1]))
        out[name] = row
    return out
