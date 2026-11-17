from collections.abc import Iterable

from casavaiano.rag.retriever import RetrievedChunk

Label = tuple[str, str]


def is_relevant(chunk: RetrievedChunk, relevant: Iterable[Label]) -> bool:
    return any(
        chunk.source == source and (section == "*" or section in chunk.sections)
        for source, section in relevant
    )


def first_hit_rank(chunks: list[RetrievedChunk], relevant: Iterable[Label]) -> int | None:
    relevant = list(relevant)
    for rank, chunk in enumerate(chunks, start=1):
        if is_relevant(chunk, relevant):
            return rank
    return None


def hit_at(rank: int | None, k: int) -> bool:
    return rank is not None and rank <= k


def reciprocal_rank(rank: int | None) -> float:
    return 0.0 if rank is None else 1 / rank
