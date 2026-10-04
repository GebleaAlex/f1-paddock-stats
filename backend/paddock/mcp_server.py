"""MCP server: lets an assistant (Claude Desktop, Claude Code, ...) query Paddock Stats.

Run with `paddock mcp` (stdio). The tools call the same functions as the HTTP API, read the same database, and
return compact JSON. Raw telemetry is not exposed, only summaries, for the same licensing reason as the API.
"""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from .api.routes import (
    analysis,
    conditions,
    drivers,
    explore,
    insights,
    races,
    records,
    seasons,
    simulate,
    teammates,
    telemetry,
)
from .api.routes import meta as meta_routes

server = MCPServer(
    name="paddock-stats",
    title="Paddock Stats",
    description="Formula 1 statistics 1950 to today: results, laps (1996+), tyres and telemetry summaries (2018+).",
    instructions=(
        "Use search first to turn names into ids (drivers like 'max-verstappen', teams like 'red-bull', circuits like "
        "'monza'). Races are addressed by year and round. Lap-by-lap data exists from 1996, pit stops from 2011, tyres, "
        "safety cars and telemetry from 2018. Data: f1db (CC BY 4.0) and Jolpica-F1 (CC BY-NC-SA 4.0); timing from "
        "Formula 1 via FastF1. Unofficial, not associated with the Formula 1 companies."
    ),
)


def _trim(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    return [{k: r.get(k) for k in keys} for r in rows]


@server.tool()
def search(query: str) -> list[dict[str, Any]]:
    """Find drivers, teams, circuits and seasons by name. Returns ids to use with the other tools."""
    return meta_routes.search(q=query, limit=8)


@server.tool()
def database_info() -> dict[str, Any]:
    """When the data was built, its sources and licences, and the latest and next race."""
    return meta_routes.meta()


@server.tool()
def get_season(year: int) -> dict[str, Any]:
    """Calendar with winners, and the drivers' and constructors' standings of a season."""
    s = seasons.season(year)
    return {
        "year": year,
        "races": _trim(
            s["races"], ("round", "date", "grand_prix", "circuit", "winner", "winner_constructor", "pole", "completed")
        ),
        "driver_standings": _trim(s["driver_standings"], ("position", "name", "points", "wins", "podiums", "poles")),
        "constructor_standings": _trim(s["constructor_standings"], ("position", "name", "engine", "points", "wins")),
    }


@server.tool()
def get_race(year: int, round: int) -> dict[str, Any]:
    """Result, grid, qualifying order and pit stop count of one race."""
    r = races.race(year, round)
    return {
        "race": {k: r["race"][k] for k in ("year", "round", "date", "grand_prix", "circuit", "laps", "distance")},
        "results": _trim(
            r["results"],
            (
                "position",
                "position_text",
                "driver",
                "constructor",
                "grid",
                "laps",
                "time",
                "gap",
                "reason_retired",
                "points",
                "fastest_lap",
            ),
        ),
        "qualifying": _trim(r["qualifying"], ("position", "driver", "constructor", "q1", "q2", "q3", "time")),
        "has_lap_data": r["has_laps"],
    }


@server.tool()
def race_story(year: int, round: int) -> dict[str, Any]:
    """Key moments of a race lap by lap: start, lead changes, pit stops, retirements, safety cars, penalties."""
    s = analysis.story(year, round)
    return {
        "periods": s["periods"],
        "rain": s["rain"],
        "events": [{"lap": e["lap"], "kind": e["kind"], "text": e["text"]} for e in s["events"]],
    }


@server.tool()
def race_strategy(year: int, round: int) -> dict[str, Any]:
    """Tyre stints per driver (compounds 2018+), time lost per pit stop, and undercut/overcut verdicts."""
    s = analysis.strategy(year, round)
    return {
        "pit_loss_s": s["pit_loss_s"],
        "drivers": [
            {
                "driver": d["name"],
                "position": d["position_text"],
                "stints": _trim(d["stints"], ("compound", "from_lap", "to_lap", "laps", "degradation_s_per_lap")),
            }
            for d in s["drivers"]
        ],
        "battles": s["battles"],
        "method": s["method"],
    }


@server.tool()
def get_driver(driver_id: str) -> dict[str, Any]:
    """Career totals, seasons, and the head-to-head record against every teammate."""
    d = drivers.driver(driver_id)
    return {
        "driver": d["driver"],
        "milestones": d["milestones"],
        "seasons": _trim(d["seasons"], ("year", "position", "points", "wins", "podiums", "poles", "constructors")),
        "teammates": _trim(
            d["teammates"],
            (
                "name",
                "constructors",
                "first_year",
                "last_year",
                "races",
                "quali_won",
                "quali_lost",
                "race_won",
                "race_lost",
                "median_gap_pct",
            ),
        ),
    }


@server.tool()
def teammate_head_to_head(driver_id: str, teammate_id: str) -> dict[str, Any]:
    """Qualifying and race duels between two teammates, overall and per season."""
    h = teammates.head_to_head(driver_id, teammate_id)
    return {"driver": h["driver"], "teammate": h["mate"], "summary": h["summary"], "seasons": h["seasons"]}


@server.tool()
def compare_drivers(driver_ids: list[str]) -> dict[str, Any]:
    """Career totals of up to four drivers side by side, and their records against each other as teammates."""
    c = drivers.compare(",".join(driver_ids))
    return {"drivers": [x["driver"] for x in c["drivers"]], "teammate_pairs": c["teammate_pairs"]}


@server.tool()
def all_time_records(board: str = "wins", limit: int = 20) -> dict[str, Any]:
    """All-time leaderboards. Boards: wins, poles, podiums, championships, starts, fastest-laps, grand-slams,
    win-rate, wins-in-a-season, consecutive-wins, youngest-winner, oldest-winner, starts-without-a-win,
    constructor-wins, constructor-championships, one-twos, constructor-poles."""
    return records.board(board, limit=limit)


@server.tool()
def explore_results(
    group: str = "driver",
    year_from: int = 1950,
    year_to: int = 2100,
    circuit: str | None = None,
    constructor: str | None = None,
    driver: str | None = None,
    teammate: str | None = None,
    grid_min: int | None = None,
    grid_max: int | None = None,
    start_tyre: str | None = None,
    min_races: int = 1,
    sort: str = "wins",
    limit: int = 25,
) -> dict[str, Any]:
    """Aggregate race results with any filters, grouped by driver, constructor, season, circuit or driver_season.
    Example: wins from outside the top 3 at Monaco: group=driver, circuit=monaco, grid_min=4."""
    return explore.explore(
        group=group,
        year_from=year_from,
        year_to=year_to,
        circuit=circuit,
        constructor=constructor,
        driver=driver,
        teammate=teammate,
        grid_min=grid_min,
        grid_max=grid_max,
        start_tyre=start_tyre,
        min_races=min_races,
        sort=sort,
        limit=limit,
    )


@server.tool()
def driver_ratings(
    model: str = "combined", min_comparisons: int = 40, year_from: int = 1950, year_to: int = 2100, limit: int = 25
) -> dict[str, Any]:
    """Cross-era driver rating from chained teammate comparisons (model: combined, qualifying or race), with 90%
    intervals. Higher is better; it is relative to the typical teammate gap of each driver's era."""
    r = insights.ratings(
        model=model, min_comparisons=min_comparisons, year_from=year_from, year_to=year_to, limit=limit
    )
    r["rows"] = _trim(
        r["rows"], ("rank", "name", "skill", "low", "high", "comparisons", "teammates", "first_year", "last_year")
    )
    return r


@server.tool()
def title_odds(year: int, after_round: int | None = None) -> dict[str, Any]:
    """Chance of each driver winning the title by simulating the remaining races, and who can still win."""
    o = insights.title_odds(year, after=after_round)
    if not o.get("available"):
        return o
    return {
        "year": year,
        **{k: o["current"][k] for k in ("after_round", "remaining_races", "remaining_sprints")},
        "drivers": [d for d in o["current"]["drivers"] if d["probability"] > 0 or d["can_still_win"]],
    }


@server.tool()
def qualifying_analysis(year: int, round: int, session: str = "Q") -> dict[str, Any]:
    """Best laps, best sectors and ideal laps of a qualifying session (2018+). session: Q or SQ."""
    q = telemetry.qualifying_analysis(year, round, session=session)
    q["rows"] = _trim(
        q["rows"], ("name", "best_ms", "gap_ms", "s1_ms", "s2_ms", "s3_ms", "ideal_ms", "left_on_table_ms", "top_speed")
    )
    return q


@server.tool()
def simulate_strategy(
    year: int, round: int, driver: str, stops: list[int] | None = None, compounds: list[str] | None = None
) -> dict[str, Any]:
    """What if a driver had pitted on other laps or fitted other tyres (2018+)? stops: laps the driver pits at the
    end of; compounds: one per stint (SOFT, MEDIUM, HARD, INTERMEDIATE, WET). Leave both out to see the real plan
    and the fitted tyre model. A model of the race, not a replay: traffic and rivals reacting are not modelled."""
    s = simulate.simulate_race(
        year,
        round,
        driver,
        None if stops is None else ",".join(map(str, stops)),
        None if compounds is None else ",".join(compounds),
    )
    return {
        k: s[k]
        for k in (
            "driver",
            "pit_loss_s",
            "model",
            "actual",
            "plan",
            "time_change_s",
            "position",
            "ahead",
            "behind",
            "best",
            "periods",
            "warnings",
        )
    }


@server.tool()
def circuit_conditions(circuit_id: str | None = None) -> dict[str, Any]:
    """Safety cars, virtual safety cars, red flags and wet races (2018+). With a circuit id: race by race at that
    circuit; without: every circuit ranked by the chance of a safety car."""
    if circuit_id:
        return conditions.circuit(circuit_id)
    return conditions.all_circuits(min_races=3)


@server.tool()
def car_ratings(year: int | None = None, constructor_id: str | None = None) -> dict[str, Any]:
    """Car performance from qualifying pace with the drivers taken out, as a gap (%) to the fastest car of the
    season. With a year: every car that season; with a constructor id: that team's cars season by season; with
    neither: the most dominant cars of all time and constructors ranked by how fast their cars usually were."""
    if year is not None:
        return insights.car_ratings_season(year)
    if constructor_id:
        return insights.car_ratings_team(constructor_id)
    r = insights.car_ratings(min_seasons=5, limit=15)
    r.pop("fastest")
    return r


@server.tool()
def compare_laps(year: int, round: int, driver_a: str, driver_b: str, session: str = "Q") -> dict[str, Any]:
    """Compare two drivers' fastest laps in a session (2018+): lap and sector times, top speed, clipping, in how
    many of 25 track sections each was faster, and the time gained corner by corner (positive: driver_a quicker),
    with minimum speeds and braking points. session: Q, SQ, S or R."""
    c = telemetry.compare_laps(year, round, session=session, drivers=f"{driver_a},{driver_b}")
    out = {}
    for d in c["drivers"]:
        lap = c["laps"][d]
        out[d] = {
            "lap": lap["lap"],
            "lap_time_ms": lap["lap_time_ms"],
            "sectors": lap["sectors"],
            **{k: c["straights"][d][k] for k in ("top_speed_kmh", "full_throttle_pct", "clipping_m")},
            "sections_won": sum(1 for s in c.get("dominance", []) if s["driver_id"] == d),
        }
    cd = c.get("corner_deltas") or {}
    return {
        "session": c["session"]["name"],
        "laps": out,
        "lap_gap_s": cd.get("lap_gap_s"),
        "straights_s": cd.get("straights_s"),
        "corners": [
            {k: x[k] for k in ("corner", "gain_s", "min_speed", "brake_before_apex_m")}
            for x in cd.get("corners", [])
            if x["reliable"]
        ],
        "corners_not_measured": [x["corner"] for x in cd.get("corners", []) if not x["reliable"]],
    }


@server.tool()
def race_pace_ranking(year: int, round: int) -> dict[str, Any]:
    """Every driver's race pace (1996+): median fuel-corrected green-flag lap, the spread of their laps (25th to
    75th percentile), the gap to the fastest and to their teammate, and where they finished."""
    r = analysis.pace_ranking(year, round)
    return {
        "has_timing": r["has_timing"],
        "rows": _trim(
            r["rows"],
            ("rank", "name", "constructor", "position", "laps", "median_s", "q25_s", "q75_s", "gap_s", "teammate"),
        ),
        "not_ranked": r["too_few_laps"],
    }


def main() -> None:
    server.run()
