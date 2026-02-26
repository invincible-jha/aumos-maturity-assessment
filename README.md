# aumos-maturity-assessment

AI maturity entry-point diagnostic — the front door for every AumOS enterprise engagement.

## Overview

The Maturity Assessment service provides multi-dimensional AI maturity scoring, industry
benchmark comparison, auto-roadmap generation, and a structured pilot accelerator designed
to address the 88% AI pilot failure rate observed across enterprise AI programmes.

### Five Assessment Dimensions

| Dimension  | Weight | Measures |
|------------|--------|----------|
| Data       | 25%    | Quality, governance, infrastructure, accessibility |
| Process    | 20%    | MLOps maturity, deployment pipelines, automation |
| People     | 20%    | AI literacy, talent density, upskilling investment |
| Technology | 20%    | AI tooling, compute, infrastructure readiness |
| Governance | 15%    | Ethics policy, compliance, risk management |

### Maturity Levels

| Level | Range | Label |
|-------|-------|-------|
| 1 | 0-19 | Initial |
| 2 | 20-39 | Developing |
| 3 | 40-59 | Defined |
| 4 | 60-79 | Managed |
| 5 | 80-100 | Optimizing |

## API Surface

```
POST   /api/v1/maturity/assessments                  Create assessment
GET    /api/v1/maturity/assessments                  List assessments
GET    /api/v1/maturity/assessments/{id}             Assessment results
POST   /api/v1/maturity/assessments/{id}/responses   Submit responses
POST   /api/v1/maturity/assessments/{id}/score       Compute scores
GET    /api/v1/maturity/assessments/{id}/score       Detailed scoring
POST   /api/v1/maturity/benchmarks/compare           Peer comparison
GET    /api/v1/maturity/benchmarks/{industry}        Industry benchmarks
POST   /api/v1/maturity/roadmaps/generate            Auto-generate roadmap
GET    /api/v1/maturity/roadmaps/{id}                Roadmap detail
POST   /api/v1/maturity/roadmaps/{id}/publish        Publish roadmap
POST   /api/v1/maturity/pilots/design                Design pilot
GET    /api/v1/maturity/pilots/{id}                  Pilot status
PUT    /api/v1/maturity/pilots/{id}/status           Update pilot status
POST   /api/v1/maturity/pilots/{id}/execution-log    Log weekly update
POST   /api/v1/maturity/reports/generate             Generate report
GET    /api/v1/maturity/reports/{id}                 Report detail
```

## Local Development

```bash
# Install dependencies
make install

# Start all services
make dev

# Run tests
make test

# Lint and format
make lint

# Type check
make typecheck

# Apply migrations
make migrate
```

## Architecture

Hexagonal architecture — business logic in `core/` is fully decoupled from FastAPI
and SQLAlchemy. All external dependencies (DB, Kafka, report generators) are injected
via interfaces defined in `core/interfaces.py`.

```
api/         → Thin FastAPI routes, Pydantic schemas
core/        → Business logic, SQLAlchemy models, Protocol interfaces
adapters/    → Repos, Kafka publisher, scoring engine, generators
migrations/  → Alembic schema migrations
```

## Database Tables

| Table | Purpose |
|-------|---------|
| `mat_assessments` | Assessment instances with multi-dimensional scores |
| `mat_assessment_responses` | Individual question responses |
| `mat_benchmarks` | Industry benchmark data |
| `mat_roadmaps` | Auto-generated adoption roadmaps |
| `mat_pilots` | Pilot designs and execution tracking |
| `mat_reports` | Generated executive reports |

All tables have RLS enabled for tenant isolation.

## License

Apache 2.0 — see [LICENSE](LICENSE)
