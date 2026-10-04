"""Unit tests for the analysis, telemetry and rating maths on small made-up inputs."""

import numpy as np

from paddock import analysis as an
from paddock import cars
from paddock import simulator as sim
from paddock import telemetry as tm
from paddock.eras import era_for
from paddock.rating import fit


def test_lap_status_priority():
    assert an.lap_status("1") is None
    assert an.lap_status("24") == "sc"
    assert an.lap_status("671") == "vsc"
    assert an.lap_status("45") == "red"


def test_periods_join_consecutive_laps():
    spans = an.periods({3: "sc", 4: "sc", 5: "sc", 9: "vsc", 12: "sc"})
    assert [(p["kind"], p["from_lap"], p["to_lap"]) for p in spans] == [("sc", 3, 5), ("vsc", 9, 9), ("sc", 12, 12)]


def test_fuel_correction_shrinks_over_the_race():
    first = 90000 - an.fuel_corrected(90000, 1, 50)
    last = 90000 - an.fuel_corrected(90000, 50, 50)
    assert round(first) == round(an.FUEL_START_KG * an.FUEL_S_PER_KG * 1000)
    assert last < first / 10


def test_clean_laps_drop_pits_safety_cars_and_slow_laps():
    laps = [{"lap": n, "time_ms": 90000} for n in range(1, 11)]
    laps[3]["pit_in"] = True
    laps[4]["pit_out"] = True
    laps[7]["time_ms"] = 120000
    clean = {r["lap"] for r in an.clean_laps(laps, {6: "sc"})}
    assert clean == {2, 3, 7, 9, 10}


def test_stints_merge_without_a_stop_and_measure_wear():
    laps = []
    for n in range(1, 21):
        laps.append(
            {
                "driver_id": "a",
                "lap": n,
                "time_ms": 90000 + n * 100,
                "compound": "MEDIUM",
                "tyre_life": n,
                "stint": 1 if n < 3 else 2,
                "pit_in": False,
                "pit_out": False,
            }
        )
    out = an.stints(laps, 20, {})
    assert len(out["a"]) == 1  # the stint counter changed, but there was no stop
    assert out["a"][0]["degradation_s_per_lap"] is not None


def test_undercut_verdict():
    # A (behind B by 1s) stops on lap 10, B on lap 12; after both stops A is ahead.
    positions = {
        "a": {9: 2, 10: 3, 11: 3, 12: 1, 13: 1},
        "b": {9: 1, 10: 1, 11: 1, 12: 3, 13: 2},
    }
    cumulative = {"a": {9: 1000, 13: 10000}, "b": {9: 0, 13: 11000}}
    stops = [{"driver_id": "a", "lap": 10}, {"driver_id": "b", "lap": 12}]
    battles = an.pit_battles(positions, cumulative, stops, {})
    assert battles[0]["verdict"] == "undercut worked" and battles[0]["winner"] == "a"


def test_penalty_text():
    assert an.penalty_text("FIA STEWARDS: 5 SECOND TIME PENALTY FOR CAR 5 (BOR) - UNSAFE RELEASE", "Bortoleto") == (
        "Bortoleto: 5 second time penalty for unsafe release"
    )
    assert an.penalty_text("FIA STEWARDS: NO FURTHER INVESTIGATION", None) is None


def _lap(speed: float, length: int = 1000) -> dict:
    d = np.arange(0, length, 10.0)
    return {
        "distance": d.tolist(),
        "time": (d / speed).tolist(),
        "speed": [speed * 3.6] * len(d),
        "throttle": [100] * len(d),
    }


def test_delta_and_dominance():
    fast, slow = _lap(50.0), _lap(40.0)
    delta = tm.delta(fast, slow)
    assert delta[0] == 0 and delta[-1] > 0
    dom = tm.dominance({"fast": fast, "slow": slow}, sectors=5)
    assert {s["driver_id"] for s in dom} == {"fast"}


def test_straights_detect_clipping():
    lap = _lap(80.0, 2000)
    speeds = [min(300, 200 + i) for i in range(100)] + [300 - i for i in range(100)]
    lap["speed"] = speeds
    st = tm.straights(lap)
    assert st["top_speed_kmh"] == 300 and st["clipping_m"] > 500


def test_rating_recovers_known_order():
    rng = np.random.default_rng(1)
    skill = {"a": 1.0, "b": 0.5, "c": 0.0, "d": -0.5}
    pairs = []
    for x, y in [("a", "b"), ("b", "c"), ("c", "d")]:
        for _ in range(60):
            pairs.append((x, y, skill[y] - skill[x] + rng.normal(0, 0.3)))
    r = fit(pairs)
    order = sorted(r, key=lambda d: -r[d]["skill"])
    assert order == ["a", "b", "c", "d"]
    assert all(r[d]["low"] < r[d]["skill"] < r[d]["high"] for d in r)


def test_eras():
    assert era_for(1988)["id"] == "1977"
    assert era_for(2026)["to"] is None


def test_race_conditions_count_restart_with_red_flag():
    laps = [{"lap": n, "position": 1, "track_status": "1", "compound": "MEDIUM"} for n in range(1, 31)]
    for n, code in {5: "4", 6: "4", 10: "5", 11: "5", 12: "4", 20: "6"}.items():
        laps[n - 1]["track_status"] = code
    laps += [{"lap": n, "position": 2, "track_status": "1", "compound": "INTERMEDIATE"} for n in range(1, 31)]
    c = an.race_conditions(laps, rain=True)
    assert (c["safety_cars"], c["virtual_safety_cars"], c["red_flags"]) == (1, 1, 1)
    assert c["neutralised_laps"] == 6 and c["race_laps"] == 30
    assert c["wet_share"] == 0.5 and c["wet"] and c["rain"]


def _synthetic_race(total=50):
    """Twenty drivers, soft then hard, with known compound offsets and wear."""
    rng = np.random.default_rng(3)
    truth = {"SOFT": (-0.5, 0.08), "HARD": (0.0, 0.03)}
    laps = []
    for i in range(20):
        stop = 15 + i
        for lap in range(1, total + 1):
            c = "SOFT" if lap <= stop else "HARD"
            age = lap if c == "SOFT" else lap - stop
            off, wear = truth[c]
            fuel = an.FUEL_START_KG * (1 - (lap - 1) / total) * an.FUEL_S_PER_KG
            t = 90 + 0.1 * i + off + wear * age + fuel + rng.normal(0, 0.05)
            laps.append(
                {
                    "driver_id": f"d{i}",
                    "lap": lap,
                    "time_ms": t * 1000 + (20000 if lap == stop else 0),
                    "compound": c,
                    "tyre_life": age,
                    "pit_in": lap == stop,
                    "pit_out": lap == stop + 1,
                    "position": i + 1,
                    "track_status": "1",
                }
            )
    return laps, truth


def test_simulator_recovers_tyre_model():
    laps, truth = _synthetic_race()
    model = sim.fit(laps, {}, 50)
    assert model["reference"] in ("SOFT", "HARD")
    soft, hard = model["compounds"]["SOFT"], model["compounds"]["HARD"]
    assert abs((soft["offset_s"] - hard["offset_s"]) - (truth["SOFT"][0] - truth["HARD"][0])) < 0.05
    assert abs(soft["wear_s_per_lap"] - 0.08) < 0.01 and abs(hard["wear_s_per_lap"] - 0.03) < 0.01


def test_simulator_costs_and_best_stop():
    model = {
        "compounds": {
            "SOFT": {"offset_s": -0.5, "wear_s_per_lap": 0.1},
            "HARD": {"offset_s": 0.0, "wear_s_per_lap": 0.02},
        }
    }
    actual = sim.make_plan([], [10], ["SOFT", "HARD"], 50)
    later = sim.make_plan(actual, [11], ["SOFT", "HARD"], 50)
    a = sim.lap_costs(model, actual, 50, {}, 20.0)
    b = sim.lap_costs(model, later, 50, {}, 20.0)
    assert a[10] > 20 and b[11] > 20  # the pit loss lands on the in-lap
    # Pitting under a safety car costs half the pit loss, and those laps cost nothing extra for tyres.
    cheap = sim.lap_costs(model, sim.make_plan(actual, [30], ["SOFT", "HARD"], 50), 50, {30: "sc"}, 20.0)
    assert cheap[30] == 10.0
    best = sim.best_stops(model, actual, 50, {}, 20.0)
    assert 1 <= best[0] < 49
    total = lambda s: sim.lap_costs(model, sim.make_plan(actual, s, ["SOFT", "HARD"], 50), 50, {}, 20.0).sum()  # noqa: E731
    assert all(total(best) <= total([x]) + 1e-9 for x in range(1, 50))
    errors, warnings = sim.check_plan(sim.make_plan(actual, [20], ["HARD", "HARD"], 50), model, 50, dry_race=True)
    assert not errors and warnings
    errors, _ = sim.check_plan(sim.make_plan(actual, [20], ["SOFT", "WET"], 50), model, 50, dry_race=True)
    assert errors


def test_car_model_separates_car_from_driver():
    # Driver "ace" is 0.5% faster than anyone; he moves from car A to car B, which is really 0.3% slower than A.
    rng = np.random.default_rng(5)
    car = {"A1": 0.0, "B1": 0.3, "A2": 0.0, "B2": 0.3}
    driver = {"ace": -0.5, "x": 0.0, "y": 0.0, "z": 0.0}
    lineup = {"A1": ["ace", "x"], "B1": ["y", "z"], "A2": ["x", "y"], "B2": ["ace", "z"]}
    rows = [(c, d, car[c] + driver[d] + rng.normal(0, 0.05)) for c, ds in lineup.items() for d in ds for _ in range(40)]
    effects, drivers = cars.fit(rows)
    assert abs((effects["B2"] - effects["A2"]) - 0.3) < 0.1
    assert drivers["ace"] < drivers["x"] - 0.3
    table = cars.season_table([{"key": "A2", "effect": effects["A2"]}, {"key": "B2", "effect": effects["B2"]}])
    assert table[0]["key"] == "A2" and table[0]["margin_pct"] == table[1]["gap_pct"] and table[1]["percentile"] == 0


def _circle_lap(lap_s: float, slow_from: float | None = None, dropout: tuple[int, int] | None = None) -> dict:
    """A 1 km circular lap at constant speed, optionally slower in the second half, with optional speed dropout."""
    d = np.arange(0, 1000, 10.0)
    v = np.full(d.size, 1000 / lap_s)
    if slow_from is not None:
        v[d >= slow_from] *= 0.9
    t = np.concatenate([[0.0], np.cumsum(10 / v[:-1])])
    angle = d / 1000 * 2 * np.pi
    lap = {
        "distance": d.tolist(),
        "time": t.tolist(),
        "speed": (v * 3.6).tolist(),
        "throttle": [100] * d.size,
        "brake": [0] * d.size,
        "x": (np.cos(angle) * 1591.5).tolist(),  # tenths of a metre: radius 159 m, about 1 km round
        "y": (np.sin(angle) * 1591.5).tolist(),
        "lap_time_ms": t[-1] * 1000,
    }
    if dropout:
        a, b = dropout
        lap["x"][a:b] = [lap["x"][a]] * (b - a)
        lap["y"][a:b] = [lap["y"][a]] * (b - a)
    return lap


def test_corner_deltas_add_up_to_the_lap_gap():
    fast, slow = _circle_lap(20.0), _circle_lap(20.0, slow_from=500)
    corners = [{"number": n, "letter": "", "distance": m} for n, m in ((1, 250), (2, 600), (3, 850))]
    cd = tm.corner_deltas(fast, slow, corners)
    assert cd["lap_gap_s"] > 0
    assert abs(sum(c["gain_s"] for c in cd["corners"]) + cd["straights_s"] - cd["lap_gap_s"]) < 1e-6
    by = {c["corner"]: c for c in cd["corners"]}
    assert abs(by["1"]["gain_s"]) < 0.01  # same speed in the first half
    assert by["2"]["gain_s"] > 0 and by["3"]["gain_s"] > 0  # the fast lap gains where the other slowed
    assert all(c["reliable"] for c in cd["corners"])


def test_dropouts_are_found_and_flag_corners():
    clean, broken = _circle_lap(20.0), _circle_lap(20.0, dropout=(55, 65))
    assert tm.dropouts(clean) == [] and tm.dropouts(broken)
    aligned = tm.align(clean, broken)
    gaps = tm.gap_regions(clean, broken, aligned)
    corners = [{"number": 1, "letter": "", "distance": 250}, {"number": 2, "letter": "", "distance": 600}]
    cd = tm.corner_deltas(clean, broken, corners, aligned, gaps=gaps)
    assert [c["reliable"] for c in cd["corners"]] == [True, False]
