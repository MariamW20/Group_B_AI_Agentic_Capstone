"""
Ingestion stage.

Responsibility: read raw documents from a corpus folder and turn them into a
uniform list of Document objects, each carrying its text plus provenance
metadata (where it came from, what kind of document it is, when it was
added). Everything downstream (chunking, indexing, retrieval) depends on
this metadata for source grounding, so we attach it once, here, and carry
it through the whole pipeline.

Expects a corpus folder containing:
  - a manifest.json (or .csv) with one record per document, at minimum:
        doc_id, title, file   (any other fields are carried through as-is)
  - the actual document files referenced by "file"

Supports .txt and .md natively. For .pdf/.docx, plug in an extractor and
call it before constructing the Document (kept out of this file so the
ingestion logic doesn't depend on heavy parsing libraries).
"""

from __future__ import annotations
import json
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Document:
    doc_id: str
    title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _load_manifest(corpus_dir: Path) -> list[dict]:
    json_path = corpus_dir / "manifest.json"
    csv_path = corpus_dir / "manifest.csv"

    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    raise FileNotFoundError(
        f"No manifest.json or manifest.csv found in {corpus_dir}. "
        "The corpus/source register is expected to live there."
    )


def load_corpus(corpus_dir: str | Path) -> list[Document]:
    """
    Load every document listed in the corpus manifest.
    Raises a clear error (rather than silently skipping) if a manifest
    entry points at a file that doesn't exist, since a silent gap here
    would quietly shrink the corpus without anyone noticing.
    """
    corpus_dir = Path(corpus_dir)
    records = _load_manifest(corpus_dir)

    documents: list[Document] = []
    for rec in records:
        file_path = corpus_dir / rec["file"]
        if not file_path.exists():
            raise FileNotFoundError(
                f"Manifest entry {rec.get('doc_id', '?')} points to "
                f"missing file: {file_path}"
            )

        text = file_path.read_text(encoding="utf-8")
        metadata = {k: v for k, v in rec.items() if k not in ("doc_id", "title", "file")}

        documents.append(
            Document(
                doc_id=rec["doc_id"],
                title=rec.get("title", rec["file"]),
                text=text,
                metadata=metadata,
            )
        )

    return documents


if __name__ == "__main__":
    # Smoke test using in-memory throwaway data (not real corpus content) —
    # just proves the loader round-trips a document + its metadata correctly.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "doc1.txt").write_text("The sky is blue. Water boils at 100 degrees Celsius.")
        manifest = [{"doc_id": "T01", "title": "Test doc", "file": "doc1.txt", "category": "test"}]
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        docs = load_corpus(tmp_path)
        assert len(docs) == 1
        assert docs[0].doc_id == "T01"
        assert docs[0].metadata["category"] == "test"
        print("ingest.py self-test passed:", docs[0])