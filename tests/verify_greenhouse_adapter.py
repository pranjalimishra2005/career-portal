import json
import asyncio
from pathlib import Path

from app.db.profile_schema import UserProfile
from app.tools.browser_manager import BrowserManager, LOCAL_TEST_FORM_URL
from app.agents.form_fill.greenhouse_adapter import fill_greenhouse_application


async def main():
    with open("data/profile/profile.json", "r", encoding="utf-8") as f:
        profile = UserProfile(**json.load(f))

    resume_path = Path("data/exports/sample_backend_01_resume.docx")

    # Run in headless mode for quick verification
    bm = BrowserManager(headless=True)
    page = await bm.start()
    await bm.goto(LOCAL_TEST_FORM_URL)

    report = await fill_greenhouse_application(
        page=page,
        job_id="sample_backend_01",
        profile=profile,
        resume_path=resume_path
    )

    print("=== Greenhouse Adapter Execution Report ===")
    print(f"Status: {report.status}")
    print(f"Fields Filled: {report.fields_filled_count}")
    print(f"Security Barrier: {report.security_status.is_blocked}")
    print(f"Pending Questions for Human: {len(report.pending_human_questions)}")
    print(f"Preview Screenshot: {report.screenshot_path}")
    print(f"Summary: {report.summary}")

    await bm.close()


if __name__ == "__main__":
    asyncio.run(main())