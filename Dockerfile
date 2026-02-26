FROM python:3.11-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source
COPY src/ src/
COPY tests/ tests/

FROM base AS production
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "aumos_maturity_assessment.main:app", "--host", "0.0.0.0", "--port", "8000"]
