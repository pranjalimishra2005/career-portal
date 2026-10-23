from typing import List, Union, Optional
from pydantic import BaseModel, Field

from app.db.retriever import query_profile
from app.db.vector_store import get_profile_collection
from app.llm.factory import get_llm_provider
from app.agents.tailoring.schema import (
    TailoredResume,
    TailoredCoverLetter,
    ClaimVerificationResult,
    VerificationAuditReport
)


class ExtractedClaims(BaseModel):
    claims: List[str] = Field(
        ...,
        description="List of discrete historical factual claims (metrics, tools, accomplishments)"
    )


async def extract_atomic_claims(text: str) -> List[str]:
    """
    Extracts only historical factual assertions (metrics, technologies used, responsibilities).
    Ignores forward-looking statements of intent (e.g. 'excited to join company X').
    """
    prompt = f"""
Extract all discrete, historical factual claims from this text regarding past experience, metrics, tools used, and achievements.

RULES:
1. Extract only claims about past actions, technologies used, and quantifiable results.
2. Do NOT extract future-looking statements of interest or intent (e.g., 'eager to contribute to Company X').

TEXT:
{text}
"""
    llm = get_llm_provider()
    result = await llm.generate_structured(
        prompt=prompt,
        response_model=ExtractedClaims,
        system_instruction="Extract only verifiable past factual claims. Output valid JSON.",
        temperature=0.0
    )
    return result.claims


def get_chunk_by_id(chunk_id: str) -> Optional[str]:
    """Fetches exact chunk text directly by ID from ChromaDB."""
    try:
        collection = get_profile_collection()
        res = collection.get(ids=[chunk_id])
        if res and res.get("documents") and len(res["documents"]) > 0:
            return res["documents"][0]
    except Exception:
        pass
    return None


async def verify_claim(claim: str, expected_chunk_id: Optional[str] = None) -> ClaimVerificationResult:
    """
    Verifies a claim against candidate profile facts.
    Uses direct cited chunk lookup if available, otherwise falls back to semantic search.
    """
    evidence_text = ""
    cited_id = expected_chunk_id

    # 1. If a chunk was explicitly cited, fetch that chunk directly
    if expected_chunk_id:
        doc = get_chunk_by_id(expected_chunk_id)
        if doc:
            evidence_text = f"[Direct Citation {expected_chunk_id}]: {doc}"

    # 2. If no direct citation or not found, search top 4 semantic matches
    if not evidence_text:
        evidence = query_profile(query_text=claim, top_k=4)
        if evidence:
            cited_id = evidence[0].chunk_id
            evidence_text = "\n\n".join([f"[{e.chunk_id}]: {e.content}" for e in evidence])

    if not evidence_text:
        return ClaimVerificationResult(
            claim_text=claim,
            is_supported=False,
            cited_chunk_id=None,
            confidence=0.9,
            reason="No relevant facts found in candidate profile to support this claim."
        )

    # 3. Strict auditor evaluation
    verification_prompt = f"""
You are a strict anti-fraud auditor verifying a resume claim against verified profile facts.

CLAIM TO VERIFY:
"{claim}"

VERIFIED EVIDENCE FROM PROFILE:
"{evidence_text}"

AUDIT RULES:
1. Is the claim factually supported by the evidence?
2. If the claim mentions metrics, tools, or responsibilities NOT in the evidence, mark is_supported as FALSE.
3. Minor variations in wording are acceptable if the underlying fact is true.
"""

    class SingleClaimAudit(BaseModel):
        is_supported: bool
        confidence: float = Field(ge=0.0, le=1.0)
        reason: str

    llm = get_llm_provider()
    audit = await llm.generate_structured(
        prompt=verification_prompt,
        response_model=SingleClaimAudit,
        system_instruction="Strict factual auditor. Reject any unmentioned metrics or tools. Output valid JSON.",
        temperature=0.0
    )

    return ClaimVerificationResult(
        claim_text=claim,
        is_supported=audit.is_supported,
        cited_chunk_id=cited_id if audit.is_supported else None,
        confidence=audit.confidence,
        reason=audit.reason
    )


async def audit_tailored_document(
    doc: Union[TailoredResume, TailoredCoverLetter]
) -> VerificationAuditReport:
    """
    Conducts a comprehensive audit of all factual claims in a generated resume or cover letter.
    Passes ONLY if 100% of claims are verified.
    """
    doc_type = "resume" if isinstance(doc, TailoredResume) else "cover_letter"
    verified_results: List[ClaimVerificationResult] = []

    if isinstance(doc, TailoredResume):
        # Audit Summary Claims
        summary_claims = await extract_atomic_claims(doc.professional_summary)
        for claim in summary_claims:
            res = await verify_claim(claim)
            verified_results.append(res)

        # Audit Experience Bullets (using direct source_chunk_ids citations!)
        for exp in doc.experience:
            for bullet in exp.bullets:
                primary_id = bullet.source_chunk_ids[0] if bullet.source_chunk_ids else "exp_0"
                res = await verify_claim(bullet.text, expected_chunk_id=primary_id)
                verified_results.append(res)

        # Audit Project Bullets
        for proj in doc.projects:
            for bullet in proj.bullets:
                primary_id = bullet.source_chunk_ids[0] if bullet.source_chunk_ids else "proj_0"
                res = await verify_claim(bullet.text, expected_chunk_id=primary_id)
                verified_results.append(res)
    else:
        full_text = f"{doc.opening_paragraph}\n" + "\n".join(doc.body_paragraphs) + f"\n{doc.closing_paragraph}"
        claims = await extract_atomic_claims(full_text)
        for claim in claims:
            res = await verify_claim(claim)
            verified_results.append(res)

    # Compile audit report
    total = len(verified_results)
    verified = sum(1 for r in verified_results if r.is_supported)
    unsupported = total - verified
    passed = (unsupported == 0) and (total > 0)

    summary = (
        f"Audit Passed: All {total} claims verified against profile."
        if passed
        else f"Audit Failed: {unsupported} of {total} claims could not be verified against profile."
    )

    return VerificationAuditReport(
        document_type=doc_type,
        total_claims=total,
        verified_claims=verified,
        unsupported_claims=unsupported,
        passed_audit=passed,
        claims=verified_results,
        audit_summary=summary
    )