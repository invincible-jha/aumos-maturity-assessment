"""Seed data for the agentic AI maturity dimension.

Provides the seed data for the mat_dimension_configs table, including
the new agentic_ai dimension aligned to Gartner's Agentic AI Maturity
Framework (2025), plus updated weights for the existing five dimensions
when six dimensions are selected.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Agentic AI dimension seed data (Gartner Agentic AI Maturity Framework 2025)
# ---------------------------------------------------------------------------

AGENTIC_AI_DIMENSION: dict = {
    "id": "agentic_ai",
    "display_name": "Agentic AI Readiness",
    "description": (
        "Organizational readiness for autonomous AI agent deployment, "
        "covering orchestration patterns, oversight mechanisms, security posture, "
        "and governance frameworks for agentic AI workflows."
    ),
    "default_weight": 0.15,
    "introduced_in_version": "1.1",
    "framework_alignment": "Gartner Agentic AI Maturity Framework 2025",
    "is_active": True,
    "question_bank": [
        {
            "id": "agent_arch_readiness",
            "text": "Does your organization have defined orchestration patterns for multi-agent workflows?",
            "scoring_guidance": "0-20: No concept. 40-60: Piloting single-agent. 80-100: Standardized multi-agent.",
        },
        {
            "id": "agent_oversight_capability",
            "text": "Are there defined human intervention points for each autonomous agent workflow?",
            "scoring_guidance": "0-20: No oversight plan. 40-60: Ad-hoc. 80-100: Systematic HITL checkpoints.",
        },
        {
            "id": "agent_security_posture",
            "text": "Has your organization assessed and mitigated prompt injection and agent hijacking risks?",
            "scoring_guidance": "0-20: No assessment. 40-60: Informal review. 80-100: Formal threat model applied.",
        },
        {
            "id": "agent_workflow_governance",
            "text": "Are agentic AI workflows subject to formal governance review before deployment?",
            "scoring_guidance": "0-20: No governance. 40-60: Case-by-case review. 80-100: Standardized approval process.",
        },
        {
            "id": "agent_observability",
            "text": "Do you have tooling to trace, audit, and replay the decision chains of deployed agents?",
            "scoring_guidance": "0-20: No observability. 40-60: Partial logging. 80-100: Full trace and replay capability.",
        },
    ],
}

# ---------------------------------------------------------------------------
# Auto-rebalanced weights when all 6 dimensions are selected
# ---------------------------------------------------------------------------

SIX_DIMENSION_WEIGHTS: dict[str, float] = {
    "data": 0.22,
    "process": 0.18,
    "people": 0.18,
    "technology": 0.18,
    "governance": 0.14,
    "agentic_ai": 0.10,
}

# ---------------------------------------------------------------------------
# Seven-dimension weights (culture + strategy added per Gartner 7-dim model)
# ---------------------------------------------------------------------------

SEVEN_DIMENSION_WEIGHTS: dict[str, float] = {
    "data": 0.18,
    "process": 0.15,
    "people": 0.15,
    "technology": 0.15,
    "governance": 0.12,
    "culture": 0.13,
    "strategy": 0.12,
}

# ---------------------------------------------------------------------------
# Culture and Strategy dimension seed data (Gartner 7-dimension model)
# ---------------------------------------------------------------------------

CULTURE_DIMENSION: dict = {
    "id": "culture",
    "display_name": "AI Culture & Ethics",
    "description": (
        "Organizational culture around AI adoption, including leadership AI literacy, "
        "ethical AI principles, and employee sentiment toward AI-enabled work."
    ),
    "default_weight": 0.13,
    "introduced_in_version": "1.2",
    "framework_alignment": "Gartner AI Maturity Model 7-Dimension Extension 2025",
    "is_active": True,
    "question_bank": [
        {
            "id": "leadership_ai_literacy",
            "text": "Do C-suite and board members have baseline AI literacy to make informed AI investment decisions?",
            "scoring_guidance": "0-20: No literacy. 40-60: Some training attended. 80-100: Certified or externally validated.",
        },
        {
            "id": "ai_ethics_policy",
            "text": "Does the organization have a published AI ethics policy covering fairness, transparency, and accountability?",
            "scoring_guidance": "0-20: No policy. 40-60: Draft policy in review. 80-100: Published and operationalized.",
        },
        {
            "id": "employee_ai_acceptance",
            "text": "What is the measured level of employee acceptance and engagement with AI-assisted tools?",
            "scoring_guidance": "0-20: Active resistance. 40-60: Neutral/cautious adoption. 80-100: Enthusiastic adoption.",
        },
        {
            "id": "ai_experimentation_culture",
            "text": "Does the organization provide safe-to-fail environments for AI experimentation?",
            "scoring_guidance": "0-20: No sandbox. 40-60: Ad-hoc sandbox. 80-100: Formal innovation lab.",
        },
        {
            "id": "ai_change_readiness",
            "text": "Has change management planning been completed for AI-related role changes?",
            "scoring_guidance": "0-20: No planning. 40-60: Partial planning. 80-100: Full change management plan executed.",
        },
    ],
}

STRATEGY_DIMENSION: dict = {
    "id": "strategy",
    "display_name": "AI Strategy & Competitive Positioning",
    "description": (
        "Alignment between AI investments and business strategy, including competitive "
        "differentiation, board-level AI strategy ownership, and value realization tracking."
    ),
    "default_weight": 0.12,
    "introduced_in_version": "1.2",
    "framework_alignment": "Gartner AI Maturity Model 7-Dimension Extension 2025",
    "is_active": True,
    "question_bank": [
        {
            "id": "ai_strategy_alignment",
            "text": "Is the AI strategy formally aligned to and approved by the board-level business strategy?",
            "scoring_guidance": "0-20: No alignment. 40-60: Informal alignment. 80-100: Board-approved roadmap.",
        },
        {
            "id": "competitive_ai_positioning",
            "text": "Has the organization benchmarked its AI maturity against direct competitors?",
            "scoring_guidance": "0-20: No benchmarking. 40-60: Informal comparison. 80-100: Formal external assessment.",
        },
        {
            "id": "ai_value_tracking",
            "text": "Are AI initiative ROI metrics tracked and reported to senior leadership quarterly?",
            "scoring_guidance": "0-20: No tracking. 40-60: Ad-hoc tracking. 80-100: Formal dashboard with OKRs.",
        },
        {
            "id": "ai_portfolio_management",
            "text": "Does the organization maintain a centralized AI use-case portfolio with prioritization criteria?",
            "scoring_guidance": "0-20: No portfolio. 40-60: Informal list. 80-100: Governed portfolio with ROI gates.",
        },
        {
            "id": "ai_investment_governance",
            "text": "Are AI investments subject to a formal business case process with defined exit criteria?",
            "scoring_guidance": "0-20: No process. 40-60: Informal review. 80-100: Stage-gated investment governance.",
        },
    ],
}


def rebalance_weights(
    selected_dimensions: list[str],
    custom_weights: dict[str, float] | None = None,
) -> dict[str, float]:
    """Compute dimension weights for a given set of selected dimensions.

    If custom_weights are provided, validates they sum to 1.0 and returns them.
    Otherwise applies standard rebalancing rules:
    - 5 dimensions: original default weights
    - 6 dimensions (adds agentic_ai): SIX_DIMENSION_WEIGHTS
    - 7 dimensions (adds culture + strategy): SEVEN_DIMENSION_WEIGHTS
    - Other combinations: proportional rebalancing from defaults

    Args:
        selected_dimensions: List of dimension IDs to include.
        custom_weights: Optional explicit weights per dimension.

    Returns:
        Dict mapping dimension ID to weight (sum == 1.0).

    Raises:
        ValueError: If custom_weights do not sum to 1.0 (±0.001 tolerance).
    """
    if custom_weights is not None:
        total = sum(custom_weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Custom dimension weights must sum to 1.0, got {total:.4f}"
            )
        return custom_weights

    dim_set = set(selected_dimensions)

    # Exact preset matches
    if dim_set == {"data", "process", "people", "technology", "governance", "agentic_ai"}:
        return {k: v for k, v in SIX_DIMENSION_WEIGHTS.items() if k in dim_set}

    if dim_set == {
        "data", "process", "people", "technology", "governance", "culture", "strategy"
    }:
        return {k: v for k, v in SEVEN_DIMENSION_WEIGHTS.items() if k in dim_set}

    # Default weights for each known dimension
    _defaults: dict[str, float] = {
        "data": 0.25,
        "process": 0.20,
        "people": 0.20,
        "technology": 0.20,
        "governance": 0.15,
        "agentic_ai": 0.15,
        "culture": 0.13,
        "strategy": 0.12,
    }

    # Collect raw weights for selected dimensions then normalize
    raw = {dim: _defaults.get(dim, 0.10) for dim in selected_dimensions}
    total = sum(raw.values())
    return {dim: round(w / total, 4) for dim, w in raw.items()}
