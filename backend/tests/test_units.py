from paddock.build import categorize_retirement
from paddock.scoring import BY_ID, points_for
from paddock.sources import svg_path_data


def test_retirement_categories():
    assert categorize_retirement("Collision damage") == "accident"
    assert categorize_retirement("Spun off") == "accident"
    assert categorize_retirement("Gearbox") == "technical"
    assert categorize_retirement("Power unit") == "technical"
    assert categorize_retirement("Ignored black flag") == "rules"
    assert categorize_retirement("Withdrew") == "other"


def test_points_modern_with_fastest_lap():
    s = BY_ID["2019"]
    assert points_for(s, 1, False) == 25
    assert points_for(s, 1, True) == 26
    assert points_for(s, 11, True) == 0  # fastest lap outside the top 10 scores nothing
    assert points_for(s, None, False) == 0


def test_points_1950s_fastest_lap_for_anyone():
    s = BY_ID["1950"]
    assert points_for(s, 5, False) == 2
    assert points_for(s, None, True) == 1


def test_svg_path_data():
    svg = '<svg><path style="fill: none" d="M1 2L3 4z"/></svg>'
    assert svg_path_data(svg) == "M1 2L3 4z"
    assert svg_path_data("<svg/>") is None
