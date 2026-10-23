import pytest
from app.core.config import BASE_DIR
from app.db.profile_schema import UserProfile, ScreeningPreferences, FAQItem
from app.db.chunker import chunk_profile
from app.tools.browser_manager import BrowserManager, LOCAL_TEST_FORM_URL
from app.agents.form_fill.ats_adapter import fill_ats_application


@pytest.fixture
def sample_profile_with_screening():
    profile = UserProfile(
        full_name="Suhani Khare",
        email="suhani@example.com",
        phone="+91 9876543210",
        location="Indore, India",
        linkedin="https://linkedin.com/in/suhanikhare",
        github="https://github.com/suhanikhare",
        screening=ScreeningPreferences(
            authorized_to_work=True,
            requires_sponsorship=False,
            notice_period="Immediate",
            willing_to_relocate=True,
            work_location_preference="Flexible",
            pronouns="She/Her",
            expected_salary="Negotiable",
            custom_qa=[
                FAQItem(question="Years of Python experience", answer="2+ years")
            ]
        )
    )
    return profile


def test_chunker_indexes_screening_preferences(sample_profile_with_screening):
    """Verify that chunk_profile indexes structured screening and work auth facts for RAG."""
    chunks = chunk_profile(sample_profile_with_screening)
    screening_chunks = [c for c in chunks if c.source_type == "screening"]
    
    assert len(screening_chunks) >= 2
    chunk_ids = [c.chunk_id for c in screening_chunks]
    assert "screening_0" in chunk_ids
    assert "screening_qa_0" in chunk_ids
    
    screening_text = " ".join([c.content for c in screening_chunks])
    assert "Legal Work Authorization: Yes" in screening_text
    assert "Visa Sponsorship Need: No" in screening_text
    assert "Notice Period / Earliest Availability: Immediate" in screening_text


@pytest.mark.asyncio
async def test_form_fill_uses_screening_preferences(sample_profile_with_screening):
    """Verify ATS form autofill selects work authorization dropdown based on verified vault preferences."""
    bm = BrowserManager(headless=True)
    page = await bm.start()
    try:
        await bm.goto(LOCAL_TEST_FORM_URL)
        report = await fill_ats_application(
            page=page,
            job_id="test_screening_job",
            profile=sample_profile_with_screening,
            platform="greenhouse"
        )
        assert report.status in ["filled_partial", "ready_for_approval", "ready_for_review"]
        selected_val = await page.input_value("#work_auth")
        assert selected_val.lower() == "yes"
    finally:
        await bm.close()
