"""
app.py - Streamlit web app around the same planner the CLI uses.

Run:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from baselines import compare
from graph import RoadGraph
from planner import YatraPlanner
from plots import comparison_chart, route_map

st.set_page_config(page_title="Char Dham Yatra Planner (A*)", layout="wide")


@st.cache_resource
def load_graph() -> RoadGraph:
    return RoadGraph()


@st.cache_data(show_spinner=False)
def plan(start: str, start_date: date, max_hours: float, sensitivity: float, with_bfs: bool) -> dict:
    """Run the search once per unique set of inputs (cached)."""
    graph = load_graph()
    planner = YatraPlanner(graph, start, start_date, max_hours, sensitivity)
    names = ["A*", "Dijkstra", "Naive shortest-road"] + (["BFS"] if with_bfs else [])
    rows = compare(planner, names)
    out = {"rows": {n: {k: v for k, v in r.items() if k != "result"} for n, r in rows.items()},
           "actions": {n: r["result"].actions for n, r in rows.items()},
           "itinerary": {n: planner.itinerary(r["result"].actions) for n, r in rows.items() if r["found"]}}
    return out


graph = load_graph()

st.title("Char Dham Yatra Planner")
st.caption("A* search over (location, dhams visited, day, time of day). "
           "It plans the order and the schedule, not just the shortest road.")
st.warning("Landslide-risk values, season multipliers and cost weights are **assumptions** made for "
           "this course project (see `data/graph.json`). Distances and drive times are approximate. "
           "This is not official data: do not use it for real travel decisions.")

with st.sidebar:
    st.header("Trip settings")
    start = st.selectbox("Start city", ["Haridwar", "Rishikesh", "Dehradun"])
    start_date = st.date_input("Start date", date(2027, 5, 10))
    max_hours = st.slider("Max driving hours per day", 6.0, 12.0, 9.0, 0.5)
    sensitivity = st.slider("Landslide-risk sensitivity", 0.0, 2.0, 1.0, 0.1,
                            help="0 = ignore risk, 1 = default, 2 = very cautious (more buffer days)")
    with_bfs = st.checkbox("Also run BFS (slower)", value=False)
    go = st.button("Plan my yatra", type="primary")

if go:
    with st.spinner("Searching..."):
        st.session_state["plan"] = plan(start, start_date, max_hours, sensitivity, with_bfs)
        st.session_state["label"] = f"{start}, {start_date:%d %b %Y}, {max_hours:g} h/day, sensitivity {sensitivity:g}"

if "plan" not in st.session_state:
    st.info("Choose your settings in the sidebar and press **Plan my yatra**.")
    st.stop()

res = st.session_state["plan"]
rows = res["rows"]
if not rows["A*"]["found"]:
    st.error("No plan found with these settings. Increase the max driving hours per day.")
    st.stop()

if start_date.month in (11, 12, 1, 2, 3, 4):
    st.warning("The shrines are normally closed in winter; opening dates change every year.")
if start_date.month in (7, 8, 9):
    st.info("Monsoon dates: the assumed risk multiplier is high, so expect many buffer days.")

best, naive = rows["A*"], rows["Naive shortest-road"]
st.subheader(f"A* plan: {st.session_state['label']}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Planned days", best["total_days"], f"{best['total_days'] - naive['total_days']:+d} vs naive", delta_color="off")
c2.metric("Buffer days", best["buffer_days"])
c3.metric("Expected delay days", best["expected_delay_days"],
          f"{best['expected_delay_days'] - naive['expected_delay_days']:+.2f} vs naive", delta_color="inverse")
c4.metric("Plan cost (effective h)", best["plan_cost"],
          f"{best['plan_cost'] - naive['plan_cost']:+.2f} vs naive", delta_color="inverse")
st.write("**Dham order:** " + " → ".join(best["order"]))

left, right = st.columns([1.15, 1])
with left:
    st.markdown("#### Day-by-day itinerary")
    st.dataframe(pd.DataFrame(res["itinerary"]["A*"]), hide_index=True, height=530)
with right:
    st.markdown("#### Route map")
    st.pyplot(route_map(graph, res["actions"]["A*"]))

st.markdown("#### A* vs baselines")
st.pyplot(comparison_chart(rows))
table = pd.DataFrame([{"Algorithm": n, "Nodes expanded": r["nodes_expanded"], "Runtime (ms)": r["runtime_ms"],
                       "Plan cost": r["plan_cost"], "Days": r["total_days"], "Buffer days": r["buffer_days"],
                       "Expected delay days": r["expected_delay_days"]} for n, r in rows.items()])
st.dataframe(table, hide_index=True)

with st.expander("Naive shortest-road itinerary (for comparison)"):
    st.dataframe(pd.DataFrame(res["itinerary"]["Naive shortest-road"]), hide_index=True)
with st.expander("Where does the A* plan's cost come from?"):
    st.dataframe(pd.DataFrame([best["cost_parts"]]), hide_index=True)
    st.caption("All terms are in effective hours. Weights are assumptions from data/graph.json.")
