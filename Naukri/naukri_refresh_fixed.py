#!/usr/bin/env python3
"""
Daily Naukri profile refresh (runs on YOUR machine, not in the cloud).

What it does: logs in, then either re-uploads your resume or flips your resume
headline between two near-identical versions. Either counts as a profile update,
which bumps your "last updated" timestamp that recruiters sort/filter by.

It does NOT apply to jobs. Applying stays manual on purpose.

Setup:  see NAUKRI_SETUP.md
Config (environment variables, never hardcode the password):
  NAUKRI_EMAIL        login email / username
  NAUKRI_PASSWORD     password
  NAUKRI_RESUME_PATH  (optional) full path to the PDF to re-upload
  HEADLINE_A / HEADLINE_B  (optional) two headline variants, used on alternate days
  HEADLESS            "1" (default) or "0" to watch the browser (use 0 for first run)
"""
import os, sys, random, logging, datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

HERE = Path(__file__).resolve().parent
STATE = HERE / "naukri_state.json"          # saved session, reduces OTP/captcha prompts
SHOTS = HERE / "screenshots"; SHOTS.mkdir(exist_ok=True)
logging.basicConfig(
    filename=HERE / "naukri_refresh.log", level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("naukri")

EMAIL = os.environ.get("NAUKRI_EMAIL")
PASSWORD = os.environ.get("NAUKRI_PASSWORD")
RESUME = os.environ.get("NAUKRI_RESUME_PATH")
HEADLESS = os.environ.get("HEADLESS", "0") != "0"
HEAD_A = os.environ.get("HEADLINE_A",
    "Cloud Support Engineer | AWS | Linux Administration | Jenkins CI/CD | Production Support")
HEAD_B = os.environ.get("HEADLINE_B",
    "Cloud Support Engineer | AWS | Linux Administration | Jenkins CI/CD | Production Support ")  # trailing space

LOGIN_URL = "https://www.naukri.com/nlogin/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"


def pause(a=1.0, b=2.5):
    import time; time.sleep(random.uniform(a, b))


def snap(page, name):
    p = SHOTS / f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{name}.png"
    try: page.screenshot(path=str(p), full_page=True)
    except Exception: pass
    return p


def is_logged_in(page):
    return "nlogin" not in page.url and "login" not in page.url.lower()


def login(page):
    page.goto(LOGIN_URL, wait_until="domcontentloaded"); pause()
    page.fill("#usernameField", EMAIL); pause(0.5, 1.2)
    page.fill("#passwordField", PASSWORD); pause(0.5, 1.2)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle", timeout=30000); pause(2, 3)
    if not is_logged_in(page):
        snap(page, "login_failed")
        raise RuntimeError("Login did not complete (wrong credentials, OTP or captcha?). "
                           "Run once with HEADLESS=0 and finish it manually.")


def upload_resume(page):
    """Upload the configured resume using the profile page's visible resume controls."""
    if not RESUME:
        raise RuntimeError("NAUKRI_RESUME_PATH is not set.")

    path = Path(RESUME).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Resume file not found: {path}")
    if path.suffix.lower() != ".pdf":
        log.warning("Resume is not a PDF: %s", path.name)

    # First try any file input already present on the profile page.
    # If Naukri only creates it after clicking the resume control, click that control.
    file_inputs = page.locator('input[type="file"]')
    try:
        if file_inputs.count() == 0:
            controls = [
                page.get_by_text("Update Resume", exact=False),
                page.get_by_text("Upload Resume", exact=False),
                page.get_by_text("Update resume", exact=False),
                page.get_by_text("Upload resume", exact=False),
            ]
            clicked = False
            for control in controls:
                try:
                    if control.count() and control.first.is_visible():
                        control.first.click(timeout=3000)
                        clicked = True
                        page.wait_for_timeout(1000)
                        break
                except Exception:
                    continue
            if not clicked:
                raise RuntimeError(
                    "Could not find a visible 'Update Resume'/'Upload Resume' control. "
                    "Check the saved screenshot in the screenshots folder."
                )
            file_inputs = page.locator('input[type="file"]')

        if file_inputs.count() == 0:
            raise RuntimeError(
                "No file-upload input appeared after opening the resume control."
            )

        # Use the first available file input to avoid strict-mode errors when the
        # page contains multiple upload inputs.
        file_inputs.first.set_input_files(str(path), timeout=15000)
        page.wait_for_timeout(4000)

        # Save evidence in the log; do not claim success solely because a file was selected.
        log.info("Selected resume file for upload: %s", path.name)

        # Naukri may show an explicit Save/Upload button after selecting a file.
        for name in ("Save", "Upload", "Update"):
            try:
                button = page.get_by_role("button", name=name, exact=True)
                if button.count() and button.first.is_visible():
                    button.first.click(timeout=3000)
                    page.wait_for_timeout(2500)
                    log.info("Clicked post-selection button: %s", name)
                    break
            except Exception:
                continue

        snap(page, "resume_upload_attempt")
        print("Resume file selected; check the Naukri page and log to confirm the upload completed.")
    except Exception:
        snap(page, "resume_upload_failed")
        log.exception("Resume upload failed for %s", path)
        raise


def toggle_headline(page):
    headline = HEAD_A if datetime.date.today().toordinal() % 2 == 0 else HEAD_B
    section = page.locator("text=Resume headline").first
    section.scroll_into_view_if_needed(); pause()
    # pencil/edit icon sits next to the "Resume headline" heading
    section.locator("xpath=ancestor::*[self::div or self::section][1]") \
           .locator(".edit, [class*=edit], text=Edit").first.click(); pause()
    box = page.locator("textarea").first
    box.fill(headline); pause(0.5, 1)
    page.get_by_role("button", name="Save").first.click(); pause(2, 3)
    log.info("Headline saved (variant %s)", "A" if headline == HEAD_A else "B")


def main():
    if not EMAIL or not PASSWORD:
        sys.exit("Set NAUKRI_EMAIL and NAUKRI_PASSWORD environment variables.")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        ctx = browser.new_context(
            storage_state=str(STATE) if STATE.exists() else None,
            viewport={"width": 1366, "height": 850},
            locale="en-IN", timezone_id="Asia/Kolkata")
        page = ctx.new_page()
        try:
            page.goto(PROFILE_URL, wait_until="domcontentloaded"); pause(2, 3)
            if not is_logged_in(page):
                log.info("Session expired, logging in")
                login(page)
                page.goto(PROFILE_URL, wait_until="domcontentloaded"); pause(2, 3)
            ctx.storage_state(path=str(STATE))
            try:
                STATE.chmod(0o600)
            except Exception:
                pass

            if RESUME:
                upload_resume(page)
                snap(page, "success")
                print("Resume upload attempt finished. Verify the updated resume on your Naukri profile.")
            else:
                raise RuntimeError(
                    "NAUKRI_RESUME_PATH is not set. Set it to your resume PDF path; "
                    "this script will not change your headline as a fallback."
                )
        except (PWTimeout, Exception) as e:
            snap(page, "error"); log.exception("Refresh failed: %s", e)
            print(f"FAILED: {e}\nSee naukri_refresh.log and the screenshots folder.")
            sys.exit(1)
        finally:
            ctx.close(); browser.close()


if __name__ == "__main__":
    main()
