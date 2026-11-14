"""
plots.py - the two charts used by the CLI, the Streamlit app and the slides.

route_map()         schematic map (approximate lat/lon) with the planned route
comparison_chart()  A* vs baselines on four numbers
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")                     # draw to files / Streamlit, no window needed
import matplotlib.pyplot as plt

from graph import RoadGraph
from planner import Action

INK = "#1C1F23"       # dark neutral
ACCENT = "#C8501E"    # single accent colour
GREY = "#B8BCC2"
LIGHT = "#DDE0E4"
BAND = "#F4D9CC"     # pale tint of the accent, marks slide-prone stretches


def route_map(g: RoadGraph, actions: list[Action], title: str = "", ax=None):
    """Draw the road graph and overlay the plan. Returns the matplotlib Figure."""
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(9, 5.6), dpi=150)
    for e in g.edges:                                         # all roads; risky ones get a pale band
        (x0, y0), (x1, y1) = g.coords[e.src], g.coords[e.dst]
        if e.risk >= 0.10:
            ax.plot([x0, x1], [y0, y1], color=BAND, lw=9, solid_capstyle="round", zorder=0)
        ax.plot([x0, x1], [y0, y1], color=LIGHT, lw=1.6, zorder=1)

    drives = [a for a in actions if a.kind == "drive"]
    for a in drives:                                          # the planned route
        (x0, y0), (x1, y1) = g.coords[a.src], g.coords[a.dst]
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), zorder=3,
                    arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=2.0,
                                    shrinkA=4, shrinkB=4, mutation_scale=9))

    order = {a.dst: i + 1 for i, a in enumerate(a for a in drives if a.visit)}
    buffers = {a.dst for a in drives if a.buffered}
    for n, (x, y) in g.coords.items():
        if n in g.dham_nodes:
            ax.scatter(x, y, s=260, color=ACCENT, zorder=4, edgecolor="white", lw=1.5)
            ax.text(x, y, str(order.get(n, "")), color="white", ha="center", va="center",
                    fontsize=9, fontweight="bold", zorder=5)
            label = f"{n}\n({g.dham_nodes[n]})" if n != g.dham_nodes[n] else n
            ax.text(x, y + 0.045, label, ha="center", va="bottom", fontsize=8,
                    color=INK, fontweight="bold", zorder=5)
        else:
            ax.scatter(x, y, s=28, color=INK, zorder=4)
            ax.text(x + 0.02, y - 0.02, n, ha="left", va="top", fontsize=7, color=INK, zorder=5,
                    bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=0.8))
        if n in buffers:
            ax.scatter(x, y, s=520, facecolor="none", edgecolor=INK, lw=1.4, marker="s", zorder=4)

    ax.plot([], [], color=ACCENT, lw=2, label="Planned route")
    ax.plot([], [], color=BAND, lw=7, label="Slide-prone stretch (assumed risk >= 10%)")
    ax.scatter([], [], s=90, color=ACCENT, label="Dham road-head (number = visiting order)")
    ax.scatter([], [], s=110, facecolor="none", edgecolor=INK, marker="s", label="Buffer day reserved here")
    ax.legend(loc="lower right", fontsize=7, frameon=False)
    ax.set_title(title or "Planned route (schematic, not to scale)", loc="left",
                 fontsize=11, color=INK, fontweight="bold")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.margins(0.08)
    if fig:
        fig.tight_layout()
    return fig or ax.figure


def comparison_chart(rows: dict[str, dict], title: str = "A* vs baselines"):
    """Four small bar charts: nodes expanded, plan cost, total days, expected delay days."""
    panels = [("nodes_expanded", "Nodes expanded", "{:,.0f}"),
              ("plan_cost", "Plan cost (effective hours)", "{:.1f}"),
              ("total_days", "Planned days", "{:.0f}"),
              ("expected_delay_days", "Expected delay days", "{:.2f}")]
    names = [n for n, r in rows.items() if r.get("found")]
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.4), dpi=150)
    for ax, (key, label, fmt) in zip(axes, panels):
        vals = [rows[n][key] for n in names]
        colors = [ACCENT if n == "A*" else GREY for n in names]
        bars = ax.barh(names[::-1], vals[::-1], color=colors[::-1], height=0.6)
        for b, v in zip(bars, vals[::-1]):
            ax.text(b.get_width(), b.get_y() + b.get_height() / 2, " " + fmt.format(v),
                    va="center", ha="left", fontsize=8, color=INK)
        ax.set_title(label, fontsize=9, loc="left", color=INK, fontweight="bold")
        ax.set_xlim(0, max(vals) * 1.32 if max(vals) else 1)
        ax.set_xticks([])
        ax.tick_params(axis="y", labelsize=8, length=0, colors=INK)
        for s in ax.spines.values():
            s.set_visible(False)
        if ax is not axes[0]:
            ax.set_yticklabels([])
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, fontweight="bold", color=INK)
    fig.text(0.01, 0.01, "Risk values and cost weights are project assumptions, not official data. "
             "Naive is not a search: its 'nodes expanded' is its step count.",
             fontsize=7, color="#6B7078")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    return fig
