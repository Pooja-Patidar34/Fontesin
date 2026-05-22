"""Playwright drive script — opens the BU's company modal and captures
the new Contact Person + Certifying Consultant sections."""

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
EMAIL = "buser6@gmail.com"
PASSWORD = "verifypw123"
OUT = Path(__file__).parent / "verify_artifacts"
OUT.mkdir(exist_ok=True)


def main():
    findings = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
        page = ctx.new_page()

        # ---- Login ----
        page.goto(f"{BASE}/login/")
        page.fill('input[name="email"], input[name="username"]', EMAIL)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(OUT / "01_after_login.png"))
        print("after_login_url:", page.url)

        # ---- Company Database ----
        page.goto(f"{BASE}/companies/")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(OUT / "02_companies_list.png"), full_page=True)

        # Narrow the list to one row by submitting the name filter.
        page.goto(f"{BASE}/companies/?name=sell&country=GB&page=1")
        page.wait_for_load_state("networkidle")
        # If the filter didn't reduce to 1 row, fall back to the unfiltered list.
        rows = page.locator("table tbody tr")
        time.sleep(0.4)
        print("rows after filter:", rows.count())
        page.screenshot(path=str(OUT / "03_filtered_list.png"), full_page=True)

        # Trigger the View action directly — the click handler is document-
        # level so we don't need the dropdown to be visually open.
        result = page.evaluate(
            """
            (() => {
              const btn = document.querySelector('table tbody tr .view-company-btn');
              if (!btn) return 'no view btn';
              btn.click();
              return 'clicked ' + (btn.dataset.url || '?');
            })()
            """
        )
        print("click_result:", result)
        page.wait_for_selector("#companyModal.show", state="visible", timeout=5000)
        # Wait for the JS populator to fill the inputs and toggle sections.
        time.sleep(0.8)

        # Scroll the modal to where Contact / Consultant sections live.
        modal_body = page.locator("#companyModal .modal-body").first
        # Capture a screenshot of the modal in its initial state.
        page.screenshot(path=str(OUT / "04_modal_top.png"), full_page=True)

        # Scroll to the Contact Person heading and capture.
        page.evaluate(
            """
            const headings = document.querySelectorAll('#companyModal .section-title');
            for (const h of headings) {
              if ((h.textContent || '').includes('Contact Person')) { h.scrollIntoView({block:'start'}); break; }
            }
            """
        )
        time.sleep(0.4)
        page.screenshot(path=str(OUT / "05_contact_person.png"), full_page=True)

        # Scroll to the Certifying Consultant section.
        page.evaluate(
            """
            const headings = document.querySelectorAll('#companyModal .section-title');
            for (const h of headings) {
              if ((h.textContent || '').includes('Certifying Consultant')) { h.scrollIntoView({block:'start'}); break; }
            }
            """
        )
        time.sleep(0.4)
        page.screenshot(path=str(OUT / "06_certifying_consultant.png"), full_page=True)

        # Programmatic checks against the DOM so the verdict isn't pixel-only.
        report = page.evaluate(
            """
            (() => {
              const out = {};
              const fn = document.getElementById('id_contact_first_name');
              const ln = document.getElementById('id_contact_last_name');
              out.first_name_exists = !!fn;
              out.last_name_exists  = !!ln;
              out.first_name_readonly = !!(fn && (fn.readOnly || fn.disabled));
              out.last_name_readonly  = !!(ln && (ln.readOnly || ln.disabled));
              out.first_name_value = fn ? fn.value : null;
              out.last_name_value  = ln ? ln.value : null;
              const helperText = Array.from(document.querySelectorAll('#companyModal small.form-text'))
                .map(s => s.textContent.trim());
              out.has_maintained_helper = helperText.some(t => /Maintained by the certifying consultant/i.test(t));
              const sec = document.getElementById('company-consultant-section');
              out.consultant_section_present = !!sec;
              out.consultant_section_visible = sec ? sec.style.display !== 'none' : false;
              const cName = document.getElementById('company-consultant-name');
              const cEmail = document.getElementById('company-consultant-email');
              const cPhone = document.getElementById('company-consultant-phone');
              out.consultant_name  = cName  ? cName.value  : null;
              out.consultant_email = cEmail ? cEmail.value : null;
              out.consultant_phone = cPhone ? cPhone.value : null;
              out.consultant_name_readonly  = !!(cName  && (cName.readOnly  || cName.disabled));
              out.consultant_email_readonly = !!(cEmail && (cEmail.readOnly || cEmail.disabled));
              out.consultant_phone_readonly = !!(cPhone && (cPhone.readOnly || cPhone.disabled));
              return out;
            })()
            """
        )
        print("DOM_REPORT:", report)

        browser.close()

    print("findings:", findings)
    return 0


if __name__ == "__main__":
    sys.exit(main())