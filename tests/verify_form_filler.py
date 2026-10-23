import json
import asyncio
from pathlib import Path
from app.db.profile_schema import UserProfile
from app.tools.browser_manager import BrowserManager, LOCAL_TEST_FORM_URL
from app.tools.field_detector import detect_form_fields
from app.agents.form_fill.form_filler import autofill_application_form


async def main():
    # Load profile data
    with open("data/profile/profile.json", "r", encoding="utf-8") as f:
        profile = UserProfile(**json.load(f))

    resume_path = Path("data/exports/sample_backend_01_resume.docx")

    # Launch browser in HEADED mode (so you can watch it fill live on your screen!)
    bm = BrowserManager(headless=False)
    page = await bm.start()
    await bm.goto(LOCAL_TEST_FORM_URL)

    fields = await detect_form_fields(page)
    result = await autofill_application_form(page, fields, profile, resume_path)

    print(f"Autofill Completed! Filled {result['fields_filled_count']} fields.")
    print(f"Screenshot saved to: {result['screenshot_path']}\n")
    print("Sample Filled Values:")
    for label, val in list(result["details"].items())[:4]:
        print(f" - {label}: {val}")

    # Keep browser open for 4 seconds so you can see it
    await asyncio.sleep(4)
    await bm.close()


if __name__ == "__main__":
    asyncio.run(main())