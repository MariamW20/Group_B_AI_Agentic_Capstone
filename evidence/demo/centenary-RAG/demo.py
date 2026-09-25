"""Run the four catalogue-defined Week 4 tools with simulated data.

From this directory: python3 demo.py
"""
from tools import (
    default_service_data, make_get_service_status_tool,
    make_get_ticket_status_tool, make_create_support_ticket_tool,
    make_escalate_support_case_tool,
)
from orchestrator import ToolOrchestrator, CallerContext


def show(title, result):
    print(f"\n{title}\n{result}")


def main():
    service_down = {"value": False}
    ticket_down = {"value": False}
    create_malformed = {"value": False}
    escalation_down = {"value": False}
    tickets = {
        "CS-10245": {
            "ticket_id": "CS-10245", "customer_id": "CUST-88213",
            "status": "in_progress", "category": "mobile_banking",
            "created_at": "2026-09-20T10:02:00Z", "last_updated": "2026-09-21T14:30:00Z",
            "summary": "Repeated mobile app login failures.",
        },
        "CS-10246": {
            "ticket_id": "CS-10246", "customer_id": "CUST-OTHER",
            "status": "open", "category": "card_services",
            "created_at": "2026-09-20T10:02:00Z", "last_updated": "2026-09-21T14:30:00Z",
            "summary": "Private record for ownership-check demonstration.",
        },
    }
    approved = {}
    service_data = default_service_data()
    service_data["mobile_banking"]["status"] = "degraded"
    service_data["mobile_banking"]["message"] = "Simulated demo status; not live bank data."

    tools = [
        make_get_service_status_tool(service_data, service_down),
        make_get_ticket_status_tool(tickets, ticket_down),
        make_create_support_ticket_tool(tickets, ticket_down, create_malformed),
        make_escalate_support_case_tool(approved, escalation_down),
    ]
    runner = ToolOrchestrator(tools)
    customer = CallerContext(auth_level=2, customer_id="CUST-88213")

    show("1. get_service_status (specific service)", runner.call("get_service_status", {"service_name": "mobile_banking"}, customer))
    show("2. get_service_status (service_name omitted: all monitored services)", runner.call("get_service_status", {}, customer))
    show("3. get_ticket_status (ticket belongs to caller)", runner.call("get_ticket_status", {"ticket_id": "CS-10245"}, customer))
    show("4. get_ticket_status (different customer's ticket; no details returned)", runner.call("get_ticket_status", {"ticket_id": "CS-10246"}, customer))
    show("5. create_support_ticket", runner.call("create_support_ticket", {
        "category": "mobile_banking", "description": "Mobile banking sign-in fails repeatedly since this morning.",
        "channel": "chat", "suggested_priority": "medium",
    }, customer))

    escalation = {"case_reference": "CS-10245", "reason": "Customer reports suspected unauthorized account access.", "urgency": "high"}
    show("6. escalate_support_case without human approval", runner.call("escalate_support_case", escalation, customer))
    token = "APPR-demo-0001"
    approved[token] = dict(escalation)
    approved_context = CallerContext(auth_level=2, customer_id="CUST-88213", human_approved=True, human_approval_token=token)
    show("7. escalate_support_case after explicit human approval", runner.call("escalate_support_case", escalation, approved_context))

    service_down["value"] = True
    show("8. service status backend unavailable", runner.call("get_service_status", {}, customer))
    service_down["value"] = False
    show("9. required ticket_id missing", runner.call("get_ticket_status", {}, customer))
    show("10. unknown service name", runner.call("get_service_status", {"service_name": "branch_network"}, customer))

    print("\nDemo data is synthetic. Service status and ticket records are not connected to Centenary Bank systems.")


if __name__ == "__main__":
    main()
