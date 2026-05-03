.PHONY: help install lint test unit integration e2e build dev-up dev-down deploy-aks clean

AGENT_DIR := services/agent
DASHBOARD_DIR := services/dashboard
CHAOS_UI_DIR := services/chaos-ui

help:
	@echo "SRE Agent Platform - development commands"
	@echo ""
	@echo "  install        Install all dependencies"
	@echo "  lint           Run linters (ruff, mypy, eslint)"
	@echo "  test           Run unit + integration tests"
	@echo "  unit           Run unit tests only (fast, domain-only)"
	@echo "  integration    Run integration tests (testcontainers)"
	@echo "  e2e            Run e2e against kind cluster"
	@echo "  build          Build all Docker images"
	@echo "  dev-up         Start local dev stack (docker-compose)"
	@echo "  dev-down       Stop local dev stack"
	@echo "  deploy-aks     Deploy to AKS via Helm"
	@echo "  clean          Remove caches and build artifacts"

install:
	cd $(AGENT_DIR) && python -m pip install -e ".[dev]"
	cd $(DASHBOARD_DIR) && npm install
	cd $(CHAOS_UI_DIR) && python -m pip install -r requirements.txt

lint:
	cd $(AGENT_DIR) && ruff check src tests && ruff format --check src tests && mypy src
	cd $(AGENT_DIR) && python -m lint_imports --config=.importlinter
	cd $(DASHBOARD_DIR) && npm run lint

test: unit integration

unit:
	cd $(AGENT_DIR) && pytest tests/unit -v --cov=src/sre_agent/domain --cov=src/sre_agent/application --cov-report=term-missing

integration:
	cd $(AGENT_DIR) && pytest tests/integration -v

e2e:
	cd $(AGENT_DIR) && pytest tests/e2e -v --timeout=300

build:
	docker build -t ghcr.io/sre-agent/agent:local $(AGENT_DIR)
	docker build -t ghcr.io/sre-agent/dashboard:local $(DASHBOARD_DIR)
	docker build -t ghcr.io/sre-agent/chaos-ui:local $(CHAOS_UI_DIR)

dev-up:
	docker compose -f docker-compose.dev.yml up -d
	@echo "Stack up. Agent: http://localhost:8000  Dashboard: http://localhost:3000  Chaos UI: http://localhost:8501"

dev-down:
	docker compose -f docker-compose.dev.yml down

deploy-aks:
	./scripts/deploy-aks.sh

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
