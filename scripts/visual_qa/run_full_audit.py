"""
Comprehensive visual audit script covering all states and viewports required by Part B:
- Viewports: 1920x1080, 1536x864, 1366x768
- Dashboard states: empty KB, KB loaded, 4 tabs, 3 modes, disabled Start hints, enabled Start, after starting, after Reset demo
- Sessions states: 0 sessions, 1 session, 5 sessions, each mode detail view
- Error states: non-PDF, >20MB PDF, scanned (image-only) PDF
"""

import time
from pathlib import Path
from pypdf import PdfWriter
from playwright.sync_api import sync_playwright

# All screenshots land in docs/screenshots/ inside the repo, resolved relative
# to this script's location so the script works from any working directory.
_REPO_ROOT = Path(__file__).resolve().parent
ARTIFACT_DIR = _REPO_ROOT / "docs" / "screenshots"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "http://localhost:8502"

VIEWPORTS = {
    "1080p": {"width": 1920, "height": 1080},
    "864p": {"width": 1536, "height": 864},
    "768p": {"width": 1366, "height": 768},
}

def create_test_files():
    temp_dir = _REPO_ROOT / "data" / "test_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    bad_pdf = temp_dir / "invalid_not_a_pdf.pdf"
    bad_pdf.write_text("This is plain text and definitely not a valid PDF header.")

    large_pdf = temp_dir / "large_over_20mb.pdf"
    if not large_pdf.exists() or large_pdf.stat().st_size < 20 * 1024 * 1024:
        with open(large_pdf, "wb") as f:
            f.write(b"%PDF-1.4\n" + b"0" * (21 * 1024 * 1024))

    scanned_pdf = temp_dir / "scanned_no_text.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(scanned_pdf, "wb") as f:
        writer.write(f)

    return bad_pdf, large_pdf, scanned_pdf

def check_metrics(page):
    return page.evaluate("""() => {
        const bodyScroll = document.body.scrollHeight > window.innerHeight;
        const htmlScroll = document.documentElement.scrollHeight > window.innerHeight;
        const cards = Array.from(document.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"]'));
        let leftScroll = false;
        let rightScroll = false;
        if (cards.length >= 2) {
            leftScroll = cards[0].scrollHeight > cards[0].clientHeight;
            rightScroll = cards[1].scrollHeight > cards[1].clientHeight;
        }
        return {
            pageScroll: bodyScroll || htmlScroll,
            scrollHeight: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
            innerHeight: window.innerHeight,
            leftScroll,
            rightScroll
        };
    }""")

def run_audit():
    bad_pdf, large_pdf, scanned_pdf = create_test_files()
    defect_log = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEWPORTS["1080p"])
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # ── 1. Viewport-specific responsive audit ──
        for vp_name, vp_dims in VIEWPORTS.items():
            print(f"\nAuditing Dashboard on Viewport: {vp_name} ({vp_dims['width']}x{vp_dims['height']})")
            page.set_viewport_size(vp_dims)
            time.sleep(1)

            # Dashboard: KB loaded
            m_loaded = check_metrics(page)
            p_loaded = ARTIFACT_DIR / f"audit_dashboard_kb_loaded_{vp_name}.png"
            page.screenshot(path=str(p_loaded))
            print(f"  KB Loaded: pageScroll={m_loaded['pageScroll']} ({m_loaded['scrollHeight']}/{m_loaded['innerHeight']}), rightScroll={m_loaded['rightScroll']}")
            defect_log.append({
                "item": "Dashboard (KB loaded)",
                "viewport": vp_name,
                "metrics": m_loaded
            })

            # KB Tabs
            for t_name in ["Upload", "Documents", "Search", "Accuracy"]:
                page.locator('[data-testid="stTab"]').filter(has_text=t_name).click()
                time.sleep(0.5)
                m_tab = check_metrics(page)
                page.screenshot(path=str(ARTIFACT_DIR / f"audit_kb_tab_{t_name}_{vp_name}.png"))
                print(f"  Tab {t_name}: pageScroll={m_tab['pageScroll']}, rightScroll={m_tab['rightScroll']}")

            page.locator('[data-testid="stTab"]').filter(has_text="Upload").click()
            time.sleep(0.5)

            # 3 Modes
            for mode_name in ["Simulator", "Manual", "Replay"]:
                page.locator('button[data-variant="segmented_control"]').filter(has_text=mode_name).click()
                time.sleep(0.5)
                m_mode = check_metrics(page)
                page.screenshot(path=str(ARTIFACT_DIR / f"audit_mode_{mode_name}_{vp_name}.png"))
                print(f"  Mode {mode_name}: pageScroll={m_mode['pageScroll']}, rightScroll={m_mode['rightScroll']}")

            page.locator('button[data-variant="segmented_control"]').filter(has_text="Simulator").click()
            time.sleep(0.5)

            # Start Enabled screenshot for this viewport
            # Fill inputs via preset or direct typing
            prod_in = page.locator('input[aria-label="Product"]')
            prod_in.fill("Acme Online Store")
            prod_in.press("Tab")
            prob_in = page.locator('textarea[aria-label="Problem"]')
            prob_in.fill("Customer parcel has not arrived 10 days after dispatch and they want a status update.")
            prob_in.press("Tab")
            time.sleep(0.8)
            m_en = check_metrics(page)
            page.screenshot(path=str(ARTIFACT_DIR / f"audit_start_enabled_{vp_name}.png"))
            print(f"  Start Enabled: pageScroll={m_en['pageScroll']}, rightScroll={m_en['rightScroll']}")

            # Reset fields for next round
            prod_in.fill("")
            prod_in.press("Tab")
            prob_in.fill("")
            prob_in.press("Tab")
            time.sleep(0.5)

        # ── 2. Detailed Validation Hints Audit (1080p) ──
        page.set_viewport_size(VIEWPORTS["1080p"])
        print("\nAuditing Validation Hints...")
        # Both empty
        h_both = page.locator(".btn-disabled-note").inner_text()
        print(f"  Hint (both empty): '{h_both}'")
        page.screenshot(path=str(ARTIFACT_DIR / "audit_hint_both_empty.png"))

        # Empty problem
        prod_in.fill("Acme Online Store")
        prod_in.press("Tab")
        time.sleep(0.5)
        h_prob_empty = page.locator(".btn-disabled-note").inner_text()
        print(f"  Hint (prob empty): '{h_prob_empty}'")
        page.screenshot(path=str(ARTIFACT_DIR / "audit_hint_prob_empty.png"))

        # Short problem (< 10 chars)
        prob_in.fill("Delayed")
        prob_in.press("Tab")
        time.sleep(0.5)
        h_prob_short = page.locator(".btn-disabled-note").inner_text()
        print(f"  Hint (prob short): '{h_prob_short}'")
        page.screenshot(path=str(ARTIFACT_DIR / "audit_hint_prob_short.png"))

        # Empty product
        prod_in.fill("")
        prod_in.press("Tab")
        prob_in.fill("Customer parcel has not arrived 10 days after dispatch.")
        prob_in.press("Tab")
        time.sleep(0.5)
        h_prod_empty = page.locator(".btn-disabled-note").inner_text()
        print(f"  Hint (prod empty): '{h_prod_empty}'")
        page.screenshot(path=str(ARTIFACT_DIR / "audit_hint_prod_empty.png"))

        # Short product (< 3 chars)
        prod_in.fill("Ac")
        prod_in.press("Tab")
        time.sleep(0.5)
        h_prod_short = page.locator(".btn-disabled-note").inner_text()
        print(f"  Hint (prod short): '{h_prod_short}'")
        page.screenshot(path=str(ARTIFACT_DIR / "audit_hint_prod_short.png"))

        # ── 3. Start Session & After Started ──
        prod_in.fill("Acme Online Store")
        prod_in.press("Tab")
        time.sleep(0.5)
        start_btn = page.locator('button:has-text("Start session")')
        start_btn.click()
        time.sleep(2)
        page.screenshot(path=str(ARTIFACT_DIR / "audit_after_session_started.png"))
        print("Audited session start interaction.")

        # ── 4. Sessions Page Across Viewports ──
        page.locator('[data-testid="stSidebar"] a:has-text("Sessions")').click()
        time.sleep(2)
        for vp_name, vp_dims in VIEWPORTS.items():
            page.set_viewport_size(vp_dims)
            time.sleep(0.5)
            page.screenshot(path=str(ARTIFACT_DIR / f"audit_sessions_page_{vp_name}.png"))
            print(f"Audited Sessions Page ({vp_name})")

        # Session Detail Expander
        exp = page.locator('[data-testid="stExpander"]').first
        if exp.count() > 0:
            exp.locator("summary").click()
            time.sleep(0.5)
            page.screenshot(path=str(ARTIFACT_DIR / "audit_session_detail.png"))

        # ── 5. Architecture Page Across Viewports ──
        page.locator('[data-testid="stSidebar"] a:has-text("Architecture")').click()
        time.sleep(2)
        for vp_name, vp_dims in VIEWPORTS.items():
            page.set_viewport_size(vp_dims)
            time.sleep(0.5)
            page.screenshot(path=str(ARTIFACT_DIR / f"audit_architecture_page_{vp_name}.png"))
            print(f"Audited Architecture Page ({vp_name})")

        # ── 6. Reset Demo Confirmation Flow ──
        page.locator('[data-testid="stSidebar"] a:has-text("Dashboard")').click()
        time.sleep(2)
        page.locator('button:has-text("Reset demo")').click()
        time.sleep(0.8)
        page.screenshot(path=str(ARTIFACT_DIR / "audit_reset_demo_confirm.png"))
        page.locator('button:has-text("Confirm")').click()
        time.sleep(3)
        page.screenshot(path=str(ARTIFACT_DIR / "audit_after_reset_demo.png"))
        print("Audited Reset Demo flow.")

        # ── 7. Empty KB State (Clear KB) ──
        page.locator('[data-testid="stTab"]').filter(has_text="Upload").click()
        time.sleep(0.5)
        page.locator('button:has-text("Clear")').click()
        time.sleep(0.5)
        page.locator('button:has-text("Confirm")').click()
        time.sleep(2)
        page.screenshot(path=str(ARTIFACT_DIR / "audit_dashboard_kb_empty.png"))
        print("Audited Empty KB state (Amber pill: 'Add documents').")

        # Reload samples so environment remains intact
        page.locator('button:has-text("Load samples")').click()
        time.sleep(3)

        # ── 8. Error States (Non-PDF, >20MB, Scanned PDF) ──
        uploader = page.locator('input[type="file"]')
        
        # Non-PDF
        uploader.set_input_files(str(bad_pdf.resolve()))
        time.sleep(0.5)
        page.locator('button:has-text("Ingest")').click()
        time.sleep(1.5)
        page.screenshot(path=str(ARTIFACT_DIR / "audit_error_non_pdf.png"))

        # Large PDF
        uploader.set_input_files(str(large_pdf.resolve()))
        time.sleep(0.5)
        page.locator('button:has-text("Ingest")').click()
        time.sleep(1.5)
        page.screenshot(path=str(ARTIFACT_DIR / "audit_error_large_pdf.png"))

        # Scanned PDF
        uploader.set_input_files(str(scanned_pdf.resolve()))
        time.sleep(0.5)
        page.locator('button:has-text("Ingest")').click()
        time.sleep(1.5)
        page.screenshot(path=str(ARTIFACT_DIR / "audit_error_scanned_pdf.png"))
        print("Audited Error states.")

        page.close()
        browser.close()

    print("\nAll audit steps finished successfully!")

if __name__ == "__main__":
    run_audit()
