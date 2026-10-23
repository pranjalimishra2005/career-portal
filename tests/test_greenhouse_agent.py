import json
import pytest
from pathlib import Path

from app.db.profile_schema import UserProfile
from app.tools.browser_manager import BrowserManager, LOCAL_TEST_FORM_URL
from app.agents.form_fill.greenhouse_adapter import fill_greenhouse_application


@pytest.fixture
def profile_data():
    with open("data/profile/profile.json", "r", encoding="utf-8") as f:
        return UserProfile(**json.load(f))


@pytest.mark.asyncio
async def test_greenhouse_clean_form_fill_ready_for_approval(profile_data, tmp_path):
    """Verify clean form fills factual contact fields and stops before submit."""
    bm = BrowserManager(headless=True)
    page = await bm.start()
    try:
        await bm.goto(LOCAL_TEST_FORM_URL)
        resume_path = tmp_path / "test_resume.docx"
        resume_path.write_text("dummy resume content")

        report = await fill_greenhouse_application(
            page=page,
            job_id="test_gh_clean",
            profile=profile_data,
            resume_path=resume_path
        )

        assert report.status == "ready_for_approval"
        assert report.fields_filled_count >= 5
        assert report.security_status.is_blocked is False

        # Verify preview screenshot was created
        assert report.screenshot_path is not None
        assert Path(report.screenshot_path).exists()

        # Verify submit was NOT clicked
        status_text = await page.inner_text("#status-message")
        assert status_text == ""
    finally:
        await bm.close()


@pytest.mark.asyncio
async def test_greenhouse_halts_on_captcha(profile_data):
    """Verify agent immediately halts when CAPTCHA is detected."""
    bm = BrowserManager(headless=True)
    page = await bm.start()
    try:
        await bm.goto(LOCAL_TEST_FORM_URL)
        # Inject CAPTCHA challenge iframe
        await page.evaluate("""() => {
            const div = document.createElement('div');
            div.className = 'g-recaptcha';
            div.innerHTML = '<iframe src="https://www.google.com/recaptcha/api2/anchor"></iframe>';
            document.body.prepend(div);
        }""")

        report = await fill_greenhouse_application(
            page=page,
            job_id="test_gh_captcha",
            profile=profile_data
        )

        assert report.status == "blocked_by_protection"
        assert report.security_status.is_blocked is True
        assert report.security_status.block_type == "captcha"
        assert report.fields_filled_count == 0  # Zero fields touched
    finally:
        await bm.close()


@pytest.mark.asyncio
async def test_greenhouse_leaves_custom_questions_for_human(profile_data):
    """Verify custom/screening questions are deliberately untouched for user review."""
    bm = BrowserManager(headless=True)
    page = await bm.start()
    try:
        await bm.goto(LOCAL_TEST_FORM_URL)
        # Inject custom unanswerable question
        await page.evaluate("""() => {
            const div = document.createElement('div');
            div.className = 'form-group';
            div.innerHTML = '<label for="security_clearance">What is your active Top Secret military security clearance level? *</label><textarea id="security_clearance" name="security_clearance" rows="2"></textarea>';
            document.querySelector('#application-form').prepend(div);
        }""")

        report = await fill_greenhouse_application(
            page=page,
            job_id="test_gh_custom_unfilled",
            profile=profile_data
        )

        assert report.status == "ready_for_approval"
        # Verify custom question textarea remains empty for candidate to review
        textarea_val = await page.input_value("#security_clearance")
        assert textarea_val == ""
    finally:
        await bm.close()
