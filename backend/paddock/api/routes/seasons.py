from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query

from ...eras import era_for
from ...scoring import BY_ID, SYSTEMS, points_for
from ..db import db

router = APIRouter(prefix="/seasons", tags=["seasons"])


@router.get("")
def list_seasons():
    return db.rows(
        """
        SELECT s.year,
               (SELECT count(*) FROM race r WHERE r.year = s.year) AS races,
               dc.driver_id AS driver_champion_id, d.name AS driver_champion,
               cc.constructor_id AS constructor_champion_id, c.name AS constructor_champion
        FROM season s
        LEFT JOIN season_driver_standing dc ON dc.year = s.year AND dc.position_number = 1
        LEFT JOIN driver d ON d.id = dc.driver_id
        LEFT JOIN season_constructor_standing cc ON cc.year = s.year AND cc.position_number = 1
        LEFT JOIN constructor c ON c.id = cc.constructor_id
        ORDER BY s.year DESC
        """
    )


def _require_season(year: int) -> None:
    if not db.one("SELECT 1 FROM season WHERE year = ?", [year]):
        raise HTTPException(404, "Season not found")


@router.get("/{year}")
def season(year: int):
    _require_season(year)
    races = db.rows(
        """
        SELECT r.id, r.round, r.date, gp.id AS grand_prix_id, gp.full_name AS grand_prix, gp.abbreviation,
               r.circuit_id, ci.name AS circuit, ci.place_name, co.name AS country, co.alpha2_code AS country_code,
               (r.sprint_race_date IS NOT NULL
                OR EXISTS (SELECT 1 FROM sprint_race_result s WHERE s.race_id = r.id)) AS has_sprint,
               w.driver_id AS winner_id, wd.name AS winner, w.constructor_id AS winner_constructor_id,
               wc.name AS winner_constructor,
               p.driver_id AS pole_id, pd.name AS pole,
               EXISTS (SELECT 1 FROM race_result x WHERE x.race_id = r.id) AS completed
        FROM race r
        JOIN grand_prix gp ON gp.id = r.grand_prix_id
        JOIN circuit ci ON ci.id = r.circuit_id
        JOIN country co ON co.id = ci.country_id
        LEFT JOIN race_result w ON w.race_id = r.id AND w.position_number = 1
        LEFT JOIN driver wd ON wd.id = w.driver_id
        LEFT JOIN constructor wc ON wc.id = w.constructor_id
        LEFT JOIN starting_grid_position p ON p.race_id = r.id AND p.position_number = 1
        LEFT JOIN driver pd ON pd.id = p.driver_id
        WHERE r.year = ?
        ORDER BY r.round
        """,
        [year],
    )
    drivers = db.rows(
        """
        SELECT st.position_number AS position, st.position_text, st.driver_id, d.name, d.abbreviation,
               d.nationality_country_id, n.alpha2_code AS nationality_code, st.points,
               sd.total_race_wins AS wins, sd.total_podiums AS podiums, sd.total_pole_positions AS poles,
               sd.total_race_starts AS starts,
               (SELECT list(DISTINCT e.constructor_id ORDER BY e.constructor_id) FROM season_entrant_driver e
                 WHERE e.year = st.year AND e.driver_id = st.driver_id AND NOT e.test_driver) AS constructor_ids
        FROM season_driver_standing st
        JOIN driver d ON d.id = st.driver_id
        LEFT JOIN country n ON n.id = d.nationality_country_id
        LEFT JOIN season_driver sd ON sd.year = st.year AND sd.driver_id = st.driver_id
        WHERE st.year = ?
        ORDER BY st.position_display_order
        """,
        [year],
    )
    constructors = db.rows(
        """
        SELECT st.position_number AS position, st.position_text, st.constructor_id, c.name,
               st.engine_manufacturer_id, em.name AS engine, st.points,
               sc.total_race_wins AS wins, sc.total_podiums AS podiums, sc.total_pole_positions AS poles
        FROM season_constructor_standing st
        JOIN constructor c ON c.id = st.constructor_id
        LEFT JOIN engine_manufacturer em ON em.id = st.engine_manufacturer_id
        LEFT JOIN season_constructor sc ON sc.year = st.year AND sc.constructor_id = st.constructor_id
        WHERE st.year = ?
        ORDER BY st.position_display_order
        """,
        [year],
    )
    names = {
        r["id"]: r["name"]
        for r in db.rows(
            "SELECT DISTINCT c.id, c.name FROM season_entrant_constructor e"
            " JOIN constructor c ON c.id = e.constructor_id WHERE e.year = ?",
            [year],
        )
    }
    for d in drivers:
        d["constructors"] = [{"id": c, "name": names.get(c, c)} for c in (d.pop("constructor_ids") or [])]
    bounds = db.one("SELECT min(year) AS first, max(year) AS last FROM season")
    return {
        "year": year,
        "races": races,
        "driver_standings": drivers,
        "constructor_standings": constructors,
        "era": era_for(year),
        "prev": year - 1 if year > bounds["first"] else None,
        "next": year + 1 if year < bounds["last"] else None,
    }


@router.get("/{year}/progression")
def progression(year: int):
    """Cumulative championship points after each round, for drivers and constructors."""
    _require_season(year)
    rounds = db.rows(
        """
        SELECT r.id, r.round, gp.abbreviation, gp.full_name AS grand_prix FROM race r
        JOIN grand_prix gp ON gp.id = r.grand_prix_id
        WHERE r.year = ? AND r.id IN (SELECT race_id FROM race_driver_standing)
        ORDER BY r.round
        """,
        [year],
    )
    index = {r["id"]: i for i, r in enumerate(rounds)}

    def series(table: str, key: str, name_sql: str) -> list[dict]:
        rows = db.rows(
            f"""
            SELECT s.race_id, s.{key} AS id, {name_sql} AS name, s.points, s.position_number
            FROM {table} s JOIN race r ON r.id = s.race_id {
                "JOIN driver x ON x.id = s.driver_id"
                if key == "driver_id"
                else "JOIN constructor x ON x.id = s.constructor_id"
            }
            WHERE r.year = ?
            """,
            [year],
        )
        out: dict[str, dict] = {}
        for row in rows:
            entry = out.setdefault(
                row["id"],
                {
                    "id": row["id"],
                    "name": row["name"],
                    "points": [None] * len(rounds),
                    "positions": [None] * len(rounds),
                },
            )
            i = index[row["race_id"]]
            entry["points"][i] = row["points"]
            entry["positions"][i] = row["position_number"]
        # A driver who joins mid-season has no standing before their first race; carry values forward after it.
        for entry in out.values():
            last = 0
            for i, p in enumerate(entry["points"]):
                if p is None:
                    entry["points"][i] = last
                else:
                    last = p
        return sorted(out.values(), key=lambda e: -(e["points"][-1] or 0))

    return {
        "rounds": rounds,
        "drivers": series("race_driver_standing", "driver_id", "x.name"),
        "constructors": series("race_constructor_standing", "constructor_id", "x.name"),
    }


@router.get("/{year}/results-grid")
def results_grid(year: int):
    """Every driver's result in every race of the season, ordered by final standing."""
    _require_season(year)
    rounds = db.rows(
        """
        SELECT r.id, r.round, gp.abbreviation, gp.full_name AS grand_prix, co.alpha2_code AS country_code
        FROM race r JOIN grand_prix gp ON gp.id = r.grand_prix_id
        JOIN circuit ci ON ci.id = r.circuit_id JOIN country co ON co.id = ci.country_id
        WHERE r.year = ? ORDER BY r.round
        """,
        [year],
    )
    results = db.rows(
        """
        SELECT rr.race_id, rr.driver_id, rr.constructor_id, rr.position_number, rr.position_text, rr.points,
               rr.grid_position_number AS grid, rr.fastest_lap, rr.pole_position, rr.reason_retired,
               s.position_number AS sprint_position
        FROM race_result rr JOIN race r ON r.id = rr.race_id
        LEFT JOIN sprint_race_result s ON s.race_id = rr.race_id AND s.driver_id = rr.driver_id
        WHERE r.year = ?
        """,
        [year],
    )
    order = db.rows(
        """
        SELECT d.id, d.name, d.abbreviation, st.position_number AS position, st.points
        FROM season_driver_standing st JOIN driver d ON d.id = st.driver_id
        WHERE st.year = ? ORDER BY st.position_display_order
        """,
        [year],
    )
    by_driver: dict[str, dict] = defaultdict(dict)
    for r in results:
        by_driver[r.pop("driver_id")][r.pop("race_id")] = r
    rows = [
        {**d, "results": [by_driver[d["id"]].get(rd["id"]) for rd in rounds]} for d in order if d["id"] in by_driver
    ]
    return {"rounds": rounds, "rows": rows}


@router.get("/{year}/rescore")
def rescore(year: int, system: str = Query("2010", description="Points system id, see /api/points-systems")):
    """Driver standings for the season under another points system (Grand Prix results only, every result counts)."""
    _require_season(year)
    if system not in BY_ID:
        raise HTTPException(400, f"Unknown points system. Use one of: {', '.join(BY_ID)}")
    ps = BY_ID[system]
    results = db.rows(
        """
        SELECT rr.driver_id, d.name, d.abbreviation, rr.position_number, coalesce(rr.fastest_lap, false) AS fastest_lap
        FROM race_result rr JOIN race r ON r.id = rr.race_id JOIN driver d ON d.id = rr.driver_id
        WHERE r.year = ?
        """,
        [year],
    )
    official = {
        r["driver_id"]: r
        for r in db.rows("SELECT driver_id, position_number, points FROM season_driver_standing WHERE year = ?", [year])
    }
    table: dict[str, dict] = {}
    for r in results:
        row = table.setdefault(
            r["driver_id"],
            {
                "driver_id": r["driver_id"],
                "name": r["name"],
                "abbreviation": r["abbreviation"],
                "points": 0.0,
                "wins": 0,
                "finishes": [],
            },
        )
        row["points"] += points_for(ps, r["position_number"], r["fastest_lap"])
        row["wins"] += r["position_number"] == 1
        if r["position_number"]:
            row["finishes"].append(r["position_number"])
    # Ties are broken by count-back: most wins, then most second places, and so on.
    standings = sorted(
        table.values(),
        key=lambda x: (-x["points"], *[-x["finishes"].count(p) for p in range(1, 31)]),
    )
    out = []
    for i, row in enumerate(standings, start=1):
        if row["points"] == 0 and i > 1:
            continue
        o = official.get(row["driver_id"], {})
        out.append(
            {
                "position": i,
                "driver_id": row["driver_id"],
                "name": row["name"],
                "abbreviation": row["abbreviation"],
                "points": row["points"],
                "wins": row["wins"],
                "official_position": o.get("position_number"),
                "official_points": o.get("points"),
            }
        )
    return {"system": ps.__dict__, "standings": out}


points_router = APIRouter(tags=["seasons"])


@points_router.get("/points-systems")
def points_systems():
    return [s.__dict__ for s in SYSTEMS]
