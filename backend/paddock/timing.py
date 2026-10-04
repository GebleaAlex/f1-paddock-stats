"""2018+ timing data through FastF1: laps with tyres and sectors, track status (safety cars, flags), race control
messages, weather, and the fastest-lap telemetry of every driver in each session.

`paddock timing --years 2024 2025 2026` processes every qualifying, sprint qualifying, sprint and race of those
seasons that is not processed yet and writes small Parquet files per session to data/timing/<session_key>/.
`paddock build` then loads them into the database. FastF1's raw cache is deleted after each event, so disk use
stays small, and the run stops cleanly when FastF1's request limit is reached; run it again later to continue.

The data comes from Formula 1's live timing service and has no open licence: it is used to draw charts and
summaries on the site and is never offered as a download or a bulk API (see data/LICENSE.md).
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np

from . import config

TIMING_DIR = config.DATA_DIR / "timing"
CACHE_DIR = config.DATA_DIR / "fastf1-cache"

# FastF1 session names -> our short codes.
SESSIONS = {
    "Qualifying": "Q",
    "Sprint Qualifying": "SQ",
    "Sprint Shootout": "SQ",
    "Sprint": "S",
    "Race": "R",
}

log = logging.getLogger("paddock.timing")


def session_key(year: int, rnd: int, code: str) -> str:
    return f"{year}-{rnd:02d}-{code}"


def _ms(td) -> float | None:
    """Timedelta (pandas) to milliseconds, None for NaT."""
    if _na(td):
        return None
    try:
        return round(td.total_seconds() * 1000)
    except (AttributeError, ValueError):
        return None


def _na(x) -> bool:
    import pandas as pd

    try:
        return x is None or bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def _int(x) -> int | None:
    return None if _na(x) else int(x)


def _float(x) -> float | None:
    return None if _na(x) else float(x)


def _str(x) -> str | None:
    return None if _na(x) else str(x)


def _bool(x, default: bool | None = None) -> bool | None:
    return default if _na(x) else bool(x)


def _seconds(td) -> float | None:
    ms = _ms(td)
    return None if ms is None else ms / 1000


def _driver_map(con: duckdb.DuckDBPyConnection, year: int, rnd: int, code: str) -> dict[str, str]:
    """Car number -> f1db driver id for the race weekend (any session the driver took part in)."""
    rows = con.execute(
        """
        SELECT DISTINCT x.driver_number, x.driver_id FROM race r
        JOIN (
            SELECT race_id, driver_number, driver_id FROM race_result
            UNION ALL SELECT race_id, driver_number, driver_id FROM qualifying_result
            UNION ALL SELECT race_id, driver_number, driver_id FROM sprint_race_result
            UNION ALL SELECT race_id, driver_number, driver_id FROM starting_grid_position
        ) x ON x.race_id = r.id
        WHERE r.year = ? AND r.round = ?
        """,
        [year, rnd],
    ).fetchall()
    return {str(n): d for n, d in rows if n is not None}


def _write(df_rows: list[dict], path: Path) -> None:
    """Write rows to Parquet through DuckDB (keeps us free of a pyarrow dependency)."""
    if not df_rows:
        return
    con = duckdb.connect()
    cols = list(df_rows[0].keys())
    con.execute("CREATE TABLE t AS SELECT * FROM (SELECT unnest($rows, recursive := true))", {"rows": df_rows})
    con.execute(f"COPY (SELECT {', '.join(cols)} FROM t) TO '{path.as_posix()}' (FORMAT parquet)")
    con.close()


def _resample(tel, step: float = 10.0) -> dict:
    """Telemetry of one lap on an even distance grid (every `step` metres), small enough to send to a browser."""
    d = tel["Distance"].to_numpy(dtype=float)
    keep = np.concatenate([[True], np.diff(d) > 0])
    d = d[keep]
    grid = np.arange(0, d[-1], step)

    def lin(col):
        return np.interp(grid, d, tel[col].to_numpy(dtype=float)[keep])

    def step_col(col):
        values = tel[col].to_numpy(dtype=float)[keep]
        idx = np.clip(np.searchsorted(d, grid, side="right") - 1, 0, len(values) - 1)
        return values[idx]

    t = tel["Time"].dt.total_seconds().to_numpy(dtype=float)[keep]
    return {
        "distance": grid.round(1).tolist(),
        "time": np.interp(grid, d, t).round(3).tolist(),
        "speed": lin("Speed").round(1).tolist(),
        "throttle": lin("Throttle").clip(0, 100).round(0).tolist(),
        "brake": step_col("Brake").astype(int).tolist(),
        "gear": step_col("nGear").astype(int).tolist(),
        "rpm": lin("RPM").round(0).tolist(),
        "drs": step_col("DRS").astype(int).tolist(),
        "x": lin("X").round(1).tolist(),
        "y": lin("Y").round(1).tolist(),
    }


def process_session(session, year: int, rnd: int, code: str, race_id: int, drivers: dict[str, str]) -> dict:
    key = session_key(year, rnd, code)
    out = TIMING_DIR / key
    tmp = out.with_name(key + ".part")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    from fastf1.req import RateLimitExceededError

    try:
        session.load(laps=True, telemetry=True, weather=True, messages=True)
    except RateLimitExceededError:
        raise
    except Exception as e:  # some sessions miss car or position data: keep the laps, skip telemetry
        log.warning("%s: loading without telemetry (%s)", key, e)
        session.load(laps=True, telemetry=False, weather=True, messages=True)
    laps = session.laps
    t0 = getattr(session, "t0_date", None)  # wall-clock time of session time zero

    lap_rows = []
    for _, r in laps.iterrows():
        driver_id = drivers.get(str(r["DriverNumber"]))
        if not driver_id or _na(r["LapNumber"]):
            continue
        lap_rows.append(
            {
                "session_key": key,
                "driver_id": driver_id,
                "lap": int(r["LapNumber"]),
                "time_ms": _ms(r["LapTime"]),
                "s1_ms": _ms(r["Sector1Time"]),
                "s2_ms": _ms(r["Sector2Time"]),
                "s3_ms": _ms(r["Sector3Time"]),
                "compound": _str(r["Compound"]),
                "tyre_life": _int(r["TyreLife"]),
                "stint": _int(r["Stint"]),
                "fresh_tyre": _bool(r["FreshTyre"]),
                "pit_in": _ms(r["PitInTime"]) is not None,
                "pit_out": _ms(r["PitOutTime"]) is not None,
                "track_status": _str(r["TrackStatus"]),
                "position": _int(r["Position"]),
                "is_accurate": _bool(r["IsAccurate"], False),
                "deleted": _bool(r["Deleted"], False),
                "speed_trap": _float(r["SpeedST"]),
                "lap_start_s": _seconds(r["LapStartTime"]),
                "personal_best": _bool(r["IsPersonalBest"], False),
            }
        )
    _write(lap_rows, tmp / "lap.parquet")

    _write(
        [
            {"session_key": key, "t_s": _seconds(r["Time"]), "status": str(r["Status"]), "message": str(r["Message"])}
            for _, r in session.track_status.iterrows()
        ],
        tmp / "track_status.parquet",
    )

    rc = []
    for _, r in session.race_control_messages.iterrows():
        rc.append(
            {
                "session_key": key,
                "t_s": None if t0 is None or _na(r["Time"]) else (r["Time"] - t0).total_seconds(),
                "lap": _int(r["Lap"]),
                "category": _str(r["Category"]),
                "flag": _str(r["Flag"]),
                "scope": _str(r["Scope"]),
                "driver_id": None if _na(r["RacingNumber"]) else drivers.get(str(r["RacingNumber"])),
                "message": str(r["Message"]),
            }
        )
    _write(rc, tmp / "race_control.parquet")

    w = session.weather_data
    _write(
        [
            {
                "session_key": key,
                "t_s": _seconds(r["Time"]),
                "air_temp": _float(r["AirTemp"]),
                "track_temp": _float(r["TrackTemp"]),
                "humidity": _float(r["Humidity"]),
                "rain": _bool(r["Rainfall"], False),
                "wind_speed": _float(r["WindSpeed"]),
            }
            for _, r in w.iterrows()
        ]
        if w is not None
        else [],
        tmp / "weather.parquet",
    )

    # Fastest lap of every driver, resampled.
    tel_rows = []
    for number, driver_id in drivers.items():
        try:
            dl = laps.pick_drivers(number)
            if dl.empty:
                continue
            fl = dl.pick_fastest()
            if fl is None or getattr(fl, "empty", False) or _ms(fl["LapTime"]) is None:
                continue
            tel = fl.get_telemetry()
            if tel is None or len(tel) < 20:
                continue
            channels = _resample(tel)
            if len(channels["distance"]) < 20:  # no usable distance (car data missing): nothing to compare
                continue
            tel_rows.append(
                {
                    "session_key": key,
                    "driver_id": driver_id,
                    "lap": _int(fl["LapNumber"]),
                    "lap_time_ms": _ms(fl["LapTime"]),
                    **channels,
                }
            )
        except Exception as e:  # one driver's missing telemetry must not lose the session
            log.warning("%s %s: no telemetry (%s)", key, driver_id, e)
    _write(tel_rows, tmp / "telemetry.parquet")

    try:
        ci = session.get_circuit_info()
    except Exception:  # circuit info needs position data, which a few sessions lack
        ci = None
    corners = (
        [
            {
                "number": _int(c["Number"]),
                "letter": _str(c["Letter"]) or "",
                "distance": _float(c["Distance"]),
                "x": _float(c["X"]),
                "y": _float(c["Y"]),
                "angle": _float(c["Angle"]),
            }
            for _, c in ci.corners.iterrows()
        ]
        if ci is not None
        else []
    )
    total_laps = _int(laps["LapNumber"].max()) if not laps.empty else None
    meta = {
        "session_key": key,
        "race_id": race_id,
        "year": year,
        "round": rnd,
        "type": code,
        "name": session.name,
        "start_utc": str(session.date),
        "total_laps": total_laps,
        "rotation": float(ci.rotation) if ci is not None else 0.0,
        "corners": json.dumps(corners),
        "processed_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _write([meta], tmp / "session.parquet")
    shutil.rmtree(out, ignore_errors=True)
    tmp.replace(out)
    return meta


def run(years: list[int], codes: set[str] | None = None, limit: int | None = None, db_path: Path | None = None) -> dict:
    import fastf1
    from fastf1.req import RateLimitExceededError

    logging.getLogger("fastf1").setLevel(logging.ERROR)
    TIMING_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))
    codes = codes or {"Q", "SQ", "S", "R"}
    con = duckdb.connect(str(db_path or config.current_db_path()), read_only=True)
    done, skipped, failed = [], 0, []
    attempts = 0
    failures_in_a_row = 0
    try:
        for year in years:
            races = con.execute(
                "SELECT id, round FROM race WHERE year = ? AND id IN (SELECT race_id FROM race_result) ORDER BY round",
                [year],
            ).fetchall()
            schedule = fastf1.get_event_schedule(year, include_testing=False)
            for race_id, rnd in races:
                ev = schedule[schedule["RoundNumber"] == rnd]
                if ev.empty:
                    continue
                ev = ev.iloc[0]
                names = [ev[f"Session{i}"] for i in range(1, 6) if ev.get(f"Session{i}") in SESSIONS]
                touched = False
                for name in names:
                    code = SESSIONS[name]
                    if code not in codes or (TIMING_DIR / session_key(year, rnd, code) / "session.parquet").exists():
                        skipped += 1
                        continue
                    if limit is not None and attempts >= limit:
                        return {"done": done, "skipped": skipped, "failed": failed, "stopped": "limit"}
                    if failures_in_a_row >= 3:
                        return {"done": done, "skipped": skipped, "failed": failed, "stopped": "3 failures in a row"}
                    attempts += 1
                    started = time.perf_counter()
                    try:
                        s = fastf1.get_session(year, int(rnd), name)
                        drivers = _driver_map(con, year, int(rnd), code)
                        process_session(s, year, int(rnd), code, race_id, drivers)
                        done.append(session_key(year, rnd, code))
                        touched = True
                        failures_in_a_row = 0
                        print(
                            f"  {session_key(year, rnd, code)} {name:<18} {time.perf_counter() - started:5.1f}s",
                            flush=True,
                        )
                    except RateLimitExceededError:
                        return {"done": done, "skipped": skipped, "failed": failed, "stopped": "rate limit"}
                    except Exception as e:  # keep going; a single broken session should not stop a season
                        failed.append(f"{session_key(year, rnd, code)}: {e}")
                        failures_in_a_row += 1
                        touched = True
                        shutil.rmtree(TIMING_DIR / f"{session_key(year, rnd, code)}.part", ignore_errors=True)
                        print(f"  {session_key(year, rnd, code)} FAILED: {e}", flush=True)
                if touched:
                    # The raw FastF1 cache for an event is ~100 MB; we keep only our extracted files.
                    for p in CACHE_DIR.glob(f"{year}/*"):
                        shutil.rmtree(p, ignore_errors=True)
    finally:
        con.close()
    return {"done": done, "skipped": skipped, "failed": failed, "stopped": None}
