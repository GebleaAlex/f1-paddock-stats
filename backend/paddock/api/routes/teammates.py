"""Teammate head-to-head, built on the `teammate_race` table (one row per pair of teammates per race).

Conventions, used everywhere:
- qualifying: whoever qualified ahead wins the duel;
- race: only races where both drivers were classified count, so a mechanical failure is not a lost duel;
- qualifying gap: median over the races of the gap in the last session both set a time in, as a percentage
  (positive = slower than the teammate).
"""

from fastapi import APIRouter, HTTPException, Query

from ..db import db

router = APIRouter(prefix="/teammates", tags=["teammates"])

# The pair seen from one driver ($me), whichever side of the stored (driver_a < driver_b) pair they are on.
ORIENTED = """
    SELECT t.race_id, t.year, t.round, t.date, t.constructor_id,
           CASE WHEN t.driver_a = $me THEN t.driver_b ELSE t.driver_a END AS mate,
           CASE WHEN t.driver_a = $me THEN t.quali_pos_a ELSE t.quali_pos_b END AS quali_me,
           CASE WHEN t.driver_a = $me THEN t.quali_pos_b ELSE t.quali_pos_a END AS quali_mate,
           CASE WHEN t.driver_a = $me THEN t.race_pos_a ELSE t.race_pos_b END AS race_me,
           CASE WHEN t.driver_a = $me THEN t.race_pos_b ELSE t.race_pos_a END AS race_mate,
           CASE WHEN t.driver_a = $me THEN t.race_text_a ELSE t.race_text_b END AS race_text_me,
           CASE WHEN t.driver_a = $me THEN t.race_text_b ELSE t.race_text_a END AS race_text_mate,
           CASE WHEN t.driver_a = $me THEN t.grid_a ELSE t.grid_b END AS grid_me,
           CASE WHEN t.driver_a = $me THEN t.grid_b ELSE t.grid_a END AS grid_mate,
           CASE WHEN t.driver_a = $me THEN t.points_a ELSE t.points_b END AS points_me,
           CASE WHEN t.driver_a = $me THEN t.points_b ELSE t.points_a END AS points_mate,
           CASE WHEN t.driver_a = $me THEN t.reason_a ELSE t.reason_b END AS reason_me,
           CASE WHEN t.driver_a = $me THEN t.reason_b ELSE t.reason_a END AS reason_mate,
           CASE WHEN t.driver_a = $me THEN t.quali_gap_pct ELSE -t.quali_gap_pct END AS gap_pct
    FROM teammate_race t
    WHERE t.driver_a = $me OR t.driver_b = $me
"""

SUMMARY = """
    count(*) AS races,
    min(year) AS first_year, max(year) AS last_year,
    count(*) FILTER (WHERE quali_me < quali_mate) AS quali_won,
    count(*) FILTER (WHERE quali_me > quali_mate) AS quali_lost,
    count(*) FILTER (WHERE race_me < race_mate) AS race_won,
    count(*) FILTER (WHERE race_me > race_mate) AS race_lost,
    sum(points_me) AS points_me, sum(points_mate) AS points_mate,
    round(median(gap_pct) FILTER (WHERE abs(gap_pct) < 5), 3) AS median_gap_pct,
    count(gap_pct) FILTER (WHERE abs(gap_pct) < 5) AS gap_races
"""


def teammates_of(driver_id: str) -> list[dict]:
    return db.rows(
        f"""
        WITH o AS ({ORIENTED})
        SELECT mate AS driver_id, d.name, d.abbreviation, {SUMMARY},
               list(DISTINCT c.name) AS constructors
        FROM o JOIN driver d ON d.id = o.mate JOIN constructor c ON c.id = o.constructor_id
        GROUP BY mate, d.name, d.abbreviation
        ORDER BY min(o.date)
        """,
        {"me": driver_id},
    )


@router.get("")
def pairings(
    year_from: int = Query(1950, alias="from"),
    year_to: int = Query(2100, alias="to"),
    min_races: int = Query(10, ge=1),
    constructor: str | None = None,
):
    """Every teammate pairing in the window with at least `min_races` races together."""
    return db.rows(
        f"""
        WITH o AS (
            SELECT t.*, t.driver_a AS me_id, t.driver_b AS mate_id,
                   t.quali_pos_a AS quali_me, t.quali_pos_b AS quali_mate,
                   t.race_pos_a AS race_me, t.race_pos_b AS race_mate,
                   t.points_a AS points_me, t.points_b AS points_mate, t.quali_gap_pct AS gap_pct
            FROM teammate_race t
            WHERE t.year BETWEEN $from AND $to AND ($constructor IS NULL OR t.constructor_id = $constructor)
        )
        SELECT me_id AS driver_a, da.name AS name_a, mate_id AS driver_b, db.name AS name_b, {SUMMARY},
               list(DISTINCT c.name) AS constructors
        FROM o JOIN driver da ON da.id = me_id JOIN driver db ON db.id = mate_id
        JOIN constructor c ON c.id = o.constructor_id
        GROUP BY me_id, da.name, mate_id, db.name
        HAVING count(*) >= $min
        ORDER BY races DESC
        """,
        {"from": year_from, "to": year_to, "min": min_races, "constructor": constructor},
    )


@router.get("/{driver_id}/{mate_id}")
def head_to_head(driver_id: str, mate_id: str):
    names = {
        r["id"]: r
        for r in db.rows("SELECT id, name, abbreviation FROM driver WHERE id IN (?, ?)", [driver_id, mate_id])
    }
    if len(names) < 2:
        raise HTTPException(404, "Driver not found")
    races = db.rows(
        f"""
        WITH o AS ({ORIENTED})
        SELECT o.*, gp.full_name AS grand_prix, gp.abbreviation, c.name AS constructor
        FROM o JOIN race r ON r.id = o.race_id JOIN grand_prix gp ON gp.id = r.grand_prix_id
        JOIN constructor c ON c.id = o.constructor_id
        WHERE o.mate = $mate ORDER BY o.date
        """,
        {"me": driver_id, "mate": mate_id},
    )
    if not races:
        raise HTTPException(404, "These drivers were never teammates")
    summary = db.one(
        f"WITH o AS ({ORIENTED}) SELECT {SUMMARY} FROM o WHERE mate = $mate", {"me": driver_id, "mate": mate_id}
    )
    seasons = db.rows(
        f"WITH o AS ({ORIENTED}) SELECT year, {SUMMARY} FROM o WHERE mate = $mate GROUP BY year ORDER BY year",
        {"me": driver_id, "mate": mate_id},
    )
    return {"driver": names[driver_id], "mate": names[mate_id], "summary": summary, "seasons": seasons, "races": races}
