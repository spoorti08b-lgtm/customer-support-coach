from pathlib import Path
from playwright.sync_api import sync_playwright

# Resolve docs/screenshots/ relative to this script so the script works from
# any working directory and on any machine.
_REPO_ROOT = Path(__file__).resolve().parent
_OUT = _REPO_ROOT / "docs" / "screenshots"
_OUT.mkdir(parents=True, exist_ok=True)

p = sync_playwright().start()
b = p.chromium.launch()

pg = b.new_page(viewport={"width": 1366, "height": 768})
pg.goto("http://localhost:8502")
pg.wait_for_timeout(3000)
pg.screenshot(path=str(_OUT / "sidebar_open.png"))
print("Screenshot 1: sidebar open")

# Find collapse button
collapse_btn = pg.locator('[data-testid="stBaseButton-headerNoPadding"]').first
collapse_btn.click()
pg.wait_for_timeout(1500)
pg.screenshot(path=str(_OUT / "sidebar_collapsed.png"))
print("Screenshot 2: sidebar collapsed")

# Re-expand
expand_btn = pg.locator('[data-testid="stBaseButton-headerNoPadding"]').first
expand_btn.click()
pg.wait_for_timeout(1500)
pg.screenshot(path=str(_OUT / "sidebar_reopened.png"))
print("Screenshot 3: sidebar reopened")

b.close()
p.stop()
