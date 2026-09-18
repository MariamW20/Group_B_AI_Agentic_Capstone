"""
Chunking / segmentation stage.

Responsibility: split each Document into smaller, independently-retrievable
Chunks. Every chunk keeps a back-reference to its parent document's doc_id
and title, since that's what lets us cite a *specific* source later, not
just "the corpus somewhere."

Two strategies are provided:
  - chunk_by_paragraph: splits on blank lines first (structure-aware), then
    merges/splits paragraphs to hit a target word count. Preferred default
    for policy/FAQ documents that already have logical sections.
  - chunk_fixed_size: pure sliding window over words with overlap. Simpler,
    useful as a fallback for unstructured text (e.g. a wall of prose with
    no paragraph breaks).

Both attach a chunk_id of the form "{doc_id}::{index}" so it's traceable.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from ingest import Document


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    doc_title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_fixed_size(doc: Document, chunk_words: int = 200, overlap_words: int = 40) -> list[Chunk]:
    words = doc.text.split()
    if not words:
        return []

    chunks: list[Chunk] = []
    start = 0
    idx = 0
    step = max(1, chunk_words - overlap_words)

    while start < len(words):
        end = min(start + chunk_words, len(words))
        text = " ".join(words[start:end])
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}::{idx}",
                doc_id=doc.doc_id,
                doc_title=doc.title,
                text=text,
                metadata={**doc.metadata, "chunk_method": "fixed_size"},
            )
        )
        idx += 1
        if end == len(words):
            break
        start += step

    return chunks


def chunk_by_paragraph(doc: Document, target_words: int = 200, overlap_words: int = 30) -> list[Chunk]:
    paragraphs = [p.strip() for p in doc.text.split("\n\n") if p.strip()]

    if len(paragraphs) <= 1:
        # No real paragraph structure to exploit — fall back to fixed-size.
        return chunk_fixed_size(doc, chunk_words=target_words, overlap_words=overlap_words)

    chunks: list[Chunk] = []
    buffer_words: list[str] = []
    idx = 0

    def flush(overlap: list[str]):
        nonlocal idx
        if not buffer_words:
            return overlap
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}::{idx}",
                doc_id=doc.doc_id,
                doc_title=doc.title,
                text=" ".join(buffer_words),
                metadata={**doc.metadata, "chunk_method": "paragraph"},
            )
        )
        idx += 1
        # keep the last `overlap_words` words as the start of the next chunk
        return buffer_words[-overlap_words:] if overlap_words else []

    for para in paragraphs:
        para_words = para.split()
        if buffer_words and len(buffer_words) + len(para_words) > target_words:
            buffer_words = flush(buffer_words)
        buffer_words.extend(para_words)

    flush(buffer_words)
    return chunks


def chunk_documents(
    documents: list[Document],
    strategy: str = "paragraph",
    chunk_words: int = 200,
    overlap_words: int = 30,
) -> list[Chunk]:
    fn = chunk_by_paragraph if strategy == "paragraph" else chunk_fixed_size
    all_chunks: list[Chunk] = []
    for doc in documents:
        all_chunks.extend(fn(doc, chunk_words, overlap_words))
    return all_chunks


if __name__ == "__main__":
    # Throwaway test document — mechanics check only, not corpus content.
    test_doc = Document(
        doc_id="T01",
        title="Test doc",
        text=(
            "Paragraph one is short.\n\n"
            "Paragraph two is a bit longer and talks about something else entirely, "
            "just to give the chunker more than a handful of words to work with.\n\n"
            "Paragraph three closes things out."
        ),
        metadata={"category": "test"},
    )
    chunks = chunk_by_paragraph(test_doc, target_words=15, overlap_words=3)
    assert all(c.doc_id == "T01" for c in chunks)
    assert len(chunks) >= 1
    for c in chunks:
        print(c.chunk_id, "->", c.text)
    print("chunk.py self-test passed")
