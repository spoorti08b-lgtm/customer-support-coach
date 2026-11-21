import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# Resolve paths relative to this script so the script works from any working
# directory and on any machine — no absolute user-specific paths.
_REPO_ROOT = Path(__file__).resolve().parent
DOCS_SCREENSHOTS = _REPO_ROOT / "docs" / "screenshots"
DOCS_SCREENSHOTS.mkdir(parents=True, exist_ok=True)

# Secondary output directory for intermediate/extra captures (kept local,
# ignored by .gitignore via docs/screenshots/screenshot_*.png pattern).
ARTIFACTS_DIR = DOCS_SCREENSHOTS

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        
        # ── 1. Dashboard at 1920x940 (Usable height budget test) ───────────
        page = await browser.new_page(viewport={"width": 1920, "height": 940})
        await page.goto("http://localhost:8502", wait_until="networkidle")
        await page.wait_for_timeout(3500)

        metrics_940 = await page.evaluate("""() => {
            const header = document.querySelector('.app-header-row');
            const stats = document.querySelector('.stat-card-row');
            const cards = Array.from(document.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"]'));
            const footer = document.querySelector('.app-footer');
            const main = document.querySelector('section.main') || document.querySelector('[data-testid="stAppViewContainer"]');
            const startBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText && b.innerText.includes('Start session'));
            
            return {
                windowHeight: window.innerHeight,
                headerHeight: header ? header.getBoundingClientRect().height : null,
                statsHeight: stats ? stats.getBoundingClientRect().height : null,
                cardHeights: cards.map(c => c.getBoundingClientRect().height),
                footerBottom: footer ? footer.getBoundingClientRect().bottom : null,
                startBtnBottom: startBtn ? startBtn.getBoundingClientRect().bottom : null,
                mainScrollHeight: main ? main.scrollHeight : null,
                mainClientHeight: main ? main.clientHeight : null,
                hasVerticalScroll: main ? (main.scrollHeight > main.clientHeight) : null,
            };
        }""")
        print("940px Usable Height Metrics:")
        import pprint
        pprint.pprint(metrics_940)

        dash_path = DOCS_SCREENSHOTS / "dashboard.png"
        await page.screenshot(path=str(dash_path))
        await page.screenshot(path=str(ARTIFACTS_DIR / "dashboard_final_940.png"))
        print(f"Saved Dashboard screenshot to {dash_path}")

        # ── 2. Dashboard at 1920x1080 ──────────────────────────────────────
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(ARTIFACTS_DIR / "dashboard_final_1080.png"))

        # ── 3. Sessions Page ───────────────────────────────────────────────
        nav_links = await page.query_selector_all('[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]')
        for link in nav_links:
            text = await link.inner_text()
            if "Sessions" in text:
                await link.click()
                break
        await page.wait_for_timeout(2500)
        sess_path = DOCS_SCREENSHOTS / "sessions.png"
        await page.screenshot(path=str(sess_path))
        await page.screenshot(path=str(ARTIFACTS_DIR / "sessions_final_1080.png"))
        print(f"Saved Sessions screenshot to {sess_path}")

        # ── 4. Architecture Page ───────────────────────────────────────────
        nav_links = await page.query_selector_all('[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]')
        for link in nav_links:
            text = await link.inner_text()
            if "Architecture" in text:
                await link.click()
                break
        await page.wait_for_timeout(2500)
        arch_path = DOCS_SCREENSHOTS / "architecture.png"
        await page.screenshot(path=str(arch_path))
        await page.screenshot(path=str(ARTIFACTS_DIR / "architecture_final_1080.png"))
        print(f"Saved Architecture screenshot to {arch_path}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
