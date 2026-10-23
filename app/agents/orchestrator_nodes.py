import json
from typing import Dict, Any, Optional
from pathlib import Path

from app.core.config import BASE_DIR, settings
from app.db.sqlite_client import get_job_by_id, save_job
from app.db.profile_schema import UserProfile
from app.agents.orchestrator_state import AgentState
from app.agents.matching.llm_reranker import evaluate_job_with_llm, JobMatchEvaluation
from app.agents.tailoring.generator import generate_tailored_resume, generate_tailored_cover_letter
from app.agents.tailoring.verifier import audit_tailored_document
from app.tools.document_exporter import (
    export_resume_docx,
    export_cover_letter_docx,
    export_resume_pdf,
    export_cover_letter_pdf
)
from app.tools.browser_manager import BrowserManager, LOCAL_TEST_FORM_URL, ensure_default_desktop
from app.agents.form_fill.ats_adapter import fill_ats_application


# Active interactive browser sessions (job_id -> BrowserManager)
ACTIVE_BROWSERS: Dict[str, BrowserManager] = {}


async def close_active_browser(job_id: str):
    """Gracefully closes a live headed browser session for a job."""
    bm = ACTIVE_BROWSERS.pop(job_id, None)
    if bm:
        try:
            await bm.close()
        except Exception:
            pass


def load_profile_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Loads candidate profile from ground truth JSON."""
    profile_path = BASE_DIR / "data" / "profile" / "profile.json"
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
        profile = UserProfile(**profile_data)
        
    job = get_job_by_id(state.job_id)
    if not job:
        raise ValueError(f"Job {state.job_id} not found in SQLite.")

    return {
        "profile": profile,
        "job": job,
        "current_step": "profile_loaded",
        "logs": state.logs + [f"Loaded profile for {profile.full_name} and job {job.title}."]
    }


async def match_job_node(state: AgentState) -> Dict[str, Any]:
    """Node 2: Evaluates job fit using Stage 2 LLM reranker (cached if pre-ranked)."""
    if state.job.llm_score is not None and state.job.llm_reasoning:
        score = int(state.job.llm_score)
        verdict = "strong_match" if score >= 80 else ("moderate_match" if score >= 60 else "no_match")
        eval_result = JobMatchEvaluation(
            match_score=score,
            verdict=verdict,
            matched_skills=["Grounded profile fit"],
            missing_requirements=[],
            explanation=state.job.llm_reasoning
        )
    else:
        eval_result = await evaluate_job_with_llm(state.job)
    is_match = eval_result.match_score >= 60

    status = "in_progress" if is_match else "rejected_mismatch"
    log_msg = f"Match evaluated: {eval_result.match_score}/100 ({eval_result.verdict}). Matched: {is_match}"

    return {
        "match_evaluation": eval_result,
        "is_matched": is_match,
        "workflow_status": status,
        "current_step": "job_matched",
        "logs": state.logs + [log_msg]
    }


async def tailor_application_node(state: AgentState) -> Dict[str, Any]:
    """Node 3: Generates role-tailored resume and cover letter citing chunk IDs."""
    resume = await generate_tailored_resume(state.job, state.profile)
    letter = await generate_tailored_cover_letter(state.job, state.profile)

    # Export high-quality ATS Word (.docx) and headless PDF (.pdf) files
    r_path = export_resume_docx(resume)
    l_path = export_cover_letter_docx(letter)
    r_pdf_path = None
    l_pdf_path = None
    try:
        r_pdf = await export_resume_pdf(resume)
        l_pdf = await export_cover_letter_pdf(letter)
        r_pdf_path = str(r_pdf)
        l_pdf_path = str(l_pdf)
    except Exception as e:
        print(f"[TailorNode] Headless PDF export notice: {e}")

    return {
        "tailored_resume": resume,
        "tailored_cover_letter": letter,
        "resume_docx_path": str(r_path),
        "cover_letter_docx_path": str(l_path),
        "resume_pdf_path": r_pdf_path,
        "cover_letter_pdf_path": l_pdf_path,
        "current_step": "application_tailored",
        "logs": state.logs + [f"Tailored resume and cover letter generated in DOCX and PDF for {state.job.company}."]
    }


async def verify_claims_node(state: AgentState) -> Dict[str, Any]:
    """Node 4: Adversarial Claim Verifier audits every claim against ChromaDB."""
    audit = await audit_tailored_document(state.tailored_resume)
    status = "in_progress" if audit.passed_audit else "failed_audit"

    return {
        "audit_report": audit,
        "workflow_status": status,
        "current_step": "claims_verified",
        "logs": state.logs + [f"Audit completed. Passed: {audit.passed_audit} ({audit.verified_claims}/{audit.total_claims} verified)."]
    }


async def fill_form_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 5: Universal Multi-ATS Form Filler (Greenhouse, Lever, Ashby, Custom).
    Autofills verified candidate resume contact fields and uploads tailored documents.
    Leaves screening and work auth for direct user review in Chromium.
    """
    ensure_default_desktop()
    bm = BrowserManager(headless=settings.HEADLESS_BROWSER)
    page = await bm.start()
    try:
        url_lower = (state.job.url or "").lower()

        # Determine target application URL
        if any(token in url_lower for token in ["nexussystems", "acme", "careers.", "example.com"]) or not state.job.url.startswith("http"):
            url = LOCAL_TEST_FORM_URL
        else:
            url = state.job.url

        # Detect ATS platform
        if "lever.co" in url_lower or state.job.platform == "lever":
            platform = "lever"
        elif "ashbyhq.com" in url_lower or state.job.platform == "ashby":
            platform = "ashby"
        else:
            platform = "greenhouse"

        await bm.goto(url)

        # Prepare plaintext cover letter for ATS textareas (Lever comments / Ashby coverLetter)
        letter = state.tailored_cover_letter
        cover_letter_text = None
        if letter:
            body = "\n\n".join(letter.body_paragraphs) if letter.body_paragraphs else ""
            cover_letter_text = (
                f"{letter.salutation}\n\n"
                f"{letter.opening_paragraph}\n\n"
                f"{body}\n\n"
                f"{letter.closing_paragraph}\n\n"
                f"{letter.sign_off}"
            )

        # Execute universal multi-ATS autofill
        report = await fill_ats_application(
            page=page,
            job_id=state.job_id,
            profile=state.profile,
            resume_path=Path(state.resume_docx_path) if state.resume_docx_path else None,
            cover_letter_path=Path(state.cover_letter_docx_path) if state.cover_letter_docx_path else None,
            cover_letter_text=cover_letter_text,
            platform=platform
        )

        if not settings.HEADLESS_BROWSER:
            # Keep browser pop-up open for live user review & direct input
            ACTIVE_BROWSERS[state.job_id] = bm
        else:
            await bm.close()

        return {
            "form_report": report,
            "preview_screenshot_path": report.screenshot_path,
            "application_url": url,
            "workflow_status": "pending_approval",
            "current_step": "form_filled_ready_for_approval",
            "logs": state.logs + [f"Form populated ({report.fields_filled_count} fields) on {platform.capitalize()}. Preview saved. Waiting for human approval."]
        }
    except Exception:
        await bm.close()
        raise


def submit_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 6: Final Submission Node.
    EXECUTES ONLY IF human_approved == True.
    """
    if not state.human_approved:
        raise PermissionError("HARD CONSTRAINT VIOLATION: Cannot submit application without explicit human approval.")

    # Mark as applied in SQLite database
    state.job.status = "applied"
    save_job(state.job)

    return {
        "workflow_status": "applied",
        "current_step": "completed",
        "logs": state.logs + [f"APPLICATION APPROVED BY USER! Marked as applied in SQLite database."]
    }
