import pytest

from app.utils.scoring import opportunity_score, priority_for_score


@pytest.mark.parametrize("volume,difficulty,visible,position", [
    (0, 100, False, None),
    (10_000_000, 0, False, None),
    (-5, 150, True, 1),
    (5000, 50, None, None),
])
def test_score_is_always_between_zero_and_one(volume, difficulty, visible, position):
    assert 0.0 <= opportunity_score(volume, difficulty, visible, position) <= 1.0


def test_score_orders_opportunities_meaningfully():
    gap_easy = opportunity_score(25_000, 30, False, None)
    gap_hard = opportunity_score(25_000, 85, False, None)
    visible_low = opportunity_score(25_000, 85, True, 4)
    visible_top = opportunity_score(25_000, 30, True, 1)
    small_gap = opportunity_score(50, 30, False, None)

    assert gap_easy > gap_hard > visible_low > visible_top
    assert gap_easy > small_gap


def test_volume_above_one_hundred_thousand_still_raises_the_score():
    assert opportunity_score(1_000_000, 50, False, None) > opportunity_score(100_000, 50, False, None)


def test_priority_follows_the_score_chip_bands():
    assert priority_for_score(0.7) == "high"
    assert priority_for_score(0.4) == "medium"
    assert priority_for_score(0.39) == "low"


def test_visibility_position_lowers_score_monotonically():
    scores = [opportunity_score(10_000, 50, True, p) for p in (1, 2, 3, 4, 9)]
    assert scores == sorted(scores)
