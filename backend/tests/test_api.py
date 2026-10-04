"""API tests against the real database built by `paddock update`.

The facts checked here are historical and cannot change (1988 results, 2013-2016 Mercedes pairing), so the tests stay
valid as new seasons are added.
"""

import pytest
from fastapi.testclient import TestClient

from paddock import config
from paddock.api.main import app

pytestmark = pytest.mark.skipif(
    not config.current_db_path().exists(), reason="run `paddock update` to build the database"
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def get(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    return r.json()


def test_meta_counts(client):
    m = get(client, "/api/meta")
    assert m["counts"]["seasons"] >= 77
    assert m["counts"]["laps"] > 500_000
    assert {s["name"] for s in m["sources"]} == {"f1db", "Jolpica-F1"}


def test_search_ignores_accents_and_case(client):
    names = [r["name"] for r in get(client, "/api/search?q=perez")]
    assert "Sergio Pérez" in names
    assert get(client, "/api/search?q=1988")[0]["type"] == "season"


def test_season_1988(client):
    s = get(client, "/api/seasons/1988")
    assert len(s["races"]) == 16
    assert s["driver_standings"][0]["driver_id"] == "ayrton-senna"
    assert s["constructor_standings"][0]["constructor_id"] == "mclaren"
    assert sum(r["winner_constructor_id"] == "mclaren" for r in s["races"]) == 15


def test_progression_is_cumulative(client):
    p = get(client, "/api/seasons/2021/progression")
    for d in p["drivers"]:
        assert d["points"] == sorted(d["points"])
    leaders = {p["drivers"][0]["id"], p["drivers"][1]["id"]}
    assert leaders == {"max-verstappen", "lewis-hamilton"}


def test_rescore_1988_modern_points_gives_prost_the_title(client):
    r = get(client, "/api/seasons/1988/rescore?system=2010")
    assert r["standings"][0]["driver_id"] == "alain-prost"
    assert r["standings"][0]["official_position"] == 2


def test_rescore_unknown_system(client):
    assert client.get("/api/seasons/1988/rescore?system=nope").status_code == 400


def test_race_with_laps(client):
    r = get(client, "/api/races/2021/22")
    assert r["results"][0]["driver_id"] == "max-verstappen"
    assert r["has_laps"]
    laps = get(client, "/api/races/2021/22/laps")
    ver = laps["laps"]["max-verstappen"]
    assert len(ver) == 58 and ver[-1][1] == 1  # 58 laps, leading on the last one


def test_unknown_race_is_404(client):
    assert client.get("/api/races/1949/1").status_code == 404


def test_driver_page(client):
    d = get(client, "/api/drivers/lewis-hamilton")
    assert d["driver"]["wins"] >= 105
    assert d["milestones"]["first_race"]["year"] == 2007
    mates = {t["driver_id"]: t for t in d["teammates"]}
    assert "fernando-alonso" in mates and "nico-rosberg" in mates


def test_teammate_head_to_head_is_symmetric(client):
    a = get(client, "/api/teammates/lewis-hamilton/nico-rosberg")["summary"]
    b = get(client, "/api/teammates/nico-rosberg/lewis-hamilton")["summary"]
    assert a["races"] == b["races"]
    assert (a["quali_won"], a["race_won"]) == (b["quali_lost"], b["race_lost"])
    assert a["median_gap_pct"] == -b["median_gap_pct"]


def test_never_teammates(client):
    assert client.get("/api/teammates/ayrton-senna/max-verstappen").status_code == 404


def test_compare(client):
    c = get(client, "/api/compare?drivers=ayrton-senna,alain-prost")
    assert [d["driver"]["id"] for d in c["drivers"]] == ["ayrton-senna", "alain-prost"]
    assert c["teammate_pairs"][0]["races"] >= 30  # McLaren 1988-1989
    senna = c["drivers"][0]["starts"]
    assert senna[-1]["wins"] == 41


def test_constructor_lineage(client):
    c = get(client, "/api/constructors/alpine")
    assert [x["id"] for x in c["lineage"] if x["chain_id"] == "alpine"][0] == "toleman"


def test_circuit(client):
    c = get(client, "/api/circuits/monaco")
    assert c["stats"]["races"] >= 70
    assert c["most_wins"]["drivers"][0]["id"] == "ayrton-senna"
    assert any(layout["path"] for layout in c["layouts"])


def test_records(client):
    boards = {b["id"] for b in get(client, "/api/records")}
    assert {"wins", "consecutive-wins", "youngest-winner"} <= boards
    youngest = get(client, "/api/records/youngest-winner")["rows"][0]
    assert youngest["id"] == "max-verstappen" and youngest["value"] < 19


# ---------- Phases 3 to 5 ----------


def test_race_story_and_strategy_before_2018(client):
    s = get(client, "/api/races/2021/22/story")
    kinds = {e["kind"] for e in s["events"]}
    assert {"lead", "pit", "finish"} <= kinds
    assert any(e["kind"] == "lead" and "Verstappen" in e["text"] for e in s["events"])
    st = get(client, "/api/races/2021/22/strategy")
    assert st["has_stops"] and st["pit_loss_s"] and 15 < st["pit_loss_s"] < 40
    assert all(d["stints"] for d in st["drivers"] if d["laps"])


def test_pace_needs_drivers(client):
    assert client.get("/api/races/2021/22/pace").status_code == 400
    p = get(client, "/api/races/2021/22/pace?drivers=max-verstappen")
    laps = p["laps"]["max-verstappen"]
    assert len(laps) == 58 and any(r["clean"] for r in laps)


def test_circuit_pit_loss(client):
    p = get(client, "/api/circuits/monza/pit-loss")
    assert p["typical_s"] and 15 < p["typical_s"] < 40


def test_competitive_order(client):
    o = get(client, "/api/seasons/1988/competitive-order")
    assert o["teams"][0]["name"] == "McLaren"


def test_explore(client):
    e = get(client, "/api/explore?circuit=monaco&grid_min=4&sort=wins")
    assert e["rows"][0]["wins"] >= 1 and e["total"]["races"] > 50
    assert client.get("/api/explore?sort=nonsense").status_code == 400
    t = get(client, "/api/explore?teammate=lewis-hamilton&sort=races")
    assert {r["key"] for r in t["rows"][:3]} >= {"valtteri-bottas", "nico-rosberg"}


def test_ratings(client):
    r = get(client, "/api/ratings?model=combined&limit=20")
    names = {x["driver_id"] for x in r["rows"]}
    assert {"max-verstappen", "lewis-hamilton", "michael-schumacher", "ayrton-senna"} & names
    assert all(x["low"] <= x["skill"] <= x["high"] for x in r["rows"])
    assert client.get("/api/ratings?model=nope").status_code == 400


def test_title_odds_2021_finale(client):
    o = get(client, "/api/seasons/2021/title-odds?after=21")
    top = {d["driver_id"]: d for d in o["current"]["drivers"]}
    assert top["max-verstappen"]["probability"] + top["lewis-hamilton"]["probability"] > 0.99
    assert not top["valtteri-bottas"]["can_still_win"]


def test_eras_and_cars(client):
    eras = get(client, "/api/eras")
    assert eras[0]["from"] == 1950 and any(e["id"] == "2014" and e["top_team"] == "Mercedes" for e in eras)
    car = get(client, "/api/cars/mclaren-mp4-4")
    assert car["years"] == [1988] and car["results"]["wins"] == 15
    assert client.get("/api/cars/not-a-car").status_code == 404


def test_teammates_are_same_entrant(client):
    # Senna and Prost: 1988-1989 at McLaren, 32 races.
    h = get(client, "/api/teammates/ayrton-senna/alain-prost")
    assert h["summary"]["races"] == 32 and h["summary"]["quali_won"] == 28


def test_telemetry_when_available(client):
    key = client.get("/api/races/2026/1/sessions")
    if key.status_code != 200 or not key.json():
        pytest.skip("no 2026 timing data loaded; run `paddock timing --years 2026`")
    q = next(s for s in key.json() if s["type"] == "Q")
    a, b = q["laps"][0]["driver_id"], q["laps"][1]["driver_id"]
    t = get(client, f"/api/races/2026/1/telemetry?session=Q&drivers={a},{b}")
    assert len(t["delta"]) == len(t["laps"][a]["distance"]) and len(t["dominance"]) == 25
    qa = get(client, "/api/races/2026/1/qualifying-analysis")
    assert qa["rows"][0]["gap_ms"] == 0 and qa["rows"][0]["ideal_ms"] <= qa["rows"][0]["best_ms"] + 1


def test_social_preview_image(client):
    r = client.get("/api/og.png", params={"title": "Kimi Räikkönen", "stats": "Wins:21|Titles:1", "color": "dc0000"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert client.get("/api/og.png", params={"title": "x" * 200}).status_code == 422


def test_car_ratings(client):
    r = get(client, "/api/car-ratings")
    top = [(c["year"], c["constructor_id"]) for c in r["dominant"][:15]]
    assert (1993, "williams") in top and (1992, "williams") in top
    assert r["constructors"][0]["seasons"] >= 5
    season = get(client, "/api/car-ratings/1988")
    first = season["cars"][0]
    assert first["constructor_id"] == "mclaren" and first["gap_pct"] == 0
    assert {"id": "mclaren-mp4-4", "name": "MP4/4"} in first["chassis"]
    team = get(client, "/api/car-ratings/team/mercedes")
    assert all(s["rank"] == 1 for s in team["seasons"] if 2014 <= s["year"] <= 2016)
    assert client.get("/api/car-ratings/1949").status_code == 404


def test_conditions_and_simulator_when_timing_available(client):
    if not get(client, "/api/conditions?min_races=1")["circuits"]:
        pytest.skip("no timing data loaded; run `paddock timing`")
    races = get(client, "/api/circuits/monaco/conditions")["races"]
    assert all(r["safety_cars"] >= 0 and r["race_laps"] > 0 for r in races)
    race = next((x for x in races), None)
    if race is None:
        pytest.skip("no Monaco race with timing")
    s = get(client, f"/api/races/{race['year']}/{race['round']}/simulate")
    assert s["time_change_s"] == 0 and s["position"]["real"] == s["position"]["simulated"]
    assert len(s["laps"]) == s["last_lap"] and s["plan"] == s["actual"]
    stops = [st["to_lap"] for st in s["actual"][:-1]]
    if stops:
        moved = ",".join(str(x - 1) for x in stops)
        comps = ",".join(st["compound"] for st in s["actual"])
        r = get(
            client,
            f"/api/races/{race['year']}/{race['round']}/simulate?driver={s['driver']}&stops={moved}&compounds={comps}",
        )
        assert r["time_change_s"] != 0 or r["periods"]
    bad = client.get(f"/api/races/{race['year']}/{race['round']}/simulate?stops=5&compounds=SOFT")
    assert bad.status_code == 400


def test_timing_race_times_match_lap_data(client):
    from paddock.api.routes import analysis as a

    race = client.get("/api/races/2026/5").json()["race"]
    key = a._timing_key(race["id"])
    if not key:
        pytest.skip("no 2026 timing data loaded")
    jolpica = a._lap_tables(race["id"])[1]
    timing, _, stops = a._timing_race_times(key)
    shared = [d for d in jolpica if d in timing]
    assert shared and stops
    for d in shared:
        last = max(set(jolpica[d]) & set(timing[d]))
        assert abs(jolpica[d][last] / 1000 - timing[d][last]) < 2
