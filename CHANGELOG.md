# Changelog

All notable changes to aumos-maturity-assessment will be documented here.

## [Unreleased]

## [0.1.0] — 2024-01-01

### Added
- Initial implementation of maturity assessment service
- Multi-dimensional scoring: data, process, people, technology, governance
- Industry benchmark comparison with percentile ranking
- Auto-roadmap generation from assessment scores
- Pilot accelerator with structured success criteria enforcement
- Executive report generation
- Six DB tables: mat_assessments, mat_assessment_responses, mat_benchmarks,
  mat_roadmaps, mat_pilots, mat_reports
- Full API surface: 16 endpoints under /api/v1/maturity/
- RLS tenant isolation on all tables
- Kafka event publishing for all state changes
- Rule-based scoring engine with 1-5 maturity level thresholds
- Rule-based roadmap generator with initiative templates per dimension
