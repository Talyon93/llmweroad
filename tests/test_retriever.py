import shutil

import pytest

from casavaiano.config import KB_DIR
from casavaiano.rag.metrics import first_hit_rank, hit_at, reciprocal_rank
from casavaiano.rag.retriever import RetrievedChunk, Retriever


@pytest.fixture
def kb_copy(tmp_path):
    target = tmp_path / "kb"
    shutil.copytree(KB_DIR, target)
    return target


@pytest.fixture
def retriever(tmp_path, kb_copy, hash_embedder):
    return Retriever("headings", hash_embedder, index_dir=tmp_path / "index", kb_dir=kb_copy)


def test_search_returns_ranked_chunks(retriever):
    results = retriever.search("swimming pool opening hours lifeguard", k=3)
    assert len(results) == 3
    assert results[0].source == "services"
    assert results[0].sections == ("Swimming pool",)
    assert results[0].score >= results[1].score >= results[2].score


def test_index_is_reused_until_kb_changes(retriever, kb_copy):
    assert retriever.ensure_index()
    assert not retriever.ensure_index()
    with (kb_copy / "faq.md").open("a", encoding="utf-8") as f:
        f.write("\n## Do you sell truffles?\n\nYes, in autumn.\n")
    assert retriever.ensure_index()
    assert retriever.search("do you sell truffles", k=1)[0].sections == ("Do you sell truffles?",)


def test_strategies_use_separate_collections(tmp_path, kb_copy, hash_embedder):
    headings = Retriever("headings", hash_embedder, tmp_path / "index", kb_copy)
    fixed = Retriever("fixed", hash_embedder, tmp_path / "index", kb_copy)
    headings.ensure_index()
    fixed.ensure_index()
    assert headings._collection.count() != fixed._collection.count()


def chunk(source: str, *sections: str) -> RetrievedChunk:
    return RetrievedChunk(id="x", text="", source=source, sections=sections, score=0.5)


def test_retrieval_metrics():
    results = [chunk("prices", "Seasons"), chunk("policies", "Pets", "Children")]
    assert first_hit_rank(results, [("policies", "Children")]) == 2
    assert first_hit_rank(results, [("prices", "*")]) == 1
    assert first_hit_rank(results, [("events", "*")]) is None
    assert hit_at(2, 4)
    assert not hit_at(None, 4)
    assert reciprocal_rank(2) == 0.5


def test_named_sections_are_found_by_title(retriever):
    found = retriever.named("Is the Pets policy strict? And the swimming pool?")
    assert {c.sections[0] for c in found} >= {"Pets", "Swimming pool"}
    assert all(c.score == 1.0 for c in found)
    assert retriever.named("nothing relevant here") == []


def test_overviews_of_retrieved_documents(retriever):
    intros = retriever.overviews({"rooms", "faq"})
    assert {c.source for c in intros} == {"rooms"}  # faq.md has no intro text
    assert all(c.sections == ("Overview",) for c in intros)
    assert retriever.overviews(set()) == []


def test_assistant_warm_up_loads_retriever(retriever):
    from casavaiano.agent.graph import Assistant
    from casavaiano.config import Settings
    from casavaiano.llm.fake import FakeLLM

    settings = Settings(_env_file=None, kb_dir=str(retriever.kb_dir))
    assistant = Assistant(FakeLLM([]), retriever=retriever, settings=settings)
    assistant.warm_up()
    assert retriever._collection is not None and retriever._chunks is not None
