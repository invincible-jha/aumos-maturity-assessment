"""Service-specific settings extending AumOS base config.

All standard AumOS configuration is inherited from AumOSSettings.
Repo-specific settings use the AUMOS_MATURITY_ env prefix.
"""

from pydantic_settings import SettingsConfigDict

from aumos_common.config import AumOSSettings


class Settings(AumOSSettings):
    """Settings for aumos-maturity-assessment.

    Inherits all standard AumOS settings (database, kafka, keycloak, etc.)
    and adds maturity-assessment-specific configuration.

    Environment variable prefix: AUMOS_MATURITY_
    """

    service_name: str = "aumos-maturity-assessment"

    # Scoring configuration
    score_max_dimension: int = 100
    score_maturity_levels: int = 5

    # Benchmark configuration
    benchmark_cache_ttl_seconds: int = 3600
    benchmark_update_interval_days: int = 30

    # Roadmap generation
    roadmap_max_initiatives: int = 20
    roadmap_default_horizon_months: int = 18

    # Pilot accelerator
    pilot_target_success_rate: float = 0.12  # Address the 88% failure rate
    pilot_default_duration_weeks: int = 8

    # Report generation
    report_max_pages: int = 50
    report_include_benchmarks: bool = True

    # AI Readiness Assessment lead magnet (self-service, no auth)
    hubspot_api_key: str = ""
    assessment_benchmark_refresh_days: int = 30
    assessment_email_from: str = "assessments@aumos.ai"
    enable_assessment_lead_capture: bool = True

    # GAP-286: Configurable dimension system
    default_dimensions: list[str] = [
        "data",
        "process",
        "people",
        "technology",
        "governance",
    ]
    max_assessment_dimensions: int = 7

    # GAP-287: Benchmark enrichment
    benchmark_min_contribution_tenants: int = 30
    benchmark_confidence_tier_thresholds: dict = {
        "seed_estimate": 0,
        "preliminary": 30,
        "reliable": 100,
        "robust": 500,
    }

    # GAP-289: Change management integration
    change_mgmt_trigger_threshold: float = 50.0
    change_mgmt_integration_enabled: bool = True

    # GAP-291: Assessment progress
    progress_lookback_assessments: int = 5

    model_config = SettingsConfigDict(env_prefix="AUMOS_MATURITY_")
