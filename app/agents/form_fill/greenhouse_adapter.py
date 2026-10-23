from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from playwright.async_api import Page

from app.core.config import BASE_DIR
from app.db.profile_schema import UserProfile
from app.tools.field_detector import detect_form_fields, DetectedField
from app.agents.form_fill.security_guard import check_page_security, PageSecurityStatus
from app.agents.form_fill.form_filler import fill_form_field

SCREENSHOT_DIR = BASE_DIR / "data" / "exports"


class GreenhouseFillReport(BaseModel):
    job_id: str
    status: str = Field(
        default="ready_for_approval",
        description="'ready_for_approval', 'requires_human_input', or 'blocked_by_protection'"
    )
    security_status: PageSecurityStatus
    fields_filled_count: int
    screenshot_path: Optional[str] = None
    summary: str


async def fill_greenhouse_application(
    page: Page,
    job_id: str,
    profile: UserProfile,
    resume_path: Optional[Path] = None,
    cover_letter_path: Optional[Path] = None
) -> GreenhouseFillReport:
    """
    Autofills ONLY factual contact fields and document uploads present in the candidate resume.
    All custom questions, work authorizations, and surveys are deliberately left blank
    for direct human input in the live Chromium window.
    """
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_file = SCREENSHOT_DIR / f"{job_id}_form_preview.png"

    # 1. Security Check (Cloudflare / Turnstile Protection)
    security = await check_page_security(page)
    if security.is_blocked:
        try:
            await page.screenshot(path=str(screenshot_file), full_page=True)
        except Exception:
            pass
        return GreenhouseFillReport(
            job_id=job_id,
            status="blocked_by_protection",
            security_status=security,
            fields_filled_count=0,
            screenshot_path=str(screenshot_file),
            summary=f"Halted by Security Guard: {security.reason}"
        )

    # 2. Field Detection
    fields = await detect_form_fields(page)
    if not fields:
        try:
            await page.screenshot(path=str(screenshot_file), full_page=True)
        except Exception:
            pass
        return GreenhouseFillReport(
            job_id=job_id,
            status="requires_human_input",
            security_status=security,
            fields_filled_count=0,
            screenshot_path=str(screenshot_file),
            summary="No standard form fields detected on page."
        )

    # Prepare standard candidate data directly from profile
    name_parts = profile.full_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    filled_count = 0

    # 3. Fill ONLY Verified Resume Contact & File Fields
    for field in fields:
        if field.semantic_type == "first_name":
            await fill_form_field(page, field, first_name)
            filled_count += 1
        elif field.semantic_type == "last_name":
            await fill_form_field(page, field, last_name)
            filled_count += 1
        elif field.semantic_type == "email":
            await fill_form_field(page, field, profile.email)
            filled_count += 1
        elif field.semantic_type == "phone" and profile.phone:
            await fill_form_field(page, field, profile.phone)
            filled_count += 1
        elif field.semantic_type in ["linkedin", "linkedin_url"] and profile.linkedin_url:
            await fill_form_field(page, field, profile.linkedin_url)
            filled_count += 1
        elif field.semantic_type in ["github", "github_url"] and profile.github_url:
            await fill_form_field(page, field, profile.github_url)
            filled_count += 1

        # File Uploads (Resume & Cover Letter)
        elif field.semantic_type == "resume_upload" and resume_path and resume_path.exists():
            await fill_form_field(page, field, resume_path)
            filled_count += 1
        elif field.semantic_type == "cover_letter_upload" and cover_letter_path and cover_letter_path.exists():
            await fill_form_field(page, field, cover_letter_path)
            filled_count += 1

        # Screening questions, work auth, surveys: DELIBERATELY SKIPPED
        # Allows human to review and answer directly in Chromium.

    # 4. Preview Screenshot Capture
    try:
        await page.screenshot(path=str(screenshot_file), full_page=True)
    except Exception:
        pass

    return GreenhouseFillReport(
        job_id=job_id,
        status="ready_for_approval",
        security_status=security,
        fields_filled_count=filled_count,
        screenshot_path=str(screenshot_file),
        summary=f"Filled {filled_count} factual resume fields. Paused in Chromium for direct human review."
    )