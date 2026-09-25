"""QA tests for the four tool contracts in the Week 4 catalogue."""
import sys
import unittest
from pathlib import Path

DEMO = Path(__file__).resolve().parents[2] / "evidence" / "demo" / "centenary-RAG"
sys.path.insert(0, str(DEMO))

from orchestrator import CallerContext, ToolOrchestrator
from tools import (
    ToolSpec, default_service_data, make_get_service_status_tool,
    make_get_ticket_status_tool, make_create_support_ticket_tool,
    make_escalate_support_case_tool, make_search_knowledge_base_tool,
    make_legacy_create_support_ticket_tool,
)


class CatalogueToolTests(unittest.TestCase):
    def setUp(self):
        self.service_down = {"value": False}
        self.ticket_down = {"value": False}
        self.malformed = {"value": False}
        self.approvals = {}
        self.tickets = {
            "CS-10245": {"ticket_id": "CS-10245", "customer_id": "CUST-A", "status": "open",
                          "category": "mobile_banking", "created_at": "2026-09-24T10:00:00Z",
                          "last_updated": "2026-09-24T10:00:00Z", "summary": "Login fails repeatedly."},
            "CS-10246": {"ticket_id": "CS-10246", "customer_id": "CUST-B", "status": "open",
                          "category": "card_services", "created_at": "2026-09-24T10:00:00Z",
                          "last_updated": "2026-09-24T10:00:00Z", "summary": "Private ticket."},
        }
        self.tools = [
            make_get_service_status_tool(default_service_data(), self.service_down),
            make_get_ticket_status_tool(self.tickets, self.ticket_down),
            make_create_support_ticket_tool(self.tickets, self.ticket_down, self.malformed),
            make_escalate_support_case_tool(self.approvals, {"value": False}),
        ]
        self.runner = ToolOrchestrator(self.tools)
        self.caller = CallerContext(auth_level=2, customer_id="CUST-A")

    def test_registry_matches_all_four_catalogue_tool_names(self):
        self.assertEqual(set(self.runner.registry), {
            "get_service_status", "get_ticket_status", "create_support_ticket", "escalate_support_case"
        })

    def test_service_name_is_optional_and_returns_all_services(self):
        result = self.runner.call("get_service_status", {}, self.caller)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"]["status_code"], "OK")
        self.assertGreaterEqual(len(result["result"]["services"]), 1)

    def test_unknown_service_is_rejected(self):
        result = self.runner.call("get_service_status", {"service_name": "branch_network"}, self.caller)
        self.assertEqual(result["error_type"], "invalid_arguments")

    def test_missing_ticket_id_is_rejected(self):
        result = self.runner.call("get_ticket_status", {}, self.caller)
        self.assertEqual(result["error_type"], "invalid_arguments")

    def test_ticket_lookup_returns_only_callers_record(self):
        own = self.runner.call("get_ticket_status", {"ticket_id": "CS-10245"}, self.caller)
        other = self.runner.call("get_ticket_status", {"ticket_id": "CS-10246"}, self.caller)
        self.assertEqual(own["result"]["status_code"], "OK")
        self.assertEqual(other["result"], {"status_code": "UNAUTHORIZED", "ticket_id": "CS-10246"})
        self.assertNotIn("summary", other["result"])

    def test_customer_id_cannot_be_supplied_or_overridden_by_tool_arguments(self):
        result = self.runner.call("create_support_ticket", {
            "customer_id": "CUST-B", "category": "other", "description": "A sufficiently long issue description."
        }, self.caller)
        self.assertEqual(result["error_type"], "invalid_arguments")

    def test_create_ticket_requires_fields_and_enforces_description_bounds(self):
        missing = self.runner.call("create_support_ticket", {"category": "other"}, self.caller)
        too_short = self.runner.call("create_support_ticket", {"category": "other", "description": "short"}, self.caller)
        self.assertEqual(missing["error_type"], "invalid_arguments")
        self.assertEqual(too_short["error_type"], "invalid_arguments")
        self.assertEqual(len(self.tickets), 2)

    def test_unauthenticated_session_cannot_create_ticket(self):
        result = self.runner.call("create_support_ticket", {
            "category": "other", "description": "A sufficiently long issue description."
        }, CallerContext(auth_level=0))
        self.assertEqual(result["error_type"], "unauthorized")
        self.assertEqual(len(self.tickets), 2)

    def test_ticket_creation_uses_session_customer_and_succeeds(self):
        result = self.runner.call("create_support_ticket", {
            "category": "mobile_banking", "description": "Mobile app sign-in fails repeatedly this morning."
        }, self.caller)
        self.assertEqual(result["result"]["status_code"], "OK")
        self.assertEqual(self.tickets[result["result"]["ticket_id"]]["customer_id"], "CUST-A")

    def test_unavailable_service_returns_structured_error(self):
        self.service_down["value"] = True
        result = self.runner.call("get_service_status", {}, self.caller)
        self.assertEqual(result["error_type"], "service_unavailable")

    def test_unavailable_ticket_service_returns_structured_error(self):
        self.ticket_down["value"] = True
        result = self.runner.call("get_ticket_status", {"ticket_id": "CS-10245"}, self.caller)
        self.assertEqual(result["error_type"], "service_unavailable")

    def test_malformed_create_response_is_not_reported_as_success(self):
        self.malformed["value"] = True
        result = self.runner.call("create_support_ticket", {
            "category": "other", "description": "A sufficiently long issue description."
        }, self.caller)
        self.assertEqual(result["error_type"], "unexpected_response")
        self.assertNotIn("result", result)

    def test_escalation_requires_human_approval_token(self):
        args = {"case_reference": "CS-10245", "reason": "Suspected unauthorized account access.", "urgency": "high"}
        denied = self.runner.call("escalate_support_case", args, self.caller)
        self.assertEqual(denied["error_type"], "unauthorized")
        token = "APPR-test-01"
        self.approvals[token] = dict(args)
        pending = self.runner.call("escalate_support_case", args, CallerContext(auth_level=2, customer_id="CUST-A", human_approval_token=token))
        self.assertEqual(pending["status"], "pending_approval")
        approved = self.runner.call("escalate_support_case", args, CallerContext(auth_level=2, customer_id="CUST-A", human_approved=True, human_approval_token=token))
        self.assertEqual(approved["result"]["status_code"], "OK")
        self.assertEqual(approved["result"]["status"], "assigned")

    def test_approval_token_is_bound_to_approved_request(self):
        approved_args = {"case_reference": "CS-10245", "reason": "Suspected unauthorized account access.", "urgency": "high"}
        token = "APPR-test-02"
        self.approvals[token] = dict(approved_args)
        changed = dict(approved_args, urgency="low")
        result = self.runner.call("escalate_support_case", changed, CallerContext(auth_level=2, customer_id="CUST-A", human_approved=True, human_approval_token=token))
        self.assertEqual(result["result"]["status_code"], "UNAUTHORIZED")


    def test_legacy_search_knowledge_base_tool_is_retained(self):
        class Source:
            marker = "[S1]"
            doc_id = "FAQ-1"
            doc_title = "Demo FAQ"
            score = 0.9
            text = "Sample approved FAQ passage."
        class Pipeline:
            def answer(self, query, k=4):
                class Answer:
                    sources = [Source()]
                return Answer()
        legacy = make_search_knowledge_base_tool(Pipeline(), {"value": False})
        result = ToolOrchestrator([legacy]).call(
            "search_knowledge_base", {"query": "sample question"}, CallerContext(auth_level=1)
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"]["results"][0]["doc_id"], "FAQ-1")

    def test_legacy_ticket_contract_is_retained(self):
        store = []
        legacy = make_legacy_create_support_ticket_tool(store, {"value": False}, {"value": False})
        result = ToolOrchestrator([legacy]).call(
            "create_support_ticket_legacy",
            {"customer_ref": "CUST-OLD", "subject": "Old caller", "description": "Legacy contract still works."},
            CallerContext(auth_level=2, human_approved=True),
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"]["customer_ref"], "CUST-OLD")
        self.assertEqual(len(store), 1)

    def test_non_object_tool_response_is_handled_without_crashing(self):
        bad = ToolSpec("bad", "fixture", {}, {"reply": "string"}, 0, False, {}, lambda: None)
        result = ToolOrchestrator([bad]).call("bad", {}, CallerContext(auth_level=0))
        self.assertEqual(result["error_type"], "unexpected_response")


if __name__ == "__main__":
    unittest.main()
