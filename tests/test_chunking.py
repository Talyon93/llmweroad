import re

import pytest

from casavaiano.config import KB_DIR
from casavaiano.rag.chunking import (
    FIXED_OVERLAP_WORDS,
    FIXED_SIZE_WORDS,
    HEADINGS_MAX_WORDS,
    chunk_by_headings,
    chunk_fixed,
    chunk_kb,
    load_documents,
    parse_document,
)

SAMPLE = """# Sample doc

Intro line.

## First

Alpha beta gamma.

## Second

Delta epsilon.

Zeta eta.
"""


@pytest.fixture
def sample(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text(SAMPLE, encoding="utf-8")
    return parse_document(path)


def kb_words() -> set[str]:
    texts = [p.read_text(encoding="utf-8") for p in KB_DIR.glob("*.md")]
    return {word for t in texts for word in re.sub(r"^#+ ", "", t, flags=re.M).split()}


def test_parse_document(sample):
    assert sample.title == "Sample doc"
    assert [h for h, _ in sample.sections] == ["Overview", "First", "Second"]
    assert sample.sections[2][1] == "Delta epsilon.\n\nZeta eta."


def test_headings_one_chunk_per_section_with_prefix(sample):
    chunks = chunk_by_headings(sample)
    assert [c.sections for c in chunks] == [("Overview",), ("First",), ("Second",)]
    assert chunks[1].text == "Sample doc - First\n\nAlpha beta gamma."
    assert [c.id for c in chunks] == ["sample:0", "sample:1", "sample:2"]


def test_headings_split_long_section_on_paragraphs(sample):
    chunks = chunk_by_headings(sample, max_words=3)
    second = [c for c in chunks if c.sections == ("Second",)]
    assert [c.text.split("\n\n", 1)[1] for c in second] == ["Delta epsilon.", "Zeta eta."]


def test_fixed_windows_overlap_and_track_sections(sample):
    chunks = chunk_fixed(sample, size=6, overlap=2)
    bodies = [c.text.split("\n\n", 1)[1].split() for c in chunks]
    assert all(len(b) <= 6 for b in bodies)
    assert bodies[0][-2:] == bodies[1][:2]
    assert chunks[0].sections == ("Overview", "First")


@pytest.mark.parametrize("strategy", ["headings", "fixed"])
def test_kb_chunks_cover_every_word(strategy):
    covered = set(" ".join(c.text for c in chunk_kb(strategy)).split())
    assert kb_words() - covered == set()


def test_kb_chunk_sizes():
    for chunk in chunk_kb("headings"):
        body = chunk.text.split("\n\n", 1)[1]
        assert len(body.split()) <= HEADINGS_MAX_WORDS or "\n\n" not in body
    for chunk in chunk_kb("fixed"):
        body = chunk.text.split("\n\n", 1)[1]
        assert len(body.split()) <= FIXED_SIZE_WORDS
    assert FIXED_OVERLAP_WORDS < FIXED_SIZE_WORDS


def test_every_kb_section_is_its_own_heading_chunk():
    sections = {(d.name, h) for d in load_documents() for h, _ in d.sections}
    chunked = {(c.source, c.sections[0]) for c in chunk_kb("headings")}
    assert sections == chunked
