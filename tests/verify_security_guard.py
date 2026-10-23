import asyncio
from app.tools.browser_manager import BrowserManager, LOCAL_TEST_FORM_URL
from app.agents.form_fill.security_guard import check_page_security


async def main():
    bm = BrowserManager(headless=True)
    page = await bm.start()

    print("--- Test 1: Clean Form Security Check ---")
    await bm.goto(LOCAL_TEST_FORM_URL)
    status1 = await check_page_security(page)
    print(f"Is Blocked: {status1.is_blocked} | Reason: {status1.reason}\n")

    print("--- Test 2: Injected CAPTCHA Detection ---")
    # Simulate a Cloudflare / Turnstile challenge appearing on the page
    await page.evaluate("""() => {
        const div = document.createElement('div');
        div.className = 'g-recaptcha';
        div.innerHTML = '<iframe src=\"https://www.google.com/recaptcha/api2/anchor\"></iframe>';
        document.body.prepend(div);
    }""")
    status2 = await check_page_security(page)
    print(f"Is Blocked: {status2.is_blocked} | Block Type: {status2.block_type}")
    print(f"Reason: {status2.reason}")
    print(f"Requires Human: {status2.requires_human_intervention}")

    await bm.close()


if __name__ == "__main__":
    asyncio.run(main())