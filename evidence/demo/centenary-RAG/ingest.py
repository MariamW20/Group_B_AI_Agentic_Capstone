"""
Ingestion stage.

Responsibility: read raw documents from a corpus folder and turn them into a
uniform list of Document objects, each carrying its text plus provenance
metadata (where it came from, what kind of document it is, when it was
added). Everything downstream (chunking, indexing, retrieval) depends on
this metadata for source grounding, so we attach it once, here, and carry
it through the whole pipeline.

Supports two loading paths:

1. load_corpus(corpus_dir)
   Classic folder-based loader. Expects:
     - manifest.json or manifest.csv  (doc_id, title, file, …)
     - the text files referenced by "file"

2. load_from_csvs(faqs_csv, register_csv)
   Loads directly from the project's two source CSVs without a corpus folder:
     - centenary_bank_faqs.csv  — columns: id, question, answer
     - REGISTER.csv             — columns: entry_type, entry_id, title,
                                    category_or_answer_type, location_or_csv_row,
                                    source_basis, notes
   Only rows with entry_type == "record" become documents (source rows are
   governance metadata, not searchable content). The location_or_csv_row field
   is the FAQ row id that supplies the Q+A text.

3. load_project_corpus()
   Convenience wrapper: finds both CSVs relative to this file's project root
   and calls load_from_csvs automatically.
"""

from __future__ import annotations
import json
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Project root is three levels up from this file:
# evidence/demo/centenary-RAG/ingest.py → evidence/demo/centenary-RAG → evidence/demo → evidence → project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_FAQS = _PROJECT_ROOT / "centenary_bank_faqs.csv"
_DEFAULT_REGISTER = _PROJECT_ROOT / "REGISTER.csv"


@dataclass
class Document:
    doc_id: str
    title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Path 1: classic corpus-folder loader (unchanged)
# ---------------------------------------------------------------------------

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

    documents = []
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


# ---------------------------------------------------------------------------
# Path 2: load directly from centenary_bank_faqs.csv + REGISTER.csv
# ---------------------------------------------------------------------------

def _read_faqs(faqs_csv: Path) -> dict[str, dict]:
    """Return a dict keyed by the FAQ row id (string) → {id, question, answer}."""
    rows = {}
    with open(faqs_csv, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows[row["id"].strip()] = row
    return rows


def _read_register_records(register_csv: Path) -> list[dict]:
    """Return only the 'record' rows from REGISTER.csv (skips 'source' rows)."""
    records = []
    with open(register_csv, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("entry_type", "").strip() == "record":
                records.append(row)
    return records


def load_from_csvs(
    faqs_csv: str | Path = _DEFAULT_FAQS,
    register_csv: str | Path = _DEFAULT_REGISTER,
) -> list[Document]:
    """
    Build Document objects from centenary_bank_faqs.csv and REGISTER.csv.

    Each REGISTER.csv 'record' row is joined to its FAQ row via
    location_or_csv_row (the numeric FAQ id). The document text is:
        Q: <question>
        A: <answer>

    Provenance metadata (category, source_basis, notes) is attached from
    the register row so retrieval results carry full grounding information.

    Skips register rows whose FAQ row id cannot be found in the FAQ file
    and prints a warning so gaps are visible without crashing.
    """
    faqs = _read_faqs(Path(faqs_csv))
    register_records = _read_register_records(Path(register_csv))

    documents = []
    for rec in register_records:
        faq_id = rec.get("location_or_csv_row", "").strip()
        faq_row = faqs.get(faq_id)
        if faq_row is None:
            print(
                f"[ingest] WARNING: register entry {rec.get('entry_id')} "
                f"references FAQ row '{faq_id}' which was not found — skipped."
            )
            continue

        question = faq_row.get("question", "").strip()
        answer = faq_row.get("answer", "").strip()
        text = f"Q: {question}\nA: {answer}"

        documents.append(
            Document(
                doc_id=rec["entry_id"].strip(),
                title=rec.get("title", question[:60]).strip(),
                text=text,
                metadata={
                    "category": rec.get("category_or_answer_type", "").strip(),
                    "source_basis": rec.get("source_basis", "").strip(),
                    "notes": rec.get("notes", "").strip(),
                    "faq_id": faq_id,
                },
            )
        )

    return documents


def load_project_corpus() -> list[Document]:
    """
    Convenience loader: reads the project's two CSV files from the
    standard locations relative to this file and returns all documents.
    """
    if not _DEFAULT_FAQS.exists():
        raise FileNotFoundError(f"FAQ CSV not found at {_DEFAULT_FAQS}")
    if not _DEFAULT_REGISTER.exists():
        raise FileNotFoundError(f"Register CSV not found at {_DEFAULT_REGISTER}")
    return load_from_csvs(_DEFAULT_FAQS, _DEFAULT_REGISTER)


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    # --- Test 1: classic corpus-folder loader ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "doc1.txt").write_text("The sky is blue. Water boils at 100 degrees Celsius.")
        manifest = [{"doc_id": "T01", "title": "Test doc", "file": "doc1.txt", "category": "test"}]
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        docs = load_corpus(tmp_path)
        assert len(docs) == 1
        assert docs[0].doc_id == "T01"
        assert docs[0].metadata["category"] == "test"
        print("load_corpus self-test passed:", docs[0].doc_id)

    # --- Test 2: CSV loader ---
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        faqs = tmp_path / "faqs.csv"
        faqs.write_text(
            "id,question,answer\n"
            "1,What is the minimum balance?,UShs. 10,000.\n"
            "3,Where is head office?,Mapeera House Kampala.\n"
        )

        register = tmp_path / "register.csv"
        register.write_text(
            "entry_type,entry_id,title,category_or_answer_type,location_or_csv_row,source_basis,notes\n"
            "source,G-01,AI Boundary Matrix,governance,,R-01,Primary control\n"
            "record,COR-001,Minimum balance,Account rule,1,R-01,Verified\n"
            "record,COR-002,Head office location,Contact,3,R-01,Verified\n"
        )

        docs = load_from_csvs(faqs, register)
        assert len(docs) == 2, f"expected 2 docs, got {len(docs)}"
        assert docs[0].doc_id == "COR-001"
        assert "minimum balance" in docs[0].text.lower()
        assert docs[0].metadata["category"] == "Account rule"
        assert docs[1].doc_id == "COR-002"
        print("load_from_csvs self-test passed:", [d.doc_id for d in docs])

    # --- Test 3: project corpus (only if the real files exist) ---
    if _DEFAULT_FAQS.exists() and _DEFAULT_REGISTER.exists():
        docs = load_project_corpus()
        print(f"load_project_corpus: loaded {len(docs)} documents from the project CSVs")
        for d in docs[:3]:
            print(f"  {d.doc_id}: {d.title[:50]}")
    else:
        print("Skipping load_project_corpus test (project CSV files not found at expected paths)")

    print("\ningest.py self-tests passed.")