# Naukri automation setup (semi-automated alerts + daily profile refresh)

## Part A: Job alerts (5 minutes, do this first)

On Naukri, run a search, then click **Create Job Alert** / the bell icon. Make 4 saved searches, all set to **daily email**:

| # | Keywords | Locations | Experience |
|---|----------|-----------|------------|
| 1 | Cloud Support Engineer, Cloud Operations Engineer, AWS Support | Pune, Mumbai, Hyderabad, Bengaluru | 1 yr |
| 2 | AWS Cloud Engineer, AWS Engineer | same | 1 yr |
| 3 | Junior DevOps Engineer, DevOps Engineer Jenkins | same | 1 yr |
| 4 | Production Support Engineer Linux AWS, Application Support Engineer | same | 1 yr |

Tips:
- Do not add Delhi NCR / Gurgaon anywhere.
- Set experience to 1 (or 0-2) so you are not shown senior roles.
- Also turn on alerts on LinkedIn Jobs for the same searches ("Date posted: Past 24 hours").
- Add a Gmail filter: from `naukri.com` -> label "Job Alerts", so they don't drown your inbox.

## Part B: Your 20-minute morning routine

1. Open alert emails, shortlist 5-8 roles that match (right city, 0-2 yrs, AWS/Linux/support).
2. Add each to `Job_Application_Tracker.xlsx` with status **Shortlisted**.
3. For each, pick resume version (Cloud Support vs AWS/DevOps), apply, change status to **Applied**.
4. For your top 2 roles of the day, find an employee/recruiter on LinkedIn and send a short message (paste the JD here and I'll draft it).
5. Sunday: check the Dashboard tab. Which resume version and which source get replies? Do more of that.

## Part C: Daily profile refresh script

### 1. One-time install (Python 3.9+)
```bash
pip install playwright
playwright install chromium
```

### 2. Set environment variables
**Windows (PowerShell):**
```powershell
setx NAUKRI_EMAIL "you@example.com"
setx NAUKRI_PASSWORD "your-password"
setx NAUKRI_RESUME_PATH "C:\Users\You\Documents\Prathamesh_Bhoge_Resume.pdf"
```
(Open a new terminal afterwards.)

**Linux/macOS** (add to `~/.bashrc` or `~/.zshrc`):
```bash
export NAUKRI_EMAIL="you@example.com"
export NAUKRI_PASSWORD="your-password"
export NAUKRI_RESUME_PATH="$HOME/Documents/Prathamesh_Bhoge_Resume.pdf"
```
Leave `NAUKRI_RESUME_PATH` unset if you prefer the headline-toggle method instead.

### 3. First run, with the browser visible
```bash
HEADLESS=0 python naukri_refresh.py        # Windows: set HEADLESS=0 then python naukri_refresh.py
```
Watch it. If Naukri asks for OTP/captcha, complete it by hand; the session is saved to `naukri_state.json` and later runs reuse it.

### 4. Schedule it (runs on your own computer)

**Windows (Task Scheduler):**
```powershell
schtasks /create /tn "NaukriRefresh" /tr "python C:\path\to\naukri_refresh.py" /sc daily /st 09:10
```
Then in Task Scheduler open the task -> Settings -> tick "Run task as soon as possible after a scheduled start is missed".

**Linux/macOS (cron):**
```bash
crontab -e
10 9 * * * cd /path/to/folder && /usr/bin/python3 naukri_refresh.py
```
Cron does not see your shell variables, so put the `export` lines at the top of a small wrapper script and call that instead.

### 5. Check it worked
- `naukri_refresh.log` shows each run.
- `screenshots/` has a `success` or `error` image per run.

## Known limits (please read)

- **I could not test this against live Naukri.** The login field IDs are the standard ones, but the profile-page selectors (the hidden file input, the headline edit icon) are the fragile part and Naukri changes its UI often. If the first run fails, look at the error screenshot and paste the log here; I'll fix the selectors.
- **Naukri's terms generally disallow automated access.** A once-a-day refresh is low-profile, but there is some risk of a captcha prompt or account flag. Keep it to once a day, don't add auto-apply, and don't run it from a cloud server.
- **Laptop must be on** at the scheduled time (or catch up later, per the Windows setting above).
- Use a unique password for Naukri, since it is stored in an environment variable on your machine.
- If it breaks, the manual fallback is a 1-minute daily edit of your headline on the Naukri app.
