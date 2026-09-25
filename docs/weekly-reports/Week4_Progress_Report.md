# BSE4104 Emerging Trends in Software Engineering
## GROUP B - EVENING CLASS
### Week 4 Progress Report: Tools and Function Calling

**Reporting period:** 21-25 September 2026  
**Project:** Centenary Bank Customer Support AI Agent  
**ClickUp task IDs:** `123tp5x7wnu` (implementation), `123tp5x7wmq` (tool catalogue), `123tp5x7wq3` (failure and authorization tests), `123tp5x7wt6` (Walusimbi Ashraf - updated architecture and progress report)  
**Git baseline:** `4d511f0`

## 1. Objective

Week 4 moved the system beyond grounded answer generation by introducing explicit, bounded software tools. The model can request a tool, but the application/orchestration layer decides whether that request is valid, authorized and safe to execute. The implementation uses synthetic in-memory data and does not connect to live Centenary Bank systems.

## 2. Implementation completed

The team added a Python tool layer beside the Week 3 RAG pipeline. The `ToolOrchestrator` maintains an allow-list, validates input arguments against each tool schema, injects trusted session identity and approval data, checks authorization, executes the tool, validates the output and returns structured success or failure results.

Four tools are now defined in the Week 4 catalogue:

- `get_service_status` retrieves the status of supported digital and card services from synthetic demo data.
- `get_ticket_status` retrieves a ticket only when it belongs to the authenticated customer.
- `create_support_ticket` creates a low-risk simulated support ticket using the customer ID from the session rather than from model-supplied arguments.
- `escalate_support_case` submits a case for simulated human follow-up only after a valid, request-bound approval token and explicit human approval.

The catalogue records each tool's purpose, input and output schema, required authorization level and failure behaviour. The architecture has been updated in `docs/architecture/updated-agent-architecture.md` to show the new registry, validation, authorization, approval and structured-trace path between the agent and tool backends.

## 3. Failure, authorization and approval controls

The implementation tests missing and malformed parameters, unknown tools and service names, unauthenticated sessions, cross-customer ticket access, attempts to override the session customer ID, unavailable services and malformed downstream responses. Output validation prevents the orchestrator from reporting a malformed tool response as success.

Higher-impact escalation is separated from ordinary lookup and ticket creation. Without approval, the call returns `pending_approval`; the approval token is bound to the exact case reference, reason and urgency, and is consumed after successful use. Reusing a token for a changed request is rejected.

## 4. Evaluation evidence

The automated Week 4 suite contains 17 passing tests. It covers the four catalogue tools, authorization boundaries, input validation, unavailable services, malformed responses, human approval and backward compatibility with the earlier RAG search and ticket contracts.

Reproduction from the repository root:

```text
python -m unittest discover -s tests/week4 -v
python evidence/demo/centenary-RAG/demo.py
```

The detailed scenario results are recorded in `docs/evaluation/Week-4-Tool-QA.md`. The tool catalogue is `docs/requirements/Week4_Tool_Catalogue.docx`.

## 5. Integration with previous weeks

Week 2 supplied the Gemini foundation-model integration and versioned prompt. Week 3 supplied the controlled 24-record corpus, TF-IDF retrieval, grounded context and retrieval evaluation. Week 4 retains the RAG search contract and adds tools as a separate controlled capability, so the system can answer from approved evidence and request a bounded operational action without granting the model direct system access.

## 6. Limitations and next steps

The service data, ticket records, authentication context and approval tokens are fixtures for the academic demonstration. They are not production security controls or live bank integrations. The malformed ticket-response test also exposes a remaining idempotency risk: a backend could write a record and then return an incomplete response, so a retry might create a duplicate. A production implementation would add durable storage, idempotency keys, real identity validation, audit persistence and reconciliation.

Week 5 should use this tool layer in a bounded multi-step agent loop with explicit iteration limits, stop conditions, recovery behaviour and execution traces.

## 7. Team contribution evidence

The shared Git history records Yusuf580 implementing the tool orchestration and demo, Ssenoga Herman submitting the tool catalogue, Mariam Wambui updating the failure and authorization evidence, and Walusimbi Ashraf preparing the updated architecture and progress report. This report consolidates all four contributions and links them to the ClickUp task IDs above.
