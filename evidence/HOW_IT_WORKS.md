# How RAG and Agents Work — A Builder's Guide

**Based on the Centenary Bank Helpdesk Agent (BSE4104 Group B)**  
*Written from the actual code in this project — every concept maps to a real file you can open.*

---

## Table of Contents

1. [Python Basics You Must Know](#1-python-basics-you-must-know)
2. [What Problem Are We Solving?](#2-what-problem-are-we-solving)
3. [RAG — Retrieval-Augmented Generation](#3-rag--retrieval-augmented-generation)
4. [The RAG Pipeline Step by Step](#4-the-rag-pipeline-step-by-step)
5. [Agents — Making the AI Take Actions](#5-agents--making-the-ai-take-actions)
6. [The Agent Architecture](#6-the-agent-architecture)
7. [Orchestration — Who Controls What](#7-orchestration--who-controls-what)
8. [How All the Pieces Connect](#8-how-all-the-pieces-connect)
9. [Reading the Code in Order](#9-reading-the-code-in-order)

---

## 1. Python Basics You Must Know

Before anything else. These patterns appear constantly in the codebase.

### Dataclasses — the project's main data structure

A dataclass is a class that just holds data. You define the fields, Python handles `__init__` for free.

```python
# From evidence/demo/centenary-RAG/ingest.py
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Document:
    doc_id: str        # required field, must be a string
    title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)  # optional, defaults to {}
```

`field(default_factory=dict)` means "give every new Document its OWN empty dict, not one shared dict". This matters — if you wrote `metadata: dict = {}`, every Document would share the same dict and mutating one would mutate all of them.

You create one like:
```python
doc = Document(doc_id="COR-001", title="Minimum Balance", text="The minimum is UGX 10,000.")
print(doc.doc_id)   # "COR-001"
print(doc.metadata) # {}
```

**Files using dataclasses:** `ingest.py` (Document), `chunk.py` (Chunk), `retrieve.py` (RetrievedChunk), `context_builder.py` (GroundedContext, SourceRef), `orchestrator.py` (CallerContext), `agent_state.py` (AgentState).

---

### Type hints — `str | None`, `list[dict]`

```python
def call(self, tool_name: str, arguments: dict, caller: CallerContext) -> dict:
```

The `str`, `dict`, `CallerContext`, `-> dict` are **hints** — Python does not enforce them at runtime. They are documentation for you and your editor. `str | None` means "either a string or None (nothing)". `list[dict]` means "a list of dicts".

---

### `from __future__ import annotations`

```python
from __future__ import annotations
```

This line appears at the top of every file. It tells Python 3.8 to treat all type hints as strings instead of evaluating them immediately. Without it, writing `list[dict]` in a type hint would crash on Python 3.8 (it became native in 3.9). This one import makes the code forward-compatible.

---

### `sys.path.insert` — how files import each other

Python's import system looks through `sys.path` (a list of folder paths) when you write `import something`. The project's files are spread across different folders, so each file adds its own folder to `sys.path` before importing:

```python
# From evidence/demo/centenary-agent-week5/agent_controller.py
import sys
from pathlib import Path

_DEMO = Path(__file__).resolve().parent.parent / "centenary-RAG"
sys.path.insert(0, str(_DEMO))

from orchestrator import CallerContext  # now Python can find this
```

`Path(__file__)` is the path to the current file. `.resolve()` turns it into an absolute path. `.parent` goes up one folder. This is how the Week 5 agent imports the Week 4 tools without copying files.

---

### `dict.get()` vs `dict[]`

```python
result.get("status")          # returns None if "status" key is missing
result["status"]              # raises KeyError if "status" key is missing
result.get("status", "error") # returns "error" if "status" key is missing
```

The agent code uses `.get()` almost everywhere because tool results may be partial on failure. Never use `[]` on an untrusted dict.

---

### `pathlib.Path` — modern file paths

```python
from pathlib import Path

p = Path("evidence/traces/week5")
p.mkdir(parents=True, exist_ok=True)   # create folder (and parents) if missing
p.exists()                             # True or False
p / "myfile.json"                      # join paths with /
p.read_text()                          # read the file as a string
p.write_text(json.dumps(data))         # write a string to the file
```

Never use raw string concatenation like `"folder/" + "file"` for paths — `Path` handles OS differences automatically.

---

## 2. What Problem Are We Solving?

A plain LLM (like Gemini or GPT) was trained on internet data up to a cutoff date. It:
- **Does not know** Centenary Bank's specific fees, products, or procedures
- **Cannot look up** a customer's ticket
- **Makes things up** (hallucination) when it does not know
- **Cannot take actions** on its own (create a ticket, check a service)

We solve this with two complementary techniques:

| Problem | Solution |
|---|---|
| LLM doesn't know bank-specific facts | **RAG** — retrieve real documents before the LLM answers |
| LLM cannot act on systems | **Agent with tools** — give it approved functions it can call |
| LLM might act dangerously | **Orchestration** — code validates everything before execution |

---

## 3. RAG — Retrieval-Augmented Generation

**The core idea:** Before the LLM generates an answer, retrieve the most relevant passages from a trusted document collection and paste them into the prompt. The LLM answers from those passages, not from its training memory.

```
Customer question
       │
       ▼
  [Search the knowledge base]
       │
       ▼
  Top 4 relevant passages  ←── comes from centenary_bank_faqs.csv
       │
       ▼
  Prompt: "Using ONLY these sources, answer: ..."
       │
       ▼
  LLM generates answer with citations [S1][S2]
```

**Why this beats a plain LLM:**
- The answer is grounded in real bank documents
- The LLM is told "only use these sources" — it cannot hallucinate
- Every claim in the response maps back to a specific source (`[S1]`, `[S2]`)
- You can audit exactly what evidence the LLM saw

**The key tradeoff:** The quality of the answer is bounded by the quality of the retrieval. If retrieval returns the wrong passages, the LLM will produce a wrong but confident-sounding answer from them. This is why the evaluation and trace exist.

---

## 4. The RAG Pipeline Step by Step

The pipeline has five sequential stages. Each stage is its own Python file.

```
centenary_bank_faqs.csv + REGISTER.csv
              │
              ▼
    [Stage 1] ingest.py          → list[Document]
              │
              ▼
    [Stage 2] chunk.py           → list[Chunk]
              │
              ▼
    [Stage 3] index_store.py     → RagIndex  (TF-IDF matrix)
              │
              ▼
    [Stage 4] retrieve.py        → list[RetrievedChunk]  (for one query)
              │
              ▼
    [Stage 5] context_builder.py → GroundedContext + LLM messages
```

`pipeline.py` is the glue that connects all five stages into one callable object.

---

### Stage 1 — Ingest (`ingest.py`)

**Job:** Read raw source files and turn them into `Document` objects.

```python
@dataclass
class Document:
    doc_id: str    # "COR-001"
    title: str     # "What is the minimum account balance?"
    text: str      # "Q: What is the minimum... A: UShs. 10,000."
    metadata: dict # {"category": "Account rule", "source_basis": "R-05"}
```

Our `load_from_csvs()` function joins `REGISTER.csv` (which tells us WHAT to load and its metadata) with `centenary_bank_faqs.csv` (which contains the actual Q+A text):

```python
# REGISTER.csv says: entry_id=COR-005, location_or_csv_row=8
# centenary_bank_faqs.csv row 8 says: question="What is the minimum balance?", answer="UShs 10,000"
# Result:
Document(
    doc_id="COR-005",
    title="What is the required minimum account balance?",
    text="Q: What is the required minimum account balance?\nA: UShs. 10,000.",
    metadata={"category": "Account rule", "source_basis": "R-01; R-05"}
)
```

The `REGISTER.csv` `source` rows (URLs, governance docs) are skipped — they are metadata about sources, not searchable content.

---

### Stage 2 — Chunk (`chunk.py`)

**Job:** Split each Document into smaller pieces so retrieval is precise.

**Why chunk at all?** If a document is 2,000 words and the answer is in the last 50 words, a retriever that returns the whole document as one block wastes most of the LLM's context window. Smaller chunks → more precise retrieval.

```python
@dataclass
class Chunk:
    chunk_id: str   # "COR-005::0"  (doc_id + index)
    doc_id: str     # "COR-005"     (back-reference to source)
    doc_title: str  # "Minimum balance"
    text: str       # the actual chunk text
```

Two strategies:

**Paragraph chunking** (default): splits on blank lines first, then merges until `target_words` is reached. Respects the document's own structure — good for FAQs.

**Fixed-size chunking**: sliding window of N words with M words of overlap. The overlap ensures a sentence that falls on a boundary is not lost.

```
Document text (100 words):
[---- chunk 0: words 0-50 ----][---- chunk 1: words 30-80 ----][---- chunk 2: words 60-100 ----]
                  └── overlap ──┘                  └── overlap ──┘
```

Overlap prevents "chunk boundary blindness" — if the key sentence is at word 49, it appears in both chunk 0 and chunk 1.

---

### Stage 3 — Index (`index_store.py`)

**Job:** Build a searchable structure from the chunks so retrieval is fast.

This project uses **TF-IDF** (Term Frequency-Inverse Document Frequency):

- **TF (Term Frequency):** how often a word appears in a chunk. "balance" appearing 5 times in a 50-word chunk is more significant than appearing once.
- **IDF (Inverse Document Frequency):** how rare a word is across ALL chunks. "the" appears everywhere so it gets near-zero weight. "CenteMobile" appears rarely so it gets high weight.
- **Result:** every chunk becomes a vector of numbers (one number per unique word in the corpus). Words that are common everywhere get low values; words that are distinctive get high values.

```python
from sklearn.feature_extraction.text import TfidfVectorizer

vectorizer = TfidfVectorizer(
    lowercase=True,
    stop_words="english",   # ignore "the", "is", "a", etc.
    ngram_range=(1, 2),     # match single words AND two-word phrases
)
matrix = vectorizer.fit_transform(texts)  # shape: (num_chunks, num_unique_words)
```

The result is a `RagIndex` containing:
- the `vectorizer` (to transform queries into the same vector space)
- the `matrix` (all chunk vectors, one row per chunk)
- the `chunks` list (to map a matrix row back to the original Chunk)

---

### Stage 4 — Retrieve (`retrieve.py`)

**Job:** Given a query, return the top-k most relevant chunks.

```python
def retrieve(index, query, k=4, min_score=0.05):
    query_vec = index.vectorizer.transform([query])       # query → vector
    scores = cosine_similarity(query_vec, index.matrix)[0] # compare to all chunks
    ranked = sorted(zip(index.chunks, scores), key=lambda x: -x[1])
    return [RetrievedChunk(chunk=c, score=float(s)) for c, s in ranked[:k] if s >= min_score]
```

**Cosine similarity** measures the angle between two vectors. Two chunks that use the exact same words as the query will have a score close to 1.0. Chunks that share no words score 0.0.

The `min_score` threshold is important: if the best match is below 0.05, the corpus probably does not contain the answer. The agent then says "I don't have that information" instead of forcing a bad answer.

---

### Stage 5 — Context Builder (`context_builder.py`)

**Job:** Format the retrieved chunks into a prompt the LLM can use, and produce a sources trace.

```python
# Input: [RetrievedChunk(chunk=..., score=0.9), ...]
# Output:
GroundedContext(
    prompt_context="""
[S1] (source: Minimum balance FAQ, doc_id=COR-005)
Q: What is the required minimum account balance?
A: UShs. 10,000.

[S2] (source: CenteSacco Savings Account, doc_id=COR-006)
...
""",
    sources=[SourceRef(marker="S1", doc_id="COR-005", score=0.9, text="..."), ...]
)
```

The `[S1]`, `[S2]` markers are injected into the prompt. The system instruction tells the LLM: *"Only use the numbered sources. Cite them inline."* So the LLM output says things like "The minimum balance is UShs. 10,000 [S1]."

The `sources` list is the **trace** — it records exactly what evidence the LLM saw, independent of what it said. A grounding failure (LLM ignores a good source, or makes up something not in the sources) is visible in this trace.

---

### The Glue — `pipeline.py`

`RagPipeline` wires all five stages together behind one method call:

```python
pipeline = RagPipeline.from_corpus("path/to/corpus")
result = pipeline.answer("What is the minimum balance?")

result.sources    # list of SourceRef — what was retrieved
result.messages   # list of dicts — ready to send to the LLM API
```

`from_corpus()` runs stages 1–3 once (ingest → chunk → index). The index is held in memory. Each call to `.answer()` runs stages 4–5 (retrieve → build context).

---

## 5. Agents — Making the AI Take Actions

A RAG pipeline answers questions. An **agent** can also *do things* — check a ticket, create a ticket, escalate a case. But an agent that can do anything freely is dangerous. This project implements a **bounded agent** with explicit limits.

### What makes something an "agent"?

An agent runs in a loop:
1. **Observe** the current state
2. **Decide** what action to take
3. **Act** — execute the action
4. **Observe** the result
5. **Repeat or stop**

The key difference from a pipeline: the agent decides its own next step. A pipeline is a fixed sequence of stages. An agent's path depends on what it finds at each step.

### The seven actions this agent can take

The contract defines exactly seven — no more:

| Action | What happens |
|---|---|
| `answer_from_evidence` | Use retrieved passages to answer the customer |
| `check_service_status` | Call `get_service_status` tool |
| `check_ticket_status` | Call `get_ticket_status` tool |
| `create_support_ticket` | Call `create_support_ticket` tool |
| `request_escalation_approval` | Ask a human to approve escalation |
| `ask_for_clarification` | Ask the customer for missing information |
| `refuse_or_handoff` | Decline an out-of-scope request |

The model cannot invent new actions. The code enforces this at the action gate.

---

## 6. The Agent Architecture

### The five-step loop

```
                    ┌─────────────────────────────────────────┐
                    │         AgentController.run()            │
                    │                                          │
  Customer ──────►  │  1. SENSE / CONTEXT                      │
  request           │     Build prompt from AgentState         │
                    │     (request, evidence, tool results,     │
                    │      iterations left, allowed actions)    │
                    │              │                            │
                    │              ▼                            │
                    │  2. PLAN / DECIDE  ──────────► Gemini    │
                    │     Model returns one JSON action         │
                    │     {intent, action, tool, arguments}    │
                    │              │                            │
                    │              ▼                            │
                    │  3. ACTION GATE (code, not model)        │
                    │     ✓ action is in allowed list?         │
                    │     ✓ no customer_id in arguments?       │
                    │     ✓ tool is on allow-list?             │
                    │     ✗ reject → re-plan                   │
                    │              │                            │
                    │              ▼                            │
                    │  4. ACT / TOOL                           │
                    │     ToolOrchestrator.call(tool, args)    │
                    │     CallerContext from trusted session   │
                    │              │                            │
                    │              ▼                            │
                    │  5. OBSERVE                              │
                    │     Check status, status_code            │
                    │     Retry once if service_unavailable    │
                    │     Stop or re-plan                      │
                    └─────────────────────────────────────────┘
                                   │ stop
                                   ▼
                            Final response
                            + terminal outcome
                            + trace file
```

### AgentState — the memory of one request

```python
# evidence/demo/centenary-agent-week5/agent_state.py
@dataclass
class AgentState:
    request_id: str           # never changes
    customer_id: str          # never changes — set from trusted session
    user_request: str         # never changes — original message

    intent: str               # model sets this, updated each iteration
    retrieved_evidence: list  # APPEND ONLY — model cannot remove evidence
    planned_action: str       # model's current choice
    tool_calls: list          # APPEND ONLY — every tool call is recorded
    attempt_count: int        # INCREMENT ONLY — code controls this, not model
    approval_status: str      # "not_required" / "pending" / "approved" / "denied"
    final_response: str       # SET ONCE at stop
    stop_reason: str          # SET ONCE at stop
    terminal_outcome: str     # SET ONCE at stop — one of 10 defined outcomes
```

**Why these mutation rules matter:** If the model could decrement `attempt_count`, it could run forever. If it could remove `retrieved_evidence`, it could hide what it found. The rules are enforced by the controller code, not by trusting the model.

### The 10 terminal outcomes

Every run ends with exactly one of these — no exceptions:

```
ANSWERED_FROM_KNOWLEDGE    — answered from knowledge base
SERVICE_STATUS_RETURNED    — returned service status
TICKET_STATUS_RETURNED     — returned ticket status
TICKET_CREATED             — created a support ticket
ESCALATED_AFTER_APPROVAL   — escalated with human approval
CLARIFICATION_REQUIRED     — asked customer for more info
OUT_OF_SCOPE_HANDOFF       — refused or handed off
AUTHORIZATION_DENIED       — access denied
TOOL_FAILURE_HANDOFF       — tool failed after retry
ITERATION_LIMIT_REACHED    — ran out of iterations
```

These outcomes make the agent auditable. You can count how many requests ended in `TOOL_FAILURE_HANDOFF` and investigate.

---

## 7. Orchestration — Who Controls What

Orchestration is the layer between "the model wants to do something" and "something actually happens." This is the most important safety concept in the entire project.

### The rule: the model proposes, code decides

```
Model output:  { "action": "check_ticket_status",
                 "tool": "get_ticket_status",
                 "arguments": { "ticket_id": "CS-10245" } }
                 
                         │
                         ▼
                   ACTION GATE (code)
                   • Is "check_ticket_status" in ALLOWED_ACTIONS? ✓
                   • Is "get_ticket_status" in ALLOWED_TOOLS? ✓
                   • Does "arguments" contain "customer_id"? ✗ (good — rejected if yes)
                   • Does "arguments" contain "human_approval_token"? ✗ (good)
                         │
                         ▼
                   TOOL ORCHESTRATOR (code)
                   • Inject customer_id from trusted session (not from model)
                   • Validate arguments against the tool's schema
                   • Check auth_level
                   • Execute the tool function
                   • Validate the tool's output before returning it
```

### Why can't the model supply `customer_id`?

If the model could supply `customer_id`, it could say:
```json
{ "tool": "get_ticket_status", "arguments": { "ticket_id": "CS-10246", "customer_id": "CUST-OTHER" } }
```
...and see another customer's private ticket. The orchestrator rejects any arguments containing `customer_id` — it is always injected from the authenticated session by trusted code.

### The ToolOrchestrator (`orchestrator.py`)

```python
class ToolOrchestrator:
    def call(self, tool_name, arguments, caller: CallerContext) -> dict:
        # 1. Does this tool exist?
        # 2. Strip identity fields from arguments, inject from CallerContext
        # 3. Validate all arguments against the tool's schema
        # 4. Check caller's auth_level >= tool's required_auth_level
        # 5. For higher-impact tools: require human_approved=True
        # 6. Execute the tool function
        # 7. Validate the output matches the expected schema
        # 8. Return {"status": "success", "result": {...}} or {"status": "error", ...}
```

Every tool call goes through all 8 steps. The tool function itself never sees the caller's auth level or token — those are checked before the function runs.

### CallerContext — the trust boundary

```python
@dataclass
class CallerContext:
    auth_level: int                   # 0=unauthenticated, 1=read, 2=write
    customer_id: str | None = None    # from authenticated session
    human_approved: bool = False      # set by trusted approval gate
    human_approval_token: str | None = None  # single-use, bound to exact args
```

This is created by trusted application code (the controller), not by the model. The model never sees it.

### The tools (`tools.py`)

Each tool is a `ToolSpec` — a contract that says what arguments it takes, what it returns, and what can go wrong:

```python
ToolSpec(
    name="get_ticket_status",
    purpose="Retrieve a ticket belonging to the authenticated customer.",
    input_schema={
        "ticket_id": {"type": "string", "required": True},
        "customer_id": {"type": "string", "required": True, "source": "session"},
        #                                                     ▲
        #                         "source": "session" means the orchestrator
        #                         injects this from CallerContext, not from model args
    },
    output_schema={"status_code": "string", "ticket_id": "string"},
    required_auth_level=2,
    higher_impact=False,
    ...
)
```

The `"source": "session"` annotation is the key. The orchestrator reads this and knows: "do not accept this field from model-generated arguments; take it from the authenticated session."

### The Planner (`planner.py`)

The planner is the only place the LLM is called inside the loop. It receives a text description of the current state and returns one JSON object:

```python
# What the planner sends to Gemini:
"""
Customer request: What is the status of ticket CS-10245?
Current intent: ticket-status request
Iterations left: 3
Retrieved evidence: (none yet)
Earlier tool results: (none yet)
Choose the best next action and return ONLY the JSON object.
"""

# What Gemini returns:
{
  "intent": "ticket status check",
  "action": "check_ticket_status",
  "tool": "get_ticket_status",
  "arguments": {"ticket_id": "CS-10245"},
  "reason": "Customer explicitly asked for ticket CS-10245 status."
}
```

The planner communicates with Gemini using the REST API directly via Python's built-in `urllib`:

```python
import urllib.request
import json

url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
payload = {
    "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
    "contents": [{"parts": [{"text": prompt}]}],
}
req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                              headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as resp:
    body = json.loads(resp.read().decode())
    text = body["candidates"][0]["content"]["parts"][0]["text"]
```

No SDK required — the Gemini API is just an HTTPS endpoint that accepts JSON and returns JSON.

### The Trace Recorder (`trace_recorder.py`)

Every iteration writes one record to `evidence/traces/week5/<request_id>.json`:

```json
[
  {
    "iteration": 1,
    "intent": "ticket status check",
    "planned_action": "check_ticket_status",
    "gate_decision": "approved",
    "tool_name": "get_ticket_status",
    "arguments": {"ticket_id": "CS-10245"},
    "status": "success",
    "status_code": "OK",
    "error_type": null,
    "retried": false,
    "approval_status": "not_required",
    "stop_reason": "ticket_status_returned",
    "terminal_outcome": "TICKET_STATUS_RETURNED"
  }
]
```

`customer_id` and `human_approval_token` are redacted before writing. This trace is your evidence that the system behaved correctly.

---

## 8. How All the Pieces Connect

Here is the complete picture with file names:

```
Customer request
      │
      ▼
demo_week5.py
  └─ creates AgentController(pipeline, ticket_store, approvals)
         │
         ├─── SimplePipeline (simple_pipeline.py)
         │      └─ loads chunks from load_project_corpus() (ingest.py)
         │             reads centenary_bank_faqs.csv + REGISTER.csv
         │
         ├─── ToolOrchestrator (orchestrator.py)
         │      registers 5 tools from tools.py:
         │        search_knowledge_base
         │        get_service_status
         │        get_ticket_status
         │        create_support_ticket
         │        escalate_support_case
         │
         └─── Planner (planner.py)
                calls Gemini REST API

AgentController.run(user_request, session)
      │
      └─ creates AgentState (agent_state.py)
      │
      └─ loop (max 4 iterations):
           │
           ├─ Planner.decide() → JSON action
           │
           ├─ Action gate (in agent_controller.py)
           │
           ├─ Tool call via ToolOrchestrator.call()
           │    └─ CallerContext from trusted session
           │
           ├─ Observe result, update AgentState
           │
           └─ trace_recorder.append_trace() → evidence/traces/week5/
      │
      └─ returns AgentState with final_response + terminal_outcome
```

---

## 9. Reading the Code in Order

Read the files in this sequence. Each one is short and self-contained.

### Week 3 — The RAG Pipeline

| Order | File | What to notice |
|---|---|---|
| 1 | `evidence/demo/centenary-RAG/ingest.py` | `Document` dataclass; `load_from_csvs()` — how raw CSV becomes structured data |
| 2 | `evidence/demo/centenary-RAG/chunk.py` | `Chunk` dataclass; why overlap matters; `chunk_id = "{doc_id}::{index}"` |
| 3 | `evidence/demo/centenary-RAG/index_store.py` | TF-IDF vectorizer; why the matrix shape is `(n_chunks, n_terms)` |
| 4 | `evidence/demo/centenary-RAG/retrieve.py` | Cosine similarity; the `min_score` threshold |
| 5 | `evidence/demo/centenary-RAG/context_builder.py` | `[S1]`, `[S2]` markers; `GroundedContext`; system instruction |
| 6 | `evidence/demo/centenary-RAG/pipeline.py` | How all five stages are wired into one object |

### Week 4 — Tools and Orchestration

| Order | File | What to notice |
|---|---|---|
| 7 | `evidence/demo/centenary-RAG/tools.py` | `ToolSpec`; `"source": "session"` in schema; `simulate_down` pattern |
| 8 | `evidence/demo/centenary-RAG/orchestrator.py` | The 8-step validation; `CallerContext`; why output is validated too |
| 9 | `tests/week4/test_tool_orchestrator.py` | Run these tests; read them as a specification of what the tools must do |

### Week 5 — The Agent Loop

| Order | File | What to notice |
|---|---|---|
| 10 | `evidence/demo/centenary-agent-week5/agent_state.py` | Which fields the model controls vs code controls |
| 11 | `evidence/demo/centenary-agent-week5/planner.py` | The system prompt; `_build_prompt()`; why we call the REST API not a SDK |
| 12 | `evidence/demo/centenary-agent-week5/trace_recorder.py` | Why tokens are redacted before writing |
| 13 | `evidence/demo/centenary-agent-week5/agent_controller.py` | Read `run()` method top to bottom; follow one iteration |
| 14 | `evidence/demo/centenary-agent-week5/simple_pipeline.py` | Same interface as `RagPipeline` — shows how interfaces enable swap-out |
| 15 | `evidence/demo/centenary-agent-week5/demo_week5.py` | The three scenarios; how a session dict is built |

---

## Key Insight to Remember

The LLM is powerful but untrustworthy with authority. The architecture in this project gives the LLM a very narrow job: **read context, choose one action from a fixed list, fill in non-sensitive arguments, explain your reasoning.** Everything else — executing the action, injecting identity, issuing tokens, counting iterations, writing traces, deciding when to stop — is done by Python code that does not hallucinate.

The model is the brain. The orchestrator is the hands. The brain tells the hands what to do. The hands decide whether it is safe to do it.
