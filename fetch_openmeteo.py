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
# One entry per site whose external weather we track. Each writes to its own
# output directory and is loaded by build.py as a separate pair of logger series,
# so a region spanning several sites can show every site's weather at once.
#
# Open-Meteo needs no API key and no account: a location is just a latitude and
# longitude. Adding a site therefore means adding an entry here and a matching
# feed in build.py's OPENMETEO_FEEDS.
#
# NOTE ON THE UK COORDINATES: these are the Open-Meteo model grid cell centres
# for the two buildings, not the buildings themselves. Requesting any point
# inside a cell returns that cell's series, so asking for the centre gives
# byte-identical data to asking for the building - while the number committed to
# this public repository is a fixed feature of the weather model rather than a
# private address. The cell centres sit 0.60 km (Grove) and 0.65 km (Holywell)
# from the buildings.
#
# To move a site, request its real position once, read "latitude"/"longitude"
# back from the API response, and put those here.
#
# start_date is the first day of that building's own sensor record minus a
# 30-day lead-in. The lead-in is not padding: the EN16798-1 running mean is
# seeded from its first day and decays that seed by alpha=0.8 per day, so
# without a run-up the first fortnight of comfort points would be measured
# against a running mean still carrying an arbitrary starting value. Thirty days
# reduces the seed's weight to about 0.1%.
LOCATIONS = {
    "tz": {                           # House 5, Al-Mizan ecovillage, Mkuranga
        # Rounded to 2dp for the same reason as the UK sites, and here it costs
        # nothing at all: Open-Meteo serves this region from a coarse global
        # model, so even 1dp (3.9 km away) returns byte-identical data. 2dp puts
        # the published coordinate 0.56 km from the building. The previous value
        # carried seven decimals, which is centimetre-level precision on a
        # children's facility in a public repository.
        "lat": -7.07,
        "lon": 39.30,
        "elevation": "61.0",
        "timezone": "Africa/Dar_es_Salaam",
        "tz_abbr": "EAT",
        "utc_offset_seconds": "10800",
        # House 5's first sensor reading is 2023-03-14, so the feed previously
        # began a day AFTER the data it was meant to contextualise: the running
        # mean had no run-up at all and the opening fortnight of comfort points
        # were measured against a seed value. Same 30-day lead-in as the UK.
        "start_date": "2023-02-12",
        "outdir": Path("data/openmeteo"),
    },
    "grove": {                        # Grove Cottage, Hereford
        "lat": 52.057774,             # model grid cell centre - see note above
        "lon": -2.704697,
        "elevation": "",
        "timezone": "Europe/London",
        "tz_abbr": "GMT",
        "utc_offset_seconds": "0",    # only used to pick "today" at the site
        "start_date": "2026-07-01",   # sensors start 2026-07-31, less 30 days
        "outdir": Path("data/openmeteo_grove"),
    },
    "holywell": {                     # Holywell Barn, Criccieth
        "lat": 52.926643,             # model grid cell centre - see note above
        "lon": -4.230377,
        "elevation": "",
        "timezone": "Europe/London",
        "tz_abbr": "GMT",
        "utc_offset_seconds": "0",
        "start_date": "2026-07-01",   # sensors start 2026-07-31, less 30 days
        "outdir": Path("data/openmeteo_holywell"),
    },
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

    print(f"Open-Meteo fetch [{args.location}] - {now_utc.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Today ({loc['tz_abbr']}): {today_str}")
    print(f"  Historical range: {loc['start_date']} → {yesterday_str}")

    loc["outdir"].mkdir(parents=True, exist_ok=True)

    ok = True

    print("\n[1/2] Historical data...")
    try:
        fetch_historical(loc, yesterday_str, now_tag)
    except Exception as e:
        print(f"  FAILED: {e}", file=sys.stderr)
        print("  Skipping historical - previous data files (if any) are still in place.")
        ok = False

    print("\n[2/2] Forecast data...")
    try:
        fetch_forecast(loc, today_str, now_tag)
    except Exception as e:
        print(f"  FAILED: {e}", file=sys.stderr)
        print("  Skipping forecast - previous data files (if any) are still in place.")
        ok = False

    if ok:
        print("\nDone.")
    else:
        print("\nDone (with errors - some fetches failed, pipeline will continue).")


if __name__ == "__main__":
    main()
