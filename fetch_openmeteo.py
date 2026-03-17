#!/usr/bin/env python3
"""
Fetch Open-Meteo historical and forecast data for Dar es Salaam.

Uses only the standard library (no pip installs needed).
Writes two CSVs to data/openmeteo/:
  - historical_YYYYMMDD_HHMM.csv  (start_date=2023-03-15 to yesterday)
  - forecast_YYYYMMDD_HHMM.csv    (today onwards, up to 16 days)

Existing timestamped CSVs are moved to data/openmeteo/legacy/ before writing.
"""

import csv
import json
import os
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
LAT = -7.0650263
LON = 39.298985
START_DATE = "2023-03-15"
OUTDIR = Path("data/openmeteo")
LEGACY_DIR = OUTDIR / "legacy"

# Metadata header matching the existing Open-Meteo CSV format
META_ROWS = [
    ["latitude", "longitude", "elevation", "utc_offset_seconds", "timezone", "timezone_abbreviation"],
    [str(LAT), str(LON), "61.0", "10800", "Africa/Dar_es_Salaam", "EAT"],
]
DATA_HEADERS = ["time", "temperature_2m (°C)", "relative_humidity_2m (%)"]


def fetch_json(url: str, retries: int = 3, backoff: int = 60) -> dict:
    """Fetch a URL and parse the JSON response, retrying on 5xx errors."""
    print(f"  Fetching {url[:120]}...")
    req = urllib.request.Request(url, headers={"User-Agent": "arc-tz-temp-humid/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status} from {url}")
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code >= 500 and attempt < retries - 1:
                wait = backoff * (attempt + 1)
                print(f"  Server error (HTTP {e.code}), retrying in {wait}s (attempt {attempt + 1}/{retries})...")
                time.sleep(wait)
                continue
            raise


def write_csv(path: Path, times: list, temps: list, humids: list):
    """Write a CSV in the format expected by build.py's load_external_temperature()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        # Metadata rows
        w.writerow(META_ROWS[0])
        w.writerow(META_ROWS[1])
        w.writerow([])  # blank line separator
        # Data header + rows
        w.writerow(DATA_HEADERS)
        for t, temp, hum in zip(times, temps, humids):
            w.writerow([t, temp if temp is not None else "", hum if hum is not None else ""])
    print(f"  Wrote {len(times):,} rows → {path}")


def rotate_legacy(pattern: str):
    """Move existing timestamped CSVs matching pattern into legacy/."""
    existing = sorted(OUTDIR.glob(pattern))
    if not existing:
        return
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)
    for p in existing:
        dest = LEGACY_DIR / p.name
        shutil.move(str(p), str(dest))
        print(f"  Archived {p.name} → legacy/")


def fetch_historical(yesterday: str, now_tag: str):
    """Fetch historical data from start_date to yesterday."""
    url = (
        f"https://historical-forecast-api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        f"&hourly=temperature_2m,relative_humidity_2m"
        f"&timezone=Africa/Dar_es_Salaam"
        f"&start_date={START_DATE}&end_date={yesterday}"
    )
    data = fetch_json(url)
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    humids = hourly.get("relative_humidity_2m", [])

    if not times:
        raise RuntimeError("Historical API returned no data")

    # Warn if fewer rows than expected (~24 per day)
    expected_days = (datetime.strptime(yesterday, "%Y-%m-%d") - datetime.strptime(START_DATE, "%Y-%m-%d")).days + 1
    expected_rows = expected_days * 24
    if len(times) < expected_rows * 0.9:
        print(f"  WARNING: Expected ~{expected_rows} rows but got {len(times)}")

    rotate_legacy("historical_*.csv")
    out_path = OUTDIR / f"historical_{now_tag}.csv"
    write_csv(out_path, times, temps, humids)


def fetch_forecast(today: str, now_tag: str):
    """Fetch forecast data (today onwards, up to 16 days)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        f"&hourly=temperature_2m,relative_humidity_2m"
        f"&timezone=Africa/Dar_es_Salaam"
        f"&forecast_days=16"
    )
    data = fetch_json(url)
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    humids = hourly.get("relative_humidity_2m", [])

    if not times:
        raise RuntimeError("Forecast API returned no data")

    # Filter to only future hours (from today 00:00 onwards)
    # The API may return some past hours; keep only today onwards
    filtered = [(t, te, h) for t, te, h in zip(times, temps, humids) if t >= today]
    if not filtered:
        raise RuntimeError("Forecast API returned no future data")

    f_times, f_temps, f_humids = zip(*filtered)

    rotate_legacy("forecast_*.csv")
    out_path = OUTDIR / f"forecast_{now_tag}.csv"
    write_csv(out_path, list(f_times), list(f_temps), list(f_humids))


def main():
    now_utc = datetime.now(timezone.utc)
    # EAT = UTC+3
    eat_offset = timedelta(hours=3)
    now_eat = now_utc + eat_offset
    yesterday_eat = now_eat - timedelta(days=1)

    today_str = now_eat.strftime("%Y-%m-%d")
    yesterday_str = yesterday_eat.strftime("%Y-%m-%d")
    now_tag = now_utc.strftime("%Y%m%d_%H%M")  # GMT timestamp for filename

    print(f"Open-Meteo fetch — {now_utc.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Today (EAT): {today_str}")
    print(f"  Historical range: {START_DATE} → {yesterday_str}")

    OUTDIR.mkdir(parents=True, exist_ok=True)

    ok = True

    print("\n[1/2] Historical data...")
    try:
        fetch_historical(yesterday_str, now_tag)
    except Exception as e:
        print(f"  FAILED: {e}", file=sys.stderr)
        print("  Skipping historical — previous data files (if any) are still in place.")
        ok = False

    print("\n[2/2] Forecast data...")
    try:
        fetch_forecast(today_str, now_tag)
    except Exception as e:
        print(f"  FAILED: {e}", file=sys.stderr)
        print("  Skipping forecast — previous data files (if any) are still in place.")
        ok = False

    if ok:
        print("\nDone.")
    else:
        print("\nDone (with errors — some fetches failed, pipeline will continue).")


if __name__ == "__main__":
    main()
