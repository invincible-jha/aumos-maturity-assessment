"""Roadmap mapping configuration for the AI Readiness Assessment lead magnet.

Maps each assessment dimension and score band (low/medium/high) to the AumOS
platform modules that address the identified capability gap. Used by the scoring
engine to generate tailored roadmap recommendations.

Score bands:
    low    — dimension score 0-39 (Initial to Developing)
    medium — dimension score 40-69 (Defined to approaching Managed)
    high   — dimension score 70-100 (Managed to Optimizing)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoadmapItem:
    """A single roadmap recommendation item.

    Attributes:
        module: AumOS platform module identifier.
        dimension: Assessment dimension this recommendation addresses.
        score_band: The score band that triggers this recommendation (low/medium/high).
        title: Human-readable initiative title.
        description: Brief explanation of how this module addresses the gap.
        priority: Suggested priority level (critical/high/medium/low).
        estimated_effort_weeks: Rough implementation effort estimate.
    """

    module: str
    dimension: str
    score_band: str
    title: str
    description: str
    priority: str
    estimated_effort_weeks: int


ROADMAP_MAPPINGS: dict[str, dict[str, list[str]]] = {
    "data_infrastructure": {
        "low": ["aumos-data-pipeline", "aumos-data-layer"],
        "medium": ["aumos-context-graph", "aumos-fidelity-validator"],
        "high": ["aumos-federated-learning", "aumos-privacy-engine"],
    },
    "governance": {
        "low": ["aumos-governance-engine", "aumos-maturity-assessment"],
        "medium": ["aumos-ai-bom", "aumos-approval-workflow"],
        "high": ["aumos-zero-knowledge-compliance", "aumos-stakeholder-consensus"],
    },
    "talent_culture": {
        "low": ["aumos-change-management", "aumos-human-ai-collab"],
        "medium": ["aumos-critical-thinking", "aumos-testing-harness"],
        "high": ["aumos-agent-framework", "aumos-llm-serving"],
    },
    "technology_stack": {
        "low": ["aumos-platform-core", "aumos-composable-installer"],
        "medium": ["aumos-mlops-lifecycle", "aumos-model-registry"],
        "high": ["aumos-llm-serving", "aumos-context-graph"],
    },
    "security_posture": {
        "low": ["aumos-security-runtime", "aumos-auth-gateway"],
        "medium": ["aumos-adversarial-immunity", "aumos-hallucination-shield"],
        "high": [
            "aumos-cryptographic-inference-escrow",
            "aumos-secrets-vault",
        ],
    },
    "strategic_alignment": {
        "low": ["aumos-maturity-assessment", "aumos-shadow-ai-toolkit"],
        "medium": ["aumos-vendor-intelligence", "aumos-ai-finops"],
        "high": ["aumos-b2b-agent-commerce", "aumos-marketplace"],
    },
}

# Detailed initiative templates per module
_MODULE_DETAILS: dict[str, dict[str, object]] = {
    "aumos-data-pipeline": {
        "title": "Automated Data Pipeline Deployment",
        "description": (
            "Deploy AumOS Data Pipeline to automate ingestion, transformation, and "
            "validation of enterprise data sources for AI model training and serving."
        ),
        "priority": "critical",
        "estimated_effort_weeks": 8,
    },
    "aumos-data-layer": {
        "title": "Unified Data Layer Implementation",
        "description": (
            "Implement a unified data layer that provides AI teams with governed, "
            "consistent access to enterprise data assets with lineage tracking."
        ),
        "priority": "critical",
        "estimated_effort_weeks": 12,
    },
    "aumos-context-graph": {
        "title": "Enterprise Context Graph Construction",
        "description": (
            "Build an enterprise knowledge graph enabling AI models to access rich "
            "contextual relationships across organisational data domains."
        ),
        "priority": "high",
        "estimated_effort_weeks": 14,
    },
    "aumos-fidelity-validator": {
        "title": "Data Fidelity Validation Framework",
        "description": (
            "Deploy automated fidelity validation to continuously monitor data "
            "quality, detect anomalies, and prevent degraded model performance."
        ),
        "priority": "high",
        "estimated_effort_weeks": 6,
    },
    "aumos-federated-learning": {
        "title": "Federated Learning Infrastructure",
        "description": (
            "Implement federated learning capabilities to train models across "
            "distributed data sources without centralising sensitive data."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 20,
    },
    "aumos-privacy-engine": {
        "title": "Privacy-Preserving AI Engine",
        "description": (
            "Deploy differential privacy and data anonymisation capabilities "
            "to enable AI development on sensitive data with regulatory compliance."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 16,
    },
    "aumos-governance-engine": {
        "title": "AI Governance Engine Deployment",
        "description": (
            "Establish a centralised AI governance engine managing policy enforcement, "
            "model approval workflows, and continuous compliance monitoring."
        ),
        "priority": "critical",
        "estimated_effort_weeks": 10,
    },
    "aumos-maturity-assessment": {
        "title": "Continuous Maturity Assessment Programme",
        "description": (
            "Run structured AI maturity assessments quarterly to track progress, "
            "identify emerging gaps, and recalibrate the AI roadmap accordingly."
        ),
        "priority": "high",
        "estimated_effort_weeks": 2,
    },
    "aumos-ai-bom": {
        "title": "AI Bill of Materials Implementation",
        "description": (
            "Deploy an AI-BOM system to maintain a complete inventory of AI models, "
            "training data, dependencies, and provenance for audit and compliance."
        ),
        "priority": "high",
        "estimated_effort_weeks": 8,
    },
    "aumos-approval-workflow": {
        "title": "AI Model Approval Workflow",
        "description": (
            "Implement structured approval workflows for AI model promotion through "
            "staging environments, with risk review and sign-off at each gate."
        ),
        "priority": "high",
        "estimated_effort_weeks": 6,
    },
    "aumos-zero-knowledge-compliance": {
        "title": "Zero-Knowledge Compliance Verification",
        "description": (
            "Adopt zero-knowledge proofs to verify model compliance properties "
            "without exposing proprietary training data or model internals."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 24,
    },
    "aumos-stakeholder-consensus": {
        "title": "AI Stakeholder Consensus Platform",
        "description": (
            "Deploy tools for structured AI governance deliberation, enabling "
            "diverse stakeholder input into high-stakes AI deployment decisions."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 10,
    },
    "aumos-change-management": {
        "title": "AI Change Management Programme",
        "description": (
            "Launch a structured change management programme to build AI awareness, "
            "address workforce concerns, and drive adoption across the organisation."
        ),
        "priority": "critical",
        "estimated_effort_weeks": 12,
    },
    "aumos-human-ai-collab": {
        "title": "Human-AI Collaboration Framework",
        "description": (
            "Deploy tools and protocols for effective human-AI task handoff, "
            "ensuring appropriate oversight and decision authority in AI-assisted workflows."
        ),
        "priority": "high",
        "estimated_effort_weeks": 8,
    },
    "aumos-critical-thinking": {
        "title": "AI Critical Thinking Upskilling",
        "description": (
            "Run structured programmes to develop critical thinking skills for "
            "evaluating AI outputs, challenging model assumptions, and detecting errors."
        ),
        "priority": "high",
        "estimated_effort_weeks": 6,
    },
    "aumos-testing-harness": {
        "title": "AI Testing Harness Deployment",
        "description": (
            "Implement a comprehensive testing harness for AI models covering "
            "unit tests, integration tests, behavioural tests, and regression suites."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 10,
    },
    "aumos-agent-framework": {
        "title": "Autonomous Agent Framework",
        "description": (
            "Deploy the AumOS agent framework to enable teams to build and operate "
            "autonomous AI agents with tool use, memory, and multi-step reasoning."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 20,
    },
    "aumos-llm-serving": {
        "title": "Enterprise LLM Serving Infrastructure",
        "description": (
            "Deploy scalable, cost-optimised LLM serving infrastructure with "
            "caching, load balancing, and provider abstraction for model switching."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 14,
    },
    "aumos-platform-core": {
        "title": "AumOS Platform Core Deployment",
        "description": (
            "Deploy the foundational AumOS platform core to provide a unified "
            "AI infrastructure layer across compute, storage, and model management."
        ),
        "priority": "critical",
        "estimated_effort_weeks": 16,
    },
    "aumos-composable-installer": {
        "title": "Composable Platform Installation",
        "description": (
            "Use the AumOS composable installer to selectively deploy only the "
            "platform components needed for current AI maturity stage and use cases."
        ),
        "priority": "high",
        "estimated_effort_weeks": 4,
    },
    "aumos-mlops-lifecycle": {
        "title": "MLOps Lifecycle Standardisation",
        "description": (
            "Standardise the full ML model lifecycle from development to retirement "
            "with automated CI/CD, testing gates, and deployment approvals."
        ),
        "priority": "high",
        "estimated_effort_weeks": 12,
    },
    "aumos-model-registry": {
        "title": "Enterprise Model Registry",
        "description": (
            "Deploy a centralised model registry to manage model versions, metadata, "
            "lineage, and deployment status across all AI workloads."
        ),
        "priority": "high",
        "estimated_effort_weeks": 8,
    },
    "aumos-security-runtime": {
        "title": "AI Security Runtime Protection",
        "description": (
            "Deploy runtime security monitoring for AI systems to detect anomalous "
            "inputs, adversarial prompts, and unauthorised access attempts in real time."
        ),
        "priority": "critical",
        "estimated_effort_weeks": 10,
    },
    "aumos-auth-gateway": {
        "title": "AI Authentication Gateway",
        "description": (
            "Implement a centralised authentication and authorisation gateway for "
            "all AI model APIs with fine-grained access control and audit logging."
        ),
        "priority": "critical",
        "estimated_effort_weeks": 8,
    },
    "aumos-adversarial-immunity": {
        "title": "Adversarial Robustness Programme",
        "description": (
            "Build adversarial immunity into AI systems through red-teaming, "
            "robustness testing, and adaptive defences against prompt injection attacks."
        ),
        "priority": "high",
        "estimated_effort_weeks": 16,
    },
    "aumos-hallucination-shield": {
        "title": "Hallucination Detection and Mitigation",
        "description": (
            "Deploy hallucination detection and output validation layers on "
            "all LLM-powered applications to prevent factual errors reaching end users."
        ),
        "priority": "high",
        "estimated_effort_weeks": 10,
    },
    "aumos-cryptographic-inference-escrow": {
        "title": "Cryptographic Inference Escrow",
        "description": (
            "Implement cryptographic escrow for AI inference to provide "
            "verifiable audit trails of model inputs and outputs for regulatory compliance."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 24,
    },
    "aumos-secrets-vault": {
        "title": "AI Secrets and Credentials Vault",
        "description": (
            "Deploy a dedicated secrets vault for AI system credentials, model weights, "
            "and API keys with automatic rotation and access logging."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 6,
    },
    "aumos-shadow-ai-toolkit": {
        "title": "Shadow AI Discovery and Governance",
        "description": (
            "Deploy the shadow AI toolkit to discover unsanctioned AI tool usage "
            "across the organisation and bring it under governance and security controls."
        ),
        "priority": "critical",
        "estimated_effort_weeks": 8,
    },
    "aumos-vendor-intelligence": {
        "title": "AI Vendor Intelligence Platform",
        "description": (
            "Implement vendor intelligence capabilities to evaluate, monitor, and "
            "compare AI vendors, models, and services against strategic requirements."
        ),
        "priority": "high",
        "estimated_effort_weeks": 10,
    },
    "aumos-ai-finops": {
        "title": "AI FinOps and Cost Management",
        "description": (
            "Deploy AI FinOps tooling to track, allocate, and optimise AI infrastructure "
            "spend with per-team cost visibility, budgets, and anomaly detection."
        ),
        "priority": "high",
        "estimated_effort_weeks": 8,
    },
    "aumos-b2b-agent-commerce": {
        "title": "B2B AI Agent Commerce Platform",
        "description": (
            "Leverage AumOS B2B agent commerce capabilities to deploy AI agents "
            "that can autonomously execute business transactions and workflows."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 24,
    },
    "aumos-marketplace": {
        "title": "Enterprise AI Marketplace",
        "description": (
            "Deploy the AumOS marketplace to create an internal catalogue of "
            "approved AI models, components, and accelerators available to all teams."
        ),
        "priority": "medium",
        "estimated_effort_weeks": 16,
    },
}


def get_score_band(score: float) -> str:
    """Determine the score band label for a dimension score.

    Args:
        score: Dimension score in the range 0-100.

    Returns:
        Score band string: 'low', 'medium', or 'high'.
    """
    if score < 40.0:
        return "low"
    if score < 70.0:
        return "medium"
    return "high"


def get_roadmap_items_for_dimension(
    dimension: str,
    score: float,
) -> list[RoadmapItem]:
    """Return RoadmapItem recommendations for a dimension at the given score.

    Args:
        dimension: Assessment dimension name.
        score: Computed dimension score (0-100).

    Returns:
        List of RoadmapItem recommendations for the dimension.

    Raises:
        ValueError: If dimension is not recognised.
    """
    if dimension not in ROADMAP_MAPPINGS:
        raise ValueError(f"Unknown dimension: {dimension!r}")

    score_band = get_score_band(score)
    module_ids = ROADMAP_MAPPINGS[dimension][score_band]

    items: list[RoadmapItem] = []
    for module_id in module_ids:
        details = _MODULE_DETAILS.get(module_id, {})
        items.append(
            RoadmapItem(
                module=module_id,
                dimension=dimension,
                score_band=score_band,
                title=str(details.get("title", module_id)),
                description=str(details.get("description", "")),
                priority=str(details.get("priority", "medium")),
                estimated_effort_weeks=int(details.get("estimated_effort_weeks", 8)),
            )
        )
    return items
