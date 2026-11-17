import hashlib
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from casavaiano.config import INDEX_DIR, KB_DIR, get_settings
from casavaiano.rag.chunking import Chunk, Strategy, chunk_kb
from casavaiano.rag.embeddings import Embedder, FastEmbedder


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    text: str
    source: str
    sections: tuple[str, ...]
    score: float


class Retriever:
    """Chroma-backed retriever. One collection per chunking strategy.

    The index rebuilds itself when the KB files, the strategy or the embedding model change,
    detected through a fingerprint stored in the collection metadata.
    """

    def __init__(
        self,
        strategy: Strategy,
        embedder: Embedder,
        index_dir: Path = INDEX_DIR,
        kb_dir: Path = KB_DIR,
    ):
        self.strategy = strategy
        self.embedder = embedder
        self.kb_dir = kb_dir
        self._client = chromadb.PersistentClient(
            path=str(index_dir), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._collection = None

    @property
    def collection_name(self) -> str:
        return f"kb_{self.strategy}"

    def fingerprint(self) -> str:
        digest = hashlib.sha256(f"{self.strategy}|{self.embedder.name}".encode())
        for path in sorted(self.kb_dir.glob("*.md")):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()[:16]

    def ensure_index(self) -> bool:
        """Build the index if missing or stale. Returns True if it was rebuilt."""
        fingerprint = self.fingerprint()
        existing = {c.name for c in self._client.list_collections()}
        if self.collection_name in existing:
            collection = self._client.get_collection(self.collection_name)
            if (collection.metadata or {}).get("fingerprint") == fingerprint:
                self._collection = collection
                return False
            self._client.delete_collection(self.collection_name)
        self._collection = self._build(fingerprint)
        return True

    def search(self, query: str, k: int | None = None) -> list[RetrievedChunk]:
        if self._collection is None:
            self.ensure_index()
        result = self._collection.query(
            query_embeddings=[self.embedder.embed_query(query)],
            n_results=k or get_settings().retrieval_k,
        )
        return [
            RetrievedChunk(
                id=chunk_id,
                text=text,
                source=meta["source"],
                sections=tuple(meta["sections"].split("|")),
                score=round(1 - distance, 4),
            )
            for chunk_id, text, meta, distance in zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
                strict=True,
            )
        ]

    def _build(self, fingerprint: str):
        chunks: list[Chunk] = chunk_kb(self.strategy, self.kb_dir)
        collection = self._client.create_collection(
            self.collection_name,
            metadata={"fingerprint": fingerprint, "hnsw:space": "cosine"},
        )
        collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=self.embedder.embed_documents([c.text for c in chunks]),
            metadatas=[{"source": c.source, "sections": "|".join(c.sections)} for c in chunks],
        )
        return collection


def default_retriever(strategy: Strategy | None = None) -> Retriever:
    settings = get_settings()
    return Retriever(strategy or settings.chunking_strategy, FastEmbedder(settings.embedding_model))
