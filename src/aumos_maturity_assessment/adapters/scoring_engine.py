"""Maturity scoring computation engine for the Maturity Assessment service.

Implements the IScoringEngine interface. Computes per-dimension weighted
average scores and maps the overall composite score to a maturity level.
"""

from typing import Any

from aumos_common.observability import get_logger

logger = get_logger(__name__)

# Maturity level breakpoints (overall score 0-100)
MATURITY_LEVEL_THRESHOLDS: dict[int, float] = {
    1: 0.0,   # Initial: 0-19
    2: 20.0,  # Developing: 20-39
    3: 40.0,  # Defined: 40-59
    4: 60.0,  # Managed: 60-79
    5: 80.0,  # Optimizing: 80-100
}


class ScoringEngine:
    """Rule-based maturity scoring engine.

    Computes weighted average scores per dimension, then combines them
    using configurable dimension weights to produce an overall composite score.
    Maps the composite score to a 1-5 maturity level using standard thresholds.
    """

    async def compute_scores(
        self,
        responses: list[dict[str, Any]],
        dimension_weights: dict[str, float],
    ) -> dict[str, Any]:
        """Compute all dimension scores and overall maturity level.

        Groups responses by dimension, computes the weighted average score
        for each dimension, then combines dimension scores using the supplied
        dimension weights to produce the composite score.

        Args:
            responses: List of response dicts with numeric_score, dimension, weight.
            dimension_weights: Per-dimension weighting factors (must sum to 1.0).

        Returns:
            Dict with overall_score, maturity_level, and per-dimension scores.
        """
        # Group by dimension and compute weighted averages
        dimension_scores: dict[str, float] = {}
        dimensions = ["data", "process", "people", "technology", "governance"]

        for dimension in dimensions:
            dim_responses = [r for r in responses if r.get("dimension") == dimension]
            if not dim_responses:
                dimension_scores[dimension] = 0.0
                continue

            # Weighted average: sum(score * weight) / sum(weight)
            total_weight = sum(r.get("weight", 1.0) for r in dim_responses)
            if total_weight == 0:
                dimension_scores[dimension] = 0.0
                continue

            weighted_sum = sum(
                (r.get("numeric_score") or 0.0) * r.get("weight", 1.0)
                for r in dim_responses
            )
            dimension_scores[dimension] = round(weighted_sum / total_weight, 2)

        # Composite score = sum(dimension_score * dimension_weight)
        overall_score = sum(
            dimension_scores.get(dim, 0.0) * dimension_weights.get(dim, 0.0)
            for dim in dimensions
        )
        overall_score = round(overall_score, 2)

        maturity_level = _score_to_maturity_level(overall_score)

        logger.debug(
            "Maturity scores computed",
            overall_score=overall_score,
            maturity_level=maturity_level,
            dimension_scores=dimension_scores,
        )

        return {
            "overall_score": overall_score,
            "maturity_level": maturity_level,
            "data_score": dimension_scores.get("data", 0.0),
            "process_score": dimension_scores.get("process", 0.0),
            "people_score": dimension_scores.get("people", 0.0),
            "technology_score": dimension_scores.get("technology", 0.0),
            "governance_score": dimension_scores.get("governance", 0.0),
        }


def _score_to_maturity_level(score: float) -> int:
    """Map a 0-100 score to a 1-5 maturity level using standard thresholds.

    Level  Score range  Label
    -----  -----------  -----------
    1      0-19         Initial
    2      20-39        Developing
    3      40-59        Defined
    4      60-79        Managed
    5      80-100       Optimizing

    Args:
        score: Composite maturity score 0-100.

    Returns:
        Maturity level 1-5.
    """
    if score >= 80.0:
        return 5
    if score >= 60.0:
        return 4
    if score >= 40.0:
        return 3
    if score >= 20.0:
        return 2
    return 1
