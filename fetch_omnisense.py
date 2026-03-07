#!/usr/bin/env python3
"""
Fetch Omnisense sensor data for ARC Tanzania ecovillage.

Uses only the standard library (no pip installs needed).
Authenticates via environment variables OMNISENSE_USERNAME and OMNISENSE_PASSWORD.
Writes CSV to data/omnisense/omnisense_YYYYMMDD_HHMM.csv

The Omnisense server tracks sessions by IP (no cookies), so all requests
must go through the same opener to maintain the authenticated session.
"""

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
DOWNLOAD_URL = "https://omnisense.com/dnld_rqst5.asp"
OUTPUT_DIR = Path("data/omnisense")
LEGACY_DIR = OUTPUT_DIR / "legacy"
EARLIEST_DATE = "2025-01-25"
DEFAULT_LOOKBACK_DAYS = 90
USER_AGENT = "arc-tz-temp-humid/1.0"


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
    import argparse
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

    # Prepare both date formats to try
    start_parts = start_date.split("-")
    end_parts = today_str.split("-")
    date_formats = [
        # Try mm/dd/yyyy first (US format seen in HAR capture)
        (f"{start_parts[1]}/{start_parts[2]}/{start_parts[0]}",
         f"{end_parts[1]}/{end_parts[2]}/{end_parts[0]}",
         "mm/dd/yyyy"),
        # Fall back to yyyy-mm-dd (dateFormat=SE might expect ISO input)
        (start_date, today_str, "yyyy-mm-dd"),
    ]

    print(f"Omnisense fetch — {now_utc.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Date range: {start_date} → {today_str}")

    # ── Build opener (shares state across requests for IP-based session) ──────
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

    # ── Step 1: Login ─────────────────────────────────────────────────────────
    print("\n[1/3] Logging in...")
    login_data = urllib.parse.urlencode({
        "target": "",
        "userId": username,
        "userPass": password,
        "btnAct": "Log-In",
    }).encode()
    login_req = urllib.request.Request(
        LOGIN_URL,
        data=login_data,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        login_resp = opener.open(login_req, timeout=60)
    except urllib.error.HTTPError as e:
        print(f"ERROR: Login failed with HTTP {e.code}.", file=sys.stderr)
        sys.exit(1)

    # Check we ended up at the right place (redirect to site_select.asp)
    final_url = login_resp.geturl()
    if "site_select" not in final_url and "site_home" not in final_url:
        print(f"ERROR: Login may have failed. Redirected to: {final_url}", file=sys.stderr)
        body = login_resp.read().decode("utf-8", errors="replace")
        if "invalid" in body.lower() or "error" in body.lower():
            print("  Server indicated invalid credentials.", file=sys.stderr)
        sys.exit(1)
    print("  Login successful.")

    # ── Step 2: Request the download (try multiple date formats) ────────────
    csv_path = None
    last_html = ""
    for form_start, form_end, fmt_label in date_formats:
        print(f"\n[2/3] Requesting data export ({fmt_label}: {form_start} → {form_end})...")
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
        download_req = urllib.request.Request(
            DOWNLOAD_URL,
            data=download_data,
            headers={"User-Agent": USER_AGENT},
        )
        try:
            resp = opener.open(download_req, timeout=120)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} — trying next format...", file=sys.stderr)
            continue

        last_html = resp.read().decode("utf-8", errors="replace")

        # Parse the CSV URL from response HTML
        # Pattern: go('/fileshare/images/download_NNNNN.csv')
        match = re.search(r"go\('(/fileshare/images/download_\d+\.csv)'\)", last_html)
        if match:
            csv_path = match.group(1)
            print(f"  Download link found: {csv_path}")
            break
        elif "No data found" in last_html:
            print(f"  No data found with {fmt_label} format, trying next...")
        else:
            print(f"  Unexpected response with {fmt_label} format, trying next...")

    if not csv_path:
        if "No data found" in last_html:
            print("WARNING: No Omnisense data found for any date format tried. Skipping.", file=sys.stderr)
        else:
            print("WARNING: Could not find download link in response. Skipping.", file=sys.stderr)
            print(last_html[:500], file=sys.stderr)
        print("\nDone (no data downloaded).")
        sys.exit(0)

    csv_url = f"https://omnisense.com{csv_path}"

    # ── Step 3: Download the CSV ──────────────────────────────────────────────
    print("\n[3/3] Downloading CSV...")
    csv_req = urllib.request.Request(csv_url, headers={"User-Agent": USER_AGENT})
    try:
        csv_resp = opener.open(csv_req, timeout=120)
    except urllib.error.HTTPError as e:
        print(f"ERROR: CSV download failed with HTTP {e.code}.", file=sys.stderr)
        sys.exit(1)

    csv_data = csv_resp.read()

    # Validate the CSV
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
