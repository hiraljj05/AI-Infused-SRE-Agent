from __future__ import annotations

import asyncio
from typing import Any

from sre_agent.domain.ports.embeddings import EmbeddingsPort


class SentenceTransformersEmbeddingsAdapter(EmbeddingsPort):
    """Local CPU embedding model (sentence-transformers/all-MiniLM-L6-v2 by default).

    Model loading is deferred until first use. Inference is offloaded to a thread to
    keep the event loop responsive.
    """

    def __init__(self, *, model_name: str, expected_dim: int = 384) -> None:
        self._model_name = model_name
        self._expected_dim = expected_dim
        self._model: Any | None = None
        self._load_lock = asyncio.Lock()

    @property
    def dimension(self) -> int:
        return self._expected_dim

    async def embed_one(self, text: str) -> list[float]:
        vecs = await self.embed_many([text])
        return vecs[0]

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        await self._ensure_loaded()

        def _encode() -> list[list[float]]:
            assert self._model is not None
            arr = self._model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return [v.tolist() for v in arr]

        return await asyncio.to_thread(_encode)

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        async with self._load_lock:
            if self._model is not None:
                return

            def _load() -> Any:
                from sentence_transformers import SentenceTransformer  # noqa: PLC0415

                model = SentenceTransformer(self._model_name)
                dim = model.get_sentence_embedding_dimension()
                if dim != self._expected_dim:
                    raise ValueError(
                        f"Model dim {dim} != expected {self._expected_dim} "
                        f"(model={self._model_name})"
                    )
                return model

            self._model = await asyncio.to_thread(_load)
