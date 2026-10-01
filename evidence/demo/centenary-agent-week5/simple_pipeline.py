"""
Lightweight keyword-search pipeline that implements the same interface as
RagPipeline from evidence/demo/centenary-RAG/pipeline.py.

Used in demo_week5.py and tests so the agent can run without scikit-learn.
The real TF-IDF pipeline can be swapped in by replacing SimplePipeline with
RagPipeline.from_corpus(...) once the environment supports it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class _Source:
    marker: str
    doc_id: str
    doc_title: str
    score: float
    text: str


class _Answer:
    def __init__(self, sources: List[_Source]):
        self.sources = sources


class SimplePipeline:
    """
    Ranks chunks by simple keyword overlap with the query.
    Returns up to k results above a minimum score.
    """

    def __init__(self, chunks: List[dict]):
        """
        chunks: list of dicts with keys doc_id, doc_title, text
        """
        self._chunks = chunks

    def answer(self, query: str, k: int = 4, min_score: float = 0.05) -> _Answer:
        query_words = set(query.lower().split())
        scored = []
        for i, chunk in enumerate(self._chunks):
            chunk_words = set(chunk["text"].lower().split())
            overlap = len(query_words & chunk_words)
            score = overlap / max(len(query_words), 1)
            if score >= min_score:
                scored.append((score, i, chunk))

        scored.sort(key=lambda x: -x[0])
        sources = [
            _Source(
                marker=f"S{rank + 1}",
                doc_id=chunk["doc_id"],
                doc_title=chunk["doc_title"],
                score=round(score, 4),
                text=chunk["text"],
            )
            for rank, (score, _, chunk) in enumerate(scored[:k])
        ]
        return _Answer(sources)
