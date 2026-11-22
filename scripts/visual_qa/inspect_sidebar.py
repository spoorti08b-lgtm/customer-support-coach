from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("http://localhost:8502")
    pg.wait_for_timeout(3000)

    # Collapse sidebar
    collapse_btn = pg.locator('[aria-label="Collapse sidebar"]').first
    if collapse_btn.count() > 0:
        collapse_btn.click()
        pg.wait_for_timeout(1000)

    rules = pg.evaluate("""() => {
        const btn = document.querySelector('[data-testid="stExpandSidebarButton"]');
        let el = btn;
        const res = [];
        while (el && el !== document.body) {
            for (const sheet of Array.from(document.styleSheets)) {
                try {
                    for (const rule of Array.from(sheet.cssRules)) {
                        if (rule.selectorText && el.matches(rule.selectorText)) {
                            res.push({
                                el: el.tagName + '.' + el.className + '[' + el.getAttribute('data-testid') + ']',
                                selector: rule.selectorText,
                                css: rule.cssText
                            });
                        }
                    }
                } catch(e) {}
            }
            el = el.parentElement;
        }
        return res;
    }""")
    for r in rules:
        print(r)
    b.close()
