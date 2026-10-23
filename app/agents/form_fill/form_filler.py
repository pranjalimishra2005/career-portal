import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from playwright.async_api import Page

from app.core.config import BASE_DIR
from app.db.profile_schema import UserProfile
from app.db.retriever import query_profile
from app.llm.factory import get_llm_provider
from app.tools.field_detector import DetectedField

SCREENSHOT_PATH = BASE_DIR / "data" / "exports" / "preview_filled_form.png"


async def generate_rag_answer_for_question(question: str) -> str:
    """
    Answers an open-ended ATS screening question using ONLY real facts retrieved from ChromaDB.
    """
    # 1. Retrieve the most relevant facts for this specific question
    facts = query_profile(query_text=question, top_k=3)
    facts_text = "\n\n".join([f"- {f.content}" for f in facts])

    # 2. Prompt LLM to answer concisely and factually
    prompt = f"""
You are answering an application question on behalf of a job candidate.

QUESTION:
"{question}"

CANDIDATE FACTS (from real profile):
{facts_text}

RULES:
1. Answer concisely in 2-3 sentences.
2. Rely strictly on the provided candidate facts.
3. If no facts answer the question, state truthfully what experience the candidate has.
"""
    llm = get_llm_provider()
    answer = await llm.generate_text(
        prompt=prompt,
        system_instruction="Answer application screening questions truthfully and concisely. No fluff.",
        temperature=0.1
    )
    return answer.strip()


async def fill_form_field(page: Page, field: DetectedField, value: Any):
    """
    Interacts with the Playwright page to fill an individual field based on its tag and type.
    Supports select dropdowns, radio buttons, checkboxes, file uploads, textareas, and text inputs.
    """
    if field.tag_name == "select":
        val_str = str(value).strip().lower()
        matched_option = None

        # 1. Exact or partial option label match
        for opt in field.options:
            opt_lower = opt.strip().lower()
            if opt_lower == val_str or val_str in opt_lower or opt_lower in val_str:
                matched_option = opt
                break

        # 2. Boolean mapping: "yes" / "no"
        if not matched_option and val_str in ["true", "yes", "1"]:
            for opt in field.options:
                if any(y in opt.lower() for y in ["yes", "authorized", "require"]):
                    matched_option = opt
                    break
        elif not matched_option and val_str in ["false", "no", "0"]:
            for opt in field.options:
                if any(n in opt.lower() for n in ["no", "not authorized", "don't require", "do not"]):
                    matched_option = opt
                    break

        if matched_option:
            try:
                await page.select_option(field.selector, label=matched_option)
            except Exception:
                await page.select_option(field.selector, value=matched_option)
        elif field.options and len(field.options) > 1:
            try:
                await page.select_option(field.selector, index=1)
            except Exception:
                pass

    elif field.input_type == "radio":
        val_str = str(value).strip().lower()
        try:
            el = await page.query_selector(field.selector)
            if el:
                name_attr = await el.get_attribute("name")
                if name_attr:
                    radios = await page.query_selector_all(f"input[type='radio'][name='{name_attr}']")
                    for r in radios:
                        r_val = (await r.get_attribute("value") or "").lower()
                        r_id = await r.get_attribute("id") or ""
                        lbl_text = ""
                        if r_id:
                            lbl_el = await page.query_selector(f"label[for='{r_id}']")
                            if lbl_el:
                                lbl_text = (await lbl_el.inner_text()).lower()
                        if val_str in r_val or val_str in lbl_text:
                            await r.check()
                            return
            # Direct check if single element
            await page.check(field.selector)
        except Exception:
            pass

    elif field.input_type == "checkbox":
        try:
            should_check = value is True or str(value).strip().lower() in ["true", "yes", "1"]
            if should_check:
                await page.check(field.selector)
            else:
                await page.uncheck(field.selector)
        except Exception:
            pass

    elif field.input_type == "file":
        # File upload (e.g. resume or cover letter)
        file_path = str(value)
        if os.path.exists(file_path):
            await page.set_input_files(field.selector, file_path)

    elif field.tag_name == "textarea":
        await page.fill(field.selector, str(value))

    else:
        # Standard text/email/tel inputs
        await page.fill(field.selector, str(value))


async def autofill_application_form(
    page: Page,
    fields: List[DetectedField],
    profile: UserProfile,
    resume_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Maps profile data and RAG answers to all detected fields on the page.
    STOPS BEFORE SUBMISSION and captures a preview screenshot.
    """
    # Split name into first and last
    name_parts = profile.full_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    filled_data = {}

    for field in fields:
        val = None

        if field.semantic_type == "first_name":
            val = first_name
        elif field.semantic_type == "last_name":
            val = last_name
        elif field.semantic_type == "email":
            val = profile.email
        elif field.semantic_type == "phone":
            val = profile.phone
        elif field.semantic_type == "linkedin_url":
            val = profile.linkedin_url or ""
        elif field.semantic_type == "github_url":
            val = profile.github_url or ""
        elif field.semantic_type == "resume_upload":
            val = str(resume_path) if resume_path and resume_path.exists() else ""
        elif field.semantic_type == "work_auth":
            # Pre-approved FAQ answer: authorized without sponsorship
            val = "Yes"
        elif field.semantic_type == "open_ended_question":
            # Generate grounded answer via RAG
            val = await generate_rag_answer_for_question(field.label_text)

        if val:
            await fill_form_field(page, field, val)
            filled_data[field.label_text] = val

    # HARD SAFETY CONSTRAINT: DO NOT CLICK SUBMIT.
    # Capture a preview screenshot for human inspection
    SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)

    return {
        "status": "ready_for_review",
        "fields_filled_count": len(filled_data),
        "screenshot_path": str(SCREENSHOT_PATH),
        "details": filled_data
    }