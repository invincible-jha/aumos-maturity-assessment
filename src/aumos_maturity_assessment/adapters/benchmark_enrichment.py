"""Benchmark data enrichment adapter for the Maturity Assessment service.

Implements the quarterly benchmark enrichment process using opt-in tenant data.
Minimum 30 consenting tenants required before updating any benchmark segment to
ensure statistical significance and tenant privacy protection.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from aumos_common.observability import get_logger

logger = get_logger(__name__)

# Minimum consenting tenants required before enriching a benchmark segment
MIN_CONSENTING_TENANTS: int = 30

# Confidence tier thresholds by sample size
CONFIDENCE_TIERS: dict[str, tuple[int, int]] = {
    "seed_estimate": (0, 29),
    "preliminary": (30, 99),
    "reliable": (100, 499),
    "robust": (500, 999_999),
}


@dataclass
class EnrichmentResult:
    """Result of a benchmark enrichment run.

    Attributes:
        segments_evaluated: Number of benchmark segments checked.
        segments_updated: Number of segments with enough data to update.
        segments_skipped: Number of segments below the minimum tenant threshold.
        contributing_tenant_count: Total opt-in tenants in this enrichment run.
    """

    segments_evaluated: int
    segments_updated: int
    segments_skipped: int
    contributing_tenant_count: int


def _determine_confidence_tier(sample_size: int) -> str:
    """Map a sample size to a confidence tier label.

    Args:
        sample_size: Number of data points in the benchmark sample.

    Returns:
        Confidence tier string: seed_estimate | preliminary | reliable | robust.
    """
    for tier, (lower, upper) in CONFIDENCE_TIERS.items():
        if lower <= sample_size <= upper:
            return tier
    return "seed_estimate"


class BenchmarkEnrichmentService:
    """Quarterly benchmark enrichment using anonymized opt-in platform data.

    Aggregates maturity assessment scores from tenants that have explicitly
    consented to contribute their data to industry benchmarks. Requires a
    minimum of 30 consenting tenants per segment before updating.
    """

    def __init__(self, session: Any) -> None:
        """Initialise with an async SQLAlchemy session.

        Args:
            session: AsyncSession for database access.
        """
        self._session = session

    async def run_quarterly_enrichment(
        self,
        benchmark_period: str,
    ) -> EnrichmentResult:
        """Aggregate opt-in tenant data and update benchmark records.

        Iterates over all industry × size segments, aggregates completed
        assessment scores from consenting tenants, and updates the benchmark
        record only if the minimum tenant threshold is met.

        Args:
            benchmark_period: Benchmark period label (e.g. "2026-Q1").

        Returns:
            EnrichmentResult summarizing the enrichment run outcomes.
        """
        from sqlalchemy import text

        logger.info("benchmark_enrichment_starting", benchmark_period=benchmark_period)

        # Fetch all consenting tenant IDs
        consent_result = await self._session.execute(
            text(
                """
                SELECT tenant_id
                FROM mat_benchmark_contribution_consents
                WHERE consented = TRUE
                """
            )
        )
        consenting_tenant_ids = [str(row[0]) for row in consent_result.fetchall()]
        contributing_tenant_count = len(consenting_tenant_ids)

        logger.info(
            "benchmark_enrichment_consenting_tenants",
            count=contributing_tenant_count,
        )

        if contributing_tenant_count < MIN_CONSENTING_TENANTS:
            logger.warning(
                "benchmark_enrichment_insufficient_tenants",
                consenting_count=contributing_tenant_count,
                minimum_required=MIN_CONSENTING_TENANTS,
            )
            return EnrichmentResult(
                segments_evaluated=0,
                segments_updated=0,
                segments_skipped=0,
                contributing_tenant_count=contributing_tenant_count,
            )

        # Aggregate scores by industry × organization_size segment
        segments_result = await self._session.execute(
            text(
                """
                SELECT
                    a.industry,
                    a.organization_size,
                    COUNT(DISTINCT a.tenant_id) AS tenant_count,
                    AVG(a.overall_score) AS avg_overall,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY a.overall_score) AS p25,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY a.overall_score) AS p50,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY a.overall_score) AS p75,
                    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY a.overall_score) AS p90,
                    AVG(a.data_score) AS avg_data,
                    AVG(a.process_score) AS avg_process,
                    AVG(a.people_score) AS avg_people,
                    AVG(a.technology_score) AS avg_technology,
                    AVG(a.governance_score) AS avg_governance
                FROM mat_assessments a
                WHERE a.status = 'completed'
                  AND a.tenant_id = ANY(:tenant_ids)
                GROUP BY a.industry, a.organization_size
                HAVING COUNT(DISTINCT a.tenant_id) >= :min_tenants
                """
            ),
            {
                "tenant_ids": consenting_tenant_ids,
                "min_tenants": MIN_CONSENTING_TENANTS,
            },
        )
        rows = segments_result.fetchall()

        segments_evaluated = len(rows)
        segments_updated = 0

        for row in rows:
            industry, org_size, tenant_count = row[0], row[1], row[2]
            p25, p50, p75, p90 = row[4], row[5], row[6], row[7]
            confidence_tier = _determine_confidence_tier(int(tenant_count))

            await self._session.execute(
                text(
                    """
                    INSERT INTO mat_benchmarks (
                        id, tenant_id, industry, organization_size,
                        benchmark_period, sample_size, overall_p25, overall_p50,
                        overall_p75, overall_p90, data_p50, process_p50,
                        people_p50, technology_p50, governance_p50,
                        dimension_breakdowns, top_strengths, top_gaps,
                        data_source, confidence_tier, data_collected_at,
                        contributing_tenant_count, created_at, updated_at
                    ) VALUES (
                        gen_random_uuid(), '00000000-0000-0000-0000-000000000000',
                        :industry, :org_size, :benchmark_period,
                        :sample_size, :p25, :p50, :p75, :p90,
                        :data_p50, :process_p50, :people_p50, :technology_p50,
                        :governance_p50, :dimension_breakdowns, :top_strengths,
                        :top_gaps, :data_source, :confidence_tier,
                        :collected_at, :tenant_count, NOW(), NOW()
                    )
                    ON CONFLICT (industry, organization_size, benchmark_period)
                    DO UPDATE SET
                        sample_size = EXCLUDED.sample_size,
                        overall_p25 = EXCLUDED.overall_p25,
                        overall_p50 = EXCLUDED.overall_p50,
                        overall_p75 = EXCLUDED.overall_p75,
                        overall_p90 = EXCLUDED.overall_p90,
                        data_p50 = EXCLUDED.data_p50,
                        process_p50 = EXCLUDED.process_p50,
                        people_p50 = EXCLUDED.people_p50,
                        technology_p50 = EXCLUDED.technology_p50,
                        governance_p50 = EXCLUDED.governance_p50,
                        confidence_tier = EXCLUDED.confidence_tier,
                        contributing_tenant_count = EXCLUDED.contributing_tenant_count,
                        updated_at = NOW()
                    """
                ),
                {
                    "industry": industry,
                    "org_size": org_size,
                    "benchmark_period": benchmark_period,
                    "sample_size": int(tenant_count),
                    "p25": float(p25 or 0),
                    "p50": float(p50 or 0),
                    "p75": float(p75 or 0),
                    "p90": float(p90 or 0),
                    "data_p50": float(row[8] or 0),
                    "process_p50": float(row[9] or 0),
                    "people_p50": float(row[10] or 0),
                    "technology_p50": float(row[11] or 0),
                    "governance_p50": float(row[12] or 0),
                    "dimension_breakdowns": {},
                    "top_strengths": [],
                    "top_gaps": [],
                    "data_source": f"AumOS opt-in benchmark contribution ({benchmark_period})",
                    "confidence_tier": confidence_tier,
                    "collected_at": date.today().isoformat(),
                    "tenant_count": int(tenant_count),
                },
            )
            segments_updated += 1

        await self._session.commit()

        logger.info(
            "benchmark_enrichment_complete",
            benchmark_period=benchmark_period,
            segments_evaluated=segments_evaluated,
            segments_updated=segments_updated,
            contributing_tenants=contributing_tenant_count,
        )

        return EnrichmentResult(
            segments_evaluated=segments_evaluated,
            segments_updated=segments_updated,
            segments_skipped=segments_evaluated - segments_updated,
            contributing_tenant_count=contributing_tenant_count,
        )

    async def update_contribution_consent(
        self,
        tenant_id: uuid.UUID,
        consented: bool,
        consent_version: str,
    ) -> None:
        """Record or update a tenant's benchmark contribution consent.

        Args:
            tenant_id: Tenant UUID granting or revoking consent.
            consented: True to grant consent, False to revoke.
            consent_version: Version string of the consent agreement.
        """
        from sqlalchemy import text

        consented_at = datetime.now(timezone.utc).isoformat() if consented else None

        await self._session.execute(
            text(
                """
                INSERT INTO mat_benchmark_contribution_consents (
                    id, tenant_id, consented, consented_at, consent_version,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), :tenant_id, :consented,
                    :consented_at, :consent_version, NOW(), NOW()
                )
                ON CONFLICT (tenant_id) DO UPDATE SET
                    consented = EXCLUDED.consented,
                    consented_at = EXCLUDED.consented_at,
                    consent_version = EXCLUDED.consent_version,
                    updated_at = NOW()
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "consented": consented,
                "consented_at": consented_at,
                "consent_version": consent_version,
            },
        )
        await self._session.commit()

        logger.info(
            "benchmark_contribution_consent_updated",
            tenant_id=str(tenant_id),
            consented=consented,
            consent_version=consent_version,
        )
