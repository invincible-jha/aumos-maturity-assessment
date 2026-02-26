# Contributing to aumos-maturity-assessment

## Development Setup

```bash
git clone <repo>
cd aumos-maturity-assessment
pip install -e ".[dev]"
cp .env.example .env
make dev
```

## Contribution Guidelines

- Follow all coding standards in `CLAUDE.md`
- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- Tests required for new business logic (80% coverage target)
- Type hints on all function signatures
- Google-style docstrings on all public classes and functions

## Pull Request Process

1. Branch from `main`: `feature/`, `fix/`, `docs/`
2. Add tests for new functionality
3. Run `make lint typecheck test` before submitting
4. Squash-merge only (clean history)

## Domain Invariants (Do Not Bypass)

- Assessments require all 5 dimensions before scoring
- Pilots require ≥3 measurable success criteria
- Completed assessments are immutable (no rescoring)
- Benchmark comparison requires a completed assessment
