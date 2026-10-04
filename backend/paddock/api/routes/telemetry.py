"""Telemetry and timing endpoints (2018+): sessions, lap comparison, qualifying analysis, straight-line speed.

Telemetry is served one lap at a time for charts. There is deliberately no bulk endpoint: the underlying data
belongs to Formula 1 and is not ours to redistribute.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from ... import telemetry as tm
from ..db import db

router = APIRouter(prefix="/races", tags=["telemetry"])
driver_router = APIRouter(prefix="/drivers", tags=["telemetry"])
season_router = APIRouter(prefix="/seasons", tags=["telemetry"])

SESSION_NAMES = {"Q": "Qualifying", "SQ": "Sprint qualifying", "S": "Sprint", "R": "Race"}
ORDER = ["Q", "SQ", "S", "R"]


def _race_id(year: int, round_: int) -> int:
    row = db.one_or_404("SELECT id FROM race WHERE year = ? AND round = ?", [year, round_], "Race")
    return row["id"]


def _session(race_id: int, kind: str) -> dict:
    s = db.one("SELECT * FROM timing_session WHERE race_id = ? AND type = ?", [race_id, kind])
    if not s:
        raise HTTPException(404, "No timing data for this session")
    s["corners"] = json.loads(s["corners"] or "[]")
    return s


@router.get("/{year}/{round_}/sessions")
def sessions(year: int, round_: int):
    """Sessions of the weekend with timing data, and the drivers with a telemetry lap in each."""
    rid = _race_id(year, round_)
    rows = db.rows(
        """
        SELECT s.type, s.session_key, count(t.driver_id) AS drivers
        FROM timing_session s LEFT JOIN timing_telemetry t ON t.session_key = s.session_key
        WHERE s.race_id = ? GROUP BY ALL
        """,
        [rid],
    )
    rows.sort(key=lambda r: ORDER.index(r["type"]) if r["type"] in ORDER else 9)
    drivers = db.rows(
        """
        SELECT t.session_key, t.driver_id, d.name, d.abbreviation, t.lap, t.lap_time_ms,
               coalesce(rr.constructor_id, q.constructor_id, sr.constructor_id) AS constructor_id
        FROM timing_telemetry t JOIN timing_session s ON s.session_key = t.session_key
        JOIN driver d ON d.id = t.driver_id
        LEFT JOIN race_result rr ON rr.race_id = s.race_id AND rr.driver_id = t.driver_id
        LEFT JOIN qualifying_result q ON q.race_id = s.race_id AND q.driver_id = t.driver_id
        LEFT JOIN sprint_race_result sr ON sr.race_id = s.race_id AND sr.driver_id = t.driver_id
        WHERE s.race_id = ? ORDER BY t.lap_time_ms
        """,
        [rid],
    )
    for r in rows:
        r["name"] = SESSION_NAMES.get(r["type"], r["type"])
        r["laps"] = [d for d in drivers if d["session_key"] == r["session_key"]]
    return rows


@router.get("/{year}/{round_}/telemetry")
def compare_laps(
    year: int,
    round_: int,
    session: str = Query("Q", description="Q, SQ, S or R"),
    drivers: str = Query(..., description="Two driver ids; the first is the reference"),
):
    """Fastest laps of two drivers in a session, aligned on distance, with the time gap and mini-sector winners."""
    rid = _race_id(year, round_)
    s = _session(rid, session)
    ids = [d for d in drivers.split(",") if d][:2]
    if not ids:
        raise HTTPException(400, "Give one or two driver ids")
    laps = {}
    for driver_id in ids:
        row = db.one(
            """
            SELECT t.*, d.name, d.abbreviation FROM timing_telemetry t JOIN driver d ON d.id = t.driver_id
            WHERE t.session_key = ? AND t.driver_id = ?
            """,
            [s["session_key"], driver_id],
        )
        if not row:
            raise HTTPException(404, f"No telemetry lap for {driver_id} in this session")
        sectors = db.one(
            "SELECT s1_ms, s2_ms, s3_ms, compound, tyre_life FROM timing_lap WHERE session_key = ? AND driver_id = ? AND lap = ?",
            [s["session_key"], driver_id, row["lap"]],
        )
        row.pop("session_key")
        row["sectors"] = sectors
        laps[driver_id] = row
    base = laps[ids[0]]
    out = {
        "session": {k: s[k] for k in ("session_key", "type", "name", "rotation", "corners", "total_laps")},
        "drivers": ids,
        "laps": laps,
        "straights": {d: tm.straights(lap) for d, lap in laps.items()},
    }
    if len(ids) == 2:
        out["delta"] = tm.delta(base, laps[ids[1]])
        out["dominance"] = tm.dominance(laps)
    return out


@router.get("/{year}/{round_}/qualifying-analysis")
def qualifying_analysis(year: int, round_: int, session: str = Query("Q")):
    """Best lap, best sectors, ideal lap and top speed of every driver in a qualifying session (2018+)."""
    rid = _race_id(year, round_)
    s = _session(rid, session)
    rows = db.rows(
        """
        SELECT l.driver_id, d.name, d.abbreviation,
               min(l.time_ms) FILTER (WHERE NOT l.deleted) AS best_ms,
               min(l.s1_ms) FILTER (WHERE NOT l.deleted) AS s1_ms,
               min(l.s2_ms) FILTER (WHERE NOT l.deleted) AS s2_ms,
               min(l.s3_ms) FILTER (WHERE NOT l.deleted) AS s3_ms,
               max(l.speed_trap) AS top_speed,
               count(*) FILTER (WHERE l.time_ms IS NOT NULL) AS laps,
               any_value(q.constructor_id) AS constructor_id, any_value(q.position_number) AS position
        FROM timing_lap l JOIN driver d ON d.id = l.driver_id
        LEFT JOIN qualifying_result q ON q.race_id = ? AND q.driver_id = l.driver_id
        WHERE l.session_key = ? GROUP BY l.driver_id, d.name, d.abbreviation
        HAVING best_ms IS NOT NULL
        ORDER BY best_ms
        """,
        [rid, s["session_key"]],
    )
    if not rows:
        return {"session": s["type"], "rows": []}
    pole = rows[0]["best_ms"]
    best = {k: min((r[k] for r in rows if r[k]), default=None) for k in ("s1_ms", "s2_ms", "s3_ms")}
    for r in rows:
        r["gap_ms"] = r["best_ms"] - pole
        r["ideal_ms"] = r["s1_ms"] + r["s2_ms"] + r["s3_ms"] if r["s1_ms"] and r["s2_ms"] and r["s3_ms"] else None
        r["left_on_table_ms"] = r["best_ms"] - r["ideal_ms"] if r["ideal_ms"] else None
        r["sector_best"] = [k for k in ("s1_ms", "s2_ms", "s3_ms") if r[k] and r[k] == best[k]]
    ideal = sorted((r for r in rows if r["ideal_ms"]), key=lambda r: r["ideal_ms"])
    return {
        "session": s["type"],
        "rows": rows,
        "best_sectors": best,
        "ideal_order": [r["driver_id"] for r in ideal],
    }


@router.get("/{year}/{round_}/straights")
def straight_line(year: int, round_: int, session: str = Query("Q")):
    """Top speed, share of the lap at full throttle and clipping for every driver's fastest lap."""
    rid = _race_id(year, round_)
    s = _session(rid, session)
    rows = db.rows(
        """
        SELECT t.*, d.name, d.abbreviation, coalesce(q.constructor_id, rr.constructor_id) AS constructor_id
        FROM timing_telemetry t JOIN driver d ON d.id = t.driver_id
        LEFT JOIN qualifying_result q ON q.race_id = ? AND q.driver_id = t.driver_id
        LEFT JOIN race_result rr ON rr.race_id = ? AND rr.driver_id = t.driver_id
        WHERE t.session_key = ?
        """,
        [rid, rid, s["session_key"]],
    )
    out = []
    for r in rows:
        st = tm.straights(r)
        out.append(
            {
                "driver_id": r["driver_id"],
                "name": r["name"],
                "abbreviation": r["abbreviation"],
                "constructor_id": r["constructor_id"],
                "lap_time_ms": r["lap_time_ms"],
                **{k: st[k] for k in ("top_speed_kmh", "full_throttle_pct", "clipping_m")},
                "longest": max(st["zones"], key=lambda z: z["to_m"] - z["from_m"], default=None),
            }
        )
    out.sort(key=lambda r: -(r["top_speed_kmh"] or 0))
    return {"session": s["type"], "year": year, "rows": out}


@driver_router.get("/{driver_id}/telemetry-laps")
def driver_telemetry_laps(driver_id: str):
    """Every session with a telemetry lap of this driver, newest first (links from the driver page)."""
    return db.rows(
        """
        SELECT s.year, s.round, s.type, gp.full_name AS grand_prix, t.lap, t.lap_time_ms,
               (SELECT min(t2.lap_time_ms) FROM timing_telemetry t2 WHERE t2.session_key = t.session_key) AS best_ms
        FROM timing_telemetry t JOIN timing_session s ON s.session_key = t.session_key
        JOIN race r ON r.id = s.race_id JOIN grand_prix gp ON gp.id = r.grand_prix_id
        WHERE t.driver_id = ? AND s.type IN ('Q', 'SQ')
        ORDER BY s.year DESC, s.round DESC, s.type
        """,
        [driver_id],
    )


@season_router.get("/{year}/competitive-order")
def competitive_order(year: int):
    """Each team's best qualifying lap at every race, as a percentage slower than the fastest car."""
    rows = db.rows(
        """
        WITH best AS (
            SELECT q.race_id, q.constructor_id,
                   min(least(coalesce(q.q1_millis, 1e12), coalesce(q.q2_millis, 1e12), coalesce(q.q3_millis, 1e12),
                             coalesce(q.time_millis, 1e12))) AS ms
            FROM qualifying_result q JOIN race r ON r.id = q.race_id
            WHERE r.year = ? GROUP BY ALL
        ), pole AS (SELECT race_id, min(ms) AS ms FROM best WHERE ms < 1e12 GROUP BY 1)
        SELECT r.round, gp.abbreviation, b.constructor_id, c.name, round((b.ms - p.ms) * 100.0 / p.ms, 3) AS gap_pct
        FROM best b JOIN pole p ON p.race_id = b.race_id JOIN race r ON r.id = b.race_id
        JOIN grand_prix gp ON gp.id = r.grand_prix_id JOIN constructor c ON c.id = b.constructor_id
        WHERE b.ms < 1e12 ORDER BY r.round
        """,
        [year],
    )
    rounds = sorted({(r["round"], r["abbreviation"]) for r in rows})
    teams: dict[str, dict] = {}
    for r in rows:
        t = teams.setdefault(r["constructor_id"], {"id": r["constructor_id"], "name": r["name"], "gaps": {}})
        # Gaps over 5% are almost always a lap without a proper attempt (crash, failure, rain); leave them out.
        if r["gap_pct"] is not None and r["gap_pct"] <= 5:
            t["gaps"][r["round"]] = r["gap_pct"]
    series = []
    for t in teams.values():
        values = [t["gaps"].get(rn) for rn, _ in rounds]
        known = [v for v in values if v is not None]
        if len(known) >= max(2, len(rounds) // 3):
            series.append(
                {"id": t["id"], "name": t["name"], "gaps": values, "average": round(sum(known) / len(known), 3)}
            )
    series.sort(key=lambda t: t["average"])
    return {"rounds": [{"round": r, "abbreviation": a} for r, a in rounds], "teams": series}
