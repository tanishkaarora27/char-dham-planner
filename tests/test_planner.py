"""
Unit tests. Run with:  pytest -q

They check the claims the project makes:
  * the heuristic is admissible and consistent
  * A* finds the same optimal cost as Dijkstra, with fewer expansions
  * A* is never worse than the naive plan or BFS
  * the hard rules (night ban, daily cap) are never broken
"""
import random
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from a_star import a_star                                    # noqa: E402
from baselines import run_a_star, run_bfs, run_dijkstra, run_naive  # noqa: E402
from graph import RoadGraph                                  # noqa: E402
from planner import YatraPlanner                             # noqa: E402

EPS = 1e-6


@pytest.fixture(scope="module")
def graph():
    return RoadGraph()


@pytest.fixture(scope="module")
def planner(graph):
    return YatraPlanner(graph, "Haridwar", date(2027, 5, 10), 9.0, 1.0)


@pytest.fixture(scope="module")
def results(planner):
    return {"astar": run_a_star(planner), "dijkstra": run_dijkstra(planner),
            "bfs": run_bfs(planner), "naive": run_naive(planner)}


def test_generic_a_star_on_toy_graph():
    """A* on a 4-node graph where the direct edge is NOT the cheapest path."""
    edges = {"A": [("B", 1), ("C", 5)], "B": [("C", 1), ("D", 5)], "C": [("D", 1)], "D": []}
    r = a_star("A", lambda s: s == "D", lambda s: [(n, c, (s, n)) for n, c in edges[s]])
    assert r.found and r.cost == 3 and r.states == ["A", "B", "C", "D"]


def test_graph_data_is_sane(graph):
    for e in graph.edges:
        assert e.src in graph.nodes and e.dst in graph.nodes
        assert e.hours > 0 and e.km > 0 and 0 <= e.risk <= 1
        assert (e.hours * 2).is_integer(), "drive times must be multiples of 0.5 h"
    assert len(graph.dhams) == 4
    assert all(graph.dist["Haridwar"][n] < float("inf") for n in graph.nodes), "graph must be connected"


def test_heuristic_is_zero_at_goal(planner):
    goal = (planner.home, planner.all_dhams, 12, 15.0)
    assert planner.is_goal(goal) and planner.heuristic(goal) == 0


def test_heuristic_admissible(planner):
    """h(s) must not exceed the TRUE optimal remaining cost (found by Dijkstra from s)."""
    rng = random.Random(7)
    dhams = sorted(planner.all_dhams)
    for _ in range(25):
        loc = rng.choice(planner.g.nodes)
        visited = frozenset(d for d in dhams if rng.random() < 0.5)
        s = (loc, visited, 1, planner.day_start_hour)
        true = a_star(s, planner.is_goal, planner.successors).cost
        assert planner.heuristic(s) <= true + EPS, (s, planner.heuristic(s), true)


def test_heuristic_consistent(planner):
    """h(s) <= step_cost + h(s') for every action from a broad sample of states."""
    dhams = sorted(planner.all_dhams)
    checked = 0
    for loc in planner.g.nodes:
        for mask in range(16):
            visited = frozenset(d for i, d in enumerate(dhams) if mask >> i & 1)
            for t in (8.0, 10.5, 13.0):
                s = (loc, visited, 1, t)
                for nxt, cost, _ in planner.successors(s):
                    assert planner.heuristic(s) <= cost + planner.heuristic(nxt) + EPS
                    checked += 1
    assert checked > 1000


def test_a_star_matches_dijkstra_cost(results):
    assert results["astar"].found and results["dijkstra"].found
    assert results["astar"].cost <= results["dijkstra"].cost + EPS
    assert abs(results["astar"].cost - results["dijkstra"].cost) < EPS     # both optimal


def test_a_star_expands_fewer_nodes_than_dijkstra(results):
    assert results["astar"].nodes_expanded < results["dijkstra"].nodes_expanded


def test_a_star_not_worse_than_naive_or_bfs(results):
    assert results["astar"].cost <= results["naive"].cost + EPS
    assert results["astar"].cost <= results["bfs"].cost + EPS


def test_plan_visits_all_dhams_and_returns_home(planner, results):
    for r in results.values():
        final = r.states[-1]
        assert final[1] == planner.all_dhams and final[0] == planner.home


def test_hard_rules_never_broken(planner, results):
    """No arrival after the night ban starts, never more than the daily driving cap."""
    for r in results.values():
        per_day = {}
        for a in r.actions:
            if a.kind == "drive":
                assert a.arrive <= planner.night_ban_start_hour + EPS
                per_day[a.day] = per_day.get(a.day, 0) + a.hours
        assert max(per_day.values()) <= planner.max_hours + EPS


def test_zero_sensitivity_removes_delay_cost(graph):
    p = YatraPlanner(graph, risk_sensitivity=0.0)
    m = p.metrics(run_a_star(p).actions, run_a_star(p).states[-1])
    assert m["cost_parts"]["expected delay"] == 0 and m["buffer_days"] == 0


def test_higher_sensitivity_never_reduces_buffer_days(graph):
    counts = []
    for sens in (0.5, 1.0, 2.0):
        p = YatraPlanner(graph, risk_sensitivity=sens)
        r = run_a_star(p)
        counts.append(p.metrics(r.actions, r.states[-1])["buffer_days"])
    assert counts == sorted(counts)


def test_one_way_trip_is_cheaper_than_round_trip(graph, results):
    p = YatraPlanner(graph, round_trip=False)
    assert run_a_star(p).cost < results["astar"].cost


def test_unknown_start_is_rejected(graph):
    with pytest.raises(ValueError):
        YatraPlanner(graph, start="Mumbai")
