import json
import pytest
from pathlib import Path

from app.db.profile_schema import UserProfile, SkillCategory
from app.tools.browser_manager import BrowserManager, LOCAL_TEST_FORM_URL
from app.tools.field_detector import detect_form_fields
from app.agents.form_fill.form_filler import autofill_application_form, SCREENSHOT_PATH


@pytest.fixture
def test_profile():
    profile_path = Path("data/profile/profile.json")
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            return UserProfile(**json.load(f))
    return UserProfile(
        full_name="Alex Morgan",
        email="alex.morgan@example.com",
        phone="+1 555-019-2834",
        location="San Francisco, CA",
        summary="Experienced Software Engineer with expertise in Python, FastAPI, and React.",
        education=[],
        experience=[],
        projects=[],
        skills=[
            SkillCategory(category="Technical", skills=["Python", "FastAPI", "React"])
        ]
    )


@pytest.mark.asyncio
async def test_field_detection_accuracy():
    """Verify that all standard ATS field types are correctly classified."""
    bm = BrowserManager(headless=True)
    page = await bm.start()
    try:
        await bm.goto(LOCAL_TEST_FORM_URL)
        fields = await detect_form_fields(page)

        types_found = {f.semantic_type for f in fields}
        expected_types = {
            "first_name", "last_name", "email", "phone",
            "resume_upload", "work_auth", "linkedin_url",
            "github_url", "open_ended_question"
        }
        assert expected_types.issubset(types_found)
    finally:
        await bm.close()


@pytest.mark.asyncio
async def test_form_autofill_and_preview_screenshot(test_profile, tmp_path):
    """
    Verify form filler sets DOM values accurately, attaches resume,
    creates preview screenshot, and NEVER clicks submit.
    """
    bm = BrowserManager(headless=True)
    page = await bm.start()
    try:
        await bm.goto(LOCAL_TEST_FORM_URL)
        fields = await detect_form_fields(page)

        resume_path = tmp_path / "test_resume.docx"
        resume_path.write_text("dummy resume content")

        result = await autofill_application_form(
            page=page,
            fields=fields,
            profile=test_profile,
            resume_path=resume_path
        )

        assert result["status"] == "ready_for_review"
        assert result["fields_filled_count"] >= 7

        # 1. Verify DOM input values directly in the browser
        name_parts = test_profile.full_name.split(" ", 1)
        assert await page.input_value("#first_name") == name_parts[0]
        if len(name_parts) > 1:
            assert await page.input_value("#last_name") == name_parts[1]
        assert await page.input_value("#email") == test_profile.email
        assert await page.input_value("#phone") == test_profile.phone
        assert (await page.input_value("#work_auth")).lower() in ["yes", "authorized", "1"]

        # 2. Verify open-ended RAG response was typed into textarea
        textarea_val = await page.input_value("#experience_summary")
        assert len(textarea_val) > 10

        # 3. Verify screenshot was saved
        assert SCREENSHOT_PATH.exists()
        assert SCREENSHOT_PATH.stat().st_size > 1000

        # 4. HARD SAFETY ASSERTION: Form was NOT submitted
        status_msg = await page.inner_text("#status-message")
        assert status_msg == ""  # Blank because submit button was untouched
    finally:
        await bm.close()
