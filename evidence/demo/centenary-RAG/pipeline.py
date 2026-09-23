"""
End-to-end RAG pipeline: ingest -> chunk -> index -> retrieve -> grounded context.

This is the module that ties your four tasks together into one callable
pipeline. It deliberately does NOT call an LLM itself -- that keeps this
piece testable and swappable independent of which model/API your team ends
up using for generation. `answer()` returns the exact messages you'd send
to an LLM, plus the sources trace, so you (or whoever owns generation) can
plug in the actual API call around this.

Usage:
    pipeline = RagPipeline.from_corpus("path/to/corpus")
    result = pipeline.answer("What are the ATM card replacement fees?")
    print(result.messages)       # ready to send to an LLM
    print(result.sources)        # trace for logging / evaluation
"""

from __future__ import annotations
from dataclasses import dataclass

from ingest import load_corpus, Document
from chunk import chunk_documents, Chunk
from index_store import build_index, RagIndex
from retrieve import retrieve, RetrievedChunk
from context_builder import build_context, build_llm_messages, GroundedContext


@dataclass
class RagAnswerContext:
    query: str
    retrieved: list[RetrievedChunk]
    grounded: GroundedContext
    messages: list[dict]

    @property
    def sources(self):
        return self.grounded.sources


class RagPipeline:
    def __init__(self, index: RagIndex):
        self.index = index

    @classmethod
    def from_corpus(
        cls,
        corpus_dir: str,
        chunk_strategy: str = "paragraph",
        chunk_words: int = 200,
        overlap_words: int = 30,
    ) -> "RagPipeline":
        documents: list[Document] = load_corpus(corpus_dir)
        chunks: list[Chunk] = chunk_documents(
            documents, strategy=chunk_strategy, chunk_words=chunk_words, overlap_words=overlap_words
        )
        index = build_index(chunks)
        return cls(index)

    @classmethod
    def from_chunks(cls, chunks: list[Chunk]) -> "RagPipeline":
        return cls(build_index(chunks))

    def answer(self, query: str, k: int = 4, min_score: float = 0.05) -> RagAnswerContext:
        retrieved = retrieve(self.index, query, k=k, min_score=min_score)
        grounded = build_context(retrieved)
        messages = build_llm_messages(query, grounded)
        return RagAnswerContext(query=query, retrieved=retrieved, grounded=grounded, messages=messages)


if __name__ == "__main__":
    # Mechanics test with throwaway in-memory chunks -- swap in
    # RagPipeline.from_corpus("your/corpus/dir") once the corpus exists.
    test_chunks = [
        Chunk(chunk_id="T01::0", doc_id="T01", doc_title="ATM card facts",
              text="Replacing a lost ATM card costs a small administrative fee and takes three working days."),
        Chunk(chunk_id="T02::0", doc_id="T02", doc_title="Branch hours",
              text="Branches are open Monday to Friday, 8am to 5pm, and Saturday mornings."),
    ]

    pipeline = RagPipeline.from_chunks(test_chunks)

    print("=== Answerable query ===")
    r1 = pipeline.answer("How much does it cost to replace a lost ATM card?")
    print("Retrieved:", [(h.chunk.doc_id, round(h.score, 3)) for h in r1.retrieved])
    print("Sources trace:", [(s.marker, s.doc_id, s.score) for s in r1.sources])
    assert r1.sources and r1.sources[0].doc_id == "T01"

    print("\n=== Deliberately unanswerable query ===")
    r2 = pipeline.answer("What is the exchange rate for Japanese yen today?", min_score=0.15)
    print("Retrieved:", r2.retrieved)
    print("Messages sent to LLM:", r2.messages[1]["content"][:200])
    assert not r2.sources, "expected no sources above threshold for an out-of-corpus query"

    print("\npipeline.py self-test passed")
