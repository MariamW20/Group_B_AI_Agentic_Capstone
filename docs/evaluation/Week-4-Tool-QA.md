# Week 4 Tool Failure and Authorization Tests

**Course week:** 21–25 September 2026  
**Test evidence date:** 24 September 2026  
**System under test:** `evidence/demo/centenary-RAG/tools.py`, `orchestrator.py`, and `demo.py`

## Scope and execution

The Python demo implements the four tools and names documented in [the Week 4 catalogue](../../Centenary_Bank_AI_Agent_Week4_Tool_Catalogue.docx). It also retains the earlier `search_knowledge_base` tool and the prior ticket schema as `create_support_ticket_legacy` for existing callers. Service status, ticket records, and escalations are synthetic in-memory data. They are not connected to Centenary Bank or Gemini.

Run from the repository root:

```sh
python3 -m unittest discover -s tests/week4 -v
python3 evidence/demo/centenary-RAG/demo.py
```

Latest automated run: **17 tests passed**. The standalone demonstration also completed all ten displayed scenarios, including an owned ticket lookup, a denied cross-customer lookup, ticket creation, escalation blocked without approval, and escalation after approval.

| Scenario | Expected result | Observed |
|---|---|---|
| `get_service_status` without optional service name | Returns monitored services | Pass |
| Invalid service name | `invalid_arguments`; no tool call | Pass |
| Missing ticket ID | `invalid_arguments` | Pass |
| Ticket belongs to caller | Returns ticket status | Pass |
| Ticket belongs to another customer | `UNAUTHORIZED`; no ticket details | Pass |
| Model supplies/overrides `customer_id` | Rejected; identity must come from session | Pass |
| Missing or short ticket description | `invalid_arguments`; no ticket created | Pass |
| Missing authenticated customer session | `unauthorized`; no ticket created | Pass |
| Valid support ticket creation | Uses session customer ID and returns confirmation | Pass |
| Status service unavailable | Structured `service_unavailable` error | Pass |
| Ticket service unavailable | Structured `service_unavailable` error | Pass |
| Ticket creation returns malformed response | `unexpected_response`; no success result returned | Pass |
| Escalation without approval token | `unauthorized`; no escalation submitted | Pass |
| Escalation with a valid token for that exact request | Success after human approval | Pass |
| Approval token reused for changed request | Tool returns `UNAUTHORIZED` | Pass |
| Legacy `search_knowledge_base` call | Existing RAG-backed search contract remains callable | Pass |
| Legacy ticket call (`customer_ref` / `subject`) | Backward-compatible ticket contract remains callable | Pass |

## Findings and safeguards

- Session-bound `customer_id` and the human approval token are injected by trusted orchestration context. Tool arguments cannot override either value.
- Ticket lookup checks record ownership before returning ticket fields. A cross-customer response contains no status, category, timestamp, or summary.
- Human approval is required for escalation. Tokens are bound to the approved case reference, reason, and urgency, and are consumed after use.
- Input validation enforces required fields, types, enumerations, and the catalogue's description/reason length limits. Output validation catches malformed objects and fields before results leave the orchestrator.
- The tools use only in-memory sample data. The service status values are explicitly marked as demo values; no response should be represented as a live bank result.

## Limitations

The malformed-ticket simulation models a response that goes wrong after the in-memory ticket write. It deliberately returns no success result, but a record may already exist; a retry can create a duplicate. A real ticket backend needs idempotency or reconciliation. Authentication levels, sessions, approval-token issuance, and all backends are fixtures for this academic demonstration, not production security controls.
