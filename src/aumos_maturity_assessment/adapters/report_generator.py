"""Report generation adapter for the AumOS Maturity Assessment service.

Implements the IReportGeneratorAdapter interface. Compiles assessment data,
benchmark comparisons, and roadmap recommendations into structured report content.
For production use, this adapter can be extended to integrate with PDF/PPTX
generation libraries or an external document service.
"""

from datetime import datetime, timezone
from typing import Any

from aumos_common.observability import get_logger

from aumos_maturity_assessment.settings import Settings

logger = get_logger(__name__)


class ReportGeneratorAdapter:
    """Structured report content generator.

    Assembles assessment findings, benchmark comparisons, and roadmap
    recommendations into a structured content dict suitable for rendering
    into the requested output format (PDF, PPTX, DOCX, JSON).
    """

    def __init__(self, settings: Settings) -> None:
        """Initialise with service settings.

        Args:
            settings: Service settings with report configuration.
        """
        self._settings = settings

    async def generate(
        self,
        assessment: Any,
        benchmark: Any | None,
        roadmap: Any | None,
        report_type: str,
        format: str,  # noqa: A002
        include_benchmarks: bool,
    ) -> dict[str, Any]:
        """Generate a structured report from assessment data.

        Args:
            assessment: Completed Assessment with dimension scores.
            benchmark: Optional industry benchmark for comparison.
            roadmap: Optional associated roadmap.
            report_type: Type of report to generate.
            format: Output format (pdf, pptx, docx, json).
            include_benchmarks: Whether to include benchmark data.

        Returns:
            Dict with content (structured report sections) and optional artifact_url.
        """
        now = datetime.now(tz=timezone.utc)

        # Build executive summary section
        executive_summary = self._build_executive_summary(
            assessment=assessment,
            benchmark=benchmark if include_benchmarks else None,
        )

        # Build dimension analysis section
        dimension_analysis = self._build_dimension_analysis(
            assessment=assessment,
            benchmark=benchmark if include_benchmarks else None,
        )

        # Build roadmap section if available
        roadmap_section: dict[str, Any] = {}
        if roadmap is not None:
            roadmap_section = self._build_roadmap_section(roadmap=roadmap)

        # Build recommendations
        recommendations = self._build_recommendations(
            assessment=assessment,
            benchmark=benchmark if include_benchmarks else None,
        )

        content: dict[str, Any] = {
            "report_type": report_type,
            "format": format,
            "generated_at": now.isoformat(),
            "organization_name": assessment.organization_name,
            "industry": assessment.industry,
            "organization_size": assessment.organization_size,
            "sections": {
                "executive_summary": executive_summary,
                "dimension_analysis": dimension_analysis,
                "recommendations": recommendations,
            },
            "metadata": {
                "assessment_id": str(assessment.id),
                "overall_score": assessment.overall_score,
                "maturity_level": assessment.maturity_level,
                "include_benchmarks": include_benchmarks,
                "benchmark_period": benchmark.benchmark_period if benchmark else None,
                "roadmap_included": roadmap is not None,
                "template_version": "1.0",
            },
        }

        if roadmap_section:
            content["sections"]["roadmap"] = roadmap_section

        logger.debug(
            "Report content generated",
            assessment_id=str(assessment.id),
            report_type=report_type,
            format=format,
            section_count=len(content["sections"]),
        )

        return {
            "content": content,
            "artifact_url": None,  # TODO: Integrate with document rendering service
        }

    def _build_executive_summary(
        self,
        assessment: Any,
        benchmark: Any | None,
    ) -> dict[str, Any]:
        """Build the executive summary section.

        Args:
            assessment: Assessment with scores.
            benchmark: Optional benchmark for comparison.

        Returns:
            Executive summary section dict.
        """
        maturity_labels = {
            1: "Initial",
            2: "Developing",
            3: "Defined",
            4: "Managed",
            5: "Optimizing",
        }
        maturity_label = maturity_labels.get(assessment.maturity_level or 1, "Unknown")

        summary: dict[str, Any] = {
            "title": "Executive Summary",
            "overall_score": assessment.overall_score,
            "maturity_level": assessment.maturity_level,
            "maturity_label": maturity_label,
            "headline": (
                f"{assessment.organization_name} is at the {maturity_label} stage of AI maturity "
                f"with an overall score of {assessment.overall_score:.1f}/100."
            ),
            "key_findings": [
                f"Overall maturity level: {maturity_label} ({assessment.overall_score:.1f}/100)",
                f"Strongest dimension: {self._strongest_dimension(assessment)}",
                f"Priority improvement area: {self._weakest_dimension(assessment)}",
            ],
        }

        if benchmark:
            summary["benchmark_context"] = {
                "industry": assessment.industry,
                "benchmark_period": benchmark.benchmark_period,
                "industry_median": benchmark.overall_p50,
                "vs_median": round((assessment.overall_score or 0) - benchmark.overall_p50, 2),
            }

        return summary

    def _build_dimension_analysis(
        self,
        assessment: Any,
        benchmark: Any | None,
    ) -> dict[str, Any]:
        """Build the dimension-by-dimension analysis section.

        Args:
            assessment: Assessment with dimension scores.
            benchmark: Optional benchmark for comparison.

        Returns:
            Dimension analysis section dict.
        """
        dimensions = ["data", "process", "people", "technology", "governance"]
        dimension_details: dict[str, Any] = {}

        for dim in dimensions:
            score = getattr(assessment, f"{dim}_score") or 0.0
            detail: dict[str, Any] = {
                "score": score,
                "weight": assessment.dimension_weights.get(dim, 0.0),
            }

            if benchmark:
                median = getattr(benchmark, f"{dim}_p50")
                detail["benchmark_median"] = median
                detail["gap"] = round(score - median, 2)
                detail["above_median"] = score >= median

            dimension_details[dim] = detail

        return {
            "title": "Multi-Dimensional Analysis",
            "dimensions": dimension_details,
        }

    def _build_roadmap_section(self, roadmap: Any) -> dict[str, Any]:
        """Build the roadmap summary section.

        Args:
            roadmap: Associated roadmap.

        Returns:
            Roadmap section dict.
        """
        return {
            "title": "AI Adoption Roadmap",
            "roadmap_id": str(roadmap.id),
            "roadmap_title": roadmap.title,
            "horizon_months": roadmap.horizon_months,
            "target_maturity_level": roadmap.target_maturity_level,
            "quick_wins": roadmap.quick_wins,
            "total_initiatives": len(roadmap.initiatives),
            "estimated_roi_multiplier": roadmap.estimated_roi_multiplier,
            "phases": {
                "quick_wins": [i for i in roadmap.initiatives if i.get("phase") == "quick_wins"],
                "foundation": [i for i in roadmap.initiatives if i.get("phase") == "foundation"],
                "scale": [i for i in roadmap.initiatives if i.get("phase") == "scale"],
                "optimize": [i for i in roadmap.initiatives if i.get("phase") == "optimize"],
            },
        }

    def _build_recommendations(
        self,
        assessment: Any,
        benchmark: Any | None,
    ) -> dict[str, Any]:
        """Build the recommendations section.

        Args:
            assessment: Assessment with dimension scores.
            benchmark: Optional benchmark for priority guidance.

        Returns:
            Recommendations section dict.
        """
        weakest = self._weakest_dimension(assessment)
        strongest = self._strongest_dimension(assessment)

        immediate_actions: list[str] = []
        if weakest == "data":
            immediate_actions.append(
                "Conduct a data quality audit across core data assets within 30 days."
            )
        elif weakest == "governance":
            immediate_actions.append(
                "Establish an AI ethics committee and publish an AI usage policy within 60 days."
            )
        elif weakest == "people":
            immediate_actions.append(
                "Launch an AI literacy programme for business stakeholders within 45 days."
            )
        elif weakest == "process":
            immediate_actions.append(
                "Define and document your ML model deployment process within 30 days."
            )
        elif weakest == "technology":
            immediate_actions.append(
                "Assess your ML tooling landscape and identify consolidation opportunities."
            )

        return {
            "title": "Strategic Recommendations",
            "immediate_actions": immediate_actions,
            "priority_dimension": weakest,
            "leverage_dimension": strongest,
            "next_milestone": f"Advance from Level {assessment.maturity_level} to Level {min((assessment.maturity_level or 1) + 1, 5)}",
        }

    def _weakest_dimension(self, assessment: Any) -> str:
        """Identify the dimension with the lowest score.

        Args:
            assessment: Assessment with dimension scores.

        Returns:
            Dimension name string.
        """
        scores = {
            "data": assessment.data_score or 0.0,
            "process": assessment.process_score or 0.0,
            "people": assessment.people_score or 0.0,
            "technology": assessment.technology_score or 0.0,
            "governance": assessment.governance_score or 0.0,
        }
        return min(scores, key=lambda k: scores[k])

    def _strongest_dimension(self, assessment: Any) -> str:
        """Identify the dimension with the highest score.

        Args:
            assessment: Assessment with dimension scores.

        Returns:
            Dimension name string.
        """
        scores = {
            "data": assessment.data_score or 0.0,
            "process": assessment.process_score or 0.0,
            "people": assessment.people_score or 0.0,
            "technology": assessment.technology_score or 0.0,
            "governance": assessment.governance_score or 0.0,
        }
        return max(scores, key=lambda k: scores[k])
