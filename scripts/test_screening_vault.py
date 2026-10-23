import asyncio
import json
import urllib.request
from pathlib import Path

from app.core.config import BASE_DIR
from app.db.profile_schema import UserProfile, ScreeningPreferences, FAQItem
from app.db.chunker import chunk_profile
from app.tools.browser_manager import BrowserManager, LOCAL_TEST_FORM_URL
from app.tools.field_detector import detect_form_fields
from app.agents.form_fill.ats_adapter import fill_ats_application

async def run_screening_tests():
    print("=== Testing Screening & Work Authorization Vault ===")

    # 1. Update Candidate Screening Preferences
    profile_path = BASE_DIR / "data" / "profile" / "profile.json"
    with open(profile_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    profile = UserProfile(**data)
    profile.screening = ScreeningPreferences(
        authorized_to_work=True,
        requires_sponsorship=False,
        notice_period="Immediate",
        willing_to_relocate=True,
        work_location_preference="Flexible",
        pronouns="She/Her",
        expected_salary="Negotiable",
        custom_qa=[
            FAQItem(question="Years of Python experience", answer="2+ years in academic and full-stack projects")
        ]
    )

    with open(profile_path, "w", encoding="utf-8") as f:
        f.write(profile.model_dump_json(indent=2))

    print("Step 1: Successfully saved screening preferences to profile.json")

    # 2. Verify Chunker indexing
    chunks = chunk_profile(profile)
    screening_chunks = [c for c in chunks if c.source_type == "screening"]
    print(f"Step 2: Chunker produced {len(screening_chunks)} screening chunks:")
    for sc in screening_chunks:
        print(f" - [{sc.chunk_id}] {sc.content[:70]}...")

    assert len(screening_chunks) >= 2, "Expected at least 2 screening chunks"

    # 3. Test Form Autofill with Screening Preferences
    print("\nStep 3: Testing live multi-ATS form autofill with work authorization...")
    bm = BrowserManager(headless=True)
    page = await bm.start()
    await bm.goto(LOCAL_TEST_FORM_URL)

    report = await fill_ats_application(
        page=page,
        job_id="test_screening_job",
        profile=profile,
        platform="greenhouse"
    )

    print(f"Report: status={report.status}, fields_filled={report.fields_filled_count}")
    
    # Check what was selected in #work_auth
    selected_val = await page.input_value("#work_auth")
    print(f"Work Auth select element value on page: '{selected_val}'")
    assert selected_val.lower() == "yes", f"Expected work_auth to be selected as 'yes', got '{selected_val}'"

    await bm.close()
    print("\nSUCCESS: Screening Vault correctly detected and autofilled verified work authorization!")

if __name__ == "__main__":
    asyncio.run(run_screening_tests())
