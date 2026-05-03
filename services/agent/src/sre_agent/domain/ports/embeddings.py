from __future__ import annotations

from typing import Protocol


class EmbeddingsPort(Protocol):
    @property
    def dimension(self) -> int:
        ...

    async def embed_one(self, text: str) -> list[float]:
        ...

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        ...
