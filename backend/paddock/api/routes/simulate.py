"""Strategy simulator endpoint (see paddock/simulator.py for the model)."""

from __future__ import annotations

from statistics import median

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from ... import analysis as an
from ... import simulator as sim
from .analysis import _lap_tables, _race, _stops, _timing_key, _timing_laps, _timing_race_times

router = APIRouter(prefix="/races", tags=["analysis"])

DEFAULT_PIT_LOSS_S = 22.0


def _ints(text: str) -> list[int]:
    try:
        return [int(x) for x in text.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(400, "stops must be comma-separated lap numbers") from None


def simulate_race(year: int, round_: int, driver: str = "", stops: str | None = None, compounds: str | None = None):
    race = _race(year, round_)
    rid = race["id"]
    timing = _timing_laps(_timing_key(rid))
    if not timing:
        raise HTTPException(404, "The simulator needs tyre data, which is recorded from 2018")
    neutral = an.neutralised_laps(timing)
    total = race["laps"] or max(r["lap"] for r in timing)
    model = sim.fit(timing, neutral, total)
    if not model:
        raise HTTPException(404, "Not enough green-flag laps in this race to fit a tyre model")
    stint_map = an.stints(timing, total, neutral)
    _, cumulative_ms, times = _lap_tables(rid)
    cumulative = {d: {lap: ms / 1000 for lap, ms in laps.items()} for d, laps in cumulative_ms.items()}
    stops_list = _stops(rid)
    if not cumulative:
        cumulative, times, timing_stops = _timing_race_times(_timing_key(rid))
        stops_list = stops_list or timing_stops
    losses = an.pit_loss(times, stops_list, neutral)
    pit_loss_s = round(median(losses), 1) if losses else DEFAULT_PIT_LOSS_S
    dry_race = not any(r.get("compound") in ("INTERMEDIATE", "WET") for r in timing)

    finishers = [
        d
        for d in sorted(cumulative, key=lambda d: (-max(cumulative[d]), cumulative[d][max(cumulative[d])]))
        if d in stint_map
    ]
    options = []
    for d in finishers:
        plan = sim.plan_from_stints(stint_map[d])
        last = max(cumulative[d])
        errors, _ = sim.check_plan(plan, model, plan[-1]["to_lap"], dry_race) if plan else (["no laps"], [])
        if not errors and last >= 10:
            options.append(d)
    if not cumulative:
        raise HTTPException(404, "No lap-by-lap times for this race yet")
    if len(options) < 3:
        raise HTTPException(404, "Conditions changed too much in this race to model the tyres")
    driver = driver if driver in options else options[0]

    actual = sim.plan_from_stints(stint_map[driver])
    last_lap = min(actual[-1]["to_lap"], max(cumulative[driver]))
    actual[-1]["to_lap"] = last_lap
    if stops is None and compounds is None:
        new_stops = [st["to_lap"] for st in actual[:-1]]
        new_compounds = [st["compound"] for st in actual]
    else:
        new_stops = sorted(_ints(stops or ""))
        new_compounds = [c.strip().upper() for c in (compounds or "").split(",") if c.strip()]
        if len(new_compounds) != len(new_stops) + 1:
            raise HTTPException(400, "Give one compound per stint: one more than the number of stops")
        if len(new_stops) > 5:
            raise HTTPException(400, "At most five stops")
        if any(s < 1 or s >= last_lap for s in new_stops) or len(set(new_stops)) != len(new_stops):
            raise HTTPException(400, f"Stops must be different laps between 1 and {last_lap - 1}")
    plan = sim.make_plan(actual, new_stops, new_compounds, last_lap)
    errors, warnings = sim.check_plan(plan, model, last_lap, dry_race)
    if errors:
        raise HTTPException(400, errors[0])

    real_cost = sim.lap_costs(model, actual, last_lap, neutral, pit_loss_s)
    new_cost = sim.lap_costs(model, plan, last_lap, neutral, pit_loss_s)
    delta = np.cumsum(new_cost - real_cost)
    real_pos, sim_pos = sim.positions(driver, cumulative, delta, last_lap)

    # The cars around the driver at the end of the simulated race, with the simulated gap.
    final = cumulative[driver][last_lap] + delta[last_lap]
    others = sorted(
        ((d, c[last_lap] - final) for d, c in cumulative.items() if d != driver and last_lap in c),
        key=lambda x: x[1],
    )
    ahead = next(({"driver_id": d, "gap_s": round(-g, 2)} for d, g in reversed(others) if g < 0), None)
    behind = next(({"driver_id": d, "gap_s": round(g, 2)} for d, g in others if g >= 0), None)

    best = sim.best_stops(model, plan, last_lap, neutral, pit_loss_s)
    best_plan = sim.make_plan(actual, best, new_compounds, last_lap)
    best_gain = float(np.sum(sim.lap_costs(model, best_plan, last_lap, neutral, pit_loss_s) - real_cost))

    return {
        "race": race,
        "driver": driver,
        "drivers": options,
        "last_lap": last_lap,
        "total_laps": total,
        "pit_loss_s": pit_loss_s,
        "pit_loss_measured": bool(losses),
        "dry_race": dry_race,
        "model": model,
        "actual": actual,
        "plan": plan,
        "time_change_s": round(float(delta[last_lap]), 2),
        "position": {"real": real_pos[-1], "simulated": sim_pos[-1]},
        "ahead": ahead,
        "behind": behind,
        "laps": [
            {"lap": n, "delta_s": round(float(delta[n]), 2), "real": real_pos[n - 1], "simulated": sim_pos[n - 1]}
            for n in range(1, last_lap + 1)
        ],
        "best": {"stops": best, "time_change_s": round(best_gain, 2)},
        "periods": an.periods(neutral),
        "warnings": warnings,
        "method": {"pit_factor": sim.PIT_FACTOR, "min_compound_laps": sim.MIN_COMPOUND_LAPS},
    }


@router.get("/{year}/{round_}/simulate")
def simulate(
    year: int,
    round_: int,
    driver: str = Query("", description="Driver id; defaults to the winner"),
    stops: str | None = Query(None, description="Comma-separated laps the driver pits at the end of"),
    compounds: str | None = Query(None, description="One compound per stint, e.g. MEDIUM,HARD"),
):
    """What if a driver had pitted on other laps or fitted other tyres? A model of the race, not a replay (2018+)."""
    return simulate_race(year, round_, driver, stops, compounds)
