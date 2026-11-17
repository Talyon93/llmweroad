from functools import cached_property
from typing import Protocol

from casavaiano.config import ROOT_DIR

MODEL_CACHE_DIR = ROOT_DIR / ".cache" / "fastembed"


class Embedder(Protocol):
    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedder:
    """Local ONNX embeddings: no API cost, no PyTorch, works offline once downloaded."""

    def __init__(self, model_name: str):
        self.name = model_name

    @cached_property
    def _model(self):
        from fastembed import TextEmbedding

        return TextEmbedding(self.name, cache_dir=str(MODEL_CACHE_DIR))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed(text))).tolist()
