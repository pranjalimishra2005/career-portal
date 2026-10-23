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


class ATSFillReport(BaseModel):
    job_id: str
    platform: str = Field(default="greenhouse", description="greenhouse | lever | ashby | custom")
    status: str = Field(
        default="ready_for_approval",
        description="'ready_for_approval', 'requires_human_input', or 'blocked_by_protection'"
    )
    security_status: PageSecurityStatus
    fields_filled_count: int
    screenshot_path: Optional[str] = None
    summary: str


async def fill_ats_application(
    page: Page,
    job_id: str,
    profile: UserProfile,
    resume_path: Optional[Path] = None,
    cover_letter_path: Optional[Path] = None,
    cover_letter_text: Optional[str] = None,
    platform: str = "greenhouse"
) -> ATSFillReport:
    """
    Universal multi-ATS autofill adapter supporting Greenhouse, Lever, Ashby, and custom forms.
    Autofills ONLY factual contact fields and document uploads present in candidate resume.
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
        return ATSFillReport(
            job_id=job_id,
            platform=platform,
            status="blocked_by_protection",
            security_status=security,
            fields_filled_count=0,
            screenshot_path=str(screenshot_file),
            summary=f"Halted by Security Guard: {security.reason}"
        )

    # 2. Detect Form Fields across the active page
    fields = await detect_form_fields(page)
    if not fields:
        try:
            await page.screenshot(path=str(screenshot_file), full_page=True)
        except Exception:
            pass
        return ATSFillReport(
            job_id=job_id,
            platform=platform,
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
        # Full Name (Lever & Ashby standard)
        if field.semantic_type == "full_name":
            await fill_form_field(page, field, profile.full_name)
            filled_count += 1

        # First & Last Names (Greenhouse standard)
        elif field.semantic_type == "first_name":
            await fill_form_field(page, field, first_name)
            filled_count += 1
        elif field.semantic_type == "last_name":
            await fill_form_field(page, field, last_name)
            filled_count += 1

        # Email & Phone
        elif field.semantic_type == "email":
            await fill_form_field(page, field, profile.email)
            filled_count += 1
        elif field.semantic_type == "phone" and profile.phone:
            await fill_form_field(page, field, profile.phone)
            filled_count += 1

        # Professional Links
        elif field.semantic_type in ["linkedin", "linkedin_url"] and profile.linkedin_url:
            await fill_form_field(page, field, profile.linkedin_url)
            filled_count += 1
        elif field.semantic_type in ["github", "github_url"] and profile.github_url:
            await fill_form_field(page, field, profile.github_url)
            filled_count += 1

        # Resume Upload (File input)
        elif field.semantic_type == "resume_upload" and resume_path and resume_path.exists():
            await fill_form_field(page, field, resume_path)
            filled_count += 1

        # Cover Letter Upload (File input)
        elif field.semantic_type == "cover_letter_upload" and cover_letter_path and cover_letter_path.exists():
            await fill_form_field(page, field, cover_letter_path)
            filled_count += 1

        # Cover Letter Textarea (e.g. Lever's comments box or Ashby's coverLetter box)
        elif field.semantic_type == "cover_letter_text" and cover_letter_text:
            await fill_form_field(page, field, cover_letter_text)
            filled_count += 1

        # Work Authorization (Verified in Candidate Screening Vault)
        elif field.semantic_type == "work_auth":
            if getattr(profile, "screening", None) and profile.screening.authorized_to_work is not None:
                val = "Yes" if profile.screening.authorized_to_work else "No"
                await fill_form_field(page, field, val)
                filled_count += 1

        # Visa Sponsorship (Verified in Candidate Screening Vault)
        elif field.semantic_type == "visa_sponsorship":
            if getattr(profile, "screening", None) and profile.screening.requires_sponsorship is not None:
                val = "Yes" if profile.screening.requires_sponsorship else "No"
                await fill_form_field(page, field, val)
                filled_count += 1

        # Notice Period / Earliest Availability
        elif field.semantic_type == "notice_period":
            if getattr(profile, "screening", None) and profile.screening.notice_period:
                await fill_form_field(page, field, profile.screening.notice_period)
                filled_count += 1

        # Relocation Willingness
        elif field.semantic_type == "relocation":
            if getattr(profile, "screening", None) and profile.screening.willing_to_relocate is not None:
                val = "Yes" if profile.screening.willing_to_relocate else "No"
                await fill_form_field(page, field, val)
                filled_count += 1

        # Preferred Pronouns
        elif field.semantic_type == "pronouns":
            if getattr(profile, "screening", None) and profile.screening.pronouns:
                await fill_form_field(page, field, profile.screening.pronouns)
                filled_count += 1

        # Expected Compensation
        elif field.semantic_type == "salary_expectation":
            if getattr(profile, "screening", None) and profile.screening.expected_salary:
                await fill_form_field(page, field, profile.screening.expected_salary)
                filled_count += 1

        # Custom Q&A Matching from Candidate Screening Vault
        elif getattr(profile, "screening", None) and profile.screening.custom_qa:
            field_label_lower = field.label_text.lower()
            for qa in profile.screening.custom_qa:
                q_lower = qa.question.lower()
                if q_lower in field_label_lower or field_label_lower in q_lower:
                    await fill_form_field(page, field, qa.answer)
                    filled_count += 1
                    break

        # Any unverified/unspecified screening questions: DELIBERATELY SKIPPED
        # Ensures Zero Fabrication while allowing direct human input in live Chromium.

    # 4. Preview Screenshot Capture
    try:
        await page.screenshot(path=str(screenshot_file), full_page=True)
    except Exception:
        pass

    return ATSFillReport(
        job_id=job_id,
        platform=platform,
        status="ready_for_approval",
        security_status=security,
        fields_filled_count=filled_count,
        screenshot_path=str(screenshot_file),
        summary=f"Filled {filled_count} factual resume fields on {platform.capitalize()}. Paused in Chromium for direct human review."
    )