# Data Retrieval Pipeline - Code Explainer

This document explains how sensor data is automatically fetched, processed, and built into the dashboard every day. It covers the GitHub Actions workflow, each fetch script, the build system's `--auto` mode, and how data flows from external APIs into the final `index.html`.

---

## 1. Overview

The dashboard combines data from four sources:

| Source | What it provides | How it gets there |
|---|---|---|
| **Open-Meteo** | Hourly outdoor temperature and humidity (historical + 16-day forecast) | Auto-fetched daily by GitHub Action |
| **Omnisense** | Indoor/outdoor wireless sensor readings (temperature + humidity) | Auto-fetched daily by GitHub Action |
| **Climate cycles** | ENSO ONI, IOD DMI, MJO ROMI indices for Long-Term Mode | Auto-fetched daily by GitHub Action |
| **TinyTag** | Indoor logger data exported as `.xlsx` files | Added manually, processed during full builds |

Every day at 04:00 UTC, a GitHub Action runs all three auto-fetch scripts, then rebuilds the dashboard using `python build.py --auto`. The `--auto` flag tells the build to use a pre-saved snapshot of the TinyTag data (so it does not need the original `.xlsx` files) combined with the freshly fetched data.

---

## 2. The GitHub Action

The workflow file lives at `.github/workflows/update-dashboard-data.yml`.

### Trigger

```yaml
on:
  schedule:
    - cron: '0 4 * * *'  # daily at 04:00 UTC (07:00 EAT)
  workflow_dispatch:       # manual trigger from GitHub UI
```

It runs once a day on a schedule, and can also be triggered manually from the GitHub Actions tab.

### Steps

The job runs on `ubuntu-latest` and does the following in order:

**Step 1: Checkout the repo and install Python dependencies**

```yaml
- name: Install build dependencies
  run: pip install pandas pytz requests
```

**Step 2: Fetch climate cycle data**

```yaml
- name: Fetch climate cycle data (ENSO, IOD, MJO)
  continue-on-error: true
  run: python fetch_cycles.py
```

Each fetch step uses `continue-on-error: true`. This means if the NOAA server is down, or the Omnisense login fails, the workflow keeps going and still commits whatever data it did manage to fetch. A single failure does not block the entire pipeline.

**Step 3: Fetch Open-Meteo data**

```yaml
- name: Fetch Open-Meteo data
  continue-on-error: true
  run: python fetch_openmeteo.py
```

**Step 4: Fetch Omnisense data**

```yaml
- name: Fetch Omnisense data
  continue-on-error: true
  env:
    OMNISENSE_USERNAME: ${{ secrets.OMNISENSE_USERNAME }}
    OMNISENSE_PASSWORD: ${{ secrets.OMNISENSE_PASSWORD }}
  run: python fetch_omnisense.py
```

The Omnisense credentials are stored as GitHub repository secrets and injected as environment variables at runtime. They never appear in logs or code.

**Step 5: Rebuild the dashboard**

```yaml
- name: Rebuild dashboard
  run: python build.py --auto
```

This regenerates `index.html` using the sensor snapshot plus the freshly fetched data.

**Step 6: Commit and push if anything changed**

```yaml
- name: Commit and push if changed
  id: push
  run: |
    git config user.name "github-actions[bot]"
    git config user.email "actions@users.noreply.github.com"
    git add data/openmeteo/ index.html
    [ -d data/omnisense ] && git add data/omnisense/ || true
    [ -d data/cycles ] && git add data/cycles/ || true
    if git diff --cached --quiet; then
      echo "changed=false" >> $GITHUB_OUTPUT
    else
      git commit -m "auto-update data $(date -u +%Y-%m-%d)"
      git push
      echo "changed=true" >> $GITHUB_OUTPUT
    fi
```

This stages only the data directories and `index.html`. If `git diff --cached --quiet` finds no changes (for example, the API returned the same data as yesterday), it skips the commit entirely. The `changed` output variable is used by the next step.

**Step 7: Notify the main site**

```yaml
- name: Trigger main site sync
  if: steps.push.outputs.changed == 'true'
  run: |
    curl -X POST \
      -H "Authorization: Bearer ${{ secrets.MAIN_SITE_PAT }}" \
      https://api.github.com/repos/actionresearchprojects/actionresearchprojects.github.io/dispatches \
      -d '{"event_type":"sync-embedded","client_payload":{"source_repo":"arc_tz_temp_humid"}}'
```

If data was committed, this sends a `repository_dispatch` event to the main site repo (`actionresearchprojects.github.io`), telling it to pull in the updated dashboard. This uses a Personal Access Token stored as the `MAIN_SITE_PAT` secret.

### Push notification workflow

A separate, simpler workflow (`.github/workflows/notify-main-site.yml`) also triggers a main site sync whenever `index.html`, `config.html`, or files in `logo/` are pushed to main by anyone (not just the bot). This covers manual pushes.

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'index.html'
      - 'config.html'
      - 'logo/**'
```

---

## 3. fetch_openmeteo.py - Weather Data

This script fetches hourly temperature and humidity from the Open-Meteo API for Dar es Salaam.

### Configuration

```python
LAT = -7.0650263
LON = 39.298985
START_DATE = "2023-03-15"
OUTDIR = Path("data/openmeteo")
```

The coordinates point to the ecovillage site. Data collection starts from 15 March 2023, well before the first TinyTag loggers were deployed, so the running mean has a long warm-up period.

### Two separate fetches

The script makes two API calls:

**Historical data** (everything up to yesterday):

```python
def fetch_historical(yesterday: str, now_tag: str):
    url = (
        f"https://historical-forecast-api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        f"&hourly=temperature_2m,relative_humidity_2m"
        f"&timezone=Africa/Dar_es_Salaam"
        f"&start_date={START_DATE}&end_date={yesterday}"
    )
```

This uses the `historical-forecast-api` endpoint, which provides verified past observations. The date range spans from `START_DATE` (2023-03-15) to yesterday. At the time of writing, this is roughly 3 years of hourly data, around 26,000 rows.

**Forecast data** (today onwards, up to 16 days):

```python
def fetch_forecast(today: str, now_tag: str):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        f"&hourly=temperature_2m,relative_humidity_2m"
        f"&timezone=Africa/Dar_es_Salaam"
        f"&forecast_days=16"
    )
```

This uses the standard forecast endpoint. The dashboard shows forecast data as dashed lines and excludes it from comfort calculations.

### Output format

Both fetches write CSVs with a metadata header that `build.py` expects:

```python
META_ROWS = [
    ["latitude", "longitude", "elevation", "utc_offset_seconds", "timezone", "timezone_abbreviation"],
    [str(LAT), str(LON), "61.0", "10800", "Africa/Dar_es_Salaam", "EAT"],
]
DATA_HEADERS = ["time", "temperature_2m (C)", "relative_humidity_2m (%)"]
```

The files are named with a UTC timestamp, for example `historical_20260322_0449.csv`. Before writing, any existing timestamped files are moved to `data/openmeteo/legacy/` so the directory always has exactly one current file of each type.

### Error handling

```python
def fetch_json(url: str, retries: int = 3, backoff: int = 60) -> dict:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code >= 500 and attempt < retries - 1:
                wait = backoff * (attempt + 1)
                time.sleep(wait)
                continue
            raise
```

Server errors (HTTP 500+) are retried up to 3 times with increasing backoff (60s, 120s, 180s). Client errors (4xx) fail immediately. If the historical fetch fails, the previous CSV files remain untouched in `data/openmeteo/` and the build uses whatever data is already there.

---

## 4. fetch_omnisense.py - Wireless Sensors

This script logs into the Omnisense web portal, submits a data export form, and downloads the resulting CSV. There is no public API, so it works by mimicking a browser session.

### Authentication

```python
session = requests.Session()
session.headers.update(HEADERS)

login_data = {
    "target": "",
    "userId": username,
    "userPass": password,
    "btnAct": "Log-In",
}
resp = session.post(f"{BASE}/user_login.asp", data=login_data, allow_redirects=True)
```

The script creates a `requests.Session` (which persists cookies between requests) and POSTs the login form. If the response still contains the login page HTML, the credentials were wrong.

### Data export

```python
form_data = {
    "siteNbr": SITE_NBR,        # "152865" - the ecovillage site
    "sensorId": "",              # empty = all sensors
    "gwayId": "",                # empty = all gateways
    "dateFormat": "SE",          # gives yyyy-mm-dd hh:mm:ss timestamps
    "dnldFrDate": start_ddmmyyyy,
    "dnldToDate": end_ddmmyyyy,
    "averaging": "N",            # raw data, no averaging
    "btnAct": "Submit",
}
resp = session.post(f"{BASE}/dnld_rqst5.asp", data=form_data)
```

The form is submitted with all sensors selected and a date range covering the last 90 days (or from `EARLIEST_DATA = "2026-01-25"` with `--full-history`). The server processes the request and returns a page containing a JavaScript redirect to the generated CSV file.

### Parsing the download link

```python
match = re.search(r"go\(\s*\\'([^']+)\\'\)", resp.text)
```

The server's response page contains JavaScript like `go(\'/fileshare/images/abc.csv\')`. The regex extracts the CSV path, then the script downloads it:

```python
csv_url = f"{BASE}{csv_path}"
resp = session.get(csv_url, stream=True)
```

### Output

The CSV is saved as `data/omnisense/omnisense_YYYYMMDD_HHMM.csv`, with previous files archived to `legacy/`. The script validates that the download is a real Omnisense CSV by checking for the `sensor_desc` column header and a minimum file size of 100 bytes.

---

## 5. fetch_cycles.py - Climate Oscillation Indices

This is the simplest fetch script. It downloads three plain-text data files from public climate agencies:

```python
SOURCES = {
    "enso": {
        "url": "https://psl.noaa.gov/data/correlation/oni.csv",
        "dest": CYCLES_DIR / "enso" / "oni.csv",
    },
    "iod": {
        "url": "https://www.bom.gov.au/clim_data/IDCK000072/iod_1.txt",
        "dest": CYCLES_DIR / "iod" / "iod_1.txt",
    },
    "mjo": {
        "url": "https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt",
        "dest": CYCLES_DIR / "mjo" / "romi.cpcolr.1x.txt",
    },
}
```

| Index | What it measures | Source |
|---|---|---|
| **ENSO ONI** | El Nino / La Nina state based on Pacific sea surface temperatures | NOAA |
| **IOD DMI** | Indian Ocean Dipole, affects East African rainfall and temperature | Bureau of Meteorology (Australia) |
| **MJO ROMI** | Madden-Julian Oscillation, a 30-60 day tropical weather pattern | NOAA |

Each file is simply downloaded and saved. A timestamp file (`cycles_fetched_YYYYMMDD_HHMM.txt`) is written so the build system knows when the data was last refreshed.

These indices are parsed by `build.py` and displayed as coloured overlays on the Long-Term Mode chart, helping researchers see whether temperature patterns correlate with large-scale climate events.

---

## 6. build.py --auto Mode

The `--auto` flag is the key to making automated builds work without the original TinyTag `.xlsx` files. Here is how it works.

### The sensor snapshot

When you run a full build (no `--auto` flag), `build.py` processes all the raw `.xlsx` and CSV source files, then saves the processed data to `data/sensor_snapshot.json`:

```python
def save_sensor_snapshot(datasets_dfs):
    """Save non-Open-Meteo data from all datasets to sensor_snapshot.json.
    Excludes Open-Meteo data (fetched automatically). Omnisense data IS included
    in the snapshot as a fallback for when the automated Omnisense fetch fails."""
```

The snapshot contains every sensor's processed readings except Open-Meteo (which is always fetched fresh). Omnisense data is included in the snapshot as a fallback, but fresh Omnisense data replaces it when available.

### The --auto build flow

```python
if args.auto:
    # 1. Load the snapshot (TinyTag + Omnisense fallback data)
    datasets_dfs = load_sensor_snapshot()

    # 2. Load fresh Open-Meteo data
    ext_df_raw = load_external_temperature()

    # 3. Load fresh Omnisense data (if available)
    omnisense_files = sorted(OMNISENSE_DIR.glob("omnisense_*.csv"))
    if omnisense_files:
        os_df = load_omnisense_csv(omnisense_files[-1], sensor_filter=OMNISENSE_T_H_SENSORS)

    # 4. For each dataset, merge everything together
    for key, cfg in DATASETS.items():
        df = datasets_dfs.get(key, pd.DataFrame())

        # Merge fresh Open-Meteo
        if cfg["external_logger"] in OPENMETEO_IDS and not ext_df.empty:
            df = pd.concat([df, filtered_ext]).sort_index()

        # Replace snapshot Omnisense with fresh Omnisense (House 5 only)
        if key == "house5" and not omnisense_df.empty:
            df = df[~df["logger_id"].isin(OMNISENSE_T_H_SENSORS)]
            df = pd.concat([df, omnisense_df]).sort_index()
```

The logic is:
1. Start with the saved snapshot (contains TinyTag data and Omnisense as fallback)
2. Add fresh Open-Meteo data on top
3. If fresh Omnisense data was fetched, remove the snapshot's Omnisense data and replace it with the new data
4. If the Omnisense fetch failed, the snapshot's Omnisense data stays in place as a fallback

### Full build vs auto build

| | Full build (`python build.py`) | Auto build (`python build.py --auto`) |
|---|---|---|
| **When to use** | After adding new TinyTag `.xlsx` files | Daily automated runs |
| **TinyTag data** | Read from `.xlsx` files in `data/house5/` and `data/schoolteacher/` | Read from `sensor_snapshot.json` |
| **Open-Meteo data** | Loaded from CSVs in `data/openmeteo/` | Same |
| **Omnisense data** | Loaded from CSV in `data/omnisense/` | Fresh CSV if available, otherwise snapshot fallback |
| **Saves snapshot?** | Yes, writes `sensor_snapshot.json` | No |
| **Where it runs** | Your local machine | GitHub Actions (daily) |

---

## 7. Data Freshness Checks

After building, the dashboard embeds timestamps showing when each data source was last updated. At runtime in the browser, the JavaScript checks whether the data is stale:

- **Open-Meteo and Omnisense**: data should reach at least the day before the last fetch (2-day tolerance)
- **MJO**: should be within 3 weeks of current date
- **ENSO and IOD**: should be within 3 months (these indices update less frequently)

If data is stale, a warning triangle appears next to the "last updated" line in the sidebar footer, with a hover tooltip explaining what is out of date.

---

## 8. End-to-End Flow

Here is what happens every day at 04:00 UTC, from start to finish:

1. GitHub Actions triggers `update-dashboard-data.yml`
2. `fetch_cycles.py` downloads ENSO/IOD/MJO index files to `data/cycles/`
3. `fetch_openmeteo.py` downloads ~26,000 rows of historical weather data and ~384 rows of forecast data to `data/openmeteo/`
4. `fetch_omnisense.py` logs into omnisense.com and downloads the last 90 days of wireless sensor data to `data/omnisense/`
5. `build.py --auto` loads the sensor snapshot, merges in the fresh Open-Meteo and Omnisense data, processes everything, and writes a new `index.html`
6. The workflow checks if any files changed. If so, it commits and pushes with the message `auto-update data YYYY-MM-DD`
7. If a push happened, a `repository_dispatch` event notifies the main site to pull in the updated dashboard
8. The main site (`actionresearchprojects.github.io`) syncs the new files and the live dashboard is updated

If any single fetch fails (API down, credentials expired, server timeout), the pipeline continues with whatever data it has. The previous data files remain in place, so the dashboard always has something to show.
