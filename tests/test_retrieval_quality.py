"""Regression guard on real multilingual retrieval. Uses the local embedding model (downloaded on
first run, ~220 MB). Thresholds sit just below the measured baseline in
evals/results/chunking_retrieval.json, so a drop means something got worse."""

import json

import pytest

from casavaiano.config import EVALS_DIR
from casavaiano.rag.metrics import first_hit_rank, hit_at
from casavaiano.rag.retriever import Retriever, default_retriever

pytestmark = pytest.mark.embedding

QUERIES = [
    json.loads(line)
    for line in (EVALS_DIR / "retrieval_queries.jsonl").read_text(encoding="utf-8").splitlines()
]


@pytest.fixture(scope="module")
def headings_retriever(tmp_path_factory) -> Retriever:
    base = default_retriever("headings")
    return Retriever("headings", base.embedder, index_dir=tmp_path_factory.mktemp("index"))


def hit_rate(retriever: Retriever, queries: list[dict], k: int = 4) -> float:
    hits = [
        hit_at(first_hit_rank(retriever.search(q["query"], k), q["relevant"]), k) for q in queries
    ]
    return sum(hits) / len(hits)


def test_overall_hit_rate(headings_retriever):
    assert hit_rate(headings_retriever, QUERIES) >= 0.9


@pytest.mark.parametrize("lang", ["en", "it", "de"])
def test_hit_rate_per_language(headings_retriever, lang):
    assert hit_rate(headings_retriever, [q for q in QUERIES if q["lang"] == lang]) >= 0.8


@pytest.mark.parametrize(
    ("query", "source", "section"),
    [
        ("Sind Hunde erlaubt?", "policies", "Pets"),
        ("Accettate cani?", "policies", "Pets"),
        ("Can I bring my dog?", "policies", "Pets"),
    ],
)
def test_same_question_in_three_languages_hits_same_section(
    headings_retriever, query, source, section
):
    top = headings_retriever.search(query, 1)[0]
    assert (top.source, top.sections[0]) == (source, section)
