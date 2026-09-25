# Updated Agent Architecture - Week 4

This architecture extends the Week 3 grounded RAG flow with an allow-listed tool registry, deterministic validation, authorization, structured failures and a human approval gate for higher-impact actions.

```mermaid
flowchart TD
    U[Customer / support agent] --> UI[Website chat widget]
    UI --> ORCH[Agent orchestration layer]
    ORCH --> LLM[Gemini foundation model]
    ORCH --> RAG[Approved RAG pipeline]
    RAG --> KB[(24-record controlled corpus)]
    ORCH --> REG[Tool registry and schema validator]
    REG --> AUTH[Session authentication and authorization]
    AUTH --> STATUS[get_service_status]
    AUTH --> LOOKUP[get_ticket_status]
    AUTH --> CREATE[create_support_ticket]
    AUTH --> APPROVAL{Human approval required?}
    APPROVAL -->|approved token| ESC[escalate_support_case]
    APPROVAL -->|not approved| DENY[Structured denial / pending approval]
    STATUS --> SERVICES[(Synthetic service-status data)]
    LOOKUP --> TICKETS[(Synthetic ticket store)]
    CREATE --> TICKETS
    ESC --> HANDOFF[Simulated human support handoff]
    LLM --> RESP[Grounded response with sources or tool result]
    RAG --> TRACE[Retrieval trace]
    REG --> TRACE2[Tool outcome and error trace]
    RESP --> UI
```

## Week 4 boundary

The model may request one of the four registered tools, but it cannot execute arbitrary functions or supply trusted identity and approval values. The orchestration layer injects session-bound `customer_id`, validates arguments and output, checks authorization, and converts failures into structured results. All service, ticket and escalation records are synthetic in-memory fixtures; no live banking system is accessed.

