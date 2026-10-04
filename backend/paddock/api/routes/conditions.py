"""Safety cars, red flags and rain per circuit, from the timing data (2018+)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ...analysis import WET_RACE_SHARE
from ..db import db

router = APIRouter(tags=["analysis"])

SUMMARY = """
    SELECT rc.circuit_id, c.name, c.place_name, co.alpha2_code AS country_code, count(*) AS races,
           min(rc.year) AS first_year, max(rc.year) AS last_year,
           count(*) FILTER (WHERE rc.safety_cars > 0) AS safety_car_races,
           count(*) FILTER (WHERE rc.safety_cars > 0 OR rc.virtual_safety_cars > 0) AS neutralised_races,
           sum(rc.safety_cars) AS safety_cars, sum(rc.virtual_safety_cars) AS virtual_safety_cars,
           count(*) FILTER (WHERE rc.red_flags > 0) AS red_flag_races,
           count(*) FILTER (WHERE rc.wet) AS wet_races, count(*) FILTER (WHERE rc.rain) AS rain_races,
           round(sum(rc.neutralised_laps) * 100.0 / nullif(sum(rc.race_laps), 0), 1) AS neutralised_pct,
           round(count(*) FILTER (WHERE rc.safety_cars > 0) * 1.0 / count(*), 3) AS safety_car_chance,
           round(sum(rc.safety_cars) * 1.0 / count(*), 2) AS safety_cars_per_race
    FROM race_conditions rc JOIN circuit c ON c.id = rc.circuit_id
    LEFT JOIN country co ON co.id = c.country_id
"""

METHOD = {
    "since": 2018,
    "wet_race": f"At least {round(WET_RACE_SHARE * 100)}% of all laps on intermediate or wet tyres",
    "rain": "Rain recorded by the circuit weather station at any time during the race",
    "safety_car": "A safety car that only leads the field away after a red flag counts with the red flag",
}


@router.get("/conditions")
def all_circuits(min_races: int = Query(3, ge=1)):
    """Every circuit with timing data: how often the safety car comes out, red flags and wet races."""
    rows = db.rows(
        SUMMARY + " GROUP BY ALL HAVING count(*) >= ? ORDER BY safety_car_chance DESC, safety_cars_per_race DESC",
        [min_races],
    )
    totals = db.one(
        """SELECT count(*) AS races, round(count(*) FILTER (WHERE safety_cars > 0) * 1.0 / nullif(count(*), 0), 3)
                  AS safety_car_chance, count(*) FILTER (WHERE wet) AS wet_races,
                  count(*) FILTER (WHERE red_flags > 0) AS red_flag_races
           FROM race_conditions"""
    )
    return {"circuits": rows, "totals": totals, "method": METHOD}


@router.get("/circuits/{circuit_id}/conditions")
def circuit(circuit_id: str):
    """Race by race at one circuit: safety cars, virtual safety cars, red flags, rain and wet running."""
    races = db.rows(
        """
        SELECT rc.year, rc.round, rc.safety_cars, rc.virtual_safety_cars, rc.red_flags, rc.neutralised_laps,
               rc.race_laps, rc.rain, rc.wet, rc.wet_share, gp.full_name AS grand_prix
        FROM race_conditions rc JOIN race r ON r.id = rc.race_id JOIN grand_prix gp ON gp.id = r.grand_prix_id
        WHERE rc.circuit_id = ? ORDER BY rc.year DESC
        """,
        [circuit_id],
    )
    summary = db.one(SUMMARY + " WHERE rc.circuit_id = ? GROUP BY ALL", [circuit_id])
    rank = None
    if summary and summary["races"] >= 3:
        ranked = db.rows(SUMMARY + " GROUP BY ALL HAVING count(*) >= 3")
        rank = {
            "safety_car": 1 + sum(r["safety_car_chance"] > summary["safety_car_chance"] for r in ranked),
            "of": len(ranked),
        }
    return {"races": races, "summary": summary, "rank": rank, "method": METHOD}
