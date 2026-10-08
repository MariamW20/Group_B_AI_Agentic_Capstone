yusuf@yusuf-Latitude-E6330:~/Desktop/Group_B_AI_Agentic_Capstone$ python3 evidence/demo/centenary-agent-week6/demo_week6.py
Week 6 Memory and State Demonstration
Centenary Bank Helpdesk Agent — BSE4104

############################################################
  SCENARIO: 1 — New customer creates a ticket  (watch memory_store write)
############################################################

  WHAT WE ARE TESTING:
    - CUST-99001 has no prior case history.
    - The agent creates a support ticket for their mobile banking crash.
    - AFTER the ticket is confirmed, the controller writes a case record
      to the MemoryStore.  The model does not do this — the controller does.
  

============================================================
  START — request_id=demo-week6-s1  customer=CUST-99001
============================================================
  Request: My mobile banking app keeps crashing every time I try to log in.
  [MEMORY_LOADED] no prior cases — fresh customer session
  [CLASSIFY_REQUEST] intent='create_ticket'  action=create_support_ticket  tool=create_support_ticket
  [SELECT_ACTION] APPROVED — action=create_support_ticket
  [EXECUTE_TOOL] calling create_support_ticket  args={'category': 'mobile_banking', 'description': 'Mobile banking app crashes on login screen on Android device.'}
  [OBSERVE_RESULT] tool=create_support_ticket status=success code=OK error_type=None
  [RESPOND] stop_reason=ticket_created  outcome=TICKET_CREATED
  [MEMORY_WRITE] case record stored for ticket CS-10246

============================================================
  COMPLETE — outcome=TICKET_CREATED
============================================================
  Response: Your support ticket has been created: CS-10246. Ticket CS-10246 has been created.

  PASSED — outcome=TICKET_CREATED
  Memory now contains 1 case for CUST-99001: CS-10246

############################################################
  SCENARIO: 2 — Returning customer  (memory gives continuity)
############################################################

  WHAT WE ARE TESTING:
    - CUST-88213 already has ticket CS-10245 in memory (pre-seeded above).
    - They return and ask "What is the update on my issue?" — no ticket ID given.
    - The planner reads memory_context (loaded by the controller) and uses the
      stored ticket_id CS-10245 directly.
    - The customer does NOT need to repeat their issue or ticket reference.
  

============================================================
  START — request_id=demo-week6-s2  customer=CUST-88213
============================================================
  Request: What is the update on my issue?
  [MEMORY_LOADED] 1 prior case(s) found for this customer
    ticket=CS-10245 status=in_progress category=mobile_banking
  [CLASSIFY_REQUEST] intent='ticket_status'  action=check_ticket_status  tool=get_ticket_status
  [SELECT_ACTION] APPROVED — action=check_ticket_status
  [EXECUTE_TOOL] calling get_ticket_status  args={'ticket_id': 'CS-10245'}
  [OBSERVE_RESULT] tool=get_ticket_status status=success code=OK error_type=None
  [RESPOND] stop_reason=ticket_status_returned  outcome=TICKET_STATUS_RETURNED

============================================================
  COMPLETE — outcome=TICKET_STATUS_RETURNED
============================================================
  Response: Ticket CS-10245 — Status: in_progress, Category: mobile_banking. Summary: Repeated mobile app login failures on Android.

  PASSED — outcome=TICKET_STATUS_RETURNED
  Memory context loaded on start — customer did NOT repeat their issue.
  memory_context count = 1

############################################################
  SCENARIO: 3 — Cross-customer access control  (session binds customer_id)
############################################################

  WHAT WE ARE TESTING:
    - CUST-HACKER asks for the status of CS-10245 (which belongs to CUST-88213).
    - customer_id in the tool call comes from SESSION (CUST-HACKER), NOT the message.
    - The ticket ownership check rejects this: status_code = UNAUTHORIZED.
    - Memory for CUST-HACKER is also empty — they cannot see CUST-88213's cases.
  

============================================================
  START — request_id=demo-week6-s3  customer=CUST-HACKER
============================================================
  Request: What is the status of ticket CS-10245?
  [MEMORY_LOADED] no prior cases — fresh customer session
  [CLASSIFY_REQUEST] intent='ticket_status'  action=check_ticket_status  tool=get_ticket_status
  [SELECT_ACTION] APPROVED — action=check_ticket_status
  [EXECUTE_TOOL] calling get_ticket_status  args={'ticket_id': 'CS-10245'}
  [OBSERVE_RESULT] tool=get_ticket_status status=success code=UNAUTHORIZED error_type=None
  [RESPOND] stop_reason=ticket_unauthorized  outcome=AUTHORIZATION_DENIED

============================================================
  COMPLETE — outcome=AUTHORIZATION_DENIED
============================================================
  Response: I can only access tickets that belong to your account.

  PASSED — outcome=AUTHORIZATION_DENIED
  CUST-HACKER memory: []  (correctly empty)
  customer_id in tool was CUST-HACKER, not CUST-88213 — access denied.

############################################################
  SCENARIO: 4 — Memory cannot auto-approve escalation
############################################################

  WHAT WE ARE TESTING:
    - CUST-88213 has CS-10245 in memory.
    - They request escalation.  The planner proposes request_escalation_approval.
    - The controller's approval gate runs even though memory shows the case exists.
    - Memory context is INFORMATION; it cannot authorize actions.
    - A simulated auto-approval then completes the escalation.
  

============================================================
  START — request_id=demo-week6-s4  customer=CUST-88213
============================================================
  Request: My issue has been open for 7 days. Please escalate it to a manager.
  [MEMORY_LOADED] 1 prior case(s) found for this customer
    ticket=CS-10245 status=in_progress category=mobile_banking
  [CLASSIFY_REQUEST] intent='escalation'  action=request_escalation_approval  tool=None
  [SELECT_ACTION] APPROVED — action=request_escalation_approval
  [REQUEST_APPROVAL] case=CS-10245 urgency=high
  NOTE: memory_context may show this case — it does NOT automatically approve escalation.

  [SIMULATED APPROVAL GATE]
    case=CS-10245  urgency=high
    reason=Issue unresolved for 7 days. Customer requests human review.
    Simulating: APPROVED
  [EXECUTE_TOOL] escalate_support_case (token=APPR-demo-we...)
  [RESPOND] stop_reason=escalated_after_approval  outcome=ESCALATED_AFTER_APPROVAL

============================================================
  COMPLETE — outcome=ESCALATED_AFTER_APPROVAL
============================================================
  Response: Your case has been escalated (ID: ESC-00001). Assigned to: Human Support Team.

  PASSED — outcome=ESCALATED_AFTER_APPROVAL
  Approval gate ran — memory alone could NOT trigger escalation.
  approval_status in state = 'approved'

============================================================
  MEMORY AUDIT LOG (all reads, writes, deletes this session)
============================================================
  [WRITE ] customer=CUST-88213      ticket=CS-10245   req=seed-request-001       ts=2026-10-08T09:13:26+00:00
  [READ  ] customer=CUST-99001      ticket=—          req=demo-week6-s1          ts=2026-10-08T09:13:26+00:00
  [WRITE ] customer=CUST-99001      ticket=CS-10246   req=demo-week6-s1          ts=2026-10-08T09:13:26+00:00
  [READ  ] customer=CUST-99001      ticket=—          req=verify-s1              ts=2026-10-08T09:13:26+00:00
  [READ  ] customer=CUST-88213      ticket=—          req=demo-week6-s2          ts=2026-10-08T09:13:26+00:00
  [READ  ] customer=CUST-HACKER     ticket=—          req=demo-week6-s3          ts=2026-10-08T09:13:26+00:00
  [READ  ] customer=CUST-HACKER     ticket=—          req=verify-s3              ts=2026-10-08T09:13:26+00:00
  [READ  ] customer=CUST-88213      ticket=—          req=demo-week6-s4          ts=2026-10-08T09:13:26+00:00

============================================================
  All four scenarios completed successfully.
  State model and memory lifecycle demonstrated.
============================================================