"""Strategy simulator: what if a driver had stopped on other laps, or fitted other tyres (2018+).

A tyre model is fitted on the race itself, on every driver's clean laps (see analysis.clean_laps):

    fuel-corrected lap time = driver pace + compound offset + compound wear x tyre age + track trend x race lap

Driver pace is one number per driver; offset and wear are shared by the field, one pair per compound, so the model
leans on every car that ran a compound rather than on one driver's handful of laps. The track trend (rubber going
down, and whatever the fuel correction misses) is the same whatever the plan, so it only keeps the wear honest. Wear that comes out negative
(track evolution can outweigh tyre wear) is held at zero.

A different plan for one driver changes only that driver's green-flag laps and pit stops. The difference is added to
their real race time lap by lap, so the start, safety cars and real incidents stay as they were, and everyone else
keeps their real race. A stop costs the race's typical pit loss, less under a safety car or a virtual safety car and
nothing under a red flag (tyres can be changed for free). Traffic, tyre warm-up and rivals reacting are not modelled.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np

from . import analysis as an

DRY = ("SOFT", "MEDIUM", "HARD")
COMPOUNDS = (*DRY, "INTERMEDIATE", "WET")
MIN_COMPOUND_LAPS = 15
# Beyond these, a compound's fit says more about the weather than about the tyre.
MAX_OFFSET_S = 3.0
MAX_WEAR_S = 0.3
# Share of the green-flag pit loss paid when stopping under each neutralisation.
PIT_FACTOR = {"sc": 0.5, "vsc": 0.65, "red": 0.0}


def fit(timing_laps: list[dict], neutral: dict[int, str], total_laps: int) -> dict | None:
    """Fit the tyre model on a race's clean laps. None when there are too few laps to say anything."""
    by_driver: dict[str, list[dict]] = defaultdict(list)
    for r in timing_laps:
        by_driver[r["driver_id"]].append(r)
    rows = []
    for d, laps in by_driver.items():
        laps.sort(key=lambda r: r["lap"])
        for r in an.clean_laps(laps, neutral):
            if r.get("compound") in COMPOUNDS and r.get("tyre_life") is not None:
                y = an.fuel_corrected(r["time_ms"], r["lap"], total_laps) / 1000
                rows.append((d, r["compound"], float(r["tyre_life"]), y, r["lap"]))
    counts = Counter(r[1] for r in rows)
    compounds = sorted((c for c, n in counts.items() if n >= MIN_COMPOUND_LAPS), key=COMPOUNDS.index)
    rows = [r for r in rows if r[1] in compounds]
    if len(rows) < 50:
        return None
    drivers = sorted({r[0] for r in rows})
    reference = max(compounds, key=lambda c: counts[c])
    keep = np.ones(len(rows), dtype=bool)
    flat: set[str] = set()  # wear groups held at zero
    # Compounds that share one wear number. A softer dry compound cannot wear more slowly than a harder one; when the
    # fit says otherwise (a few laps at the wrong part of the race), the two are given one shared wear number.
    group = {c: c for c in compounds}
    for _ in range(8):
        offsets = [c for c in compounds if c != reference]
        wears = sorted({group[c] for c in compounds} - flat, key=COMPOUNDS.index)
        cols = len(drivers) + len(offsets) + len(wears) + 1
        X = np.zeros((len(rows), cols))
        y = np.array([r[3] for r in rows])
        for i, (d, c, age, _, lap) in enumerate(rows):
            X[i, -1] = lap
            X[i, drivers.index(d)] = 1
            if c in offsets:
                X[i, len(drivers) + offsets.index(c)] = 1
            if group[c] in wears:
                X[i, len(drivers) + len(offsets) + wears.index(group[c])] = age
        beta, *_ = np.linalg.lstsq(X[keep], y[keep], rcond=None)
        resid = y - X @ beta
        # Drop laps far off the model (traffic, a mistake, a slow puncture) and fit again.
        mad = float(np.median(np.abs(resid[keep]))) * 1.4826 or 0.1
        new_keep = np.abs(resid) <= 3 * mad
        by_group = dict(zip(wears, beta[len(drivers) + len(offsets) : -1], strict=True))
        wear = {c: by_group.get(group[c], 0.0) for c in compounds}
        negative = {g for g, w in by_group.items() if w < 0}
        dry = [c for c in DRY if c in compounds]
        merge = next(
            ((a, b) for a, b in zip(dry, dry[1:], strict=False) if group[a] != group[b] and wear[a] < wear[b] - 1e-6),
            None,
        )
        if not negative and not merge and (new_keep == keep).all():
            break
        flat |= negative
        if merge:
            old_group, new_group = group[merge[1]], group[merge[0]]
            group = {c: new_group if g == old_group else g for c, g in group.items()}
            flat.discard(new_group)
        keep = new_keep
    offset = dict(zip(offsets, beta[len(drivers) : len(drivers) + len(offsets)], strict=True))
    used = Counter(rows[i][1] for i in np.flatnonzero(keep))
    fitted = {
        c: {
            "offset_s": round(float(offset.get(c, 0.0)), 3),
            "wear_s_per_lap": round(max(0.0, float(wear.get(c, 0.0))), 4),
            "laps": used[c],
        }
        for c in compounds
    }
    # A changing track (drying, or rain arriving) breaks the model: a compound used only in other conditions comes
    # out seconds apart from the rest. Such compounds are left out rather than simulated with made-up numbers.
    plausible = {
        c: p for c, p in fitted.items() if abs(p["offset_s"]) <= MAX_OFFSET_S and p["wear_s_per_lap"] <= MAX_WEAR_S
    }
    if not plausible:
        return None
    return {
        "reference": reference,
        "drivers": {d: round(float(beta[i]), 3) for i, d in enumerate(drivers)},
        "compounds": plausible,
        "left_out": sorted(set(fitted) - set(plausible), key=COMPOUNDS.index),
        "track_s_per_lap": round(float(beta[-1]), 4),
        "laps": int(keep.sum()),
        "rmse_s": round(float(np.sqrt(np.mean(resid[keep] ** 2))), 3),
    }


def plan_from_stints(stints: list[dict]) -> list[dict]:
    """The plan a driver really ran: compound, first and last lap and tyre age before the first lap of each stint."""
    return [
        {
            "compound": s["compound"],
            "from_lap": s["from_lap"],
            "to_lap": s["to_lap"],
            "age_start": s.get("tyre_age_at_start") or 0,
        }
        for s in stints
    ]


def make_plan(actual: list[dict], stops: list[int], compounds: list[str], last_lap: int) -> list[dict]:
    """A plan from stop laps (the driver pits at the end of each) and one compound per stint.

    A stint on the same compound as the real stint in the same place starts on tyres of the same age; any other
    stint starts on a new set.
    """
    bounds = [0, *stops, last_lap]
    plan = []
    for i, c in enumerate(compounds):
        same = i < len(actual) and actual[i]["compound"] == c
        plan.append(
            {
                "compound": c,
                "from_lap": bounds[i] + 1,
                "to_lap": bounds[i + 1],
                "age_start": actual[i]["age_start"] if same else 0,
            }
        )
    return plan


def stop_cost(lap: int, neutral: dict[int, str], pit_loss_s: float) -> float:
    return pit_loss_s * PIT_FACTOR.get(neutral.get(lap, ""), 1.0)


def lap_costs(model: dict, plan: list[dict], last_lap: int, neutral: dict[int, str], pit_loss_s: float) -> np.ndarray:
    """Seconds each lap costs under a plan, from tyres and stops, compared with an imaginary new reference tyre.

    Index 0 is unused so that index n is lap n. Neutralised laps cost nothing extra: the pace is set by the safety car.
    """
    cost = np.zeros(last_lap + 1)
    for st in plan:
        p = model["compounds"][st["compound"]]
        for lap in range(st["from_lap"], min(st["to_lap"], last_lap) + 1):
            if lap not in neutral:
                age = st["age_start"] + lap - st["from_lap"] + 1
                cost[lap] += p["offset_s"] + p["wear_s_per_lap"] * age
        if st["to_lap"] < last_lap:
            cost[st["to_lap"]] += stop_cost(st["to_lap"], neutral, pit_loss_s)
    return cost


def check_plan(plan: list[dict], model: dict, last_lap: int, dry_race: bool) -> tuple[list[str], list[str]]:
    """(errors, warnings) for a plan."""
    errors, warnings = [], []
    for st in plan:
        if st["compound"] not in model["compounds"]:
            errors.append(f"Not enough laps on {st['compound'].lower()} tyres in this race to model them")
        if st["to_lap"] < st["from_lap"]:
            errors.append("Stops must be on different laps, in order")
    if plan and plan[-1]["to_lap"] != last_lap:
        errors.append("The plan must cover the whole race")
    used = {st["compound"] for st in plan}
    if dry_race and used <= set(DRY) and len(used) < 2:
        warnings.append("The rules require two different dry compounds in a dry race")
    return errors, warnings


def best_stops(model: dict, plan: list[dict], last_lap: int, neutral: dict[int, str], pit_loss_s: float) -> list[int]:
    """Stop laps that make the same compounds, in the same order, fastest in the model (coordinate search)."""
    stops = [st["to_lap"] for st in plan[:-1]]
    compounds = [st["compound"] for st in plan]

    def total(s: list[int]) -> float:
        return float(lap_costs(model, make_plan(plan, s, compounds, last_lap), last_lap, neutral, pit_loss_s).sum())

    best = total(stops)
    for _ in range(4):
        moved = False
        for i in range(len(stops)):
            low = stops[i - 1] + 1 if i else 1
            high = stops[i + 1] - 1 if i + 1 < len(stops) else last_lap - 1
            for lap in range(low, high + 1):
                trial = [*stops[:i], lap, *stops[i + 1 :]]
                t = total(trial)
                if t < best - 1e-9:
                    best, stops, moved = t, trial, True
        if not moved:
            break
    return stops


def positions(
    driver: str, cumulative: dict[str, dict[int, float]], delta: np.ndarray, last_lap: int
) -> tuple[list[int | None], list[int | None]]:
    """Real and simulated position on every lap, by race time against everyone else's real race time."""
    own = cumulative.get(driver, {})
    real, sim = [], []
    for lap in range(1, last_lap + 1):
        t = own.get(lap)
        if t is None:
            real.append(None)
            sim.append(None)
            continue
        others = [c[lap] for d, c in cumulative.items() if d != driver and lap in c]
        real.append(1 + sum(o < t for o in others))
        shifted = t + float(delta[lap])
        sim.append(1 + sum(o < shifted for o in others))
    return real, sim
