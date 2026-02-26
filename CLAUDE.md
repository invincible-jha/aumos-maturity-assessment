# CLAUDE.md — AumOS Maturity Assessment

## Project Overview

AumOS Enterprise is a composable enterprise AI platform with 9 products + 2 services
across 62 repositories. This repo (`aumos-maturity-assessment`) is part of **Tier B: GTM / Sales Acceleration**:
the front door for every enterprise engagement, providing AI maturity diagnostics
that convert prospects to platform customers.

**Release Tier:** B: Open Core
**Product Mapping:** Product 8 — Enterprise Engagement Accelerator
**Phase:** 4 (Months 16-20)

## Repo Purpose

AI maturity entry-point diagnostic for enterprise clients. Delivers multi-dimensional
scoring across data, process, people, technology, and governance dimensions with
industry benchmark comparison, auto-roadmap generation, and a pilot accelerator
designed to address the 88% AI pilot failure rate.

## Architecture Position

```
aumos-platform-core → aumos-auth-gateway → THIS REPO → aumos-event-bus (publishes events)
aumos-governance-engine (governance scores)             ↘ aumos-data-layer (stores assessments)
aumos-model-registry (maturity of ML practice)         ↘ aumos-observability (metrics)
```

**Upstream dependencies (this repo IMPORTS from):**
- `aumos-common` — auth, database, events, errors, config, health, pagination
- `aumos-proto` — Protobuf message definitions for Kafka events

**Downstream dependents (other repos IMPORT from this):**
- `aumos-change-management` — receives assessment context for change planning
- `aumos-human-ai-collab` — uses maturity level to calibrate collaboration mode

## Tech Stack (DO NOT DEVIATE)

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.110+ | REST API framework |
| SQLAlchemy | 2.0+ (async) | Database ORM |
| asyncpg | 0.29+ | PostgreSQL async driver |
| Pydantic | 2.6+ | Data validation, settings, API schemas |
| confluent-kafka | 2.3+ | Kafka producer/consumer |
| structlog | 24.1+ | Structured JSON logging |
| OpenTelemetry | 1.23+ | Distributed tracing |
| pytest | 8.0+ | Testing framework |
| ruff | 0.3+ | Linting and formatting |
| mypy | 1.8+ | Type checking |

## Coding Standards

### ABSOLUTE RULES (violations will break integration with other repos)

1. **Import aumos-common, never reimplement.**
2. **Type hints on EVERY function.**
3. **Pydantic models for ALL API inputs/outputs.**
4. **RLS tenant isolation via aumos-common.**
5. **Structured logging via structlog.**
6. **Publish domain events to Kafka after state changes.**
7. **Async by default.**
8. **Google-style docstrings** on all public classes and functions.

### File Structure

```
src/aumos_maturity_assessment/
├── __init__.py
├── main.py                   # FastAPI app entry point
├── settings.py               # Extends AumOSSettings (AUMOS_MATURITY_ prefix)
├── api/
│   ├── router.py             # All endpoints under /api/v1/maturity/
│   └── schemas.py            # Pydantic request/response models
├── core/
│   ├── models.py             # SQLAlchemy ORM (mat_ prefix)
│   ├── services.py           # AssessmentService, BenchmarkService, RoadmapService,
│   │                         #   PilotService, ReportService
│   └── interfaces.py         # Protocol classes for all dependencies
├── adapters/
│   ├── repositories.py       # SQLAlchemy repos for all 6 models
│   ├── kafka.py              # MaturityEventPublisher
│   ├── scoring_engine.py     # Rule-based scoring (ScoringEngine)
│   ├── roadmap_generator.py  # Initiative generation (RoadmapGeneratorAdapter)
│   └── report_generator.py   # Report content assembly (ReportGeneratorAdapter)
└── migrations/
    └── versions/20240101_mat_initial_schema.py
```

## API Conventions

- All endpoints under `/api/v1/maturity/` prefix
- Auth: Bearer JWT token (validated by aumos-common)
- Tenant: `X-Tenant-ID` header

## API Surface

```
POST   /api/v1/maturity/assessments                    # Create assessment
GET    /api/v1/maturity/assessments                    # List assessments
GET    /api/v1/maturity/assessments/{id}               # Assessment results
POST   /api/v1/maturity/assessments/{id}/responses     # Submit responses
POST   /api/v1/maturity/assessments/{id}/score         # Compute scores
GET    /api/v1/maturity/assessments/{id}/score         # Detailed scoring
POST   /api/v1/maturity/benchmarks/compare             # Compare against industry
GET    /api/v1/maturity/benchmarks/{industry}          # Industry benchmarks
POST   /api/v1/maturity/roadmaps/generate              # Auto-generate roadmap
GET    /api/v1/maturity/roadmaps/{id}                  # Roadmap detail
POST   /api/v1/maturity/roadmaps/{id}/publish          # Publish roadmap
POST   /api/v1/maturity/pilots/design                  # Design pilot
GET    /api/v1/maturity/pilots/{id}                    # Pilot status
PUT    /api/v1/maturity/pilots/{id}/status             # Update pilot status
POST   /api/v1/maturity/pilots/{id}/execution-log      # Log weekly update
POST   /api/v1/maturity/reports/generate               # Generate executive report
GET    /api/v1/maturity/reports/{id}                   # Report detail
```

## Database Conventions

- Table prefix: `mat_` (e.g., `mat_assessments`)
- ALL tables extend `AumOSModel` (id, tenant_id, created_at, updated_at)
- RLS enabled on all tables via migration

## Maturity Scoring Model

### Five Dimensions
| Dimension  | Default Weight | What It Measures |
|------------|---------------|------------------|
| data       | 25%           | Quality, governance, infrastructure, accessibility |
| process    | 20%           | MLOps, deployment pipelines, automation maturity |
| people     | 20%           | AI literacy, talent density, upskilling |
| technology | 20%           | AI tooling, compute, infrastructure readiness |
| governance | 15%           | Ethics, compliance, risk management |

### Maturity Levels
| Level | Score Range | Label |
|-------|-------------|-------|
| 1     | 0-19        | Initial |
| 2     | 20-39       | Developing |
| 3     | 40-59       | Defined |
| 4     | 60-79       | Managed |
| 5     | 80-100      | Optimizing |

### Pilot Accelerator (88% Failure Rate Mitigation)
- Minimum 3 measurable success criteria enforced by PilotService
- Pre-identified failure modes with mitigation actions required
- Stakeholder mapping required before pilot approval
- Weekly execution log tracking with status/metrics/blockers

## Kafka Events Published

| Event Type | Topic | Trigger |
|------------|-------|---------|
| maturity.assessment.created | MATURITY_ASSESSMENT | Create assessment |
| maturity.assessment.completed | MATURITY_ASSESSMENT | Score computed |
| maturity.roadmap.generated | MATURITY_ROADMAP | Roadmap auto-generated |
| maturity.pilot.designed | MATURITY_PILOT | Pilot designed |
| maturity.pilot.status_changed | MATURITY_PILOT | Status transition |
| maturity.report.generated | MATURITY_REPORT | Report ready |

## Environment Variables

All vars use the `AUMOS_MATURITY_` prefix. See `.env.example` for full list.

## What Claude Code Should NOT Do

1. **Do NOT reimplement anything in aumos-common.**
2. **Do NOT bypass the 3 success criteria minimum for pilots** — this is a domain invariant.
3. **Do NOT allow scoring an in-progress assessment without all 5 dimensions.**
4. **Do NOT return raw dicts from API endpoints.**
5. **Do NOT write raw SQL.** Use SQLAlchemy ORM with BaseRepository.
6. **Do NOT skip type hints.**
7. **Do NOT put business logic in router.py** — it belongs in services.
