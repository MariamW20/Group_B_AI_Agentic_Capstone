# RAG pipeline — ingestion, chunking, indexing, retrieval, grounded context

Five small modules, each owning exactly one stage, so the pipeline is easy to
test, debug, and explain in your progress report.

```
ingest.py           -> Document: load corpus files + provenance metadata
chunk.py             -> Chunk: split documents into retrievable pieces
index_store.py       -> RagIndex: TF-IDF index over chunks (swappable for embeddings)
retrieve.py           -> RetrievedChunk: top-k search with similarity scores
context_builder.py    -> GroundedContext: prompt context + sources trace
pipeline.py            -> RagPipeline: wires all of the above into one call
```

Each file has a `__main__` self-test at the bottom using tiny throwaway
strings (not real corpus content) — run `python3 <file>.py` on any of them
to see that stage work in isolation. Run all six with:

```bash
for f in ingest.py chunk.py index_store.py retrieve.py context_builder.py pipeline.py; do
  python3 "$f"
done
```

## Plugging in the real corpus

Once your teammate delivers the corpus/source register, it needs to look like:

```
corpus/
  manifest.json        <- one record per document (this IS the source register)
  doc1.txt
  doc2.txt
  ...
```

Each manifest record needs at minimum `doc_id`, `title`, `file`; any other
fields (source_type, date_added, category, version...) are carried through
automatically as metadata onto every chunk and every retrieved source.

Then:

```python
from pipeline import RagPipeline

pipeline = RagPipeline.from_corpus("corpus")
result = pipeline.answer("What are the requirements to open a savings account?")

print(result.messages)   # send this straight to your LLM of choice
print(result.sources)    # the grounding trace: which chunks, which docs, what scores
```

`result.messages` is a ready-made `[{"role": "system", ...}, {"role": "user", ...}]`
list — whoever on the team owns the actual LLM call just needs to pass this
to their API of choice (Anthropic, OpenAI, etc.) and the model's response
will come back with inline `[S1]`, `[S2]` citations that map 1:1 to
`result.sources`.

## Design notes for your progress report

- **Chunking**: paragraph-aware by default (`chunk_by_paragraph`), falls back
  to a fixed sliding window (`chunk_fixed_size`) for documents with no
  paragraph structure. 200-word target, 30-word overlap — tune these once you
  see real documents; short FAQ entries may want smaller chunks.
- **Indexing**: TF-IDF + cosine similarity via scikit-learn. Chosen over a
  vector database because at 10-50 documents a sparse keyword index is fast,
  dependency-light, and easy to audit — every match can be explained by
  which words overlapped. If evaluation later reveals paraphrase misses
  (a question worded very differently from the source text), that's your
  signal to swap `index_store.py` for a dense embedding index — the rest of
  the pipeline (`retrieve.py`, `context_builder.py`, `pipeline.py`) doesn't
  need to change, since it only depends on `RagIndex` producing scored chunks.
- **Grounding**: `min_score` in `retrieve()` is the unanswerable-question
  safety valve — below threshold, no chunks are returned and the prompt
  explicitly tells the model to say it doesn't know rather than guess. This
  is what you'll point to when documenting how the "deliberately unanswerable"
  test questions are handled.
- **Traceability**: `GroundedContext.sources` is a plain list of `SourceRef`
  dataclasses (doc_id, chunk_id, score, exact text) — log this alongside every
  query/answer pair during evaluation. It's what lets you diagnose *why* a
  wrong answer happened: bad retrieval (wrong chunk, check the trace) vs. bad
  generation (right chunk retrieved, model ignored it, check messages vs.
  final answer) — exactly the distinction your grounding-failure writeups need.
