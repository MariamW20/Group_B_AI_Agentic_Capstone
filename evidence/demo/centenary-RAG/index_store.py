"""
Indexing stage.

Responsibility: turn a list of Chunks into a structure that can be searched
fast. Implemented here as TF-IDF (sparse, keyword-based) via scikit-learn --
a strong, dependency-light baseline for a 10-50 document corpus. The
interface (build / save / load / as used by retrieve.py) is written so a
dense embedding index can be swapped in later without touching retrieve.py's
calling code: only this file would change.

Persisted to disk with pickle so ingestion+chunking+indexing don't have to
re-run every time you want to query.
"""

from __future__ import annotations
import pickle
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer

from chunk import Chunk


@dataclass
class RagIndex:
    vectorizer: TfidfVectorizer
    matrix: any  # scipy sparse matrix, shape (n_chunks, n_terms)
    chunks: list[Chunk]

    def save(self, path: str | Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: str | Path) -> "RagIndex":
        with open(path, "rb") as f:
            return pickle.load(f)


def build_index(chunks: list[Chunk]) -> RagIndex:
    if not chunks:
        raise ValueError("Cannot build an index over zero chunks — check ingestion/chunking output.")

    texts = [c.text for c in chunks]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),  # unigrams + bigrams: helps match short phrases like "minimum balance"
        min_df=1,
    )
    matrix = vectorizer.fit_transform(texts)
    return RagIndex(vectorizer=vectorizer, matrix=matrix, chunks=chunks)


if __name__ == "__main__":
    test_chunks = [
        Chunk(chunk_id="T01::0", doc_id="T01", doc_title="Test", text="The sky is blue and clear."),
        Chunk(chunk_id="T02::0", doc_id="T02", doc_title="Test2", text="Water boils at 100 degrees Celsius."),
    ]
    idx = build_index(test_chunks)
    assert idx.matrix.shape[0] == 2
    print("index_store.py self-test passed, matrix shape:", idx.matrix.shape)
