"""Telemetry analysis (2018+): lap comparison, mini-sector dominance and straight-line speed.

Each driver's fastest lap of a session is stored on a 10 m distance grid (see paddock/timing.py), so two laps can be
compared point by point after aligning them on distance.
"""

from __future__ import annotations

import numpy as np

MINI_SECTORS = 25


def _arr(lap: dict, key: str) -> np.ndarray:
    return np.asarray(lap[key], dtype=float)


def delta(base: dict, other: dict) -> list[float]:
    """Time gap of `other` to `base` along `base`'s distance grid, in seconds (positive: `other` is behind)."""
    d = _arr(base, "distance")
    t_base = _arr(base, "time")
    t_other = np.interp(d, _arr(other, "distance"), _arr(other, "time"))
    return np.round(t_other - t_base, 3).tolist()


def dominance(laps: dict[str, dict], sectors: int = MINI_SECTORS) -> list[dict]:
    """Split the lap into equal-distance mini-sectors and name the driver who was quickest through each one."""
    if not laps:
        return []
    length = min(_arr(lap, "distance")[-1] for lap in laps.values())
    edges = np.linspace(0, length, sectors + 1)
    out = []
    for i in range(sectors):
        times = {}
        for driver, lap in laps.items():
            d, t = _arr(lap, "distance"), _arr(lap, "time")
            times[driver] = float(np.interp(edges[i + 1], d, t) - np.interp(edges[i], d, t))
        best = min(times, key=times.get)
        out.append(
            {
                "from_m": round(float(edges[i]), 1),
                "to_m": round(float(edges[i + 1]), 1),
                "driver_id": best,
                "times": {k: round(v, 3) for k, v in times.items()},
            }
        )
    return out


def straights(lap: dict, min_length_m: float = 300, full_throttle: float = 98) -> dict:
    """Straight-line behaviour on one lap.

    Full-throttle zones are stretches of at least `min_length_m` with the throttle above `full_throttle`%. Within
    each, "clipping" is the distance over which the car slows down while still at full throttle, which with the
    2026 power units mostly means the battery has stopped deploying.
    """
    d = _arr(lap, "distance")
    v = _arr(lap, "speed")
    thr = _arr(lap, "throttle")
    on = thr >= full_throttle
    zones = []
    i = 0
    n = len(d)
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and on[j + 1]:
            j += 1
        if d[j] - d[i] >= min_length_m:
            seg_v = v[i : j + 1]
            peak = int(np.argmax(seg_v))
            after = seg_v[peak:]
            # Distance after the peak where speed keeps dropping by more than 1 km/h at full throttle.
            clipping = (
                float(d[i + peak + len(after) - 1] - d[i + peak])
                if after.size > 1 and seg_v[peak] - after[-1] > 1
                else 0.0
            )
            zones.append(
                {
                    "from_m": round(float(d[i]), 1),
                    "to_m": round(float(d[j]), 1),
                    "entry_kmh": round(float(seg_v[0]), 1),
                    "peak_kmh": round(float(seg_v[peak]), 1),
                    "exit_kmh": round(float(seg_v[-1]), 1),
                    "peak_at_m": round(float(d[i + peak]), 1),
                    "clipping_m": round(clipping, 1),
                    "speed_lost_kmh": round(float(seg_v[peak] - seg_v[-1]), 1),
                }
            )
        i = j + 1
    total = float(d[-1] - d[0]) if n > 1 else 0.0
    return {
        "top_speed_kmh": round(float(v.max()), 1) if n else None,
        "full_throttle_pct": round(float(on.mean() * 100), 1) if n else None,
        "clipping_m": round(sum(z["clipping_m"] for z in zones), 1),
        "lap_length_m": round(total, 1),
        "zones": zones,
    }
