# Final Evaluation and Evidence Pack

**Project:** Group B - Centenary Bank AI Agentic Helpdesk  
**Course:** BSE4104 Emerging Trends in Software Engineering  
**Final release:** v1.0.0  
**Week:** 8 - Hardening, Final Release and Demonstration  
**ClickUp task ID:** 123tp5xf1rg

## 1. Purpose

This document is the index for the final evaluation and evidence pack. It connects each required engineering capability to the repository artifact, implementation, test, trace, or report that demonstrates it. Raw evidence remains in its original location so that a reviewer can inspect the source, reproduce the run, and distinguish implementation from generated results.

## 2. System under evaluation

The system is a bounded Centenary Bank helpdesk agent. It combines:

- A controlled knowledge corpus and RAG retrieval pipeline.
- Explicit tools for knowledge search, service status, ticket status, ticket creation, and approved escalation.
- A bounded sense-plan-act-observe workflow.
- Session-bound identity and persistent support-case memory.
- Named guardrails for scope, identity, evidence grounding, authorization, secrets, prompt injection, and iteration limits.
- Structured traces for retrieval, memory, tool calls, outcomes, latency, errors, and safety flags.

The deterministic evidence demos use `ScriptedPlanner` so that the results are reproducible without an API key. Live Gemini planning is documented separately and is not required to reproduce the evidence pack.

## 3. Evidence coverage matrix

| Requirement | Primary evidence | Verification |
|---|---|---|
| Problem, users, scope, and AI boundaries | `docs/requirements/Project_Charter_Final_3_Pages.docx`, `docs/requirements/User-Stories-and-Acceptance-Criteria.docx`, `docs/requirements/AI_Boundary_Matrix.docx` | Review the defined helpdesk workflow and prohibited actions |
| Foundation model and prompt engineering | `docs/requirements/Foundation Model Selection Centenary Helpdesk Agent.docx`, `docs/requirements/Prompt-Specification-v1.0.md`, `docs/evaluation/11-Case Prompt Evaluation Table v1.0.docx` | Review model rationale, prompt constraints, and baseline cases |
| Controlled corpus and RAG | `docs/requirements/Corpus_and_Source_Register.docx`, `docs/evaluation/Week-3-15-Case-RAG-Evaluation.md`, `evidence/traces/rag-evaluation.json` | Inspect provenance, retrieval results, grounding, and unsupported-answer cases |
| Tools and authorization | `docs/requirements/Week4_Tool_Catalogue.docx`, `docs/evaluation/Week-4-Tool-QA.md`, `tests/week4/test_tool_orchestrator.py` | Run Week 4 unit tests and inspect schemas/failure handling |
| Agent architecture and task contract | `docs/architecture/Week5-Agent-Architecture.md`, `docs/requirements/Week5_Agent_Task_Contract.md`, `evidence/traces/week5/` | Review the bounded loop, approved actions, limits, and traces |
| State and persistent memory | `docs/requirements/week6/Week6_State_Model.md`, `docs/requirements/week6/Week6_Memory_Design_and_Data_Handling_Note.md`, `docs/requirements/week6/mcp-interface-specification.md` | Run the Week 6 demo and inspect memory/state traces |
| 30-scenario evaluation | `docs/evaluation/week7/Week_7_AI_Agent_Evaluation_Simple_Test_Cases.md`, `evidence/traces/week7/week7-observability-evidence.json` | Run the Week 7 evaluation harness; confirm 30 scenarios are recorded |
| Observability and tracing | `evidence/traces/week7/README.md`, `evidence/traces/week7/week7-observability-evidence.json` | Inspect run IDs, scenario IDs, events, tool calls, latency, outcomes, and safety flags |
| Failure catalogue and re-test evidence | `docs/evaluation/week7/Week7_Failure_Catalogue.md` | Review five failure conditions, remediation, and linked re-test traces |
| Guardrails | `docs/evaluation/week7/Week7_Guardrail_Catalogue.md`, `evidence/demo/centenary-agent-week6/guardrails.py`, `evidence/traces/week7/guardrail-evidence.json` | Run the guardrail demo; confirm all 27 cases pass |
| Release instructions and limitations | `README.md`, `evidence/HOW_IT_WORKS.md` | Follow the reproducible run instructions and review stated limitations |

## 4. Evaluation results

### 4.1 Final scenario evaluation

The final evaluation set contains 30 scenarios in six groups:

- 5 normal cases (`N1`-`N5`)
- 5 edge cases (`E1`-`E5`)
- 5 incorrect-information cases (`I1`-`I5`)
- 5 adversarial cases (`A1`-`A5`)
- 5 tool-failure cases (`T1`-`T5`)
- 5 unauthorized-action cases (`U1`-`U5`)

The expected safety behavior is zero unsafe actions, no fabricated evidence, correct tool selection, explicit uncertainty where evidence is unavailable, and bounded handling of failures. The structured bundle is stored at `evidence/traces/week7/week7-observability-evidence.json`.

### 4.2 Guardrail evaluation

The guardrail catalogue covers 10 named controls and 27 deterministic test cases:

1. Action allow-list
2. Identity-injection prevention
3. Tool allow-list
4. Evidence grounding
5. Escalation approval gate
6. Memory-not-authorization
7. Credential non-disclosure
8. Scope boundary
9. Prompt-injection detection
10. Iteration limit

The guardrail evidence is stored at `evidence/traces/week7/guardrail-evidence.json`. The expected result is 27 passed cases and zero unsafe behavior.

### 4.3 Failure and remediation evidence

The failure catalogue records five controlled failure conditions and the response after remediation:

- Empty retrieval and grounding protection.
- Unicode input and Windows console portability.
- Missing ticket data and bounded clarification.
- Unsupported service identifiers and schema validation.
- Prompt injection and instruction-boundary protection.

The detailed records and re-test references are in `docs/evaluation/week7/Week7_Failure_Catalogue.md`.

## 5. Reproduction commands

Run from the repository root. The deterministic demos do not require an API key.

### Week 4 tool QA

```text
python -m unittest discover -s tests/week4 -v
```

### Week 6 memory/state demonstration

```text
python evidence/demo/centenary-agent-week6/demo_week6.py
```

### Week 7 guardrail evidence

```text
python evidence/demo/centenary-agent-week6/demo_guardrails.py
```

Expected result: all 27 guardrail cases pass and `evidence/traces/week7/guardrail-evidence.json` is written.

### Week 7 evaluation harness

```text
python -m unittest tests/week7/test_week7_evaluation_harness.py -v
```

Expected result: the 30 scenario definitions are loaded and the observability bundle is written to `evidence/traces/week7/week7-observability-evidence.json`.

## 6. Release and security checks

- No production credentials or API keys are committed.
- The repository uses synthetic/demo customer and ticket data.
- Customer identity is taken from trusted session context, not model-generated arguments.
- Escalation requires human approval for the exact case, reason, and urgency.
- The agent cannot perform funds movement, loan decisions, account changes, or arbitrary code execution.
- Tool responses are validated before success is reported.
- Iteration and retry limits prevent runaway execution.
- Traces redact secrets and record normalized error types rather than raw stack traces.

## 7. Known limitations

- The deterministic demonstrations use `ScriptedPlanner`; live Gemini planning requires a configured API key.
- The current memory implementation is in-process and loses state when the process exits.
- The RAG index uses TF-IDF and may miss paraphrased queries.
- The corpus is English-only and the application data is synthetic.
- The evaluation demonstrates bounded behavior for the defined scenarios; it is not a production banking security certification.

## 8. Final hand-off checklist

- [x] Final evaluation set and structured trace evidence are present.
- [x] Guardrail catalogue and guardrail evidence are present.
- [x] Failure catalogue links remediation to re-test evidence.
- [x] Reproduction commands are documented.
- [x] Known limitations and human-control boundaries are documented.
- [ ] Team adds the final presentation/deployment evidence and completes the ClickUp board.

## 9. Evidence ownership note

This pack is an index and review aid. The linked source files, tests, traces, screenshots, progress reports, and demos are the authoritative evidence artifacts. Reviewers should use the commit history and linked files to verify ownership, reproducibility, and the relationship between implementation and evaluation results.

