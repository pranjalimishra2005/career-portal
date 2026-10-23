import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def run_test():
    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 12mm 15mm; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 10pt; color: #0f172a; line-height: 1.35; }
  .name { font-size: 18pt; font-weight: bold; text-align: center; margin-bottom: 4px; }
  .contact { text-align: center; font-size: 9pt; color: #475569; margin-bottom: 12px; }
  .sec { font-size: 10pt; font-weight: bold; text-transform: uppercase; border-bottom: 1px solid #cbd5e1; padding-bottom: 2px; margin: 10px 0 4px 0; }
  ul { padding-left: 18px; margin-top: 2px; }
  li { margin-bottom: 2px; color: #334155; }
</style>
</head>
<body>
  <div class="name">Pranjali Mishra</div>
  <div class="contact">pranjali@example.com • +91 9876543210 • Indore, India • linkedin.com/in/pranjalimishra</div>
  <div class="sec">Professional Summary</div>
  <p>Software Engineer specializing in Python, FastAPI, and machine learning pipelines.</p>
  <div class="sec">Technical Skills</div>
  <p><strong>Core Languages & Frameworks:</strong> Python, FastAPI, React, PostgreSQL, Docker, Playwright, Scikit-Learn</p>
  <div class="sec">Key Technical Projects</div>
  <p><strong>FoodBridge AI</strong> — <em>FastAPI, PostgreSQL, Scikit-Learn</em></p>
  <ul>
    <li>Engineered food redistribution microservices handling dynamic demand routing.</li>
    <li>Implemented predictive models reducing food wastage by 34%.</li>
  </ul>
</body>
</html>"""
    
    out_dir = Path("data/exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "sample_verification.pdf"
    
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.set_content(html, wait_until="networkidle")
    await page.pdf(path=str(out_file), format="A4", print_background=True)
    await browser.close()
    await pw.stop()
    print("SUCCESS: PDF created successfully at", out_file, "size:", out_file.stat().st_size)

if __name__ == "__main__":
    asyncio.run(run_test())
