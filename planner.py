"""
planner.py - turns "plan my Char Dham yatra" into a search problem.

STATE   (location, dhams_visited, day, time_of_day)
          location       town we are in
          dhams_visited  frozenset of dham road-heads already visited
          day            1, 2, 3 ...
          time_of_day    clock hour, e.g. 8.0 = 08:00, 13.5 = 13:30

ACTIONS drive            to a neighbouring town (same day)
        drive + buffer   same drive, but one spare "buffer day" is reserved
                         after it so a blocked road does not break the plan
        halt             stop for the night; next day starts at day_start_hour

        Arriving at a dham we have not visited yet always ends the day there
        (darshan), plus the dham's visit_extra_days for trek shrines.

COST g  every term is in "effective hours" and is >= 0:
          base driving time
        + expected landslide delay  = sensitivity * P(blocked) * hours lost
        + near-night-ban penalty    (driving inside the last hours before the ban)
        + fatigue penalty           (driving beyond the comfortable daily hours)
        + overnight cost            (each night on the road is not free)
        + buffer-day cost           (when a buffer day is reserved)

HARD RULES  no arrival after the night ban starts; no more than
            max_hours_per_day of driving in one day.

All weights and risk numbers come from data/graph.json and are ASSUMPTIONS.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from itertools import combinations
from typing import Iterator

from graph import Edge, RoadGraph

State = tuple[str, frozenset, int, float]


@dataclass(frozen=True)
class Action:
    """One step of a plan, with its cost split into parts so we can explain it."""
    kind: str                 # "drive" or "halt"
    src: str
    dst: str
    day: int
    depart: float = 0.0
    arrive: float = 0.0
    hours: float = 0.0
    p_block: float = 0.0      # assumed probability the stretch is blocked that day
    buffered: bool = False
    visit: str | None = None  # dham name if this drive ends in a darshan
    extra_days: int = 0
    c_drive: float = 0.0
    c_delay: float = 0.0
    c_night: float = 0.0
    c_fatigue: float = 0.0
    c_overnight: float = 0.0
    c_buffer: float = 0.0

    @property
    def cost(self) -> float:
        return (self.c_drive + self.c_delay + self.c_night +
                self.c_fatigue + self.c_overnight + self.c_buffer)


def overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    """Length of the overlap between intervals [a0, a1] and [b0, b1]."""
    return max(0.0, min(a1, b1) - max(a0, b0))


class YatraPlanner:
    """Holds the road graph + trip settings and exposes the search problem."""

    def __init__(self, graph: RoadGraph, start: str = "Haridwar",
                 start_date: date | None = None, max_hours_per_day: float = 9.0,
                 risk_sensitivity: float = 1.0, round_trip: bool = True):
        if start not in graph.nodes:
            raise ValueError(f"Unknown start town '{start}'. Choose one of: {', '.join(graph.nodes)}")
        self.g = graph
        self.home = start
        self.start_date = start_date or date(2027, 5, 10)
        self.max_hours = float(max_hours_per_day)
        self.sens = float(risk_sensitivity)
        self.round_trip = round_trip
        for key, value in graph.cost_model.items():   # copy cost weights as attributes
            setattr(self, key, value)
        self.max_trip_days = int(self.max_trip_days)
        self.all_dhams = frozenset(graph.dham_nodes)
        self._mst_cache: dict[frozenset, float] = {}

    # ---------------------------------------------------------------- problem
    def start_state(self) -> State:
        return (self.home, frozenset(), 1, self.day_start_hour)

    def is_goal(self, s: State) -> bool:
        loc, visited, _, _ = s
        return visited == self.all_dhams and (loc == self.home or not self.round_trip)

    def p_block(self, edge: Edge, day: int) -> float:
        """Assumed chance the stretch is blocked on that calendar day (season-adjusted)."""
        month = (self.start_date + timedelta(days=day - 1)).month
        return min(1.0, edge.risk * self.g.season[month])

    def drive(self, s: State, e: Edge, buffered: bool) -> tuple[State, float, Action] | None:
        """Apply a drive action. Returns None if a hard rule forbids it."""
        loc, visited, day, t = s
        arrive = t + e.hours
        if arrive > self.night_ban_start_hour + 1e-9:                    # night driving ban
            return None
        if arrive - self.day_start_hour > self.max_hours + 1e-9:         # daily driving cap
            return None

        p = self.p_block(e, day)
        lost = self.hours_lost_if_blocked_with_buffer if buffered else self.hours_lost_if_blocked_no_buffer
        c_delay = self.sens * p * lost
        dusk0 = self.night_ban_start_hour - self.near_ban_margin_hours
        c_night = self.near_ban_penalty_per_hour * overlap(t, arrive, dusk0, self.night_ban_start_hour)
        driven0, driven1 = t - self.day_start_hour, arrive - self.day_start_hour
        c_fatigue = self.fatigue_penalty_per_hour * overlap(driven0, driven1, self.comfort_hours_per_day, 24)

        new_dham = e.dst in self.all_dhams and e.dst not in visited
        extra = self.g.visit_extra_days[e.dst] if new_dham else 0
        # nights spent before the next driving day:
        #   darshan -> 1 night + trek days;  buffer -> halt night + the spare day itself
        nights = (1 + extra if new_dham else 1 if buffered else 0) + (1 if buffered else 0)
        if new_dham or buffered:        # the day ends here; wake up `nights` days later
            nxt: State = (e.dst, visited | {e.dst} if new_dham else visited,
                          day + nights, self.day_start_hour)
        else:
            nxt = (e.dst, visited, day, arrive)
        if nxt[2] > self.max_trip_days:
            return None

        act = Action("drive", loc, e.dst, day, t, arrive, e.hours, p, buffered,
                     self.g.dham_nodes[e.dst] if new_dham else None, extra,
                     c_drive=e.hours, c_delay=c_delay, c_night=c_night, c_fatigue=c_fatigue,
                     c_overnight=self.overnight_cost * nights,
                     c_buffer=self.buffer_day_cost if buffered else 0.0)
        return nxt, act.cost, act

    def halt(self, s: State) -> tuple[State, float, Action] | None:
        """Stop for the night. Only allowed after driving, so the search cannot idle forever."""
        loc, visited, day, t = s
        if t <= self.day_start_hour or day + 1 > self.max_trip_days:
            return None
        act = Action("halt", loc, loc, day, t, t, c_overnight=self.overnight_cost)
        return (loc, visited, day + 1, self.day_start_hour), act.cost, act

    def successors(self, s: State) -> Iterator[tuple[State, float, Action]]:
        """All legal actions from state s, as (next_state, step_cost, action)."""
        for e in self.g.adj[s[0]]:
            for buffered in (False, True):
                step = self.drive(s, e, buffered)
                if step:
                    yield step
        step = self.halt(s)
        if step:
            yield step

    # -------------------------------------------------------------- heuristic
    def _mst(self, towns: frozenset) -> float:
        """Weight of a minimum spanning tree over `towns`, using fastest base driving hours.

        Kruskal's algorithm; at most 5 towns, and results are cached per subset.
        """
        if towns in self._mst_cache:
            return self._mst_cache[towns]
        comp = {t: t for t in towns}

        def find(x):
            while comp[x] != x:
                x = comp[x]
            return x

        total = 0.0
        for w, a, b in sorted((self.g.dist[a][b], a, b) for a, b in combinations(sorted(towns), 2)):
            ra, rb = find(a), find(b)
            if ra != rb:
                comp[ra] = rb
                total += w
        self._mst_cache[towns] = total
        return total

    def heuristic(self, s: State) -> float:
        """h(n) = fastest link from here to any unvisited dham
                 + MST over the unvisited dhams (and home, on a round trip).

        ADMISSIBLE (never overestimates):
          Whatever we do next, we must first reach SOME unvisited dham, which
          takes at least the fastest link. From there the rest of the trip is a
          path through all remaining dhams (ending at home on a round trip).
          A path through a set of towns is a spanning tree of them, so it is at
          least as long as the MINIMUM spanning tree. Every real cost adds
          non-negative penalties on top of base driving hours, so
          h <= true remaining cost.

        CONSISTENT (h(n) <= step cost + h(n')):
          * drive to a non-dham town v: the fastest link can shrink by at most
            dist(n, v) <= step cost (triangle inequality on fastest-road hours);
            the MST term does not change.
          * drive to an unvisited dham t: fastest link <= dist(n, t) <= step cost,
            and MST(S) <= MST(S - t) + cheapest link from t into S - t
            (hang t on the smaller tree as a leaf), which is exactly h(n').
          * halt / buffer: location and visited set do not change, cost >= 0.

        Note: the textbook "MST over unvisited dhams PLUS the current town" is
        admissible too, but it can break consistency at in-between towns such as
        Rudraprayag (a junction can act like a Steiner point). Attaching the
        current town by its single fastest link fixes that and is never weaker.
        tests/test_planner.py checks both properties numerically.
        """
        loc, visited, _, _ = s
        todo = self.all_dhams - visited
        if not todo:
            return self.g.dist[loc][self.home] if self.round_trip else 0.0
        link = min(self.g.dist[loc][t] for t in todo)
        return link + self._mst(todo | {self.home} if self.round_trip else todo)

    # ---------------------------------------------------------------- reports
    def fmt_date(self, day: int) -> str:
        return (self.start_date + timedelta(days=day - 1)).strftime("%d %b %Y")

    def itinerary(self, actions: list[Action]) -> list[dict]:
        """Day-by-day table built from a plan's actions."""
        days: dict[int, dict] = {}

        def row(d: int) -> dict:
            return days.setdefault(d, {"route": [], "hours": 0.0, "notes": []})

        for a in actions:
            if a.kind == "halt":
                row(a.day)["notes"].append(f"Night halt at {a.src}")
                continue
            r = row(a.day)
            if not r["route"]:
                r["route"].append(a.src)
            r["route"].append(a.dst)
            r["hours"] += a.hours
            where = a.dst
            if a.visit:
                r["notes"].append(f"{a.visit} darshan; night halt at {a.dst}")
                for k in range(1, a.extra_days + 1):
                    row(a.day + k)["notes"].append(f"{a.visit} trek / darshan day (base: {a.dst})")
            if a.buffered:
                row(a.day + 1 + a.extra_days)["notes"].append(
                    f"BUFFER DAY at {where}: slack for the {a.src}-{a.dst} stretch "
                    f"(assumed block chance {a.p_block:.0%})")
                if not a.visit:
                    r["notes"].append(f"Night halt at {a.dst}")

        table = []
        for d in sorted(days):
            r = days[d]
            table.append({
                "Day": d,
                "Date": self.fmt_date(d),
                "Route": " > ".join(r["route"]) if r["route"] else "-",
                "Drive (h)": round(r["hours"], 1),
                "Notes": "; ".join(r["notes"]),
            })
        return table

    def metrics(self, actions: list[Action], final: State) -> dict:
        """Numbers used to compare plans."""
        drives = [a for a in actions if a.kind == "drive"]
        last_day = final[2] if final[3] > self.day_start_hour else final[2] - 1
        return {
            "plan_cost": round(sum(a.cost for a in actions), 2),
            "total_days": last_day,
            "drive_hours": round(sum(a.hours for a in drives), 1),
            "buffer_days": sum(a.buffered for a in drives),
            # each unbuffered blockage is assumed to cost one schedule day
            "expected_delay_days": round(sum(a.p_block for a in drives if not a.buffered), 2),
            "order": [a.visit for a in drives if a.visit],
            "cost_parts": {
                "driving": round(sum(a.c_drive for a in actions), 2),
                "expected delay": round(sum(a.c_delay for a in actions), 2),
                "near night-ban": round(sum(a.c_night for a in actions), 2),
                "fatigue": round(sum(a.c_fatigue for a in actions), 2),
                "overnights": round(sum(a.c_overnight for a in actions), 2),
                "buffer days": round(sum(a.c_buffer for a in actions), 2),
            },
        }
