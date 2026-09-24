"""
Working demonstration of both tools through the orchestration layer.

Covers:
  - Tool 1 (search_knowledge_base) success path
  - Tool 2 (create_support_ticket) blocked pending human approval, then
    succeeding once approved -- the higher-impact gate in action
  - Missing required parameter
  - Unauthorized caller
  - Downstream service unavailable (simulated for both tools)
  - Unexpected/malformed tool response (simulated for tool 2)

Run: python3 demo.py
"""

from chunk import Chunk
from pipeline import RagPipeline
from tools import make_search_knowledge_base_tool, make_create_support_ticket_tool
from orchestrator import ToolOrchestrator, CallerContext


def banner(title: str):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def show(label: str, response: dict):
    print(f"-- {label}")
    print(f"   {response}")


def main():
    # --- Set up Tool 1's engine: last week's RAG pipeline, with throwaway
    #     example chunks purely so this demo is runnable standalone.
    example_chunks = [
        Chunk(chunk_id="T01::0", doc_id="T01", doc_title="ATM card facts",
              text="Replacing a lost ATM card costs a small administrative fee and takes three working days."),
        Chunk(chunk_id="T02::0", doc_id="T02", doc_title="Branch hours",
              text="Branches are open Monday to Friday, 8am to 5pm, and Saturday mornings."),
    ]
    rag_pipeline = RagPipeline.from_chunks(example_chunks)

    kb_down = {"value": False}
    ticket_down = {"value": False}
    ticket_malformed = {"value": False}
    ticket_store: list[dict] = []

    tool1 = make_search_knowledge_base_tool(rag_pipeline, simulate_down=kb_down)
    tool2 = make_create_support_ticket_tool(ticket_store, simulate_down=ticket_down, simulate_malformed=ticket_malformed)

    orchestrator = ToolOrchestrator([tool1, tool2])

    guest = CallerContext(auth_level=1)                       # can read, cannot write
    agent = CallerContext(auth_level=2)                       # can request writes
    agent_approved = CallerContext(auth_level=2, human_approved=True)  # write, human signed off

    # -------------------------------------------------------------------
    banner("1. search_knowledge_base -- success path (low risk, no approval needed)")
    r = orchestrator.call("search_knowledge_base", {"query": "how much to replace a lost ATM card"}, guest)
    show("guest asks a question", r)
    assert r["status"] == "success" and r["result"]["results"], "expected a successful hit"

    # -------------------------------------------------------------------
    banner("2. create_support_ticket -- higher-impact tool blocked pending human approval")
    args = {"customer_ref": "CUST-4471", "subject": "Card not received",
            "description": "Customer says replacement ATM card never arrived after 10 days.", "priority": "high"}
    r = orchestrator.call("create_support_ticket", args, agent)
    show("agent requests a ticket (not yet approved)", r)
    assert r["status"] == "pending_approval"

    banner("3. create_support_ticket -- same request, now human-approved")
    r = orchestrator.call("create_support_ticket", args, agent_approved)
    show("same request, human_approved=True", r)
    assert r["status"] == "success" and "ticket_id" in r["result"]

    # -------------------------------------------------------------------
    banner("4. Failure mode: missing required parameter")
    r = orchestrator.call("search_knowledge_base", {}, guest)
    show("search with no query", r)
    assert r["status"] == "error" and r["error_type"] == "invalid_arguments"

    r = orchestrator.call("create_support_ticket", {"customer_ref": "CUST-1"}, agent_approved)
    show("create_ticket missing subject/description", r)
    assert r["status"] == "error" and r["error_type"] == "invalid_arguments"

    # -------------------------------------------------------------------
    banner("5. Failure mode: unauthorized request")
    r = orchestrator.call("create_support_ticket", args, guest)  # guest has auth_level 1, tool needs 2
    show("guest (auth_level=1) tries to create a ticket directly", r)
    assert r["status"] == "error" and r["error_type"] == "unauthorized"

    # -------------------------------------------------------------------
    banner("6. Failure mode: downstream service unavailable")
    kb_down["value"] = True
    r = orchestrator.call("search_knowledge_base", {"query": "branch hours"}, guest)
    show("knowledge base is down", r)
    assert r["status"] == "error" and r["error_type"] == "service_unavailable"
    kb_down["value"] = False  # restore for later use

    ticket_down["value"] = True
    r = orchestrator.call("create_support_ticket", args, agent_approved)
    show("ticketing backend is down", r)
    assert r["status"] == "error" and r["error_type"] == "service_unavailable"
    ticket_down["value"] = False

    # -------------------------------------------------------------------
    banner("7. Failure mode: unexpected/malformed tool response")
    ticket_malformed["value"] = True
    r = orchestrator.call("create_support_ticket", args, agent_approved)
    show("ticketing backend returns a record missing ticket_id", r)
    assert r["status"] == "error" and r["error_type"] == "unexpected_response"
    ticket_malformed["value"] = False

    # -------------------------------------------------------------------
    banner("8. Failure mode: unanswerable query -- not an error, empty result")
    r = orchestrator.call("search_knowledge_base", {"query": "what is today's forex rate for yen"}, guest)
    show("out-of-corpus question", r)
    assert r["status"] == "success" and r["result"]["results"] == []

    banner("All scenarios passed")
    print(f"Tickets actually created in this run: {len(ticket_store)}")
    for t in ticket_store:
        print("  ", t)


if __name__ == "__main__":
    main()
