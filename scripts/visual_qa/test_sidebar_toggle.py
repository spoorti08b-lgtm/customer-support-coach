from pathlib import Path
from playwright.sync_api import sync_playwright

# Resolve docs/screenshots/ relative to this script so the script works from
# any working directory and on any machine.
_REPO_ROOT = Path(__file__).resolve().parent
_OUT = _REPO_ROOT / "docs" / "screenshots"
_OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1366, "height": 768})
    pg.goto("http://localhost:8502", wait_until="domcontentloaded")
    pg.wait_for_selector(".app-title", timeout=30000)
    pg.wait_for_timeout(1500)

    # 1. Screenshot initially open
    pg.screenshot(path=str(_OUT / "verified_sidebar_open.png"))
    print("1. Saved verified_sidebar_open.png")

    # 2. Collapse sidebar
    collapse_btn = pg.locator('[aria-label="Collapse sidebar"]').first
    collapse_btn.click()
    pg.wait_for_timeout(1000)

    # 3. Screenshot collapsed (must see expand button chevron!)
    pg.screenshot(path=str(_OUT / "verified_sidebar_collapsed.png"))
    print("2. Saved verified_sidebar_collapsed.png")

    # 4. Find expand button
    expand_btn = pg.locator('[data-testid="stExpandSidebarButton"], [aria-label="Expand sidebar"]').first
    print("Expand button visible:", expand_btn.is_visible())
    print("Expand button rect:", expand_btn.bounding_box())
    expand_btn.click()
    pg.wait_for_timeout(1000)

    # 5. Screenshot reopened
    pg.screenshot(path=str(_OUT / "verified_sidebar_reopened.png"))
    print("3. Saved verified_sidebar_reopened.png")

    b.close()
