import pytest
from pathlib import Path
from langgraph.graph import END

from app.db.job_schema import JobPosting
from app.db.sqlite_client import init_db, get_job_by_id, save_job
from app.tools.browser_manager import LOCAL_TEST_FORM_URL
from app.agents.orchestrator_state import AgentState
from app.agents.orchestrator_nodes import submit_node
from app.agents.orchestrator import (
    application_orchestrator,
    start_application_pipeline,
    resume_with_human_decision,
    check_match_route,
    check_audit_route
)
from app.agents.tailoring.schema import VerificationAuditReport


@pytest.fixture(autouse=True)
def setup_test_job():
    init_db()
    test_job = JobPosting(
        id="test_orchestrator_job",
        title="Full Stack Software Engineer",
        company="Tech Solutions",
        location="Remote",
        description="Seeking Python, FastAPI, and React engineer to build scalable web applications.",
        url=LOCAL_TEST_FORM_URL,
        platform="greenhouse",
        source="test",
        status="discovered"
    )
    save_job(test_job)
    return test_job


@pytest.mark.asyncio
async def test_orchestrator_pipeline_pauses_and_resumes(setup_test_job):
    """
    Test 1: Full pipeline execution through Matching -> Tailoring -> Audit -> Form Fill.
    Ensures:
      1. Graph automatically pauses at ('submit_application',).
      2. Human approval resumes execution and marks job as 'applied'.
    """
    job_id = setup_test_job.id
    run_result = await start_application_pipeline(job_id)

    thread_id = run_result["thread_id"]
    next_node = run_result["next_node"]
    state = run_result["state"]

    # Assert workflow paused at the approval checkpoint
    assert next_node == ("submit_application",)
    assert state["workflow_status"] == "pending_approval"
    assert state["human_approved"] is False

    # Assert prerequisites succeeded
    assert state["match_evaluation"].match_score >= 0
    assert state["audit_report"] is not None
    assert state["audit_report"].total_claims > 0
    assert state["audit_report"].verified_claims > 0
    assert Path(state["preview_screenshot_path"]).exists()

    # Step 2: Resume with human approval
    decision = await resume_with_human_decision(thread_id=thread_id, approve=True)
    assert decision["status"] == "applied"

    # Verify job status in SQLite
    updated_job = get_job_by_id(job_id)
    assert updated_job.status == "applied"


@pytest.mark.asyncio
async def test_orchestrator_human_rejection(setup_test_job):
    """
    Test 2: When the user declines to submit, the workflow cancels cleanly.
    """
    run_result = await start_application_pipeline(setup_test_job.id)
    thread_id = run_result["thread_id"]

    decision = await resume_with_human_decision(
        thread_id=thread_id,
        approve=False,
        feedback="Target salary is below expectations."
    )
    assert decision["status"] == "rejected_by_user"
    assert "Target salary is below expectations" in decision["message"]

    # Verify state snapshot in checkpointer records user rejection
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = application_orchestrator.get_state(config)
    assert snapshot.values["human_approved"] is False
    assert snapshot.values["workflow_status"] == "rejected_by_user"


def test_submit_node_hard_safety_constraint():
    """
    Test 3: submit_node MUST raise PermissionError if human_approved is False.
    """
    unapproved_state = AgentState(
        job_id="test_safety",
        human_approved=False
    )
    with pytest.raises(PermissionError, match="HARD CONSTRAINT VIOLATION"):
        submit_node(unapproved_state)


def test_conditional_routing_logic():
    """
    Test 4: Unit test the routing functions.
    """
    matched_state = AgentState(job_id="test", is_matched=True)
    assert check_match_route(matched_state) == "tailor_application"

    passed_audit = VerificationAuditReport(
        document_type="resume",
        total_claims=5,
        verified_claims=5,
        unsupported_claims=0,
        passed_audit=True,
        claims=[],
        audit_summary="All verified."
    )
    audit_pass_state = AgentState(job_id="test", audit_report=passed_audit)
    assert check_audit_route(audit_pass_state) == "fill_form"
