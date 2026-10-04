"""An open cross-era driver rating built only from teammate comparisons.

The idea: the only fair comparison in Formula 1 is against the driver in the same car. Every race in which two
teammates both set a qualifying time (or both finished) gives one equation:

    result(a) - result(b) = skill(a) - skill(b) + noise

Solving all of them together links drivers across eras through chains of shared teammates (Prost - Senna - Berger -
Alesi - ...). The solution is a least-squares fit with a small ridge penalty that pulls drivers with few races towards
the average. The 90% interval comes from the same fit: the residual variance times the diagonal of the inverted
normal matrix, so drivers with few or one-sided comparisons get wide intervals.

Two models:
- qualifying: the qualifying gap in percent of lap time (gaps over 5% are left out);
- race: finishing places ahead of or behind the teammate, both classified, capped at 10.
`combined` averages the two after putting them on the same scale (z-scores).

Limits, also shown on the site: the chain is only as strong as its weakest link, drivers with one or two teammates are
rated mostly against those teammates, and age, health and team orders are not modelled.
"""

from __future__ import annotations

import numpy as np

RIDGE = 2.0
Z90 = 1.645


def fit(pairs: list[tuple[str, str, float]]) -> dict[str, dict]:
    """pairs: (driver_a, driver_b, y) with y = how much worse a was than b. Returns skill (higher is better) and CI."""
    drivers = sorted({p[0] for p in pairs} | {p[1] for p in pairs})
    index = {d: i for i, d in enumerate(drivers)}
    a = np.array([index[p[0]] for p in pairs])
    b = np.array([index[p[1]] for p in pairs])
    y = np.array([p[2] for p in pairs], dtype=float)
    n = len(drivers)
    m = np.zeros((n, n))
    rhs = np.zeros(n)
    np.add.at(m, (a, a), 1.0)
    np.add.at(m, (b, b), 1.0)
    np.add.at(m, (a, b), -1.0)
    np.add.at(m, (b, a), -1.0)
    np.add.at(rhs, a, y)
    np.add.at(rhs, b, -y)
    m[np.diag_indices(n)] += RIDGE
    inverse = np.linalg.inv(m)
    slowness = inverse @ rhs
    residual = y - (slowness[a] - slowness[b])
    sigma2 = float(residual.var())
    half = Z90 * np.sqrt(sigma2 * np.diag(inverse))
    skill = -slowness
    comparisons = np.bincount(a, minlength=n) + np.bincount(b, minlength=n)
    return {
        d: {
            "skill": float(skill[i]),
            "low": float(skill[i] - half[i]),
            "high": float(skill[i] + half[i]),
            "comparisons": int(comparisons[i]),
        }
        for d, i in index.items()
    }


def standardise(ratings: dict[str, dict]) -> dict[str, dict]:
    values = np.array([r["skill"] for r in ratings.values()])
    mu, sd = values.mean(), values.std() or 1.0
    return {
        d: {**r, "z": (r["skill"] - mu) / sd, "z_low": (r["low"] - mu) / sd, "z_high": (r["high"] - mu) / sd}
        for d, r in ratings.items()
    }
