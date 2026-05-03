from __future__ import annotations

from fastapi import Request

from sre_agent.composition_root import Container


def get_container(request: Request) -> Container:
    container: Container | None = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("Container not initialised on app.state")
    return container
