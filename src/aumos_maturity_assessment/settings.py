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

    model_config = SettingsConfigDict(env_prefix="AUMOS_MATURITY_")
