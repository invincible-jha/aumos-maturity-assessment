.PHONY: install dev lint typecheck test test-cov migrate run clean

install:
	pip install -e ".[dev]"

dev:
	docker-compose -f docker-compose.dev.yml up

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

typecheck:
	mypy src/

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=aumos_maturity_assessment --cov-report=html --cov-report=term-missing

migrate:
	alembic -c src/aumos_maturity_assessment/migrations/alembic.ini upgrade head

migrate-down:
	alembic -c src/aumos_maturity_assessment/migrations/alembic.ini downgrade -1

run:
	uvicorn aumos_maturity_assessment.main:app --host 0.0.0.0 --port 8000 --reload

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ dist/ build/
