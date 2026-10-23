from typing import List, Optional
from pydantic import BaseModel, Field


class TailoredBulletPoint(BaseModel):
    text: str = Field(..., description="The tailored resume bullet point")
    source_chunk_ids: List[str] = Field(
        default_factory=list,
        description="IDs of profile chunks that prove this bullet point (e.g. ['exp_0', 'proj_0'])"
    )
    relevance_explanation: str = Field(
        ...,
        description="Why this specific bullet was highlighted for this target role"
    )


class TailoredWorkExperience(BaseModel):
    company: str
    role: str
    period: str
    bullets: List[TailoredBulletPoint] = Field(default_factory=list)


class TailoredProject(BaseModel):
    title: str
    technologies: List[str] = Field(default_factory=list)
    bullets: List[TailoredBulletPoint] = Field(default_factory=list)


class TailoredResume(BaseModel):
    target_job_id: str
    target_role: str
    target_company: str
    professional_summary: str = Field(
        ...,
        description="2-3 sentence summary tailored specifically to the target job description"
    )
    highlighted_skills: List[str] = Field(
        ...,
        description="Skills explicitly matching the job description"
    )
    experience: List[TailoredWorkExperience] = Field(
        default_factory=list,
        description="Work experience. Leave EMPTY [] if candidate has no prior employment."
    )
    projects: List[TailoredProject] = Field(
        default_factory=list,
        description="Real candidate projects matching the role."
    )


class TailoredCoverLetter(BaseModel):
    target_job_id: str
    company_name: str
    role_title: str
    salutation: str = Field(default="Dear Hiring Team,")
    opening_paragraph: str = Field(
        ...,
        description="States interest in role and company, aligned with real profile"
    )
    body_paragraphs: List[str] = Field(
        ...,
        description="2 paragraphs detailing relevant experience using only real profile facts"
    )
    closing_paragraph: str = Field(
        ...,
        description="Polite wrap-up and call to interview"
    )
    sign_off: str = Field(
        default="Sincerely,\nApplicant",
        description="Candidate formal sign-off including candidate real name"
    )


class ClaimVerificationResult(BaseModel):
    claim_text: str = Field(..., description="The specific factual claim extracted from text")
    is_supported: bool = Field(..., description="True if proven by profile facts, False if fabricated")
    cited_chunk_id: Optional[str] = Field(default=None, description="The chunk ID supporting this claim")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Verification confidence score")
    reason: str = Field(..., description="Explanation of why this claim is supported or rejected")


class VerificationAuditReport(BaseModel):
    document_type: str = Field(..., description="'resume' or 'cover_letter'")
    total_claims: int
    verified_claims: int
    unsupported_claims: int
    passed_audit: bool = Field(..., description="True if 100% of claims are verified, False otherwise")
    claims: List[ClaimVerificationResult]
    audit_summary: str