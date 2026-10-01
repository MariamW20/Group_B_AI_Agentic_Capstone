# Week 5 Agent Task Contract

**Project:** Centenary Bank Helpdesk Agent  
**Course:** BSE4104 Emerging Trends in Software Engineering  
**Week:** 5 - Agent Architecture and Bounded Autonomy  
**Deliverable:** Agent Task Contract  
**Status:** Specification for implementation

## 1. Agent task

The agent receives a Centenary Bank customer-support request and guides it to a safe, traceable resolution. It must use the approved knowledge base and application tools to understand the request, retrieve relevant information, check permitted current status, create a simulated support ticket when necessary, or prepare a case for human escalation.

The agent is not a general-purpose assistant. It may only perform the support tasks and tool calls defined in this contract.

## 2. Goal

For each authenticated customer request, the agent should:

1. Understand the customer's support need.
2. Retrieve relevant evidence from the approved knowledge base.
3. Decide whether the request can be answered directly or requires an approved tool.
4. Use the minimum number of tools needed to resolve the request.
5. Return a grounded answer, a ticket confirmation, or a clear human hand-off.
6. Stop safely when the request is outside scope, evidence is insufficient, a tool fails repeatedly, or human approval is required.

## 3. In-scope tasks

The agent may handle:

- Questions about supported Centenary Bank services and procedures using the approved knowledge base.
- Current status checks for supported demo services.
- Status checks for a support ticket belonging to the authenticated customer.
- Creation of a low-risk simulated support ticket using the authenticated customer session.
- Preparation and human-approved escalation of a support case.

## 4. Out-of-scope and prohibited tasks

The agent must not:

- Make account, loan, credit, fee, admissions, disciplinary, legal, or financial decisions.
- Approve transactions, change account details, transfer money, or control banking infrastructure.
- Retrieve or reveal another customer's ticket or personal information.
- Invent bank policies, service status, ticket details, or successful tool results.
- Use tools that are not in the approved allow-list.
- Execute arbitrary code, browse unrestricted websites, or perform arbitrary file or shell operations.
- Escalate a case without the required human approval.

## 5. Approved tools

| Tool | Purpose | Agent may call when | Side effect | Approval |
|---|---|---|---|---|
| `search_knowledge_base` | Retrieve relevant passages from the approved corpus | The request needs policy, procedure, or troubleshooting evidence | None | Not required |
| `get_service_status` | Retrieve the current status of a supported demo service | The customer asks whether a supported service is available | None | Not required |
| `get_ticket_status` | Check a ticket owned by the authenticated customer | The customer provides a ticket ID and requests its status | None | Not required |
| `create_support_ticket` | Create a low-risk simulated support ticket | The issue cannot be resolved directly and the customer provides enough details | Creates a simulated ticket | Not required |
| `escalate_support_case` | Submit a case to the human support team | The issue requires human intervention and the exact action has been approved | Creates a simulated escalation | Required |

The agent must not provide `customer_id` or `human_approval_token` as model-generated arguments. These values must be injected and validated by trusted orchestration code.

## 6. Required workflow

The agent follows this bounded loop:

**Sense/context -> Plan/decide -> Act/tool -> Observe -> Stop or re-plan**

### Step 1: Sense and classify

The agent reads the customer request and identifies the likely intent, such as:

- Knowledge or procedure question
- Service-status request
- Ticket-status request
- New support issue
- Escalation or human-help request
- Unsupported or unsafe request

If the request is ambiguous, the agent asks one focused clarification question before calling a tool.

### Step 2: Retrieve context

For knowledge or troubleshooting questions, the agent calls `search_knowledge_base` and uses the returned passages as the evidence for its response. If no reliable evidence is found, it must state that the approved knowledge base does not provide enough information and offer a human hand-off where appropriate.

### Step 3: Select an approved action

The agent chooses only one of the following actions:

- Answer from retrieved evidence.
- Check a supported service status.
- Check the authenticated customer's ticket status.
- Create a support ticket.
- Request human approval for escalation.
- Ask for clarification.
- Refuse or hand off an out-of-scope request.

### Step 4: Execute and observe

The orchestrator validates the tool name, arguments, authorization level, approval requirements, and tool response. The agent must inspect the structured result before producing its next response.

### Step 5: Stop or re-plan

The agent stops when a terminal condition is reached. It may re-plan only when the tool result shows that another approved step is necessary and the iteration limit has not been reached.

## 7. State contract

The workflow state must contain, at minimum:

| State field | Description | Source | Mutable by agent? |
|---|---|---|---|
| `request_id` | Unique identifier for the interaction | Trusted application | No |
| `customer_id` | Authenticated customer identity | Trusted session | No |
| `user_request` | Original customer message | User/application | No |
| `intent` | Classified support intent | Agent | Yes, with trace |
| `retrieved_evidence` | Knowledge-base passages and source markers | RAG tool | Append only |
| `planned_action` | Next approved action | Agent | Yes, with trace |
| `tool_calls` | Tool names, arguments, results, and statuses | Orchestrator | Append only |
| `attempt_count` | Number of agent iterations | Orchestrator | Increment only |
| `approval_status` | Not required, pending, approved, or denied | Trusted application/human | Controlled |
| `final_response` | Answer, confirmation, refusal, or hand-off | Agent | Set once at stop |
| `stop_reason` | Reason the workflow ended | Orchestrator/agent | Set once at stop |

The agent may propose an action, but trusted orchestration code remains responsible for identity, authorization, approval tokens, iteration limits, and tool execution.

## 8. Limits and guardrails

The initial implementation shall enforce these limits:

- Maximum of **4 agent iterations** for one customer request.
- Maximum of **1 retry per failed tool call** when retrying is safe.
- Only the five tools listed in Section 5 may be called.
- No tool arguments may override the authenticated session identity.
- No ticket details may be returned unless the ticket belongs to the authenticated customer.
- Escalation requires explicit human approval for the exact case reference, reason, and urgency.
- Approval tokens are single-use and must not be reused for a changed request.
- The agent must not claim that an action succeeded unless the tool returns a valid success response.
- Every tool call and terminal outcome must be recorded in the execution trace.

## 9. Stop conditions

The workflow must stop immediately when any of the following occurs:

1. A grounded answer has been produced from sufficient evidence.
2. A service or ticket status has been returned successfully.
3. A support ticket has been created and confirmed by a valid response.
4. Human escalation is approved and successfully submitted.
5. The customer request is outside the agent's scope.
6. Required information is missing and the agent cannot safely infer it.
7. A tool returns an authorization failure.
8. A tool remains unavailable after one safe retry.
9. A tool returns a malformed or unexpected response.
10. The maximum of four iterations is reached.

When stopping because of failure, the agent must explain the limitation without exposing internal secrets, raw stack traces, or another customer’s data.

## 10. Human hand-off and approval

The agent must hand off to a human when:

- The customer requests an action outside the approved tools.
- The issue involves a sensitive account, financial, legal, disciplinary, or safety decision.
- The knowledge base does not contain enough evidence for a reliable answer.
- A support issue needs investigation beyond the simulated ticket workflow.
- The customer requests escalation.

Before calling `escalate_support_case`, the agent must present the proposed case reference, reason, and urgency for human approval. The escalation tool may run only after trusted application code supplies a valid approval token tied to those exact values.

## 11. Failure and recovery behavior

| Failure | Agent response | Recovery |
|---|---|---|
| Missing required input | Ask the customer for the missing information | Continue only after clarification |
| Invalid tool arguments | Do not repeat the same invalid call | Correct the plan or ask for clarification |
| Unauthorized ticket request | Do not reveal ticket details | Explain that only the authenticated customer's ticket can be checked |
| Knowledge base unavailable | Report that evidence is temporarily unavailable | Retry once, then hand off or stop |
| Status/ticket service unavailable | Do not invent a result | Retry once, then report the limitation |
| Malformed tool response | Do not claim success | Stop safely and record the unexpected response |
| Escalation without approval | Do not execute escalation | Request human approval |
| Maximum iterations reached | Return a bounded failure message | Offer human support |

## 12. Expected terminal outcomes

Every execution must end with exactly one of these outcomes:

- `ANSWERED_FROM_KNOWLEDGE`
- `SERVICE_STATUS_RETURNED`
- `TICKET_STATUS_RETURNED`
- `TICKET_CREATED`
- `ESCALATED_AFTER_APPROVAL`
- `CLARIFICATION_REQUIRED`
- `OUT_OF_SCOPE_HANDOFF`
- `AUTHORIZATION_DENIED`
- `TOOL_FAILURE_HANDOFF`
- `ITERATION_LIMIT_REACHED`

The final response must include a human-readable explanation and must correspond to the recorded terminal outcome.

## 13. Acceptance criteria

This Agent Task Contract is satisfied when:

- The workflow has a clearly defined goal and scope.
- The agent uses only the approved tool allow-list.
- State, identity, authorization, and approval responsibilities are explicit.
- The workflow implements the Sense/Context -> Plan/Decide -> Act/Tool -> Observe -> Stop/Re-plan pattern.
- The agent has a maximum iteration limit and safe stop conditions.
- At least one failure/recovery path is defined and traceable.
- Human approval is required before escalation.
- The implementation can produce three traces: a successful grounded resolution, a successful ticket workflow, and a failure/recovery or human-handoff workflow.
