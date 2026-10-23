from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field

from app.db.job_schema import JobPosting
from app.db.profile_schema import UserProfile
from app.agents.matching.llm_reranker import JobMatchEvaluation
from app.agents.tailoring.schema import TailoredResume, TailoredCoverLetter, VerificationAuditReport
from app.agents.form_fill.ats_adapter import ATSFillReport
from app.agents.form_fill.greenhouse_adapter import GreenhouseFillReport


class AgentState(BaseModel):
    """
    Central state shared across all nodes in the LangGraph application graph.
    """
    job_id: str
    job: Optional[JobPosting] = None
    profile: Optional[UserProfile] = None
    
    # Stage 1 & 2 Matching
    match_evaluation: Optional[JobMatchEvaluation] = None
    is_matched: bool = False
    
    # Tailoring & Anti-Hallucination Audit
    tailored_resume: Optional[TailoredResume] = None
    tailored_cover_letter: Optional[TailoredCoverLetter] = None
    audit_report: Optional[VerificationAuditReport] = None
    
    # File Paths & Direct Links
    resume_docx_path: Optional[str] = None
    cover_letter_docx_path: Optional[str] = None
    resume_pdf_path: Optional[str] = None
    cover_letter_pdf_path: Optional[str] = None
    preview_screenshot_path: Optional[str] = None
    application_url: Optional[str] = None
    
    # Form Filling & Safety
    form_report: Optional[Union[ATSFillReport, GreenhouseFillReport]] = None
    
    # Human-in-the-Loop Approval Gate
    human_approved: bool = False
    rejection_reason: Optional[str] = None
    
    # Overall Workflow Status
    current_step: str = "initialized"
    workflow_status: str = Field(
        default="in_progress",
        description="in_progress | rejected_mismatch | failed_audit | pending_approval | applied"
    )
    logs: List[str] = Field(default_factory=list)
