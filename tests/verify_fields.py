import asyncio
from app.tools.browser_manager import BrowserManager, LOCAL_TEST_FORM_URL
from app.tools.field_detector import detect_form_fields


async def main():
    bm = BrowserManager(headless=True)
    page = await bm.start()
    await bm.goto(LOCAL_TEST_FORM_URL)
    
    fields = await detect_form_fields(page)
    print(f"Detected {len(fields)} form fields:")
    for f in fields:
        print(f" - [{f.semantic_type}] {f.selector} | Label: '{f.label_text}' (Req: {f.is_required})")
        
    await bm.close()


if __name__ == "__main__":
    asyncio.run(main())