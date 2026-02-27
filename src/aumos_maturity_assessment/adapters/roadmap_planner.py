"""Advanced roadmap planning adapter for the AumOS Maturity Assessment service.

Transforms gap analysis data into detailed, actionable improvement roadmaps with
priority sequencing, effort/impact estimation, timeline generation, milestone
definition, dependency identification, and Gantt-compatible export formats.

This adapter complements ``RoadmapGeneratorAdapter`` by providing richer planning
outputs suitable for executive presentations and project management tooling.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from aumos_common.observability import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIMENSIONS: list[str] = ["data", "process", "people", "technology", "governance"]

# Effort buckets (weeks) → label
EFFORT_LABELS: list[tuple[int, str]] = [
    (4, "quick_win"),
    (8, "short_term"),
    (16, "medium_term"),
    (999, "long_term"),
]

# Impact score → label
IMPACT_LABELS: list[tuple[float, str]] = [
    (8.0, "transformational"),
    (6.0, "significant"),
    (4.0, "moderate"),
    (0.0, "incremental"),
]

# Dependency graph: which dimensions typically must precede others
DIMENSION_DEPENDENCIES: dict[str, list[str]] = {
    "process": ["data"],          # Process maturity needs data foundation
    "technology": ["data"],       # Technology investments require solid data
    "governance": ["process"],    # Governance formalizes mature processes
    "people": [],                 # People initiatives can run in parallel
    "data": [],                   # Data is the foundation — no prerequisites
}

# Phase labels in priority order
PHASE_ORDER: list[str] = ["quick_wins", "foundation", "scale", "optimize"]

# Typical milestone achievement weeks per initiative count
_MILESTONE_CADENCE_WEEKS: int = 8


class RoadmapPlanner:
    """Advanced roadmap planning adapter.

    Converts gap analysis results into structured roadmaps with:
    - Priority-sequenced initiatives (quick wins first, strategic later)
    - Effort and impact estimation per action
    - Timeline generation with start/end weeks
    - Milestone definitions at 8-week intervals
    - Dependency identification across dimensions
    - Roadmap export in JSON and Gantt-compatible formats

    Args:
        action_library: Mapping of dimension to list of action templates.
            Each template requires keys: title, description, effort_weeks,
            impact_score, phase, tags (list[str]).
        initiative_cap: Maximum number of initiatives to include in a roadmap.
        quick_win_effort_threshold_weeks: Max effort weeks to classify as quick win.
        quick_win_impact_threshold: Min impact score to classify as quick win.
    """

    def __init__(
        self,
        action_library: dict[str, list[dict[str, Any]]] | None = None,
        initiative_cap: int = 20,
        quick_win_effort_threshold_weeks: int = 6,
        quick_win_impact_threshold: float = 6.5,
    ) -> None:
        """Initialise with optional custom action library.

        Args:
            action_library: Custom dimension-to-actions mapping. Defaults to
                built-in library if not provided.
            initiative_cap: Maximum initiatives per roadmap.
            quick_win_effort_threshold_weeks: Max effort weeks for quick win classification.
            quick_win_impact_threshold: Min impact score for quick win classification.
        """
        self._library = action_library or _build_default_action_library()
        self._initiative_cap = initiative_cap
        self._quick_win_effort_weeks = quick_win_effort_threshold_weeks
        self._quick_win_impact = quick_win_impact_threshold

    async def map_gaps_to_actions(
        self,
        gap_analysis: dict[str, Any],
        horizon_months: int = 12,
    ) -> dict[str, Any]:
        """Map dimension gaps to specific, actionable initiatives.

        Selects relevant actions from the library for each dimension that has
        a positive gap (below target). Skips dimensions already at or above target.

        Args:
            gap_analysis: Output from BenchmarkComparator.analyze_gap_vs_best_in_class
                containing keys: overall_gap, dimension_gaps (list of
                {dimension, score, best_in_class_score, gap_to_best_in_class}).
            horizon_months: Planning horizon to constrain initiative selection.

        Returns:
            Dict with keys: actions (list), total_actions_count, dimensions_addressed,
            horizon_months.
        """
        horizon_weeks = horizon_months * 4.33

        dimension_gaps: dict[str, float] = {}
        for gap_item in gap_analysis.get("dimension_gaps", []):
            dimension = gap_item.get("dimension", "")
            gap_value = gap_item.get("gap_to_best_in_class", 0.0)
            if dimension and gap_value > 0:
                dimension_gaps[dimension] = gap_value

        actions: list[dict[str, Any]] = []
        action_counter = 0

        # Sort by gap magnitude descending for priority ordering
        sorted_dims = sorted(dimension_gaps.items(), key=lambda x: x[1], reverse=True)

        for dimension, gap in sorted_dims:
            if action_counter >= self._initiative_cap:
                break

            dim_actions = self._library.get(dimension, [])
            for action_template in dim_actions:
                if action_counter >= self._initiative_cap:
                    break

                effort_weeks: int = action_template.get("effort_weeks", 8)
                impact_score: float = action_template.get("impact_score", 5.0)
                phase: str = action_template.get("phase", "foundation")

                # Exclude actions that exceed the horizon (unless they are quick wins)
                if effort_weeks * 1.2 > horizon_weeks and phase != "quick_wins":
                    continue

                action_id = f"act-{dimension[:3]}-{action_counter + 1:03d}"
                effort_label = _effort_to_label(effort_weeks)
                impact_label = _impact_to_label(impact_score)

                actions.append(
                    {
                        "id": action_id,
                        "dimension": dimension,
                        "title": action_template["title"],
                        "description": action_template["description"],
                        "effort_weeks": effort_weeks,
                        "effort_label": effort_label,
                        "impact_score": impact_score,
                        "impact_label": impact_label,
                        "phase": phase,
                        "gap_addressed_points": round(gap, 2),
                        "tags": action_template.get("tags", [dimension]),
                    }
                )
                action_counter += 1

        dimensions_addressed = list({a["dimension"] for a in actions})

        logger.info(
            "Gap-to-action mapping completed",
            total_actions=len(actions),
            dimensions_addressed=dimensions_addressed,
            horizon_months=horizon_months,
        )

        return {
            "actions": actions,
            "total_actions_count": len(actions),
            "dimensions_addressed": dimensions_addressed,
            "horizon_months": horizon_months,
        }

    async def sequence_by_priority(
        self,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Sequence actions from quick wins through strategic initiatives.

        Ordering rules (applied in sequence):
        1. Phase order: quick_wins → foundation → scale → optimize
        2. Within same phase: higher impact_score first
        3. Within same impact band: lower effort_weeks first

        Also flags dimension dependencies (e.g., process actions that
        depend on data actions being completed first).

        Args:
            actions: List of action dicts from map_gaps_to_actions.

        Returns:
            Dict with keys: sequenced_actions, quick_wins, strategic_initiatives,
            dependency_warnings.
        """

        def sort_key(action: dict[str, Any]) -> tuple[int, float, int]:
            phase_rank = PHASE_ORDER.index(action.get("phase", "scale")) if action.get("phase") in PHASE_ORDER else 2
            return (phase_rank, -action.get("impact_score", 0.0), action.get("effort_weeks", 999))

        sequenced = sorted(actions, key=sort_key)

        quick_wins = [
            a for a in sequenced
            if (
                a.get("effort_weeks", 999) <= self._quick_win_effort_weeks
                and a.get("impact_score", 0.0) >= self._quick_win_impact
            )
            or a.get("phase") == "quick_wins"
        ]

        strategic_initiatives = [
            a for a in sequenced
            if a not in quick_wins and a.get("phase") in ("scale", "optimize")
        ]

        # Detect dependency violations
        dependency_warnings = _detect_dependency_violations(sequenced)

        logger.info(
            "Actions sequenced by priority",
            total=len(sequenced),
            quick_wins=len(quick_wins),
            strategic=len(strategic_initiatives),
            dependency_warnings=len(dependency_warnings),
        )

        return {
            "sequenced_actions": sequenced,
            "quick_wins": quick_wins,
            "strategic_initiatives": strategic_initiatives,
            "dependency_warnings": dependency_warnings,
        }

    async def estimate_effort_and_impact(
        self,
        actions: list[dict[str, Any]],
        team_capacity_hours_per_week: float = 40.0,
        hourly_cost_usd: float = 150.0,
    ) -> dict[str, Any]:
        """Compute detailed effort and impact estimates for each action.

        Args:
            actions: List of sequenced action dicts.
            team_capacity_hours_per_week: Available team hours per week (default 40).
            hourly_cost_usd: Fully-loaded hourly team cost in USD (default 150).

        Returns:
            Dict with keys: enriched_actions, total_effort_weeks, total_cost_usd,
            total_weighted_impact, capacity_utilization_percent.
        """
        enriched: list[dict[str, Any]] = []
        total_effort_weeks = 0.0
        total_cost_usd = 0.0
        total_weighted_impact = 0.0

        for action in actions:
            effort_weeks: float = float(action.get("effort_weeks", 8))
            impact_score: float = action.get("impact_score", 5.0)

            # Estimated hours: effort_weeks × 60% team utilization
            estimated_hours = effort_weeks * team_capacity_hours_per_week * 0.60
            estimated_cost = estimated_hours * hourly_cost_usd

            # ROI index: impact per dollar invested (normalized)
            roi_index = impact_score / (estimated_cost / 1000.0) if estimated_cost > 0 else 0.0

            enriched_action = {
                **action,
                "estimated_hours": round(estimated_hours, 1),
                "estimated_cost_usd": round(estimated_cost, 2),
                "roi_index": round(roi_index, 4),
                "confidence_level": _compute_confidence_level(effort_weeks, impact_score),
            }
            enriched.append(enriched_action)

            total_effort_weeks += effort_weeks
            total_cost_usd += estimated_cost
            total_weighted_impact += impact_score * (10.0 - effort_weeks / 4.0)

        # Capacity utilization: how saturated is the team
        capacity_utilization_percent = min(
            100.0,
            (total_effort_weeks / (len(actions) * 12.0)) * 100.0 if actions else 0.0,
        )

        logger.info(
            "Effort and impact estimation completed",
            action_count=len(enriched),
            total_effort_weeks=round(total_effort_weeks, 1),
            total_cost_usd=round(total_cost_usd, 2),
        )

        return {
            "enriched_actions": enriched,
            "total_effort_weeks": round(total_effort_weeks, 1),
            "total_cost_usd": round(total_cost_usd, 2),
            "total_weighted_impact": round(total_weighted_impact, 2),
            "capacity_utilization_percent": round(capacity_utilization_percent, 1),
        }

    async def generate_timeline(
        self,
        sequenced_actions: list[dict[str, Any]],
        start_date: datetime | None = None,
        parallel_streams: int = 2,
    ) -> dict[str, Any]:
        """Assign start/end dates to each action based on sequencing and parallelism.

        Actions in the same phase can run in parallel streams. Actions with
        dependencies on other dimensions are scheduled after their prerequisites.

        Args:
            sequenced_actions: Priority-ordered actions from sequence_by_priority.
            start_date: Roadmap kickoff date (defaults to today UTC).
            parallel_streams: Number of work streams running concurrently.

        Returns:
            Dict with keys: timeline_entries (list), start_date, projected_end_date,
            duration_weeks.
        """
        effective_start = start_date or datetime.now(tz=timezone.utc)
        start_week = 0

        # Assign each action to a stream and compute week offsets
        stream_end_weeks: list[float] = [0.0] * parallel_streams
        dimension_completion_weeks: dict[str, float] = {}

        timeline_entries: list[dict[str, Any]] = []

        for action in sequenced_actions:
            dimension = action.get("dimension", "")
            effort_weeks: float = float(action.get("effort_weeks", 8))

            # Check if this action has a dimension dependency
            prereqs = DIMENSION_DEPENDENCIES.get(dimension, [])
            earliest_start_week: float = float(start_week)
            for prereq_dim in prereqs:
                prereq_completion = dimension_completion_weeks.get(prereq_dim, 0.0)
                earliest_start_week = max(earliest_start_week, prereq_completion)

            # Assign to the earliest available stream that respects the constraint
            best_stream = 0
            best_stream_start = float("inf")
            for stream_idx, stream_end in enumerate(stream_end_weeks):
                candidate_start = max(stream_end, earliest_start_week)
                if candidate_start < best_stream_start:
                    best_stream_start = candidate_start
                    best_stream = stream_idx

            action_start_week = best_stream_start
            action_end_week = action_start_week + effort_weeks

            stream_end_weeks[best_stream] = action_end_week

            # Track when each dimension's actions complete
            existing_completion = dimension_completion_weeks.get(dimension, 0.0)
            dimension_completion_weeks[dimension] = max(existing_completion, action_end_week)

            # Convert week offsets to calendar dates
            start_offset_days = int(action_start_week * 7)
            end_offset_days = int(action_end_week * 7)

            from datetime import timedelta
            action_start_date = effective_start + timedelta(days=start_offset_days)
            action_end_date = effective_start + timedelta(days=end_offset_days)

            timeline_entries.append(
                {
                    "action_id": action.get("id", ""),
                    "title": action.get("title", ""),
                    "dimension": dimension,
                    "phase": action.get("phase", ""),
                    "stream": best_stream + 1,
                    "start_week": round(action_start_week, 1),
                    "end_week": round(action_end_week, 1),
                    "start_date": action_start_date.strftime("%Y-%m-%d"),
                    "end_date": action_end_date.strftime("%Y-%m-%d"),
                    "effort_weeks": effort_weeks,
                }
            )

        total_duration_weeks = max(stream_end_weeks) if stream_end_weeks else 0.0
        from datetime import timedelta
        projected_end_date = effective_start + timedelta(days=int(total_duration_weeks * 7))

        logger.info(
            "Timeline generated",
            action_count=len(timeline_entries),
            duration_weeks=round(total_duration_weeks, 1),
            parallel_streams=parallel_streams,
            projected_end=projected_end_date.strftime("%Y-%m-%d"),
        )

        return {
            "timeline_entries": timeline_entries,
            "start_date": effective_start.strftime("%Y-%m-%d"),
            "projected_end_date": projected_end_date.strftime("%Y-%m-%d"),
            "duration_weeks": round(total_duration_weeks, 1),
        }

    async def define_milestones(
        self,
        timeline_entries: list[dict[str, Any]],
        horizon_months: int = 12,
    ) -> dict[str, Any]:
        """Define milestone checkpoints at regular intervals.

        Milestones are placed every 8 weeks and capture which actions complete
        in each interval. Also identifies phase completion milestones.

        Args:
            timeline_entries: Timeline data from generate_timeline.
            horizon_months: Total roadmap horizon for milestone spacing.

        Returns:
            Dict with keys: milestones, phase_completions, total_milestone_count.
        """
        total_weeks = horizon_months * 4.33
        milestone_interval = _MILESTONE_CADENCE_WEEKS

        milestones: list[dict[str, Any]] = []
        milestone_number = 1

        week_cursor = milestone_interval
        while week_cursor <= total_weeks + milestone_interval:
            actions_completing = [
                entry
                for entry in timeline_entries
                if week_cursor - milestone_interval <= entry.get("end_week", 0) < week_cursor
            ]

            if actions_completing or week_cursor <= total_weeks:
                milestones.append(
                    {
                        "milestone_id": f"M{milestone_number:02d}",
                        "week": int(week_cursor),
                        "label": f"Week {int(week_cursor)} Checkpoint",
                        "actions_completed_count": len(actions_completing),
                        "actions_completed": [
                            {"id": e["action_id"], "title": e["title"]}
                            for e in actions_completing
                        ],
                        "cumulative_actions_completed": sum(
                            1 for entry in timeline_entries
                            if entry.get("end_week", 0) <= week_cursor
                        ),
                    }
                )
                milestone_number += 1

            week_cursor += milestone_interval

        # Phase completion milestones
        phase_completions: list[dict[str, Any]] = []
        for phase in PHASE_ORDER:
            phase_entries = [e for e in timeline_entries if e.get("phase") == phase]
            if phase_entries:
                completion_week = max(e.get("end_week", 0) for e in phase_entries)
                phase_completions.append(
                    {
                        "phase": phase,
                        "completion_week": round(completion_week, 1),
                        "action_count": len(phase_entries),
                    }
                )

        logger.info(
            "Milestones defined",
            milestone_count=len(milestones),
            phase_completions=len(phase_completions),
        )

        return {
            "milestones": milestones,
            "phase_completions": phase_completions,
            "total_milestone_count": len(milestones),
        }

    async def identify_dependencies(
        self,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Identify and document dependencies between actions.

        Maps intra-dimension sequencing (phase order within a dimension)
        and inter-dimension dependencies (data before process, etc.).

        Args:
            actions: List of action dicts with id, dimension, and phase.

        Returns:
            Dict with keys: dependencies (list of {from_action_id, to_action_id,
            dependency_type, description}), dependency_graph, orphaned_actions.
        """
        dependencies: list[dict[str, Any]] = []
        dependency_graph: dict[str, list[str]] = {}

        # Group actions by dimension
        by_dimension: dict[str, list[dict[str, Any]]] = {}
        for action in actions:
            dim = action.get("dimension", "unknown")
            by_dimension.setdefault(dim, []).append(action)

        # Intra-dimension: phase order (quick_wins → foundation → scale → optimize)
        for dimension, dim_actions in by_dimension.items():
            sorted_dim = sorted(
                dim_actions,
                key=lambda a: PHASE_ORDER.index(a.get("phase", "scale"))
                if a.get("phase") in PHASE_ORDER
                else 2,
            )
            for i in range(len(sorted_dim) - 1):
                predecessor = sorted_dim[i]
                successor = sorted_dim[i + 1]
                if predecessor.get("phase") != successor.get("phase"):
                    dep = {
                        "from_action_id": predecessor["id"],
                        "to_action_id": successor["id"],
                        "dependency_type": "phase_sequence",
                        "description": (
                            f"{predecessor['title']} should complete before "
                            f"{successor['title']} within {dimension}."
                        ),
                    }
                    dependencies.append(dep)
                    dependency_graph.setdefault(successor["id"], []).append(predecessor["id"])

        # Inter-dimension: dimension prerequisite graph
        for dimension, prereq_dims in DIMENSION_DEPENDENCIES.items():
            if not prereq_dims:
                continue

            dim_actions = by_dimension.get(dimension, [])
            for prereq_dim in prereq_dims:
                prereq_actions = by_dimension.get(prereq_dim, [])
                if not prereq_actions or not dim_actions:
                    continue

                # The first action of the dependent dimension depends on
                # the foundation-phase actions of the prerequisite dimension
                prereq_foundation = [
                    a for a in prereq_actions if a.get("phase") in ("quick_wins", "foundation")
                ]
                if not prereq_foundation:
                    prereq_foundation = prereq_actions[:1]

                first_dependent = min(
                    dim_actions,
                    key=lambda a: PHASE_ORDER.index(a.get("phase", "scale"))
                    if a.get("phase") in PHASE_ORDER
                    else 2,
                )

                for prereq_action in prereq_foundation[:2]:  # Cap at 2 dependencies per pair
                    dep = {
                        "from_action_id": prereq_action["id"],
                        "to_action_id": first_dependent["id"],
                        "dependency_type": "cross_dimension",
                        "description": (
                            f"'{dimension}' maturity initiatives benefit from "
                            f"'{prereq_dim}' foundation being in place first."
                        ),
                    }
                    dependencies.append(dep)
                    dependency_graph.setdefault(first_dependent["id"], []).append(prereq_action["id"])

        # Orphaned actions: actions with no dependencies (valid, just worth noting)
        dependent_action_ids = {dep["to_action_id"] for dep in dependencies}
        orphaned_actions = [
            {"id": a["id"], "title": a["title"], "dimension": a["dimension"]}
            for a in actions
            if a["id"] not in dependent_action_ids
        ]

        logger.info(
            "Dependencies identified",
            total_dependencies=len(dependencies),
            orphaned_actions=len(orphaned_actions),
            dimensions_with_cross_deps=len(
                {d["to_action_id"] for d in dependencies if d["dependency_type"] == "cross_dimension"}
            ),
        )

        return {
            "dependencies": dependencies,
            "dependency_graph": dependency_graph,
            "orphaned_actions": orphaned_actions,
        }

    async def export_roadmap_json(
        self,
        actions: list[dict[str, Any]],
        timeline: dict[str, Any],
        milestones: dict[str, Any],
        dependencies: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Export the complete roadmap as a structured JSON document.

        Args:
            actions: Sequenced and enriched action list.
            timeline: Timeline data from generate_timeline.
            milestones: Milestone data from define_milestones.
            dependencies: Dependency data from identify_dependencies.
            metadata: Optional metadata dict (assessment_id, tenant_id, etc.).

        Returns:
            Complete roadmap JSON document dict.
        """
        exported_at = datetime.now(tz=timezone.utc).isoformat()

        dimension_summary: dict[str, dict[str, Any]] = {}
        for action in actions:
            dim = action.get("dimension", "unknown")
            if dim not in dimension_summary:
                dimension_summary[dim] = {
                    "action_count": 0,
                    "total_effort_weeks": 0.0,
                    "avg_impact_score": 0.0,
                    "phases": set(),
                }
            dimension_summary[dim]["action_count"] += 1
            dimension_summary[dim]["total_effort_weeks"] += action.get("effort_weeks", 0)
            dimension_summary[dim]["avg_impact_score"] += action.get("impact_score", 0.0)
            dimension_summary[dim]["phases"].add(action.get("phase", ""))

        for dim, summary in dimension_summary.items():
            count = summary["action_count"]
            summary["avg_impact_score"] = round(summary["avg_impact_score"] / count, 2) if count else 0.0
            summary["total_effort_weeks"] = round(summary["total_effort_weeks"], 1)
            summary["phases"] = sorted(summary["phases"])

        roadmap_document = {
            "schema_version": "1.0",
            "exported_at": exported_at,
            "metadata": metadata or {},
            "summary": {
                "total_actions": len(actions),
                "total_duration_weeks": timeline.get("duration_weeks", 0),
                "start_date": timeline.get("start_date", ""),
                "projected_end_date": timeline.get("projected_end_date", ""),
                "milestone_count": milestones.get("total_milestone_count", 0),
                "dependency_count": len(dependencies.get("dependencies", [])),
                "dimension_summary": dimension_summary,
            },
            "actions": actions,
            "timeline": timeline.get("timeline_entries", []),
            "milestones": milestones.get("milestones", []),
            "phase_completions": milestones.get("phase_completions", []),
            "dependencies": dependencies.get("dependencies", []),
        }

        logger.info(
            "Roadmap JSON export completed",
            total_actions=len(actions),
            exported_at=exported_at,
        )

        return roadmap_document

    async def export_gantt_data(
        self,
        timeline_entries: list[dict[str, Any]],
        milestones: dict[str, Any],
        start_date: str,
    ) -> dict[str, Any]:
        """Export roadmap data in Gantt chart format.

        Produces data compatible with common Gantt chart libraries (e.g.,
        DHTMLX Gantt, Frappe Gantt, Mermaid gantt). Uses task/link structure.

        Args:
            timeline_entries: Timeline data from generate_timeline.
            milestones: Milestone data from define_milestones.
            start_date: Roadmap start date string (YYYY-MM-DD).

        Returns:
            Dict with keys: tasks (list), links (list), milestones_gantt (list),
            chart_config (metadata for rendering).
        """
        # Phase color mapping for visual grouping
        phase_colors: dict[str, str] = {
            "quick_wins": "#22c55e",    # green
            "foundation": "#3b82f6",   # blue
            "scale": "#f59e0b",        # amber
            "optimize": "#8b5cf6",     # purple
        }

        dimension_colors: dict[str, str] = {
            "data": "#06b6d4",         # cyan
            "process": "#10b981",      # emerald
            "people": "#f97316",       # orange
            "technology": "#6366f1",   # indigo
            "governance": "#ec4899",   # pink
        }

        tasks: list[dict[str, Any]] = []
        task_id_map: dict[str, int] = {}

        for idx, entry in enumerate(timeline_entries, start=1):
            task_id = idx
            task_id_map[entry.get("action_id", "")] = task_id

            tasks.append(
                {
                    "id": task_id,
                    "action_id": entry.get("action_id", ""),
                    "text": entry.get("title", ""),
                    "start_date": entry.get("start_date", ""),
                    "end_date": entry.get("end_date", ""),
                    "duration_weeks": entry.get("effort_weeks", 0),
                    "progress": 0.0,
                    "parent": 0,
                    "phase": entry.get("phase", ""),
                    "dimension": entry.get("dimension", ""),
                    "color": phase_colors.get(entry.get("phase", ""), "#64748b"),
                    "dimension_color": dimension_colors.get(entry.get("dimension", ""), "#64748b"),
                    "stream": entry.get("stream", 1),
                    "open": True,
                }
            )

        # Build milestone markers for Gantt
        milestones_gantt: list[dict[str, Any]] = []
        for milestone in milestones.get("milestones", []):
            milestone_id = len(tasks) + len(milestones_gantt) + 1
            milestones_gantt.append(
                {
                    "id": milestone_id,
                    "text": milestone.get("label", ""),
                    "milestone_id": milestone.get("milestone_id", ""),
                    "week": milestone.get("week", 0),
                    "actions_completed_count": milestone.get("actions_completed_count", 0),
                    "color": "#f43f5e",  # rose
                }
            )

        # Chart configuration metadata
        chart_config = {
            "start_date": start_date,
            "scale_unit": "week",
            "date_format": "%Y-%m-%d",
            "columns": [
                {"name": "text", "label": "Initiative", "width": 200},
                {"name": "dimension", "label": "Dimension", "width": 100},
                {"name": "phase", "label": "Phase", "width": 90},
                {"name": "duration_weeks", "label": "Weeks", "width": 60},
            ],
            "phase_colors": phase_colors,
            "dimension_colors": dimension_colors,
        }

        logger.info(
            "Gantt data export completed",
            task_count=len(tasks),
            milestone_count=len(milestones_gantt),
        )

        return {
            "tasks": tasks,
            "milestones_gantt": milestones_gantt,
            "chart_config": chart_config,
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _effort_to_label(effort_weeks: int) -> str:
    """Convert effort in weeks to a human-readable label.

    Args:
        effort_weeks: Estimated effort in weeks.

    Returns:
        Effort label: quick_win | short_term | medium_term | long_term.
    """
    for threshold, label in EFFORT_LABELS:
        if effort_weeks <= threshold:
            return label
    return "long_term"


def _impact_to_label(impact_score: float) -> str:
    """Convert an impact score to a human-readable label.

    Args:
        impact_score: Impact score (0.0–10.0).

    Returns:
        Impact label: transformational | significant | moderate | incremental.
    """
    for threshold, label in IMPACT_LABELS:
        if impact_score >= threshold:
            return label
    return "incremental"


def _compute_confidence_level(effort_weeks: float, impact_score: float) -> str:
    """Estimate confidence level of the effort/impact estimate.

    Shorter, higher-impact actions tend to be more predictable.

    Args:
        effort_weeks: Estimated effort weeks.
        impact_score: Impact score (0.0–10.0).

    Returns:
        Confidence level: high | medium | low.
    """
    if effort_weeks <= 6 and impact_score >= 7.0:
        return "high"
    if effort_weeks <= 14:
        return "medium"
    return "low"


def _detect_dependency_violations(
    sequenced_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect cases where dimension prerequisites appear after dependent actions.

    Args:
        sequenced_actions: Priority-ordered list of actions.

    Returns:
        List of warning dicts describing violated dependencies.
    """
    warnings: list[dict[str, Any]] = []

    # Track first occurrence index of each dimension
    first_index: dict[str, int] = {}
    for idx, action in enumerate(sequenced_actions):
        dim = action.get("dimension", "")
        if dim not in first_index:
            first_index[dim] = idx

    for dimension, prereq_dims in DIMENSION_DEPENDENCIES.items():
        for prereq_dim in prereq_dims:
            dim_first = first_index.get(dimension)
            prereq_first = first_index.get(prereq_dim)

            if dim_first is not None and prereq_first is not None:
                if dim_first < prereq_first:
                    warnings.append(
                        {
                            "warning_type": "dependency_violation",
                            "dimension": dimension,
                            "prerequisite_dimension": prereq_dim,
                            "message": (
                                f"'{dimension}' actions start before '{prereq_dim}' "
                                f"foundation is in place. Consider reordering or running "
                                f"'{prereq_dim}' work in a parallel stream first."
                            ),
                        }
                    )

    return warnings


def _build_default_action_library() -> dict[str, list[dict[str, Any]]]:
    """Build the built-in action library with templates for all five dimensions.

    Returns:
        Dict mapping dimension name to list of action template dicts.
    """
    return {
        "data": [
            {
                "title": "Data Quality Baseline Assessment",
                "description": (
                    "Conduct a comprehensive audit of core data assets to establish "
                    "a quality baseline. Profile completeness, consistency, accuracy, "
                    "and timeliness metrics per data domain."
                ),
                "effort_weeks": 3,
                "impact_score": 7.5,
                "phase": "quick_wins",
                "tags": ["data", "quality", "assessment"],
            },
            {
                "title": "Enterprise Data Catalogue Deployment",
                "description": (
                    "Deploy a searchable data catalogue (e.g., DataHub, Collibra) with "
                    "business glossary, ownership metadata, lineage tracking, and "
                    "sensitivity classification across all AI-relevant data assets."
                ),
                "effort_weeks": 8,
                "impact_score": 8.0,
                "phase": "foundation",
                "tags": ["data", "governance", "catalogue"],
            },
            {
                "title": "Automated Data Pipeline Validation",
                "description": (
                    "Implement automated data quality checks (Great Expectations or "
                    "similar) within all data pipelines feeding AI/ML models. Define "
                    "SLAs per pipeline and alert on quality degradation."
                ),
                "effort_weeks": 10,
                "impact_score": 8.5,
                "phase": "foundation",
                "tags": ["data", "quality", "pipelines"],
            },
            {
                "title": "Feature Store Implementation",
                "description": (
                    "Build a centralised feature store (Feast, Tecton) to eliminate "
                    "redundant feature engineering across teams. Enable feature reuse, "
                    "versioning, and point-in-time correct lookups."
                ),
                "effort_weeks": 16,
                "impact_score": 9.0,
                "phase": "scale",
                "tags": ["data", "ml", "feature-store"],
            },
            {
                "title": "Real-Time Data Streaming Architecture",
                "description": (
                    "Extend the data platform with real-time streaming capabilities "
                    "(Kafka, Flink) to support online inference use cases and continuous "
                    "model monitoring with live data."
                ),
                "effort_weeks": 20,
                "impact_score": 8.5,
                "phase": "optimize",
                "tags": ["data", "streaming", "real-time"],
            },
        ],
        "process": [
            {
                "title": "Model Development Standard Operating Procedures",
                "description": (
                    "Define and publish SOPs for model development covering data "
                    "preparation, experiment design, code review, and handoff to "
                    "production. Reduces time-to-deploy by 40%."
                ),
                "effort_weeks": 3,
                "impact_score": 7.0,
                "phase": "quick_wins",
                "tags": ["process", "standards", "governance"],
            },
            {
                "title": "MLOps Pipeline Standardisation",
                "description": (
                    "Implement CI/CD for model development: automated unit tests, "
                    "integration tests, deployment gates, canary releases, and "
                    "one-click rollback. Target: models deployable in under 2 hours."
                ),
                "effort_weeks": 10,
                "impact_score": 9.0,
                "phase": "foundation",
                "tags": ["process", "mlops", "automation"],
            },
            {
                "title": "Model Monitoring and Drift Detection",
                "description": (
                    "Deploy production monitoring covering data drift, concept drift, "
                    "performance degradation, and business metric correlation. Implement "
                    "auto-retraining triggers with human-in-the-loop approval."
                ),
                "effort_weeks": 8,
                "impact_score": 8.5,
                "phase": "foundation",
                "tags": ["process", "monitoring", "mlops"],
            },
            {
                "title": "AI Experiment Tracking Platform",
                "description": (
                    "Deploy ML experiment tracking (MLflow, W&B) with automatic "
                    "hyperparameter logging, metric comparison dashboards, and "
                    "reproducibility verification for all model training runs."
                ),
                "effort_weeks": 6,
                "impact_score": 8.0,
                "phase": "foundation",
                "tags": ["process", "experiments", "mlops"],
            },
            {
                "title": "Continuous Model Improvement Loop",
                "description": (
                    "Establish automated human feedback collection, active learning "
                    "data selection, and scheduled retraining cycles. Target: "
                    "quarterly model refresh with measurable quality improvement."
                ),
                "effort_weeks": 18,
                "impact_score": 9.5,
                "phase": "optimize",
                "tags": ["process", "improvement", "feedback"],
            },
        ],
        "people": [
            {
                "title": "AI Literacy Workshop Series",
                "description": (
                    "Launch a structured 6-session AI literacy programme for all "
                    "business stakeholders. Covers AI fundamentals, use-case "
                    "identification, prompt engineering basics, and responsible AI."
                ),
                "effort_weeks": 4,
                "impact_score": 7.5,
                "phase": "quick_wins",
                "tags": ["people", "training", "literacy"],
            },
            {
                "title": "AI Champion Network",
                "description": (
                    "Identify and train 1-2 AI champions per business unit. Provide "
                    "advanced training on use-case discovery, ROI measurement, and "
                    "bridging technical and business teams."
                ),
                "effort_weeks": 6,
                "impact_score": 7.5,
                "phase": "quick_wins",
                "tags": ["people", "champions", "culture"],
            },
            {
                "title": "Data Science Hiring Plan",
                "description": (
                    "Define target team structure, competency profiles, and hiring "
                    "funnel for ML engineers, data scientists, and AI product managers. "
                    "Partner with HR to build pipelines for 6-month and 12-month goals."
                ),
                "effort_weeks": 8,
                "impact_score": 8.5,
                "phase": "foundation",
                "tags": ["people", "hiring", "talent"],
            },
            {
                "title": "AI Skills Upskilling Programme",
                "description": (
                    "Launch structured upskilling pathways (Python, ML fundamentals, "
                    "prompt engineering, MLOps) with internal certification milestones "
                    "and external learning platform subscriptions."
                ),
                "effort_weeks": 12,
                "impact_score": 8.0,
                "phase": "scale",
                "tags": ["people", "upskilling", "training"],
            },
            {
                "title": "AI Centre of Excellence",
                "description": (
                    "Establish a dedicated AI CoE with ML engineers, data scientists, "
                    "AI PMs, and an AI ethicist. Define operating model, funding, "
                    "and governance to drive enterprise-wide AI adoption at scale."
                ),
                "effort_weeks": 20,
                "impact_score": 9.5,
                "phase": "optimize",
                "tags": ["people", "coe", "strategy"],
            },
        ],
        "technology": [
            {
                "title": "AI Tool Inventory and Consolidation Plan",
                "description": (
                    "Audit all AI/ML tools currently in use across the organisation. "
                    "Identify redundancies, integration gaps, and consolidation "
                    "opportunities. Produce a target-state tool architecture."
                ),
                "effort_weeks": 3,
                "impact_score": 6.5,
                "phase": "quick_wins",
                "tags": ["technology", "inventory", "consolidation"],
            },
            {
                "title": "Unified ML Platform Deployment",
                "description": (
                    "Deploy a unified ML platform (AWS SageMaker, Azure ML, GCP Vertex) "
                    "with centralised experiment tracking, model registry, and serving "
                    "infrastructure. Retire fragmented point solutions."
                ),
                "effort_weeks": 14,
                "impact_score": 9.0,
                "phase": "foundation",
                "tags": ["technology", "platform", "mlops"],
            },
            {
                "title": "Vector Database and RAG Infrastructure",
                "description": (
                    "Deploy vector database infrastructure (Pinecone, Weaviate, pgvector) "
                    "to power retrieval-augmented generation for enterprise knowledge "
                    "bases. Establish indexing pipelines and query latency SLAs."
                ),
                "effort_weeks": 10,
                "impact_score": 8.5,
                "phase": "foundation",
                "tags": ["technology", "rag", "llm"],
            },
            {
                "title": "GPU Infrastructure Optimisation",
                "description": (
                    "Optimise GPU utilisation through intelligent scheduling, spot "
                    "instance strategies, and resource quotas. Implement cost "
                    "allocation tagging to reduce compute spend by 30-40%."
                ),
                "effort_weeks": 8,
                "impact_score": 8.0,
                "phase": "scale",
                "tags": ["technology", "gpu", "cost-optimisation"],
            },
            {
                "title": "Edge AI Deployment Capability",
                "description": (
                    "Build capability to deploy quantised models to edge devices for "
                    "low-latency inference without cloud dependency. Target use cases "
                    "requiring sub-100ms response times."
                ),
                "effort_weeks": 22,
                "impact_score": 8.0,
                "phase": "optimize",
                "tags": ["technology", "edge", "inference"],
            },
        ],
        "governance": [
            {
                "title": "AI Use Case Risk Classification Policy",
                "description": (
                    "Develop a risk classification policy (low/medium/high/critical) "
                    "for all AI use cases based on data sensitivity, decision impact, "
                    "and regulatory exposure. Publish and train all teams within 30 days."
                ),
                "effort_weeks": 4,
                "impact_score": 8.0,
                "phase": "quick_wins",
                "tags": ["governance", "risk", "policy"],
            },
            {
                "title": "AI Ethics and Responsible AI Framework",
                "description": (
                    "Define and publish an AI ethics policy covering fairness, "
                    "transparency, accountability, human oversight, and environmental "
                    "impact. Map to EU AI Act risk categories for regulatory readiness."
                ),
                "effort_weeks": 6,
                "impact_score": 8.5,
                "phase": "quick_wins",
                "tags": ["governance", "ethics", "responsible-ai"],
            },
            {
                "title": "AI Model Risk Register",
                "description": (
                    "Implement a structured AI risk register covering all production "
                    "models. Include quarterly impact assessments, owner assignment, "
                    "mitigation tracking, and executive reporting dashboards."
                ),
                "effort_weeks": 8,
                "impact_score": 8.5,
                "phase": "foundation",
                "tags": ["governance", "risk", "compliance"],
            },
            {
                "title": "AI Audit Trail and Explainability Programme",
                "description": (
                    "Implement model decision audit logging, SHAP-based explainability "
                    "reports for high-risk decisions, and a stakeholder-accessible "
                    "explanation portal for regulated use cases."
                ),
                "effort_weeks": 12,
                "impact_score": 8.5,
                "phase": "scale",
                "tags": ["governance", "explainability", "audit"],
            },
            {
                "title": "Continuous Compliance Monitoring System",
                "description": (
                    "Deploy automated compliance monitoring for GDPR, EU AI Act, HIPAA "
                    "(where applicable), and sector-specific regulations. Include "
                    "real-time alerting on policy drift and automated remediation triggers."
                ),
                "effort_weeks": 16,
                "impact_score": 9.0,
                "phase": "optimize",
                "tags": ["governance", "compliance", "automation"],
            },
        ],
    }
