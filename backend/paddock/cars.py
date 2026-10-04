"""Car performance from qualifying pace, with the drivers taken out.

Every qualifying lap is a gap to pole, in percent. Each gap is split into what the car was worth that season and
what the driver was worth over their career:

    gap to pole (%) = car (one per team per season) + driver (one per career) + noise

Teammates share a car, so the split comes from drivers who changed teams: how each one compared with their teammates
in one car and then in another places every car of every season on one chain. Driver numbers are held towards zero
(ridge regression), so a driver seen in a handful of races cannot explain away a car. Each car is then shown as a gap
to the fastest car of its season, and a driver's form is taken as the same over a whole career, which it is not.
"""

from __future__ import annotations

import numpy as np

# Strength of the pull of driver numbers towards zero, counted in races.
RIDGE = 20.0
# Laps more than this far off pole are almost always a failed attempt (crash, failure, rain) rather than pace.
MAX_GAP_PCT = 7.0


def fit(rows: list[tuple[str, str, float]]) -> tuple[dict[str, float], dict[str, float]]:
    """rows: (car, driver, gap to pole in %). Returns (car effects, driver effects), both in %."""
    cars = sorted({r[0] for r in rows})
    drivers = sorted({r[1] for r in rows})
    ci = {c: i for i, c in enumerate(cars)}
    di = {d: len(cars) + i for i, d in enumerate(drivers)}
    n = len(cars) + len(drivers)
    m = np.zeros((n, n))
    b = np.zeros(n)
    # Normal equations, built directly: each row touches one car and one driver.
    for car, driver, y in rows:
        i, j = ci[car], di[driver]
        m[i, i] += 1
        m[j, j] += 1
        m[i, j] += 1
        m[j, i] += 1
        b[i] += y
        b[j] += y
    m[len(cars) :, len(cars) :] += RIDGE * np.eye(len(drivers))
    m[: len(cars), : len(cars)] += 1e-6 * np.eye(len(cars))
    beta = np.linalg.solve(m, b)
    return {c: float(beta[ci[c]]) for c in cars}, {d: float(beta[di[d]]) for d in drivers}


def season_table(cars: list[dict]) -> list[dict]:
    """Rank one season's cars ({key, effect, ...}) by effect: gap to the fastest car, margin and percentile."""
    ordered = sorted(cars, key=lambda c: c["effect"])
    if not ordered:
        return []
    best = ordered[0]["effect"]
    out = []
    for rank, c in enumerate(ordered, start=1):
        gap = c["effect"] - best
        out.append(
            {
                **c,
                "rank": rank,
                "cars": len(ordered),
                "gap_pct": round(gap, 3),
                "margin_pct": round(ordered[1]["effect"] - best, 3) if rank == 1 and len(ordered) > 1 else None,
                "percentile": round(1 - (rank - 1) / (len(ordered) - 1), 3) if len(ordered) > 1 else 1.0,
            }
        )
    return out
