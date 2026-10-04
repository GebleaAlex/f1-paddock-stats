"""Championship points systems used since 1950, for re-scoring any season under another system.

Re-scoring is deliberately simple and the same for every system, so the comparison is fair:
- only Grand Prix results count (sprints are left out);
- every result counts (the dropped-score rules used until 1990 are ignored);
- a classified finish scores by position; the fastest-lap bonus goes to the driver with the race's fastest lap,
  with the top-10 condition where the system had it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PointsSystem:
    id: str
    label: str
    years: str
    points: tuple[float, ...]
    fastest_lap: float = 0
    fastest_lap_top10_only: bool = False


SYSTEMS: list[PointsSystem] = [
    PointsSystem("1950", "8-6-4-3-2 + 1 for fastest lap", "1950–1959", (8, 6, 4, 3, 2), fastest_lap=1),
    PointsSystem("1960", "8-6-4-3-2-1", "1960", (8, 6, 4, 3, 2, 1)),
    PointsSystem("1961", "9-6-4-3-2-1", "1961–1990", (9, 6, 4, 3, 2, 1)),
    PointsSystem("1991", "10-6-4-3-2-1", "1991–2002", (10, 6, 4, 3, 2, 1)),
    PointsSystem("2003", "10-8-6-5-4-3-2-1", "2003–2009", (10, 8, 6, 5, 4, 3, 2, 1)),
    PointsSystem("2010", "25-18-15-12-10-8-6-4-2-1", "2010–2018, 2025–", (25, 18, 15, 12, 10, 8, 6, 4, 2, 1)),
    PointsSystem(
        "2019",
        "25-18-15-12-10-8-6-4-2-1 + 1 for fastest lap",
        "2019–2024",
        (25, 18, 15, 12, 10, 8, 6, 4, 2, 1),
        fastest_lap=1,
        fastest_lap_top10_only=True,
    ),
    PointsSystem("winner", "Winner takes all: 1 point per win", "never used", (1,)),
    PointsSystem("medals", "Podiums only: 3-2-1", "never used", (3, 2, 1)),
]

BY_ID = {s.id: s for s in SYSTEMS}


def points_for(system: PointsSystem, position: int | None, fastest_lap: bool) -> float:
    score = 0.0
    if position is not None and 1 <= position <= len(system.points):
        score += system.points[position - 1]
    if fastest_lap and system.fastest_lap:
        eligible = not system.fastest_lap_top10_only or (position is not None and position <= 10)
        if eligible:
            score += system.fastest_lap
    return score
