"""
main.py - command-line entry point.

Example:
    python main.py --start Haridwar --max-hours-per-day 9 --start-date 2027-05-10

Prints the A* itinerary, compares it with BFS, Dijkstra and the naive plan,
and saves two charts plus a JSON results file in outputs/.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from baselines import compare
from graph import DEFAULT_GRAPH, RoadGraph
from planner import YatraPlanner


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Char Dham Yatra planner using A* search")
    ap.add_argument("--start", default="Haridwar", help="start (and end) town")
    ap.add_argument("--max-hours-per-day", type=float, default=9.0, help="hard cap on driving hours per day")
    ap.add_argument("--start-date", type=date.fromisoformat, default=date(2027, 5, 10), help="YYYY-MM-DD")
    ap.add_argument("--risk-sensitivity", type=float, default=1.0,
                    help="how strongly landslide risk is weighted (0 = ignore, 1 = default, 2 = cautious)")
    ap.add_argument("--one-way", action="store_true", help="finish at the last dham instead of returning")
    ap.add_argument("--graph", default=str(DEFAULT_GRAPH), help="path to graph.json")
    ap.add_argument("--out", default="outputs", help="folder for charts and results.json")
    ap.add_argument("--no-plots", action="store_true", help="skip saving charts")
    return ap.parse_args()


def print_table(rows: list[dict]) -> None:
    widths = {k: max(len(str(k)), *(len(str(r[k])) for r in rows)) for k in rows[0]}
    line = "  ".join(f"{k:<{widths[k]}}" for k in rows[0])
    print(line); print("-" * len(line))
    for r in rows:
        print("  ".join(f"{str(r[k]):<{widths[k]}}" for k in r))


def main() -> None:
    a = parse_args()
    graph = RoadGraph(a.graph)
    planner = YatraPlanner(graph, a.start, a.start_date, a.max_hours_per_day,
                           a.risk_sensitivity, round_trip=not a.one_way)

    print("\nCHAR DHAM YATRA PLANNER (A* search)")
    print(f"Start: {a.start} | Start date: {a.start_date} | Max driving: {a.max_hours_per_day} h/day | "
          f"Risk sensitivity: {a.risk_sensitivity} | {'One-way' if a.one_way else 'Round trip'}")
    print("NOTE: landslide-risk values and cost weights are ASSUMPTIONS in data/graph.json, "
          "not official data.\n")
    if a.start_date.month in (11, 12, 1, 2, 3, 4):
        print("WARNING: the shrines are normally closed in winter; opening dates change every year.\n")

    rows = compare(planner)
    best = rows["A*"]
    if not best["found"]:
        raise SystemExit("No plan found. Try a higher --max-hours-per-day "
                         "(the longest single stretch is 5 hours).")

    print("A* ITINERARY  (dham order: " + " > ".join(best["order"]) + ")")
    print_table(planner.itinerary(best["result"].actions))
    print("\nCost breakdown (effective hours):",
          ", ".join(f"{k} {v}" for k, v in best["cost_parts"].items()))

    print("\nCOMPARISON")
    table = [{"Algorithm": n, "Nodes expanded": r["nodes_expanded"], "Runtime (ms)": r["runtime_ms"],
              "Plan cost": r.get("plan_cost", "-"), "Days": r.get("total_days", "-"),
              "Buffer days": r.get("buffer_days", "-"),
              "Expected delay days": r.get("expected_delay_days", "-")} for n, r in rows.items()]
    print_table(table)
    print("\nNAIVE ITINERARY  (dham order: " + " > ".join(rows["Naive shortest-road"]["order"]) + ")")
    print_table(planner.itinerary(rows["Naive shortest-road"]["result"].actions))

    out = Path(a.out); out.mkdir(exist_ok=True)
    summary = {"settings": {"start": a.start, "start_date": str(a.start_date),
                            "max_hours_per_day": a.max_hours_per_day,
                            "risk_sensitivity": a.risk_sensitivity, "round_trip": not a.one_way},
               "comparison": {n: {k: v for k, v in r.items() if k != "result"} for n, r in rows.items()},
               "a_star_itinerary": planner.itinerary(best["result"].actions),
               "naive_itinerary": planner.itinerary(rows["Naive shortest-road"]["result"].actions)}
    (out / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if not a.no_plots:
        from plots import comparison_chart, route_map
        route_map(graph, best["result"].actions,
                  "A* route (schematic, not to scale)").savefig(out / "route_map.png")
        route_map(graph, rows["Naive shortest-road"]["result"].actions,
                  "Naive shortest-road route (schematic, not to scale)").savefig(out / "route_map_naive.png")
        comparison_chart(rows).savefig(out / "comparison.png")
        print(f"\nSaved: {out/'route_map.png'}, {out/'route_map_naive.png'}, "
              f"{out/'comparison.png'}, {out/'results.json'}")


if __name__ == "__main__":
    main()
