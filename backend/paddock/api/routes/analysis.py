"""Race analysis endpoints: story, strategy and pace (see paddock/analysis.py for the methods)."""

from __future__ import annotations

from collections import defaultdict
from statistics import median

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from ... import analysis as an
from ..db import db

router = APIRouter(prefix="/races", tags=["analysis"])
circuit_router = APIRouter(prefix="/circuits", tags=["analysis"])


def _race(year: int, round_: int) -> dict:
    return db.one_or_404(
        """
        SELECT r.id, r.year, r.round, r.laps, r.circuit_id, gp.full_name AS grand_prix
        FROM race r JOIN grand_prix gp ON gp.id = r.grand_prix_id WHERE r.year = ? AND r.round = ?
        """,
        [year, round_],
        "Race",
    )


def _timing_key(race_id: int, kind: str = "R") -> str | None:
    return db.scalar("SELECT session_key FROM timing_session WHERE race_id = ? AND type = ?", [race_id, kind])


def _timing_laps(key: str | None) -> list[dict]:
    if not key:
        return []
    return db.rows(
        """
        SELECT driver_id, lap, time_ms, compound, tyre_life, stint, fresh_tyre, pit_in, pit_out, track_status,
               position, is_accurate
        FROM timing_lap WHERE session_key = ? ORDER BY driver_id, lap
        """,
        [key],
    )


def _timing_race_times(key: str) -> tuple[dict[str, dict[int, float]], dict[str, list[tuple[int, int]]], list[dict]]:
    """Race time at the end of every lap, lap times and stops from the timing data alone.

    Used for the latest races, before the lap-by-lap dump (Jolpica) and the pit stop list (f1db) include them.
    A lap ends when the next one starts; the last lap ends at its start plus its lap time.
    """
    rows = db.rows(
        "SELECT driver_id, lap, lap_start_s, time_ms, pit_in FROM timing_lap WHERE session_key = ? ORDER BY driver_id, lap",
        [key],
    )
    start = min((r["lap_start_s"] for r in rows if r["lap"] == 1 and r["lap_start_s"] is not None), default=0.0)
    by_driver: dict[str, list[dict]] = {}
    for r in rows:
        by_driver.setdefault(r["driver_id"], []).append(r)
    cumulative: dict[str, dict[int, float]] = {}
    times: dict[str, list[tuple[int, int]]] = {}
    stops = []
    for d, laps in by_driver.items():
        cumulative[d], times[d] = {}, []
        for i, r in enumerate(laps):
            if r["lap_start_s"] is None:
                continue
            nxt = laps[i + 1] if i + 1 < len(laps) else None
            if nxt and nxt["lap"] == r["lap"] + 1 and nxt["lap_start_s"] is not None:
                end = nxt["lap_start_s"]
            elif r["time_ms"]:
                end = r["lap_start_s"] + r["time_ms"] / 1000
            else:
                continue
            cumulative[d][r["lap"]] = end - start
            times[d].append((r["lap"], round((end - r["lap_start_s"]) * 1000)))
            if r["pit_in"]:
                stops.append({"driver_id": d, "lap": r["lap"]})
        if not cumulative[d]:
            del cumulative[d]
    return cumulative, times, stops


def _lap_tables(race_id: int):
    rows = db.rows("SELECT driver_id, lap, position, time_ms FROM lap WHERE race_id = ? ORDER BY lap", [race_id])
    positions: dict[str, dict[int, int]] = defaultdict(dict)
    cumulative: dict[str, dict[int, int]] = defaultdict(dict)
    times: dict[str, list[tuple[int, int]]] = defaultdict(list)
    running: dict[str, int] = defaultdict(int)
    for r in rows:
        positions[r["driver_id"]][r["lap"]] = r["position"]
        running[r["driver_id"]] += r["time_ms"] or 0
        cumulative[r["driver_id"]][r["lap"]] = running[r["driver_id"]]
        times[r["driver_id"]].append((r["lap"], r["time_ms"]))
    return positions, cumulative, times


def _stops(race_id: int) -> list[dict]:
    return db.rows("SELECT driver_id, lap, stop, time_millis AS duration_ms FROM pit_stop WHERE race_id = ?", [race_id])


@router.get("/{year}/{round_}/story")
def story(year: int, round_: int):
    """Key moments of a race, lap by lap, plus safety-car and red-flag periods (2018+)."""
    race = _race(year, round_)
    rid = race["id"]
    results = db.rows(
        """
        SELECT rr.driver_id, d.abbreviation, d.name, rr.constructor_id, rr.position_number AS position,
               rr.position_text, rr.grid_position_number AS grid, rr.laps, rr.reason_retired,
               rc.category AS retirement_category
        FROM race_result rr JOIN driver d ON d.id = rr.driver_id
        LEFT JOIN retirement_reason rc ON rc.reason = rr.reason_retired
        WHERE rr.race_id = ? ORDER BY rr.position_display_order
        """,
        [rid],
    )
    name = {r["driver_id"]: r["name"] for r in results}
    positions, _, _ = _lap_tables(rid)
    key = _timing_key(rid)
    timing = _timing_laps(key)
    neutral = an.neutralised_laps(timing)
    events: list[dict] = []

    # Start: biggest movers on lap 1.
    movers = []
    for r in results:
        p1 = positions.get(r["driver_id"], {}).get(1)
        if p1 and r["grid"]:
            movers.append((r["grid"] - p1, r["driver_id"], r["grid"], p1))
    for gain, d, g, p in sorted(movers, reverse=True)[:2]:
        if gain >= 3:
            events.append(
                {
                    "lap": 1,
                    "kind": "start",
                    "drivers": [d],
                    "text": f"{name[d]} gains {gain} places at the start, P{g} to P{p}",
                }
            )
    for gain, d, g, p in sorted(movers)[:2]:
        if gain <= -3:
            events.append(
                {
                    "lap": 1,
                    "kind": "start",
                    "drivers": [d],
                    "text": f"{name[d]} drops {-gain} places on lap 1, P{g} to P{p}",
                }
            )

    # Lead changes.
    leaders = {}
    for d, laps in positions.items():
        for lap, pos in laps.items():
            if pos == 1:
                leaders[lap] = d
    previous = next((r["driver_id"] for r in results if r["grid"] == 1), None)
    for lap in sorted(leaders):
        d = leaders[lap]
        if previous and d != previous:
            events.append(
                {
                    "lap": lap,
                    "kind": "lead",
                    "drivers": [d, previous],
                    "text": f"{name.get(d, d)} takes the lead from {name.get(previous, previous)}",
                }
            )
        previous = d

    # Pit stops. With tyre data (2018+), a pass through the pit lane without new tyres (e.g. the field led
    # through the pit lane under a safety car) is not a stop; those become one "through the pit lane" moment.
    # Stops made under the same safety car are one moment ("eight drivers pit under the safety car").
    tyre_change: set[tuple[str, int]] | None = None
    if timing:
        tyre_change = set()
        by_driver: dict[str, list[dict]] = defaultdict(list)
        for r in timing:
            by_driver[r["driver_id"]].append(r)
        for d, laps in by_driver.items():
            laps.sort(key=lambda r: r["lap"])
            for prev, cur in zip(laps, laps[1:], strict=False):
                if cur.get("compound") != prev.get("compound") or (
                    cur.get("tyre_life") is not None
                    and prev.get("tyre_life") is not None
                    and cur["tyre_life"] < prev["tyre_life"]
                ):
                    tyre_change.add((d, prev["lap"]))
    cheap: dict[int, list[str]] = defaultdict(list)
    passes: dict[int, list[str]] = defaultdict(list)
    for s in _stops(rid):
        if tyre_change is not None and (s["driver_id"], s["lap"]) not in tyre_change:
            passes[s["lap"]].append(s["driver_id"])
            continue
        kind = neutral.get(s["lap"])
        if kind:
            cheap[s["lap"]].append(s["driver_id"])
            continue
        # f1db's stop number counts pit-lane passes too, so only show it when there is no tyre data.
        number = "" if tyre_change is not None else f" (stop {s['stop']})"
        text = f"{name.get(s['driver_id'], s['driver_id'])} pits{number}"
        events.append({"lap": s["lap"], "kind": "pit", "drivers": [s["driver_id"]], "text": text})
    for lap, ids in cheap.items():
        label = an.PERIOD_LABEL[neutral[lap]].lower()
        who = name.get(ids[0], ids[0]) if len(ids) == 1 else f"{len(ids)} drivers"
        text = f"{who} {'pits' if len(ids) == 1 else 'pit'} under the {label}"
        if len(ids) > 1:
            text += ": " + ", ".join(name.get(i, i).split(" ")[-1] for i in ids)
        events.append({"lap": lap, "kind": "pit", "drivers": ids, "text": text, "cheap": True})
    if passes:
        laps_ = sorted(passes)
        runs: list[list[int]] = []
        for lap in laps_:
            if runs and lap == runs[-1][-1] + 1:
                runs[-1].append(lap)
            else:
                runs.append([lap])
        for run in runs:
            ids = sorted({d for lap in run for d in passes[lap]})
            span = f"lap {run[0]}" if len(run) == 1 else f"laps {run[0]}–{run[-1]}"
            who = "The field goes" if len(ids) > 5 else ", ".join(name.get(i, i).split(" ")[-1] for i in ids) + " go"
            events.append(
                {
                    "lap": run[0],
                    "kind": "pit",
                    "drivers": ids,
                    "text": f"{who} through the pit lane without changing tyres, {span}",
                    "cheap": True,
                }
            )

    # Retirements.
    for r in results:
        if r["position"] is None and r["laps"] is not None and r["position_text"] in ("DNF", "NC", "DSQ"):
            reason = (r["reason_retired"] or r["position_text"]).lower()
            events.append(
                {
                    "lap": max(r["laps"], 1),
                    "kind": "retire",
                    "drivers": [r["driver_id"]],
                    "text": f"{r['name']} out: {reason}",
                    "category": r["retirement_category"],
                }
            )

    # Safety cars and red flags.
    spans = an.periods(neutral)
    for p in spans:
        laps = f"lap {p['from_lap']}" if p["from_lap"] == p["to_lap"] else f"laps {p['from_lap']}–{p['to_lap']}"
        events.append({"lap": p["from_lap"], "kind": p["kind"], "drivers": [], "text": f"{p['label']}, {laps}"})

    # Penalties from race control (2018+).
    if key:
        for m in db.rows(
            """
            SELECT lap, driver_id, message FROM timing_race_control
            WHERE session_key = ? AND message ILIKE '%PENALTY%' AND message NOT ILIKE '%NO FURTHER%'
              AND message NOT ILIKE '%SERVED%' AND message NOT ILIKE '%REVIEWED%'
            ORDER BY t_s
            """,
            [key],
        ):
            text = an.penalty_text(m["message"], name.get(m["driver_id"]))
            if text:
                events.append(
                    {
                        "lap": m["lap"] or 1,
                        "kind": "penalty",
                        "drivers": [m["driver_id"]] if m["driver_id"] else [],
                        "text": text,
                    }
                )

    fl = db.one("SELECT driver_id, lap, time FROM fastest_lap WHERE race_id = ? AND position_number = 1", [rid])
    if fl and fl["lap"]:
        events.append(
            {
                "lap": fl["lap"],
                "kind": "fastest",
                "drivers": [fl["driver_id"]],
                "text": f"Fastest lap: {name.get(fl['driver_id'], fl['driver_id'])}, {fl['time']}",
            }
        )
    winner = next((r for r in results if r["position"] == 1), None)
    if winner:
        events.append(
            {
                "lap": race["laps"] or winner["laps"] or 0,
                "kind": "finish",
                "drivers": [winner["driver_id"]],
                "text": f"{winner['name']} wins",
            }
        )

    order = {
        "start": 0,
        "sc": 1,
        "vsc": 1,
        "red": 1,
        "lead": 2,
        "retire": 3,
        "pit": 4,
        "penalty": 5,
        "fastest": 6,
        "finish": 7,
    }
    events.sort(key=lambda e: (e["lap"], order.get(e["kind"], 9)))
    rain = bool(key and db.scalar("SELECT bool_or(rain) FROM timing_weather WHERE session_key = ?", [key]))
    return {"race": race, "has_timing": bool(key), "periods": spans, "events": events, "rain": rain}


@router.get("/{year}/{round_}/strategy")
def strategy(year: int, round_: int):
    """Tyre stints (compounds from 2018), pit-stop time loss and undercut/overcut verdicts (2011+)."""
    race = _race(year, round_)
    rid = race["id"]
    key = _timing_key(rid)
    timing = _timing_laps(key)
    neutral = an.neutralised_laps(timing)
    total = race["laps"] or max((r["lap"] for r in timing), default=0)
    stops = _stops(rid)
    positions, cumulative, times = _lap_tables(rid)

    drivers = db.rows(
        """
        SELECT rr.driver_id, d.abbreviation, d.name, rr.constructor_id, c.name AS constructor,
               rr.position_number AS position, rr.position_text, rr.laps
        FROM race_result rr JOIN driver d ON d.id = rr.driver_id JOIN constructor c ON c.id = rr.constructor_id
        WHERE rr.race_id = ? AND rr.laps > 0 ORDER BY rr.position_display_order
        """,
        [rid],
    )
    if timing:
        stint_map = an.stints(timing, total, neutral)
    else:
        # Before 2018: stints from pit stop laps, without compounds.
        stint_map = {}
        by = defaultdict(list)
        for s in stops:
            by[s["driver_id"]].append(s["lap"])
        for d in drivers:
            bounds = [0, *sorted(x for x in by.get(d["driver_id"], []) if x < (d["laps"] or 0)), d["laps"] or 0]
            stint_map[d["driver_id"]] = [
                {
                    "stint": i + 1,
                    "compound": None,
                    "from_lap": bounds[i] + 1,
                    "to_lap": bounds[i + 1],
                    "laps": bounds[i + 1] - bounds[i],
                }
                for i in range(len(bounds) - 1)
                if bounds[i + 1] > bounds[i]
            ]
    if not times and key:
        # The newest races are in the timing data before the lap-by-lap dump and the pit stop list include them.
        _, times, timing_stops = _timing_race_times(key)
        stops = stops or timing_stops
    losses = an.pit_loss(times, stops, neutral) if stops and times else []
    battles = an.pit_battles(positions, cumulative, stops, neutral) if stops and positions else []
    compounds = sorted({s["compound"] for st in stint_map.values() for s in st if s.get("compound")})
    return {
        "race": race,
        "has_timing": bool(timing),
        "has_stops": bool(stops),
        "total_laps": total,
        "drivers": [{**d, "stints": stint_map.get(d["driver_id"], [])} for d in drivers],
        "compounds": compounds,
        "periods": an.periods(neutral),
        "pit_loss_s": round(median(losses), 1) if losses else None,
        "pit_loss_samples": len(losses),
        "battles": battles,
        "method": {"fuel_start_kg": an.FUEL_START_KG, "fuel_s_per_kg": an.FUEL_S_PER_KG, "slow_lap": an.SLOW_LAP},
    }


@router.get("/{year}/{round_}/pace")
def pace(year: int, round_: int, drivers: str = Query("", description="Comma-separated driver ids, up to 4")):
    """Every lap of the chosen drivers with fuel-corrected time, tyre and a clean-lap flag."""
    race = _race(year, round_)
    rid = race["id"]
    ids = [d for d in drivers.split(",") if d][:4]
    if not ids:
        raise HTTPException(400, "Give one to four driver ids")
    key = _timing_key(rid)
    timing = [r for r in _timing_laps(key) if r["driver_id"] in ids]
    neutral = an.neutralised_laps(_timing_laps(key)) if key else {}
    total = race["laps"] or 0
    if not timing:
        timing = db.rows(
            f"SELECT driver_id, lap, time_ms FROM lap WHERE race_id = ? AND driver_id IN ({','.join('?' * len(ids))}) ORDER BY lap",
            [rid, *ids],
        )
        pit_laps = {(s["driver_id"], s["lap"]) for s in _stops(rid)}
        for r in timing:
            r["pit_in"] = (r["driver_id"], r["lap"]) in pit_laps
            r["pit_out"] = (r["driver_id"], r["lap"] - 1) in pit_laps
    out = {}
    for d in ids:
        laps = [r for r in timing if r["driver_id"] == d]
        clean = {r["lap"] for r in an.clean_laps(laps, neutral)}
        out[d] = [
            {
                "lap": r["lap"],
                "time_ms": r["time_ms"],
                "corrected_ms": round(an.fuel_corrected(r["time_ms"], r["lap"], total)) if r["time_ms"] else None,
                "compound": r.get("compound"),
                "tyre_life": r.get("tyre_life"),
                "stint": r.get("stint"),
                "clean": r["lap"] in clean,
                "neutral": neutral.get(r["lap"]),
            }
            for r in laps
        ]
    return {"race": race, "has_timing": bool(key), "laps": out, "periods": an.periods(neutral)}


@circuit_router.get("/{circuit_id}/pit-loss")
def circuit_pit_loss(circuit_id: str):
    """Typical time lost to a pit stop at this circuit, race by race (2011+)."""
    races = db.rows(
        "SELECT id, year, round FROM race WHERE circuit_id = ? AND id IN (SELECT race_id FROM pit_stop) ORDER BY year",
        [circuit_id],
    )
    out = []
    for r in races:
        _, _, times = _lap_tables(r["id"])
        key = _timing_key(r["id"])
        losses = an.pit_loss(times, _stops(r["id"]), an.neutralised_laps(_timing_laps(key)) if key else None)
        if losses:
            out.append(
                {"year": r["year"], "round": r["round"], "pit_loss_s": round(median(losses), 1), "stops": len(losses)}
            )
    # Median over every race here: single races are skewed by safety cars and red flags.
    values = [x["pit_loss_s"] for x in out]
    return {"races": out, "typical_s": round(median(values), 1) if values else None}


PACE_MIN_LAPS = 5


@router.get("/{year}/{round_}/pace-ranking")
def pace_ranking(year: int, round_: int):
    """Every driver's race pace: the median of their fuel-corrected green-flag laps, the spread of those laps and the
    gap to their teammate (1996+, with tyres and safety cars from 2018)."""
    race = _race(year, round_)
    rid = race["id"]
    key = _timing_key(rid)
    timing = _timing_laps(key)
    neutral = an.neutralised_laps(timing)
    total = race["laps"] or max((r["lap"] for r in timing), default=0)
    laps = timing
    if not laps:
        laps = db.rows("SELECT driver_id, lap, time_ms FROM lap WHERE race_id = ? ORDER BY driver_id, lap", [rid])
        pit_laps = {(s["driver_id"], s["lap"]) for s in _stops(rid)}
        for r in laps:
            r["pit_in"] = (r["driver_id"], r["lap"]) in pit_laps
            r["pit_out"] = (r["driver_id"], r["lap"] - 1) in pit_laps
    drivers = {
        d["driver_id"]: d
        for d in db.rows(
            """
            SELECT rr.driver_id, d.name, d.abbreviation, rr.constructor_id, c.name AS constructor,
                   rr.position_number AS position, rr.position_text
            FROM race_result rr JOIN driver d ON d.id = rr.driver_id JOIN constructor c ON c.id = rr.constructor_id
            WHERE rr.race_id = ?
            """,
            [rid],
        )
    }
    by_driver: dict[str, list[dict]] = defaultdict(list)
    for r in laps:
        by_driver[r["driver_id"]].append(r)
    rows, too_few = [], []
    for d, ls in by_driver.items():
        if d not in drivers:
            continue
        ls.sort(key=lambda r: r["lap"])
        clean = an.clean_laps(ls, neutral)
        if len(clean) < PACE_MIN_LAPS:
            too_few.append(d)
            continue
        corrected = np.array([an.fuel_corrected(r["time_ms"], r["lap"], total) for r in clean]) / 1000
        q25, med, q75 = np.percentile(corrected, [25, 50, 75])
        rows.append(
            {
                **drivers[d],
                "laps": len(clean),
                "median_s": round(float(med), 3),
                "q25_s": round(float(q25), 3),
                "q75_s": round(float(q75), 3),
                "raw_median_s": round(float(np.median([r["time_ms"] for r in clean])) / 1000, 3),
            }
        )
    rows.sort(key=lambda r: r["median_s"])
    best = rows[0]["median_s"] if rows else 0
    medians: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for r in rows:
        medians[r["constructor_id"]].append((r["driver_id"], r["median_s"]))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
        r["gap_s"] = round(r["median_s"] - best, 3)
        mates = [(m, v) for m, v in medians[r["constructor_id"]] if m != r["driver_id"]]
        r["teammate"] = {"driver_id": mates[0][0], "gap_s": round(r["median_s"] - mates[0][1], 3)} if mates else None
    return {
        "race": race,
        "has_timing": bool(timing),
        "rows": rows,
        "too_few_laps": [drivers[d]["name"] for d in too_few],
        "method": {"min_laps": PACE_MIN_LAPS, "fuel_start_kg": an.FUEL_START_KG, "fuel_s_per_kg": an.FUEL_S_PER_KG},
    }
