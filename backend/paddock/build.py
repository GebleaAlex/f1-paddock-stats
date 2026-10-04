"""Builds data/paddock.duckdb from the downloaded sources.

The build writes to a temporary file and swaps it in at the end, so a running API keeps reading the previous database
until the new one is complete.

Tables:
- every f1db table and view, copied as-is (f1db ids such as `max-verstappen`, `red-bull`, `monza` are the ids used
  everywhere in the API and in URLs);
- `lap`: Jolpica lap-by-lap times and positions (1996+), mapped onto f1db race and driver ids;
- `circuit_layout_path`: SVG path data for each circuit layout;
- `retirement_reason`: every retirement reason with a category (accident, technical, rules, other);
- `teammate_race`: one row per pair of teammates per race, with their qualifying and race results side by side;
- `car_rating`: each team's car per season as a gap to the fastest car, drivers taken out (see paddock/cars.py);
- `race_conditions`: safety cars, red flags and wet running per race (2018+, from the timing data);
- `meta`: build time and source versions.
"""

from __future__ import annotations

import contextlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from . import config
from .sources import read_manifest, svg_path_data

SCHEMA_VERSION = 1

# f1db's race_data is the storage table behind the per-type views; the views are what we keep.
SKIP_TABLES = {"race_data"}

JOLPICA_TABLES = ["lap", "session", "sessionentry", "roundentry", "round", "season", "teamdriver", "driver"]


def categorize_retirement(reason: str) -> str:
    r = reason.lower()
    if re.search(r"accident|collision|spun|^spin|crash|damage", r):
        return "accident"
    if re.search(
        r"illegal|ignored|failed|misled|outside assistance|rejoined|push start|incorrect|overtaking on formation"
        r"|reversed|weight|underweight|fuel sample|infringement|too slowly|wrong tyres|unraceworthy",
        r,
    ):
        return "rules"
    if re.search(
        r"withdrew|illness|injury|physical|unfit|unwell|dispute|shortage|safety concerns|car raced by|reserve driver"
        r"|practice only|seized|not ready|^retirement$|camera car",
        r,
    ):
        return "other"
    return "technical"


def _copy_f1db(con: duckdb.DuckDBPyConnection, f1db_path: Path) -> list[str]:
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute(f"ATTACH '{f1db_path.as_posix()}' AS src (TYPE sqlite, READ_ONLY)")
    names = [
        r[0]
        for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_catalog = 'src' ORDER BY table_name"
        ).fetchall()
    ]
    for name in names:
        if name in SKIP_TABLES or name.startswith("sqlite_"):
            continue
        con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM src."{name}"')
    con.execute("DETACH src")

    # SQLite stores dates as text. Make the ones we filter and sort on real dates.
    for table, columns in {
        "race": ["date"],
        "driver": ["date_of_birth", "date_of_death"],
    }.items():
        for col in columns:
            con.execute(f'ALTER TABLE "{table}" ALTER COLUMN {col} TYPE DATE USING TRY_CAST({col} AS DATE)')
    return [n for n in names if n not in SKIP_TABLES]


def _load_laps(con: duckdb.DuckDBPyConnection, jolpica_dir: Path) -> None:
    for t in JOLPICA_TABLES:
        path = (jolpica_dir / f"formula_one_{t}.csv").as_posix()
        con.execute(f"CREATE TEMP TABLE j_{t} AS SELECT * FROM read_csv('{path}', header = true)")

    # One row per race entry in Jolpica, with what we need to find the same entry in f1db.
    con.execute(
        """
        CREATE TEMP TABLE j_entry AS
        SELECT se.id AS session_entry_id, ss.year, rd.number AS round, CAST(re.car_number AS VARCHAR) AS car_number,
               lower(strip_accents(d.surname)) AS surname
        FROM j_sessionentry se
        JOIN j_session s ON s.id = se.session_id AND s.type = 'R'
        JOIN j_round rd ON rd.id = s.round_id
        JOIN j_season ss ON ss.id = rd.season_id
        JOIN j_roundentry re ON re.id = se.round_entry_id
        JOIN j_teamdriver td ON td.id = re.team_driver_id
        JOIN j_driver d ON d.id = td.driver_id
        WHERE se.id IN (SELECT DISTINCT session_entry_id FROM j_lap)
        """
    )
    # Match on race + surname + car number, falling back to surname or car number alone (renumbered cars, double
    # surnames). Keep the best-scoring f1db entry per Jolpica entry.
    con.execute(
        """
        CREATE TEMP TABLE j_map AS
        WITH candidates AS (
            SELECT e.session_entry_id, r.id AS race_id, rr.driver_id,
                   (CASE WHEN lower(strip_accents(d.last_name)) = e.surname THEN 3
                         WHEN contains(lower(strip_accents(d.last_name)), e.surname)
                              OR contains(e.surname, lower(strip_accents(d.last_name))) THEN 2
                         ELSE 0 END)
                 + (CASE WHEN rr.driver_number = e.car_number THEN 1 ELSE 0 END) AS score
            FROM j_entry e
            JOIN race r ON r.year = e.year AND r.round = e.round
            JOIN race_result rr ON rr.race_id = r.id
            JOIN driver d ON d.id = rr.driver_id
        )
        SELECT session_entry_id, race_id, driver_id FROM candidates
        WHERE score >= 2
        QUALIFY row_number() OVER (PARTITION BY session_entry_id ORDER BY score DESC) = 1
        """
    )
    con.execute(
        """
        CREATE TABLE lap AS
        SELECT m.race_id, m.driver_id, CAST(l.number AS INTEGER) AS lap, CAST(l.position AS INTEGER) AS position,
               CAST(round(extract(epoch FROM CAST(CAST(l.time AS VARCHAR) AS INTERVAL)) * 1000) AS INTEGER) AS time_ms
        FROM j_lap l
        JOIN j_map m ON m.session_entry_id = l.session_entry_id
        -- A handful of stray rows (fastest-lap markers) have a lap number but no position; they are not real laps.
        WHERE l.number IS NOT NULL AND l.position IS NOT NULL AND NOT l.is_deleted
        ORDER BY m.race_id, m.driver_id, lap
        """
    )


def _load_layouts(con: duckdb.DuckDBPyConnection, svg_dir: Path) -> None:
    rows = []
    for svg in sorted(svg_dir.glob("*.svg")):
        if path := svg_path_data(svg.read_text(encoding="utf-8")):
            rows.append((svg.stem, path))
    con.execute("CREATE TABLE circuit_layout_path (layout_id VARCHAR PRIMARY KEY, path VARCHAR NOT NULL)")
    if rows:
        con.executemany("INSERT INTO circuit_layout_path VALUES (?, ?)", rows)


def _derive(con: duckdb.DuckDBPyConnection) -> None:
    reasons = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT reason_retired FROM race_result WHERE reason_retired IS NOT NULL"
        ).fetchall()
    ]
    con.execute("CREATE TABLE retirement_reason (reason VARCHAR PRIMARY KEY, category VARCHAR NOT NULL)")
    con.executemany("INSERT INTO retirement_reason VALUES (?, ?)", [(r, categorize_retirement(r)) for r in reasons])

    # Teammates: drivers of the same constructor in the same race (shared-car entries excluded). The qualifying gap
    # compares the last session both drivers set a time in (Q3, then Q2, then Q1, then the single-session time), as
    # a percentage of the faster of the two: positive means driver_a was slower.
    con.execute(
        """
        CREATE TABLE teammate_race AS
        WITH rr AS (
            SELECT race_id, driver_id, constructor_id, position_number, position_text, position_display_order,
                   points, reason_retired, laps, grid_position_number
            FROM race_result WHERE NOT coalesce(shared_car, false)
        ), q AS (
            SELECT race_id, driver_id, position_number, q1_millis, q2_millis, q3_millis, time_millis
            FROM qualifying_result
        ), pairs AS (
            SELECT a.race_id, a.constructor_id, a.driver_id AS driver_a, b.driver_id AS driver_b,
                   a.position_number AS race_pos_a, b.position_number AS race_pos_b,
                   a.position_text AS race_text_a, b.position_text AS race_text_b,
                   a.position_display_order AS race_order_a, b.position_display_order AS race_order_b,
                   coalesce(a.points, 0) AS points_a, coalesce(b.points, 0) AS points_b,
                   a.reason_retired AS reason_a, b.reason_retired AS reason_b,
                   a.grid_position_number AS grid_a, b.grid_position_number AS grid_b,
                   qa.position_number AS quali_pos_a, qb.position_number AS quali_pos_b,
                   CASE
                       WHEN qa.q3_millis IS NOT NULL AND qb.q3_millis IS NOT NULL THEN qa.q3_millis
                       WHEN qa.q2_millis IS NOT NULL AND qb.q2_millis IS NOT NULL THEN qa.q2_millis
                       WHEN qa.q1_millis IS NOT NULL AND qb.q1_millis IS NOT NULL THEN qa.q1_millis
                       ELSE qa.time_millis END AS quali_ms_a,
                   CASE
                       WHEN qa.q3_millis IS NOT NULL AND qb.q3_millis IS NOT NULL THEN qb.q3_millis
                       WHEN qa.q2_millis IS NOT NULL AND qb.q2_millis IS NOT NULL THEN qb.q2_millis
                       WHEN qa.q1_millis IS NOT NULL AND qb.q1_millis IS NOT NULL THEN qb.q1_millis
                       ELSE qb.time_millis END AS quali_ms_b
            FROM rr a
            JOIN rr b ON a.race_id = b.race_id AND a.constructor_id = b.constructor_id AND a.driver_id < b.driver_id
            LEFT JOIN q qa ON qa.race_id = a.race_id AND qa.driver_id = a.driver_id
            LEFT JOIN q qb ON qb.race_id = b.race_id AND qb.driver_id = b.driver_id
            JOIN race ra ON ra.id = a.race_id
            -- Same team, not just the same make of car: in the 1950s and 60s privateers often ran customer cars,
            -- so both drivers must have been entered by the same entrant that season. The Indianapolis 500
            -- (1950-1960 championship rounds) is left out: its entries have nothing to do with the F1 teams.
            WHERE ra.grand_prix_id <> 'indianapolis'
              AND EXISTS (
                SELECT 1 FROM season_entrant_driver ea JOIN season_entrant_driver eb
                  ON ea.year = eb.year AND ea.entrant_id = eb.entrant_id AND ea.constructor_id = eb.constructor_id
                WHERE ea.year = ra.year AND ea.driver_id = a.driver_id AND eb.driver_id = b.driver_id
                  AND ea.constructor_id = a.constructor_id)
        )
        SELECT p.*, r.year, r.round, r.date,
               CASE WHEN quali_ms_a IS NOT NULL AND quali_ms_b IS NOT NULL
                    THEN round((quali_ms_a - quali_ms_b) * 100.0 / least(quali_ms_a, quali_ms_b), 3) END
                   AS quali_gap_pct
        FROM pairs p JOIN race r ON r.id = p.race_id
        ORDER BY driver_a, driver_b, r.date
        """
    )


TIMING_SCHEMA = {
    "timing_session": """session_key VARCHAR PRIMARY KEY, race_id INTEGER, year INTEGER, round INTEGER, type VARCHAR,
        name VARCHAR, start_utc VARCHAR, total_laps INTEGER, rotation DOUBLE, corners VARCHAR, processed_at VARCHAR""",
    "timing_lap": """session_key VARCHAR, driver_id VARCHAR, lap INTEGER, time_ms DOUBLE, s1_ms DOUBLE, s2_ms DOUBLE,
        s3_ms DOUBLE, compound VARCHAR, tyre_life INTEGER, stint INTEGER, fresh_tyre BOOLEAN, pit_in BOOLEAN,
        pit_out BOOLEAN, track_status VARCHAR, position INTEGER, is_accurate BOOLEAN, deleted BOOLEAN,
        speed_trap DOUBLE, lap_start_s DOUBLE, personal_best BOOLEAN""",
    "timing_track_status": "session_key VARCHAR, t_s DOUBLE, status VARCHAR, message VARCHAR",
    "timing_race_control": """session_key VARCHAR, t_s DOUBLE, lap INTEGER, category VARCHAR, flag VARCHAR,
        scope VARCHAR, driver_id VARCHAR, message VARCHAR""",
    "timing_weather": """session_key VARCHAR, t_s DOUBLE, air_temp DOUBLE, track_temp DOUBLE, humidity DOUBLE,
        rain BOOLEAN, wind_speed DOUBLE""",
    "timing_telemetry": """session_key VARCHAR, driver_id VARCHAR, lap INTEGER, lap_time_ms DOUBLE, distance DOUBLE[],
        time DOUBLE[], speed DOUBLE[], throttle DOUBLE[], brake INTEGER[], gear INTEGER[], rpm DOUBLE[], drs INTEGER[],
        x DOUBLE[], y DOUBLE[]""",
}


def _load_timing(con: duckdb.DuckDBPyConnection, timing_dir: Path) -> int:
    """Load the per-session Parquet files written by `paddock timing` (2018+). Empty tables when there are none."""
    files = {
        "timing_session": "session",
        "timing_lap": "lap",
        "timing_track_status": "track_status",
        "timing_race_control": "race_control",
        "timing_weather": "weather",
        "timing_telemetry": "telemetry",
    }
    for table, schema in TIMING_SCHEMA.items():
        con.execute(f"CREATE TABLE {table} ({schema})")
        pattern = timing_dir / "*" / f"{files[table]}.parquet"
        if any(timing_dir.glob(f"*/{files[table]}.parquet")):
            con.execute(
                f"INSERT INTO {table} BY NAME SELECT * FROM read_parquet('{pattern.as_posix()}', union_by_name = true)"
            )
    return con.execute("SELECT count(*) FROM timing_session").fetchone()[0]


def _derive_car_ratings(con: duckdb.DuckDBPyConnection) -> None:
    """`car_rating`: every team's car, season by season, as a gap to the fastest car with the drivers taken out."""
    from .cars import MAX_GAP_PCT, fit, season_table

    # One qualifying lap per driver per race: the best of Q1, Q2, Q3 or the single session, as a gap to pole. The
    # car is the team's entry that season (constructor and entrant: privateers ran customer cars in the early years).
    rows = con.execute(
        f"""
        WITH q AS (
            SELECT q.race_id, r.year, q.driver_id, q.constructor_id,
                   least(coalesce(q.q1_millis, 1e12), coalesce(q.q2_millis, 1e12), coalesce(q.q3_millis, 1e12),
                         coalesce(q.time_millis, 1e12)) AS ms
            FROM qualifying_result q JOIN race r ON r.id = q.race_id
            WHERE r.grand_prix_id <> 'indianapolis'
        ), pole AS (SELECT race_id, min(ms) AS ms FROM q WHERE ms < 1e12 GROUP BY 1),
        entrant AS (
            SELECT year, driver_id, constructor_id, min(entrant_id) AS entrant_id
            FROM season_entrant_driver GROUP BY ALL
        )
        SELECT q.year, q.constructor_id, e.entrant_id, q.driver_id, q.race_id, (q.ms - p.ms) * 100.0 / p.ms AS gap
        FROM q JOIN pole p USING (race_id)
        JOIN entrant e ON e.year = q.year AND e.driver_id = q.driver_id AND e.constructor_id = q.constructor_id
        WHERE q.ms < 1e12 AND (q.ms - p.ms) * 100.0 / p.ms <= {MAX_GAP_PCT}
        """
    ).fetchall()
    car_effect, _ = fit([(f"{y}|{c}|{e}", d, g) for y, c, e, d, _, g in rows])

    # Races and the team's median best gap per car; one car per team per season (the entry with the most races).
    best: dict[str, dict[int, float]] = {}
    for y, c, e, _, race_id, g in rows:
        team = best.setdefault(f"{y}|{c}|{e}", {})
        team[race_id] = min(team.get(race_id, 99.0), g)
    races = {key: set(team) for key, team in best.items()}
    chosen: dict[tuple[int, str], str] = {}
    for key in car_effect:
        y, c, _ = key.split("|")
        current = chosen.get((int(y), c))
        if len(races[key]) >= 3 and (current is None or len(races[key]) > len(races[current])):
            chosen[(int(y), c)] = key
    seasons: dict[int, list[dict]] = {}
    for (y, c), key in chosen.items():
        team_best = sorted(best[key].values())
        seasons.setdefault(y, []).append(
            {
                "year": y,
                "constructor_id": c,
                "entrant_id": key.split("|")[2],
                "effect": car_effect[key],
                "raw_gap_pct": round(team_best[len(team_best) // 2], 3),
                "races": len(races[key]),
            }
        )
    con.execute(
        """CREATE TABLE car_rating (year INTEGER, constructor_id VARCHAR, entrant_id VARCHAR, gap_pct DOUBLE,
           raw_gap_pct DOUBLE, races INTEGER, rank INTEGER, cars INTEGER, margin_pct DOUBLE, percentile DOUBLE)"""
    )
    out = [
        (
            c["year"],
            c["constructor_id"],
            c["entrant_id"],
            c["gap_pct"],
            c["raw_gap_pct"],
            c["races"],
            c["rank"],
            c["cars"],
            c["margin_pct"],
            c["percentile"],
        )
        for y in sorted(seasons)
        for c in season_table(seasons[y])
    ]
    if out:
        con.executemany("INSERT INTO car_rating VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", out)


def _derive_conditions(con: duckdb.DuckDBPyConnection) -> None:
    """`race_conditions`: safety cars, red flags and rain per race, from the timing data (2018+)."""
    from .analysis import race_conditions

    con.execute(
        """CREATE TABLE race_conditions (race_id INTEGER, year INTEGER, round INTEGER, circuit_id VARCHAR,
           safety_cars INTEGER, virtual_safety_cars INTEGER, red_flags INTEGER, neutralised_laps INTEGER,
           race_laps INTEGER, rain BOOLEAN, wet_share DOUBLE, wet BOOLEAN)"""
    )
    sessions = con.execute(
        """SELECT s.session_key, s.race_id, r.year, r.round, r.circuit_id
           FROM timing_session s JOIN race r ON r.id = s.race_id WHERE s.type = 'R'"""
    ).fetchall()
    rows = []
    for key, race_id, year, round_, circuit_id in sessions:
        cur = con.execute("SELECT lap, track_status, position, compound FROM timing_lap WHERE session_key = ?", [key])
        names = [d[0] for d in cur.description]
        laps = [dict(zip(names, r, strict=True)) for r in cur.fetchall()]
        if not laps:
            continue
        rain = con.execute(
            "SELECT coalesce(bool_or(rain), false) FROM timing_weather WHERE session_key = ?", [key]
        ).fetchone()[0]
        c = race_conditions(laps, rain)
        rows.append((race_id, year, round_, circuit_id, *c.values()))
    if rows:
        con.executemany("INSERT INTO race_conditions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)


def _derive_ratings(con: duckdb.DuckDBPyConnection) -> None:
    """Cross-era driver ratings from teammate comparisons (see paddock/rating.py)."""
    from .rating import fit, standardise

    # Each season's gaps are divided by that season's median absolute teammate gap, so a big spread in the 1950s and a
    # tight one today count the same: the rating measures how a driver compares with the typical teammate gap of
    # their time, not raw tenths.
    quali = con.execute(
        """
        WITH g AS (SELECT year, driver_a, driver_b, quali_gap_pct AS y FROM teammate_race WHERE abs(quali_gap_pct) < 5),
        s AS (SELECT year, greatest(median(abs(y)), 0.05) AS scale FROM g GROUP BY year)
        SELECT driver_a, driver_b, y / scale FROM g JOIN s USING (year)
        """
    ).fetchall()
    race = con.execute(
        """
        WITH g AS (
            SELECT year, driver_a, driver_b, greatest(-10, least(10, race_pos_a - race_pos_b)) AS y
            FROM teammate_race WHERE race_pos_a IS NOT NULL AND race_pos_b IS NOT NULL
        ), s AS (SELECT year, greatest(median(abs(y)), 1) AS scale FROM g GROUP BY year)
        SELECT driver_a, driver_b, y / scale FROM g JOIN s USING (year)
        """
    ).fetchall()
    models = {"qualifying": standardise(fit(quali)), "race": standardise(fit(race))}
    combined = {}
    for d in models["qualifying"].keys() & models["race"].keys():
        q, r = models["qualifying"][d], models["race"][d]
        combined[d] = {
            "skill": (q["z"] + r["z"]) / 2,
            "low": (q["z_low"] + r["z_low"]) / 2,
            "high": (q["z_high"] + r["z_high"]) / 2,
            "comparisons": q["comparisons"] + r["comparisons"],
        }
    models["combined"] = standardise(combined)
    con.execute(
        """CREATE TABLE driver_rating (model VARCHAR, driver_id VARCHAR, skill DOUBLE, low DOUBLE, high DOUBLE,
           z DOUBLE, z_low DOUBLE, z_high DOUBLE, comparisons INTEGER)"""
    )
    con.executemany(
        "INSERT INTO driver_rating VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (m, d, r["skill"], r["low"], r["high"], r["z"], r["z_low"], r["z_high"], r["comparisons"])
            for m, rows in models.items()
            for d, r in rows.items()
        ],
    )


def build(raw: Path | None = None, db_path: Path | None = None) -> Path:
    raw = raw or config.RAW_DIR
    versioned = db_path is None
    if versioned:
        # A new file per build; data/paddock.current names the live one (see config.current_db_path).
        db_path = config.DATA_DIR / f"paddock-{datetime.now(UTC):%Y%m%d%H%M%S}.duckdb"
    tmp = db_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)

    con = duckdb.connect(str(tmp))
    try:
        tables = _copy_f1db(con, raw / "f1db.db")
        _load_laps(con, raw / "jolpica")
        _load_layouts(con, raw / "circuits")
        _derive(con)
        _derive_ratings(con)
        _derive_car_ratings(con)
        _load_timing(con, config.DATA_DIR / "timing")
        _derive_conditions(con)
        manifest = read_manifest(raw)
        con.execute("CREATE TABLE meta (key VARCHAR PRIMARY KEY, value VARCHAR)")
        con.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [
                ("schema_version", str(SCHEMA_VERSION)),
                ("built_at", datetime.now(UTC).isoformat(timespec="seconds")),
                ("sources", json.dumps(manifest.get("sources", []))),
                ("f1db_tables", json.dumps(tables)),
            ],
        )
        con.execute("CHECKPOINT")
    finally:
        con.close()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp.replace(db_path)
    if versioned:
        previous = config.current_db_path()
        config.DB_POINTER.write_text(db_path.name, encoding="utf-8")
        # Keep the new build and the one before it (a running API may still be reading it); remove older ones.
        for old in config.DATA_DIR.glob("paddock*.duckdb"):
            if old not in (db_path, previous):
                with contextlib.suppress(OSError):  # still open somewhere; the next build will remove it
                    old.unlink()
    return db_path
