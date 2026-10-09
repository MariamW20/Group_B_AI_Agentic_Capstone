# Week 6 Memory Design and Data Handling Note

**Project:** Centenary Bank Helpdesk Agent  
**Course:** BSE4104 Emerging Trends in Software Engineering  
**Week:** 6 - Memory, State and Interoperability  
**Deliverable:** Memory Design and Data Handling Note

## 1. Memory use case

The agent uses one justified persistent-memory capability: an approved support-case history for the authenticated customer. The memory records limited information needed to continue a support conversation across sessions, such as a support ticket ID, issue category, short issue summary, ticket status, last action, and last-updated time.

This memory helps the agent avoid asking the customer to repeat the same issue and helps it retrieve the current status of an existing support case. It does not make a financial decision, change an account, approve a transaction, or replace a human support officer.

## 2. What is stored

| Data item | Reason for storage | Example | Sensitivity/control |
|---|---|---|---|
| `customer_id` reference | Associate a case with the authenticated customer | Session-bound customer reference | Access-controlled; never model-supplied |
| `ticket_id` | Find an existing support case | `CS-10245` | Visible only to the authenticated customer |
| `category` | Identify the type of issue | `mobile_banking` | Limited operational data |
| `summary` | Restore context without storing a full conversation | Short issue description | Minimized and validated |
| `status` | Continue an unresolved case | `open` or `assigned` | Read-only for the agent |
| `last_action` | Explain what has already happened | `ticket_created` | Append-only history |
| `last_updated` | Identify whether the record is current | UTC timestamp | Used for freshness checks |

The system must not store passwords, PINs, approval tokens, full account numbers, card security codes, unrestricted conversation transcripts, or unnecessary personal information.

## 3. Why memory is justified

Without persistent case history, a returning customer may need to repeat the same issue and ticket reference. Limited case memory improves continuity by allowing the agent to retrieve the relevant case summary and offer the next safe support step. The memory is narrowly related to customer support and is not a general profile used for personalization or automated financial decisions.

## 4. Access and authorization

- The authenticated customer may request the status of their own support case.
- The agent may read relevant case-history fields only after the customer session has been authenticated.
- The agent may not search memory by an arbitrary customer ID supplied in a message.
- The orchestrator binds `customer_id` to the trusted session and checks ownership before returning ticket details.
- Support staff may access case records according to the application's authorized support role.
- The model never receives passwords, PINs, approval tokens, or unrestricted customer records.
- Human approval is required before a case is escalated.

## 5. Retention and deletion

For this academic prototype, case-history memory is retained only for the active demonstration period and is stored in synthetic/in-memory or approved project-controlled data. A production implementation should define a documented retention period based on institutional policy and delete or anonymize records when that period expires.

Deletion requirements are:

1. A customer or authorized support officer can request deletion of an eligible case-history record.
2. Deletion removes the persistent memory record and any non-required derived copy.
3. Audit metadata should record that deletion occurred without retaining the deleted sensitive content.
4. Deletion must not remove records that are legally or operationally required without an authorized retention decision.
5. The agent must not recreate deleted memory from an old conversation unless the customer explicitly provides the information again and storage is authorized.

## 6. Data minimization and protection

- Store the smallest useful case summary rather than a complete conversation.
- Use synthetic data for demonstrations and tests.
- Validate fields before storage and reject unexpected fields.
- Keep session identity and approval tokens outside model-generated arguments.
- Restrict memory reads to the authenticated customer's records.
- Do not expose raw database errors, secrets, or internal identifiers unnecessarily.
- Record memory reads and writes in the workflow trace.
- Mark demo service status and ticket information as synthetic rather than live bank data.

## 7. Memory read/write behavior

### Read

At the start of a relevant support request, the system may retrieve case-history entries belonging to the authenticated customer. The agent uses the result only to understand the current case and choose an approved support action.

### Write

Memory is written only after a validated support event, such as creation of a simulated ticket or receipt of a confirmed ticket-status update. The write must include the request ID, timestamp, case reference, and event type. The agent may propose a memory update, but trusted application code validates and performs the write.

### No silent control

Memory can provide context, but it cannot automatically approve an escalation, override authorization, change customer identity, or determine a financial outcome. A current request and trusted authorization checks always take precedence over stored memory.

## 8. Demonstration scenario

1. Customer opens a support case about mobile banking.
2. The system creates a simulated ticket and stores the ticket ID, category, short summary, status, and timestamp.
3. The customer returns later and asks for an update.
4. The system authenticates the session and retrieves only that customer's case history.
5. The agent uses the stored ticket ID and status to respond without asking the customer to repeat the full issue.
6. If escalation is needed, the agent requests human approval; stored memory alone cannot trigger escalation.

## 9. Limitations

The current demonstration uses synthetic in-memory data and does not represent a production banking database, institutional retention policy, or production authentication system. A production version would require a secure database, access logging, encryption, formal deletion workflows, privacy review, and approved retention rules.

## 10. Acceptance criteria

This memory design is complete when:

- One legitimate persistent-memory use case is clearly defined.
- Stored fields and excluded fields are listed.
- The purpose of each stored field is explained.
- Access control, retention, deletion, and minimization rules are documented.
- A demonstration shows that memory improves support continuity.
- Memory cannot silently make critical decisions or bypass authorization.
- Synthetic/demo limitations are clearly stated.

