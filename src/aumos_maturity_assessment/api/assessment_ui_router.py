"""Self-Assessment Questionnaire UI router (GAP-288).

Provides a multi-step guided wizard interface for business leaders to
complete AI maturity assessments without writing JSON API requests.

Routes are HTML responses using Jinja2 templates with an embedded
Chart.js radar chart for score visualization.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aumos_common.auth import get_current_tenant
from aumos_common.observability import get_logger

logger = get_logger(__name__)

assessment_ui_router = APIRouter(
    prefix="/maturity-ui",
    tags=["assessment-ui"],
)

# Templates are expected at src/aumos_maturity_assessment/templates/
# This is a relative import path — the actual Jinja2Templates instance
# must be configured in main.py with the correct absolute path.
_templates: Jinja2Templates | None = None


def set_templates(templates: Jinja2Templates) -> None:
    """Register the Jinja2Templates instance from the application factory.

    Must be called during application startup before any UI routes are served.

    Args:
        templates: Configured Jinja2Templates instance.
    """
    global _templates  # noqa: PLW0603
    _templates = templates


def _get_templates() -> Jinja2Templates:
    """Retrieve the configured templates instance.

    Returns:
        Jinja2Templates instance.

    Raises:
        RuntimeError: If templates have not been configured via set_templates().
    """
    if _templates is None:
        raise RuntimeError(
            "Jinja2 templates not configured. Call set_templates() during app startup."
        )
    return _templates


# ---------------------------------------------------------------------------
# Wizard step definitions
# ---------------------------------------------------------------------------

_WIZARD_STEPS: list[dict[str, Any]] = [
    {"step": 0, "title": "Welcome", "description": "Profile selection (industry, company size)"},
    {"step": 1, "title": "Data", "description": "Data quality, governance, and infrastructure"},
    {"step": 2, "title": "Process", "description": "MLOps, deployment pipelines, automation"},
    {"step": 3, "title": "People", "description": "AI literacy, talent density, upskilling"},
    {"step": 4, "title": "Technology", "description": "AI tooling, compute, infrastructure"},
    {"step": 5, "title": "Governance", "description": "Ethics, compliance, risk management"},
    {"step": 6, "title": "Results", "description": "Scores, benchmark comparison, roadmap preview"},
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@assessment_ui_router.get("/", response_class=HTMLResponse)
async def wizard_start(
    request: Request,
) -> HTMLResponse:
    """Step 0: Welcome page and profile selection.

    Renders the wizard entry page where users select their industry
    and company size before the assessment begins.

    Args:
        request: FastAPI request object.

    Returns:
        HTML response with the wizard start page.
    """
    templates = _get_templates()
    logger.info("assessment_wizard_started")
    return templates.TemplateResponse(
        "assessment/wizard_start.html",
        {
            "request": request,
            "steps": _WIZARD_STEPS,
            "current_step": 0,
            "industries": [
                "financial_services",
                "healthcare",
                "manufacturing",
                "retail",
                "technology",
                "government",
                "other",
            ],
            "organization_sizes": [
                "startup",
                "smb",
                "mid_market",
                "enterprise",
                "large_enterprise",
            ],
        },
    )


@assessment_ui_router.get("/step/{step}", response_class=HTMLResponse)
async def wizard_step(
    request: Request,
    step: int,
    assessment_id: uuid.UUID,
    tenant_id: str = Depends(get_current_tenant),
) -> HTMLResponse:
    """Steps 1-5: Dimension-by-dimension response collection.

    Renders a question form for the current dimension step.
    Each step corresponds to one maturity dimension.

    Args:
        request: FastAPI request object.
        step: Wizard step number (1-5).
        assessment_id: UUID of the assessment in progress.
        tenant_id: Current tenant identifier from auth middleware.

    Returns:
        HTML response with the dimension question form.
    """
    templates = _get_templates()
    if step < 1 or step > 5:
        return templates.TemplateResponse(
            "assessment/wizard_error.html",
            {
                "request": request,
                "error": f"Invalid wizard step: {step}. Steps must be 1-5.",
            },
            status_code=400,
        )

    step_config = _WIZARD_STEPS[step]
    logger.info(
        "assessment_wizard_step_viewed",
        step=step,
        assessment_id=str(assessment_id),
        tenant_id=str(tenant_id),
    )
    return templates.TemplateResponse(
        "assessment/wizard_step.html",
        {
            "request": request,
            "steps": _WIZARD_STEPS,
            "current_step": step,
            "step_config": step_config,
            "assessment_id": str(assessment_id),
            "next_step": step + 1 if step < 5 else None,
            "prev_step": step - 1 if step > 1 else 0,
        },
    )


@assessment_ui_router.post("/step/{step}/submit", response_class=HTMLResponse)
async def wizard_step_submit(
    request: Request,
    step: int,
    assessment_id: uuid.UUID,
    tenant_id: str = Depends(get_current_tenant),
) -> HTMLResponse:
    """Submit responses for one dimension and advance to next step.

    Processes the form data from a dimension step and redirects to the
    next wizard step (or results page after step 5).

    Args:
        request: FastAPI request object.
        step: Current wizard step number (1-5).
        assessment_id: UUID of the assessment in progress.
        tenant_id: Current tenant identifier from auth middleware.

    Returns:
        HTML redirect to next step or results page.
    """
    from fastapi.responses import RedirectResponse

    templates = _get_templates()
    form_data = await request.form()
    logger.info(
        "assessment_wizard_step_submitted",
        step=step,
        assessment_id=str(assessment_id),
        tenant_id=str(tenant_id),
        response_count=len(form_data),
    )

    # After step 5, redirect to results
    if step >= 5:
        return RedirectResponse(
            url=f"/maturity-ui/results/{assessment_id}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/maturity-ui/step/{step + 1}?assessment_id={assessment_id}",
        status_code=303,
    )


@assessment_ui_router.get("/results/{assessment_id}", response_class=HTMLResponse)
async def wizard_results(
    request: Request,
    assessment_id: uuid.UUID,
    tenant_id: str = Depends(get_current_tenant),
) -> HTMLResponse:
    """Results page: radar chart, benchmark comparison, roadmap preview.

    Renders the final assessment results with:
    - Dimension score radar chart (Chart.js)
    - Benchmark comparison bar chart
    - Top 3 quick-win recommendations
    - Roadmap preview and download link

    Args:
        request: FastAPI request object.
        assessment_id: UUID of the completed assessment.
        tenant_id: Current tenant identifier from auth middleware.

    Returns:
        HTML response with the assessment results dashboard.
    """
    templates = _get_templates()
    logger.info(
        "assessment_wizard_results_viewed",
        assessment_id=str(assessment_id),
        tenant_id=str(tenant_id),
    )
    # Placeholder data — the actual implementation wires up AssessmentService
    # and BenchmarkService to populate real scores before template rendering.
    return templates.TemplateResponse(
        "assessment/wizard_results.html",
        {
            "request": request,
            "assessment_id": str(assessment_id),
            "dimension_names": ["Data", "Process", "People", "Technology", "Governance"],
            "dimension_scores": [0.0, 0.0, 0.0, 0.0, 0.0],
            "benchmark_scores": [50.0, 50.0, 50.0, 50.0, 50.0],
            "overall_score": 0.0,
            "maturity_level": 1,
            "maturity_label": "Initial",
            "quick_wins": [],
        },
    )
