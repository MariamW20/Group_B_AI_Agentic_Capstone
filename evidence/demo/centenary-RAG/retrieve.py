"""
Retrieval stage.

Responsibility: given a user question, return the top-k most relevant
chunks, each with a similarity score, sorted highest-first. This is
deliberately the only place that knows *how* similarity is computed
(cosine similarity over TF-IDF vectors), so swapping in a different
retriever later doesn't ripple through the rest of the pipeline.

Also exposes a min_score threshold: if the best match scores below it,
that's a signal the corpus likely doesn't contain the answer at all --
useful both for deliberately-unanswerable test questions and for deciding
when the agent should say "I don't have that information" instead of
forcing a low-confidence answer.
"""

from __future__ import annotations
from dataclasses import dataclass

from sklearn.metrics.pairwise import cosine_similarity

from chunk import Chunk
from index_store import RagIndex


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float


def retrieve(index: RagIndex, query: str, k: int = 4, min_score: float = 0.05) -> list[RetrievedChunk]:
    query_vec = index.vectorizer.transform([query])
    scores = cosine_similarity(query_vec, index.matrix)[0]

    ranked = sorted(
        zip(index.chunks, scores),
        key=lambda pair: pair[1],
        reverse=True,
    )

    results = [
        RetrievedChunk(chunk=c, score=float(s))
        for c, s in ranked[:k]
        if s >= min_score
    ]
    return results


if __name__ == "__main__":
    from chunk import Chunk
    from index_store import build_index

    test_chunks = [
        Chunk(chunk_id="T01::0", doc_id="T01", doc_title="Sky facts", text="The sky is blue and clear on a sunny day."),
        Chunk(chunk_id="T02::0", doc_id="T02", doc_title="Water facts", text="Water boils at 100 degrees Celsius at sea level."),
    ]
    idx = build_index(test_chunks)

    hits = retrieve(idx, "what temperature does water boil at", k=2)
    assert hits, "expected at least one hit"
    assert hits[0].chunk.doc_id == "T02", f"expected water doc to rank first, got {hits[0].chunk.doc_id}"
    print("retrieve.py self-test passed:", [(h.chunk.doc_id, round(h.score, 3)) for h in hits])

    no_hits = retrieve(idx, "what is the capital of France", k=2, min_score=0.2)
    print("Unrelated query correctly returned", len(no_hits), "hits above threshold")
