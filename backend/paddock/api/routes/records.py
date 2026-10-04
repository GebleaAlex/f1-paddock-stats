from fastapi import APIRouter, HTTPException, Query

from ..db import db

router = APIRouter(prefix="/records", tags=["records"])

STARTED = "rr.position_text NOT IN ('DNQ', 'DNPQ', 'DNS', 'DNP', 'EX')"


def _total(column: str, entity: str = "driver") -> str:
    return f"SELECT id, name, {column} AS value FROM {entity} WHERE {column} > 0 ORDER BY value DESC, name"


# Each board returns rows of (id, name, value[, detail]); the `entity` decides where the link goes.
BOARDS: dict[str, dict] = {
    "wins": {"label": "Race wins", "entity": "driver", "sql": _total("total_race_wins")},
    "poles": {"label": "Pole positions", "entity": "driver", "sql": _total("total_pole_positions")},
    "podiums": {"label": "Podiums", "entity": "driver", "sql": _total("total_podiums")},
    "championships": {"label": "World championships", "entity": "driver", "sql": _total("total_championship_wins")},
    "starts": {"label": "Race starts", "entity": "driver", "sql": _total("total_race_starts")},
    "fastest-laps": {"label": "Fastest laps", "entity": "driver", "sql": _total("total_fastest_laps")},
    "grand-slams": {
        "label": "Grand slams",
        "hint": "Pole, win, fastest lap and leading every lap",
        "entity": "driver",
        "sql": _total("total_grand_slams"),
    },
    "win-rate": {
        "label": "Win rate",
        "hint": "At least 50 starts",
        "entity": "driver",
        "unit": "%",
        "sql": """
            SELECT id, name, round(total_race_wins * 100.0 / total_race_starts, 1) AS value,
                   total_race_wins || ' of ' || total_race_starts AS detail
            FROM driver WHERE total_race_starts >= 50 AND total_race_wins > 0 ORDER BY value DESC
        """,
    },
    "wins-in-a-season": {
        "label": "Wins in one season",
        "entity": "driver",
        "sql": """
            SELECT d.id, d.name, sd.total_race_wins AS value,
                   sd.year || ' · ' || sd.total_race_wins || ' of ' ||
                   (SELECT count(*) FROM race r WHERE r.year = sd.year) AS detail
            FROM season_driver sd JOIN driver d ON d.id = sd.driver_id
            WHERE sd.total_race_wins > 0 ORDER BY value DESC, sd.year
        """,
    },
    "consecutive-wins": {
        "label": "Consecutive wins",
        "hint": "Counted over the races the driver started",
        "entity": "driver",
        "sql": f"""
            WITH s AS (
                SELECT rr.driver_id, r.date, r.year, rr.position_number = 1 AS won,
                       row_number() OVER (PARTITION BY rr.driver_id ORDER BY r.date)
                     - row_number() OVER (PARTITION BY rr.driver_id, rr.position_number = 1 ORDER BY r.date) AS grp
                FROM race_result rr JOIN race r ON r.id = rr.race_id WHERE {STARTED}
            ), streaks AS (
                SELECT driver_id, count(*) AS value, min(year) AS y1, max(year) AS y2
                FROM s WHERE won GROUP BY driver_id, grp
            )
            SELECT d.id, d.name, value, CASE WHEN y1 = y2 THEN CAST(y1 AS VARCHAR) ELSE y1 || '–' || y2 END AS detail
            FROM streaks JOIN driver d ON d.id = streaks.driver_id
            WHERE value > 1 ORDER BY value DESC, y1
        """,
    },
    "youngest-winner": {
        "label": "Youngest race winner",
        "entity": "driver",
        "unit": "years",
        "ascending": True,
        "sql": """
            SELECT d.id, d.name, round(min(date_diff('day', d.date_of_birth, r.date)) / 365.25, 2) AS value,
                   CAST(arg_min(r.year, r.date) AS VARCHAR) AS detail
            FROM race_result rr JOIN race r ON r.id = rr.race_id JOIN driver d ON d.id = rr.driver_id
            WHERE rr.position_number = 1 GROUP BY d.id, d.name ORDER BY value
        """,
    },
    "oldest-winner": {
        "label": "Oldest race winner",
        "entity": "driver",
        "unit": "years",
        "sql": """
            SELECT d.id, d.name, round(max(date_diff('day', d.date_of_birth, r.date)) / 365.25, 2) AS value,
                   CAST(arg_max(r.year, r.date) AS VARCHAR) AS detail
            FROM race_result rr JOIN race r ON r.id = rr.race_id JOIN driver d ON d.id = rr.driver_id
            WHERE rr.position_number = 1 GROUP BY d.id, d.name ORDER BY value DESC
        """,
    },
    "starts-without-a-win": {
        "label": "Most starts without a win",
        "entity": "driver",
        "sql": """
            SELECT id, name, total_race_starts AS value,
                   CASE WHEN best_race_result IS NOT NULL THEN 'best finish P' || best_race_result END AS detail
            FROM driver WHERE total_race_wins = 0 ORDER BY value DESC
        """,
    },
    "constructor-wins": {
        "label": "Constructor wins",
        "entity": "constructor",
        "sql": _total("total_race_wins", "constructor"),
    },
    "constructor-championships": {
        "label": "Constructors' championships",
        "entity": "constructor",
        "sql": _total("total_championship_wins", "constructor"),
    },
    "one-twos": {
        "label": "One-two finishes",
        "entity": "constructor",
        "sql": _total("total_1_and_2_finishes", "constructor"),
    },
    "constructor-poles": {
        "label": "Constructor poles",
        "entity": "constructor",
        "sql": _total("total_pole_positions", "constructor"),
    },
}


@router.get("")
def boards():
    return [
        {"id": k, **{x: v[x] for x in ("label", "entity") if x in v}, "hint": v.get("hint")} for k, v in BOARDS.items()
    ]


@router.get("/{board}")
def board(board: str, limit: int = Query(25, ge=1, le=200)):
    if board not in BOARDS:
        raise HTTPException(404, "Unknown record")
    b = BOARDS[board]
    rows = db.rows(f"SELECT * FROM ({b['sql']}) LIMIT ?", [limit])
    # Shared ranks for equal values.
    rank = 0
    for i, row in enumerate(rows):
        if i == 0 or row["value"] != rows[i - 1]["value"]:
            rank = i + 1
        row["rank"] = rank
    return {
        "id": board,
        "label": b["label"],
        "hint": b.get("hint"),
        "entity": b["entity"],
        "unit": b.get("unit"),
        "rows": rows,
    }
