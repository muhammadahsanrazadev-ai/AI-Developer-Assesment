import pytest

from app.utils.scoring import opportunity_score


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


def test_visibility_position_lowers_score_monotonically():
    scores = [opportunity_score(10_000, 50, True, p) for p in (1, 2, 3, 4, 9)]
    assert scores == sorted(scores)
