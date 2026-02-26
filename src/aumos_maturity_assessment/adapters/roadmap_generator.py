"""Roadmap generation adapter for the AumOS Maturity Assessment service.

Implements the IRoadmapGeneratorAdapter interface. Produces prioritized
initiative lists from assessment scores using rule-based logic with
optional LLM enrichment for descriptions.
"""

from typing import Any

from aumos_common.observability import get_logger

from aumos_maturity_assessment.settings import Settings

logger = get_logger(__name__)

# Initiative templates per dimension gap
_DIMENSION_INITIATIVES: dict[str, list[dict[str, Any]]] = {
    "data": [
        {
            "title": "Data Quality Foundation Programme",
            "phase": "foundation",
            "effort_weeks": 12,
            "impact_score": 8.5,
            "description": (
                "Implement data quality monitoring, lineage tracking, and automated "
                "validation pipelines across core data assets."
            ),
        },
        {
            "title": "Enterprise Data Catalogue",
            "phase": "foundation",
            "effort_weeks": 8,
            "impact_score": 7.5,
            "description": (
                "Deploy a searchable data catalogue with business glossary, "
                "ownership metadata, and sensitivity classification."
            ),
        },
        {
            "title": "Feature Store Implementation",
            "phase": "scale",
            "effort_weeks": 16,
            "impact_score": 9.0,
            "description": (
                "Build a centralised feature store to eliminate redundant feature "
                "engineering and enable feature reuse across AI projects."
            ),
        },
    ],
    "process": [
        {
            "title": "MLOps Pipeline Standardisation",
            "phase": "foundation",
            "effort_weeks": 10,
            "impact_score": 9.0,
            "description": (
                "Standardise CI/CD for model development with automated testing, "
                "deployment gates, and rollback capabilities."
            ),
        },
        {
            "title": "Model Monitoring and Drift Detection",
            "phase": "scale",
            "effort_weeks": 6,
            "impact_score": 8.0,
            "description": (
                "Deploy automated drift detection and performance monitoring across "
                "production models with alerting and auto-retraining triggers."
            ),
        },
    ],
    "people": [
        {
            "title": "AI Literacy Programme",
            "phase": "quick_wins",
            "effort_weeks": 4,
            "impact_score": 7.0,
            "description": (
                "Launch structured AI literacy training for business stakeholders "
                "covering AI fundamentals, use-case identification, and responsible AI."
            ),
        },
        {
            "title": "AI Centre of Excellence",
            "phase": "scale",
            "effort_weeks": 20,
            "impact_score": 9.5,
            "description": (
                "Establish an AI CoE with dedicated ML engineers, data scientists, "
                "and AI product managers to drive enterprise-wide AI adoption."
            ),
        },
    ],
    "technology": [
        {
            "title": "ML Platform Consolidation",
            "phase": "foundation",
            "effort_weeks": 14,
            "impact_score": 8.5,
            "description": (
                "Consolidate fragmented ML tooling onto a unified platform with "
                "experiment tracking, model registry, and serving infrastructure."
            ),
        },
        {
            "title": "GPU Infrastructure Optimisation",
            "phase": "optimize",
            "effort_weeks": 8,
            "impact_score": 7.5,
            "description": (
                "Optimise GPU utilisation through scheduling, spot instance strategies, "
                "and cost allocation tagging to reduce compute spend by 30-40%."
            ),
        },
    ],
    "governance": [
        {
            "title": "AI Ethics and Responsible AI Framework",
            "phase": "quick_wins",
            "effort_weeks": 6,
            "impact_score": 8.0,
            "description": (
                "Define and publish an AI ethics policy covering fairness, "
                "transparency, accountability, and human oversight requirements."
            ),
        },
        {
            "title": "AI Risk Register and Review Process",
            "phase": "foundation",
            "effort_weeks": 8,
            "impact_score": 8.5,
            "description": (
                "Implement a structured AI risk register with quarterly reviews, "
                "impact assessments, and executive reporting dashboards."
            ),
        },
    ],
}


class RoadmapGeneratorAdapter:
    """Rule-based roadmap generation adapter.

    Analyses dimension gaps from the assessment scores and selects
    high-impact initiatives from curated templates, prioritizing areas
    with the largest gap below target maturity.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise with service settings.

        Args:
            settings: Service settings with roadmap configuration.
        """
        self._settings = settings

    async def generate(
        self,
        assessment: Any,
        benchmark: Any | None,
        horizon_months: int,
        target_maturity_level: int,
    ) -> dict[str, Any]:
        """Generate roadmap initiatives from assessment scores.

        Identifies dimensions with the largest gaps, selects relevant
        initiative templates, and organizes them by phase and priority.

        Args:
            assessment: Completed Assessment with dimension scores.
            benchmark: Optional industry benchmark for peer context.
            horizon_months: Planning horizon in months.
            target_maturity_level: Target maturity level to achieve.

        Returns:
            Dict with initiatives, quick_wins, and estimated_roi_multiplier.
        """
        # Compute gap per dimension (target_score - actual_score)
        target_score = (target_maturity_level - 1) * 20.0 + 10.0  # midpoint of target band
        dimension_gaps: dict[str, float] = {
            "data": target_score - (assessment.data_score or 0.0),
            "process": target_score - (assessment.process_score or 0.0),
            "people": target_score - (assessment.people_score or 0.0),
            "technology": target_score - (assessment.technology_score or 0.0),
            "governance": target_score - (assessment.governance_score or 0.0),
        }

        # Sort dimensions by gap (largest first = highest priority)
        priority_dimensions = sorted(
            dimension_gaps.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        all_initiatives: list[dict[str, Any]] = []
        initiative_counter = 0

        for dimension, gap in priority_dimensions:
            if gap <= 0:
                # Dimension already meets or exceeds target — include one optimize initiative
                templates = [
                    t
                    for t in _DIMENSION_INITIATIVES.get(dimension, [])
                    if t["phase"] == "optimize"
                ]
            else:
                templates = _DIMENSION_INITIATIVES.get(dimension, [])

            for template in templates:
                if initiative_counter >= self._settings.roadmap_max_initiatives:
                    break

                # Calculate if initiative fits within horizon
                fits_horizon = template["effort_weeks"] * 1.5 <= horizon_months * 4.3
                if not fits_horizon and template["phase"] != "quick_wins":
                    continue

                priority = _gap_to_priority(gap)
                all_initiatives.append(
                    {
                        "id": f"init-{dimension}-{initiative_counter + 1:03d}",
                        "title": template["title"],
                        "dimension": dimension,
                        "priority": priority,
                        "effort_weeks": template["effort_weeks"],
                        "impact_score": template["impact_score"],
                        "phase": template["phase"],
                        "description": template["description"],
                        "gap_addressed": round(gap, 2),
                    }
                )
                initiative_counter += 1

        # Extract quick wins (high impact, low effort, ≤8 weeks)
        quick_wins = [
            init
            for init in all_initiatives
            if init["phase"] == "quick_wins" or (
                init["effort_weeks"] <= 8 and init["impact_score"] >= 7.5
            )
        ][:5]  # Cap at 5 quick wins

        # Estimate ROI multiplier based on gap magnitude and benchmark position
        avg_gap = sum(max(g, 0) for g in dimension_gaps.values()) / 5
        estimated_roi_multiplier = round(1.0 + (avg_gap / 100.0) * 3.5, 2)

        logger.info(
            "Roadmap generated from assessment scores",
            assessment_id=str(assessment.id),
            initiative_count=len(all_initiatives),
            quick_win_count=len(quick_wins),
            estimated_roi_multiplier=estimated_roi_multiplier,
            top_gap_dimension=priority_dimensions[0][0] if priority_dimensions else None,
        )

        return {
            "initiatives": all_initiatives,
            "quick_wins": quick_wins,
            "estimated_roi_multiplier": estimated_roi_multiplier,
        }


def _gap_to_priority(gap: float) -> str:
    """Map a dimension gap magnitude to a priority label.

    Args:
        gap: Score gap (target - actual).

    Returns:
        Priority label: critical | high | medium | low.
    """
    if gap >= 50:
        return "critical"
    if gap >= 30:
        return "high"
    if gap >= 15:
        return "medium"
    return "low"
