from fastapi import APIRouter

from ..db import db

router = APIRouter(prefix="/constructors", tags=["constructors"])

TOTALS = """
    c.total_race_entries AS entries, c.total_race_starts AS starts, c.total_race_wins AS wins,
    c.total_1_and_2_finishes AS one_twos, c.total_podiums AS podiums, c.total_pole_positions AS poles,
    c.total_fastest_laps AS fastest_laps, c.total_points AS points, c.total_championship_wins AS championships,
    c.best_championship_position
"""


@router.get("")
def list_constructors():
    return db.rows(
        f"""
        SELECT c.id, c.name, c.full_name, n.name AS country, n.alpha2_code AS country_code, {TOTALS},
               s.first_year, s.last_year
        FROM constructor c
        LEFT JOIN country n ON n.id = c.country_id
        LEFT JOIN (SELECT constructor_id, min(year) AS first_year, max(year) AS last_year
                   FROM season_constructor GROUP BY 1) s ON s.constructor_id = c.id
        ORDER BY c.total_race_wins DESC, c.total_race_starts DESC, c.name
        """
    )


@router.get("/{constructor_id}")
def constructor(constructor_id: str):
    c = db.one_or_404(
        f"""
        SELECT c.id, c.name, c.full_name, n.name AS country, n.alpha2_code AS country_code, {TOTALS}
        FROM constructor c LEFT JOIN country n ON n.id = c.country_id WHERE c.id = ?
        """,
        [constructor_id],
        "Constructor",
    )
    seasons = db.rows(
        """
        SELECT sc.year, sc.position_number AS position, sc.position_text, st.points,
               sc.total_race_starts AS starts, sc.total_race_wins AS wins, sc.total_podiums AS podiums,
               sc.total_pole_positions AS poles, sc.total_1_and_2_finishes AS one_twos,
               (SELECT list(DISTINCT {'id': d.id, 'name': d.name}) FROM season_entrant_driver e
                  JOIN driver d ON d.id = e.driver_id
                 WHERE e.year = sc.year AND e.constructor_id = sc.constructor_id AND NOT e.test_driver) AS drivers,
               (SELECT list(DISTINCT {'id': ch.id, 'name': ch.name}) FROM season_entrant_chassis e JOIN chassis ch ON ch.id = e.chassis_id
                 WHERE e.year = sc.year AND e.constructor_id = sc.constructor_id) AS chassis,
               (SELECT list(DISTINCT en.full_name) FROM season_entrant_engine e JOIN engine en ON en.id = e.engine_id
                 WHERE e.year = sc.year AND e.constructor_id = sc.constructor_id) AS engines,
               (SELECT list(DISTINCT tm.name) FROM season_entrant_tyre_manufacturer e
                  JOIN tyre_manufacturer tm ON tm.id = e.tyre_manufacturer_id
                 WHERE e.year = sc.year AND e.constructor_id = sc.constructor_id) AS tyres
        FROM season_constructor sc
        LEFT JOIN (SELECT year, constructor_id, max(points) AS points FROM season_constructor_standing GROUP BY ALL) st
               ON st.year = sc.year AND st.constructor_id = sc.constructor_id
        WHERE sc.constructor_id = ?
        ORDER BY sc.year
        """,
        [constructor_id],
    )
    # Team lineage: the chain this constructor heads, and any chains it is part of.
    lineage = db.rows(
        """
        SELECT ch.constructor_id AS chain_id, ch.position_display_order AS step, ch.other_constructor_id AS id,
               o.name, ch.year_from, ch.year_to
        FROM constructor_chronology ch JOIN constructor o ON o.id = ch.other_constructor_id
        WHERE ch.constructor_id IN (
            SELECT constructor_id FROM constructor_chronology WHERE other_constructor_id = $id
            UNION SELECT $id)
        ORDER BY ch.constructor_id = $id DESC, ch.constructor_id, ch.position_display_order
        """,
        {"id": constructor_id},
    )
    reliability = db.rows(
        """
        SELECT r.year, coalesce(rc.category, 'technical') AS category, count(*) AS n
        FROM race_result rr JOIN race r ON r.id = rr.race_id
        LEFT JOIN retirement_reason rc ON rc.reason = rr.reason_retired
        WHERE rr.constructor_id = ? AND rr.position_text IN ('DNF', 'NC') GROUP BY ALL ORDER BY 1
        """,
        [constructor_id],
    )
    return {"constructor": c, "seasons": seasons, "lineage": lineage, "retirements": reliability}
