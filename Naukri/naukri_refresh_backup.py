#!/usr/bin/env python3
"""
Naukri profile helper (runs locally on your Windows PC).

What it does:
- Opens Naukri in a visible Chromium browser.
- Reuses a saved browser session when possible.
- Gives you time to sign in and complete OTP/CAPTCHA yourself.
- Opens your profile page and saves the browser session.
- Optionally uploads a real resume file if NAUKRI_RESUME_PATH is set.

It does NOT bypass CAPTCHA/OTP, apply to jobs, or toggle invisible headline
whitespace to try to manipulate a profile-update timestamp.

Install:
    python -m pip install playwright
    python -m playwright install chromium

Run in PowerShell:
    $env:HEADLESS = "0"
    python .\\naukri_refresh.py

Optional resume upload:
    $env:NAUKRI_RESUME_PATH = "C:\\Users\\prath\\Documents\\Naukri\\YourResume.pdf"
    python .\\naukri_refresh.py

Keep naukri_state.json private: it may contain an authenticated session.
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "naukri_state.json"
LOG_FILE = HERE / "naukri_refresh.log"
SCREENSHOT_DIR = HERE / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
LOGIN_URL = "https://www.naukri.com/nlogin/login"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("naukri_profile_helper")


def screenshot(page, label):
    path = SCREENSHOT_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{label}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        log.info("Screenshot saved: %s", path.name)
    except Exception as exc:
        log.warning("Could not save screenshot: %s", exc)
    return path


def dashboard_visible(page):
    """Best-effort check for common profile/dashboard indicators."""
    try:
        if "nlogin" in page.url.lower():
            return False

        # Use several possible indicators rather than relying on one exact URL.
        indicators = [
            page.get_by_text("Profile performance", exact=False),
            page.get_by_text("Resume headline", exact=False),
            page.get_by_text("View profile", exact=False),
        ]
        for locator in indicators:
            try:
                if locator.first.is_visible(timeout=1200):
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def wait_for_manual_login(page, timeout_seconds=180):
    """Wait for the user to sign in normally in the visible browser."""
    print(
        "\nIf Naukri asks you to sign in, do so in the opened browser.\n"
        "Complete any OTP/CAPTCHA yourself. Do not share your password or OTP.\n"
        f"Waiting up to {timeout_seconds} seconds for the profile dashboard..."
    )
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        if dashboard_visible(page):
            print("Naukri dashboard detected.")
            log.info("Dashboard detected")
            return True
        page.wait_for_timeout(1000)

    screenshot(page, "login_or_dashboard_not_detected")
    print(
        "\nCould not automatically confirm the dashboard.\n"
        "Check the browser window and the screenshots folder. If you are visibly\n"
        "logged in, the site's page text may have changed; you can still inspect\n"
        "the browser before closing it."
    )
    log.warning("Dashboard not detected before timeout")
    return False


def upload_resume_if_configured(page):
    resume_value = os.environ.get("NAUKRI_RESUME_PATH", "").strip()
    if not resume_value:
        print(
            "\nNo NAUKRI_RESUME_PATH set, so no resume was uploaded.\n"
            "You can update your profile manually in the browser."
        )
        return False

    resume_path = Path(resume_value).expanduser()
    if not resume_path.is_file():
        raise FileNotFoundError(f"Resume file does not exist: {resume_path}")

    # Upload only when a file input is present. Do not guess at hidden UI actions.
    file_input = page.locator('input[type="file"]').first
    try:
        file_input.set_input_files(str(resume_path), timeout=10000)
    except PlaywrightTimeoutError as exc:
        screenshot(page, "resume_input_not_found")
        raise RuntimeError(
            "Could not find a resume upload input on the current profile page. "
            "Use the browser to locate the Update Resume control and upload "
            "your file manually."
        ) from exc

    page.wait_for_timeout(2500)
    log.info("Selected resume file for upload: %s", resume_path.name)
    print(f"Selected resume file: {resume_path.name}")
    print(
        "Check the browser and confirm that Naukri shows the upload as complete "
        "before considering the profile updated."
    )
    return True


def main():
    headless_value = os.environ.get("HEADLESS", "0").strip().lower()
    headless = headless_value in {"1", "true", "yes"}

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            context_options = {
                "viewport": {"width": 1366, "height": 900},
                "locale": "en-IN",
                "timezone_id": "Asia/Kolkata",
            }
            if STATE_FILE.is_file():
                context_options["storage_state"] = str(STATE_FILE)

            context = browser.new_context(**context_options)
            page = context.new_page()

            try:
                print("Opening your Naukri profile...")
                page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)

                if not dashboard_visible(page):
                    print("A signed-in dashboard was not confirmed.")
                    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
                    wait_for_manual_login(page)

                # After login, return to profile and allow the page to render.
                page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)

                if dashboard_visible(page):
                    try:
                        context.storage_state(path=str(STATE_FILE))
                        try:
                            STATE_FILE.chmod(0o600)
                        except OSError:
                            pass
                        log.info("Saved browser storage state")
                        print("Saved the browser session locally.")
                    except Exception as exc:
                        log.warning("Could not save browser state: %s", exc)

                    upload_resume_if_configured(page)
                    screenshot(page, "profile_opened")
                    print(
                        "\nProfile page opened. Review it in the browser and make any "
                        "desired profile changes manually. Close the browser when done."
                    )
                else:
                    screenshot(page, "profile_not_confirmed")
                    print(
                        "\nThe profile page opened, but the script could not confirm "
                        "the signed-in state. Check the browser and screenshots folder."
                    )
                    log.warning("Profile page opened but signed-in state was not confirmed")

                input("\nPress Enter in this terminal to close the browser...")
            finally:
                context.close()
                browser.close()

    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(130)
    except Exception as exc:
        log.exception("Run failed: %s", exc)
        print(f"\nFAILED: {exc}\nSee {LOG_FILE} and {SCREENSHOT_DIR}.")
        sys.exit(1)


if __name__ == "__main__":
    main()
