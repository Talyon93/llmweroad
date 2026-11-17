"""Two chunking strategies, compared in the evals.

headings: one chunk per `##` section, prefixed with "<doc title> - <section>" so the chunk is
self-describing. Long sections are split on paragraph boundaries.

fixed: a sliding window of N words with overlap, blind to document structure. This is the common
baseline; it can cut tables and sections in half.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from casavaiano.config import KB_DIR

Strategy = Literal["headings", "fixed"]

HEADINGS_MAX_WORDS = 220
FIXED_SIZE_WORDS = 150
FIXED_OVERLAP_WORDS = 30


@dataclass(frozen=True)
class Document:
    name: str
    title: str
    sections: list[tuple[str, str]]


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    source: str
    sections: tuple[str, ...]


def parse_document(path: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"^# (.+)$", text, re.M)
    title = title_match.group(1).strip() if title_match else path.stem
    parts = re.split(r"^## (.+)$", text, flags=re.M)
    intro = re.sub(r"^# .+$", "", parts[0], flags=re.M).strip()
    sections = [("Overview", intro)] if intro else []
    sections += [(h.strip(), b.strip()) for h, b in zip(parts[1::2], parts[2::2], strict=True)]
    return Document(name=path.stem, title=title, sections=sections)


def load_documents(kb_dir: Path = KB_DIR) -> list[Document]:
    return [parse_document(p) for p in sorted(kb_dir.glob("*.md"))]


def chunk_by_headings(doc: Document, max_words: int = HEADINGS_MAX_WORDS) -> list[Chunk]:
    chunks = []
    for heading, body in doc.sections:
        for part in _split_paragraphs(body, max_words):
            text = f"{doc.title} - {heading}\n\n{part}"
            chunks.append(Chunk(f"{doc.name}:{len(chunks)}", text, doc.name, (heading,)))
    return chunks


def chunk_fixed(
    doc: Document, size: int = FIXED_SIZE_WORDS, overlap: int = FIXED_OVERLAP_WORDS
) -> list[Chunk]:
    words: list[str] = []
    word_sections: list[str] = []
    for heading, body in doc.sections:
        tokens = [*f"## {heading}".split(), *body.split()]
        words += tokens
        word_sections += [heading] * len(tokens)
    chunks = []
    step = size - overlap
    for start in range(0, max(len(words) - overlap, 1), step):
        window = slice(start, start + size)
        sections = tuple(dict.fromkeys(word_sections[window]))
        text = f"{doc.title}\n\n" + " ".join(words[window])
        chunks.append(Chunk(f"{doc.name}:{len(chunks)}", text, doc.name, sections))
    return chunks


def chunk_kb(strategy: Strategy, kb_dir: Path = KB_DIR) -> list[Chunk]:
    chunker = chunk_by_headings if strategy == "headings" else chunk_fixed
    return [chunk for doc in load_documents(kb_dir) for chunk in chunker(doc)]


def _split_paragraphs(body: str, max_words: int) -> list[str]:
    parts, current = [], []
    for paragraph in re.split(r"\n\s*\n", body):
        if current and len(" ".join([*current, paragraph]).split()) > max_words:
            parts.append("\n\n".join(current))
            current = []
        current.append(paragraph)
    if current:
        parts.append("\n\n".join(current))
    return parts
