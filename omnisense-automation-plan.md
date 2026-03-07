# Omnisense Automation — Implementation Plan for Claude Code

## Context

Phase 2 of automation for `arc_tz_temp_humid`. Phase 1 (Open-Meteo) is implemented and running.

The Omnisense download requires authentication, but uses **no cookies**. The server appears to track sessions by IP on the server side. The script must log in and download within the same connection/session.

**Repo:** `https://github.com/actionresearchprojects/arc_tz_temp_humid`

---

## The Omnisense download flow (from HAR analysis)

The entire flow is **cookieless**. No cookies are set or sent at any point. The server tracks the authenticated session internally (likely by IP).

### Step 1: Login

```
POST https://omnisense.com/user_login.asp
Content-Type: application/x-www-form-urlencoded

target=&userId={USERNAME}&userPass={PASSWORD}&btnAct=Log-In
```

Response: `302` redirect to `/site_select.asp`. No `Set-Cookie` header.

### Step 2: Request the download

```
POST https://omnisense.com/dnld_rqst5.asp
Content-Type: application/x-www-form-urlencoded

siteNbr=152865&sensorId=&gwayId=&dateFormat=SE&dnldFrDate={start}&dnldToDate={end}&averaging=N&btnAct=Submit
```

Response: `200` HTML page. The page contains JavaScript that reveals the download link. The key snippet in the response body is:

```javascript
if (103629 > 0){
    temp.innerHTML = '<input id="downloadbutton" ... onClick="go(\'/fileshare/images/download_808880031.csv\')" />&nbsp; 103629 rows of data ready for download' ;
} else {
    temp.innerHTML = '<b>No data found for current selections.  Please click Back and modify your search criteria.</b>'
}
```

The `go()` function is just `window.location = to`. So the download URL is:
```
https://omnisense.com/fileshare/images/download_{NUMBER}.csv
```

The number is unique per request. Parse it from the HTML response.

### Step 3: Download the CSV

```
GET https://omnisense.com/fileshare/images/download_{NUMBER}.csv
```

Response: `200`, `Content-Type: application/octet-stream`, body is the CSV file (~6 MB for a month of data from all sensors).

### Important: date format gotcha

Even when `dateFormat=SE` is selected (which means dates should be `yyyy-mm-dd`), the HAR shows the form actually sent dates in `mm/dd/yyyy` format:
```
dnldFrDate=02%2F02%2F2026&dnldToDate=03%2F03%2F2026
```
This was `02/02/2026` and `03/03/2026` URL-encoded. This suggests the `dateFormat` parameter controls the **output** format in the CSV, not the input format of the date fields. The input dates may always need to be `mm/dd/yyyy` (US format). **Test this empirically** — try sending `yyyy-mm-dd` format with `dateFormat=SE` and see if it works. If not, always send dates as `mm/dd/yyyy` regardless of the `dateFormat` setting.

### CSV format

Multi-block format, already parsed by `load_omnisense_csv()` in `build.py` (line 284):

```
sep=,
sensor_desc,site_name
House 5, Kitchen,ARC CEV Tanzania
sensorId,port,read_date,temperature,humidity,gpkg,dew_point,wood_Pct,battery_voltage
3276003D,0,2026-01-25 10:07:46,27.8,76.3,18.1,23.4,7,3.4
...
```

---

## 1. Create `fetch_omnisense.py`

New file in the repo root. **Standard library only** (`urllib.request`, `urllib.parse`, `re`, `datetime`, `pathlib`, `sys`, `shutil`).

### Script flow

```python
import urllib.request
import urllib.parse

# 1. Build an opener that follows redirects and shares state (same IP session)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
# (HTTPCookieProcessor is included as belt-and-suspenders — the server
#  doesn't use cookies, but if it ever starts, this handles it automatically)

# 2. Login
login_data = urllib.parse.urlencode({
    "target": "",
    "userId": USERNAME,       # from env var OMNISENSE_USERNAME
    "userPass": PASSWORD,     # from env var OMNISENSE_PASSWORD
    "btnAct": "Log-In",
}).encode()
login_req = urllib.request.Request(
    "https://omnisense.com/user_login.asp",
    data=login_data,
    headers={"User-Agent": "arc-tz-temp-humid/1.0"},
)
opener.open(login_req)  # follows 302 redirect

# 3. POST download form
download_data = urllib.parse.urlencode({
    "siteNbr": "152865",
    "sensorId": "",
    "gwayId": "",
    "dateFormat": "SE",
    "dnldFrDate": start_date,   # test both mm/dd/yyyy and yyyy-mm-dd
    "dnldToDate": end_date,
    "averaging": "N",
    "btnAct": "Submit",
}).encode()
download_req = urllib.request.Request(
    "https://omnisense.com/dnld_rqst5.asp",
    data=download_data,
    headers={"User-Agent": "arc-tz-temp-humid/1.0"},
)
resp = opener.open(download_req)
html = resp.read().decode("utf-8")

# 4. Parse the CSV URL from response HTML
#    Pattern: go('/fileshare/images/download_NNNNN.csv')
import re
match = re.search(r"go\('(/fileshare/images/download_\d+\.csv)'\)", html)
if not match:
    # Check for "No data found" message
    if "No data found" in html:
        print("ERROR: No data found for the selected date range.")
    else:
        print("ERROR: Could not find download link in response.")
        print(html[:500])
    sys.exit(1)

csv_path = match.group(1)
csv_url = f"https://omnisense.com{csv_path}"

# 5. Download the CSV
csv_req = urllib.request.Request(csv_url, headers={"User-Agent": "arc-tz-temp-humid/1.0"})
csv_resp = opener.open(csv_req)
csv_data = csv_resp.read()

# 6. Save to data/omnisense/omnisense_YYYYMMDD_HHMM.csv
```

### Configuration

```python
SITE_NBR = "152865"
LOGIN_URL = "https://omnisense.com/user_login.asp"
DOWNLOAD_URL = "https://omnisense.com/dnld_rqst5.asp"
OUTPUT_DIR = Path("data/omnisense")
LEGACY_DIR = Path("data/omnisense/legacy")
EARLIEST_DATE = "2025-01-25"   # adjust to actual first useful date
DEFAULT_LOOKBACK_DAYS = 90
```

### Credentials from environment variables

```python
USERNAME = os.environ.get("OMNISENSE_USERNAME", "")
PASSWORD = os.environ.get("OMNISENSE_PASSWORD", "")
if not USERNAME or not PASSWORD:
    print("ERROR: OMNISENSE_USERNAME and OMNISENSE_PASSWORD must be set.", file=sys.stderr)
    sys.exit(1)
```

### Date range

- Default: 90 days ago to today (for automated runs)
- `--full-history` flag: from `EARLIEST_DATE` to today (for first run)

### Legacy rotation

Same pattern as `fetch_openmeteo.py`: move existing `omnisense_*.csv` in `OUTPUT_DIR` to `LEGACY_DIR` before writing.

### Error handling

- Login failure: if the response to the login POST isn't a 302 or doesn't redirect to `/site_select.asp`, print error and exit
- Download form failure: if the response doesn't contain the download link pattern, print the first 500 chars and exit
- CSV download failure: if status isn't 200, exit
- Empty CSV: if downloaded file is tiny (<100 bytes) or doesn't contain `sensor_desc`, exit

---

## 2. GitHub Secrets

The user must add these to the repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `OMNISENSE_USERNAME` | Their Omnisense login username |
| `OMNISENSE_PASSWORD` | Their Omnisense login password |

---

## 3. Modify `build.py`

### A. Add Omnisense directory constant

At top, alongside `OPENMETEO_DIR` (line 27):

```python
OMNISENSE_DIR = DATA_FOLDER / "omnisense"
```

### B. Update Omnisense file loading path

In `load_dataset()` (line 364), check new location first:

```python
omnisense_files = sorted(OMNISENSE_DIR.glob("omnisense_*.csv"))
if not omnisense_files:
    omnisense_files = sorted(DATA_FOLDER.glob("omnisense_*.csv"))
```

### C. Rename `--openmeteo-only` to `--auto`

```python
parser.add_argument("--auto", "--openmeteo-only", action="store_true",
                    dest="auto",
                    help="Rebuild using sensor snapshot + fresh Open-Meteo/Omnisense data")
```

Update `args.openmeteo_only` → `args.auto` throughout.

### D. Pull Omnisense out of the sensor snapshot

Rename `OPENMETEO_IDS` (line 2024) and expand:

```python
AUTO_FETCHED_IDS = {OPENMETEO_HISTORICAL_ID, OPENMETEO_FORECAST_ID, OPENMETEO_LEGACY_ID} | OMNISENSE_T_H_SENSORS
```

Update `save_sensor_snapshot()` to use `AUTO_FETCHED_IDS`.

Snapshot will now contain **only TinyTag + Govee data**.

### E. Load fresh Omnisense in `--auto` mode

In the `--auto` branch of `main()`, after loading snapshot and Open-Meteo, add:

```python
print("Loading fresh Omnisense data...")
omnisense_files = sorted(OMNISENSE_DIR.glob("omnisense_*.csv"))
if not omnisense_files:
    omnisense_files = sorted(DATA_FOLDER.glob("omnisense_*.csv"))
if omnisense_files:
    os_df = load_omnisense_csv(omnisense_files[-1], sensor_filter=OMNISENSE_T_H_SENSORS)
    if not os_df.empty:
        # Weather Station cutoff (replicate from load_dataset lines 369-372)
        cutoff = pd.Timestamp("2026-02-17 12:00:00")
        os_df = os_df[~((os_df["logger_id"] == "320E02D1") & (os_df["datetime"] < cutoff))]
        os_df["datetime"] = (
            pd.to_datetime(os_df["datetime"], errors="coerce")
            .dt.tz_localize(TIMEZONE, nonexistent="shift_forward", ambiguous="NaT")
        )
        os_df = os_df.dropna(subset=["datetime"]).set_index("datetime").sort_index()
        os_df["iso_year"] = os_df.index.isocalendar().year.astype(int)
        os_df["iso_week"] = os_df.index.isocalendar().week.astype(int)
        if "house5" in datasets_dfs:
            datasets_dfs["house5"] = pd.concat([datasets_dfs["house5"], os_df]).sort_index()
        print(f"  Omnisense: {len(os_df):,} records")
```

### F. One full rebuild required after deploying

After these changes, the user must run `python build.py` locally to regenerate the snapshot (now without Omnisense), then push `data/sensor_snapshot.json`.

---

## 4. Update `.gitignore`

Add:

```gitignore
!data/omnisense/
data/omnisense/legacy/
```

---

## 5. Update GitHub Actions workflow

Update `.github/workflows/update-openmeteo.yml`:

```yaml
name: Update dashboard data

on:
  schedule:
    - cron: '0 4,16 * * *'  # twice daily
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install build dependencies
        run: pip install pandas pytz

      - name: Fetch Open-Meteo data
        run: python fetch_openmeteo.py

      - name: Fetch Omnisense data
        env:
          OMNISENSE_USERNAME: ${{ secrets.OMNISENSE_USERNAME }}
          OMNISENSE_PASSWORD: ${{ secrets.OMNISENSE_PASSWORD }}
        run: python fetch_omnisense.py

      - name: Rebuild dashboard
        run: python build.py --auto

      - name: Commit and push if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "actions@users.noreply.github.com"
          git add data/openmeteo/ data/omnisense/ index.html
          git diff --cached --quiet || git commit -m "auto-update data $(date -u +%Y-%m-%d)"
          git push
```

Note: the `env` block passes the secrets as environment variables to the Omnisense fetch step only.

---

## 6. Update documentation

### CLAUDE.md
- Data sources: Omnisense now auto-fetched to `data/omnisense/`
- Automated update: twice daily, both Open-Meteo and Omnisense
- Manual update: only TinyTag `.xlsx` needs manual updating now

### UPDATE.md
- Automated section: twice daily, both sources, mention secrets setup
- Manual section: TinyTag only
- What gets pushed: add `data/omnisense/`, `fetch_omnisense.py`
- Add a "First-time Omnisense setup" section about adding the two GitHub secrets

---

## What the human needs to do

1. **Add GitHub secrets**: Settings → Secrets and variables → Actions → add `OMNISENSE_USERNAME` and `OMNISENSE_PASSWORD`

2. **After Claude Code implements the changes**: run one full local build (`python build.py`) to regenerate the sensor snapshot without Omnisense data, then push

3. **Verify**: trigger the Action manually from the Actions tab and check it completes

---

## Workflow summary

### Twice daily (automated):
GitHub Action → `fetch_openmeteo.py` + `fetch_omnisense.py` → `build.py --auto` → commit + push

### When new TinyTag data is available (manual):
1. Add `.xlsx` to `data/house5/` or `data/dauda/`
2. `python build.py`
3. `git add index.html data/sensor_snapshot.json && git commit -m "update TinyTag data" && git push`

---

## Order of implementation

1. `fetch_omnisense.py` — test locally (set env vars: `OMNISENSE_USERNAME=... OMNISENSE_PASSWORD=... python fetch_omnisense.py`)
2. `build.py` changes (A–E above)
3. `.gitignore` update
4. GitHub Actions workflow update
5. One full local `python build.py` to regenerate snapshot
6. Test: `fetch_omnisense.py` → `build.py --auto` → verify dashboard
7. Documentation updates
8. Commit and push
