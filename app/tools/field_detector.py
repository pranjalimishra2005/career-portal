import re
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from playwright.async_api import Page


class DetectedField(BaseModel):
    field_id: str = Field(..., description="DOM ID or generated unique identifier")
    selector: str = Field(..., description="CSS selector used by Playwright to locate the field")
    tag_name: str = Field(..., description="'input', 'select', or 'textarea'")
    input_type: str = Field(default="text", description="'text', 'email', 'tel', 'file', etc.")
    label_text: str = Field(..., description="Associated visible label text")
    is_required: bool = Field(default=False)
    options: List[str] = Field(default_factory=list, description="Dropdown options if tag is select")
    semantic_type: str = Field(
        ...,
        description="full_name | first_name | last_name | email | phone | resume_upload | cover_letter_upload | cover_letter_text | linkedin_url | github_url | work_auth | open_ended_question | unknown"
    )


def classify_field_semantic_type(label: str, name: str, input_type: str, tag: str) -> str:
    """
    Classifies a form element into a profile target based on its label, name, and attributes.
    Supports Greenhouse, Lever, Ashby, and custom ATS forms.
    """
    text = f"{label} {name}".lower()

    # Resume Upload
    if input_type == "file" and ("resume" in text or "cv" in text):
        return "resume_upload"
    elif input_type == "file" and ("cover" in text and "letter" in text):
        return "cover_letter_upload"
    elif input_type == "file":
        return "resume_upload"

    # Split Names (Greenhouse standard)
    if "first name" in text or "given name" in text or name == "first_name":
        return "first_name"
    if "last name" in text or "family name" in text or "surname" in text or name == "last_name":
        return "last_name"

    # Full Name (Lever & Ashby standard: e.g. name="name", label="Full Name")
    if any(k in text for k in ["full name", "your name", "candidate name"]) or (name == "name" and "first" not in text and "last" not in text):
        return "full_name"

    # Contact Info
    if "email" in text or input_type == "email":
        return "email"
    if "phone" in text or "mobile" in text or input_type == "tel":
        return "phone"

    # Profiles & Portfolios
    if "linkedin" in text:
        return "linkedin_url"
    if "github" in text:
        return "github_url"

    # Cover Letter Text / Additional Comments
    if ("cover" in text and "letter" in text) or "comments" in text or "notes" in text:
        return "cover_letter_text"

    # Visa Sponsorship Screening
    if "sponsorship" in text or "sponsor" in text or ("require" in text and "visa" in text):
        return "visa_sponsorship"

    # Work Authorization Screening
    if any(k in text for k in ["authorized", "authorization", "legally", "right to work", "eligible to work", "work auth"]):
        return "work_auth"

    # Notice Period / Availability
    if any(k in text for k in ["notice period", "how soon can you start", "earliest start", "availability to start", "start date"]):
        return "notice_period"

    # Relocation Preference
    if "relocat" in text:
        return "relocation"

    # Preferred Pronouns
    if "pronoun" in text:
        return "pronouns"

    # Expected Salary / Compensation
    if any(k in text for k in ["expected salary", "salary expectation", "desired salary", "compensation requirement", "desired pay"]):
        return "salary_expectation"

    # Workplace / Location Preference
    if ("remote" in text or "hybrid" in text or "workplace" in text) and any(k in text for k in ["preference", "location", "mode"]):
        return "location_preference"

    # Open-ended questions
    if tag == "textarea" or len(label) > 35 or "describe" in text or "why" in text:
        return "open_ended_question"

    return "unknown"


async def detect_form_fields(page: Page) -> List[DetectedField]:
    """
    Scans the active Playwright page, finds all interactive inputs,
    and returns a structured list of classified DetectedField models.
    """
    detected_fields: List[DetectedField] = []

    elements = await page.query_selector_all("input, select, textarea")

    for idx, el in enumerate(elements):
        tag_name = await el.evaluate("el => el.tagName.toLowerCase()")
        input_type = (await el.get_attribute("type") or "text").lower()
        field_id = (await el.get_attribute("id") or f"field_{idx}")
        name_attr = (await el.get_attribute("name") or "")
        is_required = await el.evaluate("el => el.required || el.hasAttribute('aria-required')")

        if input_type in ["hidden", "submit", "button", "reset"]:
            continue

        label_text = ""
        if field_id:
            label_el = await page.query_selector(f"label[for='{field_id}']")
            if label_el:
                label_text = (await label_el.inner_text()).strip()

        if not label_text:
            label_text = await el.evaluate("""el => {
                const parent = el.closest('div');
                const lbl = parent ? parent.querySelector('label') : null;
                return lbl ? lbl.innerText : '';
            }""")

        if not label_text:
            label_text = (await el.get_attribute("placeholder") or name_attr or field_id)

        clean_label = re.sub(r"[\*\:]", "", label_text).strip()

        options = []
        if tag_name == "select":
            opt_elements = await el.query_selector_all("option")
            for opt in opt_elements:
                opt_text = (await opt.inner_text()).strip()
                if opt_text:
                    options.append(opt_text)

        selector = f"#{field_id}" if field_id and not field_id.startswith("field_") else (
            f"[name='{name_attr}']" if name_attr else f"{tag_name}:nth-of-type({idx+1})"
        )

        semantic_type = classify_field_semantic_type(
            label=clean_label,
            name=name_attr,
            input_type=input_type,
            tag=tag_name
        )

        detected_fields.append(DetectedField(
            field_id=field_id,
            selector=selector,
            tag_name=tag_name,
            input_type=input_type,
            label_text=clean_label,
            is_required=is_required,
            options=options,
            semantic_type=semantic_type
        ))

    return detected_fields