"""Driver ratings, championship odds, regulation eras and car pages."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from ...eras import ERAS, era_for
from ..db import db

router = APIRouter(tags=["insights"])

MODELS = {
    "combined": "Qualifying and race together, on a common scale",
    "qualifying": "Qualifying gap to teammates, in percent of lap time",
    "race": "Finishing places ahead of or behind teammates",
}


@router.get("/ratings")
def ratings(
    model: str = Query("combined", description="combined, qualifying or race"),
    min_comparisons: int = Query(40, ge=1),
    year_from: int = Query(1950, alias="from"),
    year_to: int = Query(2100, alias="to"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Cross-era driver rating from chained teammate comparisons, with a 90% bootstrap interval."""
    if model not in MODELS:
        raise HTTPException(400, f"model must be one of {', '.join(MODELS)}")
    rows = db.rows(
        """
        SELECT r.driver_id, d.name, n.alpha2_code AS nationality_code, r.skill, r.low, r.high, r.z, r.z_low, r.z_high,
               r.comparisons, s.first_year, s.last_year, d.total_championship_wins AS championships,
               d.total_race_wins AS wins,
               (SELECT count(DISTINCT CASE WHEN t.driver_a = r.driver_id THEN t.driver_b ELSE t.driver_a END)
                  FROM teammate_race t WHERE t.driver_a = r.driver_id OR t.driver_b = r.driver_id) AS teammates
        FROM driver_rating r JOIN driver d ON d.id = r.driver_id
        LEFT JOIN country n ON n.id = d.nationality_country_id
        LEFT JOIN (SELECT driver_id, min(year) AS first_year, max(year) AS last_year FROM season_driver
                   WHERE total_race_entries > 0 GROUP BY 1) s ON s.driver_id = r.driver_id
        WHERE r.model = $model AND r.comparisons >= $min AND s.last_year >= $from AND s.first_year <= $to
        ORDER BY r.skill DESC
        LIMIT $limit
        """,
        {"model": model, "min": min_comparisons, "from": year_from, "to": year_to, "limit": limit},
    )
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return {"model": model, "description": MODELS[model], "models": MODELS, "rows": rows}


@router.get("/ratings/{driver_id}")
def driver_rating(driver_id: str):
    rows = db.rows("SELECT model, skill, low, high, z, comparisons FROM driver_rating WHERE driver_id = ?", [driver_id])
    ranks = {}
    for r in rows:
        ranks[r["model"]] = db.scalar(
            "SELECT count(*) + 1 FROM driver_rating WHERE model = ? AND comparisons >= 40 AND skill > ?",
            [r["model"], r["skill"]],
        )
    return {"ratings": rows, "ranks": ranks}


def _season_points(year: int) -> tuple[list[dict], list[dict]]:
    races = db.rows(
        """
        SELECT r.id, r.round, gp.abbreviation, gp.full_name AS grand_prix,
               EXISTS (SELECT 1 FROM race_result x WHERE x.race_id = r.id) AS done,
               (r.sprint_race_date IS NOT NULL OR EXISTS (SELECT 1 FROM sprint_race_result s WHERE s.race_id = r.id)) AS sprint
        FROM race r JOIN grand_prix gp ON gp.id = r.grand_prix_id WHERE r.year = ? ORDER BY r.round
        """,
        [year],
    )
    results = db.rows(
        """
        SELECT r.round, x.driver_id, coalesce(x.points, 0) AS points, 'race' AS kind
        FROM race_result x JOIN race r ON r.id = x.race_id WHERE r.year = ?
        UNION ALL
        SELECT r.round, s.driver_id, coalesce(s.points, 0), 'sprint'
        FROM sprint_race_result s JOIN race r ON r.id = s.race_id WHERE r.year = ?
        """,
        [year, year],
    )
    return races, results


def _odds_after(year: int, after: int, races: list[dict], results: list[dict], sims: int, rng) -> dict:
    standings = db.rows(
        """
        SELECT s.driver_id, d.name, s.points FROM race_driver_standing s
        JOIN race r ON r.id = s.race_id JOIN driver d ON d.id = s.driver_id
        WHERE r.year = ? AND r.round = ? ORDER BY s.position_display_order
        """,
        [year, after],
    )
    if not standings:
        return {}
    remaining = [r for r in races if r["round"] > after]
    n_races = len(remaining)
    n_sprints = sum(1 for r in remaining if r["sprint"])
    history = defaultdict(lambda: {"race": [], "sprint": []})
    for r in results:
        if r["round"] <= after:
            history[r["driver_id"]][r["kind"]].append(r["points"])
    max_race = max((r["points"] for r in results if r["kind"] == "race"), default=0)
    max_sprint = max((r["points"] for r in results if r["kind"] == "sprint"), default=8 if n_sprints else 0)
    leader = standings[0]["points"]
    totals = np.zeros((sims, len(standings)))
    for i, s in enumerate(standings):
        h = history[s["driver_id"]]
        race_pts = np.array(h["race"] or [0.0])
        sprint_pts = np.array(h["sprint"] or [0.0])
        draw = race_pts[rng.integers(0, len(race_pts), (sims, n_races))].sum(axis=1) if n_races else 0
        draw_s = sprint_pts[rng.integers(0, len(sprint_pts), (sims, n_sprints))].sum(axis=1) if n_sprints else 0
        totals[:, i] = s["points"] + draw + draw_s
    # Ties are broken at random, which is close enough for a probability.
    winner = np.argmax(totals + rng.random(totals.shape) * 1e-6, axis=1)
    counts = np.bincount(winner, minlength=len(standings))
    out = []
    for i, s in enumerate(standings):
        max_possible = s["points"] + n_races * max_race + n_sprints * max_sprint
        out.append(
            {
                "driver_id": s["driver_id"],
                "name": s["name"],
                "points": s["points"],
                "probability": round(counts[i] / sims, 4),
                "max_possible": max_possible,
                "can_still_win": max_possible >= leader,
            }
        )
    return {"after_round": after, "remaining_races": n_races, "remaining_sprints": n_sprints, "drivers": out}


@router.get("/seasons/{year}/title-odds")
def title_odds(year: int, after: int | None = Query(None, description="Round to simulate from (default: latest)")):
    """Chance of each driver winning the title, by simulating the remaining races 20,000 times.

    Each driver's points in a remaining race are drawn from their own points per race so far this season (sprints
    separately), so form, reliability and the season's points system are all in the draw. Races are treated as
    independent, so this is a rough guide, not a forecast.
    """
    races, results = _season_points(year)
    if not races:
        raise HTTPException(404, "Season not found")
    done = [r["round"] for r in races if r["done"]]
    if len(done) < 2:
        return {"year": year, "available": False, "reason": "Needs at least two races."}
    latest = max(done)
    after = min(after or latest, latest)
    rng = np.random.default_rng(year)
    current = _odds_after(year, after, races, results, 20000, rng)
    history = []
    for rnd in done:
        if rnd < 2:
            continue
        o = _odds_after(year, rnd, races, results, 3000, rng)
        history.append(
            {
                "round": rnd,
                "abbreviation": next(r["abbreviation"] for r in races if r["round"] == rnd),
                "odds": {d["driver_id"]: d["probability"] for d in o["drivers"] if d["probability"] > 0},
            }
        )
    return {
        "year": year,
        "available": True,
        "current": current,
        "history": history,
        "finished": latest == races[-1]["round"],
    }


@router.get("/eras")
def eras():
    """Regulation eras with their champions and the most successful team."""
    out = []
    for e in ERAS:
        to = e["to"] or 2100
        stats = db.one(
            """
            SELECT count(DISTINCT r.id) AS races,
                   (SELECT c.name FROM race_result x JOIN race r2 ON r2.id = x.race_id JOIN constructor c ON c.id = x.constructor_id
                     WHERE r2.year BETWEEN $f AND $t AND x.position_number = 1 GROUP BY c.name ORDER BY count(*) DESC LIMIT 1) AS top_team,
                   (SELECT d.name FROM race_result x JOIN race r2 ON r2.id = x.race_id JOIN driver d ON d.id = x.driver_id
                     WHERE r2.year BETWEEN $f AND $t AND x.position_number = 1 GROUP BY d.name ORDER BY count(*) DESC LIMIT 1) AS top_driver
            FROM race r WHERE r.year BETWEEN $f AND $t AND r.id IN (SELECT race_id FROM race_result)
            """,
            {"f": e["from"], "t": to},
        )
        champions = db.rows(
            """
            SELECT s.year, d.id, d.name FROM season_driver_standing s JOIN driver d ON d.id = s.driver_id
            WHERE s.position_number = 1 AND s.year BETWEEN ? AND ? ORDER BY s.year
            """,
            [e["from"], to],
        )
        out.append({**e, **(stats or {}), "champions": champions})
    return out


@router.get("/cars/{chassis_id}")
def car(chassis_id: str):
    """A car (chassis): who raced it, with which engines and tyres, how it did and how fast it was in qualifying."""
    ch = db.one_or_404(
        """
        SELECT ch.id, ch.name, ch.full_name, ch.constructor_id, c.name AS constructor
        FROM chassis ch JOIN constructor c ON c.id = ch.constructor_id WHERE ch.id = ?
        """,
        [chassis_id],
        "Car",
    )
    seasons = db.rows(
        """
        SELECT DISTINCT e.year, e.constructor_id, e.entrant_id, en.name AS entrant
        FROM season_entrant_chassis e JOIN entrant en ON en.id = e.entrant_id
        WHERE e.chassis_id = ? ORDER BY e.year
        """,
        [chassis_id],
    )
    years = sorted({s["year"] for s in seasons})
    if not years:
        raise HTTPException(404, "Car not found")
    constructors = sorted({s["constructor_id"] for s in seasons})
    ph_y = ",".join("?" * len(years))
    ph_c = ",".join("?" * len(constructors))
    engines = db.rows(
        f"""
        SELECT DISTINCT en.id, en.full_name, en.capacity, en.configuration, en.aspiration, em.name AS manufacturer
        FROM season_entrant_engine e JOIN engine en ON en.id = e.engine_id
        JOIN engine_manufacturer em ON em.id = en.engine_manufacturer_id
        WHERE e.year IN ({ph_y}) AND e.constructor_id IN ({ph_c})
        """,
        [*years, *constructors],
    )
    others = db.rows(
        f"""
        SELECT DISTINCT e.year, ch.id, ch.name FROM season_entrant_chassis e JOIN chassis ch ON ch.id = e.chassis_id
        WHERE e.year IN ({ph_y}) AND e.constructor_id IN ({ph_c}) AND e.chassis_id <> ?
        """,
        [*years, *constructors, chassis_id],
    )
    drivers = db.rows(
        f"""
        SELECT DISTINCT d.id, d.name, e.year FROM season_entrant_driver e JOIN driver d ON d.id = e.driver_id
        WHERE e.year IN ({ph_y}) AND e.constructor_id IN ({ph_c}) AND NOT e.test_driver ORDER BY e.year, d.name
        """,
        [*years, *constructors],
    )
    results = db.one(
        f"""
        SELECT count(DISTINCT rr.race_id) AS races, count(*) FILTER (WHERE rr.position_number = 1) AS wins,
               count(*) FILTER (WHERE rr.position_number <= 3) AS podiums, count(*) FILTER (WHERE rr.pole_position) AS poles,
               sum(coalesce(rr.points, 0)) AS points,
               count(*) FILTER (WHERE rr.position_text IN ('DNF', 'NC')) AS retirements,
               count(*) AS starts
        FROM race_result rr JOIN race r ON r.id = rr.race_id
        WHERE r.year IN ({ph_y}) AND rr.constructor_id IN ({ph_c})
              AND rr.position_text NOT IN ('DNQ', 'DNPQ', 'DNS', 'DNP', 'EX')
        """,
        [*years, *constructors],
    )
    standing = db.rows(
        f"""
        SELECT year, position_number AS position, points FROM season_constructor_standing
        WHERE year IN ({ph_y}) AND constructor_id IN ({ph_c}) ORDER BY year
        """,
        [*years, *constructors],
    )
    pace = db.rows(
        f"""
        WITH best AS (
            SELECT q.race_id, q.constructor_id,
                   min(least(coalesce(q.q1_millis, 1e12), coalesce(q.q2_millis, 1e12), coalesce(q.q3_millis, 1e12),
                             coalesce(q.time_millis, 1e12))) AS ms
            FROM qualifying_result q JOIN race r ON r.id = q.race_id WHERE r.year IN ({ph_y}) GROUP BY ALL
        ), pole AS (SELECT race_id, min(ms) AS ms FROM best WHERE ms < 1e12 GROUP BY 1)
        SELECT r.year, r.round, gp.abbreviation, round((b.ms - p.ms) * 100.0 / p.ms, 3) AS gap_pct
        FROM best b JOIN pole p USING (race_id) JOIN race r ON r.id = b.race_id JOIN grand_prix gp ON gp.id = r.grand_prix_id
        WHERE b.constructor_id IN ({ph_c}) AND b.ms < 1e12 AND (b.ms - p.ms) * 100.0 / p.ms <= 5
        ORDER BY r.year, r.round
        """,
        [*years, *constructors],
    )
    gaps = [p["gap_pct"] for p in pace]
    return {
        "car": ch,
        "years": years,
        "entrants": sorted({s["entrant"] for s in seasons}),
        "era": era_for(years[0]),
        "engines": engines,
        "drivers": drivers,
        "results": results,
        "standings": standing,
        "qualifying_pace": pace,
        "average_gap_pct": round(float(np.median(gaps)), 3) if gaps else None,
        "shared_seasons": others,
    }


CAR_ROW = """
    SELECT cr.year, cr.constructor_id, c.name AS constructor, cr.entrant_id, en.name AS entrant, cr.gap_pct,
           cr.raw_gap_pct, cr.races, cr.rank, cr.cars, cr.margin_pct, cr.percentile,
           (SELECT list(DISTINCT {'id': ch.id, 'name': ch.name}) FROM season_entrant_chassis e
              JOIN chassis ch ON ch.id = e.chassis_id
             WHERE e.year = cr.year AND e.constructor_id = cr.constructor_id AND e.entrant_id = cr.entrant_id) AS chassis
    FROM car_rating cr JOIN constructor c ON c.id = cr.constructor_id LEFT JOIN entrant en ON en.id = cr.entrant_id
"""
CAR_METHOD = (
    "Qualifying gap to pole split into a car part per team per season and a driver part per career, so a great "
    "driver does not flatter a car. Shown as the gap to the fastest car of the season."
)


def _with_chassis(rows: list[dict]) -> list[dict]:
    for r in rows:
        r["chassis"] = sorted(r["chassis"] or [], key=lambda c: c["name"])
    return rows


@router.get("/car-ratings")
def car_ratings(min_seasons: int = Query(5, ge=1), limit: int = Query(25, ge=1, le=200)):
    """All time: the most dominant cars, the fastest car of every season and constructors by how fast their cars were."""
    dominant = _with_chassis(
        db.rows(
            CAR_ROW + " WHERE cr.rank = 1 AND cr.margin_pct IS NOT NULL ORDER BY cr.margin_pct DESC LIMIT ?", [limit]
        )
    )
    fastest = _with_chassis(db.rows(CAR_ROW + " WHERE cr.rank = 1 ORDER BY cr.year"))
    constructors = db.rows(
        """
        SELECT cr.constructor_id, c.name AS constructor, count(*) AS seasons, min(cr.year) AS first_year,
               max(cr.year) AS last_year, count(*) FILTER (WHERE cr.rank = 1) AS fastest_car_seasons,
               count(*) FILTER (WHERE cr.rank <= 3) AS top3_seasons, round(avg(cr.percentile), 3) AS average_percentile,
               round(median(cr.gap_pct), 3) AS median_gap_pct, min(cr.gap_pct) AS best_gap_pct
        FROM car_rating cr JOIN constructor c ON c.id = cr.constructor_id
        GROUP BY ALL HAVING count(*) >= ? ORDER BY average_percentile DESC
        """,
        [min_seasons],
    )
    for i, r in enumerate(constructors, start=1):
        r["rank"] = i
    return {"dominant": dominant, "fastest": fastest, "constructors": constructors, "method": CAR_METHOD}


@router.get("/car-ratings/team/{constructor_id}")
def car_ratings_team(constructor_id: str):
    """One constructor's cars, season by season, against the fastest car of each season."""
    rows = _with_chassis(db.rows(CAR_ROW + " WHERE cr.constructor_id = ? ORDER BY cr.year", [constructor_id]))
    return {"seasons": rows, "method": CAR_METHOD}


@router.get("/car-ratings/{year}")
def car_ratings_season(year: int):
    """Every team's car in one season, fastest first, with and without the drivers taken out."""
    rows = _with_chassis(db.rows(CAR_ROW + " WHERE cr.year = ? ORDER BY cr.rank", [year]))
    if not rows:
        raise HTTPException(404, "No qualifying times for that season")
    return {"year": year, "cars": rows, "method": CAR_METHOD}
