import json

from fastapi import APIRouter, Query

from ..db import db

router = APIRouter(tags=["meta"])


@router.get("/meta")
def meta():
    values = {r["key"]: r["value"] for r in db.rows("SELECT key, value FROM meta")}
    latest = db.one(
        """
        SELECT r.year, r.round, gp.full_name AS grand_prix, r.date
        FROM race r JOIN grand_prix gp ON gp.id = r.grand_prix_id
        WHERE r.id IN (SELECT race_id FROM race_result) ORDER BY r.date DESC LIMIT 1
        """
    )
    upcoming = db.one(
        """
        SELECT r.year, r.round, gp.full_name AS grand_prix, r.date, ci.name AS circuit
        FROM race r JOIN grand_prix gp ON gp.id = r.grand_prix_id JOIN circuit ci ON ci.id = r.circuit_id
        WHERE r.id NOT IN (SELECT race_id FROM race_result) ORDER BY r.date LIMIT 1
        """
    )
    counts = db.one(
        """
        SELECT (SELECT count(*) FROM season) AS seasons,
               (SELECT count(*) FROM race WHERE id IN (SELECT race_id FROM race_result)) AS races,
               (SELECT count(*) FROM driver) AS drivers,
               (SELECT count(*) FROM constructor) AS constructors,
               (SELECT count(*) FROM circuit) AS circuits,
               (SELECT count(*) FROM lap) AS laps,
               (SELECT count(*) FROM pit_stop) AS pit_stops
        """
    )
    return {
        "built_at": values.get("built_at"),
        "sources": json.loads(values.get("sources", "[]")),
        "counts": counts,
        "latest_race": latest,
        "next_race": upcoming,
    }


@router.get("/search")
def search(q: str = Query(..., min_length=1, max_length=60), limit: int = Query(8, ge=1, le=30)):
    """Drivers, constructors, circuits and seasons whose name matches the query (accents ignored)."""
    term = q.strip()
    like = f"%{term.lower()}%"
    results = []
    if term.isdigit() and len(term) == 4 and db.one("SELECT 1 FROM season WHERE year = ?", [int(term)]):
        results.append({"type": "season", "id": term, "name": f"{term} season", "sub": None})
    results += db.rows(
        """
        SELECT 'driver' AS type, d.id, d.name,
               coalesce(n.demonym, '') || ' · ' || s.first_year ||
               CASE WHEN s.last_year > s.first_year THEN '–' || s.last_year ELSE '' END AS sub
        FROM driver d LEFT JOIN country n ON n.id = d.nationality_country_id
        LEFT JOIN (SELECT driver_id, min(year) AS first_year, max(year) AS last_year FROM season_driver
                   WHERE total_race_entries > 0 GROUP BY 1) s
               ON s.driver_id = d.id
        WHERE lower(strip_accents(d.full_name)) LIKE strip_accents($like)
           OR lower(strip_accents(d.name)) LIKE strip_accents($like)
           OR lower(d.abbreviation) = lower($term)
        ORDER BY d.total_race_entries DESC LIMIT $limit
        """,
        {"like": like, "term": term, "limit": limit},
    )
    results += db.rows(
        """
        SELECT 'constructor' AS type, c.id, c.name, n.name AS sub FROM constructor c
        LEFT JOIN country n ON n.id = c.country_id
        WHERE lower(strip_accents(c.name)) LIKE strip_accents($like)
           OR lower(strip_accents(c.full_name)) LIKE strip_accents($like)
        ORDER BY c.total_race_entries DESC LIMIT $limit
        """,
        {"like": like, "limit": limit},
    )
    results += db.rows(
        """
        SELECT 'circuit' AS type, ci.id, ci.name, ci.place_name || ', ' || co.name AS sub FROM circuit ci
        JOIN country co ON co.id = ci.country_id
        WHERE lower(strip_accents(ci.name)) LIKE strip_accents($like)
           OR lower(strip_accents(ci.full_name)) LIKE strip_accents($like)
           OR lower(strip_accents(ci.place_name)) LIKE strip_accents($like)
           OR lower(strip_accents(co.name)) LIKE strip_accents($like)
        ORDER BY ci.total_races_held DESC LIMIT $limit
        """,
        {"like": like, "limit": limit},
    )
    return results[: limit * 2]
