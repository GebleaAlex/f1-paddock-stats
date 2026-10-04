"""Race analysis built from lap data: race story events, safety-car periods, tyre stints and pace, degradation,
undercut and overcut verdicts and pit-stop time loss.

Everything here is a pure function of rows from the database, so it is easy to test and reuse (API and MCP).
Lap-by-lap times and positions exist from 1996 (Jolpica), pit stops from 2011 (f1db), and tyres, track status and
race control messages from 2018 (FastF1 timing).

Assumptions are spelled out once, here, and shown on the site:
- Fuel correction: cars burn about FUEL_START_KG over the race and each kilogram costs FUEL_S_PER_KG seconds per
  lap, so a lap is corrected by the fuel still on board.
- A "clean" lap is a green-flag racing lap: not lap 1, not an in- or out-lap, no safety car, and not more than
  7% slower than the driver's median lap.
"""

from __future__ import annotations

import re
from collections import defaultdict
from statistics import median

import numpy as np

FUEL_START_KG = 100.0
FUEL_S_PER_KG = 0.03
SLOW_LAP = 1.07

# FastF1 track status codes (a lap can carry several, e.g. "24" or "671").
STATUS = {"2": "yellow", "4": "sc", "5": "red", "6": "vsc", "7": "vsc"}
PERIOD_LABEL = {"sc": "Safety car", "vsc": "Virtual safety car", "red": "Red flag"}


def lap_status(code: str | None) -> str | None:
    """Most important neutralisation on a lap: red flag, then safety car, then virtual safety car."""
    if not code:
        return None
    for c, kind in (("5", "red"), ("4", "sc"), ("6", "vsc"), ("7", "vsc")):
        if c in code:
            return kind
    return None


def neutralised_laps(timing_laps: list[dict]) -> dict[int, str]:
    """Race lap -> 'sc' | 'vsc' | 'red', taken from the race leader's lap (the leader defines the race lap)."""
    by_lap: dict[int, str] = {}
    rank = {"red": 3, "sc": 2, "vsc": 1}
    for r in timing_laps:
        kind = lap_status(r.get("track_status"))
        if not kind or r.get("position") not in (1, None):
            continue
        if rank[kind] > rank.get(by_lap.get(r["lap"], ""), 0):
            by_lap[r["lap"]] = kind
    return by_lap


def periods(neutral: dict[int, str]) -> list[dict]:
    """Consecutive laps of the same neutralisation joined into periods."""
    out: list[dict] = []
    for lap in sorted(neutral):
        kind = neutral[lap]
        if out and out[-1]["kind"] == kind and out[-1]["to_lap"] == lap - 1:
            out[-1]["to_lap"] = lap
        else:
            out.append({"kind": kind, "label": PERIOD_LABEL[kind], "from_lap": lap, "to_lap": lap})
    return out


WET_COMPOUNDS = ("INTERMEDIATE", "WET")
# A race counts as wet when at least this share of all laps was driven on intermediate or wet tyres.
WET_RACE_SHARE = 0.1


def race_conditions(timing_laps: list[dict], rain: bool) -> dict:
    """Safety cars, virtual safety cars, red flags and wet running in one race (2018+).

    A safety car that only leads the field away after a red flag is part of that red flag, not a new one.
    """
    neutral = neutralised_laps(timing_laps)
    spans = periods(neutral)
    count = {"sc": 0, "vsc": 0, "red": 0}
    for i, p in enumerate(spans):
        restart = (
            i and p["kind"] == "sc" and spans[i - 1]["kind"] == "red" and spans[i - 1]["to_lap"] == p["from_lap"] - 1
        )
        if not restart:
            count[p["kind"]] += 1
    tyres = [r["compound"] for r in timing_laps if r.get("compound")]
    share = sum(c in WET_COMPOUNDS for c in tyres) / len(tyres) if tyres else 0.0
    return {
        "safety_cars": count["sc"],
        "virtual_safety_cars": count["vsc"],
        "red_flags": count["red"],
        "neutralised_laps": len(neutral),
        "race_laps": max((r["lap"] for r in timing_laps), default=0),
        "rain": bool(rain),
        "wet_share": round(share, 3),
        "wet": share >= WET_RACE_SHARE,
    }


def fuel_corrected(time_ms: float, lap: int, total_laps: int) -> float:
    fuel_on_board = FUEL_START_KG * max(0.0, 1 - (lap - 1) / max(total_laps, 1))
    return time_ms - fuel_on_board * FUEL_S_PER_KG * 1000


def clean_laps(laps: list[dict], neutral: dict[int, str]) -> list[dict]:
    """Green-flag racing laps of one driver (see module docstring)."""
    times = [r["time_ms"] for r in laps if r.get("time_ms")]
    if not times:
        return []
    limit = median(times) * SLOW_LAP
    return [
        r
        for r in laps
        if r.get("time_ms")
        and r["lap"] > 1
        and not r.get("pit_in")
        and not r.get("pit_out")
        and r["lap"] not in neutral
        and r["time_ms"] <= limit
    ]


def stints(timing_laps: list[dict], total_laps: int, neutral: dict[int, str]) -> dict[str, list[dict]]:
    """Per driver: stints with compound, laps, median fuel-corrected pace and degradation in seconds per lap."""
    by_driver: dict[str, list[dict]] = defaultdict(list)
    for r in timing_laps:
        by_driver[r["driver_id"]].append(r)
    out: dict[str, list[dict]] = {}
    for driver, laps in by_driver.items():
        laps.sort(key=lambda r: r["lap"])
        clean = {r["lap"] for r in clean_laps(laps, neutral)}
        # A stint ends when the tyres change: a new compound, or the tyre age starting again. Pit-lane passes
        # without a tyre change (e.g. the field led through the pit lane under a safety car) and FastF1's own stint
        # counter, which sometimes moves on without a stop, do not count. Without tyre data, a pit stop ends a stint.
        groups: dict[int, list[dict]] = defaultdict(list)
        current = 1
        for i, r in enumerate(laps):
            if i:
                prev = laps[i - 1]
                if r.get("tyre_life") is not None and prev.get("tyre_life") is not None:
                    changed = r.get("compound") != prev.get("compound") or r["tyre_life"] < prev["tyre_life"]
                else:
                    changed = bool(prev.get("pit_in") or r.get("pit_out")) or r.get("compound") != prev.get("compound")
                if changed:
                    current += 1
            groups[current].append(r)
        result = []
        for n in sorted(groups):
            g = groups[n]
            good = [r for r in g if r["lap"] in clean]
            corrected = [fuel_corrected(r["time_ms"], r["lap"], total_laps) for r in good]
            deg = None
            if len(good) >= 5:
                x = np.array([r.get("tyre_life") or i for i, r in enumerate(good)], dtype=float)
                y = np.array(corrected) / 1000
                if np.ptp(x) > 0:
                    deg = float(np.polyfit(x, y, 1)[0])
            start_life = g[0].get("tyre_life")
            result.append(
                {
                    "stint": n,
                    "compound": g[0].get("compound"),
                    "fresh": g[0].get("fresh_tyre"),
                    "tyre_age_at_start": (start_life - 1) if start_life else None,
                    "from_lap": g[0]["lap"],
                    "to_lap": g[-1]["lap"],
                    "laps": len(g),
                    "clean_laps": len(good),
                    "median_ms": round(median(r["time_ms"] for r in good)) if good else None,
                    "median_corrected_ms": round(median(corrected)) if corrected else None,
                    "degradation_s_per_lap": None if deg is None else round(deg, 3),
                }
            )
        out[driver] = result
    return out


_PENALTY = re.compile(
    r"(\d+ SECOND TIME PENALTY|DRIVE THROUGH PENALTY|STOP AND GO PENALTY|\d+ PLACE GRID PENALTY)[^(]*?FOR CAR \d+ \((\w+)\)"
    r"(?:\s*-\s*(.*))?",
    re.IGNORECASE,
)


def penalty_text(message: str, name: str | None) -> str | None:
    """Race control penalty message in plain words, or None when it is not a penalty decision."""
    m = _PENALTY.search(message)
    if not m:
        return None
    what, code, reason = m.group(1).lower(), m.group(2), (m.group(3) or "").strip().lower()
    who = name or code
    return f"{who}: {what}" + (f" for {reason}" if reason else "")


def pit_loss(
    laps_by_driver: dict[str, list[tuple[int, int]]], stops: list[dict], neutral: dict[int, str] | None = None
) -> list[float]:
    """Seconds lost to each green-flag pit stop: in-lap plus out-lap, minus two of the driver's typical laps.

    With track status (2018+), stops whose in- or out-lap was neutralised are left out and neutralised laps do not
    count towards the typical lap: a stop under a safety car costs far less, and its slow laps are not pit time.
    """
    neutral = neutral or {}
    losses = []
    for s in stops:
        if s["lap"] in neutral or s["lap"] + 1 in neutral:
            continue
        laps = dict(laps_by_driver.get(s["driver_id"], []))
        lap_in, lap_out = laps.get(s["lap"]), laps.get(s["lap"] + 1)
        normal = [t for n, t in laps.items() if n > 1 and n not in neutral and t]
        if not lap_in or not lap_out or len(normal) < 10:
            continue
        typical = median(normal)
        # Ignore stops where either lap was far off (safety car, damage, red flag): they say nothing about the lane.
        if lap_in > typical * 1.6 or lap_out > typical * 1.6:
            continue
        losses.append(round((lap_in + lap_out - 2 * typical) / 1000, 2))
    return losses


def pit_battles(
    positions: dict[str, dict[int, int]],
    cumulative: dict[str, dict[int, int]],
    stops: list[dict],
    neutral: dict[int, str],
    window: int = 6,
    max_gap_s: float = 4.0,
) -> list[dict]:
    """Undercut and overcut attempts between cars running next to each other.

    For every stop by driver A on lap La, look at the car directly ahead of and behind A on the lap before. If that
    car (B) stops later, within `window` laps, while A has not stopped again, compare the order the lap after B's
    stop with the order before A's: the earlier stopper gaining a place is a successful undercut, the later stopper
    gaining one a successful overcut.
    """
    stops_by_driver: dict[str, list[int]] = defaultdict(list)
    for s in stops:
        stops_by_driver[s["driver_id"]].append(s["lap"])
    out = []
    seen = set()
    for s in sorted(stops, key=lambda x: x["lap"]):
        a, la = s["driver_id"], s["lap"]
        before = la - 1
        pos_a = positions.get(a, {}).get(before)
        if not pos_a:
            continue
        for b, laps_pos in positions.items():
            if b == a or abs((laps_pos.get(before) or 99) - pos_a) != 1:
                continue
            later = [lb for lb in stops_by_driver.get(b, []) if la < lb <= la + window]
            if not later:
                continue
            lb = later[0]
            if any(la < x <= lb for x in stops_by_driver.get(a, [])):  # A stopped again in between
                continue
            key = (a, b, la)
            if key in seen:
                continue
            seen.add(key)
            after = lb + 1
            pa_after, pb_after = positions.get(a, {}).get(after), laps_pos.get(after)
            ca_b, cb_b = cumulative.get(a, {}).get(before), cumulative.get(b, {}).get(before)
            ca_a, cb_a = cumulative.get(a, {}).get(after), cumulative.get(b, {}).get(after)
            if any(v is None for v in (pa_after, pb_after, ca_b, cb_b, ca_a, cb_a)):
                continue
            gap_before = (ca_b - cb_b) / 1000  # positive: A behind B
            gap_after = (ca_a - cb_a) / 1000
            if abs(gap_before) > max_gap_s or any(x in neutral for x in range(la, lb + 2)):
                continue  # too far apart to be a battle, or decided by a safety car rather than strategy
            a_ahead_before = pos_a < laps_pos[before]
            a_ahead_after = pa_after < pb_after
            if not a_ahead_before and a_ahead_after:
                verdict, winner = "undercut worked", a
            elif a_ahead_before and not a_ahead_after:
                verdict, winner = "overcut worked", b
            elif not a_ahead_before:
                verdict, winner = "undercut failed", b
            else:
                verdict, winner = "overcut failed", a
            out.append(
                {
                    "early": a,
                    "late": b,
                    "early_lap": la,
                    "late_lap": lb,
                    "verdict": verdict,
                    "winner": winner,
                    "gap_before_s": round(gap_before, 2),
                    "gap_after_s": round(gap_after, 2),
                }
            )
    return out
