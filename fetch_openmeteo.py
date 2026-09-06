#!/usr/bin/env python3
"""
Fetch Open-Meteo historical and forecast data for one configured location.

Uses only the standard library (no pip installs needed).
Writes two CSVs to the location's output directory (data/openmeteo/ by default):
  - historical_YYYYMMDD_HHMM.csv  (the location's start_date to yesterday)
  - forecast_YYYYMMDD_HHMM.csv    (today onwards, up to 16 days)

Existing timestamped CSVs are moved to that directory's legacy/ before writing.
"""

import argparse
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
# One entry per site whose external weather we track. Only Dar es Salaam is
# fetched today; ARC UK's buildings each carry their own external ambient sensor,
# which is what their adaptive comfort running mean uses.
#
# To add a UK location: uncomment the entry below with the building's
# coordinates, add `--location uk` as a step in update-dashboard-data.yml, and
# point the UK datasets at it in build.py (give them an Open-Meteo entry in
# "external_sensors" and load the CSVs from the new outdir).
LOCATIONS = {
    "tz": {
        "lat": -7.0650263,
        "lon": 39.298985,
        "elevation": "61.0",
        "timezone": "Africa/Dar_es_Salaam",
        "tz_abbr": "EAT",
        "utc_offset_seconds": "10800",
        "start_date": "2023-03-15",
        "outdir": Path("data/openmeteo"),
    },
    # "uk": {
    #     "lat": 52.0565,             # ← Grove Cottage, Hereford
    #     "lon": -2.7160,
    #     "elevation": "",
    #     "timezone": "Europe/London",
    #     "tz_abbr": "GMT",
    #     "utc_offset_seconds": "0",  # Open-Meteo returns local time for the zone
    #     "start_date": "2026-07-31",
    #     "outdir": Path("data/openmeteo_uk"),
    # },
}
DEFAULT_LOCATION = "tz"

DATA_HEADERS = ["time", "temperature_2m (°C)", "relative_humidity_2m (%)"]


def meta_rows(loc):
    """Metadata header matching the Open-Meteo CSV format build.py expects."""
    return [
        ["latitude", "longitude", "elevation", "utc_offset_seconds", "timezone", "timezone_abbreviation"],
        [str(loc["lat"]), str(loc["lon"]), loc["elevation"],
         loc["utc_offset_seconds"], loc["timezone"], loc["tz_abbr"]],
    ]


def fetch_json(url: str, retries: int = 3, backoff: int = 60) -> dict:
    """Fetch a URL and parse the JSON response, retrying on 5xx errors."""
    print(f"  Fetching {url[:120]}...")
    req = urllib.request.Request(url, headers={"User-Agent": "arc-temp-humid/1.0"})
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


def write_csv(path: Path, times: list, temps: list, humids: list, loc: dict):
    """Write a CSV in the format expected by build.py's load_external_temperature()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = meta_rows(loc)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        # Metadata rows
        w.writerow(rows[0])
        w.writerow(rows[1])
        w.writerow([])  # blank line separator
        # Data header + rows
        w.writerow(DATA_HEADERS)
        for t, temp, hum in zip(times, temps, humids):
            w.writerow([t, temp if temp is not None else "", hum if hum is not None else ""])
    print(f"  Wrote {len(times):,} rows → {path}")


def rotate_legacy(outdir: Path, pattern: str):
    """Move existing timestamped CSVs matching pattern into legacy/."""
    existing = sorted(outdir.glob(pattern))
    if not existing:
        return
    legacy_dir = outdir / "legacy"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    for p in existing:
        dest = legacy_dir / p.name
        shutil.move(str(p), str(dest))
        print(f"  Archived {p.name} → legacy/")


def fetch_historical(loc: dict, yesterday: str, now_tag: str):
    """Fetch historical data from the location's start_date to yesterday."""
    url = (
        f"https://historical-forecast-api.open-meteo.com/v1/forecast"
        f"?latitude={loc['lat']}&longitude={loc['lon']}"
        f"&hourly=temperature_2m,relative_humidity_2m"
        f"&timezone={loc['timezone']}"
        f"&start_date={loc['start_date']}&end_date={yesterday}"
    )
    data = fetch_json(url)
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    humids = hourly.get("relative_humidity_2m", [])

    if not times:
        raise RuntimeError("Historical API returned no data")

    # Warn if fewer rows than expected (~24 per day)
    expected_days = (datetime.strptime(yesterday, "%Y-%m-%d") - datetime.strptime(loc["start_date"], "%Y-%m-%d")).days + 1
    expected_rows = expected_days * 24
    if len(times) < expected_rows * 0.9:
        print(f"  WARNING: Expected ~{expected_rows} rows but got {len(times)}")

    rotate_legacy(loc["outdir"], "historical_*.csv")
    out_path = loc["outdir"] / f"historical_{now_tag}.csv"
    write_csv(out_path, times, temps, humids, loc)


def fetch_forecast(loc: dict, today: str, now_tag: str):
    """Fetch forecast data (today onwards, up to 16 days)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={loc['lat']}&longitude={loc['lon']}"
        f"&hourly=temperature_2m,relative_humidity_2m"
        f"&timezone={loc['timezone']}"
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

    rotate_legacy(loc["outdir"], "forecast_*.csv")
    out_path = loc["outdir"] / f"forecast_{now_tag}.csv"
    write_csv(out_path, list(f_times), list(f_temps), list(f_humids), loc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--location", default=DEFAULT_LOCATION, choices=sorted(LOCATIONS),
                        help="Which location to fetch (default: %(default)s)")
    args = parser.parse_args()
    loc = LOCATIONS[args.location]

    now_utc = datetime.now(timezone.utc)
    offset = timedelta(seconds=int(loc["utc_offset_seconds"]))
    now_local = now_utc + offset
    yesterday_local = now_local - timedelta(days=1)

    today_str = now_local.strftime("%Y-%m-%d")
    yesterday_str = yesterday_local.strftime("%Y-%m-%d")
    now_tag = now_utc.strftime("%Y%m%d_%H%M")  # GMT timestamp for filename

    print(f"Open-Meteo fetch [{args.location}] — {now_utc.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Today ({loc['tz_abbr']}): {today_str}")
    print(f"  Historical range: {loc['start_date']} → {yesterday_str}")

    loc["outdir"].mkdir(parents=True, exist_ok=True)

    ok = True

    print("\n[1/2] Historical data...")
    try:
        fetch_historical(loc, yesterday_str, now_tag)
    except Exception as e:
        print(f"  FAILED: {e}", file=sys.stderr)
        print("  Skipping historical — previous data files (if any) are still in place.")
        ok = False

    print("\n[2/2] Forecast data...")
    try:
        fetch_forecast(loc, today_str, now_tag)
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
