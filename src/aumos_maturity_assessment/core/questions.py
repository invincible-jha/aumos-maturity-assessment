"""AI Readiness Assessment question bank.

Contains 50 diagnostic questions across 6 dimensions used by the self-service
lead magnet assessment. Each question has an ID, dimension, text, and a weight
coefficient. Weights within each dimension sum to approximately 1.0.

Dimensions:
    data_infrastructure    — data quality, pipelines, and accessibility
    governance             — AI policy, compliance, and oversight
    talent_culture         — AI literacy, skills, and organisational culture
    technology_stack       — AI tooling, compute, and platform readiness
    security_posture       — AI security, privacy, and risk management
    strategic_alignment    — AI strategy, leadership commitment, and vision
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AssessmentQuestion:
    """A single diagnostic question in the AI readiness assessment.

    Attributes:
        question_id: Unique identifier (e.g., 'DATA_01').
        dimension: Assessment dimension this question belongs to.
        text: The full question text presented to respondents.
        weight: Scoring weight within the dimension (dimension weights sum ~1.0).
    """

    question_id: str
    dimension: str
    text: str
    weight: float


QUESTION_BANK: list[AssessmentQuestion] = [
    # -----------------------------------------------------------------------
    # Dimension: data_infrastructure (9 questions, weights sum = 1.00)
    # -----------------------------------------------------------------------
    AssessmentQuestion(
        question_id="DATA_01",
        dimension="data_infrastructure",
        text=(
            "How would you rate the overall quality and completeness of the data "
            "assets available for AI and machine learning initiatives in your organisation?"
        ),
        weight=0.14,
    ),
    AssessmentQuestion(
        question_id="DATA_02",
        dimension="data_infrastructure",
        text=(
            "To what extent does your organisation maintain a centralised, searchable "
            "data catalogue with documented ownership, lineage, and sensitivity classification?"
        ),
        weight=0.12,
    ),
    AssessmentQuestion(
        question_id="DATA_03",
        dimension="data_infrastructure",
        text=(
            "How mature are your data pipelines in terms of automation, monitoring, "
            "and ability to deliver reliable, low-latency data to AI model training and serving?"
        ),
        weight=0.12,
    ),
    AssessmentQuestion(
        question_id="DATA_04",
        dimension="data_infrastructure",
        text=(
            "How well does your organisation manage data access controls, ensuring AI teams "
            "can access the data they need while maintaining appropriate privacy boundaries?"
        ),
        weight=0.11,
    ),
    AssessmentQuestion(
        question_id="DATA_05",
        dimension="data_infrastructure",
        text=(
            "To what degree does your organisation enforce data standardisation "
            "(schema, formats, naming conventions) across systems that feed AI workloads?"
        ),
        weight=0.11,
    ),
    AssessmentQuestion(
        question_id="DATA_06",
        dimension="data_infrastructure",
        text=(
            "How capable is your organisation at integrating data from multiple heterogeneous "
            "sources (structured, unstructured, streaming) to support diverse AI use cases?"
        ),
        weight=0.11,
    ),
    AssessmentQuestion(
        question_id="DATA_07",
        dimension="data_infrastructure",
        text=(
            "How effectively does your organisation manage historical data retention "
            "and versioning to support model reproducibility and audit requirements?"
        ),
        weight=0.10,
    ),
    AssessmentQuestion(
        question_id="DATA_08",
        dimension="data_infrastructure",
        text=(
            "To what extent does your organisation have dedicated feature engineering "
            "infrastructure or a feature store that enables reuse across AI projects?"
        ),
        weight=0.10,
    ),
    AssessmentQuestion(
        question_id="DATA_09",
        dimension="data_infrastructure",
        text=(
            "How well does your organisation monitor and alert on data drift, schema "
            "changes, and quality degradation in production AI systems?"
        ),
        weight=0.09,
    ),
    # -----------------------------------------------------------------------
    # Dimension: governance (8 questions, weights sum = 1.00)
    # -----------------------------------------------------------------------
    AssessmentQuestion(
        question_id="GOV_01",
        dimension="governance",
        text=(
            "Does your organisation have a formally documented AI ethics policy that "
            "covers fairness, transparency, accountability, and human oversight?"
        ),
        weight=0.16,
    ),
    AssessmentQuestion(
        question_id="GOV_02",
        dimension="governance",
        text=(
            "How mature is your organisation's AI risk management process, including "
            "a structured risk register, impact assessments, and regular review cycles?"
        ),
        weight=0.14,
    ),
    AssessmentQuestion(
        question_id="GOV_03",
        dimension="governance",
        text=(
            "To what extent does your organisation enforce compliance with relevant AI "
            "regulations and industry standards (e.g., GDPR, EU AI Act, sector-specific rules)?"
        ),
        weight=0.14,
    ),
    AssessmentQuestion(
        question_id="GOV_04",
        dimension="governance",
        text=(
            "How well defined are the roles, responsibilities, and decision rights "
            "around AI model development, approval, and deployment in your organisation?"
        ),
        weight=0.13,
    ),
    AssessmentQuestion(
        question_id="GOV_05",
        dimension="governance",
        text=(
            "Does your organisation maintain a comprehensive AI Bill of Materials (AI-BOM) "
            "tracking all AI models in production, their data provenance, and version history?"
        ),
        weight=0.13,
    ),
    AssessmentQuestion(
        question_id="GOV_06",
        dimension="governance",
        text=(
            "How effectively does your organisation conduct bias detection and fairness "
            "audits on AI models before and after deployment?"
        ),
        weight=0.11,
    ),
    AssessmentQuestion(
        question_id="GOV_07",
        dimension="governance",
        text=(
            "To what degree does your organisation have established processes for "
            "handling AI-related incidents, including escalation paths and post-mortems?"
        ),
        weight=0.10,
    ),
    AssessmentQuestion(
        question_id="GOV_08",
        dimension="governance",
        text=(
            "How well does your organisation ensure AI model explainability and "
            "interpretability for high-stakes decisions affecting customers or employees?"
        ),
        weight=0.09,
    ),
    # -----------------------------------------------------------------------
    # Dimension: talent_culture (9 questions, weights sum = 1.00)
    # -----------------------------------------------------------------------
    AssessmentQuestion(
        question_id="TAL_01",
        dimension="talent_culture",
        text=(
            "How would you rate the overall AI and data science literacy among business "
            "stakeholders and decision makers in your organisation?"
        ),
        weight=0.14,
    ),
    AssessmentQuestion(
        question_id="TAL_02",
        dimension="talent_culture",
        text=(
            "How adequate is your organisation's supply of specialised AI talent "
            "(data scientists, ML engineers, AI product managers) relative to your ambitions?"
        ),
        weight=0.13,
    ),
    AssessmentQuestion(
        question_id="TAL_03",
        dimension="talent_culture",
        text=(
            "To what extent does your organisation invest in structured upskilling "
            "and reskilling programmes to build AI capabilities in the existing workforce?"
        ),
        weight=0.12,
    ),
    AssessmentQuestion(
        question_id="TAL_04",
        dimension="talent_culture",
        text=(
            "How well does your organisation foster a culture of experimentation, "
            "learning from failure, and iterative improvement in AI initiatives?"
        ),
        weight=0.12,
    ),
    AssessmentQuestion(
        question_id="TAL_05",
        dimension="talent_culture",
        text=(
            "To what degree does leadership actively champion AI initiatives, "
            "participate in AI steering committees, and model data-driven decision making?"
        ),
        weight=0.12,
    ),
    AssessmentQuestion(
        question_id="TAL_06",
        dimension="talent_culture",
        text=(
            "How effective is cross-functional collaboration between AI/data teams "
            "and business units in defining, building, and deploying AI solutions?"
        ),
        weight=0.11,
    ),
    AssessmentQuestion(
        question_id="TAL_07",
        dimension="talent_culture",
        text=(
            "How well does your organisation manage the human-AI collaboration dynamic, "
            "including change management and employee trust in AI-assisted decisions?"
        ),
        weight=0.10,
    ),
    AssessmentQuestion(
        question_id="TAL_08",
        dimension="talent_culture",
        text=(
            "To what extent does your organisation have established communities of "
            "practice or internal networks for AI practitioners to share knowledge?"
        ),
        weight=0.08,
    ),
    AssessmentQuestion(
        question_id="TAL_09",
        dimension="talent_culture",
        text=(
            "How capable is your organisation at attracting and retaining top AI talent "
            "through compensation, culture, meaningful work, and growth opportunities?"
        ),
        weight=0.08,
    ),
    # -----------------------------------------------------------------------
    # Dimension: technology_stack (8 questions, weights sum = 1.00)
    # -----------------------------------------------------------------------
    AssessmentQuestion(
        question_id="TECH_01",
        dimension="technology_stack",
        text=(
            "How would you rate the maturity and completeness of your organisation's "
            "ML platform, including experiment tracking, model registry, and serving infrastructure?"
        ),
        weight=0.16,
    ),
    AssessmentQuestion(
        question_id="TECH_02",
        dimension="technology_stack",
        text=(
            "How adequate is your organisation's compute infrastructure (GPU/TPU availability, "
            "autoscaling, cloud hybrid strategy) for current and planned AI workloads?"
        ),
        weight=0.14,
    ),
    AssessmentQuestion(
        question_id="TECH_03",
        dimension="technology_stack",
        text=(
            "To what extent does your organisation have standardised MLOps tooling "
            "covering CI/CD for models, automated testing, and deployment pipelines?"
        ),
        weight=0.14,
    ),
    AssessmentQuestion(
        question_id="TECH_04",
        dimension="technology_stack",
        text=(
            "How well does your technology stack support LLM and generative AI workloads, "
            "including prompt management, context retrieval, and output evaluation?"
        ),
        weight=0.13,
    ),
    AssessmentQuestion(
        question_id="TECH_05",
        dimension="technology_stack",
        text=(
            "To what degree is your organisation's AI infrastructure observable, with "
            "comprehensive monitoring, alerting, and distributed tracing across the AI stack?"
        ),
        weight=0.12,
    ),
    AssessmentQuestion(
        question_id="TECH_06",
        dimension="technology_stack",
        text=(
            "How effectively does your organisation manage AI model versioning, "
            "A/B testing, and rollback capabilities in production environments?"
        ),
        weight=0.11,
    ),
    AssessmentQuestion(
        question_id="TECH_07",
        dimension="technology_stack",
        text=(
            "To what extent does your organisation optimise AI infrastructure costs "
            "through techniques such as spot instances, model quantisation, and caching?"
        ),
        weight=0.10,
    ),
    AssessmentQuestion(
        question_id="TECH_08",
        dimension="technology_stack",
        text=(
            "How well does your organisation's technology stack integrate with "
            "external AI services, APIs, and third-party model providers?"
        ),
        weight=0.10,
    ),
    # -----------------------------------------------------------------------
    # Dimension: security_posture (8 questions, weights sum = 1.00)
    # -----------------------------------------------------------------------
    AssessmentQuestion(
        question_id="SEC_01",
        dimension="security_posture",
        text=(
            "How comprehensively does your organisation assess and mitigate adversarial "
            "AI threats, including prompt injection, model poisoning, and data extraction attacks?"
        ),
        weight=0.15,
    ),
    AssessmentQuestion(
        question_id="SEC_02",
        dimension="security_posture",
        text=(
            "To what extent does your organisation apply privacy-preserving techniques "
            "(differential privacy, federated learning, data anonymisation) in AI development?"
        ),
        weight=0.14,
    ),
    AssessmentQuestion(
        question_id="SEC_03",
        dimension="security_posture",
        text=(
            "How robust is your organisation's access control and secrets management "
            "for AI model weights, training data, and API credentials?"
        ),
        weight=0.13,
    ),
    AssessmentQuestion(
        question_id="SEC_04",
        dimension="security_posture",
        text=(
            "How effectively does your organisation conduct security testing of AI systems, "
            "including red-teaming, vulnerability assessments, and penetration testing?"
        ),
        weight=0.13,
    ),
    AssessmentQuestion(
        question_id="SEC_05",
        dimension="security_posture",
        text=(
            "To what degree does your organisation monitor AI systems for anomalous "
            "behaviour, output manipulation, and unauthorised access in real time?"
        ),
        weight=0.12,
    ),
    AssessmentQuestion(
        question_id="SEC_06",
        dimension="security_posture",
        text=(
            "How well does your organisation manage supply chain security risks "
            "for third-party AI models, open-source packages, and external data sources?"
        ),
        weight=0.12,
    ),
    AssessmentQuestion(
        question_id="SEC_07",
        dimension="security_posture",
        text=(
            "To what extent does your organisation enforce output filtering and "
            "hallucination detection on AI-generated content before it reaches end users?"
        ),
        weight=0.11,
    ),
    AssessmentQuestion(
        question_id="SEC_08",
        dimension="security_posture",
        text=(
            "How mature is your organisation's incident response plan specifically "
            "for AI security events, including containment, recovery, and stakeholder notification?"
        ),
        weight=0.10,
    ),
    # -----------------------------------------------------------------------
    # Dimension: strategic_alignment (8 questions, weights sum = 1.00)
    # -----------------------------------------------------------------------
    AssessmentQuestion(
        question_id="STR_01",
        dimension="strategic_alignment",
        text=(
            "How clearly articulated and communicated is your organisation's AI strategy, "
            "including specific objectives, target use cases, and measurable outcomes?"
        ),
        weight=0.16,
    ),
    AssessmentQuestion(
        question_id="STR_02",
        dimension="strategic_alignment",
        text=(
            "To what extent are AI investments explicitly linked to measurable business "
            "value metrics such as revenue impact, cost reduction, or customer experience?"
        ),
        weight=0.14,
    ),
    AssessmentQuestion(
        question_id="STR_03",
        dimension="strategic_alignment",
        text=(
            "How well does your organisation prioritise AI use cases using a structured "
            "framework that considers feasibility, impact, and strategic fit?"
        ),
        weight=0.14,
    ),
    AssessmentQuestion(
        question_id="STR_04",
        dimension="strategic_alignment",
        text=(
            "To what degree does your organisation track and manage AI-related financial "
            "spend (FinOps), including model inference costs, compute allocation, and ROI?"
        ),
        weight=0.13,
    ),
    AssessmentQuestion(
        question_id="STR_05",
        dimension="strategic_alignment",
        text=(
            "How actively does your organisation scan for and evaluate emerging AI "
            "technologies and vendor offerings to maintain competitive positioning?"
        ),
        weight=0.12,
    ),
    AssessmentQuestion(
        question_id="STR_06",
        dimension="strategic_alignment",
        text=(
            "To what extent does your organisation have a clear build-versus-buy "
            "framework for AI capabilities, balancing proprietary and third-party solutions?"
        ),
        weight=0.11,
    ),
    AssessmentQuestion(
        question_id="STR_07",
        dimension="strategic_alignment",
        text=(
            "How well does your organisation manage shadow AI risks, including "
            "unsanctioned AI tool adoption and unvetted AI-generated content in workflows?"
        ),
        weight=0.10,
    ),
    AssessmentQuestion(
        question_id="STR_08",
        dimension="strategic_alignment",
        text=(
            "How effectively does your organisation engage with the external AI ecosystem "
            "(partners, academia, regulators) to shape standards and accelerate AI maturity?"
        ),
        weight=0.10,
    ),
]

# Convenience mappings for fast lookup
QUESTIONS_BY_ID: dict[str, AssessmentQuestion] = {q.question_id: q for q in QUESTION_BANK}

QUESTIONS_BY_DIMENSION: dict[str, list[AssessmentQuestion]] = {}
for _question in QUESTION_BANK:
    QUESTIONS_BY_DIMENSION.setdefault(_question.dimension, []).append(_question)

ALL_DIMENSIONS: list[str] = [
    "data_infrastructure",
    "governance",
    "talent_culture",
    "technology_stack",
    "security_posture",
    "strategic_alignment",
]
