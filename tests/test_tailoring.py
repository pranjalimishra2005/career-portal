import pytest
from pathlib import Path

from app.db.sqlite_client import init_db, get_job_by_id, save_job
from app.tools.job_fetcher import get_sample_jobs
from app.agents.tailoring.generator import generate_tailored_resume, generate_tailored_cover_letter
from app.agents.tailoring.verifier import audit_tailored_document, verify_claim
from app.tools.document_exporter import (
    export_resume_docx,
    export_cover_letter_docx,
    export_resume_markdown,
    export_cover_letter_markdown,
    EXPORTS_DIR
)


@pytest.fixture(autouse=True)
def setup_data():
    init_db()
    jobs = get_sample_jobs(save_to_db=True)
    for j in jobs:
        save_job(j)


@pytest.mark.asyncio
async def test_tailored_resume_generation_and_audit():
    """Verify generated resume is grounded in real facts and passes 100% audit."""
    job = get_job_by_id("sample_backend_01")
    assert job is not None

    # 1. Generate tailored resume
    resume = await generate_tailored_resume(job)
    assert resume.target_role == job.title
    assert len(resume.highlighted_skills) > 0
    assert (len(resume.projects) > 0 or len(resume.experience) > 0)

    # Every bullet must cite a real profile chunk ID
    all_bullets = []
    for exp in resume.experience:
        all_bullets.extend(exp.bullets)
    for proj in resume.projects:
        all_bullets.extend(proj.bullets)

    for b in all_bullets:
        assert len(b.source_chunk_ids) > 0
        assert any(cid.startswith(("exp_", "proj_", "skill_")) for cid in b.source_chunk_ids)

    # 2. Audit against ChromaDB profile
    audit = await audit_tailored_document(resume)
    assert audit.passed_audit is True
    assert audit.unsupported_claims == 0
    assert audit.verified_claims == audit.total_claims


@pytest.mark.asyncio
async def test_fraud_detector_catches_unsupported_claim():
    """Verify adversarial claim verifier strictly rejects fabricated claims."""
    fake_claim = "Led a team of 15 engineers to migrate AWS infrastructure to Kubernetes."
    result = await verify_claim(fake_claim)

    assert result.is_supported is False
    assert result.cited_chunk_id is None
    assert len(result.reason) > 0


@pytest.mark.asyncio
async def test_document_export_creates_valid_files():
    """Verify professional DOCX and Markdown files are exported properly."""
    job = get_job_by_id("sample_backend_01")
    assert job is not None
    resume = await generate_tailored_resume(job)
    letter = await generate_tailored_cover_letter(job)

    r_docx = export_resume_docx(resume)
    l_docx = export_cover_letter_docx(letter)
    r_md = export_resume_markdown(resume)
    l_md = export_cover_letter_markdown(letter)

    assert r_docx.exists() and r_docx.stat().st_size > 5000  # Formatted Word doc
    assert l_docx.exists() and l_docx.stat().st_size > 5000
    assert r_md.exists() and r_md.stat().st_size > 100
    assert l_md.exists() and l_md.stat().st_size > 100
