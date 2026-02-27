"""BenchmarkComparator adapter for industry peer comparison in maturity assessments.

Compares tenant assessment scores against industry benchmark databases,
computes percentile rankings per dimension, identifies gaps vs best-in-class,
and produces comparison visualisation data for reporting.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from aumos_common.observability import get_logger

logger = get_logger(__name__)

# Five maturity dimensions with display labels
DIMENSIONS: list[str] = ["data", "process", "people", "technology", "governance"]

DIMENSION_LABELS: dict[str, str] = {
    "data": "Data & AI Readiness",
    "process": "Process & MLOps",
    "people": "People & Culture",
    "technology": "Technology & Infrastructure",
    "governance": "Governance & Risk",
}

# Maturity level thresholds (0-100 scale matching mat_assessments)
MATURITY_LEVELS: list[tuple[int, str]] = [
    (80, "Optimizing"),
    (60, "Managed"),
    (40, "Defined"),
    (20, "Developing"),
    (0, "Initial"),
]

# Organisation size tiers for peer group segmentation
SIZE_TIERS: dict[str, range] = {
    "startup": range(1, 200),
    "smb": range(200, 1000),
    "mid_market": range(1000, 5000),
    "enterprise": range(5000, 50000),
    "large_enterprise": range(50000, 1000000),
}


class BenchmarkComparator:
    """Industry peer benchmark comparison engine for AI maturity assessments.

    Computes percentile rankings for an assessed organisation across all
    five maturity dimensions (data, process, people, technology, governance)
    relative to an industry benchmark dataset. Selects appropriate peer
    groups based on industry vertical and organisation size. Identifies
    gaps versus best-in-class and generates improvement priority scores
    for roadmap sequencing.
    """

    def __init__(
        self,
        benchmark_data: list[dict[str, Any]] | None = None,
        best_in_class_percentile: float = 90.0,
        peer_group_min_size: int = 10,
    ) -> None:
        """Initialise the BenchmarkComparator.

        Args:
            benchmark_data: Optional preloaded benchmark records. Each record
                contains industry, organization_size, and per-dimension percentile
                distributions. If None, the comparator relies on data passed
                at comparison time.
            best_in_class_percentile: Percentile defining "best in class" for
                gap analysis (e.g., 90th percentile).
            peer_group_min_size: Minimum sample size to use a peer group. If the
                group is smaller, the comparator broadens to the industry level.
        """
        self._benchmark_data = benchmark_data or []
        self._best_in_class_percentile = best_in_class_percentile
        self._peer_group_min_size = peer_group_min_size

    async def select_peer_group(
        self,
        tenant_id: uuid.UUID,
        industry: str,
        organization_size: str,
        available_benchmarks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Select the most appropriate peer group for comparison.

        Applies a hierarchy of matching: exact industry + size, then
        industry-only, then global average as fallback.

        Args:
            tenant_id: Requesting tenant UUID.
            industry: Industry vertical (e.g., "financial_services").
            organization_size: Size tier (e.g., "enterprise").
            available_benchmarks: List of benchmark records from the repository.

        Returns:
            Dict with selected_benchmark, peer_group_description, match_quality,
            and sample_size fields.
        """
        logger.info(
            "Selecting peer group",
            tenant_id=str(tenant_id),
            industry=industry,
            organization_size=organization_size,
        )

        # Exact match: industry + size
        exact_matches = [
            b for b in available_benchmarks
            if b.get("industry") == industry and b.get("organization_size") == organization_size
        ]
        if exact_matches and exact_matches[0].get("sample_size", 0) >= self._peer_group_min_size:
            selected = max(exact_matches, key=lambda b: b.get("sample_size", 0))
            return {
                "selected_benchmark": selected,
                "peer_group_description": f"{industry} / {organization_size}",
                "match_quality": "exact",
                "sample_size": selected.get("sample_size", 0),
                "benchmark_period": selected.get("benchmark_period"),
            }

        # Industry-only match
        industry_matches = [b for b in available_benchmarks if b.get("industry") == industry]
        if industry_matches:
            best = max(industry_matches, key=lambda b: b.get("sample_size", 0))
            return {
                "selected_benchmark": best,
                "peer_group_description": f"{industry} (all sizes)",
                "match_quality": "industry_only",
                "sample_size": best.get("sample_size", 0),
                "benchmark_period": best.get("benchmark_period"),
            }

        # Global fallback
        if available_benchmarks:
            best_global = max(available_benchmarks, key=lambda b: b.get("sample_size", 0))
            return {
                "selected_benchmark": best_global,
                "peer_group_description": "Global average (all industries)",
                "match_quality": "global_fallback",
                "sample_size": best_global.get("sample_size", 0),
                "benchmark_period": best_global.get("benchmark_period"),
            }

        logger.warning(
            "No benchmarks available for peer group selection",
            tenant_id=str(tenant_id),
            industry=industry,
        )

        return {
            "selected_benchmark": None,
            "peer_group_description": "No benchmark data available",
            "match_quality": "none",
            "sample_size": 0,
        }

    async def compute_percentile_rankings(
        self,
        tenant_id: uuid.UUID,
        assessment_scores: dict[str, float],
        benchmark: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute percentile rankings for each dimension against benchmark data.

        Args:
            tenant_id: Requesting tenant UUID.
            assessment_scores: Dict mapping dimension name to score (0–100 scale).
            benchmark: Benchmark record with p25/p50/p75/p90 per dimension.

        Returns:
            Dict with per_dimension_rankings, overall_percentile,
            overall_maturity_level, and strengths/weaknesses classification.
        """
        logger.info(
            "Computing percentile rankings",
            tenant_id=str(tenant_id),
        )

        if benchmark is None:
            return {
                "tenant_id": str(tenant_id),
                "error": "No benchmark data available for percentile ranking.",
                "per_dimension_rankings": {},
            }

        dimension_rankings: dict[str, dict[str, Any]] = {}
        overall_scores: list[float] = []

        for dimension in DIMENSIONS:
            score = assessment_scores.get(dimension, 0.0)
            percentile = self._interpolate_percentile(score, benchmark, dimension)

            dimension_rankings[dimension] = {
                "dimension_label": DIMENSION_LABELS.get(dimension, dimension),
                "score": round(score, 2),
                "percentile": round(percentile, 1),
                "peer_p50": benchmark.get(f"{dimension}_p50", benchmark.get("overall_p50", 50.0)),
                "vs_median_delta": round(score - benchmark.get(f"{dimension}_p50", 50.0), 2),
                "maturity_level": self._score_to_maturity_level(score),
                "classification": (
                    "strength" if percentile >= 75.0
                    else "average" if percentile >= 40.0
                    else "gap"
                ),
            }
            overall_scores.append(score)

        overall_score = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
        overall_percentile = self._interpolate_percentile(overall_score, benchmark, "overall")

        strengths = [d for d, r in dimension_rankings.items() if r["classification"] == "strength"]
        weaknesses = [d for d, r in dimension_rankings.items() if r["classification"] == "gap"]

        result: dict[str, Any] = {
            "tenant_id": str(tenant_id),
            "overall_score": round(overall_score, 2),
            "overall_percentile": round(overall_percentile, 1),
            "overall_maturity_level": self._score_to_maturity_level(overall_score),
            "per_dimension_rankings": dimension_rankings,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "benchmark_period": benchmark.get("benchmark_period"),
            "peer_sample_size": benchmark.get("sample_size", 0),
            "computed_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        logger.info(
            "Percentile rankings computed",
            tenant_id=str(tenant_id),
            overall_percentile=result["overall_percentile"],
            strength_count=len(strengths),
            weakness_count=len(weaknesses),
        )

        return result

    async def analyze_gap_vs_best_in_class(
        self,
        tenant_id: uuid.UUID,
        assessment_scores: dict[str, float],
        benchmark: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Identify and quantify gaps between assessed scores and best-in-class.

        Best-in-class is defined as the configured percentile threshold
        (default: 90th percentile) in the benchmark dataset.

        Args:
            tenant_id: Requesting tenant UUID.
            assessment_scores: Dict mapping dimension name to score (0–100 scale).
            benchmark: Benchmark record with percentile values per dimension.

        Returns:
            List of gap analysis dicts per dimension, sorted by gap_size descending.
            Each dict has dimension, score, best_in_class_score, gap_size, gap_percent,
            and severity fields.
        """
        logger.info(
            "Analyzing gaps vs best-in-class",
            tenant_id=str(tenant_id),
        )

        gaps: list[dict[str, Any]] = []

        for dimension in DIMENSIONS:
            score = assessment_scores.get(dimension, 0.0)
            bic_score = benchmark.get(f"{dimension}_p90", benchmark.get("overall_p90", 80.0))
            gap_size = max(0.0, bic_score - score)
            gap_percent = round(gap_size / bic_score * 100.0, 1) if bic_score > 0 else 0.0

            severity = (
                "critical" if gap_size >= 30.0
                else "high" if gap_size >= 20.0
                else "medium" if gap_size >= 10.0
                else "low"
            )

            gaps.append({
                "dimension": dimension,
                "dimension_label": DIMENSION_LABELS.get(dimension, dimension),
                "current_score": round(score, 2),
                "best_in_class_score": round(bic_score, 2),
                "gap_size": round(gap_size, 2),
                "gap_percent": gap_percent,
                "severity": severity,
                "current_maturity_level": self._score_to_maturity_level(score),
                "target_maturity_level": self._score_to_maturity_level(bic_score),
            })

        gaps.sort(key=lambda g: g["gap_size"], reverse=True)

        logger.info(
            "Gap analysis completed",
            tenant_id=str(tenant_id),
            critical_gaps=len([g for g in gaps if g["severity"] == "critical"]),
            high_gaps=len([g for g in gaps if g["severity"] == "high"]),
        )

        return gaps

    async def score_improvement_priorities(
        self,
        tenant_id: uuid.UUID,
        gap_analysis: list[dict[str, Any]],
        assessment_scores: dict[str, float],
    ) -> list[dict[str, Any]]:
        """Score improvement priorities based on gap size, effort, and impact.

        Combines gap severity with a difficulty-to-improve estimate to produce
        an effort-adjusted impact score for roadmap sequencing.

        Args:
            tenant_id: Requesting tenant UUID.
            gap_analysis: Output from analyze_gap_vs_best_in_class.
            assessment_scores: Current assessment scores per dimension.

        Returns:
            List of priority dicts with priority_rank, dimension, impact_score,
            effort_score, priority_score, and quick_win flag, sorted by priority_score.
        """
        logger.info(
            "Scoring improvement priorities",
            tenant_id=str(tenant_id),
        )

        # Relative difficulty of improving each dimension (heuristic)
        difficulty_weights: dict[str, float] = {
            "data": 0.6,        # Moderate — data platforms and tooling
            "process": 0.5,     # Moderate — process change is enabler
            "people": 0.8,      # Hard — cultural and capability change is slow
            "technology": 0.5,  # Moderate — tooling and infrastructure
            "governance": 0.7,  # Hard — policy and compliance take time
        }

        priorities: list[dict[str, Any]] = []
        for gap in gap_analysis:
            dimension = gap["dimension"]
            gap_size = gap["gap_size"]
            severity = gap["severity"]
            difficulty = difficulty_weights.get(dimension, 0.6)

            current_score = assessment_scores.get(dimension, 0.0)

            # Impact score: higher gap = higher impact opportunity
            impact_score = min(1.0, gap_size / 40.0)

            # Effort score: difficulty + current low score = harder starting point
            effort_score = difficulty * (1.0 - min(1.0, current_score / 100.0))

            # Priority = impact / effort (higher = better return on investment)
            priority_score = round(impact_score / max(effort_score, 0.1), 4)

            is_quick_win = gap_size <= 15.0 and effort_score <= 0.40 and severity in ("medium", "low")

            priorities.append({
                "dimension": dimension,
                "dimension_label": DIMENSION_LABELS.get(dimension, dimension),
                "gap_size": gap_size,
                "severity": severity,
                "impact_score": round(impact_score, 4),
                "effort_score": round(effort_score, 4),
                "priority_score": priority_score,
                "is_quick_win": is_quick_win,
                "rationale": (
                    f"{DIMENSION_LABELS.get(dimension, dimension)}: "
                    f"gap of {gap_size:.0f} points with {'low' if effort_score < 0.5 else 'high'} effort. "
                    f"{'Quick win opportunity.' if is_quick_win else 'Strategic initiative required.'}"
                ),
            })

        priorities.sort(key=lambda p: p["priority_score"], reverse=True)
        for rank, priority in enumerate(priorities, start=1):
            priority["priority_rank"] = rank

        logger.info(
            "Improvement priorities scored",
            tenant_id=str(tenant_id),
            quick_win_count=len([p for p in priorities if p["is_quick_win"]]),
        )

        return priorities

    async def generate_comparison_visualization_data(
        self,
        tenant_id: uuid.UUID,
        assessment_scores: dict[str, float],
        percentile_rankings: dict[str, Any],
        gap_analysis: list[dict[str, Any]],
        peer_group: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate structured data for radar/spider chart and bar chart visualisation.

        Args:
            tenant_id: Requesting tenant UUID.
            assessment_scores: Current assessment scores per dimension.
            percentile_rankings: Output from compute_percentile_rankings.
            gap_analysis: Output from analyze_gap_vs_best_in_class.
            peer_group: Output from select_peer_group.

        Returns:
            Dict with radar_chart_data, percentile_bar_data, gap_waterfall_data,
            and summary_cards fields, all structured for frontend consumption.
        """
        logger.info(
            "Generating comparison visualization data",
            tenant_id=str(tenant_id),
        )

        benchmark = peer_group.get("selected_benchmark") or {}

        # Radar chart: your scores vs median vs best-in-class
        radar_series: list[dict[str, Any]] = [
            {
                "dimension": dim,
                "label": DIMENSION_LABELS.get(dim, dim),
                "your_score": round(assessment_scores.get(dim, 0.0), 2),
                "peer_median": benchmark.get(f"{dim}_p50", 50.0),
                "best_in_class": benchmark.get(f"{dim}_p90", 80.0),
            }
            for dim in DIMENSIONS
        ]

        # Percentile bar chart: your percentile per dimension
        percentile_dim = percentile_rankings.get("per_dimension_rankings", {})
        percentile_bars: list[dict[str, Any]] = [
            {
                "dimension": dim,
                "label": DIMENSION_LABELS.get(dim, dim),
                "percentile": percentile_dim.get(dim, {}).get("percentile", 0.0),
                "classification": percentile_dim.get(dim, {}).get("classification", "average"),
            }
            for dim in DIMENSIONS
        ]

        # Gap waterfall data
        gap_waterfall: list[dict[str, Any]] = [
            {
                "dimension": g["dimension"],
                "label": DIMENSION_LABELS.get(g["dimension"], g["dimension"]),
                "current_score": g["current_score"],
                "gap_size": g["gap_size"],
                "best_in_class_score": g["best_in_class_score"],
                "severity": g["severity"],
            }
            for g in gap_analysis
        ]

        # Summary cards for dashboard header
        summary_cards: list[dict[str, Any]] = [
            {
                "metric": "Overall Maturity Level",
                "value": percentile_rankings.get("overall_maturity_level", "Unknown"),
                "numeric": percentile_rankings.get("overall_score", 0.0),
                "unit": "/ 100",
            },
            {
                "metric": "Industry Percentile",
                "value": f"{percentile_rankings.get('overall_percentile', 0.0):.0f}th",
                "numeric": percentile_rankings.get("overall_percentile", 0.0),
                "unit": "percentile",
            },
            {
                "metric": "Strengths",
                "value": str(len(percentile_rankings.get("strengths", []))),
                "numeric": len(percentile_rankings.get("strengths", [])),
                "unit": f"/ {len(DIMENSIONS)} dimensions",
            },
            {
                "metric": "Critical Gaps",
                "value": str(len([g for g in gap_analysis if g["severity"] == "critical"])),
                "numeric": len([g for g in gap_analysis if g["severity"] == "critical"]),
                "unit": "dimensions",
            },
        ]

        result: dict[str, Any] = {
            "visualization_id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "peer_group_description": peer_group.get("peer_group_description"),
            "peer_sample_size": peer_group.get("sample_size", 0),
            "radar_chart_data": {
                "dimensions": DIMENSIONS,
                "series": radar_series,
                "labels": DIMENSION_LABELS,
            },
            "percentile_bar_data": {
                "bars": percentile_bars,
                "benchmark_line": 50.0,
            },
            "gap_waterfall_data": {
                "entries": gap_waterfall,
                "total_gap": sum(g["gap_size"] for g in gap_analysis),
            },
            "summary_cards": summary_cards,
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

        logger.info(
            "Comparison visualization data generated",
            tenant_id=str(tenant_id),
            radar_series_count=len(radar_series),
        )

        return result

    @staticmethod
    def _interpolate_percentile(
        score: float,
        benchmark: dict[str, Any],
        dimension: str,
    ) -> float:
        """Estimate a percentile rank for a score using benchmark quartile data.

        Uses linear interpolation between known percentile points:
        p25, p50, p75, p90.

        Args:
            score: The score to rank (0–100 scale).
            benchmark: Benchmark record with percentile breakpoints.
            dimension: Dimension name for benchmark lookup (prefix for keys).

        Returns:
            Estimated percentile (0.0–100.0).
        """
        prefix = f"{dimension}_" if dimension != "overall" else "overall_"
        p25 = benchmark.get(f"{prefix}p25", benchmark.get("overall_p25", 25.0))
        p50 = benchmark.get(f"{prefix}p50", benchmark.get("overall_p50", 50.0))
        p75 = benchmark.get(f"{prefix}p75", benchmark.get("overall_p75", 60.0))
        p90 = benchmark.get(f"{prefix}p90", benchmark.get("overall_p90", 75.0))

        if score <= p25:
            return max(0.0, 25.0 * (score / p25)) if p25 > 0 else 0.0
        if score <= p50:
            return 25.0 + 25.0 * (score - p25) / (p50 - p25) if p50 > p25 else 25.0
        if score <= p75:
            return 50.0 + 25.0 * (score - p50) / (p75 - p50) if p75 > p50 else 50.0
        if score <= p90:
            return 75.0 + 15.0 * (score - p75) / (p90 - p75) if p90 > p75 else 75.0
        return 90.0 + 10.0 * min((score - p90) / max(100.0 - p90, 1.0), 1.0)

    @staticmethod
    def _score_to_maturity_level(score: float) -> str:
        """Map a numeric score to a maturity level label.

        Args:
            score: Score between 0.0 and 100.0.

        Returns:
            Maturity level label string.
        """
        for threshold, label in MATURITY_LEVELS:
            if score >= threshold:
                return label
        return "Initial"
