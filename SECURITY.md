# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

Report security vulnerabilities to security@aumos.ai. Do not open public issues
for security vulnerabilities. We respond within 48 hours and aim to patch
critical issues within 7 days.

## Security Controls

- All endpoints require valid JWT Bearer token (aumos-common auth)
- RLS enforced on all database tables (tenant isolation)
- No secrets in code — Pydantic settings with env vars only
- Parameterized queries only via SQLAlchemy ORM
- Input validation on all API boundaries via Pydantic
