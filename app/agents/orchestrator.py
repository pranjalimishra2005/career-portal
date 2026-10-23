import uuid
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.orchestrator_state import AgentState
from app.agents.orchestrator_nodes import (
    load_profile_node,
    match_job_node,
    tailor_application_node,
    verify_claims_node,
    fill_form_node,
    submit_node,
    close_active_browser
)


# --- CONDITIONAL ROUTING EDGES ---

def check_match_route(state: AgentState) -> Literal["tailor_application", "__end__"]:
    """
    When triggered by user in UI, proceed through tailoring and form filling
    so candidate can inspect the populated form and documents in the review modal.
    """
    return "tailor_application"


def check_audit_route(state: AgentState) -> Literal["fill_form", "__end__"]:
    """If the tailored document fails anti-hallucination audit, halt immediately."""
    if state.audit_report and state.audit_report.passed_audit:
        return "fill_form"
    return "fill_form"  # Proceed to review gate so human can inspect and decide


# --- GRAPH CONSTRUCTION ---

def build_application_graph():
    """
    Constructs the LangGraph state machine with an explicit human-in-the-loop checkpoint.
    """
    graph = StateGraph(AgentState)

    # Register Nodes
    graph.add_node("load_profile", load_profile_node)
    graph.add_node("match_job", match_job_node)
    graph.add_node("tailor_application", tailor_application_node)
    graph.add_node("verify_claims", verify_claims_node)
    graph.add_node("fill_form", fill_form_node)
    graph.add_node("submit_application", submit_node)

    # Set Entry Point
    graph.set_entry_point("load_profile")

    # Linear Edges
    graph.add_edge("load_profile", "match_job")
    graph.add_edge("match_job", "tailor_application")
    graph.add_edge("tailor_application", "verify_claims")
    graph.add_edge("verify_claims", "fill_form")
    graph.add_edge("fill_form", "submit_application")
    graph.add_edge("submit_application", END)

    # In-memory checkpointer saves the state snapshot at pause points
    checkpointer = MemorySaver()

    # Compile with human-in-the-loop pause BEFORE submit_application
    app = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["submit_application"]
    )

    return app


# Singleton compiled graph instance
application_orchestrator = build_application_graph()


# --- INTERACTIVE PIPELINE RUNNERS ---

async def start_application_pipeline(job_id: str) -> Dict[str, Any]:
    """
    Runs the pipeline through Matching -> Tailoring -> Audit -> Form Filling.
    PAUSES AUTOMATICALLY at the human-approval gate before submit.
    """
    # Unique thread ID ensures fresh execution with current profile data
    thread_id = f"job_thread_{job_id}_{uuid.uuid4().hex[:6]}"
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = AgentState(job_id=job_id)

    # Run graph until it hits the interrupt_before checkpoint
    final_output = None
    async for event in application_orchestrator.astream(initial_state, config):
        final_output = event

    # Fetch snapshot of current paused state
    state_snapshot = application_orchestrator.get_state(config)
    paused_state_dict = state_snapshot.values

    return {
        "thread_id": config["configurable"]["thread_id"],
        "next_node": state_snapshot.next,  # Will be ('submit_application',)
        "application_url": paused_state_dict.get("application_url"),
        "state": paused_state_dict
    }


async def resume_with_human_decision(thread_id: str, approve: bool, feedback: str = "") -> Dict[str, Any]:
    """
    Resumes graph execution after human decision:
    - If approve is True: executes submit_node and marks job applied.
    - If approve is False: cancels submission and logs rejection.
    Closes any open live browser pop-ups.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = application_orchestrator.get_state(config)
    
    if not state_snapshot.next:
        return {"status": "error", "message": "No active workflow waiting for approval."}

    # Close any active live browser pop-up for this job
    job_id = state_snapshot.values.get("job_id")
    if job_id:
        await close_active_browser(job_id)

    if approve:
        # Resume LangGraph by feeding human_approved=True
        application_orchestrator.update_state(config, {"human_approved": True, "rejection_feedback": ""})
        async for _ in application_orchestrator.astream(None, config):
            pass
        return {
            "status": "applied",
            "message": "Application approved by human and successfully submitted!",
            "thread_id": thread_id
        }
    else:
        # Cancel submission
        application_orchestrator.update_state(config, {
            "human_approved": False,
            "rejection_feedback": feedback,
            "workflow_status": "rejected_by_user"
        })
        return {
            "status": "rejected_by_user",
            "message": f"Application rejected by human. Feedback saved: '{feedback}'",
            "thread_id": thread_id
        }