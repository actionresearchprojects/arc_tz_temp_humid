#!/usr/bin/env python3
"""
Fetch Omnisense sensor data for ARC Tanzania ecovillage.

Uses only the standard library (no pip installs needed).
Authenticates via environment variables OMNISENSE_USERNAME and OMNISENSE_PASSWORD.
Writes CSV to data/omnisense/omnisense_YYYYMMDD_HHMM.csv

The Omnisense server tracks sessions by IP (no cookies). All requests must go
through the same opener to maintain the authenticated session. The exact browser
flow must be replicated: login → site_select.asp → dnld_rqst.asp → POST form.
"""

import argparse
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
SITE_NBR = "152865"
LOGIN_URL = "https://omnisense.com/user_login.asp"
DOWNLOAD_FORM_URL = f"https://omnisense.com/dnld_rqst.asp?siteNbr={SITE_NBR}"
DOWNLOAD_POST_URL = "https://omnisense.com/dnld_rqst5.asp"
BASE_URL = "https://omnisense.com"
OUTPUT_DIR = Path("data/omnisense")
LEGACY_DIR = OUTPUT_DIR / "legacy"
EARLIEST_DATE = "2025-01-25"
DEFAULT_LOOKBACK_DAYS = 90

# Match real browser UA — old ASP sites sometimes check this
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)


def make_request(url, headers=None, data=None):
    """Build a urllib Request with default headers."""
    req = urllib.request.Request(url, data=data)
    req.add_header("User-Agent", USER_AGENT)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    return req


def rotate_legacy():
    """Move existing omnisense_*.csv in OUTPUT_DIR to LEGACY_DIR."""
    existing = sorted(OUTPUT_DIR.glob("omnisense_*.csv"))
    if not existing:
        return
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    for p in existing:
        dest = LEGACY_DIR / p.name
        shutil.move(str(p), str(dest))
        print(f"  Archived {p.name} → legacy/")


def main():
    # ── Credentials ───────────────────────────────────────────────────────────
    username = os.environ.get("OMNISENSE_USERNAME", "")
    password = os.environ.get("OMNISENSE_PASSWORD", "")
    if not username or not password:
        print("ERROR: OMNISENSE_USERNAME and OMNISENSE_PASSWORD must be set.", file=sys.stderr)
        sys.exit(1)

    # ── Date range ────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="Fetch Omnisense sensor data")
    parser.add_argument("--full-history", action="store_true",
                        help=f"Fetch from {EARLIEST_DATE} to today (instead of last {DEFAULT_LOOKBACK_DAYS} days)")
    args = parser.parse_args()

    now_utc = datetime.now(timezone.utc)
    eat_offset = timedelta(hours=3)
    now_eat = now_utc + eat_offset
    today_str = now_eat.strftime("%Y-%m-%d")
    now_tag = now_utc.strftime("%Y%m%d_%H%M")

    if args.full_history:
        start_date = EARLIEST_DATE
    else:
        start_dt = now_eat - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        start_date = start_dt.strftime("%Y-%m-%d")

    # Date format: yyyy-mm-dd hh:mm:ss (third dropdown option on the form)
    form_start = f"{start_date} 00:00:00"
    form_end = f"{today_str} 23:59:59"

    print(f"Omnisense fetch — {now_utc.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Date range: {start_date} → {today_str}")
    print(f"  Form dates: {form_start} → {form_end}")

    # ── Build opener ──────────────────────────────────────────────────────────
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

    # ── Step 1: Login ─────────────────────────────────────────────────────────
    print("\n[1/4] Logging in...")
    login_data = urllib.parse.urlencode({
        "target": "",
        "userId": username,
        "userPass": password,
        "btnAct": "Log-In",
    }).encode()
    login_req = make_request(LOGIN_URL, headers={
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/user_login.asp",
        "Content-Type": "application/x-www-form-urlencoded",
    }, data=login_data)
    try:
        login_resp = opener.open(login_req, timeout=60)
        login_resp.read()  # consume body
    except urllib.error.HTTPError as e:
        print(f"ERROR: Login failed with HTTP {e.code}.", file=sys.stderr)
        sys.exit(1)

    final_url = login_resp.geturl()
    if "site_select" not in final_url and "site_home" not in final_url:
        print(f"ERROR: Login may have failed. Redirected to: {final_url}", file=sys.stderr)
        sys.exit(1)
    print("  Login successful.")

    # ── Step 2: Visit site_select.asp (establishes session context) ───────────
    print("\n[2/4] Visiting site_select.asp...")
    site_select_req = make_request(f"{BASE_URL}/site_select.asp", headers={
        "Referer": f"{BASE_URL}/user_login.asp",
    })
    try:
        resp = opener.open(site_select_req, timeout=60)
        resp.read()
        print("  OK")
    except urllib.error.HTTPError as e:
        print(f"  Warning: HTTP {e.code}", file=sys.stderr)

    # ── Step 3: Visit download page (registers site in session) ───────────────
    print("\n[3/4] Visiting download page...")
    dnld_page_req = make_request(DOWNLOAD_FORM_URL, headers={
        "Referer": f"{BASE_URL}/site_select.asp",
    })
    try:
        resp = opener.open(dnld_page_req, timeout=60)
        resp.read()
        print("  OK")
    except urllib.error.HTTPError as e:
        print(f"  Warning: HTTP {e.code}", file=sys.stderr)

    # ── Step 4: POST the download form ────────────────────────────────────────
    print(f"\n[4/4] Requesting data export ({form_start} → {form_end})...")
    download_data = urllib.parse.urlencode({
        "siteNbr": SITE_NBR,
        "sensorId": "",
        "gwayId": "",
        "dateFormat": "SE",
        "dnldFrDate": form_start,
        "dnldToDate": form_end,
        "averaging": "N",
        "btnAct": "Submit",
    }).encode()
    download_req = make_request(DOWNLOAD_POST_URL, headers={
        "Origin": BASE_URL,
        "Referer": DOWNLOAD_FORM_URL,
        "Content-Type": "application/x-www-form-urlencoded",
    }, data=download_data)
    try:
        resp = opener.open(download_req, timeout=180)
    except urllib.error.HTTPError as e:
        print(f"ERROR: Download request failed with HTTP {e.code}.", file=sys.stderr)
        sys.exit(1)

    html = resp.read().decode("utf-8", errors="replace")

    # Parse the CSV URL from response HTML
    match = re.search(r"go\('(/fileshare/images/download_\d+\.csv)'\)", html)
    if not match:
        if "No data found" in html:
            print("WARNING: No data found for the selected date range. Skipping.", file=sys.stderr)
            print(f"  Dates sent: dnldFrDate={form_start}, dnldToDate={form_end}", file=sys.stderr)
        else:
            print("WARNING: Could not find download link in response. Skipping.", file=sys.stderr)
            print(f"  Response snippet: {html[:500]}", file=sys.stderr)
        print("\nDone (no data downloaded).")
        sys.exit(0)

    csv_path = match.group(1)
    csv_url = f"{BASE_URL}{csv_path}"
    row_match = re.search(r"(\d+) rows of data", html)
    row_count = row_match.group(1) if row_match else "?"
    print(f"  Download ready: {row_count} rows → {csv_path}")

    # ── Step 5: Download the CSV ──────────────────────────────────────────────
    print("  Downloading CSV...")
    csv_req = make_request(csv_url, headers={
        "Referer": f"{BASE_URL}/dnld_rqst5.asp",
    })
    try:
        csv_resp = opener.open(csv_req, timeout=300)
    except urllib.error.HTTPError as e:
        print(f"ERROR: CSV download failed with HTTP {e.code}.", file=sys.stderr)
        sys.exit(1)

    csv_data = csv_resp.read()

    # Validate
    if len(csv_data) < 100:
        print(f"ERROR: Downloaded file is too small ({len(csv_data)} bytes).", file=sys.stderr)
        sys.exit(1)
    csv_text = csv_data.decode("utf-8", errors="replace")
    if "sensor_desc" not in csv_text:
        print("ERROR: Downloaded file doesn't look like an Omnisense CSV.", file=sys.stderr)
        print(csv_text[:500], file=sys.stderr)
        sys.exit(1)

    # ── Save ──────────────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rotate_legacy()

    out_path = OUTPUT_DIR / f"omnisense_{now_tag}.csv"
    out_path.write_bytes(csv_data)
    size_mb = len(csv_data) / (1024 * 1024)
    print(f"  Wrote {size_mb:.1f} MB → {out_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
