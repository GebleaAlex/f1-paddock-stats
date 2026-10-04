"""Stat explorer: race results filtered by any combination of years, circuit, team, driver, teammate, starting
position and starting tyre, grouped by driver, team, season or circuit. Every filter is a query parameter, so every
answer is a link.

Only whitelisted SQL fragments are used; user values always travel as parameters.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..db import db

router = APIRouter(tags=["explore"])

GROUPS = {
    "driver": ("rr.driver_id", "d.name", "/drivers/"),
    "constructor": ("rr.constructor_id", "c.name", "/constructors/"),
    "season": ("CAST(r.year AS VARCHAR)", "CAST(r.year AS VARCHAR)", "/seasons/"),
    "circuit": ("r.circuit_id", "ci.name", "/circuits/"),
    "driver_season": ("rr.driver_id || ':' || r.year", "d.name || ' ' || r.year", None),
}
SORTS = {
    "wins": "wins DESC, podiums DESC",
    "podiums": "podiums DESC, wins DESC",
    "poles": "poles DESC, wins DESC",
    "points": "points DESC",
    "races": "races DESC",
    "win_rate": "win_rate DESC NULLS LAST, wins DESC",
    "avg_finish": "avg_finish ASC NULLS LAST",
    "gained": "avg_gained DESC NULLS LAST",
    "dnfs": "dnfs DESC",
}
TYRES = {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}


@router.get("/explore")
def explore(
    group: Literal["driver", "constructor", "season", "circuit", "driver_season"] = "driver",
    year_from: int = Query(1950, alias="from"),
    year_to: int = Query(2100, alias="to"),
    circuit: str | None = None,
    constructor: str | None = None,
    driver: str | None = None,
    teammate: str | None = Query(None, description="Only races where this driver was a teammate of the row's driver"),
    grid_min: int | None = Query(None, ge=1),
    grid_max: int | None = Query(None, ge=1),
    start_tyre: str | None = Query(None, description="Tyre the driver started the race on (2018+)"),
    min_races: int = Query(1, ge=1),
    sort: str = "wins",
    limit: int = Query(50, ge=1, le=500),
):
    if sort not in SORTS:
        raise HTTPException(400, f"sort must be one of {', '.join(SORTS)}")
    if start_tyre and start_tyre.upper() not in TYRES:
        raise HTTPException(400, f"start_tyre must be one of {', '.join(sorted(TYRES))}")
    key, label, link = GROUPS[group]
    where = ["r.year BETWEEN $from AND $to", "rr.position_text NOT IN ('DNQ', 'DNPQ', 'DNS', 'DNP', 'EX')"]
    params: dict = {"from": year_from, "to": year_to, "min": min_races, "limit": limit}
    if circuit:
        where.append("r.circuit_id = $circuit")
        params["circuit"] = circuit
    if constructor:
        where.append("rr.constructor_id = $constructor")
        params["constructor"] = constructor
    if driver:
        where.append("rr.driver_id = $driver")
        params["driver"] = driver
    if teammate:
        where.append(
            """EXISTS (SELECT 1 FROM teammate_race t WHERE t.race_id = rr.race_id
               AND ((t.driver_a = rr.driver_id AND t.driver_b = $teammate) OR (t.driver_b = rr.driver_id AND t.driver_a = $teammate)))"""
        )
        params["teammate"] = teammate
    if grid_min is not None:
        where.append("rr.grid_position_number >= $grid_min")
        params["grid_min"] = grid_min
    if grid_max is not None:
        where.append("rr.grid_position_number <= $grid_max")
        params["grid_max"] = grid_max
    if start_tyre:
        where.append(
            """EXISTS (SELECT 1 FROM timing_session s JOIN timing_lap l ON l.session_key = s.session_key
               WHERE s.race_id = rr.race_id AND s.type = 'R' AND l.driver_id = rr.driver_id AND l.lap = 1
               AND l.compound = $tyre)"""
        )
        params["tyre"] = start_tyre.upper()
    sql = f"""
        SELECT {key} AS key, {label} AS name,
               count(*) AS races,
               count(*) FILTER (WHERE rr.position_number = 1) AS wins,
               count(*) FILTER (WHERE rr.position_number <= 3) AS podiums,
               count(*) FILTER (WHERE rr.pole_position) AS poles,
               round(sum(coalesce(rr.points, 0)), 1) AS points,
               round(avg(rr.position_number), 2) AS avg_finish,
               round(avg(rr.grid_position_number), 2) AS avg_grid,
               round(avg(rr.grid_position_number - rr.position_number)
                     FILTER (WHERE rr.position_number IS NOT NULL AND rr.grid_position_number IS NOT NULL), 2) AS avg_gained,
               count(*) FILTER (WHERE rr.position_number IS NULL) AS dnfs,
               min(rr.position_number) AS best_finish,
               round(count(*) FILTER (WHERE rr.position_number = 1) * 100.0 / count(*), 1) AS win_rate,
               min(r.year) AS first_year, max(r.year) AS last_year
        FROM race_result rr
        JOIN race r ON r.id = rr.race_id
        JOIN driver d ON d.id = rr.driver_id
        JOIN constructor c ON c.id = rr.constructor_id
        JOIN circuit ci ON ci.id = r.circuit_id
        WHERE {" AND ".join(where)}
        GROUP BY 1, 2
        HAVING count(*) >= $min
        ORDER BY {SORTS[sort]}, name
        LIMIT $limit
    """
    rows = db.rows(sql, params)
    total = db.one(
        f"""
        SELECT count(*) AS entries, count(DISTINCT rr.race_id) AS races
        FROM race_result rr JOIN race r ON r.id = rr.race_id
        WHERE {" AND ".join(where)}
        """,
        {k: v for k, v in params.items() if k not in ("min", "limit")},
    )
    for r in rows:
        r["href"] = (link + r["key"]) if link else f"/drivers/{r['key'].split(':')[0]}"
    return {"rows": rows, "total": total}
