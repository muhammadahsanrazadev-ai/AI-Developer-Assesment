import math

VOLUME_CAP = 100_000
VOLUME_WEIGHT = 0.6
EASE_WEIGHT = 0.4

GAP_NOT_VISIBLE = 1.0
GAP_UNKNOWN = 0.5
GAP_BY_POSITION = {1: 0.1, 2: 0.3, 3: 0.5}
GAP_LOW_POSITION = 0.7


def volume_factor(estimated_search_volume: int) -> float:
    volume = max(0, estimated_search_volume)
    return min(1.0, math.log10(volume + 1) / math.log10(VOLUME_CAP + 1))


def ease_factor(competitive_difficulty: int) -> float:
    difficulty = min(100, max(0, competitive_difficulty))
    return 1.0 - difficulty / 100.0


def gap_factor(domain_visible: bool | None, visibility_position: int | None) -> float:
    if domain_visible is None:
        return GAP_UNKNOWN
    if not domain_visible:
        return GAP_NOT_VISIBLE
    if visibility_position is None:
        return GAP_UNKNOWN
    return GAP_BY_POSITION.get(visibility_position, GAP_LOW_POSITION)


def opportunity_score(
    estimated_search_volume: int,
    competitive_difficulty: int,
    domain_visible: bool | None,
    visibility_position: int | None,
) -> float:
    """gap x (0.6 x volume + 0.4 x ease), each factor in 0..1, so the result is in 0..1."""
    demand = (
        VOLUME_WEIGHT * volume_factor(estimated_search_volume)
        + EASE_WEIGHT * ease_factor(competitive_difficulty)
    )
    score = gap_factor(domain_visible, visibility_position) * demand
    return round(min(1.0, max(0.0, score)), 4)
