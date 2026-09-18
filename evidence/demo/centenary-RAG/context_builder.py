"""
Model context construction + source grounding.

Responsibility: turn a list of RetrievedChunks into two things:
  1. A prompt-ready context block, where each piece of evidence is tagged
     with a citation marker like [S1], and the system instructions tell the
     model to only use these sources and to cite them inline.
  2. A parallel "sources trace" -- a plain data structure (not prose) that
     maps each marker back to its doc_id, title, chunk_id and score. This
     is what lets you show sources in the response AND log a trace for
     your evaluation/failure-analysis deliverable, independent of what the
     LLM actually says.

Keeping (1) and (2) separate matters: the trace is ground truth about what
was retrieved, regardless of whether the model's final answer used it well
-- that gap (retrieved good evidence but the model ignored it) is exactly
the kind of grounding failure you're asked to document.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict

from retrieve import RetrievedChunk


@dataclass
class SourceRef:
    marker: str          # e.g. "S1" -- what appears inline in the model's answer
    chunk_id: str
    doc_id: str
    doc_title: str
    score: float
    text: str             # the exact chunk text, kept for audit / failure analysis


@dataclass
class GroundedContext:
    prompt_context: str       # ready to drop into the LLM's system/user message
    sources: list[SourceRef]  # the trace


def build_context(retrieved: list[RetrievedChunk]) -> GroundedContext:
    sources: list[SourceRef] = []
    blocks: list[str] = []

    for i, r in enumerate(retrieved, start=1):
        marker = f"S{i}"
        sources.append(
            SourceRef(
                marker=marker,
                chunk_id=r.chunk.chunk_id,
                doc_id=r.chunk.doc_id,
                doc_title=r.chunk.doc_title,
                score=round(r.score, 4),
                text=r.chunk.text,
            )
        )
        blocks.append(f"[{marker}] (source: {r.chunk.doc_title}, doc_id={r.chunk.doc_id})\n{r.chunk.text}")

    prompt_context = "\n\n".join(blocks)
    return GroundedContext(prompt_context=prompt_context, sources=sources)


SYSTEM_INSTRUCTIONS = """You are a help desk assistant. Answer the user's question using ONLY the \
numbered sources below. Every factual claim in your answer must end with the marker(s) of the \
source(s) it came from, like [S1] or [S1][S2]. If the sources do not contain enough information \
to answer, say so explicitly instead of guessing -- do not use outside knowledge."""


def build_llm_messages(query: str, grounded: GroundedContext) -> list[dict]:
    """Assembles the final message list you'd send to the LLM API."""
    if not grounded.sources:
        # Nothing was retrieved above the confidence threshold -- this is the
        # deliberately-unanswerable / out-of-corpus case. Make that explicit
        # in the prompt rather than sending an empty context and hoping.
        user_content = (
            f"Question: {query}\n\n"
            "No relevant sources were found in the corpus for this question. "
            "Tell the user you don't have that information rather than guessing."
        )
    else:
        user_content = f"Sources:\n{grounded.prompt_context}\n\nQuestion: {query}"

    return [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": user_content},
    ]


if __name__ == "__main__":
    from chunk import Chunk

    fake_hits = [
        RetrievedChunk(
            chunk=Chunk(chunk_id="T02::0", doc_id="T02", doc_title="Water facts",
                        text="Water boils at 100 degrees Celsius at sea level."),
            score=0.83,
        )
    ]
    ctx = build_context(fake_hits)
    assert ctx.sources[0].marker == "S1"
    assert "[S1]" in ctx.prompt_context

    messages = build_llm_messages("What temperature does water boil at?", ctx)
    assert "[S1]" in messages[1]["content"]

    print("context_builder.py self-test passed")
    print("\n--- Example constructed context ---")
    print(ctx.prompt_context)
    print("\n--- Sources trace (for logging / evaluation) ---")
    for s in ctx.sources:
        print(asdict(s))
