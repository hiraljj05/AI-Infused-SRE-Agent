# sre-agent

The agent backend. Python 3.12, FastAPI, LangGraph.

## Layers

- `src/sre_agent/domain/` — entities, value objects, ports. Zero infra imports.
- `src/sre_agent/application/` — use cases, LangGraph state machine, HIL saga.
- `src/sre_agent/infrastructure/` — adapters implementing ports (OpenRouter, Qdrant, K8s, ...).
- `src/sre_agent/interface/` — REST API, Teams bot, webhook handlers.

Boundaries are enforced by `import-linter` (see `.importlinter`).

## Dev loop

```
pip install -e ".[dev]"
pytest tests/unit -v
ruff check src tests
mypy src
python -m lint_imports --config=.importlinter
uvicorn sre_agent.interface.rest.app:app --reload
```
