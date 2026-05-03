FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 sre

RUN pip install uv==0.5.4

WORKDIR /app

# Layer 1: CPU-only torch (~200 MB compressed instead of ~2 GB GPU build).
RUN uv pip install --system --index-url https://download.pytorch.org/whl/cpu \
    torch==2.4.1+cpu

# Layer 2: ML libs that depend on torch (split out to keep blobs small for pushes).
RUN uv pip install --system \
    sentence-transformers==3.2.1

# Layer 3: rest of the runtime deps. Splitting from app-code so dep churn doesn't invalidate.
RUN uv pip install --system \
    "fastapi==0.115.0" \
    "uvicorn[standard]==0.32.0" \
    "pydantic[email]==2.9.2" \
    "pydantic-settings==2.6.0" \
    "openai==1.54.3" \
    "langgraph==0.2.45" \
    "langgraph-checkpoint-postgres==2.0.1" \
    "langchain-core==0.3.15" \
    "langchain-openai==0.2.5" \
    "psycopg[binary,pool]==3.2.3" \
    "pgvector==0.3.6" \
    "sqlalchemy[asyncio]==2.0.35" \
    "asyncpg==0.30.0" \
    "alembic==1.13.3" \
    "redis==5.1.1" \
    "kubernetes==31.0.0" \
    "kubernetes-asyncio==31.1.1" \
    "prometheus-client==0.21.0" \
    "prometheus-api-client==0.5.5" \
    "structlog==24.4.0" \
    "opentelemetry-api==1.28.0" \
    "opentelemetry-sdk==1.28.0" \
    "opentelemetry-instrumentation-fastapi==0.49b0" \
    "opentelemetry-exporter-otlp==1.28.0" \
    "botbuilder-core==4.16.0" \
    "botbuilder-schema==4.16.0" \
    "botbuilder-integration-aiohttp==4.16.0" \
    "tenacity==9.0.0" \
    "pybreaker==1.2.0" \
    "httpx==0.27.2" \
    "pyyaml==6.0.2" \
    "python-dotenv==1.0.1" \
    "dependency-injector==4.42.0"

# Layer 4: app code (smallest, churns most often)
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system -e . --no-deps

USER sre

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "sre_agent.interface.rest.app:app", "--host", "0.0.0.0", "--port", "8000"]
