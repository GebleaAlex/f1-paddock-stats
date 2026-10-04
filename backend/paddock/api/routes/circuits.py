from fastapi import APIRouter

from ..db import db

router = APIRouter(prefix="/circuits", tags=["circuits"])


@router.get("")
def list_circuits():
    return db.rows(
        """
        SELECT ci.id, ci.name, ci.full_name, ci.type, ci.direction, ci.place_name, co.name AS country,
               co.alpha2_code AS country_code, ci.latitude, ci.longitude, ci.length, ci.turns,
               ci.total_races_held AS races, y.first_year, y.last_year, lp.path AS layout_path
        FROM circuit ci
        JOIN country co ON co.id = ci.country_id
        LEFT JOIN (SELECT circuit_id, min(year) AS first_year, max(year) AS last_year FROM race GROUP BY 1) y
               ON y.circuit_id = ci.id
        LEFT JOIN (SELECT circuit_id, arg_max(circuit_layout_id, date) AS layout_id FROM race GROUP BY 1) l
               ON l.circuit_id = ci.id
        LEFT JOIN circuit_layout_path lp ON lp.layout_id = l.layout_id
        ORDER BY ci.total_races_held DESC, ci.name
        """
    )


@router.get("/{circuit_id}")
def circuit(circuit_id: str):
    c = db.one_or_404(
        """
        SELECT ci.id, ci.name, ci.full_name, ci.previous_names, ci.type, ci.direction, ci.place_name,
               co.name AS country, co.alpha2_code AS country_code, ci.latitude, ci.longitude, ci.length, ci.turns,
               ci.total_races_held AS races
        FROM circuit ci JOIN country co ON co.id = ci.country_id WHERE ci.id = ?
        """,
        [circuit_id],
        "Circuit",
    )
    layouts = db.rows(
        """
        SELECT l.id, l.length, l.turns, lp.path, min(r.year) AS first_year, max(r.year) AS last_year,
               count(r.id) AS races
        FROM circuit_layout l
        LEFT JOIN circuit_layout_path lp ON lp.layout_id = l.id
        LEFT JOIN race r ON r.circuit_layout_id = l.id
        WHERE l.circuit_id = ?
        GROUP BY l.id, l.length, l.turns, lp.path
        ORDER BY min(r.year) NULLS LAST
        """,
        [circuit_id],
    )
    races = db.rows(
        """
        SELECT r.year, r.round, gp.full_name AS grand_prix, r.circuit_layout_id AS layout_id, r.laps,
               w.driver_id AS winner_id, wd.name AS winner, w.constructor_id AS winner_constructor_id,
               wc.name AS winner_constructor, w.grid_position_number AS winner_grid,
               p.driver_id AS pole_id, pd.name AS pole,
               fl.driver_id AS fastest_lap_id, fd.name AS fastest_lap_driver, fl.time AS fastest_lap_time,
               fl.time_millis AS fastest_lap_ms
        FROM race r
        JOIN grand_prix gp ON gp.id = r.grand_prix_id
        LEFT JOIN race_result w ON w.race_id = r.id AND w.position_number = 1
        LEFT JOIN driver wd ON wd.id = w.driver_id
        LEFT JOIN constructor wc ON wc.id = w.constructor_id
        LEFT JOIN starting_grid_position p ON p.race_id = r.id AND p.position_number = 1
        LEFT JOIN driver pd ON pd.id = p.driver_id
        LEFT JOIN fastest_lap fl ON fl.race_id = r.id AND fl.position_number = 1
        LEFT JOIN driver fd ON fd.id = fl.driver_id
        WHERE r.circuit_id = ?
        ORDER BY r.date DESC
        """,
        [circuit_id],
    )
    done = [r for r in races if r["winner_id"]]
    from_pole = sum(1 for r in done if r["winner_grid"] == 1)
    top_drivers = db.rows(
        """
        SELECT rr.driver_id AS id, d.name, count(*) AS wins FROM race_result rr
        JOIN race r ON r.id = rr.race_id JOIN driver d ON d.id = rr.driver_id
        WHERE r.circuit_id = ? AND rr.position_number = 1 GROUP BY ALL ORDER BY wins DESC, d.name LIMIT 5
        """,
        [circuit_id],
    )
    top_constructors = db.rows(
        """
        SELECT rr.constructor_id AS id, c.name, count(*) AS wins FROM race_result rr
        JOIN race r ON r.id = rr.race_id JOIN constructor c ON c.id = rr.constructor_id
        WHERE r.circuit_id = ? AND rr.position_number = 1 GROUP BY ALL ORDER BY wins DESC, c.name LIMIT 5
        """,
        [circuit_id],
    )
    return {
        "circuit": c,
        "layouts": layouts,
        "races": races,
        "stats": {
            "races": len(done),
            "won_from_pole": from_pole,
            "won_from_outside_top3": sum(1 for r in done if (r["winner_grid"] or 99) > 3),
            "different_winners": len({r["winner_id"] for r in done}),
        },
        "most_wins": {"drivers": top_drivers, "constructors": top_constructors},
    }
