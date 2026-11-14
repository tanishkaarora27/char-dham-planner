"""
a_star.py - a small, generic A* search.

Nothing in this file knows about roads or pilgrims. It only needs:
    start        : any hashable state
    is_goal      : function(state) -> bool
    successors   : function(state) -> iterable of (next_state, step_cost, action)
    heuristic    : function(state) -> estimated remaining cost (h)

A* always expands the frontier state with the smallest f = g + h, where
    g = cost paid so far,  h = optimistic estimate of the cost still to pay.
If h never overestimates (admissible), the first goal popped is optimal.

Dijkstra / Uniform Cost Search is the same algorithm with h = 0, so
baselines.py simply calls a_star() with a zero heuristic.

Why A* and not AO*?
    AO* searches AND-OR graphs: problems that split into sub-problems which
    must ALL be solved (AND) or where ONE alternative is enough (OR).
    A yatra plan is a single sequence of actions - one path through a state
    graph - so it is an ordinary OR-graph path search. That is A*'s job;
    AO* would add machinery without adding anything.
"""
from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Hashable, Iterable


@dataclass
class SearchResult:
    """What a search returns: the plan plus the numbers we compare algorithms on."""
    found: bool
    cost: float = float("inf")
    actions: list[Any] = field(default_factory=list)     # one action per step
    states: list[Hashable] = field(default_factory=list)  # states[0] is the start
    nodes_expanded: int = 0
    runtime_ms: float = 0.0
    algorithm: str = "A*"


def reconstruct(parent: dict, goal: Hashable) -> tuple[list[Any], list[Hashable]]:
    """Walk parent pointers back from the goal to rebuild the plan."""
    actions, states = [], [goal]
    s = goal
    while parent[s] is not None:
        prev, action = parent[s]
        actions.append(action)
        states.append(prev)
        s = prev
    actions.reverse()
    states.reverse()
    return actions, states


def a_star(
    start: Hashable,
    is_goal: Callable[[Hashable], bool],
    successors: Callable[[Hashable], Iterable[tuple[Hashable, float, Any]]],
    heuristic: Callable[[Hashable], float] = lambda s: 0.0,
    algorithm_name: str = "A*",
) -> SearchResult:
    """Best-first search on f = g + h with a binary-heap priority queue."""
    t0 = time.perf_counter()
    tie = itertools.count()                 # tie-breaker so the heap never compares states
    best_g: dict[Hashable, float] = {start: 0.0}
    parent: dict[Hashable, Any] = {start: None}
    frontier = [(heuristic(start), next(tie), 0.0, start)]   # (f, tie, g, state)
    expanded = 0

    while frontier:
        f, _, g, state = heapq.heappop(frontier)
        if g > best_g.get(state, float("inf")):
            continue                        # stale queue entry: a cheaper path was found later
        if is_goal(state):
            actions, states = reconstruct(parent, state)
            return SearchResult(True, g, actions, states, expanded,
                                (time.perf_counter() - t0) * 1000, algorithm_name)
        expanded += 1
        for nxt, step_cost, action in successors(state):
            new_g = g + step_cost
            if new_g < best_g.get(nxt, float("inf")) - 1e-12:
                best_g[nxt] = new_g
                parent[nxt] = (state, action)
                heapq.heappush(frontier, (new_g + heuristic(nxt), next(tie), new_g, nxt))

    return SearchResult(False, nodes_expanded=expanded,
                        runtime_ms=(time.perf_counter() - t0) * 1000,
                        algorithm=algorithm_name)
