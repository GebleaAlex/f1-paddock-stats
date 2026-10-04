"""Telemetry analysis (2018+): lap comparison, mini-sector dominance, corner by corner and straight-line speed.

Each driver's fastest lap of a session is stored on a 10 m distance grid (see paddock/timing.py). To compare two
laps, every point of the first (the reference) is matched to the moment the second car passed the same place
(`align`); the gap trace, the mini-sectors and the corners all come from that one matching.
"""

from __future__ import annotations

import numpy as np

MINI_SECTORS = 25


def _arr(lap: dict, key: str) -> np.ndarray:
    return np.asarray(lap[key], dtype=float)


def _path_length(lap: dict) -> float | None:
    """Lap length measured from the car's positions (x and y are in tenths of a metre), or None without them."""
    if "x" not in lap or "y" not in lap:
        return None
    x, y = _arr(lap, "x"), _arr(lap, "y")
    if x.size < 2 or not np.any(x) or not np.any(y):
        return None
    return float(np.hypot(np.diff(x), np.diff(y)).sum() / 10)


def has_gaps(lap: dict, tolerance: float = 0.01) -> bool:
    """True when the speed trace has a dropout: distance integrated from speed disagrees with the distance driven.

    During a dropout the speed reads flat for a few hundred metres, which stretches the speed-based distance.
    """
    d = _arr(lap, "distance")
    path = _path_length(lap)
    return bool(path and d.size and abs(d[-1] / path - 1) > tolerance)


def path_distance(lap: dict) -> list[float]:
    """Distance along the lap measured from the car's positions, to replace a speed-based distance with dropouts."""
    x, y = _arr(lap, "x"), _arr(lap, "y")
    return np.round(np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)) / 10)]), 1).tolist()


def dropouts(lap: dict, min_samples: int = 3) -> list[tuple[int, int]]:
    """Index ranges where the car's position stalls (under 3 m per 10 m sample) although the speed says it is
    moving: the timing feed lost the car there, so nothing inside can be trusted."""
    if _path_length(lap) is None:
        return []
    x, y = _arr(lap, "x"), _arr(lap, "y")
    stalled = np.hypot(np.diff(x), np.diff(y)) / 10 < 3
    runs, i = [], 0
    while i < stalled.size:
        if stalled[i]:
            j = i
            while j + 1 < stalled.size and stalled[j + 1]:
                j += 1
            if j - i + 1 >= min_samples:
                runs.append((i, j + 1))
            i = j + 1
        else:
            i += 1
    return runs


def _project(base: dict, other: dict) -> np.ndarray:
    """For every point of `base`, the time at which `other` passed the same place: the nearest point on `other`'s
    path, searched a little ahead of the previous match and refined along the segment."""
    bx, by = _arr(base, "x"), _arr(base, "y")
    ox, oy, ot = _arr(other, "x"), _arr(other, "y"), _arr(other, "time")
    n, m = bx.size, ox.size
    out = np.empty(n)
    j = 0
    for i in range(n):
        lo, hi = max(0, j - 5), min(m - 1, j + 40)
        k = lo + int(np.argmin((ox[lo : hi + 1] - bx[i]) ** 2 + (oy[lo : hi + 1] - by[i]) ** 2))
        best_t, best_d = ot[k], np.inf
        for a in (k - 1, k):
            if a < 0 or a + 1 >= m:
                continue
            sx, sy = ox[a + 1] - ox[a], oy[a + 1] - oy[a]
            length2 = sx * sx + sy * sy
            f = 0.0 if length2 == 0 else min(1.0, max(0.0, ((bx[i] - ox[a]) * sx + (by[i] - oy[a]) * sy) / length2))
            dist = (ox[a] + f * sx - bx[i]) ** 2 + (oy[a] + f * sy - by[i]) ** 2
            if dist < best_d:
                best_d, best_t = dist, ot[a] + f * (ot[a + 1] - ot[a])
        out[i] = best_t
        j = k
    out[0], out[-1] = ot[0], ot[-1]
    # Positions jitter by a metre or two; smooth the matched times over about 50 m so the gap trace is not jagged.
    gap = out - _arr(base, "time")
    if n > 10:
        smooth = np.convolve(np.pad(gap, 2, mode="edge"), np.ones(5) / 5, mode="valid")
        smooth[0], smooth[-1] = gap[0], gap[-1]
        out = _arr(base, "time") + smooth
    return np.maximum.accumulate(out)


def _sector_lines(lap: dict) -> list[float] | None:
    """Times (s) at which the lap crossed the end of sector 1 and sector 2, from the official sector times."""
    sec = lap.get("sectors") or lap
    s1, s2 = sec.get("s1_ms"), sec.get("s2_ms")
    return [s1 / 1000, (s1 + s2) / 1000] if s1 and s2 else None


def align(base: dict, other: dict) -> np.ndarray:
    """For every point of `base`, the time at which `other` was at the same place on track.

    Normally the other lap's distance is stretched onto the base lap's, piece by piece between the two sector lines,
    where the official sector times say exactly when each car passed. When either lap's speed trace has a dropout,
    the laps are matched by position on track instead. Checked against the sector times of every 2018+ qualifying
    session loaded: pinned at one line, the error at the other has a median of 0.04 s (plain stretching: 0.05 s,
    worst case 2.5 s; position matching brings the worst case under 0.5 s).
    """
    d, t = _arr(base, "distance"), _arr(base, "time")
    od, ot = _arr(other, "distance"), _arr(other, "time")
    gaps = any(lap.get("telemetry_gaps") or has_gaps(lap) for lap in (base, other))
    if gaps and _path_length(base) and _path_length(other):
        return _project(base, other)
    xs, ys = [0.0], [0.0]
    lines_b, lines_o = _sector_lines(base), _sector_lines(other)
    if lines_b and lines_o:
        for tb, to in zip(lines_b, lines_o, strict=True):
            x, y = float(np.interp(to, ot, od)), float(np.interp(tb, t, d))
            if xs[-1] < x < od[-1] and ys[-1] < y < d[-1]:
                xs.append(x)
                ys.append(y)
    xs.append(float(od[-1]))
    ys.append(float(d[-1]))
    return np.interp(d, np.interp(od, xs, ys), ot)


def delta(base: dict, other: dict, aligned: np.ndarray | None = None) -> list[float]:
    """Time gap of `other` to `base` along `base`'s distance grid, in seconds (positive: `other` is behind)."""
    t_other = align(base, other) if aligned is None else aligned
    return np.round(t_other - _arr(base, "time"), 3).tolist()


def on_base_distance(base: dict, other: dict, aligned: np.ndarray) -> list[float]:
    """`other`'s points placed on `base`'s distance scale, so both laps' traces line up on one chart."""
    return np.round(np.interp(_arr(other, "time"), aligned, _arr(base, "distance")), 1).tolist()


def dominance(laps: dict[str, dict], sectors: int = MINI_SECTORS, aligned: dict | None = None) -> list[dict]:
    """Split the lap into equal-distance mini-sectors and name the driver who was quickest through each one.

    Distances are the first lap's; the other laps are matched to it with `align`.
    """
    if not laps:
        return []
    ids = list(laps)
    base = laps[ids[0]]
    d = _arr(base, "distance")
    when = {ids[0]: _arr(base, "time")}
    for k in ids[1:]:
        given = (aligned or {}).get(k)
        when[k] = align(base, laps[k]) if given is None else given
    edges = np.linspace(0, d[-1], sectors + 1)
    out = []
    for i in range(sectors):
        times = {k: float(np.interp(edges[i + 1], d, t) - np.interp(edges[i], d, t)) for k, t in when.items()}
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


def gap_regions(base: dict, other: dict, aligned: np.ndarray, margin_m: float = 150) -> list[tuple[float, float]]:
    """Both laps' dropouts (see `dropouts`) as distance ranges on `base`'s scale, widened by `margin_m`."""
    d = _arr(base, "distance")
    out = [(float(d[a]) - margin_m, float(d[b]) + margin_m) for a, b in dropouts(base)]
    ot = _arr(other, "time")
    for a, b in dropouts(other):
        lo, hi = (float(np.interp(ot[k], aligned, d)) for k in (a, b))
        out.append((lo - margin_m, hi + margin_m))
    return sorted(out)


def corner_deltas(
    base: dict,
    other: dict,
    corners: list[dict],
    aligned: np.ndarray | None = None,
    before_m: float = 200,
    after_m: float = 150,
    gaps: list[tuple[float, float]] | None = None,
) -> dict:
    """Time gained or lost through each corner between two laps, with minimum speed and braking point.

    Everything is measured on `base`'s distance, with `other` matched to it by `align`, so the corners and the
    straights between them add up exactly to the lap time gap. A corner runs from up to `before_m` before the apex
    (the braking zone) to `after_m` after it (the exit), never past halfway to the next corner. `gain_s` is positive
    when `base` was quicker. Differences of a few hundredths are within the precision of the data. A corner that
    overlaps one of `gaps` (telemetry dropouts) is marked unreliable.
    """
    d = _arr(base, "distance")
    if d.size < 2 or not corners:
        return {"corners": [], "lap_gap_s": None, "straights_s": None}
    t_other = align(base, other) if aligned is None else aligned
    gap = t_other - _arr(base, "time")
    od, ot = _arr(other, "distance"), _arr(other, "time")
    # Where the other car was, on its own distance scale, at each point of the base lap.
    other_at = np.interp(t_other, ot, od)
    end = float(d[-1])
    ordered = sorted((c for c in corners if 0 < c["distance"] < end), key=lambda c: c["distance"])
    apexes = [c["distance"] for c in ordered]

    def gap_at(m: float) -> float:
        return float(np.interp(m, d, gap))

    def stats(lap: dict, start: float, apex: float, stop: float) -> tuple[float | None, int | None]:
        ld, v, br = _arr(lap, "distance"), _arr(lap, "speed"), _arr(lap, "brake")
        inside = (ld >= start) & (ld <= stop)
        braking = np.flatnonzero((ld >= start) & (ld <= apex) & (br > 0))
        return (
            round(float(v[inside].min()), 1) if inside.any() else None,
            round(apex - float(ld[braking[0]])) if braking.size else None,
        )

    out = []
    for i, c in enumerate(ordered):
        apex = apexes[i]
        start = max((apexes[i - 1] + apex) / 2 if i else 0.0, apex - before_m)
        stop = min((apex + apexes[i + 1]) / 2 if i + 1 < len(apexes) else end, apex + after_m)
        o_start, o_apex, o_stop = (float(np.interp(m, d, other_at)) for m in (start, apex, stop))
        b_speed, b_brake = stats(base, start, apex, stop)
        o_speed, o_brake = stats(other, o_start, o_apex, o_stop)
        out.append(
            {
                "corner": f"{c['number']}{c.get('letter') or ''}",
                "apex_m": round(apex),
                "from_m": round(start),
                "to_m": round(stop),
                "gain_s": round(gap_at(stop) - gap_at(start), 3),
                "min_speed": [b_speed, o_speed],
                "brake_before_apex_m": [b_brake, o_brake],
                "reliable": not any(lo < stop and hi > start for lo, hi in gaps or []),
            }
        )
    # The official lap times, not the end of the telemetry trace, which stops a sample short of the line.
    if base.get("lap_time_ms") and other.get("lap_time_ms"):
        total = (other["lap_time_ms"] - base["lap_time_ms"]) / 1000
    else:
        total = gap_at(end)
    return {
        "corners": out,
        "lap_gap_s": round(total, 3),
        "straights_s": round(total - sum(c["gain_s"] for c in out), 3),
    }


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
