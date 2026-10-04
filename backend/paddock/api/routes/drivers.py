from fastapi import APIRouter, HTTPException, Query

from ..db import db
from .teammates import teammates_of

router = APIRouter(prefix="/drivers", tags=["drivers"])

TOTALS = """
    d.total_race_entries AS entries, d.total_race_starts AS starts, d.total_race_wins AS wins,
    d.total_podiums AS podiums, d.total_pole_positions AS poles, d.total_fastest_laps AS fastest_laps,
    d.total_points AS points, d.total_championship_wins AS championships, d.total_race_laps AS laps,
    d.total_grand_slams AS grand_slams, d.total_sprint_race_wins AS sprint_wins,
    d.best_championship_position, d.best_race_result, d.best_starting_grid_position AS best_grid
"""


@router.get("")
def list_drivers():
    """Every driver with career totals and first/last season. About 900 rows; the client filters and sorts."""
    return db.rows(
        f"""
        SELECT d.id, d.name, d.abbreviation, d.date_of_birth, d.nationality_country_id,
               n.name AS nationality, n.alpha2_code AS nationality_code, {TOTALS},
               s.first_year, s.last_year
        FROM driver d
        LEFT JOIN country n ON n.id = d.nationality_country_id
        LEFT JOIN (SELECT driver_id, min(year) AS first_year, max(year) AS last_year FROM season_driver
                   WHERE total_race_entries > 0 GROUP BY 1) s
               ON s.driver_id = d.id
        ORDER BY d.total_race_wins DESC, d.total_race_starts DESC, d.name
        """
    )


@router.get("/{driver_id}")
def driver(driver_id: str):
    d = db.one_or_404(
        f"""
        SELECT d.id, d.name, d.first_name, d.last_name, d.full_name, d.abbreviation, d.permanent_number,
               d.date_of_birth, d.date_of_death, d.place_of_birth,
               n.name AS nationality_country, n.demonym AS nationality, n.alpha2_code AS nationality_code,
               b.name AS birth_country, {TOTALS}
        FROM driver d
        LEFT JOIN country n ON n.id = d.nationality_country_id
        LEFT JOIN country b ON b.id = d.country_of_birth_country_id
        WHERE d.id = ?
        """,
        [driver_id],
        "Driver",
    )
    seasons = db.rows(
        """
        SELECT sd.year, sd.position_number AS position, sd.position_text, st.points,
               sd.total_race_starts AS starts, sd.total_race_wins AS wins, sd.total_podiums AS podiums,
               sd.total_pole_positions AS poles, sd.total_fastest_laps AS fastest_laps,
               (SELECT list(DISTINCT {'id': c.id, 'name': c.name})
                  FROM season_entrant_driver e JOIN constructor c ON c.id = e.constructor_id
                 WHERE e.year = sd.year AND e.driver_id = sd.driver_id AND NOT e.test_driver) AS constructors
        FROM season_driver sd
        LEFT JOIN season_driver_standing st ON st.year = sd.year AND st.driver_id = sd.driver_id
        WHERE sd.driver_id = ? AND sd.total_race_entries > 0
        ORDER BY sd.year
        """,
        [driver_id],
    )
    finishes = db.rows(
        """
        SELECT CASE WHEN rr.position_number IS NOT NULL THEN CAST(rr.position_number AS VARCHAR)
                    WHEN rr.position_text IN ('DNF', 'NC') THEN coalesce(rc.category, 'technical')
                    ELSE rr.position_text END AS outcome,
               count(*) AS n
        FROM race_result rr LEFT JOIN retirement_reason rc ON rc.reason = rr.reason_retired
        WHERE rr.driver_id = ? GROUP BY 1
        """,
        [driver_id],
    )
    milestones = db.one(
        """
        SELECT
            (SELECT {'year': r.year, 'round': r.round, 'grand_prix': gp.full_name} FROM race_result rr
               JOIN race r ON r.id = rr.race_id JOIN grand_prix gp ON gp.id = r.grand_prix_id
              WHERE rr.driver_id = $id ORDER BY r.date LIMIT 1) AS first_race,
            (SELECT {'year': r.year, 'round': r.round, 'grand_prix': gp.full_name} FROM race_result rr
               JOIN race r ON r.id = rr.race_id JOIN grand_prix gp ON gp.id = r.grand_prix_id
              WHERE rr.driver_id = $id ORDER BY r.date DESC LIMIT 1) AS last_race,
            (SELECT {'year': r.year, 'round': r.round, 'grand_prix': gp.full_name} FROM race_result rr
               JOIN race r ON r.id = rr.race_id JOIN grand_prix gp ON gp.id = r.grand_prix_id
              WHERE rr.driver_id = $id AND rr.position_number = 1 ORDER BY r.date LIMIT 1) AS first_win,
            (SELECT {'year': r.year, 'round': r.round, 'grand_prix': gp.full_name} FROM race_result rr
               JOIN race r ON r.id = rr.race_id JOIN grand_prix gp ON gp.id = r.grand_prix_id
              WHERE rr.driver_id = $id AND rr.position_number = 1 ORDER BY r.date DESC LIMIT 1) AS last_win
        """,
        {"id": driver_id},
    )
    family = db.rows(
        """
        SELECT f.other_driver_id AS driver_id, o.name, f.type FROM driver_family_relationship f
        JOIN driver o ON o.id = f.other_driver_id WHERE f.driver_id = ? ORDER BY f.position_display_order
        """,
        [driver_id],
    )
    return {
        "driver": d,
        "milestones": milestones,
        "seasons": seasons,
        "finishes": finishes,
        "teammates": teammates_of(driver_id),
        "family": family,
    }


@router.get("/{driver_id}/results")
def driver_results(driver_id: str):
    """Every race entry of the driver, oldest first, with cumulative counters for career charts."""
    if not db.one("SELECT 1 FROM driver WHERE id = ?", [driver_id]):
        raise HTTPException(404, "Driver not found")
    return db.rows(
        """
        SELECT r.year, r.round, r.date, gp.full_name AS grand_prix, gp.abbreviation, rr.constructor_id,
               c.name AS constructor, rr.grid_position_number AS grid, rr.position_number AS position,
               rr.position_text, rr.points, rr.reason_retired, rc.category AS retirement_category,
               rr.fastest_lap, rr.pole_position,
               date_diff('day', d.date_of_birth, r.date) / 365.25 AS age
        FROM race_result rr
        JOIN race r ON r.id = rr.race_id
        JOIN grand_prix gp ON gp.id = r.grand_prix_id
        JOIN constructor c ON c.id = rr.constructor_id
        JOIN driver d ON d.id = rr.driver_id
        LEFT JOIN retirement_reason rc ON rc.reason = rr.reason_retired
        WHERE rr.driver_id = ?
        ORDER BY r.date
        """,
        [driver_id],
    )


compare_router = APIRouter(tags=["drivers"])


@compare_router.get("/compare")
def compare(drivers: str = Query(..., description="Comma-separated driver ids, 2 to 4")):
    """Career series for up to four drivers, aligned by start number and by age."""
    ids = [d for d in dict.fromkeys(x.strip() for x in drivers.split(",")) if d][:4]
    if len(ids) < 1:
        raise HTTPException(400, "Give at least one driver id")
    out = []
    for driver_id in ids:
        info = db.one(
            f"""
            SELECT d.id, d.name, d.abbreviation, d.date_of_birth, n.alpha2_code AS nationality_code, {TOTALS},
                   (SELECT min(year) FROM season_driver
                     WHERE driver_id = d.id AND total_race_entries > 0) AS first_year,
                   (SELECT max(year) FROM season_driver
                     WHERE driver_id = d.id AND total_race_entries > 0) AS last_year
            FROM driver d LEFT JOIN country n ON n.id = d.nationality_country_id WHERE d.id = ?
            """,
            [driver_id],
        )
        if info is None:
            raise HTTPException(404, f"Driver not found: {driver_id}")
        series = db.rows(
            """
            SELECT r.year, r.round, gp.abbreviation,
                   round(date_diff('day', d.date_of_birth, r.date) / 365.25, 2) AS age,
                   rr.position_number AS position, rr.grid_position_number AS grid,
                   sum(CASE WHEN rr.position_number = 1 THEN 1 ELSE 0 END) OVER w AS wins,
                   sum(CASE WHEN rr.position_number <= 3 THEN 1 ELSE 0 END) OVER w AS podiums,
                   sum(CASE WHEN rr.pole_position THEN 1 ELSE 0 END) OVER w AS poles,
                   sum(coalesce(rr.points, 0)) OVER w AS points
            FROM race_result rr JOIN race r ON r.id = rr.race_id JOIN grand_prix gp ON gp.id = r.grand_prix_id
            JOIN driver d ON d.id = rr.driver_id
            WHERE rr.driver_id = ? AND rr.position_text NOT IN ('DNQ', 'DNPQ', 'DNS', 'DNP', 'EX')
            WINDOW w AS (ORDER BY r.date ROWS UNBOUNDED PRECEDING)
            ORDER BY r.date
            """,
            [driver_id],
        )
        seasons = db.rows(
            """
            SELECT year, position_number AS position FROM season_driver
            WHERE driver_id = ? AND total_race_entries > 0 ORDER BY year
            """,
            [driver_id],
        )
        out.append({"driver": info, "starts": series, "seasons": seasons})
    pairs = []
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            mates = [t for t in teammates_of(a) if t["driver_id"] == b]
            if mates:
                pairs.append({"driver_a": a, "driver_b": b, **mates[0]})
    return {"drivers": out, "teammate_pairs": pairs}
