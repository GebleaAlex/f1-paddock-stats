from collections import defaultdict

from fastapi import APIRouter

from ..db import db

router = APIRouter(prefix="/races", tags=["races"])

ENTRY_COLUMNS = """
    x.driver_id, d.name AS driver, d.abbreviation, x.driver_number,
    x.constructor_id, c.name AS constructor, x.engine_manufacturer_id, em.name AS engine
"""
ENTRY_JOINS = """
    JOIN driver d ON d.id = x.driver_id
    JOIN constructor c ON c.id = x.constructor_id
    LEFT JOIN engine_manufacturer em ON em.id = x.engine_manufacturer_id
"""


def _race(year: int, round_: int) -> dict:
    return db.one_or_404(
        """
        SELECT r.id, r.year, r.round, r.date, r.time, r.official_name, r.qualifying_format,
               r.laps, r.scheduled_laps, r.distance, r.course_length, r.turns, r.direction,
               (r.sprint_race_date IS NOT NULL
                OR EXISTS (SELECT 1 FROM sprint_race_result s WHERE s.race_id = r.id)) AS has_sprint,
               r.drivers_championship_decider, r.constructors_championship_decider,
               gp.id AS grand_prix_id, gp.full_name AS grand_prix, gp.name AS grand_prix_short,
               ci.id AS circuit_id, ci.name AS circuit, ci.full_name AS circuit_full_name, ci.place_name,
               co.name AS country, co.alpha2_code AS country_code, r.circuit_layout_id, lp.path AS layout_path
        FROM race r
        JOIN grand_prix gp ON gp.id = r.grand_prix_id
        JOIN circuit ci ON ci.id = r.circuit_id
        JOIN country co ON co.id = ci.country_id
        LEFT JOIN circuit_layout_path lp ON lp.layout_id = r.circuit_layout_id
        WHERE r.year = ? AND r.round = ?
        """,
        [year, round_],
        "Race",
    )


@router.get("/{year}/{round_}")
def race(year: int, round_: int):
    r = _race(year, round_)
    rid = r["id"]
    results = db.rows(
        f"""
        SELECT x.position_number AS position, x.position_text, {ENTRY_COLUMNS},
               x.laps, x.time, x.gap, x.gap_laps, x.interval, x.reason_retired, rc.category AS retirement_category,
               x.points, x.grid_position_number AS grid, x.positions_gained, x.pit_stops, x.fastest_lap,
               x.pole_position, x.driver_of_the_day, x.grand_slam, x.time_penalty
        FROM race_result x {ENTRY_JOINS}
        LEFT JOIN retirement_reason rc ON rc.reason = x.reason_retired
        WHERE x.race_id = ? ORDER BY x.position_display_order
        """,
        [rid],
    )
    qualifying = db.rows(
        f"""
        SELECT x.position_number AS position, x.position_text, {ENTRY_COLUMNS},
               x.time, x.time_millis, x.q1, x.q1_millis, x.q2, x.q2_millis, x.q3, x.q3_millis, x.gap, x.laps
        FROM qualifying_result x {ENTRY_JOINS}
        WHERE x.race_id = ? ORDER BY x.position_display_order
        """,
        [rid],
    )
    sprint = db.rows(
        f"""
        SELECT x.position_number AS position, x.position_text, {ENTRY_COLUMNS},
               x.laps, x.time, x.gap, x.reason_retired, x.points, x.grid_position_number AS grid
        FROM sprint_race_result x {ENTRY_JOINS}
        WHERE x.race_id = ? ORDER BY x.position_display_order
        """,
        [rid],
    )
    pit_stops = db.rows(
        f"""
        SELECT {ENTRY_COLUMNS}, x.stop, x.lap, x.time AS duration, x.time_millis AS duration_ms
        FROM pit_stop x {ENTRY_JOINS}
        WHERE x.race_id = ? ORDER BY x.lap, x.position_display_order
        """,
        [rid],
    )
    fastest_laps = db.rows(
        f"""
        SELECT x.position_number AS position, {ENTRY_COLUMNS}, x.lap, x.time, x.time_millis, x.gap
        FROM fastest_lap x {ENTRY_JOINS}
        WHERE x.race_id = ? ORDER BY x.position_display_order
        """,
        [rid],
    )
    standings = db.rows(
        """
        SELECT s.position_number AS position, s.driver_id, d.name AS driver, d.abbreviation, s.points,
               s.positions_gained, s.championship_won
        FROM race_driver_standing s JOIN driver d ON d.id = s.driver_id
        WHERE s.race_id = ? ORDER BY s.position_display_order LIMIT 10
        """,
        [rid],
    )
    neighbours = db.rows(
        """
        SELECT r.year, r.round, gp.full_name AS grand_prix FROM race r JOIN grand_prix gp ON gp.id = r.grand_prix_id
        WHERE r.date IN (
            (SELECT max(date) FROM race WHERE date < (SELECT date FROM race WHERE id = $id)),
            (SELECT min(date) FROM race WHERE date > (SELECT date FROM race WHERE id = $id))
        ) ORDER BY r.date
        """,
        {"id": rid},
    )
    prev = next((n for n in neighbours if (n["year"], n["round"]) < (year, round_)), None)
    nxt = next((n for n in neighbours if (n["year"], n["round"]) > (year, round_)), None)
    has_laps = db.scalar("SELECT count(*) > 0 FROM lap WHERE race_id = ?", [rid])
    return {
        "race": r,
        "results": results,
        "qualifying": qualifying,
        "sprint": sprint,
        "pit_stops": pit_stops,
        "fastest_laps": fastest_laps,
        "standings": standings,
        "has_laps": has_laps,
        "prev": prev,
        "next": nxt,
    }


@router.get("/{year}/{round_}/laps")
def race_laps(year: int, round_: int):
    """Lap-by-lap position and time for every driver (1996+), plus pit stops and retirements, in compact arrays."""
    r = _race(year, round_)
    rid = r["id"]
    drivers = db.rows(
        f"""
        SELECT {ENTRY_COLUMNS}, x.position_number AS position, x.position_text, x.grid_position_number AS grid,
               x.laps, x.reason_retired
        FROM race_result x {ENTRY_JOINS}
        WHERE x.race_id = ? AND x.driver_id IN (SELECT driver_id FROM lap WHERE race_id = ?)
        ORDER BY x.position_display_order
        """,
        [rid, rid],
    )
    laps: dict[str, list] = defaultdict(list)
    for row in db.rows("SELECT driver_id, lap, position, time_ms FROM lap WHERE race_id = ? ORDER BY lap", [rid]):
        laps[row["driver_id"]].append([row["lap"], row["position"], row["time_ms"]])
    pits = db.rows(
        "SELECT driver_id, stop, lap, time_millis AS duration_ms FROM pit_stop WHERE race_id = ? ORDER BY lap", [rid]
    )
    return {
        "race": {k: r[k] for k in ("id", "year", "round", "grand_prix", "laps", "date")},
        "drivers": drivers,
        "laps": laps,
        "pit_stops": pits,
    }
