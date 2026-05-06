#!/usr/bin/env python3
"""
Build script for House 5 TinyTag logger dashboard.

To update with new data:
  1. Add/replace .xlsx files in data/house5/ or data/schoolteacher/
  2. Run: python build.py
  3. git add index.html && git commit -m "update data" && git push

Output: index.html

NOTE FOR CLAUDE: After making any changes to this file or index.html,
add an entry to the Changelog in CHANGELOG.md. The heading must include
date and time to the second in CST (Taiwan, UTC+8) - always run `date`
first to get the real time: ### YYYY-MM-DD HH:MM:SS CST
"""

import argparse
import base64
import json
import math
import re
import struct
import sys
from collections import Counter
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import pytz

DATA_FOLDER = Path("data")
OPENMETEO_DIR = DATA_FOLDER / "openmeteo"
OMNISENSE_DIR = DATA_FOLDER / "omnisense"
CYCLES_DIR = DATA_FOLDER / "cycles"
SNAPSHOT_PATH = DATA_FOLDER / "sensor_snapshot.json"

# ── Configuration ──────────────────────────────────────────────────────────────
TIMEZONE = pytz.timezone("Africa/Dar_es_Salaam")
OUTPUT_FILE = Path("index.html")

OMNISENSE_T_H_SENSORS = {
    "320E02D1", "327601CB", "32760371", "3276012B", "32760164",
    "3276003D", "327601CD", "32760205", "3276028A", "32760208",
}


OPENMETEO_HISTORICAL_ID = "External Historical (Open-Meteo)"
OPENMETEO_FORECAST_ID = "External Forecast (Open-Meteo)"
OPENMETEO_LEGACY_ID = "External (Open-Meteo)"  # backward-compat with old single CSV

DATASETS = {
    "house5": {
        "label": "House 5",
        "folder": Path("data/house5"),
        "skip_rows": 350,
        "external_logger": OPENMETEO_HISTORICAL_ID,
        "external_sensors": [OPENMETEO_HISTORICAL_ID, OPENMETEO_FORECAST_ID, "861011", "320E02D1"],
        "exclude_loggers": set(),
        "room_loggers": ["780981","639148","759522","759521","759209",
                         "759492",
                         "327601CD","3276003D","3276028A","32760205",
                         "32760208","327601CB","32760371","3276012B"],
        "structural_loggers": ["759493","861004","861034","759489","32760164"],
        # Per-logger date filters: only keep data within [from, before) for that logger
        "logger_date_filters": {
            "759498": {"before": "2024-06-01"},  # moved to Schoolteacher's on 1 Jun; drop Jun 1 entirely
            "861011": {"before": "2024-05-07 12:00:00"},  # erroneous data from 12pm EAT 7 May 2024 onward
        },
        "anomalous_ranges": {
            "3276012B": {"before": "2026-02-12", "reason": "Data before 12 Feb 2026 is anomalous. A third bunk bed placed across the bay window, accomodating six occupants instead of the intended four, combined with drawn curtains, is suspected to have blocked natural airflow and trapped warm air inside. Subject to further investigation."},
        },
        # Sidebar display order: external first, then interleaved by room
        "sidebar_order": [
            OPENMETEO_HISTORICAL_ID, OPENMETEO_FORECAST_ID,       # Open-Meteo
            "861011", "320E02D1",                                  # other external
            # Living Room
            "780981",                                             # Living Room (TinyTag)
            "759493",                                             # Living Room above ceiling (TinyTag)
            "861968",                                             # Living Room below metal (TinyTag)
            "327601CD",                                           # Living Room (Omnisense)
            # Kitchen
            "3276003D",                                           # Kitchen (Omnisense)
            # Study
            "639148",                                             # Study (TinyTag)
            "3276028A",                                           # Study (Omnisense)
            # Bedroom 1
            "759522",                                             # Bedroom 1 (TinyTag)
            "32760205",                                           # Bedroom 1 (Omnisense)
            # Bedroom 2
            "759521",                                             # Bedroom 2 (TinyTag)
            "327601CB",                                           # Bedroom 2 (Omnisense)
            # Bedroom 3
            "759209",                                             # Bedroom 3 (TinyTag)
            "759498",                                             # Bedroom 3 below metal roof (TinyTag, data until Jun 2024)
            "861004",                                             # Bedroom 3 above ceiling, below insulation (TinyTag)
            "861034",                                             # Bedroom 3 above ceiling, above insulation (TinyTag)
            "32760371",                                           # Bedroom 3 (Omnisense)
            # Bedroom 4
            "759492",                                             # Bedroom 4 (TinyTag)
            "759489",                                             # Bedroom 4 above ceiling (TinyTag)
            "759519",                                             # Bedroom 4 below metal (TinyTag)
            "3276012B",                                           # Bedroom 4 (Omnisense)
            "32760164",                                           # Bedroom 4 above ceiling (Omnisense)
            # Washrooms
            "32760208",                                           # Washrooms area (Omnisense)
        ],
    },
    "schoolteacher": {
        "label": "Schoolteacher's House",
        "folder": Path("data/schoolteacher"),
        "skip_rows": 7,
        "external_logger": OPENMETEO_HISTORICAL_ID,
        "external_sensors": [OPENMETEO_HISTORICAL_ID],
        "room_loggers": None,
        "sidebar_order": [OPENMETEO_HISTORICAL_ID, "759498", "govee"],
        # Per-logger date filters — historical Open-Meteo scoped to monitoring period
        "logger_date_filters": {
            "759498": {"from": "2024-06-02"},  # arrived from House 5 on 2 Jun; drop Jun 1 entirely
            OPENMETEO_HISTORICAL_ID: {"from": "2024-06-02", "before": "2025-10-15"},
        },
        # Per-dataset name overrides (759498 is "Bedroom 3 below metal roof" globally but "Bedroom 1" here)
        "logger_name_overrides": {"759498": "Bedroom 1"},
    },
}

LOGGER_NAMES = {
    # TinyTag loggers
    "861011": "External Ambient",
    "780981": "Living Room",
    "639148": "Study",
    "759522": "Bedroom 1",
    "759521": "Bedroom 2",
    "759209": "Bedroom 3",
    "759492": "Bedroom 4",
    "861968": "Living Room (below metal roof)",
    "759493": "Living Room (above ceiling)",
    "759498": "Bedroom 3 (below metal roof)",
    "861004": "Bedroom 3 (above ceiling, below insulation)",
    "861034": "Bedroom 3 (above ceiling, above insulation)",
    "759519": "Bedroom 4 (below metal roof)",
    "759489": "Bedroom 4 (above ceiling)",
    "govee":  "Living Space",
    # Omnisense sensors
    "320E02D1": "Weather Station T&RH",
    "327601CB": "Bedroom 2",
    "32760371": "Bedroom 3",
    "3276012B": "Bedroom 4",
    "32760164": "Bedroom 4 (above ceiling)",
    "3276003D": "Kitchen",
    "327601CD": "Living Room",
    "32760205": "Bedroom 1",
    "3276028A": "Study",
    "32760208": "Washrooms area",
    OPENMETEO_HISTORICAL_ID: "Historical Temperature",
    OPENMETEO_FORECAST_ID: "Forecast Temperature",
    OPENMETEO_LEGACY_ID: "External Temperature",  # backward compat
}

LOGGER_NAMES_SW = {
    "861011": "Nje (Mazingira)",
    "780981": "Sebule",
    "639148": "Chumba cha kusoma",
    "759522": "Chumba cha kulala 1",
    "759521": "Chumba cha kulala 2",
    "759209": "Chumba cha kulala 3",
    "759492": "Chumba cha kulala 4",
    "861968": "Sebule (chini ya paa la bati)",
    "759493": "Sebule (juu ya dari)",
    "759498": "Chumba cha kulala 3 (chini ya paa la bati)",
    "861004": "Chumba cha kulala 3 (juu ya dari, chini ya insulation)",
    "861034": "Chumba cha kulala 3 (juu ya dari, juu ya insulation)",
    "759519": "Chumba cha kulala 4 (chini ya paa la bati)",
    "759489": "Chumba cha kulala 4 (juu ya dari)",
    "govee": "Eneo la kuishi",
    "320E02D1": "Kituo cha Hali ya Hewa T&RH",
    "327601CB": "Chumba cha kulala 2",
    "32760371": "Chumba cha kulala 3",
    "3276012B": "Chumba cha kulala 4",
    "32760164": "Chumba cha kulala 4 (juu ya dari)",
    "3276003D": "Jikoni",
    "327601CD": "Sebule",
    "32760205": "Chumba cha kulala 1",
    "3276028A": "Chumba cha kusoma",
    "32760208": "Eneo la vyoo",
    OPENMETEO_HISTORICAL_ID: "Joto la Kihistoria",
    OPENMETEO_FORECAST_ID: "Joto la Utabiri",
    OPENMETEO_LEGACY_ID: "Joto la Nje",
}

LOGGER_SOURCES = {
    "861011": "TinyTag", "780981": "TinyTag", "639148": "TinyTag",
    "759522": "TinyTag", "759521": "TinyTag", "759209": "TinyTag",
    "759492": "TinyTag", "861968": "TinyTag", "759493": "TinyTag",
    "759498": "TinyTag", "861004": "TinyTag", "861034": "TinyTag",
    "759519": "TinyTag", "759489": "TinyTag", "govee": "Govee Smart Hygrometer",
    "320E02D1": "Omnisense", "327601CB": "Omnisense", "32760371": "Omnisense",
    "3276012B": "Omnisense", "32760164": "Omnisense", "3276003D": "Omnisense",
    "327601CD": "Omnisense", "32760205": "Omnisense", "3276028A": "Omnisense",
    "32760208": "Omnisense",
    OPENMETEO_HISTORICAL_ID: "Open-Meteo",
    OPENMETEO_FORECAST_ID: "Open-Meteo",
    OPENMETEO_LEGACY_ID: "Open-Meteo",
}

COLORS = [
    "#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd",
    "#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf",
    "#aec7e8","#ffbb78","#98df8a","#ff9896","#c5b0d5",
    "#c49c94","#f7b6d3","#c7c7c7","#dbdb8d","#9edae5",
    "#393b79","#637939","#8c6d31","#843c39",
]

MONTH_NAMES = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

# ── Fetch-time helpers ─────────────────────────────────────────────────────────
def _ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1:'st',2:'nd',3:'rd'}.get(n % 10,'th')}"

def parse_fetch_time(path):
    """Extract UTC datetime from a filename like foo_YYYYMMDD_HHMM.csv."""
    m = re.search(r'_(\d{8})_(\d{4})\.csv$', path.name)
    if not m:
        return None
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M")

def format_fetch_time(dt):
    """Format a UTC datetime as '7th March 2026 at 04:32 UTC'."""
    if dt is None:
        return None
    return f"{_ordinal(dt.day)} {dt.strftime('%B %Y')} at {dt.strftime('%H:%M')} UTC"

# ── Cycle phase generation ────────────────────────────────────────────────────

def parse_enso_oni(path):
    """Parse NOAA ONI CSV → dict of 'YYYY-MM' → phase index (0=La Niña, 1=Neutral, 2=El Niño).
    ONI thresholds: ≤ -0.5 La Niña, ≥ 0.5 El Niño, else Neutral.
    Uses 5 consecutive overlapping 3-month running mean seasons per standard CPC definition."""
    phases = {}
    if not path.exists():
        print(f"  Warning: {path} not found, ENSO phases will be empty")
        return phases
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("Date"):
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        date_str = parts[0].strip()
        val_str = parts[1].strip()
        try:
            val = float(val_str)
        except ValueError:
            continue
        if val <= -99:  # missing value sentinel (-9999 or -99.9)
            continue
        # date_str like "1950-01-01"
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        key = f"{dt.year}-{dt.month:02d}"
        if val <= -0.5:
            phases[key] = 0  # La Niña
        elif val >= 0.5:
            phases[key] = 2  # El Niño
        else:
            phases[key] = 1  # Neutral
    print(f"  ENSO: {len(phases)} months parsed")
    return phases


def parse_iod_dmi(path):
    """Parse BoM IOD weekly DMI → dict of 'YYYY-MM' → phase index (0=Negative, 1=Neutral, 2=Positive).
    DMI thresholds: ≤ -0.4 Negative, ≥ 0.4 Positive, else Neutral.
    Weekly values are averaged per month, then classified."""
    monthly_vals = {}  # 'YYYY-MM' → list of DMI values
    if not path.exists():
        print(f"  Warning: {path} not found, IOD phases will be empty")
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        try:
            start_str = parts[0].strip()
            dmi = float(parts[2].strip())
            # start date is YYYYMMDD
            dt = datetime.strptime(start_str, "%Y%m%d")
        except (ValueError, IndexError):
            continue
        key = f"{dt.year}-{dt.month:02d}"
        monthly_vals.setdefault(key, []).append(dmi)

    phases = {}
    for key, vals in monthly_vals.items():
        avg = sum(vals) / len(vals)
        if avg <= -0.4:
            phases[key] = 0  # Negative IOD
        elif avg >= 0.4:
            phases[key] = 2  # Positive IOD
        else:
            phases[key] = 1  # Neutral
    print(f"  IOD: {len(phases)} months parsed")
    return phases


def _iso_week(dt):
    """Return ISO week string 'YYYY-Www' for a date."""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _romi_to_phase(rmm1, rmm2):
    """Convert ROMI RMM1/RMM2 components to MJO phase (1-8) using Wheeler-Hendon convention.
    Returns phase number 1-8 based on angle in RMM1-RMM2 plane."""
    angle = math.degrees(math.atan2(rmm2, rmm1)) % 360
    # Sector mapping: 0°-45°→Phase5, 45°-90°→Phase6, ... 315°-360°→Phase4
    sector = int(angle / 45) % 8
    phase_map = [5, 6, 7, 8, 1, 2, 3, 4]
    return phase_map[sector]


def parse_mjo_romi(path):
    """Parse NOAA ROMI data → dict of 'YYYY-Www' → phase index (0-7, or -1 for weak).
    Converts ROMI (RMM1/RMM2) to standard RMM phases.
    Daily data aggregated to ISO weeks by majority phase; amplitude < 1.0 → weak (-1)."""
    weekly_phases = {}  # 'YYYY-Www' → list of (phase_index_or_neg1)
    if not path.exists():
        print(f"  Warning: {path} not found, MJO phases will be empty")
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 7:
            continue
        try:
            yr, mo, dy = int(parts[0]), int(parts[1]), int(parts[2])
            rmm1 = float(parts[4])
            rmm2 = float(parts[5])
            amplitude = float(parts[6])
        except (ValueError, IndexError):
            continue
        try:
            dt = date(yr, mo, dy)
        except ValueError:
            continue
        wk = _iso_week(dt)
        if amplitude < 1.0:
            phase_idx = -1  # weak/inactive
        else:
            phase_num = _romi_to_phase(rmm1, rmm2)
            phase_idx = phase_num - 1  # 0-indexed
        weekly_phases.setdefault(wk, []).append(phase_idx)

    # For each week, pick the majority phase (excluding weak days for mode,
    # but if majority of days are weak, mark week as weak)
    phases = {}
    for wk, daily in weekly_phases.items():
        counts = Counter(daily)
        # If more than half the days are weak, mark week as weak
        n_weak = counts.get(-1, 0)
        if n_weak > len(daily) / 2:
            phases[wk] = -1
        else:
            # Mode of non-weak phases
            non_weak = {k: v for k, v in counts.items() if k >= 0}
            if non_weak:
                phases[wk] = max(non_weak, key=non_weak.get)
            else:
                phases[wk] = -1
    print(f"  MJO: {len(phases)} weeks parsed (from ROMI data)")
    return phases


def generate_cycle_phases_js():
    """Parse cycle data files and return JavaScript code for phase lookup tables."""
    print("Parsing climate cycle data...")
    enso = parse_enso_oni(CYCLES_DIR / "enso" / "oni.csv")
    iod = parse_iod_dmi(CYCLES_DIR / "iod" / "iod_1.txt")
    mjo = parse_mjo_romi(CYCLES_DIR / "mjo" / "romi.cpcolr.1x.txt")

    def dict_to_js(d, per_line=6):
        """Format a dict as compact JS object literal."""
        items = [f"'{k}':{v}" for k, v in sorted(d.items())]
        lines = []
        for i in range(0, len(items), per_line):
            lines.append("  " + ",".join(items[i:i+per_line]) + ",")
        return "{\n" + "\n".join(lines) + "\n}" if lines else "{}"

    js = []
    js.append("// Climate oscillation phase lookup tables (auto-generated from cycle data files)")
    js.append("// ENSO: ONI-based. 0=La Ni\\u00f1a, 1=Neutral, 2=El Ni\\u00f1o")
    js.append("const ENSO_LABELS = ['La Ni\\u00f1a', 'Neutral', 'El Ni\\u00f1o'];")
    js.append(f"const ENSO_PHASES = {dict_to_js(enso)};")
    js.append("// IOD: DMI-based. 0=Negative, 1=Neutral, 2=Positive")
    js.append("const IOD_LABELS = ['Negative IOD', 'Neutral', 'Positive IOD'];")
    js.append(f"const IOD_PHASES = {dict_to_js(iod)};")
    js.append("// MJO: Phase by week (YYYY-Www \\u2192 phase 0-7, or -1 for weak/inactive)")
    js.append("// Derived from ROMI (Real-time OLR-based MJO Index) converted to RMM phases")
    js.append("const MJO_LABELS = ['Phase 1 (W. Hem/Africa)','Phase 2 (Indian Ocean)','Phase 3 (E. Indian Ocean)',")
    js.append("  'Phase 4 (Maritime Continent)','Phase 5 (W. Pacific)','Phase 6 (W. Pacific/Dateline)',")
    js.append("  'Phase 7 (E. Pacific)','Phase 8 (W. Hem/Africa)'];")
    js.append(f"const MJO_PHASES = {dict_to_js(mjo)};")
    return "\n".join(js)


# ── Data loading ───────────────────────────────────────────────────────────────
def load_logger_excel(path, skip_rows):
    try:
        df = pd.read_excel(path, skiprows=skip_rows, usecols=[1, 2, 3], header=None)
        df.columns = ["datetime", "temperature", "humidity"]
        df["logger_id"] = path.stem
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
        df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce")
        df = df.dropna(subset=["datetime", "temperature", "humidity"])
        return df
    except Exception as e:
        print(f"  Warning: could not load {path.name}: {e}")
        return pd.DataFrame()


def load_copernicus_climate_data():
    """Load Copernicus ERA5 historic + CMIP6 SSP projection CSVs from data/hist_proj/."""
    hist_folder = DATA_FOLDER / "hist_proj"
    era5_path = hist_folder / "t-ERA5_timeseries_historic.csv"
    if not era5_path.exists():
        print("  No data/hist_proj/t-ERA5_timeseries_historic.csv found, skipping climate data")
        return None

    result = {"series": []}

    # Load ERA5 historic
    df = pd.read_csv(era5_path, comment="#")
    years = df.iloc[:, 0].astype(int).tolist()
    temps = df.iloc[:, 1].astype(float).tolist()
    era5_end_year = max(years)
    result["series"].append({
        "id": "ERA5",
        "label": "ERA5 Historic",
        "timestamps": [f"{y}-01-01" for y in years],
        "values": temps,
    })
    print(f"  ERA5 Historic: {len(years)} years ({years[0]}–{era5_end_year})")

    # Load SSP projection files - truncated to start after ERA5 ends
    ssp_files = sorted(hist_folder.glob("t-CMIP6_timeseries_SSP*.csv"))
    for path in ssp_files:
        # Extract SSP name from filename: t-CMIP6_timeseries_SSP2-4.5.csv → SSP2-4.5
        ssp_name = path.stem.replace("t-CMIP6_timeseries_", "")
        df = pd.read_csv(path, comment="#")
        years = df.iloc[:, 0].astype(int).tolist()
        # Compute ensemble mean across all model columns (skip Year column)
        model_cols = df.iloc[:, 1:]
        model_cols = model_cols.replace("-", float("nan")).astype(float)
        ensemble_mean = model_cols.mean(axis=1).round(5).tolist()
        n_models = len(model_cols.columns)
        # Truncate to start from 2022
        pairs = [(y, v) for y, v in zip(years, ensemble_mean) if y >= 2022]
        years = [p[0] for p in pairs]
        ensemble_mean = [p[1] for p in pairs]
        result["series"].append({
            "id": ssp_name,
            "label": ssp_name,
            "timestamps": [f"{y}-01-01" for y in years],
            "values": ensemble_mean,
        })
        print(f"  {ssp_name}: {len(years)} years ({years[0]}–{years[-1]}), {n_models} models")

    return result


def _load_openmeteo_csv(path, logger_id):
    """Load a single Open-Meteo CSV file and assign the given logger_id."""
    df = pd.read_csv(path, skiprows=3)
    df = df.rename(columns={
        "time": "datetime",
        "temperature_2m (°C)": "temperature",
        "relative_humidity_2m (%)": "humidity",
    })
    df["logger_id"] = logger_id
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
    df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce")
    df = df.dropna(subset=["datetime", "temperature", "humidity"])
    return df[["datetime", "temperature", "humidity", "logger_id"]]


def load_external_temperature():
    """Load Open-Meteo data - prefers split historical/forecast CSVs in data/openmeteo/,
    falls back to legacy single open-meteo*.csv in data/."""
    dfs = []

    # Try new split files first
    hist_files = sorted(OPENMETEO_DIR.glob("historical_*.csv"))
    forecast_files = sorted(OPENMETEO_DIR.glob("forecast_*.csv"))

    if hist_files:
        hist_file = hist_files[-1]
        print(f"  Using historical Open-Meteo: {hist_file.name}")
        hist_df = _load_openmeteo_csv(hist_file, OPENMETEO_HISTORICAL_ID)
        if not hist_df.empty:
            dfs.append(hist_df)
            print(f"    {len(hist_df):,} records")
    if forecast_files:
        fc_file = forecast_files[-1]
        print(f"  Using forecast Open-Meteo: {fc_file.name}")
        fc_df = _load_openmeteo_csv(fc_file, OPENMETEO_FORECAST_ID)
        if not fc_df.empty:
            dfs.append(fc_df)
            print(f"    {len(fc_df):,} records")

    if dfs:
        return pd.concat(dfs, ignore_index=True)

    # Fallback: legacy single CSV
    matches = sorted(DATA_FOLDER.glob("open-meteo*.csv"))
    if not matches:
        print(f"  Warning: no Open-Meteo data found, skipping external temperature")
        return pd.DataFrame()
    if len(matches) > 1:
        print(f"  Warning: multiple Open-Meteo files found - using {matches[-1].name}")
    ext_file = matches[-1]
    print(f"  Using legacy external temperature: {ext_file.name}")
    return _load_openmeteo_csv(ext_file, OPENMETEO_HISTORICAL_ID)


def load_omnisense_csv(path, sensor_filter=None):
    """Parse a multi-block Omnisense CSV.
    sensor_filter: set of sensorId strings to include (None = include all).
    """
    with open(path) as f:
        lines = f.readlines()
    if len(lines) < 4:
        print(f"  ⚠ Omnisense CSV is empty or too short ({len(lines)} lines), skipping")
        return []
    all_dfs = []
    i = 0
    while i < len(lines):
        if "sensor_desc,site_name" in lines[i]:
            if i + 2 >= len(lines):
                i += 1
                continue
            col_headers = lines[i + 2].strip().split(",")
            if "temperature" not in col_headers or "humidity" not in col_headers:
                i += 1
                continue
            sensor_id_idx = col_headers.index("sensorId") if "sensorId" in col_headers else 0
            temp_idx = col_headers.index("temperature")
            humidity_idx = col_headers.index("humidity")
            date_col, date_idx = None, None
            for col in ["read_date", "datetime", "date", "time"]:
                if col in col_headers:
                    date_col, date_idx = col, col_headers.index(col)
                    break
            if date_col is None:
                i += 1
                continue
            data_start = i + 3
            data_end = data_start
            for j in range(data_start, len(lines)):
                if "sensor_desc,site_name" in lines[j]:
                    data_end = j
                    break
                data_end = j + 1
            data_rows = []
            for row_line in lines[data_start:data_end]:
                row = row_line.strip().split(",")
                if len(row) > max(sensor_id_idx, temp_idx, humidity_idx, date_idx):
                    sensor_id = row[sensor_id_idx].strip()
                    if sensor_filter and sensor_id not in sensor_filter:
                        continue
                    try:
                        data_rows.append({
                            "datetime": row[date_idx],
                            "temperature": row[temp_idx],
                            "humidity": row[humidity_idx],
                            "logger_id": sensor_id,
                        })
                    except (IndexError, ValueError):
                        continue
            if data_rows:
                df = pd.DataFrame(data_rows)
                df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
                df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
                df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce")
                df = df.dropna()
                if not df.empty:
                    all_dfs.append(df)
            i = data_end
        else:
            i += 1
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


def load_dataset(key):
    cfg = DATASETS[key]
    folder = cfg["folder"]
    skip_rows = cfg["skip_rows"]

    xlsx_files = sorted(
        p for p in folder.glob("*.xlsx") if not p.name.startswith("~$")
    )
    if not xlsx_files:
        raise ValueError(f"No .xlsx files found in {folder}")

    dfs = [load_logger_excel(f, skip_rows) for f in xlsx_files]
    dfs = [d for d in dfs if not d.empty]
    if not dfs:
        raise ValueError(f"No valid data loaded from {folder}")

    # Import specific loggers from other datasets' folders
    for logger_id, source_key in cfg.get("import_loggers", {}).items():
        source_cfg = DATASETS[source_key]
        source_folder = source_cfg["folder"]
        source_file = source_folder / f"{logger_id}.xlsx"
        if source_file.exists():
            imported = load_logger_excel(source_file, source_cfg["skip_rows"])
            if not imported.empty:
                dfs.append(imported)
                print(f"  Imported logger {logger_id} from {source_key} ({len(imported):,} records)")

    # Load Omnisense CSV sensors (House 5 only)
    if key == "house5":
        omnisense_files = sorted(OMNISENSE_DIR.glob("omnisense_*.csv"))
        if not omnisense_files:
            omnisense_files = sorted(DATA_FOLDER.glob("omnisense_*.csv"))
        if omnisense_files:
            print(f"  Loading Omnisense CSV: {omnisense_files[-1].name}")
            os_df = load_omnisense_csv(omnisense_files[-1], sensor_filter=OMNISENSE_T_H_SENSORS)
            if not os_df.empty:
                # Weather Station T&RH (320E02D1): only reliable from 2026-02-17 12:00 EAT onwards
                # Omnisense CSV timestamps are in EAT (local time), so compare against naive EAT value
                cutoff = pd.Timestamp("2026-02-17 12:00:00")
                os_df = os_df[~((os_df["logger_id"] == "320E02D1") & (os_df["datetime"] < cutoff))]
                dfs.append(os_df)
                print(f"  Omnisense: {len(os_df):,} records")

    # Load Open-Meteo external data for any dataset that uses it
    ext_sensors = set(cfg.get("external_sensors", []))
    if ext_sensors & OPENMETEO_IDS:
        ext_df = load_external_temperature()
        if not ext_df.empty:
            # Only keep Open-Meteo logger IDs that this dataset actually uses
            ext_df = ext_df[ext_df["logger_id"].isin(ext_sensors)]
            dfs.append(ext_df)
            print(f"  Open-Meteo: {len(ext_df):,} records")

    df = pd.concat(dfs, ignore_index=True).sort_values("datetime")

    # Exclude loggers not belonging to this dataset
    exclude = cfg.get("exclude_loggers", set())
    if exclude:
        df = df[~df["logger_id"].isin(exclude)]

    df["datetime"] = (
        pd.to_datetime(df["datetime"], errors="coerce")
        .dt.tz_localize(TIMEZONE, nonexistent="shift_forward", ambiguous="NaT")
    )
    df = df.dropna(subset=["datetime"]).set_index("datetime").sort_index()

    # Apply per-logger date filters (e.g. for loggers moved between sites)
    for logger_id, filt in cfg.get("logger_date_filters", {}).items():
        if "before" in filt:
            cutoff = pd.Timestamp(filt["before"]).tz_localize(TIMEZONE)
            df = df[~((df["logger_id"] == logger_id) & (df.index >= cutoff))]
        if "from" in filt:
            cutoff = pd.Timestamp(filt["from"]).tz_localize(TIMEZONE)
            df = df[~((df["logger_id"] == logger_id) & (df.index < cutoff))]

    iso = df.index.isocalendar()
    df["iso_year"] = iso.year.astype(int)
    df["iso_week"] = iso.week.astype(int)
    return df


# ── Running mean ───────────────────────────────────────────────────────────────
def compute_exponential_running_mean(df, primary_logger, fallback_loggers, alpha=0.8):
    """EN16798-1 exponential running mean of daily external temperatures.
    Uses primary_logger for daily means, falling back to fallback_loggers for missing days.
    Returns (hourly_running_mean_series, source_spans) where source_spans is a list of
    {"source": logger_id, "from": "YYYY-MM-DD", "to": "YYYY-MM-DD"} dicts."""

    # Get primary daily means
    prim_df = df[df["logger_id"] == primary_logger]
    if prim_df.empty:
        prim_daily = pd.Series(dtype=float)
    else:
        # Select numeric column before mean to avoid TypeError with logger_id strings
        prim_daily = prim_df["temperature"].resample("D").mean().dropna()

    # Get fallback daily means (merge all fallbacks first)
    fb_df = df[df["logger_id"].isin(fallback_loggers)]
    if fb_df.empty:
        fb_daily = pd.Series(dtype=float)
    else:
        fb_daily = fb_df["temperature"].resample("D").mean().dropna()

    if prim_daily.empty and fb_daily.empty:
        return pd.Series(dtype=float), []

    # Combine: use primary if available, else fallback
    # Track which source each day came from
    if prim_daily.empty:
        combined = fb_daily
        day_sources = pd.Series("fallback", index=fb_daily.index)
    elif fb_daily.empty:
        combined = prim_daily
        day_sources = pd.Series("primary", index=prim_daily.index)
    else:
        all_days = prim_daily.index.union(fb_daily.index)
        combined = pd.Series(index=all_days, dtype=float)
        day_sources = pd.Series(index=all_days, dtype=object)
        # Fill with fallback first, then overwrite with primary where available
        combined.update(fb_daily)
        day_sources.update(pd.Series("fallback", index=fb_daily.index))
        combined.update(prim_daily)
        day_sources.update(pd.Series("primary", index=prim_daily.index))

    combined = combined.dropna()
    day_sources = day_sources.reindex(combined.index).dropna()

    if len(combined) == 0:
        return pd.Series(dtype=float), []

    trm = [combined.iloc[0]]
    for i in range(1, len(combined)):
        trm.append((1 - alpha) * combined.iloc[i - 1] + alpha * trm[-1])

    trm_series = pd.Series(trm, index=combined.index, name="running_mean")

    # Build source spans: consecutive runs of same source
    source_spans = []
    fb_label = fallback_loggers[0] if fallback_loggers else "fallback"
    if len(day_sources) > 0:
        cur_src = day_sources.iloc[0]
        cur_start = day_sources.index[0]
        for i in range(1, len(day_sources)):
            if day_sources.iloc[i] != cur_src:
                source_spans.append({
                    "source": primary_logger if cur_src == "primary" else fb_label,
                    "from": cur_start.strftime("%Y-%m-%d"),
                    "to": day_sources.index[i - 1].strftime("%Y-%m-%d"),
                })
                cur_src = day_sources.iloc[i]
                cur_start = day_sources.index[i]
        source_spans.append({
            "source": primary_logger if cur_src == "primary" else fb_label,
            "from": cur_start.strftime("%Y-%m-%d"),
            "to": day_sources.index[-1].strftime("%Y-%m-%d"),
        })

    return trm_series.resample("h").ffill(), source_spans


# ── JSON builder ───────────────────────────────────────────────────────────────
GRANULARITY_MAP = {
    "5min": "5min", "10min": "10min", "15min": "15min", "30min": "30min",
    "1h": "1h", "2h": "2h", "3h": "3h", "6h": "6h", "12h": "12h", "1d": "1D",
}

def build_dataset_json(key, df, logger_overrides=None):
    cfg = DATASETS[key]
    logger_overrides = logger_overrides or {}

    # Default external source for the dataset
    default_external_logger = cfg["external_logger"]

    # Fallback loggers are always the Open-Meteo set
    fallback_loggers = [l for l in cfg.get("external_sensors", []) if l in OPENMETEO_IDS]
    if not fallback_loggers and default_external_logger in OPENMETEO_IDS:
        fallback_loggers = [default_external_logger]

    ext_sensor_set = set(cfg.get("external_sensors", [default_external_logger] if default_external_logger else []))
    unique_loggers = sorted(df["logger_id"].unique())
    sidebar_order = cfg.get("sidebar_order", [])
    if sidebar_order:
        order_map = {l: i for i, l in enumerate(sidebar_order)}
        unique_loggers = sorted(unique_loggers, key=lambda l: order_map.get(l, 9999))

    # Room loggers (ordered by sidebar_order if available)
    if cfg["room_loggers"] is not None:
        room_loggers = [l for l in cfg["room_loggers"] if l in unique_loggers]
    else:
        room_loggers = [l for l in unique_loggers if l != default_external_logger]
    if sidebar_order:
        room_loggers = sorted(room_loggers, key=lambda l: order_map.get(l, 9999))

    # Structural loggers (above-ceiling etc) - also used in adaptive comfort
    structural_cfg = cfg.get("structural_loggers", [])
    structural_loggers = [l for l in structural_cfg if l in unique_loggers]
    if sidebar_order:
        structural_loggers = sorted(structural_loggers, key=lambda l: order_map.get(l, 9999))

    # comfort_loggers = room only (for adaptive comfort graph; no structurals)
    comfort_logger_set = set(room_loggers)
    comfort_loggers = [l for l in unique_loggers if l in comfort_logger_set]

    # Anomalous data ranges
    anomalous_cfg = cfg.get("anomalous_ranges", {})
    anomalous_ranges_js = {}
    for lid, rng in anomalous_cfg.items():
        if lid in unique_loggers:
            entry = {}
            if "before" in rng:
                dt = pd.Timestamp(rng["before"]).tz_localize(TIMEZONE)
                entry["before"] = int(dt.timestamp() * 1000)
            if "after" in rng:
                dt = pd.Timestamp(rng["after"]).tz_localize(TIMEZONE)
                entry["after"] = int(dt.timestamp() * 1000)
            if "reason" in rng:
                entry["reason"] = rng["reason"]
            if entry:
                anomalous_ranges_js[lid] = entry

    color_map = {l: COLORS[i % len(COLORS)] for i, l in enumerate(unique_loggers)}
    # Give Open-Meteo Historical the light cyan, Forecast a blue-grey
    cyan = "#17becf"
    forecast_color = "#7fafcf"
    for om_key, om_color in [(OPENMETEO_HISTORICAL_ID, cyan), (OPENMETEO_FORECAST_ID, forecast_color),
                              (OPENMETEO_LEGACY_ID, cyan)]:
        if om_key in color_map:
            for k, v in list(color_map.items()):
                if v == om_color and k != om_key:
                    color_map[k] = color_map.get(om_key, COLORS[0])
                    break
            color_map[om_key] = om_color
    name_overrides = cfg.get("logger_name_overrides", {})
    logger_names = {l: name_overrides.get(l, LOGGER_NAMES.get(l, l)) for l in unique_loggers}
    logger_sources = {l: LOGGER_SOURCES.get(l, "Unknown") for l in unique_loggers}

    # External data date range (for stale-data warning)
    om_ids = [l for l in unique_loggers if l in OPENMETEO_IDS]
    ext_data = df[df["logger_id"].isin(om_ids)] if om_ids else (
        df[df["logger_id"] == default_external_logger] if default_external_logger else pd.DataFrame()
    )
    ext_date_range = None
    if not ext_data.empty:
        ext_date_range = {
            "min": int(ext_data.index.min().timestamp() * 1000),
            "max": int(ext_data.index.max().timestamp() * 1000),
        }

    # Cache for running means to avoid redundant calculations
    running_mean_cache = {}

    available_years  = sorted(int(y) for y in df.index.year.unique())
    available_months = sorted({(int(y), int(m)) for y, m in zip(df.index.year, df.index.month)})
    available_weeks  = sorted({(int(y), int(w)) for y, w in zip(df["iso_year"], df["iso_week"])})
    available_days   = sorted(df.index.normalize().unique())
    # Tanzanian seasons: 0=Kiangazi(Jan-Feb), 1=Masika(Mar-May), 2=Kiangazi(Jun-Oct), 3=Vuli(Nov-Dec)
    _tz_season_idx = [0,0,1,1,1,2,2,2,2,2,3,3]
    _tz_season_names = ['Kiangazi (Jan\u2013Feb)','Masika (Mar\u2013May)','Kiangazi (Jun\u2013Oct)','Vuli (Nov\u2013Dec)']
    available_seasons = sorted({(int(y), _tz_season_idx[int(m)-1]) for y, m in zip(df.index.year, df.index.month)})

    series = {}
    for logger_id in unique_loggers:
        ldf = df[df["logger_id"] == logger_id].copy()
        if ldf.empty:
            continue
        # Resample to configured per-logger granularity (default 1h)
        logger_granularity = logger_overrides.get(logger_id, {}).get("granularity", "1h")
        resample_rule = GRANULARITY_MAP.get(logger_granularity, "1h")
        ldf = ldf[["temperature", "humidity"]].resample(resample_rule).mean().dropna(how="all")
        ts_ms = [int(t.timestamp() * 1000) for t in ldf.index]
        entry = {
            "timestamps":  ts_ms,
            "temperature": ldf["temperature"].round(2).tolist(),
            "humidity":    ldf["humidity"].round(2).tolist(),
        }

        # Adaptive comfort running mean for THIS logger
        if logger_id not in ext_sensor_set:
            source_id = logger_overrides.get(logger_id, {}).get("external_source", default_external_logger)
            # Ensure the source exists in data and isn't forecast
            if source_id not in unique_loggers or source_id == OPENMETEO_FORECAST_ID:
                source_id = default_external_logger
                if source_id == OPENMETEO_FORECAST_ID:
                    # Fallback if default is also forecast (unlikely)
                    source_id = OPENMETEO_HISTORICAL_ID if OPENMETEO_HISTORICAL_ID in unique_loggers else None

            if source_id:
                if source_id not in running_mean_cache:
                    running_mean_cache[source_id] = compute_exponential_running_mean(df, source_id, fallback_loggers)

                rm, src_spans = running_mean_cache[source_id]
                if not rm.empty:
                    merged = pd.merge_asof(
                        ldf[[]].reset_index().rename(columns={"datetime": "dt"}),
                        rm.reset_index().rename(columns={"datetime": "dt", "running_mean": "ext"}),
                        on="dt", direction="nearest",
                    )
                    entry["extTemp"] = merged["ext"].round(2).tolist()
                    entry["extSource"] = source_id
                    entry["extSourceSpans"] = src_spans

        series[logger_id] = entry

    return {
        "meta": {
            "loggers":      unique_loggers,
            "loggerNames":  logger_names,
            "loggerNamesSw": {k: LOGGER_NAMES_SW.get(k, v) for k, v in logger_names.items()},
            "loggerSources": logger_sources,
            "externalLogger": default_external_logger,
            "externalLoggers": [l for l in unique_loggers if l in ext_sensor_set],
            "forecastLoggers": [l for l in unique_loggers if l == OPENMETEO_FORECAST_ID],
            "roomLoggers":  room_loggers,
            "structuralLoggers": structural_loggers,
            "comfortLoggers": comfort_loggers,
            "lineLoggers":  unique_loggers,
            "histogramLoggers": unique_loggers,
            "periodicLoggers": unique_loggers,
            "colors":       color_map,
            "availableYears": available_years,
            "availableMonths": [
                {"label": f"{MONTH_NAMES[m-1]} {y}", "year": y, "month": m}
                for y, m in available_months
            ],
            "availableSeasons": [
                {"label": f"{_tz_season_names[s]} {y}", "year": y, "season": s}
                for y, s in available_seasons
            ],
            "availableWeeks": [
                {"label": "W/s " + date.fromisocalendar(y, w, 1).strftime("%d/%m/%y"), "year": y, "week": w}
                for y, w in available_weeks
            ],
            "availableDays": [
                {"label": d.strftime("%d %b %Y"), "ts": int(d.timestamp() * 1000)}
                for d in available_days
            ],
            "totalReadings": len(df),
            "dateRange": {
                "min": int(df.index.min().timestamp() * 1000),
                "max": int(df.index.max().timestamp() * 1000),
            },
            "extDateRange": ext_date_range,
            "anomalousRanges": anomalous_ranges_js,
        },
        "series": series,
    }


# ── HTML template ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<!-- NOTE FOR CLAUDE: After making any changes to this file or build.py,
     add an entry to the Changelog in CLAUDE.md. The heading must include
     date and time to the second in CST (Taiwan, UTC+8) - always run `date`
     first to get the real time: ### YYYY-MM-DD HH:MM:SS CST -->
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>
// On page load, snap viewport back to scale 1 — handles arriving from a zoomed/rotated page
// (e.g. after a password screen or landscape rotation on iOS).
// Briefly sets maximum-scale=1 to force the browser to scale 1.0, then removes it so
// the user can still pinch-zoom the Plotly chart afterwards.
(function(){var m=document.querySelector('meta[name=viewport]');if(!m)return;var c=m.content;m.content=c+',maximum-scale=1';requestAnimationFrame(function(){m.content=c;});})();
</script>
<title>Ecovillage Temperature &amp; Humidity</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Ubuntu:ital,wght@0,300;0,400;0,500;0,700;1,400&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Ubuntu', sans-serif; font-size: 13px; background: #f8f9fa; color: #333; display: flex; flex-direction: column; height: 100vh; height: 100dvh; overflow: hidden; -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
#header { background: white; border-bottom: 1px solid #ddd; padding: 6px 12px; display: flex; align-items: center; gap: 8px; flex-shrink: 0; flex-wrap: wrap; min-height: 40px; }
#header h1 { font-size: 18px; font-weight: 500; color: #222; margin-right: 2px; white-space: nowrap; }
#logo { height: 32px; width: auto; flex-shrink: 0; vertical-align: middle; }
#header a { display: flex; align-items: center; }
.bar-divider { border-left: 1px solid #ccc; height: 20px; flex-shrink: 0; margin: 0 2px; }
#main { display: flex; flex: 1; overflow: hidden; position: relative; }
#sidebar { width: 300px; background: white; border-right: 1px solid #ddd; overflow-y: auto; padding: 10px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; transition: transform 0.2s ease; z-index: 10; }
#chart-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; position: relative; }
#time-bar { background: white; border-bottom: 1px solid #ddd; padding: 6px 10px; display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
#time-bar-top { display: flex; align-items: center; width: 100%; gap: 8px; }
#time-bar-left { flex: 1; display: flex; align-items: center; gap: 8px; }
#bar-title { font-size: 14px; font-weight: 600; color: #222; white-space: nowrap; text-align: center; padding: 0 8px; overflow: hidden; text-overflow: ellipsis; }
#time-bar-right { flex: 1; display: flex; align-items: center; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }
#chart { flex: 1; min-height: 0; }
#chart.comfort-mode .annotation { transition: opacity 0.5s !important; }
#chart.comfort-mode .annotation rect { pointer-events: all !important; cursor: default; }
#chart.comfort-mode .annotation:hover { opacity: 0.08 !important; }
#chart.comfort-mode .annotation:hover rect { fill-opacity: 0.08 !important; }
#chart.comfort-mode .annotation:hover text { fill-opacity: 0.08 !important; }
.section-title { font-weight: 600; font-size: 11px; color: #666; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
.section { display: flex; flex-direction: column; gap: 2px; }
select, button, input { font-family: inherit; }
select { font-size: 12px; padding: 3px 5px; border: 1px solid #ccc; border-radius: 4px; background: white; cursor: pointer; max-width: 100%; }
select:focus { outline: none; border-color: #4a90d9; }
#chart-type option[value="beta"] { color: #c0392b; }
.beta-tag { display:inline-block; background:#c0392b; color:white; font-size:9px; font-weight:700; padding:1px 4px; border-radius:3px; margin-left:4px; vertical-align:middle; letter-spacing:0.03em; }
.cb-label { display: flex; align-items: center; gap: 5px; padding: 1px 0; cursor: pointer; line-height: 1.4; font-size: 12px; }
.cb-label:hover { color: #1f77b4; }
[data-tooltip] { position: relative; }
[data-tooltip]:hover::after { content: attr(data-tooltip); position: absolute; left: 16px; top: 100%; background: #333; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; white-space: nowrap; z-index: 100; pointer-events: none; }
.info-i { display: inline-flex; align-items: center; justify-content: center; width: 14px; height: 14px; border-radius: 50%; background: #999; color: white; font-size: 9px; font-style: italic; font-weight: 700; cursor: help; flex-shrink: 0; line-height: 1; font-family: Georgia, 'Times New Roman', serif; }
.info-i:hover { background: #666; }
.anomalous-warn { color: #d4880f; font-size: 13px; cursor: help; vertical-align: middle; margin-left: 2px; }
.stale-warn { color: #d4880f; font-size: 11px; cursor: help; }
#anomalous-fixed-tip { display:none; position:fixed; background:#5a4000; color:white; padding:6px 10px; border-radius:4px; font-size:10px; width:260px; z-index:200; pointer-events:none; line-height:1.4; }
#info-fixed-tip, #chart-info-tip, .info-tip-fixed { display:none; position:fixed; background:#333; color:white; font-size:12px; font-family:'Ubuntu',sans-serif; padding:6px 9px; border-radius:4px; line-height:1.5; width:320px; max-width:90vw; z-index:9999; pointer-events:none; white-space:normal; }
.cb-label input[type=checkbox] { cursor: pointer; margin: 0; flex-shrink: 0; }
.control-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.control-row label { font-size: 12px; color: #666; white-space: nowrap; }
input[type=date] { font-size: 12px; padding: 3px 5px; border: 1px solid #ccc; border-radius: 4px; max-width: 130px; }
#comfort-stats { background: #eef6ee; border: 1px solid #b8d4b8; border-radius: 6px; padding: 8px; }
#comfort-overall { font-weight: 600; font-size: 12px; margin-bottom: 6px; }
.room-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 4px; }
.room-item { background: white; border: 1px solid #ddd; border-radius: 4px; padding: 4px 6px; cursor: default; transition: background 0.15s; }
.room-item:hover { background: #eef4ff; border-color: #b8d4f0; }
.room-name { font-size: 10px; color: #666; line-height: 1.2; }
.room-pct { font-weight: 600; font-size: 12px; }
.room-src { font-size: 9px; color: #888; line-height: 1.3; }
#comfort-stats.has-gaps { background: #fff5e6; border: 1px solid #e8a840; }
#hist-stats-box.has-gaps { background: #fff5e6 !important; border-color: #e8a840 !important; }
#periodic-comp-box.has-gaps { background: #fff5e6 !important; border-color: #e8a840 !important; }
.room-item.has-gap { background: #f5d4a0; border-color: #d4a040; }
.room-item.has-gap:hover { background: #f0c880; border-color: #c89030; }
#gap-warning { font-size: 11px; color: #8a6d20; line-height: 1.4; margin-bottom: 6px; }
#gap-dropdown-wrap { margin-bottom: 6px; }
#gap-dropdown { font-size: 11px; width: 100%; padding: 3px 5px; border: 1px solid #d4a040; border-radius: 4px; background: #fffaf0; cursor: pointer; color: #6a5020; }
.gap-tip { display: none; position: fixed; background: #333; color: white; font-size: 11px; padding: 8px 10px; border-radius: 5px; line-height: 1.5; max-width: 280px; z-index: 9999; pointer-events: none; white-space: normal; }
.gap-tip .gap-entry { margin-bottom: 2px; }
.gap-tip .gap-more { color: #ccc; font-style: italic; margin-top: 2px; }
.gap-tip .gap-total { border-top: 1px solid #555; margin-top: 4px; padding-top: 4px; color: #f0c060; font-weight: 600; font-size: 10px; }
.periodic-warning { font-size: 11px; line-height: 1.4; padding: 4px 6px; margin-bottom: 4px; border-radius: 4px; background: #f0f0f0; color: #666; }
.periodic-warning.orange { background: #fff5e6; color: #8a6d20; border: 1px solid #e8a840; }
.periodic-warning.red { background: #fde8e8; color: #a03030; border: 1px solid #e06060; }
.hidden { display: none !important; }
/* ── Advanced Settings (Substratification) ─────────────────────────────── */
#advanced-settings-toggle { display:flex; align-items:center; gap:4px; cursor:pointer; font-size:11px; font-weight:600; color:#666; text-transform:uppercase; letter-spacing:0.05em; padding:2px 0; user-select:none; }
#advanced-settings-toggle:hover { color:#333; }
#advanced-settings-arrow { transition:transform 0.2s; display:inline-block; font-size:9px; }
#advanced-settings-arrow.open { transform:rotate(90deg); }
#advanced-settings-body { display:none; margin-top:6px; }
.wb-sub-label { padding-left:14px; }
.substrat-combine { display:flex; align-items:center; gap:6px; margin-bottom:8px; font-size:11px; }
.substrat-combine label { cursor:pointer; display:flex; align-items:center; gap:3px; }
.substrat-filter { border:1px solid #ddd; border-radius:5px; padding:8px; margin-bottom:6px; position:relative; background:#fafafa; }
.substrat-filter.invalid { border-color:#e06060; background:#fef5f5; }
.substrat-remove { position:absolute; top:4px; right:6px; background:none; border:none; cursor:pointer; font-size:14px; color:#999; line-height:1; padding:0 2px; }
.substrat-remove:hover { color:#e06060; }
.substrat-row { display:flex; align-items:center; gap:6px; margin-bottom:4px; flex-wrap:wrap; }
.substrat-row label { font-size:11px; color:#666; white-space:nowrap; min-width:36px; }
.substrat-row select { font-size:11px; padding:2px 4px; max-width:130px; }
.substrat-range-toggle { font-size:10px; color:#888; cursor:pointer; text-decoration:underline; user-select:none; margin-left:2px; }
.substrat-range-toggle:hover { color:#555; }
.substrat-phases { display:flex; flex-direction:column; gap:2px; margin-top:2px; }
.substrat-phases label { font-size:11px; cursor:pointer; display:flex; align-items:center; gap:3px; }
#substrat-add-btn { font-size:11px; padding:3px 8px; border:1px solid #ccc; border-radius:3px; background:#f5f5f5; cursor:pointer; color:#555; }
#substrat-add-btn:hover { background:#e8e8e8; }
.substrat-no-data { display:none; position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:14px; color:#999; font-style:italic; z-index:5; pointer-events:none; background:rgba(248,249,250,0.9); padding:8px 16px; border-radius:6px; }
/* ── Compare Mode ─────────────────────────────────────────────────────── */
#compare-body { margin-top:6px; }
.compare-set { border-left:3px solid #999; padding-left:8px; margin-bottom:8px; }
.compare-set-header { cursor:pointer; font-weight:600; font-size:11px; display:flex; align-items:center; gap:4px; user-select:none; padding:2px 0; }
.compare-set-header:hover { filter:brightness(0.8); }
.compare-arrow { transition:transform 0.2s; display:inline-block; font-size:9px; }
.compare-arrow.open { transform:rotate(90deg); }
.compare-set-body { margin-top:4px; }
.compare-set-body .sub-section-title { font-size:9px; }
.compare-set-body .cb-label { font-size:10px; }
.compare-set-body .sel-btn { font-size:9px; padding:0 4px; }
.compare-set-body .substrat-combine { font-size:10px; margin-bottom:4px; }
.compare-set-body .substrat-filter { padding:6px; margin-bottom:4px; }
.compare-set-body .substrat-row select { font-size:10px; }
.compare-add-filter-btn { font-size:10px; padding:2px 6px; border:1px solid #ccc; border-radius:3px; background:#f5f5f5; cursor:pointer; color:#555; margin-top:2px; }
.compare-add-filter-btn:hover { background:#e8e8e8; }
#compare-set-count { font-size:11px; margin-left:4px; padding:1px 3px; }
.compare-loggers-wrap { max-height:180px; overflow-y:auto; border:1px solid #eee; border-radius:3px; padding:2px 4px; margin-bottom:4px; }
.compare-hide-main { display:none !important; }
.sel-btn { font-size: 10px; padding: 1px 6px; border: 1px solid #ccc; border-radius: 3px; background: #f5f5f5; cursor: pointer; color: #555; }
.sel-btn:hover { background: #e8e8e8; }
.lock-btn { font-size: 10px; padding: 1px 6px; border: 1px solid #ccc; border-radius: 3px; background: #f5f5f5; cursor: pointer; color: #555; }
.lock-btn:hover { background: #e8e8e8; }
.lock-btn.locked { color: #fff; background: #888; border-color: #777; }
.lock-indicator { color: #bbb; font-size: 10px; margin-left: 3px; }
.sub-section-title { font-size: 10px; font-weight: 600; color: #999; text-transform: uppercase; letter-spacing: 0.05em; margin: 6px 0 2px; }
#room-logger-checkboxes .sub-section-title:first-of-type { margin-top: 0.1px; }
#download-btn { padding: 4px 10px; font-size: 12px; border: none; border-radius: 4px; cursor: pointer; background: #28a745; color: white; font-weight: 500; white-space: nowrap; }
#download-btn:hover { background: #218838; }
#download-btn:disabled { opacity: 0.6; cursor: default; }
#dl-spinner { display:none; width:16px; height:16px; border:2px solid rgba(40,167,69,0.3); border-top-color:#28a745; border-radius:50%; animation:dlspin 0.7s linear infinite; flex-shrink:0; }
@keyframes dlspin { to { transform:rotate(360deg); } }
hr.divider { border: none; border-top: 1px solid #eee; margin: 2px 0; }
#dataset-select { font-weight: 600; font-size: 13px; padding: 3px 7px; border: 1px solid #aaa; border-radius: 4px; background: #f5f5f5; }
#sidebar-toggle { display: none; background: none; border: 1px solid #ccc; border-radius: 4px; padding: 4px 7px; cursor: pointer; font-size: 16px; line-height: 1; color: #555; flex-shrink: 0; }
#sidebar-toggle:hover { background: #f0f0f0; }
#lang-wrap { position: relative; flex-shrink: 0; }
#lang-btn { background: none; border: 1px solid #ccc; border-radius: 4px; padding: 3px 6px; cursor: pointer; font-size: 16px; line-height: 1; color: #555; display: flex; align-items: center; }
#lang-btn:hover { background: #f0f0f0; border-color: #aaa; }
#lang-menu { display: none; position: absolute; right: 0; top: 100%; margin-top: 4px; background: white; border: 1px solid #ccc; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.12); z-index: 200; min-width: 110px; }
#lang-menu.open { display: block; }
#lang-menu button { display: block; width: 100%; text-align: left; padding: 6px 10px; border: none; background: none; cursor: pointer; font-size: 12px; font-family: inherit; color: #333; }
#lang-menu button:hover { background: #f0f4ff; }
#lang-menu button.active { font-weight: 600; color: #1f77b4; }
#sidebar-backdrop { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 9; }
@media (max-width: 900px) {
  #sidebar { width: 190px; padding: 8px; }
  #header h1 { font-size: 13px; }
}
@media (max-width: 680px) {
  #sidebar-toggle { display: block; }
  #sidebar { position: absolute; top: 0; left: 0; height: 100%; width: min(300px, 88vw); transform: translateX(-100%); box-shadow: 2px 0 8px rgba(0,0,0,0.15); }
  #sidebar.open { transform: translateX(0); }
  #sidebar-backdrop.open { display: block; }
  #header { padding: 5px 8px; gap: 6px; }
  #header h1 { font-size: 12px; }
  #time-bar { padding: 5px 8px; gap: 4px; }
  #time-bar-top { flex-wrap: wrap; gap: 4px; }
  #time-bar-left { flex: 0 0 100%; }
  #bar-title { display: none; }
  #time-bar-right { flex: 0 0 100%; justify-content: flex-start; gap: 6px; }
  select { font-size: 16px !important; min-height: 32px; }
  input[type=date] { font-size: 16px !important; min-height: 32px; }
  input[type=checkbox] { width: 16px; height: 16px; min-width: 16px; }
  .cb-label { font-size: 13px; padding: 3px 0; gap: 8px; }
}
@media (max-width: 420px) {
  #header h1 { display: none; }
  #download-btn { padding: 5px 8px; }
}
</style>
</head>
<body>

<div id="sidebar-backdrop"></div>
<div id="header">
  <button id="sidebar-toggle" aria-label="Toggle controls">☰</button>
  <a href="https://actionresearchprojects.net"><img id="logo" src="logo/logotrim.png" alt="ARC logo"></a>
  <h1 data-i18n="title">ARC Tanzania - Temperature &amp; Humidity Graphs</h1>
  <a href="https://actionresearchprojects.net/explainers/arc-tz-temp-humid" target="_blank" class="info-i" id="about-info-icon" title="About this dashboard" style="text-decoration:none;margin-left:auto;">i</a>
  <div id="lang-wrap">
    <button id="lang-btn" onclick="document.getElementById('lang-menu').classList.toggle('open')" title="Language"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg></button>
    <div id="lang-menu">
      <button onclick="setLanguage('en')">English</button>
      <button onclick="setLanguage('sw')">Kiswahili</button>
    </div>
  </div>
</div>

<div id="main">
  <div id="sidebar">
    <div id="line-controls">
      <div class="section" id="periodic-options" style="display:none">
        <div class="section-title" data-i18n="periodSettings">Period Settings</div>
        <label class="cb-label" style="margin-bottom:6px;">
          Group By
          <select id="period-group-by" style="margin-left:6px;font-size:12px;">
            <option value="hour" data-i18n="hour">Hour</option>
            <option value="synoptic" data-i18n="synopticHours">Synoptic Hours</option>
          </select>
        </label>
        <label class="cb-label" style="margin-bottom:6px;">
          Cycle
          <select id="natural-cycles" style="margin-left:6px;font-size:12px;">
            <option value="day" data-i18n="day">Day</option>
            <option value="year" data-i18n="year">Year</option>
            <option value="mjo">Madden&ndash;Julian Oscillation (MJO)</option>
            <option value="iod">Indian Ocean Dipole (IOD)</option>
            <option value="enso">El Ni&ntilde;o&ndash;Southern Oscillation (ENSO)</option>
          </select>
          <span class="info-i" id="natural-cycles-info" style="display:none;margin-left:4px;">i</span>
        </label>
        <div id="natural-cycles-tip" style="display:none;font-size:11px;color:#666;line-height:1.4;margin-bottom:6px;padding:6px 8px;background:#f5f5f5;border:1px solid #ddd;border-radius:4px;"></div>
        <div id="periodic-warnings" style="margin-top:6px;"></div>
      </div>
      <hr class="divider" id="periodic-divider" style="display:none">
      <div class="section" id="histogram-options" style="display:none">
        <div class="section-title" data-i18n="histogramSettings">Histogram Settings</div>
        <label class="cb-label" style="margin-bottom:6px;">
          Bar Mode
          <select id="histogram-barmode" style="margin-left:6px;font-size:12px;">
            <option value="stack" data-i18n="stacked">Stacked</option>
            <option value="overlay" data-i18n="overlay">Overlay</option>
          </select>
        </label>
      </div>
      <hr class="divider" id="histogram-options-divider" style="display:none">
      <div id="advanced-settings-wrap">
        <div id="advanced-settings-toggle" onclick="toggleAdvancedSettings()">
          <span id="advanced-settings-arrow">&#9654;</span> Advanced Settings
        </div>
        <div id="advanced-settings-body">
          <div class="substrat-combine substrat-only" style="display:none">
            <label><input type="radio" name="substrat-combine" value="all" checked> Match ALL</label>
            <label><input type="radio" name="substrat-combine" value="any"> Match ANY</label>
          </div>
          <div id="substrat-filters" class="substrat-only" style="display:none"></div>
          <button id="substrat-add-btn" class="substrat-only" style="display:none" onclick="addSubstratFilter()" data-i18n="addFilter">+ Add Filter</button>
          <label class="cb-label" id="anomalous-label" style="display:none"><input type="checkbox" id="cb-exclude-anomalous"> Exclude anomalous data</label>
          <div id="wetbulb-adv-wrap" style="display:none">
            <hr class="divider">
            <label class="cb-label"><input type="checkbox" id="cb-wetbulb"> <span data-i18n="wetBulbLabel">Wet Bulb (Tw)</span> <span class="info-i" id="wetbulb-info-icon">i</span></label>
            <div class="info-tip-fixed" id="wetbulb-info-tip"></div>
          </div>
          <hr class="divider" id="compare-divider">
          <label class="cb-label"><input type="checkbox" id="cb-compare"> <b>Compare Mode</b> <span class="info-i" id="compare-info-icon">i</span></label>
          <div class="info-tip-fixed" id="compare-info-tip"></div>
          <div id="compare-body" style="display:none">
            <div style="margin:4px 0 6px">
              <label style="font-size:11px;">Number of sets:
                <select id="compare-set-count">
                  <option value="2">2</option>
                  <option value="3">3</option>
                  <option value="4">4</option>
                </select>
              </label>
            </div>
            <div id="compare-sets"></div>
          </div>
        </div>
        <hr class="divider">
      </div>
      <div class="section">
        <div class="section-title" style="display:flex;align-items:center;justify-content:space-between;">Loggers<button class="sel-btn" id="reset-line-btn">Reset to default</button></div>
        <div id="logger-checkboxes"></div>
      </div>
      <hr class="divider">
      <div class="section">
        <div class="section-title" data-i18n="metrics">Metrics</div>
        <label class="cb-label"><input type="checkbox" id="cb-temperature" checked> Temperature</label>
        <label class="cb-label" id="humidity-label"><input type="checkbox" id="cb-humidity" checked> Humidity</label>
      </div>
      <hr class="divider">
      <div class="section" id="line-options-section">
        <div class="section-title" data-i18n="options">Options</div>
        <label class="cb-label"><input type="checkbox" id="cb-threshold" checked> 32–35°C Threshold</label>
        <label class="cb-label"><input type="checkbox" id="cb-seasons" checked> Season Lines</label>
      </div>
      <hr class="divider" id="line-options-divider">
      <div class="section" id="historic-section" style="display:none">
        <label class="cb-label"><input type="checkbox" id="cb-historic-mode"> <b>Long-Term Mode</b> <span class="info-i" id="longterm-info-icon">i</span></label>
        <div class="info-tip-fixed" id="longterm-info-tip"></div>
        <div id="historic-series-checkboxes" style="display:none;margin-top:4px"></div>
        <div style="font-size:10px;color:#888;margin-top:4px;line-height:1.3"><span id="longterm-note-pre" data-i18n="longTermNotePre">Long-term historic and projected future data generated from</span> <a href="https://atlas.climate.copernicus.eu/atlas" target="_blank" style="color:#6a9fd8">Copernicus Climate Change Service</a> <span id="longterm-note-post" data-i18n="longTermNotePost">information 2026.</span></div>
      </div>
      <hr class="divider">
      <div id="periodic-completeness" class="hidden">
        <div id="periodic-comp-box" style="background:#f8f8f8;border:1px solid #ddd;border-radius:6px;padding:8px;">
          <div id="periodic-comp-warning" style="font-size:11px;color:#666;line-height:1.4;margin-bottom:4px;"></div>
          <div id="periodic-comp-dropdown-wrap" class="hidden" style="margin-bottom:4px;"><select id="periodic-comp-dropdown" style="font-size:11px;width:100%;padding:3px 5px;border:1px solid #ccc;border-radius:4px;background:#fafafa;cursor:pointer;color:#555;"></select></div>
          <div id="periodic-comp-grid" class="room-grid"></div>
        </div>
        <div class="gap-tip" id="periodic-comp-tip"></div>
        <hr class="divider">
      </div>
      <div id="histogram-stats" class="hidden">
        <div id="hist-stats-box" style="background:#eef6ee;border:1px solid #b8d4b8;border-radius:6px;padding:8px;">
          <div id="hist-overall" style="font-weight:600;font-size:12px;margin-bottom:6px;">-</div>
          <div id="hist-gap-warning" class="hidden" style="font-size:11px;color:#8a6d20;line-height:1.4;margin-bottom:6px;"></div>
          <div id="hist-gap-dropdown-wrap" class="hidden" style="margin-bottom:6px;"><select id="hist-gap-dropdown" style="font-size:11px;width:100%;padding:3px 5px;border:1px solid #d4a040;border-radius:4px;background:#fffaf0;cursor:pointer;color:#6a5020;"></select></div>
          <div class="room-grid" id="hist-room-grid"></div>
        </div>
        <div class="gap-tip" id="hist-gap-tip"></div>
        <hr class="divider">
      </div>
      <div style="font-size:10px;color:#888;line-height:1.3" id="data-source-notes">
        <span data-i18n="hourlyExtTemp">Hourly external temperature from</span> <a href="https://open-meteo.com/" target="_blank" style="color:#6a9fd8">Open-Meteo</a>. <span data-i18n="forecastNote">Forecast shows the next 16 days.</span>
      </div>
    </div>

    <div id="comfort-controls" class="hidden">
      <div class="section">
        <div class="section-title" data-i18n="options">Options</div>
        <label class="cb-label"><input type="checkbox" id="cb-density" checked> Density Heatmap <span class="info-i" id="density-info-icon">i</span></label>
        <div id="info-fixed-tip"></div>
        <div style="margin-top:6px;margin-bottom:4px;">
          <div style="font-size:11px;color:#666;margin-bottom:3px;">Comfort band <span class="info-i" id="en16798-info-icon">i</span></div>
          <div class="info-tip-fixed" id="en16798-info-tip"></div>
          <select id="comfort-model" style="width:100%;font-size:12px;">
            <option value="rh_gt_60" selected>RH&gt;60% (Vellei et al.)</option>
            <option value="rh_40_60">40%&lt;RH≤60% (Vellei et al.)</option>
            <option value="rh_le_40">RH≤40% (Vellei et al.)</option>
            <option value="default" data-i18n="comfortModelDefault">Default comfort model</option>
            <option value="none" data-i18n="comfortModelNone">No comfort band</option>
          </select>
        </div>
      </div>
      <hr class="divider">
      <div class="section">
        <div class="section-title" style="display:flex;align-items:center;justify-content:space-between;">Room Loggers<button class="sel-btn" id="reset-comfort-btn">Reset to default</button></div>
        <div id="room-logger-checkboxes"></div>
      </div>
      <hr class="divider">
      <div id="comfort-stats">
        <div id="comfort-overall">-</div>
        <div id="gap-warning" class="hidden"></div>
        <div id="gap-dropdown-wrap" class="hidden"><select id="gap-dropdown"></select></div>
        <div class="room-grid" id="comfort-room-grid"></div>
      </div>
      <div class="gap-tip" id="gap-tip"></div>
      <div style="margin-top:8px;margin-bottom:4px;">
        <div style="font-size:11px;color:#666;margin-bottom:3px;">Percentage calculation</div>
        <select id="comfort-pct-mode" style="width:100%;font-size:12px;">
          <option value="below_upper" selected data-i18n="belowUpper">Below upper boundary</option>
          <option value="within" data-i18n="withinComfort">Within comfort zone</option>
          <option value="above_lower" data-i18n="aboveLower">Above lower boundary</option>
        </select>
      </div>
    </div>

    <div style="margin-top:auto;padding-top:8px;border-top:1px solid #eee;">
      <a href="https://actionresearchprojects.net/explainers/data-flow" target="_blank" style="text-decoration:none;display:block;">
        <div id="fetch-time-notes" style="font-size:10px;color:#888;line-height:1.6;cursor:pointer;"></div>
      </a>
      <div id="dataset-reading-count" style="font-size:10px;color:#888;line-height:1.6;margin-top:2px;"></div>
    </div>
  </div>

  <div id="chart-area">
    <div id="time-bar">
      <div id="time-bar-top">
        <div id="time-bar-left">
          <select id="dataset-select">
            <option value="house5" data-i18n="house5">House 5</option>
            <option value="schoolteacher" data-i18n="schoolteacher">Schoolteacher's House</option>
          </select>
          <select id="chart-type">
            <option value="line" data-i18n="lineGraph">Line Graph</option>
            <option value="comfort" data-i18n="adaptiveComfort">Adaptive Comfort</option>
            <option value="histogram" data-i18n="histogram">Histogram</option>
            <option value="periodic" data-i18n="averageProfiles">Average Profiles</option>
            <option value="beta" style="color:#c0392b" data-i18n="betaFeatures">Beta Features</option>
          </select>
          <select id="beta-chart-type" style="display:none">
            <option value="beta-diff" data-i18n="betaDiff">Temperature Differential</option>
            <option value="beta-decrement" data-i18n="betaDecrement">Decrement Factor</option>
            <option value="beta-lag" data-i18n="betaLag">Thermal Lag</option>
            <option value="beta-quality" data-i18n="betaQuality">Data Quality</option>
          </select>
          <span class="info-i" id="chart-info-icon">i</span>
          <div id="chart-info-tip"></div>
        </div>
        <span id="bar-title"></span>
        <div id="time-bar-right">
          <div class="control-row">
            <label>Range:</label>
            <select id="time-mode">
              <option value="all" data-i18n="allTime">All time</option>
              <option value="between" data-i18n="betweenDates">Between dates</option>
              <option value="year" data-i18n="year">Year</option>
              <option value="season" data-i18n="season">Season</option>
              <option value="month" data-i18n="month">Month</option>
              <option value="week" data-i18n="week">Week</option>
              <option value="day" data-i18n="day">Day</option>
            </select>
          </div>
          <div id="between-inputs" class="control-row hidden">
            <label>From <input type="date" id="date-start"></label>
            <label>To <input type="date" id="date-end"></label>
          </div>
          <div id="year-input"  class="hidden"><select id="year-select"></select></div>
          <div id="season-input" class="hidden"><select id="season-select"></select></div>
          <div id="month-input" class="hidden"><select id="month-select"></select></div>
          <div id="week-input"  class="hidden"><select id="week-select"></select></div>
          <div id="day-input"   class="hidden"><select id="day-select"></select></div>
          <button id="download-btn" data-i18n="downloadPng">Download PNG</button>
          <div id="dl-spinner"></div>
        </div>
      </div>
    </div>
    <div id="ext-data-warning" class="hidden" style="background:#fff3cd;border:1px solid #ffc107;border-radius:4px;padding:6px 10px;margin:4px 10px;font-size:12px;color:#856404;flex-shrink:0;">
      &#9888; <span id="ext-data-warning-pre">Open-Meteo external temperature data only covers to</span> <b id="ext-data-end"></b><span id="ext-data-warning-post">. Update <code>open-meteo</code> CSV to see adaptive comfort for recent dates.</span>
    </div>
    <div id="chart"></div>
    <span class="info-i" id="rm-xaxis-info-icon" style="display:none;position:fixed;z-index:60;">i</span>
    <div class="info-tip-fixed" id="rm-xaxis-info-tip"></div>
    <div id="hist-hover-tip" style="display:none;position:absolute;z-index:100;pointer-events:none;background:rgba(30,30,30,0.92);color:#fff;font-family:'Ubuntu',sans-serif;font-size:12px;padding:6px 10px;border-radius:4px;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,0.25);"></div>
    <div class="substrat-no-data" id="substrat-no-data" data-i18n="noDataFilter">No data matches the selected filter</div>
    <div id="chart-loading" style="display:none;position:absolute;inset:0;background:rgba(255,255,255,0.82);z-index:50;flex-direction:column;align-items:center;justify-content:center;gap:10px;pointer-events:none;">
      <div style="font-size:12px;color:#555;font-family:'Ubuntu',sans-serif" data-i18n="loading">Loading chart…</div>
      <div style="width:160px;height:5px;background:#e0e0e0;border-radius:3px;overflow:hidden;">
        <div id="chart-loading-bar" style="height:100%;width:0%;background:#4a90d9;border-radius:3px;transition:none;"></div>
      </div>
    </div>
    <div id="legend-tooltip" style="display:none;position:fixed;background:#333;color:white;padding:3px 8px;border-radius:3px;font-size:10px;white-space:nowrap;z-index:200;pointer-events:none;"></div>
    <div id="anomalous-fixed-tip"></div>
  </div>
</div>

<script>
const ALL_DATA = __DATA__;
const HISTORIC = __HISTORIC__;
const FETCH_TIMES = __FETCH_TIMES__;
const DATA_FRESHNESS = __DATA_FRESHNESS__;
const LOGO_B64 = '__LOGO_B64__';
const LOGO_ASPECT = __LOGO_ASPECT__;
const CLIMATE_COLORS = {
  'ERA5': '#333333',
  'SSP1-1.9': '#1a9850',
  'SSP1-2.6': '#91cf60',
  'SSP2-4.5': '#fee08b',
  'SSP3-7.0': '#fc8d59',
  'SSP5-8.5': '#d73027',
};

// ── Compare mode color utilities ──────────────────────────────────────────────
const COMPARE_HUES = {
  2: [0, 220],
  3: [0, 50, 220],
  4: [0, 50, 140, 220],
};
const COMPARE_SET_NAMES = ['Set A', 'Set B', 'Set C', 'Set D'];
function compareShades(setIndex, setCount, loggerCount) {
  const hue = COMPARE_HUES[setCount][setIndex];
  const shades = [];
  for (let i = 0; i < loggerCount; i++) {
    const t = loggerCount === 1 ? 0.4 : i / (loggerCount - 1);
    const lightness = 30 + t * 30;
    const saturation = 85 - t * 15;
    shades.push('hsl(' + hue + ', ' + saturation + '%, ' + lightness + '%)');
  }
  return shades;
}
function compareBaseColor(setIndex, setCount) {
  const hue = COMPARE_HUES[setCount][setIndex];
  return 'hsl(' + hue + ', 75%, 45%)';
}

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  datasetKey: 'house5',
  chartType: 'line',
  timeMode: 'all',
  selectedLoggers: new Set(),
  selectedMetrics: new Set(['temperature', 'humidity']),
  selectedRoomLoggers: new Set(),
  showThreshold: true,
  showSeasonLines: true,
  showDensity: true,
  historicMode: false,
  selectedHistoricSeries: new Set(),
  comfortModel: 'rh_gt_60',
  comfortPctMode: 'below_upper',
  periodCycle: 'day',
  periodGroupBy: 'hour',
  showSectionAvg: {external: true, room: true, structural: true},
  lockedAvg: {external: null, room: null, structural: null}, // null=unlocked, Set=locked logger IDs
  betweenStart: null,
  betweenEnd: null,
  selectedYear: null,
  selectedMonth: null,
  selectedWeek: null,
  selectedDay: null,
  substratFilters: [],
  substratCombine: 'all',
  histogramBarmode: 'stack',
  excludeAnomalous: false,
  wetBulbEnabled: false,
  wetBulbLoggers: new Set(),
  compareEnabled: false,
  compareSetCount: 2,
  compareSets: [],
};

// ── Language / i18n ────────────────────────────────────────────────────────────
let currentLang = localStorage.getItem('arcLang') || 'en';
const I18N = {
  en: {
    title: 'ARC Tanzania - Temperature & Humidity Graphs',
    periodSettings: 'Period Settings',
    histogramSettings: 'Histogram Settings',
    advancedSettings: 'Advanced Settings',
    loggers: 'Loggers',
    metrics: 'Metrics',
    options: 'Options',
    roomLoggers: 'Room Loggers',
    groupBy: 'Group By',
    cycle: 'Cycle',
    barMode: 'Bar Mode',
    range: 'Range:',
    comfortBand: 'Comfort band',
    pctCalc: 'Percentage calculation',
    numSets: 'Number of sets:',
    from: 'From ',
    to: 'To ',
    temperature: 'Temperature',
    humidity: 'Humidity',
    threshold: '32\u201335\u00b0C Threshold',
    seasonLines: 'Season Lines',
    longTermMode: 'Long-Term Mode',
    densityHeatmap: 'Density Heatmap',
    compareMode: 'Compare Mode',
    excludeAnomalous: 'Exclude anomalous data',
    downloadPng: 'Download PNG',
    resetDefault: 'Reset to default',
    addFilter: '+ Add Filter',
    matchAll: 'Match ALL',
    matchAny: 'Match ANY',
    loading: 'Loading chart\u2026',
    noDataFilter: 'No data matches the selected filter',
    btnAll: 'All',
    btnNone: 'None',
    lockAvg: 'Lock Avg',
    unlockAvg: 'Unlock Avg',
    hour: 'Hour',
    synopticHours: 'Synoptic Hours',
    day: 'Day',
    week: 'Week',
    month: 'Month',
    year: 'Year',
    season: 'Season',
    allTime: 'All time',
    betweenDates: 'Between dates',
    lineGraph: 'Line Graph',
    histogram: 'Histogram',
    adaptiveComfort: 'Adaptive Comfort',
    averageProfiles: 'Average Profiles',
    betaFeatures: 'Beta Features',
    betaDiff: 'Temperature Differential',
    betaDecrement: 'Decrement Factor',
    betaLag: 'Thermal Lag',
    betaQuality: 'Data Quality',

    betaDiffTitle: 'Indoor\u2013Outdoor Temperature Differential',
    betaDecrementTitle: 'Decrement Factor by Room',
    betaLagTitle: 'Diurnal Thermal Lag by Room',
    betaQualityTitle: 'Data Quality & Anomaly Detection',

    betaDiffAxis: 'Temperature Differential (\u00b0C)',
    betaDecrementAxis: 'Decrement Factor (indoor swing / outdoor swing)',
    betaLagAxis: 'Thermal Lag (hours)',
    infoBetaDiff: 'Shows the difference between indoor and outdoor temperature at each time step. Positive = hotter inside than outside (building trapping heat). Negative = cooler inside (building providing relief). Per-room lines let you compare which spaces perform best.',
    infoBetaDecrement: 'How much the building dampens the outdoor temperature swing each day. Calculated as indoor swing divided by outdoor swing. Example: outdoor high 35\u00b0C, low 23\u00b0C (swing = 12\u00b0C); indoor high 30\u00b0C, low 26\u00b0C (swing = 4\u00b0C). Factor = 4/12 = 0.33. Lower values mean the building smooths out temperature extremes better. A value of 1.0 means no damping at all.',
    infoBetaLag: 'Thermal lag measures how many hours the indoor temperature peak trails the outdoor peak. A 4-hour lag means the building\'s thermal mass absorbs heat slowly and releases it later, ideally when it\'s cooler outside.',
    infoBetaQuality: 'Data health overview showing per-sensor coverage and gap detection (periods >6h with no readings). Green = good data, orange = gap. Admin-flagged anomalous ranges shown in purple where applicable.',

    stacked: 'Stacked',
    overlay: 'Overlay',
    belowUpper: 'Below upper boundary',
    withinComfort: 'Within comfort zone',
    aboveLower: 'Above lower boundary',
    // Dataset labels
    house5: 'House 5',
    schoolteacher: "Schoolteacher's House",
    // Section sub-headers
    sectionExternal: 'External',
    sectionRoom: 'Room',
    sectionStructural: 'Structural',
    // Chart titles
    tempAndHumid: 'Temperature &amp; Humidity',
    tempOnly: 'Temperature',
    humidOnly: 'Humidity',
    tempAndHumidDist: 'Temperature &amp; Humidity Distribution',
    tempDist: 'Temperature Distribution',
    humidDist: 'Humidity Distribution',
    avgProfiles: 'Average Profiles',
    adaptiveComfortTitle: 'Adaptive Comfort',
    // Axis labels
    dateTime: 'Date / Time',
    hourOfDay: 'Hour of Day',
    timeOfDay: 'Time of Day',
    monthOfYear: 'Month of Year',
    weekOfYear: 'Week of Year',
    dayOfYear: 'Day of Year',
    tanzanianSeason: 'Tanzanian Season',
    tempAxis: 'Temperature (\u00b0C)',
    humidAxis: 'Humidity (%RH)',
    tempHumidAxis: 'Temperature (\u00b0C) / Humidity (%RH)',
    airTempAxis: 'Air temperature (\u00b0C)  [\u2248 operative temp.]',
    runningMeanAxis: 'Running mean external temperature (°C)',
    proportionAxis: 'Proportion of readings per sensor',
    sumAxis: 'Sum of reading distribution across sensors',
    // Dynamic text
    dataRangesFrom: 'Data ranges from',
    dataRangesTo: 'to',
    overall: 'Overall',
    ofTempReadingsBelow: 'of temperature readings below 32\u00b0C',
    dataCompleteness: 'Data completeness',
    seriesHaveGaps: 'series have gaps of 24h+. Hover orange boxes for details.',
    noDataRange: 'No data available in the selected range',
    noDataSelected: 'No data in selected range',
    forecast: 'Forecast',
    forecastNote: 'Forecast shows the next 16 days.',
    hourlyExtTemp: 'Hourly external temperature from',
    // Avg labels
    externalAvg: 'External Avg',
    roomAvg: 'Room Avg',
    structuralAvg: 'Structural Avg',
    // Periodic labels
    phase: 'Phase',
    // Hover text
    source: 'Source',
    runningMean: 'Running mean',
    roomTemp: 'Room temp',
    extSource: 'Ext. source',
    sensor: 'Sensor',
    // Info tooltip texts
    infoLine: 'See how temperature and humidity change over time for each logger. Vertical lines show season boundaries and the red band marks the 32-35\u00b0C heat stress range.',
    infoHistogramStack: 'Shows how often each temperature or humidity level occurs. Useful for spotting where conditions cluster and how rooms compare overall. Normalised so loggers with different sampling rates are comparable. Bars are stacked. Hover to see individual logger values.',
    infoHistogramOverlay: 'Shows how often each temperature or humidity level occurs. Useful for spotting where conditions cluster and how rooms compare overall. Normalised so loggers with different sampling rates are comparable. Bars are overlaid. Hover to see how many loggers share each bin.',
    infoComfort: 'Plots room temperature against recent outdoor conditions to show whether a building is keeping occupants comfortable without mechanical cooling. Points inside the green band are within the adaptive comfort zone for the selected humidity model.',
    infoPeriodic: 'Reveals typical patterns by averaging readings across a cycle. Use "Day" to see how rooms heat up and cool down over 24 hours, or "Year" for seasonal trends. Climate oscillations (MJO, IOD, ENSO) show how large-scale weather patterns affect local conditions.',
    infoDensity: 'Darker areas = more readings concentrated there. Scale shows % of all plotted points in each region.',
    infoCompare: 'Compare different time periods on the same chart to see how conditions have changed, e.g. this month vs last month, or dry season vs wet season. Each set can have its own loggers and date range.',
    infoLongTerm: 'Places current sensor readings in a longer climate context. Shows historic temperature data back to 1940 and future projections under different climate scenarios, so you can see how today\'s conditions relate to past and expected trends.',
    wetBulb: 'Wet Bulb',
    wetBulbSuffix: '(Wet bulb)',
    wetBulbHover: 'Wet bulb (Tw)',
    infoWetBulb: 'Wet bulb temperature (Tw) is the lowest temperature achievable by evaporative cooling, a key heat stress indicator. When Tw exceeds 32°C, cooling by sweating becomes difficult; above 35°C it is dangerous for prolonged exposure. Calculated using the Stull (2011) approximation, accurate to ±0.3°C in tropical conditions. Valid range: –20 to 50°C and 5–99% RH. Readings below 5% RH are shown as gaps; readings above 99% RH (sensor saturation) are clamped to 99% before calculating. Shown as a dashed line in the same colour as the parent sensor.',
    infoComfortBand: 'The green band shows the range of indoor temperatures considered comfortable, based on the ASHRAE-55 adaptive comfort standard. The default model ignores humidity, which can overestimate overheating by around 30%. The Vellei et al. options use <a href="https://doi.org/10.1016/j.buildenv.2017.08.005" target="_blank" style="color:#6a9fd8">humidity-aware comfort bands</a> derived from global field study data, better reflecting how people adapt in humid climates.',
    infoRunningMean: 'The running mean is an exponentially weighted average of past outdoor temperatures, where recent days count most. It captures how people acclimatise to changing weather: when outdoor temperatures have been high, occupants can tolerate higher indoor temperatures. <a href="https://actionresearchprojects.net/explainers/running-mean" target="_blank" style="color:#6a9fd8">Read more →</a>',
    // Wet bulb checkbox label
    wetBulbLabel: 'Wet Bulb (Tw)',
    // Comfort model dropdown
    comfortModelDefault: 'Default comfort model',
    comfortModelNone: 'No comfort band',
    // External data warning
    extDataWarningPre: 'Open-Meteo external temperature data only covers to',
    extDataWarningPost: '. Update <code>open-meteo</code> CSV to see adaptive comfort for recent dates.',
    // Long-term historic note
    longTermNotePre: 'Long-term historic and projected future data generated from',
    longTermNotePost: 'information 2026.',
    // Substrat filter labels
    filterBy: 'Filter by',
    optNone: 'None',
    dayOfMonth: 'Day of Month',
    rangeToggle: 'range',
    singleToggle: 'single',
    // Synoptic period labels
    lateNight: 'Late Night',
    morning: 'Morning',
    afternoon: 'Afternoon',
    evening: 'Evening',
    // Compare/filter description fragments
    noLoggers: 'No loggers',
    noFilter: 'No filter',
    // Beta data quality legend
    goodData: 'Good data',
    gapLegend: 'Gap (>6h)',
    adminFlagged: 'Admin flagged',
    noDifference: 'no difference',
    // Average profiles group-by labels
    phase18: 'Phase (1–8)',
    phasePNN: 'Phase (+/−/Neutral)',
    phaseENSO: 'Phase (Niño/Niña/Neutral)',
  },
  sw: {
    title: 'ARC Tanzania - Grafu za Joto na Unyevunyevu',
    periodSettings: 'Mipangilio ya Kipindi',
    histogramSettings: 'Mipangilio ya Histogramu',
    advancedSettings: 'Mipangilio ya Juu',
    loggers: 'Vihisi',
    metrics: 'Vipimo',
    options: 'Chaguo',
    roomLoggers: 'Vihisi vya Chumba',
    groupBy: 'Panga kwa',
    cycle: 'Mzunguko',
    barMode: 'Mtindo wa Mhimili',
    range: 'Muda:',
    comfortBand: 'Bendi ya Starehe',
    pctCalc: 'Hesabu ya asilimia',
    numSets: 'Idadi ya seti:',
    from: 'Kutoka ',
    to: 'Hadi ',
    temperature: 'Joto',
    humidity: 'Unyevunyevu',
    threshold: 'Kiwango cha 32\u201335\u00b0C',
    seasonLines: 'Mistari ya Msimu',
    longTermMode: 'Hali ya Muda Mrefu',
    densityHeatmap: 'Ramani ya Msongamano',
    compareMode: 'Hali ya Kulinganisha',
    excludeAnomalous: 'Ondoa data isiyo ya kawaida',
    downloadPng: 'Pakua PNG',
    resetDefault: 'Rejesha chaguo-msingi',
    addFilter: '+ Ongeza Chujio',
    matchAll: 'Lingana ZOTE',
    matchAny: 'Lingana YOYOTE',
    loading: 'Inapakia grafu\u2026',
    noDataFilter: 'Hakuna data inayolingana na chujio',
    btnAll: 'Zote',
    btnNone: 'Hakuna',
    lockAvg: 'Funga Wastani',
    unlockAvg: 'Fungua Wastani',
    hour: 'Saa',
    synopticHours: 'Saa za Sinoptiki',
    day: 'Siku',
    week: 'Wiki',
    month: 'Mwezi',
    year: 'Mwaka',
    season: 'Msimu',
    allTime: 'Wakati wote',
    betweenDates: 'Kati ya tarehe',
    lineGraph: 'Grafu ya Mstari',
    histogram: 'Histogramu',
    adaptiveComfort: 'Faraja ya Kubadilika',
    averageProfiles: 'Wastani wa Profaili',
    betaFeatures: 'Vipengele vya Beta',
    betaDiff: 'Tofauti ya Joto',
    betaDecrement: 'Kipengele cha Kupunguza',
    betaLag: 'Ucheleweshaji wa Joto',
    betaQuality: 'Ubora wa Data',
    betaDiffTitle: 'Tofauti ya Joto Ndani\u2013Nje',
    betaDecrementTitle: 'Kipengele cha Kupunguza kwa Chumba',
    betaLagTitle: 'Ucheleweshaji wa Joto kwa Chumba',
    betaQualityTitle: 'Ubora wa Data na Ugunduzi wa Kasoro',
    betaDiffAxis: 'Tofauti ya Joto (\u00b0C)',
    betaDecrementAxis: 'Kipengele cha Kupunguza',
    betaLagAxis: 'Ucheleweshaji (masaa)',
    infoBetaDiff: 'Inaonyesha tofauti kati ya joto la ndani na nje. Chanya = ndani ni moto zaidi kuliko nje. Hasi = ndani ni baridi zaidi.',
    infoBetaDecrement: 'Uwiano wa mabadiliko ya joto la ndani na nje kwa siku. Nambari ndogo ni bora: inamaanisha jengo linapunguza joto la nje vizuri.',
    infoBetaLag: 'Masaa mangapi kilele cha joto la ndani kinachelewa nyuma ya kilele cha nje. Ucheleweshaji mrefu = thermal mass nzuri.',
    infoBetaQuality: 'Muhtasari wa afya ya data: muda wa sensor na mapungufu. Kijani = data nzuri, machungwa = pengo. Maeneo yaliyotambuliwa na msimamizi yanaonyeshwa kwa zambarau.',

    stacked: 'Imerundikwa',
    overlay: 'Imefunikwa',
    belowUpper: 'Chini ya mpaka wa juu',
    withinComfort: 'Ndani ya eneo la starehe',
    aboveLower: 'Juu ya mpaka wa chini',
    house5: 'Nyumba 5',
    schoolteacher: 'Nyumba ya Mwalimu',
    sectionExternal: 'Nje',
    sectionRoom: 'Chumba',
    sectionStructural: 'Muundo',
    tempAndHumid: 'Joto na Unyevunyevu',
    tempOnly: 'Joto',
    humidOnly: 'Unyevunyevu',
    tempAndHumidDist: 'Usambazaji wa Joto na Unyevunyevu',
    tempDist: 'Usambazaji wa Joto',
    humidDist: 'Usambazaji wa Unyevunyevu',
    avgProfiles: 'Wastani wa Profaili',
    adaptiveComfortTitle: 'Faraja ya Kubadilika',
    dateTime: 'Tarehe / Saa',
    hourOfDay: 'Saa ya Siku',
    timeOfDay: 'Wakati wa Siku',
    monthOfYear: 'Mwezi wa Mwaka',
    weekOfYear: 'Wiki ya Mwaka',
    dayOfYear: 'Siku ya Mwaka',
    tanzanianSeason: 'Msimu wa Tanzania',
    tempAxis: 'Joto (\u00b0C)',
    humidAxis: 'Unyevunyevu (%RH)',
    tempHumidAxis: 'Joto (\u00b0C) / Unyevunyevu (%RH)',
    airTempAxis: 'Joto la hewa (\u00b0C)  [\u2248 joto la uendeshaji]',
    runningMeanAxis: 'Wastani wa joto la nje (°C)',
    proportionAxis: 'Uwiano wa masomo kwa kila kihisi',
    sumAxis: 'Jumla ya usambazaji wa masomo kwa vihisi',
    dataRangesFrom: 'Data kuanzia',
    dataRangesTo: 'hadi',
    overall: 'Jumla',
    ofTempReadingsBelow: 'ya masomo ya joto chini ya 32\u00b0C',
    dataCompleteness: 'Ukamilifu wa data',
    seriesHaveGaps: 'safu zina mapungufu ya saa 24+. Elekeza masanduku ya machungwa kwa maelezo.',
    noDataRange: 'Hakuna data katika kipindi kilichochaguliwa',
    noDataSelected: 'Hakuna data katika kipindi kilichochaguliwa',
    forecast: 'Utabiri',
    forecastNote: 'Utabiri unaonyesha siku 16 zijazo.',
    hourlyExtTemp: 'Joto la nje la kila saa kutoka',
    externalAvg: 'Wastani wa Nje',
    roomAvg: 'Wastani wa Chumba',
    structuralAvg: 'Wastani wa Muundo',
    phase: 'Awamu',
    source: 'Chanzo',
    runningMean: 'Wastani unaoendelea',
    roomTemp: 'Joto la chumba',
    extSource: 'Chanzo cha nje',
    sensor: 'Kihisi',
    // Info tooltip texts
    infoLine: 'Angalia jinsi joto na unyevunyevu unavyobadilika kwa kila sensor. Mistari ya wima inaonyesha mipaka ya misimu na bendi nyekundu inaonyesha kiwango cha joto hatari cha 32-35\u00b0C.',
    infoHistogramStack: 'Inaonyesha ni mara ngapi kiwango fulani cha joto au unyevunyevu kinatokea. Inasaidia kuona hali za kawaida na kulinganisha vyumba. Baa zimepangwa. Elekeza ili kuona thamani za kila sensor.',
    infoHistogramOverlay: 'Inaonyesha ni mara ngapi kiwango fulani cha joto au unyevunyevu kinatokea. Inasaidia kuona hali za kawaida na kulinganisha vyumba. Baa zimeingizwa juu ya nyingine. Elekeza ili kuona ni sensors ngapi zinashiriki kila bin.',
    infoComfort: 'Inaonyesha joto la chumba dhidi ya hali ya hewa ya nje ili kuona kama jengo linaweka wenyeji katika hali nzuri bila baridi ya mitambo. Alama ndani ya bendi ya kijani ziko ndani ya eneo la starehe.',
    infoPeriodic: 'Inaonyesha mifumo ya kawaida kwa kupata wastani wa masomo. Tumia "Siku" kuona jinsi vyumba vinavyopata joto na baridi kwa saa 24, au "Mwaka" kwa mwenendo wa misimu.',
    infoDensity: 'Maeneo meusi = masomo mengi yamejilimbikizia hapo. Kipimo kinaonyesha % ya alama zote zilizochorwa katika kila eneo.',
    infoCompare: 'Linganisha vipindi tofauti vya wakati kwenye chati moja ili kuona jinsi hali zilivyobadilika, k.m. mwezi huu dhidi ya mwezi uliopita, au kiangazi dhidi ya masika. Kila seti inaweza kuwa na sensors na tarehe zake.',
    infoLongTerm: 'Inaweka masomo ya sasa ya sensor katika muktadha wa hali ya hewa ya muda mrefu. Inaonyesha data ya joto ya kihistoria tangu 1940 na makadirio ya siku zijazo chini ya hali tofauti za hali ya hewa.',
    wetBulb: 'Joto la Mvua (Tw)',
    wetBulbSuffix: '(Joto la mvua)',
    wetBulbHover: 'Joto la mvua (Tw)',
    infoWetBulb: 'Joto la mvua (Tw) ni joto la chini kabisa linaloweza kufikiwa kwa kupoa kwa uvukizi, kiashiria muhimu cha msongo wa joto. Imehesabiwa kwa kutumia mkaribisho wa Stull (2011). Masafa halali: –20 hadi 50°C na 5–99% RH. Maadili chini ya 5% RH yanaonyeshwa kama mapengo; maadili zaidi ya 99% RH (kipimo kikifikia kikomo chake) yanafupishwa hadi 99% kabla ya kuhesabu. Inaonyeshwa kama mstari wa nukta katika rangi ile ile ya sensor.',
    infoComfortBand: 'Bendi ya kijani inaonyesha kiwango cha joto la ndani kinachochukuliwa kuwa na starehe, kulingana na kiwango cha ASHRAE-55. Mtindo wa kawaida unapuuza unyevunyevu, ambao unaweza kukadiri kupita kiasi kwa karibu 30%. Chaguo za Vellei et al. zinatumia <a href="https://doi.org/10.1016/j.buildenv.2017.08.005" target="_blank" style="color:#6a9fd8">bendi za starehe zinazozingatia unyevunyevu</a> kutoka data ya utafiti wa kimataifa.',
    infoRunningMean: 'Wastani unaoendelea ni wastani uliopimwa kwa uzito zaidi kwa siku za hivi karibuni za joto la nje. Unaonyesha jinsi watu wanavyozoea hali ya hewa: joto la nje likiwa juu, wenyeji wanastahimili joto zaidi ndani, hivyo bendi ya starehe inasogea kulia. <a href="https://actionresearchprojects.net/explainers/running-mean" target="_blank" style="color:#6a9fd8">Soma zaidi →</a>',
    wetBulbLabel: 'Joto la Mvua (Tw)',
    comfortModelDefault: 'Mfumo chaguo-msingi wa starehe',
    comfortModelNone: 'Bila bendi ya starehe',
    extDataWarningPre: 'Data ya joto la nje ya Open-Meteo inafika hadi',
    extDataWarningPost: '. Sasisha CSV ya <code>open-meteo</code> kuona faraja ya kubadilika kwa tarehe za hivi karibuni.',
    longTermNotePre: 'Data ya kihistoria ya muda mrefu na makadirio ya baadaye yamezalishwa kutoka',
    longTermNotePost: 'taarifa 2026.',
    filterBy: 'Chuja kwa',
    optNone: 'Hakuna',
    dayOfMonth: 'Siku ya Mwezi',
    rangeToggle: 'kipindi',
    singleToggle: 'moja',
    lateNight: 'Usiku wa Manane',
    morning: 'Asubuhi',
    afternoon: 'Mchana',
    evening: 'Jioni',
    noLoggers: 'Hakuna vihisi',
    noFilter: 'Hakuna chujio',
    goodData: 'Data nzuri',
    gapLegend: 'Pengo (>6h)',
    adminFlagged: 'Iliyobainishwa na msimamizi',
    noDifference: 'hakuna tofauti',
    phase18: 'Awamu (1–8)',
    phasePNN: 'Awamu (+/−/Neutral)',
    phaseENSO: 'Awamu (Niño/Niña/Neutral)',
  }
};
function t(key) { return (I18N[currentLang] || I18N.en)[key] || I18N.en[key] || key; }
function ln(id) {
  const m = dataset().meta;
  if (currentLang === 'sw' && m.loggerNamesSw && m.loggerNamesSw[id]) return m.loggerNamesSw[id];
  return m.loggerNames[id] || id;
}
// Logger name from a specific dataset's meta (for cross-building compare)
function lnFrom(meta, id) {
  if (currentLang === 'sw' && meta.loggerNamesSw && meta.loggerNamesSw[id]) return meta.loggerNamesSw[id];
  return (meta.loggerNames && meta.loggerNames[id]) || id;
}

function setLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('arcLang', lang);
  // Update menu active state and close
  const menu = document.getElementById('lang-menu');
  if (menu) {
    menu.classList.remove('open');
    menu.querySelectorAll('button').forEach(b => b.classList.toggle('active', b.textContent === (lang === 'sw' ? 'Kiswahili' : 'English')));
  }
  document.documentElement.lang = lang === 'sw' ? 'sw' : 'en';
  applyLanguage();
}

function applyLanguage() {
  // All elements with data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  // Translate beta chart type dropdown
  document.querySelectorAll('#beta-chart-type [data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });

  // Checkbox labels: text node after checkbox input
  const cbMap = {
    'cb-temperature': 'temperature', 'cb-humidity': 'humidity',
    'cb-threshold': 'threshold', 'cb-seasons': 'seasonLines',
    'cb-exclude-anomalous': 'excludeAnomalous',
  };
  for (const [id, key] of Object.entries(cbMap)) {
    const cb = document.getElementById(id);
    if (!cb) continue;
    const lbl = cb.closest('label');
    if (!lbl) continue;
    let found = false;
    for (const node of lbl.childNodes) {
      if (node === cb) { found = true; continue; }
      if (found && node.nodeType === 3 && node.textContent.trim()) {
        node.textContent = ' ' + t(key); break;
      }
    }
  }

  // Checkbox labels with <b> wrapper
  const boldCbMap = { 'cb-historic-mode': 'longTermMode', 'cb-compare': 'compareMode' };
  for (const [id, key] of Object.entries(boldCbMap)) {
    const cb = document.getElementById(id);
    if (!cb) continue;
    const bold = cb.parentElement.querySelector('b');
    if (bold) bold.textContent = t(key);
  }

  // Density heatmap checkbox (text before info icon)
  const densityCb = document.getElementById('cb-density');
  if (densityCb) {
    const lbl = densityCb.closest('label');
    if (lbl) {
      let found = false;
      for (const node of lbl.childNodes) {
        if (node === densityCb) { found = true; continue; }
        if (found && node.nodeType === 3 && node.textContent.trim()) {
          node.textContent = ' ' + t('densityHeatmap') + ' '; break;
        }
      }
    }
  }

  // Labels wrapping a select element
  function setSelectLabel(selId, text) {
    const sel = document.getElementById(selId);
    if (!sel) return;
    const lbl = sel.closest('label');
    if (!lbl) return;
    for (const node of lbl.childNodes) {
      if (node.nodeType === 3 && node.textContent.trim()) {
        node.textContent = '\n          ' + text + '\n          '; break;
      }
    }
  }
  setSelectLabel('period-group-by', t('groupBy'));
  setSelectLabel('natural-cycles', t('cycle'));
  setSelectLabel('histogram-barmode', t('barMode'));
  setSelectLabel('compare-set-count', t('numSets'));

  // From/To input labels
  ['date-start', 'date-end'].forEach((id, i) => {
    const inp = document.getElementById(id);
    if (!inp) return;
    const lbl = inp.closest('label');
    if (!lbl) return;
    for (const node of lbl.childNodes) {
      if (node.nodeType === 3 && node.textContent.trim()) {
        node.textContent = t(i === 0 ? 'from' : 'to'); break;
      }
    }
  });

  // Range: label
  const tmSel = document.getElementById('time-mode');
  if (tmSel) {
    const row = tmSel.closest('.control-row');
    if (row) {
      const lbl = row.querySelector('label');
      if (lbl && !lbl.querySelector('input')) lbl.textContent = t('range');
    }
  }

  // Div labels before select elements
  function setDivLabel(selId, text) {
    const sel = document.getElementById(selId);
    if (!sel) return;
    const prev = sel.previousElementSibling;
    if (prev && prev.tagName === 'DIV') prev.textContent = text;
  }
  setDivLabel('comfort-model', t('comfortBand'));
  setDivLabel('comfort-pct-mode', t('pctCalc'));

  // Section titles with adjacent buttons
  function setTitleWithBtn(btnId, titleKey, btnKey) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.textContent = t(btnKey);
    const parent = btn.parentElement;
    for (const node of parent.childNodes) {
      if (node.nodeType === 3 && node.textContent.trim()) {
        node.textContent = t(titleKey); break;
      }
    }
  }
  setTitleWithBtn('reset-line-btn', 'loggers', 'resetDefault');
  setTitleWithBtn('reset-comfort-btn', 'roomLoggers', 'resetDefault');

  // Advanced Settings toggle text
  const advToggle = document.getElementById('advanced-settings-toggle');
  if (advToggle) {
    for (const node of advToggle.childNodes) {
      if (node.nodeType === 3 && node.textContent.trim()) {
        node.textContent = ' ' + t('advancedSettings'); break;
      }
    }
  }

  // Match ALL/ANY radio labels
  document.querySelectorAll('input[name="substrat-combine"]').forEach(radio => {
    const lbl = radio.closest('label');
    if (!lbl) return;
    for (const node of lbl.childNodes) {
      if (node.nodeType === 3 && node.textContent.trim()) {
        node.textContent = ' ' + t(radio.value === 'all' ? 'matchAll' : 'matchAny'); break;
      }
    }
  });

  // Lock buttons
  document.querySelectorAll('.lock-btn').forEach(btn => {
    const locked = btn.classList.contains('locked');
    btn.textContent = t(locked ? 'unlockAvg' : 'lockAvg');
  });

  // Update logger names in sidebar checkboxes
  document.querySelectorAll('.logger-name[data-lid]').forEach(span => {
    span.textContent = ln(span.dataset.lid);
  });
  // Update wet bulb suffix text on sub-labels
  document.querySelectorAll('.wb-suffix').forEach(span => { span.textContent = ' ' + t('wetBulbSuffix'); });

  // ext-data-warning: post part contains HTML (<code>), set via innerHTML on the post span
  const extPost = document.getElementById('ext-data-warning-post');
  if (extPost) extPost.innerHTML = t('extDataWarningPost');
  const extPre = document.getElementById('ext-data-warning-pre');
  if (extPre) extPre.textContent = t('extDataWarningPre');

  // Re-render Average Profiles group-by dropdown so its option labels follow the language
  if (typeof window.updateGroupByDropdown === 'function') {
    try { window.updateGroupByDropdown(); } catch(e) {}
  }

  // Re-render any open substrat filter blocks so their labels follow the language
  document.querySelectorAll('.substrat-filter .substrat-row > label').forEach(lbl => {
    const txt = (lbl.textContent || '').trim();
    if (txt === 'Filter by' || txt === 'Chuja kwa') lbl.textContent = t('filterBy');
    else if (txt === 'Group By' || txt === 'Panga kwa') lbl.textContent = t('groupBy');
    else if (txt === 'From' || txt === 'Kutoka') lbl.textContent = t('from').trim();
    else if (txt === 'To' || txt === 'Hadi') lbl.textContent = t('to').trim();
  });
  document.querySelectorAll('.substrat-range-toggle').forEach(el => {
    const txt = (el.textContent || '').trim();
    if (txt === 'range' || txt === 'kipindi') el.textContent = t('rangeToggle');
    else if (txt === 'single' || txt === 'moja') el.textContent = t('singleToggle');
  });

  // Re-render chart with translated labels
  if (typeof updatePlot === 'function') {
    try { updatePlot(); } catch(e) {}
  }
}

function dataset() { return ALL_DATA[state.datasetKey]; }

// ── Substratification (Advanced Filtering) ────────────────────────────────────
let _substratIdCounter = 0;

const TZ_SEASON_IDX_GLOBAL = [0,0,1,1,1,2,2,2,2,2,3,3];

function toggleAdvancedSettings() {
  const body = document.getElementById('advanced-settings-body');
  const arrow = document.getElementById('advanced-settings-arrow');
  const wasOpen = body.dataset.open === '1';
  const isOpen = !wasOpen;
  body.dataset.open = isOpen ? '1' : '0';
  body.style.display = isOpen ? 'block' : 'none';
  arrow.classList.toggle('open', isOpen);
  if (!isOpen) {
    // Collapse = clear all filters and disable compare, but only replot if something changed
    const hadFilters = state.substratFilters.length > 0;
    const hadCompare = state.compareEnabled;
    state.substratFilters = [];
    document.getElementById('substrat-filters').innerHTML = '';
    state.compareEnabled = false;
    document.getElementById('cb-compare').checked = false;
    document.getElementById('compare-body').style.display = 'none';
    document.getElementById('logger-checkboxes').parentElement.classList.remove('compare-hide-main');
    document.getElementById('room-logger-checkboxes').parentElement.classList.remove('compare-hide-main');
    if (hadFilters || hadCompare) updatePlot();
  }
}

function addSubstratFilter() {
  const f = { id: ++_substratIdCounter, cycle: 'none', groupBy: null, from: null, to: null, phases: new Set() };
  state.substratFilters.push(f);
  renderSubstratFilterBlock(f);
}

function removeSubstratFilter(id) {
  state.substratFilters = state.substratFilters.filter(f => f.id !== id);
  const el = document.getElementById('substrat-f-' + id);
  if (el) el.remove();
  updatePlot();
}

function renderSubstratFilterBlock(f) {
  const container = document.getElementById('substrat-filters');
  const block = document.createElement('div');
  block.className = 'substrat-filter';
  block.id = 'substrat-f-' + f.id;

  const removeBtn = '<button class="substrat-remove" onclick="removeSubstratFilter(' + f.id + ')">&times;</button>';

  // Tier 1: cycle selector
  block.innerHTML = removeBtn +
    '<div class="substrat-row"><label>' + t('filterBy') + '</label>' +
    '<select class="substrat-cycle" onchange="substratCycleChanged(' + f.id + ', this.value)">' +
    '<option value="none">' + t('optNone') + '</option>' +
    '<option value="day">' + t('day') + '</option>' +
    '<option value="year">' + t('year') + '</option>' +
    '<option value="mjo">MJO</option>' +
    '<option value="iod">IOD</option>' +
    '<option value="enso">ENSO</option>' +
    '</select></div>' +
    '<div class="substrat-tier2"></div>' +
    '<div class="substrat-tier3"></div>';

  container.appendChild(block);
}

function substratCycleChanged(id, cycle) {
  const f = state.substratFilters.find(x => x.id === id);
  if (!f) return;
  f.cycle = cycle;
  f.groupBy = null;
  f.from = null;
  f.to = null;
  f.phases = new Set();

  const block = document.getElementById('substrat-f-' + id);
  block.classList.remove('invalid');
  const tier2 = block.querySelector('.substrat-tier2');
  const tier3 = block.querySelector('.substrat-tier3');
  tier2.innerHTML = '';
  tier3.innerHTML = '';

  if (cycle === 'none') { updatePlot(); return; }

  if (cycle === 'day' || cycle === 'year') {
    // Tier 2: group-by dropdown
    let opts = '';
    if (cycle === 'day') {
      opts = '<option value="hour">' + t('hour') + '</option><option value="synoptic">' + t('synopticHours') + '</option>';
    } else {
      opts = '<option value="day">' + t('dayOfMonth') + '</option><option value="week">' + t('week') + '</option><option value="month">' + t('month') + '</option><option value="season">' + t('season') + '</option>';
    }
    tier2.innerHTML = '<div class="substrat-row"><label>' + t('groupBy') + '</label>' +
      '<select class="substrat-group-by" onchange="substratGroupByChanged(' + id + ', this.value)">' + opts + '</select></div>';
    // Auto-select first option
    const firstVal = tier2.querySelector('select').value;
    substratGroupByChanged(id, firstVal);
  } else {
    // Oscillation: show phase checkboxes directly
    let labels, nPhases;
    if (cycle === 'mjo') { labels = MJO_LABELS; nPhases = 8; }
    else if (cycle === 'iod') { labels = IOD_LABELS; nPhases = 3; }
    else { labels = ENSO_LABELS; nPhases = 3; }

    let html = '<div class="substrat-phases">';
    for (let i = 0; i < nPhases; i++) {
      html += '<label><input type="checkbox" data-phase="' + i + '" onchange="substratPhaseChanged(' + id + ')"> ' + labels[i] + '</label>';
    }
    html += '</div>';
    tier3.innerHTML = html;
    f.groupBy = 'phase';
    updatePlot();
  }
}

function substratGroupByChanged(id, gran) {
  const f = state.substratFilters.find(x => x.id === id);
  if (!f) return;
  f.groupBy = gran;
  f.from = null;
  f.to = null;
  f._rangeMode = false;

  const block = document.getElementById('substrat-f-' + id);
  block.classList.remove('invalid');
  const tier3 = block.querySelector('.substrat-tier3');

  const opts = substratBuildOptions(f.cycle, gran);
  f.from = opts.defaultVal;
  f.to = opts.defaultVal; // single selection: from === to

  tier3.innerHTML = '<div class="substrat-row">' +
    '<select class="substrat-single" onchange="substratSingleChanged(' + id + ')">' + opts.html + '</select>' +
    '<span class="substrat-range-toggle" onclick="substratToggleRange(' + id + ')">' + t('rangeToggle') + '</span>' +
    '</div>' +
    '<div class="substrat-range-row substrat-row" style="display:none">' +
    '<label>' + t('from').trim() + '</label><select class="substrat-from" onchange="substratRangeChanged(' + id + ')">' + opts.html + '</select>' +
    '<label>' + t('to').trim() + '</label><select class="substrat-to" onchange="substratRangeChanged(' + id + ')">' + opts.html + '</select>' +
    '</div>';
  tier3.querySelector('.substrat-to').value = String(opts.lastVal);
  updatePlot();
}

function substratBuildOptions(cycle, gran) {
  let html = '', defaultVal = 0, lastVal = 0;
  if (cycle === 'day' && gran === 'hour') {
    for (let h = 0; h < 24; h++) {
      const lbl = String(h).padStart(2, '0') + ':00';
      html += '<option value="' + h + '">' + lbl + '</option>';
    }
    defaultVal = 0; lastVal = 23;
  } else if (cycle === 'day' && gran === 'synoptic') {
    const synLabels = [t('lateNight') + ' (00\u201306)', t('morning') + ' (06\u201312)', t('afternoon') + ' (12\u201318)', t('evening') + ' (18\u201300)'];
    for (let s = 0; s < 4; s++) html += '<option value="' + s + '">' + synLabels[s] + '</option>';
    defaultVal = 0; lastVal = 3;
  } else if (cycle === 'year' && gran === 'month') {
    const mns = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    for (let m = 0; m < 12; m++) html += '<option value="' + m + '">' + mns[m] + '</option>';
    defaultVal = 0; lastVal = 11;
  } else if (cycle === 'year' && gran === 'week') {
    for (let w = 1; w <= 53; w++) html += '<option value="' + w + '">W' + w + '</option>';
    defaultVal = 1; lastVal = 53;
  } else if (cycle === 'year' && gran === 'day') {
    for (let d = 1; d <= 31; d++) html += '<option value="' + d + '">' + d + '</option>';
    defaultVal = 1; lastVal = 31;
  } else if (cycle === 'year' && gran === 'season') {
    const sLabels = ['Kiangazi (Jan\u2013Feb)', 'Masika (Mar\u2013May)', 'Kiangazi (Jun\u2013Oct)', 'Vuli (Nov\u2013Dec)'];
    for (let s = 0; s < 4; s++) html += '<option value="' + s + '">' + sLabels[s] + '</option>';
    defaultVal = 0; lastVal = 3;
  }
  return { html, defaultVal, lastVal };
}

function substratSingleChanged(id) {
  const f = state.substratFilters.find(x => x.id === id);
  if (!f) return;
  const block = document.getElementById('substrat-f-' + id);
  const val = parseInt(block.querySelector('.substrat-single').value);
  f.from = val;
  f.to = val;
  block.classList.remove('invalid');
  updatePlot();
}

function substratToggleRange(id) {
  const f = state.substratFilters.find(x => x.id === id);
  if (!f) return;
  f._rangeMode = !f._rangeMode;
  const block = document.getElementById('substrat-f-' + id);
  const tier3 = block.querySelector('.substrat-tier3');
  const singleRow = tier3.querySelector('.substrat-row:first-child');
  const rangeRow = tier3.querySelector('.substrat-range-row');
  const toggle = block.querySelector('.substrat-range-toggle');

  if (f._rangeMode) {
    singleRow.style.display = 'none';
    rangeRow.style.display = '';
    toggle.textContent = t('singleToggle');
    // Sync from/to dropdowns from current state
    block.querySelector('.substrat-from').value = String(f.from);
    block.querySelector('.substrat-to').value = String(f.to);
    // Move toggle into range row
    rangeRow.appendChild(toggle);
  } else {
    singleRow.style.display = '';
    rangeRow.style.display = 'none';
    toggle.textContent = t('rangeToggle');
    // Snap to single: use 'from' value
    f.to = f.from;
    block.querySelector('.substrat-single').value = String(f.from);
    block.classList.remove('invalid');
    // Move toggle back into single row
    singleRow.appendChild(toggle);
    updatePlot();
  }
}

function substratRangeChanged(id) {
  const f = state.substratFilters.find(x => x.id === id);
  if (!f) return;
  const block = document.getElementById('substrat-f-' + id);
  f.from = parseInt(block.querySelector('.substrat-from').value);
  f.to = parseInt(block.querySelector('.substrat-to').value);

  // Validate: Day of Month and Week are NOT cyclic — invalid if from > to
  const nonCyclic = (f.cycle === 'year' && (f.groupBy === 'day' || f.groupBy === 'week'));
  if (nonCyclic && f.from > f.to) {
    block.classList.add('invalid');
  } else {
    block.classList.remove('invalid');
  }
  updatePlot();
}

function substratPhaseChanged(id) {
  const f = state.substratFilters.find(x => x.id === id);
  if (!f) return;
  const block = document.getElementById('substrat-f-' + id);
  f.phases = new Set();
  block.querySelectorAll('.substrat-phases input[type=checkbox]:checked').forEach(cb => {
    f.phases.add(parseInt(cb.dataset.phase));
  });
  updatePlot();
}

// ── Substratification: filter test ────────────────────────────────────────────

function isSubstratFilterActive(f) {
  if (f.cycle === 'none') return false;
  if (f.cycle === 'mjo' || f.cycle === 'iod' || f.cycle === 'enso') {
    return f.phases.size > 0;
  }
  if (f.from == null || f.to == null) return false;
  // Non-cyclic ranges invalid when from > to
  const nonCyclic = (f.cycle === 'year' && (f.groupBy === 'day' || f.groupBy === 'week'));
  if (nonCyclic && f.from > f.to) return false;
  return true;
}

function inCyclicRange(val, from, to, max) {
  if (from <= to) return val >= from && val <= to;
  return val >= from || val <= to; // wraps around
}

function passesFilter(ms, f) {
  const d = eatDate(ms);
  if (f.cycle === 'day') {
    const h = d.getUTCHours();
    if (f.groupBy === 'hour') return inCyclicRange(h, f.from, f.to, 24);
    if (f.groupBy === 'synoptic') {
      const syn = h < 6 ? 0 : h < 12 ? 1 : h < 18 ? 2 : 3;
      return inCyclicRange(syn, f.from, f.to, 4);
    }
  } else if (f.cycle === 'year') {
    if (f.groupBy === 'month') return inCyclicRange(d.getUTCMonth(), f.from, f.to, 12);
    if (f.groupBy === 'season') return inCyclicRange(TZ_SEASON_IDX_GLOBAL[d.getUTCMonth()], f.from, f.to, 4);
    if (f.groupBy === 'week') {
      const jan1 = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
      const wk = Math.min(53, Math.floor((d - jan1) / (7 * 86400000)) + 1);
      return wk >= f.from && wk <= f.to;
    }
    if (f.groupBy === 'day') {
      const dom = d.getUTCDate();
      return dom >= f.from && dom <= f.to;
    }
  } else if (f.cycle === 'mjo') {
    const wk = getISOWeekStr(ms);
    const ph = MJO_PHASES[wk];
    return ph != null && ph >= 0 && f.phases.has(ph);
  } else if (f.cycle === 'iod') {
    const key = d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0');
    const ph = IOD_PHASES[key];
    return ph != null && f.phases.has(ph);
  } else if (f.cycle === 'enso') {
    const key = d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0');
    const ph = ENSO_PHASES[key];
    return ph != null && f.phases.has(ph);
  }
  return true;
}

function getActiveSubstratFilters() {
  return state.substratFilters.filter(isSubstratFilterActive);
}

function passesAllSubstratFilters(ms) {
  const active = getActiveSubstratFilters();
  if (active.length === 0) return true;
  if (state.substratCombine === 'all') {
    for (const f of active) { if (!passesFilter(ms, f)) return false; }
    return true;
  } else {
    for (const f of active) { if (passesFilter(ms, f)) return true; }
    return false;
  }
}

// Apply substratification to a filtered series — returns new filtered object with non-matching points nulled
function applySubstratFilter(filtered) {
  const active = getActiveSubstratFilters();
  if (active.length === 0) return filtered;
  const n = filtered.timestamps.length;
  const ts = [], temp = [], hum = [];
  const extTemp = filtered.extTemp ? [] : null;
  for (let i = 0; i < n; i++) {
    if (passesAllSubstratFilters(filtered.timestamps[i])) {
      ts.push(filtered.timestamps[i]);
      temp.push(filtered.temperature[i]);
      hum.push(filtered.humidity[i]);
      if (extTemp) extTemp.push(filtered.extTemp[i]);
    }
  }
  if (ts.length === 0) return null;
  return { timestamps: ts, temperature: temp, humidity: hum, extTemp };
}

// ── Compare Mode ──────────────────────────────────────────────────────────────
function initCompareSets() {
  const m = dataset().meta;
  state.compareSets = [];
  for (let i = 0; i < 4; i++) {
    state.compareSets.push({
      selectedLoggers: new Set(m.lineLoggers || m.loggers),
      selectedRoomLoggers: new Set(m.roomLoggers || []),
      substratFilters: [],
      substratCombine: 'all',
    });
  }
}
let _compareSubstratIdCounter = 0;

function renderCompareSets() {
  const container = document.getElementById('compare-sets');
  container.innerHTML = '';
  const m = dataset().meta;
  const hues = COMPARE_HUES[state.compareSetCount];
  // Ensure enough sets exist
  while (state.compareSets.length < state.compareSetCount) {
    state.compareSets.push({
      selectedLoggers: new Set(m.lineLoggers || m.loggers),
      selectedRoomLoggers: new Set(m.roomLoggers || []),
      selectedCrossLoggers: {}, // {dsKey: Set<loggerId>} for other datasets
      substratFilters: [],
      substratCombine: 'all',
    });
  }
  // Ensure all sets have selectedCrossLoggers
  for (const cs of state.compareSets) {
    if (!cs.selectedCrossLoggers) cs.selectedCrossLoggers = {};
  }
  const anomRanges = m.anomalousRanges || {};
  const extSet = new Set(m.externalLoggers || []);
  const roomSet = new Set(m.roomLoggers || []);
  const lineSet = new Set(m.lineLoggers || m.loggers);
  const isComfort = state.chartType === 'comfort';
  // Determine which loggers to show based on chart type
  const loggerPool = isComfort ? (m.comfortLoggers || m.roomLoggers || []) : m.loggers;

  for (let si = 0; si < state.compareSetCount; si++) {
    const cs = state.compareSets[si];
    const baseColor = compareBaseColor(si, state.compareSetCount);
    const setDiv = document.createElement('div');
    setDiv.className = 'compare-set';
    setDiv.style.borderLeftColor = baseColor;

    const header = document.createElement('div');
    header.className = 'compare-set-header';
    header.style.color = baseColor;
    header.innerHTML = '<span class="compare-arrow">&#9654;</span> ' + COMPARE_SET_NAMES[si];

    const body = document.createElement('div');
    body.className = 'compare-set-body';
    body.style.display = 'none';
    header.addEventListener('click', () => {
      const open = body.style.display !== 'none';
      body.style.display = open ? 'none' : 'block';
      header.querySelector('.compare-arrow').classList.toggle('open', !open);
    });

    // Logger checkboxes in a scrollable wrapper
    const loggerWrap = document.createElement('div');
    loggerWrap.className = 'compare-loggers-wrap';
    const stateSet = isComfort ? cs.selectedRoomLoggers : cs.selectedLoggers;

    // Helper to make selection buttons
    function mkCmpBtn(label, onClick, i18nKey) {
      const b = document.createElement('button');
      b.className = 'sel-btn'; b.textContent = label;
      if (i18nKey) b.dataset.i18n = i18nKey;
      b.addEventListener('click', onClick); return b;
    }

    // Add sections (external, room, structural) with per-section buttons
    function addCmpSection(i18nKey, ids) {
      if (ids.length === 0) return;
      const titleEl = document.createElement('div');
      titleEl.className = 'sub-section-title';
      titleEl.textContent = t(i18nKey);
      titleEl.dataset.i18n = i18nKey;
      loggerWrap.appendChild(titleEl);
      // Per-section buttons: All / None / TinyTag / Omnisense
      const secBtnRow = document.createElement('div');
      secBtnRow.style.cssText = 'display:flex;gap:4px;margin-bottom:3px;flex-wrap:wrap;';
      secBtnRow.appendChild(mkCmpBtn(t('btnAll'), () => {
        ids.forEach(id => { stateSet.add(id); loggerWrap.querySelector('input[data-cmp-logger="' + id + '"]').checked = true; });
        updatePlot();
      }, 'btnAll'));
      secBtnRow.appendChild(mkCmpBtn(t('btnNone'), () => {
        ids.forEach(id => { stateSet.delete(id); loggerWrap.querySelector('input[data-cmp-logger="' + id + '"]').checked = false; });
        updatePlot();
      }, 'btnNone'));
      // TinyTag / Omnisense buttons only if both sources present in this section
      const hasTT = ids.some(id => m.loggerSources[id] === 'TinyTag');
      const hasOS = ids.some(id => m.loggerSources[id] === 'Omnisense');
      if (hasTT && hasOS) {
        secBtnRow.appendChild(mkCmpBtn('TinyTag', () => {
          ids.forEach(id => { const is = m.loggerSources[id] === 'TinyTag'; is ? stateSet.add(id) : stateSet.delete(id); loggerWrap.querySelector('input[data-cmp-logger="' + id + '"]').checked = is; });
          updatePlot();
        }));
        secBtnRow.appendChild(mkCmpBtn('Omnisense', () => {
          ids.forEach(id => { const is = m.loggerSources[id] === 'Omnisense'; is ? stateSet.add(id) : stateSet.delete(id); loggerWrap.querySelector('input[data-cmp-logger="' + id + '"]').checked = is; });
          updatePlot();
        }));
      }
      loggerWrap.appendChild(secBtnRow);
      for (const id of ids) {
        const lbl = document.createElement('label');
        lbl.className = 'cb-label';
        lbl.dataset.tooltip = loggerTooltip(id, m);
        const source = m.loggerSources[id] || '';
        const isExtTT = extSet.has(id) && source === 'TinyTag';
        const ttSuffix = isExtTT ? ' <span style="color:#aaa">(TinyTag)</span>' : '';
        lbl.innerHTML = '<input type="checkbox" data-cmp-logger="' + id + '" ' + (stateSet.has(id) ? 'checked' : '') + '> <span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' + m.colors[id] + ';vertical-align:middle"></span> <span class="logger-name" data-lid="' + id + '">' + ln(id) + '</span>' + meteoSuffix(id) + omniSuffix(source) + ttSuffix;
        lbl.querySelector('input').addEventListener('change', e => {
          e.target.checked ? stateSet.add(id) : stateSet.delete(id);
          updatePlot();
        });
        loggerWrap.appendChild(lbl);
      }
    }
    if (isComfort) {
      const comfortRoomIds = (m.comfortLoggers || m.roomLoggers || []).filter(id => (m.roomLoggers || []).includes(id));
      const comfortStructIds = (m.comfortLoggers || []).filter(id => (m.structuralLoggers || []).includes(id));
      addCmpSection('sectionRoom', comfortRoomIds);
      addCmpSection('sectionStructural', comfortStructIds);
    } else {
      if (m.externalLoggers && m.externalLoggers.length > 0) addCmpSection('sectionExternal', m.externalLoggers);
      const roomLoggers = m.loggers.filter(id => !extSet.has(id) && roomSet.has(id) && lineSet.has(id));
      const midLoggers = m.loggers.filter(id => !extSet.has(id) && !roomSet.has(id) && lineSet.has(id));
      addCmpSection('sectionRoom', roomLoggers);
      addCmpSection('sectionStructural', midLoggers);
    }

    // Cross-dataset loggers (other buildings)
    if (!isComfort) {
      for (const otherKey of Object.keys(ALL_DATA)) {
        if (otherKey === state.datasetKey) continue;
        const otherDs = ALL_DATA[otherKey];
        const otherM = otherDs.meta;
        const otherRoomSet = new Set(otherM.roomLoggers || []);
        const otherExtSet = new Set(otherM.externalLoggers || []);
        const otherRoomLoggers = otherM.loggers.filter(id => !otherExtSet.has(id) && otherRoomSet.has(id));
        if (otherRoomLoggers.length === 0) continue;
        // Initialize cross-logger set for this other dataset
        if (!cs.selectedCrossLoggers[otherKey]) cs.selectedCrossLoggers[otherKey] = new Set();
        const crossSet = cs.selectedCrossLoggers[otherKey];
        // Divider
        const hr = document.createElement('hr'); hr.className = 'divider'; loggerWrap.appendChild(hr);
        const otherName = otherKey === 'house5' ? t('house5') : otherKey === 'schoolteacher' ? t('schoolteacher') : otherKey;
        const titleEl = document.createElement('div');
        titleEl.className = 'sub-section-title';
        titleEl.textContent = otherName;
        loggerWrap.appendChild(titleEl);
        // All/None buttons
        const secBtnRow = document.createElement('div');
        secBtnRow.style.cssText = 'display:flex;gap:4px;margin-bottom:3px;flex-wrap:wrap;';
        secBtnRow.appendChild(mkCmpBtn(t('btnAll'), () => {
          otherRoomLoggers.forEach(id => { crossSet.add(id); loggerWrap.querySelector('input[data-cross-logger="' + otherKey + ':' + id + '"]').checked = true; });
          updatePlot();
        }, 'btnAll'));
        secBtnRow.appendChild(mkCmpBtn(t('btnNone'), () => {
          otherRoomLoggers.forEach(id => { crossSet.delete(id); loggerWrap.querySelector('input[data-cross-logger="' + otherKey + ':' + id + '"]').checked = false; });
          updatePlot();
        }, 'btnNone'));
        loggerWrap.appendChild(secBtnRow);
        for (const id of otherRoomLoggers) {
          const lbl = document.createElement('label');
          lbl.className = 'cb-label';
          const src = otherM.loggerSources[id] || '';
          const color = otherM.colors[id] || '#999';
          const dispName = lnFrom(otherM, id);
          lbl.innerHTML = '<input type="checkbox" data-cross-logger="' + otherKey + ':' + id + '" ' + (crossSet.has(id) ? 'checked' : '') + '> <span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:' + color + ';vertical-align:middle"></span> <span class="logger-name">' + dispName + '</span>' + (src ? ' <span style="color:#aaa;font-size:10px">(' + src + ')</span>' : '');
          lbl.querySelector('input').addEventListener('change', e => {
            e.target.checked ? crossSet.add(id) : crossSet.delete(id);
            updatePlot();
          });
          loggerWrap.appendChild(lbl);
        }
      }
    }
    body.appendChild(loggerWrap);

    // Match ALL/ANY + filters
    const showFilters = state.chartType !== 'line';
    if (showFilters) {
      const combineWrap = document.createElement('div');
      combineWrap.className = 'substrat-combine';
      combineWrap.style.marginTop = '4px';
      combineWrap.innerHTML =
        '<label><input type="radio" name="cmp-combine-' + si + '" value="all" ' + (cs.substratCombine === 'all' ? 'checked' : '') + '> Match ALL</label>' +
        '<label><input type="radio" name="cmp-combine-' + si + '" value="any" ' + (cs.substratCombine === 'any' ? 'checked' : '') + '> Match ANY</label>';
      combineWrap.querySelectorAll('input').forEach(r => {
        r.addEventListener('change', () => { cs.substratCombine = r.value; updatePlot(); });
      });
      body.appendChild(combineWrap);

      const filterWrap = document.createElement('div');
      filterWrap.id = 'cmp-substrat-filters-' + si;
      body.appendChild(filterWrap);

      // Render existing filters
      for (const f of cs.substratFilters) {
        renderCompareSubstratBlock(si, f, filterWrap);
      }

      const addBtn = document.createElement('button');
      addBtn.className = 'compare-add-filter-btn';
      addBtn.textContent = t('addFilter'); addBtn.dataset.i18n = 'addFilter';
      addBtn.addEventListener('click', () => addCompareSubstratFilter(si));
      body.appendChild(addBtn);
    }

    setDiv.appendChild(header);
    setDiv.appendChild(body);
    container.appendChild(setDiv);
  }
}

function addCompareSubstratFilter(si) {
  const cs = state.compareSets[si];
  const f = { id: ++_compareSubstratIdCounter, cycle: 'none', groupBy: null, from: null, to: null, phases: new Set() };
  cs.substratFilters.push(f);
  const filterWrap = document.getElementById('cmp-substrat-filters-' + si);
  renderCompareSubstratBlock(si, f, filterWrap);
}

function removeCompareSubstratFilter(si, fid) {
  const cs = state.compareSets[si];
  cs.substratFilters = cs.substratFilters.filter(f => f.id !== fid);
  const el = document.getElementById('cmp-substrat-f-' + fid);
  if (el) el.remove();
  updatePlot();
}

function renderCompareSubstratBlock(si, f, container) {
  const block = document.createElement('div');
  block.className = 'substrat-filter';
  block.id = 'cmp-substrat-f-' + f.id;

  const removeBtn = document.createElement('button');
  removeBtn.className = 'substrat-remove';
  removeBtn.innerHTML = '&times;';
  removeBtn.addEventListener('click', () => removeCompareSubstratFilter(si, f.id));
  block.appendChild(removeBtn);

  const row = document.createElement('div');
  row.className = 'substrat-row';
  row.innerHTML = '<label>' + t('filterBy') + '</label>' +
    '<select class="substrat-cycle">' +
    '<option value="none">' + t('optNone') + '</option>' +
    '<option value="day">' + t('day') + '</option>' +
    '<option value="year">' + t('year') + '</option>' +
    '<option value="mjo">MJO</option>' +
    '<option value="iod">IOD</option>' +
    '<option value="enso">ENSO</option>' +
    '</select>';
  row.querySelector('select').value = f.cycle;
  row.querySelector('select').addEventListener('change', function() {
    cmpSubstratCycleChanged(si, f.id, this.value);
  });
  block.appendChild(row);

  const tier2 = document.createElement('div');
  tier2.className = 'substrat-tier2';
  block.appendChild(tier2);
  const tier3 = document.createElement('div');
  tier3.className = 'substrat-tier3';
  block.appendChild(tier3);

  container.appendChild(block);
}

function cmpSubstratCycleChanged(si, fid, cycle) {
  const cs = state.compareSets[si];
  const f = cs.substratFilters.find(x => x.id === fid);
  if (!f) return;
  f.cycle = cycle;
  f.groupBy = null;
  f.from = null;
  f.to = null;
  f.phases = new Set();

  const block = document.getElementById('cmp-substrat-f-' + fid);
  block.classList.remove('invalid');
  const tier2 = block.querySelector('.substrat-tier2');
  const tier3 = block.querySelector('.substrat-tier3');
  tier2.innerHTML = '';
  tier3.innerHTML = '';

  if (cycle === 'none') { updatePlot(); return; }

  if (cycle === 'day' || cycle === 'year') {
    let opts = '';
    if (cycle === 'day') {
      opts = '<option value="hour">' + t('hour') + '</option><option value="synoptic">' + t('synopticHours') + '</option>';
    } else {
      opts = '<option value="day">' + t('dayOfMonth') + '</option><option value="week">' + t('week') + '</option><option value="month">' + t('month') + '</option><option value="season">' + t('season') + '</option>';
    }
    tier2.innerHTML = '<div class="substrat-row"><label>' + t('groupBy') + '</label>' +
      '<select class="substrat-group-by">' + opts + '</select></div>';
    const sel = tier2.querySelector('select');
    sel.addEventListener('change', function() {
      cmpSubstratGroupByChanged(si, fid, this.value);
    });
    cmpSubstratGroupByChanged(si, fid, sel.value);
  } else {
    let labels, nPhases;
    if (cycle === 'mjo') { labels = MJO_LABELS; nPhases = 8; }
    else if (cycle === 'iod') { labels = IOD_LABELS; nPhases = 3; }
    else { labels = ENSO_LABELS; nPhases = 3; }

    let html = '<div class="substrat-phases">';
    for (let i = 0; i < nPhases; i++) {
      html += '<label><input type="checkbox" data-phase="' + i + '"> ' + labels[i] + '</label>';
    }
    html += '</div>';
    tier3.innerHTML = html;
    tier3.querySelectorAll('input[data-phase]').forEach(cb => {
      cb.addEventListener('change', () => {
        f.phases.clear();
        tier3.querySelectorAll('input[data-phase]:checked').forEach(c => f.phases.add(parseInt(c.dataset.phase)));
        updatePlot();
      });
    });
    f.groupBy = 'phase';
    updatePlot();
  }
}

function cmpSubstratGroupByChanged(si, fid, gran) {
  const cs = state.compareSets[si];
  const f = cs.substratFilters.find(x => x.id === fid);
  if (!f) return;
  f.groupBy = gran;
  f.from = null;
  f.to = null;
  f._rangeMode = false;

  const block = document.getElementById('cmp-substrat-f-' + fid);
  block.classList.remove('invalid');
  const tier3 = block.querySelector('.substrat-tier3');

  const opts = substratBuildOptions(f.cycle, gran);
  f.from = opts.defaultVal;
  f.to = opts.defaultVal;

  tier3.innerHTML = '<div class="substrat-row">' +
    '<select class="substrat-single">' + opts.html + '</select>' +
    '<span class="substrat-range-toggle">' + t('rangeToggle') + '</span>' +
    '</div>' +
    '<div class="substrat-range-row substrat-row" style="display:none">' +
    '<label>' + t('from').trim() + '</label><select class="substrat-from">' + opts.html + '</select>' +
    '<label>' + t('to').trim() + '</label><select class="substrat-to">' + opts.html + '</select>' +
    '</div>';
  tier3.querySelector('.substrat-to').value = String(opts.lastVal);

  // Wire up events
  tier3.querySelector('.substrat-single').addEventListener('change', function() {
    f.from = parseInt(this.value);
    f.to = f.from;
    block.classList.remove('invalid');
    updatePlot();
  });
  tier3.querySelector('.substrat-range-toggle').addEventListener('click', function() {
    f._rangeMode = !f._rangeMode;
    const singleRow = tier3.querySelector('.substrat-row:first-child');
    const rangeRow = tier3.querySelector('.substrat-range-row');
    if (f._rangeMode) {
      singleRow.style.display = 'none';
      rangeRow.style.display = '';
      this.textContent = t('singleToggle');
      tier3.querySelector('.substrat-from').value = String(f.from);
      tier3.querySelector('.substrat-to').value = String(f.to);
      rangeRow.appendChild(this);
    } else {
      singleRow.style.display = '';
      rangeRow.style.display = 'none';
      this.textContent = t('rangeToggle');
      f.to = f.from;
      tier3.querySelector('.substrat-single').value = String(f.from);
      block.classList.remove('invalid');
      singleRow.appendChild(this);
      updatePlot();
    }
  });
  tier3.querySelector('.substrat-from').addEventListener('change', function() {
    f.from = parseInt(this.value);
    const nonCyclic = (f.cycle === 'year' && (f.groupBy === 'day' || f.groupBy === 'week'));
    if (nonCyclic && f.from > f.to) block.classList.add('invalid');
    else block.classList.remove('invalid');
    updatePlot();
  });
  tier3.querySelector('.substrat-to').addEventListener('change', function() {
    f.to = parseInt(this.value);
    const nonCyclic = (f.cycle === 'year' && (f.groupBy === 'day' || f.groupBy === 'week'));
    if (nonCyclic && f.from > f.to) block.classList.add('invalid');
    else block.classList.remove('invalid');
    updatePlot();
  });

  updatePlot();
}

// Describe what distinguishes each compare set from the others
function describeCompareDiffs() {
  const m = dataset().meta;
  const isComfort = state.chartType === 'comfort';
  const n = state.compareSetCount;
  const sets = state.compareSets.slice(0, n);

  // Gather per-set info
  const infos = sets.map(cs => {
    const loggerSet = isComfort ? cs.selectedRoomLoggers : cs.selectedLoggers;
    const loggerIds = [...loggerSet].sort();
    const filters = (cs.substratFilters || []).filter(f => f.cycle !== 'none');
    return { loggerIds, filters, combine: cs.substratCombine };
  });

  // Check which aspects differ between sets
  const allSameLoggers = infos.every(info => {
    if (info.loggerIds.length !== infos[0].loggerIds.length) return false;
    return info.loggerIds.every((id, i) => id === infos[0].loggerIds[i]);
  });
  const allSameFilters = infos.every(info => describeFilters(info.filters) === describeFilters(infos[0].filters));

  const descriptions = [];
  for (let si = 0; si < n; si++) {
    const parts = [];
    // Logger differences
    if (!allSameLoggers) {
      const ids = infos[si].loggerIds;
      if (ids.length === 0) {
        parts.push(t('noLoggers'));
      } else {
        // Summarise by source type if possible
        const ttCount = ids.filter(id => m.loggerSources[id] === 'TinyTag').length;
        const osCount = ids.filter(id => m.loggerSources[id] === 'Omnisense').length;
        const otherCount = ids.length - ttCount - osCount;
        const srcParts = [];
        if (ttCount > 0) srcParts.push(ttCount + ' TinyTag');
        if (osCount > 0) srcParts.push(osCount + ' Omnisense');
        if (otherCount > 0) srcParts.push(otherCount + ' other');
        // If few loggers, list names; otherwise summarise by count
        if (ids.length <= 3) {
          parts.push(ids.map(id => ln(id)).join(', '));
        } else {
          parts.push(srcParts.join(' + '));
        }
      }
    }
    // Filter differences
    if (!allSameFilters) {
      const desc = describeFilters(infos[si].filters);
      if (desc) parts.push(desc);
      else parts.push(t('noFilter'));
    }
    descriptions.push(parts.length > 0 ? parts.join(' · ') : '');
  }
  return descriptions;
}

function describeFilters(filters) {
  if (!filters || filters.length === 0) return '';
  const synLabels = [t('lateNight') + ' (00\u201306)', t('morning') + ' (06\u201312)', t('afternoon') + ' (12\u201318)', t('evening') + ' (18\u201300)'];
  const monthLabels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const seasonLabels = ['Kiangazi (Jan\u2013Feb)', 'Masika (Mar\u2013May)', 'Kiangazi (Jun\u2013Oct)', 'Vuli (Nov\u2013Dec)'];
  const parts = [];
  for (const f of filters) {
    if (f.cycle === 'none') continue;
    if (f.cycle === 'day' && f.groupBy === 'hour') {
      const from = String(f.from).padStart(2, '0') + ':00';
      const to = String(f.to).padStart(2, '0') + ':00';
      parts.push(f.from === f.to ? from : from + '\u2013' + to);
    } else if (f.cycle === 'day' && f.groupBy === 'synoptic') {
      parts.push(f.from === f.to ? synLabels[f.from] : synLabels[f.from] + '\u2013' + synLabels[f.to]);
    } else if (f.cycle === 'year' && f.groupBy === 'month') {
      parts.push(f.from === f.to ? monthLabels[f.from] : monthLabels[f.from] + '\u2013' + monthLabels[f.to]);
    } else if (f.cycle === 'year' && f.groupBy === 'season') {
      parts.push(f.from === f.to ? seasonLabels[f.from] : seasonLabels[f.from] + ' to ' + seasonLabels[f.to]);
    } else if (f.cycle === 'year' && f.groupBy === 'week') {
      parts.push(f.from === f.to ? 'W' + f.from : 'W' + f.from + '\u2013W' + f.to);
    } else if (f.cycle === 'year' && f.groupBy === 'day') {
      parts.push(f.from === f.to ? 'Day ' + f.from : 'Day ' + f.from + '\u2013' + f.to);
    } else if (f.cycle === 'mjo') {
      const phases = [...(f.phases || [])].sort();
      parts.push('MJO ' + (phases.length > 0 ? phases.map(p => MJO_LABELS[p] || ('Ph' + p)).join(', ') : 'none'));
    } else if (f.cycle === 'iod') {
      const phases = [...(f.phases || [])].sort();
      parts.push('IOD ' + (phases.length > 0 ? phases.map(p => IOD_LABELS[p] || ('Ph' + p)).join(', ') : 'none'));
    } else if (f.cycle === 'enso') {
      const phases = [...(f.phases || [])].sort();
      parts.push('ENSO ' + (phases.length > 0 ? phases.map(p => ENSO_LABELS[p] || ('Ph' + p)).join(', ') : 'none'));
    }
  }
  return parts.join(', ');
}

function getCompareIterations() {
  if (!state.compareEnabled) {
    return [{
      selectedLoggers: state.chartType === 'comfort' ? state.selectedRoomLoggers : state.selectedLoggers,
      substratFilters: state.substratFilters,
      substratCombine: state.substratCombine,
      colorMap: dataset().meta.colors,
      setLabel: null,
      setIndex: -1,
    }];
  }
  const m = dataset().meta;
  const isComfort = state.chartType === 'comfort';
  const diffs = describeCompareDiffs();
  const iterations = [];
  for (let si = 0; si < state.compareSetCount; si++) {
    const cs = state.compareSets[si];
    const loggerList = [...(isComfort ? cs.selectedRoomLoggers : cs.selectedLoggers)];
    const shades = compareShades(si, state.compareSetCount, loggerList.length);
    const colorMap = {};
    loggerList.forEach((lid, i) => { colorMap[lid] = shades[i]; });
    const diffDesc = diffs[si] || '';
    const legendName = COMPARE_SET_NAMES[si] + (diffDesc ? ': ' + diffDesc : '');
    iterations.push({
      selectedLoggers: isComfort ? cs.selectedRoomLoggers : cs.selectedLoggers,
      selectedCrossLoggers: cs.selectedCrossLoggers || {},
      substratFilters: cs.substratFilters,
      substratCombine: cs.substratCombine,
      colorMap,
      setLabel: COMPARE_SET_NAMES[si],
      setIndex: si,
      legendName,
      baseColor: compareBaseColor(si, state.compareSetCount),
    });
  }
  return iterations;
}

function isOpenMeteo(id) { return id && id.indexOf('(Open-Meteo)') !== -1; }
function isForecast(id) { return id && id.indexOf('Forecast') !== -1 && isOpenMeteo(id); }

// Stull (2011) wet-bulb approximation — accurate to ±0.3°C for tropical conditions
// Valid range: T -20 to 50°C, RH 5 to 99%
function stullWetBulb(T, RH) {
  if (T < -20 || T > 50 || RH < 5) return null;
  if (RH > 99) RH = 99; // sensor saturation artefact — clamp to valid ceiling
  return T * Math.atan(0.151977 * Math.pow(RH + 8.313659, 0.5))
    + Math.atan(T + RH)
    - Math.atan(RH - 1.676331)
    + 0.00391838 * Math.pow(RH, 1.5) * Math.atan(0.023101 * RH)
    - 4.686035;
}

function loggerTooltip(id, m) {
  const src = (m.loggerSources && m.loggerSources[id]) || '';
  let tip = (id === 'govee' || isOpenMeteo(id)) ? src : (src ? `${src} · ${id}` : id);
  const series = dataset().series[id];
  return tip;
}

// ── User config (runtime overrides from data/config.json) ─────────────────────
async function loadUserConfig() {
  try {
    const resp = await fetch('data/config.json', {cache: 'no-cache'});
    if (!resp.ok) return null;
    return await resp.json();
  } catch (e) {
    return null;
  }
}

function applyUserConfig(config) {
  if (!config) return;
  for (const [dsKey, dsCfg] of Object.entries(config)) {
    const ds = ALL_DATA[dsKey];
    if (!ds) continue;
    const meta = ds.meta;
    const overrides = dsCfg.loggers || {};
    for (const [lid, ov] of Object.entries(overrides)) {
      if (!meta.loggers.includes(lid)) continue;
      if (ov.name) meta.loggerNames[lid] = ov.name;
      if (ov.section) {
        meta.roomLoggers = (meta.roomLoggers || []).filter(id => id !== lid);
        meta.structuralLoggers = (meta.structuralLoggers || []).filter(id => id !== lid);
        meta.externalLoggers = (meta.externalLoggers || []).filter(id => id !== lid);
        if (ov.section === 'room') meta.roomLoggers.push(lid);
        else if (ov.section === 'structural') meta.structuralLoggers.push(lid);
        else if (ov.section === 'external') meta.externalLoggers.push(lid);
      }
      if (typeof ov.showInComfort === 'boolean') {
        meta.comfortLoggers = (meta.comfortLoggers || []).filter(id => id !== lid);
        if (ov.showInComfort) meta.comfortLoggers.push(lid);
      }
      if (typeof ov.showInLine === 'boolean') {
        meta.lineLoggers = (meta.lineLoggers || [...meta.loggers]).filter(id => id !== lid);
        if (ov.showInLine) meta.lineLoggers.push(lid);
      }
      if (typeof ov.showInHistogram === 'boolean') {
        meta.histogramLoggers = (meta.histogramLoggers || [...meta.loggers]).filter(id => id !== lid);
        if (ov.showInHistogram) meta.histogramLoggers.push(lid);
      }
      if (typeof ov.showInPeriodic === 'boolean') {
        meta.periodicLoggers = (meta.periodicLoggers || [...meta.loggers]).filter(id => id !== lid);
        if (ov.showInPeriodic) meta.periodicLoggers.push(lid);
      }
    }
  }
}

// ── Initialise ────────────────────────────────────────────────────────────────
async function init() {
  // Load runtime user config (logger name/category overrides)
  const userConfig = await loadUserConfig();
  applyUserConfig(userConfig);

  // Populate data freshness notes with stale-data warnings
  const ftDiv = document.getElementById('fetch-time-notes');
  if (ftDiv && (FETCH_TIMES.openmeteo || FETCH_TIMES.omnisense || FETCH_TIMES.cycles)) {
    const DAY_MS = 86400000;
    const df = DATA_FRESHNESS;
    function staleCheck(fetchMs, lastMs, toleranceDays) {
      // Data should extend to at least (fetch_date - toleranceDays days)
      if (!fetchMs || !lastMs) return null;
      const expectedMs = fetchMs - toleranceDays * DAY_MS;
      if (lastMs < expectedMs) {
        const lastDate = toEATString(lastMs).split(',')[0].trim();
        return `Data only extends to ${lastDate} — expected up to day before last update`;
      }
      return null;
    }
    function cycleStaleCheck(fetchMs) {
      // Check cycle indices have data reasonably close to fetch date
      // MJO is weekly so should be within ~3 weeks of fetch; ENSO/IOD monthly so ~3 months
      if (!fetchMs) return null;
      const issues = [];
      if (df.mjo_last) {
        // Parse "2026-W10" → approximate epoch
        const [y, w] = df.mjo_last.replace('W','').split('-').map(Number);
        const mjoMs = new Date(y, 0, 1 + (w - 1) * 7).getTime();
        if (fetchMs - mjoMs > 21 * DAY_MS) issues.push(`MJO data ends at ${df.mjo_last}`);
      }
      if (df.enso_last) {
        const [y, m] = df.enso_last.split('-').map(Number);
        const ensoMs = new Date(y, m - 1, 15).getTime();
        if (fetchMs - ensoMs > 90 * DAY_MS) issues.push(`ENSO data ends at ${df.enso_last}`);
      }
      if (df.iod_last) {
        const [y, m] = df.iod_last.split('-').map(Number);
        const iodMs = new Date(y, m - 1, 15).getTime();
        if (fetchMs - iodMs > 90 * DAY_MS) issues.push(`IOD data ends at ${df.iod_last}`);
      }
      return issues.length ? issues.join('; ') : null;
    }
    function formatDataDate(ms) {
      if (!ms) return null;
      // Timestamps are UTC ms; display in EAT (UTC+3)
      const d = new Date(ms + 3 * 3600000);
      const day = d.getUTCDate();
      const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
      const suffix = (day === 1 || day === 21 || day === 31) ? 'st' : (day === 2 || day === 22) ? 'nd' : (day === 3 || day === 23) ? 'rd' : 'th';
      return `${day}${suffix} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
    }
    const lines = [];
    if (FETCH_TIMES.openmeteo) {
      const warn = staleCheck(df.openmeteo_fetch_ms, df.openmeteo_last_ms, 2);
      const warnHtml = warn ? ` <span class="stale-warn" title="${warn}">&#9888;</span>` : '';
      const dataDate = formatDataDate(df.openmeteo_last_ms);
      lines.push(`Open-Meteo last updated: ${dataDate || FETCH_TIMES.openmeteo}${warnHtml}`);
    }
    if (FETCH_TIMES.omnisense) {
      const warn = staleCheck(df.omnisense_fetch_ms, df.omnisense_last_ms, 2);
      const warnHtml = warn ? ` <span class="stale-warn" title="${warn}">&#9888;</span>` : '';
      const dataDate = formatDataDate(df.omnisense_last_ms);
      lines.push(`Omnisense last updated: ${dataDate || FETCH_TIMES.omnisense}${warnHtml}`);
    }
    if (FETCH_TIMES.cycles) {
      const warn = cycleStaleCheck(df.openmeteo_fetch_ms || Date.now());
      const warnHtml = warn ? ` <span class="stale-warn" title="${warn}">&#9888;</span>` : '';
      lines.push(`Cycles (ENSO/IOD/MJO) updated: ${FETCH_TIMES.cycles}${warnHtml}`);
    }
    ftDiv.innerHTML = lines.join('<br>');
  }
  setupStaticListeners();
  loadDataset('house5');
  // Apply saved language preference and mark active button
  const savedLang = localStorage.getItem('arcLang') || 'en';
  if (savedLang !== 'en') setLanguage(savedLang);
  else {
    const menu = document.getElementById('lang-menu');
    if (menu) menu.querySelector('button').classList.add('active');
  }
}

function loadDataset(key) {
  state.datasetKey = key;
  const m = dataset().meta;

  // Reset selections
  state.selectedLoggers = new Set(m.lineLoggers || m.loggers);
  state.selectedRoomLoggers = new Set(m.roomLoggers);
  // Reinitialize compare sets for new dataset
  initCompareSets();
  if (state.compareEnabled) renderCompareSets();
  state.timeMode = 'all';
  document.getElementById('time-mode').value = 'all';
  ['between-inputs','year-input','month-input','week-input','day-input'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));

  // Rebuild logger checkboxes: External / Structural / Room - each with their own buttons
  const loggerDiv = document.getElementById('logger-checkboxes');
  loggerDiv.innerHTML = '';
  function mkSelBtn(label, onClick, i18nKey) {
    const b = document.createElement('button');
    b.className = 'sel-btn'; b.textContent = label;
    if (i18nKey) b.dataset.i18n = i18nKey;
    b.addEventListener('click', onClick); return b;
  }
  // Generic checkbox + section builder for both line/histogram and comfort sidebars
  const anomRanges = m.anomalousRanges || {};
  const wbEligibleSet = new Set([...(m.externalLoggers || []), ...m.loggers.filter(id => (new Set(m.roomLoggers || [])).has(id))]);
  function addCheckbox(container, stateSet, id, extraLabel, skipWb) {
    const lbl = document.createElement('label');
    lbl.className = 'cb-label';
    lbl.dataset.tooltip = loggerTooltip(id, m);
    const hasAnom = !!anomRanges[id];
    const anomSuffix = hasAnom ? ' <span class="anomalous-warn">&#9888;</span>' : '';
    lbl.innerHTML = `<input type="checkbox" data-logger-id="${id}" ${stateSet.has(id) ? 'checked' : ''}> <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${m.colors[id]};vertical-align:middle"></span> <span class="logger-name" data-lid="${id}">${ln(id)}</span>${meteoSuffix(id)}${omniSuffix(m.loggerSources[id] || '')}${extraLabel || ''}${anomSuffix}`;
    lbl.querySelector('input').addEventListener('change', e => {
      e.target.checked ? stateSet.add(id) : stateSet.delete(id);
      if (state.timeMode === 'all') _zoomReset = true; updatePlot();
    });
    if (hasAnom) {
      const warn = lbl.querySelector('.anomalous-warn');
      const tip = document.getElementById('anomalous-fixed-tip');
      const reason = anomRanges[id].reason || 'Anomalous data';
      warn.addEventListener('mouseenter', () => {
        const r = warn.getBoundingClientRect();
        tip.innerHTML = reason + '<div style="margin-top:6px;font-style:italic;color:#d4c8a0;font-size:9px;">Exclude anomalous data in Advanced Settings</div>';
        tip.style.display = 'block';
        let left = r.right + 8;
        if (left + 268 > window.innerWidth - 8) left = r.left - 268;
        tip.style.left = left + 'px';
        tip.style.top = r.top + 'px';
      });
      warn.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    }
    container.appendChild(lbl);
    // Inject wet bulb sub-checkbox directly below (only in logger-checkboxes, not comfort panel)
    if (!skipWb && wbEligibleSet.has(id)) {
      const color = m.colors[id] || '#999';
      const wbIcon = `<svg width="16" height="10" viewBox="0 0 16 10" style="vertical-align:middle;flex-shrink:0"><line x1="1" y1="5" x2="15" y2="5" stroke="${color}" stroke-width="2" stroke-dasharray="4,2.5"/></svg>`;
      const wbWrap = document.createElement('div');
      wbWrap.className = 'wb-sub-label';
      wbWrap.style.display = state.wetBulbEnabled ? '' : 'none';
      const wbLbl = document.createElement('label');
      wbLbl.className = 'cb-label';
      wbLbl.style.fontSize = '11px';
      wbLbl.innerHTML = `<input type="checkbox" data-wb-logger="${id}" ${state.wetBulbLoggers.has(id) ? 'checked' : ''}> ${wbIcon} <span class="logger-name" data-lid="${id}">${ln(id)}</span> <span class="wb-suffix" style="color:#888">${t('wetBulbSuffix')}</span>`;
      wbLbl.querySelector('input').addEventListener('change', e => {
        e.target.checked ? state.wetBulbLoggers.add(id) : state.wetBulbLoggers.delete(id);
        updatePlot();
      });
      wbWrap.appendChild(wbLbl);
      container.appendChild(wbWrap);
    }
  }
  function addSection(container, stateSet, title, ids, extraBtns, extraLabelFn, sectionKey, skipWb, titleI18nKey) {
    if (ids.length === 0) return;
    const titleEl = document.createElement('div');
    titleEl.className = 'sub-section-title';
    titleEl.textContent = title;
    const _sectionI18nMap = { external: 'sectionExternal', room: 'sectionRoom', structural: 'sectionStructural' };
    const _titleKey = titleI18nKey || _sectionI18nMap[sectionKey];
    if (_titleKey) titleEl.dataset.i18n = _titleKey;
    container.appendChild(titleEl);
    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex;gap:4px;margin-bottom:4px;flex-wrap:wrap;';
    btnRow.appendChild(mkSelBtn(t('btnAll'), () => {
      ids.forEach(id => {
        stateSet.add(id); container.querySelector(`input[data-logger-id="${id}"]`).checked = true;
        if (state.wetBulbEnabled && wbEligibleSet.has(id)) {
          state.wetBulbLoggers.add(id);
          const wbCb = container.querySelector(`input[data-wb-logger="${id}"]`);
          if (wbCb) wbCb.checked = true;
        }
      });
      if (sectionKey) { state.showSectionAvg[sectionKey] = true; const cb = container.querySelector(`input[data-section-avg="${sectionKey}"]`); if (cb) cb.checked = true; }
      if (state.timeMode === 'all') _zoomReset = true; updatePlot();
    }, 'btnAll'));
    btnRow.appendChild(mkSelBtn(t('btnNone'), () => {
      ids.forEach(id => {
        stateSet.delete(id); container.querySelector(`input[data-logger-id="${id}"]`).checked = false;
        if (state.wetBulbEnabled && wbEligibleSet.has(id)) {
          state.wetBulbLoggers.delete(id);
          const wbCb = container.querySelector(`input[data-wb-logger="${id}"]`);
          if (wbCb) wbCb.checked = false;
        }
      });
      if (sectionKey) { state.showSectionAvg[sectionKey] = false; const cb = container.querySelector(`input[data-section-avg="${sectionKey}"]`); if (cb) cb.checked = false; }
      if (state.timeMode === 'all') _zoomReset = true; updatePlot();
    }, 'btnNone'));
    if (sectionKey) {
      const lockBtn = document.createElement('button');
      lockBtn.className = 'lock-btn';
      lockBtn.dataset.sectionLock = sectionKey;
      lockBtn.style.display = state.chartType === 'periodic' ? 'inline-block' : 'none';
      lockBtn.textContent = t('lockAvg');
      lockBtn.title = 'Lock average: freeze which loggers contribute to this section average';
      lockBtn.addEventListener('click', function() {
        if (state.lockedAvg[sectionKey] !== null) {
          state.lockedAvg[sectionKey] = null;
          this.textContent = t('lockAvg');
          this.classList.remove('locked');
          this.title = 'Lock average: freeze which loggers contribute to this section average';
          const ind = container.querySelector('.lock-indicator[data-lock-ind="' + sectionKey + '"]');
          if (ind) ind.style.display = 'none';
        } else {
          state.lockedAvg[sectionKey] = new Set(ids.filter(id => stateSet.has(id)));
          this.textContent = t('unlockAvg');
          this.classList.add('locked');
          this.title = 'Click to unlock: average will follow checkbox selections again';
          const ind = container.querySelector('.lock-indicator[data-lock-ind="' + sectionKey + '"]');
          if (ind) ind.style.display = 'inline';
        }
        updatePlot();
      });
      btnRow.appendChild(lockBtn);
    }
    if (extraBtns) extraBtns.forEach(b => btnRow.appendChild(b));
    container.appendChild(btnRow);
    ids.forEach(id => addCheckbox(container, stateSet, id, extraLabelFn ? extraLabelFn(id) : '', skipWb));
  }
  function mkSourceBtns(container, stateSet, ids) {
    const hasTT = ids.some(id => m.loggerSources[id] === 'TinyTag');
    const hasOS = ids.some(id => m.loggerSources[id] === 'Omnisense');
    if (!hasTT || !hasOS) return null;
    function syncWb(id, checked) {
      if (state.wetBulbEnabled && wbEligibleSet.has(id)) {
        checked ? state.wetBulbLoggers.add(id) : state.wetBulbLoggers.delete(id);
        const wbCb = container.querySelector(`input[data-wb-logger="${id}"]`);
        if (wbCb) wbCb.checked = checked;
      }
    }
    return [
      mkSelBtn('TinyTag',  () => { ids.forEach(id => { const is = m.loggerSources[id]==='TinyTag';  is ? stateSet.add(id) : stateSet.delete(id); container.querySelector(`input[data-logger-id="${id}"]`).checked = is; syncWb(id, is); }); if (state.timeMode === 'all') _zoomReset = true; updatePlot(); }),
      mkSelBtn('Omnisense',() => { ids.forEach(id => { const is = m.loggerSources[id]==='Omnisense'; is ? stateSet.add(id) : stateSet.delete(id); container.querySelector(`input[data-logger-id="${id}"]`).checked = is; syncWb(id, is); }); if (state.timeMode === 'all') _zoomReset = true; updatePlot(); }),
    ];
  }
  const extSet   = new Set(m.externalLoggers || []);
  const roomSet  = new Set(m.roomLoggers || []);
  const lineSet  = new Set(m.lineLoggers || m.loggers);
  const midLoggers  = m.loggers.filter(id => !extSet.has(id) && !roomSet.has(id) && lineSet.has(id));
  const roomLoggers = m.loggers.filter(id => !extSet.has(id) &&  roomSet.has(id) && lineSet.has(id));
  const extTTLabel = id => (extSet.has(id) && m.loggerSources[id] === 'TinyTag') ? '<span style="color:#aaa"> (TinyTag)</span>' : '';
  // Section average checkbox helper (only shown in periodic mode)
  const sectionAvgColors = {external: '#1a1a1a', room: '#333399', structural: '#663300'};
  function addSectionAvgCheckbox(container, sectionKey) {
    const lbl = document.createElement('label');
    lbl.className = 'cb-label periodic-avg-cb';
    lbl.style.display = 'none'; // shown only in periodic mode
    const color = sectionAvgColors[sectionKey];
    const isLocked = state.lockedAvg[sectionKey] !== null;
    const avgKey = sectionKey + 'Avg';
    lbl.innerHTML = `<input type="checkbox" data-section-avg="${sectionKey}" ${state.showSectionAvg[sectionKey] ? 'checked' : ''}> <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${color};vertical-align:middle"></span> <span data-i18n="${avgKey}">${t(avgKey)}</span><span class="lock-indicator" data-lock-ind="${sectionKey}" style="display:${isLocked ? 'inline' : 'none'}; color:#999; font-size:10px; margin-left:3px;"><svg style="vertical-align:middle" width="8" height="10" viewBox="0 0 8 10"><rect x="0" y="4" width="8" height="6" rx="1" fill="#aaa"/><path d="M2 4V3a2 2 0 0 1 4 0v1" fill="none" stroke="#aaa" stroke-width="1.2"/></svg></span>`;
    lbl.querySelector('input').addEventListener('change', e => {
      state.showSectionAvg[sectionKey] = e.target.checked; updatePlot();
    });
    container.appendChild(lbl);
  }
  // Reset wet bulb logger set; sub-checkboxes are injected by addCheckbox below
  state.wetBulbLoggers = new Set();
  // External section
  if (m.externalLoggers && m.externalLoggers.length > 0) {
    addSection(loggerDiv, state.selectedLoggers, t('sectionExternal'), m.externalLoggers, null, extTTLabel, 'external');
    addSectionAvgCheckbox(loggerDiv, 'external');
    const hr = document.createElement('hr'); hr.className = 'divider'; loggerDiv.appendChild(hr);
  }
  // Room loggers section
  if (roomLoggers.length > 0) {
    addSection(loggerDiv, state.selectedLoggers, t('sectionRoom'), roomLoggers, mkSourceBtns(loggerDiv, state.selectedLoggers, roomLoggers), null, 'room');
    addSectionAvgCheckbox(loggerDiv, 'room');
  }
  // Structural section
  if (midLoggers.length > 0) {
    if (roomLoggers.length > 0) { const hr = document.createElement('hr'); hr.className = 'divider'; loggerDiv.appendChild(hr); }
    addSection(loggerDiv, state.selectedLoggers, t('sectionStructural'), midLoggers, mkSourceBtns(loggerDiv, state.selectedLoggers, midLoggers), null, 'structural');
    addSectionAvgCheckbox(loggerDiv, 'structural');
  }
  if (roomLoggers.length === 0 && midLoggers.length === 0) {
    const allNonExt = m.loggers.filter(id => !extSet.has(id));
    if (allNonExt.length > 0) addSection(loggerDiv, state.selectedLoggers, 'Loggers', allNonExt);
  }

  // Rebuild adaptive comfort logger checkboxes (reuses generic addSection/addCheckbox)
  const roomDiv = document.getElementById('room-logger-checkboxes');
  roomDiv.innerHTML = '';
  const comfortRoomIds = (m.comfortLoggers || m.roomLoggers).filter(id => (m.roomLoggers || []).includes(id));
  const comfortStructIds = (m.comfortLoggers || []).filter(id => (m.structuralLoggers || []).includes(id));
  addSection(roomDiv, state.selectedRoomLoggers, t('sectionRoom'), comfortRoomIds, mkSourceBtns(roomDiv, state.selectedRoomLoggers, comfortRoomIds), null, null, true, 'sectionRoom');
  if (comfortStructIds.length > 0) {
    if (comfortRoomIds.length > 0) { const hr = document.createElement('hr'); hr.className = 'divider'; roomDiv.appendChild(hr); }
    addSection(roomDiv, state.selectedRoomLoggers, t('sectionStructural'), comfortStructIds, mkSourceBtns(roomDiv, state.selectedRoomLoggers, comfortStructIds), null, null, true, 'sectionStructural');
  }

  // Show historic section if data available
  document.getElementById('historic-section').style.display = HISTORIC ? '' : 'none';

  // Rebuild time dropdowns
  const ysel = document.getElementById('year-select');
  const ssel = document.getElementById('season-select');
  const mosel = document.getElementById('month-select');
  const wsel = document.getElementById('week-select');
  const dsel = document.getElementById('day-select');
  ysel.innerHTML = ''; ssel.innerHTML = ''; mosel.innerHTML = ''; wsel.innerHTML = ''; dsel.innerHTML = '';

  m.availableYears.forEach(y => ysel.add(new Option(y, y)));
  m.availableSeasons.forEach(({label, year, season}) => ssel.add(new Option(label, `${year}-${season}`)));
  m.availableMonths.forEach(({label, year, month}) => mosel.add(new Option(label, `${year}-${month}`)));
  m.availableWeeks.forEach(({label, year, week}) => wsel.add(new Option(label, `${year}-${week}`)));
  m.availableDays.forEach(({label, ts}) => dsel.add(new Option(label, ts)));

  // Set defaults to last available
  const fmt = ms => new Date(ms).toISOString().slice(0, 10);
  document.getElementById('date-start').value = fmt(m.dateRange.min);
  document.getElementById('date-end').value = fmt(m.dateRange.max);
  state.betweenStart = m.dateRange.min;
  state.betweenEnd = m.dateRange.max;

  // Initialize custom cycle defaults
  const fmtMonth = ms => new Date(ms).toISOString().slice(0, 7);
  document.getElementById('periodic-warnings').innerHTML = '';

  if (m.availableYears.length) {
    state.selectedYear = m.availableYears[m.availableYears.length - 1];
    ysel.value = state.selectedYear;
  }
  if (m.availableSeasons.length) {
    const last = m.availableSeasons[m.availableSeasons.length - 1];
    state.selectedSeason = {year: last.year, season: last.season};
    ssel.value = `${last.year}-${last.season}`;
  }
  if (m.availableMonths.length) {
    const last = m.availableMonths[m.availableMonths.length - 1];
    state.selectedMonth = {year: last.year, month: last.month};
    mosel.value = `${last.year}-${last.month}`;
  }
  if (m.availableWeeks.length) {
    const last = m.availableWeeks[m.availableWeeks.length - 1];
    state.selectedWeek = {year: last.year, week: last.week};
    wsel.value = `${last.year}-${last.week}`;
  }
  if (m.availableDays.length) {
    state.selectedDay = m.availableDays[m.availableDays.length - 1].ts;
    dsel.value = state.selectedDay;
  }

  // Reset comfort stats and gap indicators
  document.getElementById('comfort-overall').textContent = '-';
  document.getElementById('comfort-room-grid').innerHTML = '';
  document.getElementById('comfort-stats').classList.remove('has-gaps');
  document.getElementById('gap-warning').classList.add('hidden');
  document.getElementById('gap-dropdown-wrap').classList.add('hidden');
  document.getElementById('gap-tip').style.display = 'none';
  // Reset histogram stats
  document.getElementById('hist-overall').textContent = '-';
  document.getElementById('hist-room-grid').innerHTML = '';
  document.getElementById('hist-stats-box').classList.remove('has-gaps');
  document.getElementById('hist-gap-warning').classList.add('hidden');
  document.getElementById('hist-gap-dropdown-wrap').classList.add('hidden');
  document.getElementById('hist-gap-tip').style.display = 'none';

  // If already in periodic mode, show periodic-specific UI elements on freshly created checkboxes
  if (state.chartType === 'periodic') {
    document.querySelectorAll('.periodic-avg-cb').forEach(el => { el.style.display = ''; });
    document.querySelectorAll('.lock-btn').forEach(el => { el.style.display = 'inline-block'; });
  }

  // Show/hide anomalous data checkbox and Advanced Settings wrap based on dataset
  const hasAnomalous = dataset().meta.anomalousRanges && Object.keys(dataset().meta.anomalousRanges).length > 0;
  document.getElementById('anomalous-label').style.display = hasAnomalous ? '' : 'none';
  const isLineChart = state.chartType === 'line';
  const showSubstratNow = !isLineChart;
  const isPeriodicChart = state.chartType === 'periodic';
  document.getElementById('advanced-settings-wrap').style.display = (showSubstratNow || hasAnomalous || isLineChart || isPeriodicChart) ? '' : 'none';
  // Show wet bulb toggle in advanced settings only on line/periodic, not in long-term mode
  const _wbOk = (isLineChart || isPeriodicChart) && !state.historicMode;
  document.getElementById('wetbulb-adv-wrap').style.display = _wbOk ? '' : 'none';

  // Update reading count in sidebar footer
  const rcEl = document.getElementById('dataset-reading-count');
  if (rcEl && m.totalReadings) {
    const minDate = new Date(m.dateRange.min).toISOString().slice(0, 10);
    const maxDate = new Date(m.dateRange.max).toISOString().slice(0, 10);
    rcEl.textContent = m.totalReadings + ' readings, ' + minDate + ' to ' + maxDate;
  }

  updatePlot();
}

// ── Default-reset helpers ──────────────────────────────────────────────────────
function resetTimeMode() {
  state.timeMode = 'all';
  document.getElementById('time-mode').value = 'all';
  ['between-inputs','year-input','month-input','week-input','day-input'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));
}

function resetMetrics() {
  state.selectedMetrics = new Set(['temperature', 'humidity']);
  document.getElementById('cb-temperature').checked = true;
  document.getElementById('cb-humidity').checked = true;
}

function resetLineDefaults() {
  const m = dataset().meta;

  // Loggers: Open-Meteo only in historic mode, all line loggers otherwise
  state.selectedLoggers.clear();
  if (state.historicMode) {
    m.loggers.forEach(lid => { if (isOpenMeteo(lid)) state.selectedLoggers.add(lid); });
  } else {
    (m.lineLoggers || m.loggers).forEach(id => state.selectedLoggers.add(id));
  }
  document.getElementById('logger-checkboxes').querySelectorAll('input[data-logger-id]').forEach(cb => {
    cb.checked = state.selectedLoggers.has(cb.dataset.loggerId);
  });

  // Metrics
  if (state.historicMode) {
    state.selectedMetrics = new Set(['temperature']);
    document.getElementById('cb-temperature').checked = true;
    document.getElementById('cb-humidity').checked = false;
    document.getElementById('humidity-label').style.display = 'none';
  } else {
    resetMetrics();
    document.getElementById('humidity-label').style.display = '';
  }

  // Time
  resetTimeMode();

  // Options
  if (state.historicMode) {
    state.showThreshold = false;
    document.getElementById('cb-threshold').checked = false;
    state.showSeasonLines = false;
    document.getElementById('cb-seasons').checked = false;
    if (state.chartType !== 'histogram') {
      document.getElementById('line-options-section').style.display = 'none';
      document.getElementById('line-options-divider').style.display = 'none';
    }
    // Reset historic series to all checked
    state.selectedHistoricSeries = new Set();
    if (HISTORIC) {
      HISTORIC.series.forEach(s => state.selectedHistoricSeries.add(s.id));
    }
    document.getElementById('historic-series-checkboxes').querySelectorAll('input[type=checkbox]').forEach(cb => {
      cb.checked = true;
    });
  } else {
    state.showThreshold = true;
    document.getElementById('cb-threshold').checked = true;
    state.showSeasonLines = true;
    document.getElementById('cb-seasons').checked = true;
    document.getElementById('line-options-section').style.display = '';
    document.getElementById('line-options-divider').style.display = '';
    state.selectedHistoricSeries = new Set();
    document.getElementById('cb-historic-mode').checked = false;
    document.getElementById('historic-series-checkboxes').style.display = 'none';
    document.getElementById('historic-series-checkboxes').innerHTML = '';
  }

  // Periodic settings
  state.periodCycle = 'day';
  state.periodGroupBy = 'hour';
  document.getElementById('natural-cycles').value = 'day';
  document.getElementById('period-group-by').value = 'hour';
  const ncTip = document.getElementById('natural-cycles-tip');
  if (ncTip) { ncTip.style.display = 'none'; ncTip.innerHTML = ''; }
  const ncInfo = document.getElementById('natural-cycles-info');
  if (ncInfo) ncInfo.style.display = 'none';

  // Histogram settings
  state.histogramBarmode = 'stack';
  document.getElementById('histogram-barmode').value = 'stack';

  // Section averages: all on, all unlocked
  state.showSectionAvg = {external: true, room: true, structural: true};
  state.lockedAvg = {external: null, room: null, structural: null};
  document.querySelectorAll('input[data-section-avg]').forEach(cb => { cb.checked = true; });
  document.querySelectorAll('[data-section-lock]').forEach(btn => {
    btn.textContent = t('lockAvg');
    btn.classList.remove('locked');
    btn.title = 'Lock average: freeze which loggers contribute to this section average';
  });
  document.querySelectorAll('.lock-indicator').forEach(el => { el.style.display = 'none'; });

  // Substratification: clear all filters and collapse
  state.substratFilters = [];
  state.substratCombine = 'all';
  document.getElementById('substrat-filters').innerHTML = '';
  document.querySelectorAll('input[name="substrat-combine"]').forEach(r => { r.checked = r.value === 'all'; });
  const advBody2 = document.getElementById('advanced-settings-body');
  advBody2.dataset.open = '0';
  advBody2.style.display = 'none';
  document.getElementById('advanced-settings-arrow').classList.remove('open');

  // Wet bulb: reset master toggle and all per-logger selections
  state.wetBulbEnabled = false;
  state.wetBulbLoggers = new Set();
  document.getElementById('cb-wetbulb').checked = false;
  document.querySelectorAll('.wb-sub-label').forEach(el => { el.style.display = 'none'; });
  document.querySelectorAll('input[data-wb-logger]').forEach(cb => { cb.checked = false; });

  updatePlot();
}

function resetComfortDefaults() {
  const m = dataset().meta;
  state.selectedRoomLoggers.clear();
  (m.roomLoggers || []).forEach(id => state.selectedRoomLoggers.add(id));
  document.getElementById('room-logger-checkboxes').querySelectorAll('input[data-logger-id]').forEach(cb => {
    cb.checked = state.selectedRoomLoggers.has(cb.dataset.loggerId);
  });
  state.comfortModel = 'rh_gt_60';
  document.getElementById('comfort-model').value = 'rh_gt_60';
  state.comfortPctMode = 'below_upper';
  document.getElementById('comfort-pct-mode').value = 'below_upper';
  resetMetrics();
  resetTimeMode();
  updatePlot();
}

// ── Static event listeners (survive dataset changes) ──────────────────────────
// ── PNG watermark (SVG DOM injection) ─────────────────────────────────────────
function injectSVGWatermark(doc, svgW, svgH, opacity) {
  if (!LOGO_B64) return;
  const ns = 'http://www.w3.org/2000/svg';
  const root = doc.querySelector('.infolayer') || doc.documentElement;
  const logoH = 40, logoW = Math.round(logoH * LOGO_ASPECT);
  const textSize = 9, lineH = 14;
  const leftMargin = 12, rightMargin = 12, bottomEdge = 10, topEdge = 12;
  const line1 = 'Graph generated by ARC (Architecture for Resilient Communities).';
  const line2 = 'Find out more about what we do at actionresearchprojects.net.';
  const logoX = leftMargin, logoY = topEdge;
  const txt2Y = svgH - bottomEdge, txt1Y = txt2Y - lineH;

  const imgEl = doc.createElementNS(ns, 'image');
  imgEl.setAttribute('href', LOGO_B64);
  imgEl.setAttribute('x', String(logoX));
  imgEl.setAttribute('y', String(logoY));
  imgEl.setAttribute('width', String(logoW));
  imgEl.setAttribute('height', String(logoH));
  imgEl.setAttribute('opacity', String(opacity));
  root.appendChild(imgEl);

  function mkTxt(y, content) {
    const el = doc.createElementNS(ns, 'text');
    el.setAttribute('x', String(svgW - rightMargin));
    el.setAttribute('y', String(y));
    el.setAttribute('text-anchor', 'end');
    el.setAttribute('dominant-baseline', 'auto');
    el.setAttribute('font-family', 'Ubuntu, sans-serif');
    el.setAttribute('font-size', String(textSize));
    el.setAttribute('fill', '#555');
    el.setAttribute('opacity', String(opacity));
    el.textContent = content;
    return el;
  }
  root.appendChild(mkTxt(txt1Y, line1));
  root.appendChild(mkTxt(txt2Y, line2));
}

// ── SVG → canvas → PNG helper ─────────────────────────────────────────────────
function svgToCanvas(svgStr, W, H, scale) {
  return new Promise((resolve, reject) => {
    const canvas = document.createElement('canvas');
    canvas.width = W * scale; canvas.height = H * scale;
    const ctx = canvas.getContext('2d');
    ctx.scale(scale, scale);
    const img = new Image();
    img.onload = () => { ctx.drawImage(img, 0, 0, W, H); resolve(canvas); };
    img.onerror = reject;
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgStr);
  });
}

function setupStaticListeners() {
  document.getElementById('reset-line-btn').addEventListener('click', resetLineDefaults);
  document.getElementById('reset-comfort-btn').addEventListener('click', resetComfortDefaults);

  // Close language menu on click outside
  document.addEventListener('click', e => {
    const wrap = document.getElementById('lang-wrap');
    const menu = document.getElementById('lang-menu');
    if (menu && wrap && !wrap.contains(e.target)) menu.classList.remove('open');
  });

  // Substratification combine logic
  document.querySelectorAll('input[name="substrat-combine"]').forEach(r => {
    r.addEventListener('change', () => { state.substratCombine = r.value; updatePlot(); });
  });

  document.getElementById('dataset-select').addEventListener('change', e => {
    loadDataset(e.target.value);
  });

  function handleChartTypeChange(newType) {
    const prevType = state.chartType;
    state.chartType = newType;
    // Show/hide beta sub-dropdown and style main dropdown
    const betaSel = document.getElementById('beta-chart-type');
    const mainSel = document.getElementById('chart-type');
    if (newType.startsWith('beta-') || newType === 'beta') {
      betaSel.style.display = '';
      mainSel.value = 'beta';
      mainSel.style.color = '#c0392b';
      if (newType === 'beta') { state.chartType = betaSel.value; }
    } else {
      betaSel.style.display = 'none';
      mainSel.style.color = '';
    }
    const isLine = state.chartType === 'line';
    const isHistogram = state.chartType === 'histogram';
    const isComfort = state.chartType === 'comfort';
    const isPeriodic = state.chartType === 'periodic';
    const isBeta = state.chartType.startsWith('beta-');
    const m = dataset().meta;
    const syncRoomSet = new Set(m.roomLoggers || []);
    // Sync selections between line/histogram ↔ adaptive comfort (room loggers only; structural defaults off)
    if (prevType === 'comfort' && !isComfort) {
      // Leaving comfort → push room logger comfort selections back into selectedLoggers
      for (const id of syncRoomSet) {
        state.selectedRoomLoggers.has(id) ? state.selectedLoggers.add(id) : state.selectedLoggers.delete(id);
      }
      // Update line-controls checkboxes to match
      document.getElementById('logger-checkboxes').querySelectorAll('input[data-logger-id]').forEach(cb => {
        cb.checked = state.selectedLoggers.has(cb.dataset.loggerId);
      });
    } else if (isComfort && prevType !== 'comfort') {
      // Entering comfort → push line logger selections into selectedRoomLoggers (room loggers only)
      for (const id of syncRoomSet) {
        state.selectedLoggers.has(id) ? state.selectedRoomLoggers.add(id) : state.selectedRoomLoggers.delete(id);
      }
      // Update comfort checkboxes to match
      document.getElementById('room-logger-checkboxes').querySelectorAll('input[data-logger-id]').forEach(cb => {
        cb.checked = state.selectedRoomLoggers.has(cb.dataset.loggerId);
      });
    }
    document.getElementById('line-controls').classList.toggle('hidden', isComfort || isBeta);
    document.getElementById('comfort-controls').classList.toggle('hidden', !isComfort);
    document.getElementById('histogram-stats').classList.toggle('hidden', !isHistogram);
    if (!isPeriodic) document.getElementById('periodic-completeness').classList.add('hidden');
    document.getElementById('periodic-options').style.display = isPeriodic ? '' : 'none';
    document.getElementById('periodic-divider').style.display = isPeriodic ? '' : 'none';
    document.getElementById('histogram-options').style.display = isHistogram ? '' : 'none';
    document.getElementById('histogram-options-divider').style.display = isHistogram ? '' : 'none';
    // Advanced Settings for all chart types; substrat controls hidden on line graph
    const advWrap = document.getElementById('advanced-settings-wrap');
    const showSubstrat = isPeriodic || isHistogram || isComfort;
    if (isComfort) {
      const comfortCtrl = document.getElementById('comfort-controls');
      comfortCtrl.insertBefore(advWrap, comfortCtrl.children[0]);
    } else {
      const anchor = document.getElementById('histogram-options-divider');
      anchor.parentNode.insertBefore(advWrap, anchor.nextSibling);
    }
    const hasAnomalousData = dataset().meta.anomalousRanges && Object.keys(dataset().meta.anomalousRanges).length > 0;
    advWrap.style.display = isBeta ? 'none' : ''; // hide advanced settings for beta charts
    document.querySelectorAll('.substrat-only').forEach(el => { el.style.display = (showSubstrat && !state.compareEnabled) ? '' : 'none'; });
    const advBody = document.getElementById('advanced-settings-body');
    advBody.style.display = (advBody.dataset.open === '1') ? 'block' : 'none';
    if (!showSubstrat) {
      state.substratFilters = [];
      document.getElementById('substrat-filters').innerHTML = '';
    }
    document.querySelectorAll('.periodic-avg-cb').forEach(el => { el.style.display = isPeriodic ? '' : 'none'; });
    document.querySelectorAll('.lock-btn').forEach(el => { el.style.display = isPeriodic ? 'inline-block' : 'none'; });
    if (isBeta) {
      // Beta charts: show line-controls for logger selection, hide irrelevant sidebar controls
      document.getElementById('line-controls').classList.remove('hidden');
      document.getElementById('line-options-section').style.display = 'none';
      document.getElementById('line-options-divider').style.display = 'none';
      if (HISTORIC) document.getElementById('historic-section').style.display = 'none';
      document.getElementById('humidity-label').style.display = 'none';
      document.getElementById('cb-threshold').parentElement.style.display = 'none';
      document.getElementById('cb-seasons').parentElement.style.display = 'none';
      // Hide external logger checkboxes; show room loggers (+ structural for data quality)
      const _m = dataset().meta;
      const _roomSet = new Set(_m.roomLoggers || []);
      const _structSet = new Set(_m.structuralLoggers || []);
      const _isQuality = state.chartType === 'beta-quality';
      const loggerDiv = document.getElementById('logger-checkboxes');
      // First reset all children to visible, then apply filter
      for (const c of loggerDiv.children) { c.style.display = ''; }
      let inVisibleSection = false;
      for (const child of Array.from(loggerDiv.children)) {
        if (child.classList && child.classList.contains('sub-section-title')) {
          let sib = child.nextElementSibling;
          let sectionVisible = false;
          while (sib && !sib.classList.contains('sub-section-title')) {
            const cb = sib.querySelector && sib.querySelector('input[data-logger-id]');
            if (cb) {
              const lid = cb.dataset.loggerId;
              sectionVisible = _roomSet.has(lid) || (_isQuality && _structSet.has(lid));
              break;
            }
            sib = sib.nextElementSibling;
          }
          inVisibleSection = sectionVisible;
          child.style.display = inVisibleSection ? '' : 'none';
        } else {
          child.style.display = inVisibleSection ? '' : 'none';
        }
      }
    } else {
      // Non-beta: ensure all logger sections are visible
      const loggerDiv = document.getElementById('logger-checkboxes');
      for (const child of loggerDiv.children) { child.style.display = ''; }
    }
    // Re-apply controls whose visibility was clobbered by the display reset above
    const _loggerDiv = document.getElementById('logger-checkboxes');
    _loggerDiv.querySelectorAll('.periodic-avg-cb').forEach(el => { el.style.display = isPeriodic ? '' : 'none'; });
    _loggerDiv.querySelectorAll('.lock-btn').forEach(el => { el.style.display = isPeriodic ? 'inline-block' : 'none'; });
    if (!state.wetBulbEnabled) _loggerDiv.querySelectorAll('.wb-sub-label').forEach(el => { el.style.display = 'none'; });
    if (isBeta) {
      // already handled above
    } else if (isPeriodic) {
      document.getElementById('line-options-section').style.display = state.periodCycle === 'year' ? '' : 'none';
      document.getElementById('line-options-divider').style.display = state.periodCycle === 'year' ? '' : 'none';
      if (HISTORIC) document.getElementById('historic-section').style.display = 'none';
      document.getElementById('humidity-label').style.display = '';
      document.getElementById('cb-threshold').parentElement.style.display = 'none';
      document.getElementById('cb-seasons').parentElement.style.display = state.periodCycle === 'year' ? '' : 'none';
    } else if (isHistogram) {
      // Show options but hide season lines checkbox (not applicable to histogram)
      document.getElementById('line-options-section').style.display = '';
      document.getElementById('line-options-divider').style.display = '';
      document.getElementById('cb-threshold').parentElement.style.display = '';
      document.getElementById('cb-seasons').parentElement.style.display = 'none';
      if (HISTORIC) document.getElementById('historic-section').style.display = '';
      if (state.historicMode) {
        // Historic mode on: keep current state, ensure series checkboxes visible
        document.getElementById('humidity-label').style.display = 'none';
        if (!document.getElementById('historic-series-checkboxes').children.length) {
          buildHistoricSeriesCheckboxes();
        }
        document.getElementById('historic-series-checkboxes').style.display = '';
      }
    } else if (isLine) {
      document.getElementById('cb-threshold').parentElement.style.display = '';
      document.getElementById('cb-seasons').parentElement.style.display = '';
      document.getElementById('line-options-section').style.display = '';
      document.getElementById('line-options-divider').style.display = '';
      if (HISTORIC) document.getElementById('historic-section').style.display = '';
      // Re-apply historic mode visual effects now that we're back on line graph
      if (state.historicMode) {
        document.getElementById('cb-humidity').checked = false;
        state.selectedMetrics.delete('humidity');
        document.getElementById('humidity-label').style.display = 'none';
        document.getElementById('line-options-section').style.display = 'none';
        document.getElementById('line-options-divider').style.display = 'none';
        // Ensure series checkboxes visible when returning from adaptive comfort
        if (!document.getElementById('historic-series-checkboxes').children.length) {
          buildHistoricSeriesCheckboxes();
        }
        document.getElementById('historic-series-checkboxes').style.display = '';
      }
    }
    document.getElementById('anomalous-label').style.display =
      (dataset().meta.anomalousRanges && Object.keys(dataset().meta.anomalousRanges).length > 0) ? '' : 'none';
    // Show wet bulb toggle in advanced settings only on line/periodic, not in long-term mode
    const _showWb = (isLine || isPeriodic) && !state.historicMode;
    document.getElementById('wetbulb-adv-wrap').style.display = _showWb ? '' : 'none';
    // Re-render compare sets when chart type changes (logger pool differs for comfort)
    if (state.compareEnabled) renderCompareSets();
    updatePlot();
  }
  document.getElementById('chart-type').addEventListener('change', e => {
    handleChartTypeChange(e.target.value);
  });
  document.getElementById('beta-chart-type').addEventListener('change', e => {
    handleChartTypeChange(e.target.value);
  });

  document.getElementById('comfort-model').addEventListener('change', e => {
    state.comfortModel = e.target.value; updatePlot();
  });

  document.getElementById('comfort-pct-mode').addEventListener('change', e => {
    state.comfortPctMode = e.target.value; updatePlot();
  });

  document.getElementById('time-mode').addEventListener('change', e => {
    state.timeMode = e.target.value;
    ['between-inputs','year-input','season-input','month-input','week-input','day-input'].forEach(id =>
      document.getElementById(id).classList.add('hidden'));
    const map = {between:'between-inputs',year:'year-input',season:'season-input',month:'month-input',week:'week-input',day:'day-input'};
    if (map[state.timeMode]) document.getElementById(map[state.timeMode]).classList.remove('hidden');
    _zoomReset = true; updatePlot();
  });

  document.getElementById('date-start').addEventListener('change', e => {
    state.betweenStart = new Date(e.target.value + 'T00:00:00').getTime(); _zoomReset = true; updatePlot();
  });
  document.getElementById('date-end').addEventListener('change', e => {
    state.betweenEnd = new Date(e.target.value + 'T23:59:59').getTime(); _zoomReset = true; updatePlot();
  });
  document.getElementById('year-select').addEventListener('change', e => {
    state.selectedYear = parseInt(e.target.value); _zoomReset = true; updatePlot();
  });
  document.getElementById('season-select').addEventListener('change', e => {
    const [y, s] = e.target.value.split('-').map(Number);
    state.selectedSeason = {year: y, season: s}; _zoomReset = true; updatePlot();
  });
  document.getElementById('month-select').addEventListener('change', e => {
    const [y, mo] = e.target.value.split('-').map(Number);
    state.selectedMonth = {year: y, month: mo}; _zoomReset = true; updatePlot();
  });
  document.getElementById('week-select').addEventListener('change', e => {
    const [y, w] = e.target.value.split('-').map(Number);
    state.selectedWeek = {year: y, week: w}; _zoomReset = true; updatePlot();
  });
  document.getElementById('day-select').addEventListener('change', e => {
    state.selectedDay = parseInt(e.target.value); _zoomReset = true; updatePlot();
  });

  document.getElementById('cb-temperature').addEventListener('change', e => {
    e.target.checked ? state.selectedMetrics.add('temperature') : state.selectedMetrics.delete('temperature');
    _zoomReset = true; updatePlot();
  });
  document.getElementById('cb-humidity').addEventListener('change', e => {
    e.target.checked ? state.selectedMetrics.add('humidity') : state.selectedMetrics.delete('humidity');
    _zoomReset = true; updatePlot();
  });
  document.getElementById('cb-wetbulb').addEventListener('change', e => {
    state.wetBulbEnabled = e.target.checked;
    document.querySelectorAll('.wb-sub-label').forEach(el => { el.style.display = e.target.checked ? '' : 'none'; });
    updatePlot();
  });
  document.getElementById('cb-threshold').addEventListener('change', e => {
    state.showThreshold = e.target.checked; updatePlot();
  });
  document.getElementById('cb-seasons').addEventListener('change', e => {
    state.showSeasonLines = e.target.checked; updatePlot();
  });
  document.getElementById('cb-exclude-anomalous').addEventListener('change', e => {
    state.excludeAnomalous = e.target.checked; updatePlot();
  });
  document.getElementById('cb-compare').addEventListener('change', e => {
    state.compareEnabled = e.target.checked;
    document.getElementById('compare-body').style.display = state.compareEnabled ? 'block' : 'none';
    // Hide/show main logger checkboxes and comfort room checkboxes
    document.getElementById('logger-checkboxes').parentElement.classList.toggle('compare-hide-main', state.compareEnabled);
    document.getElementById('room-logger-checkboxes').parentElement.classList.toggle('compare-hide-main', state.compareEnabled);
    // Hide main substrat controls in compare mode
    document.querySelectorAll('.substrat-only').forEach(el => {
      el.style.display = state.compareEnabled ? 'none' : (state.chartType !== 'line' ? '' : 'none');
    });
    if (state.compareEnabled) {
      if (state.compareSets.length === 0) initCompareSets();
      renderCompareSets();
    }
    updatePlot();
  });
  document.getElementById('compare-set-count').addEventListener('change', e => {
    state.compareSetCount = parseInt(e.target.value);
    renderCompareSets();
    updatePlot();
  });
  document.getElementById('cb-density').addEventListener('change', e => {
    state.showDensity = e.target.checked; updatePlot();
  });

  // Average profiles controls — recomputed on each call so it follows the language
  function groupByOptionsFor(cycle) {
    const map = {
      day:  [{value:'hour', label:t('hour')}, {value:'synoptic', label:t('synopticHours')}],
      year: [{value:'day', label:t('day')}, {value:'week', label:t('week')}, {value:'month', label:t('month')}, {value:'season', label:t('season')}],
      mjo:  [{value:'phase', label:t('phase18')}],
      iod:  [{value:'phase', label:t('phasePNN')}],
      enso: [{value:'phase', label:t('phaseENSO')}],
    };
    return map[cycle] || [];
  }
  const oscInfoTexts = {
    mjo: 'Madden\u2013Julian Oscillation: a tropical weather pattern that circles the globe every 30\u201360 days, modulating rainfall and temperature. 8 phases track its position \u2014 Phases 2\u20133 (Indian Ocean) and 4\u20135 (Maritime Continent) are most relevant to East Africa. Weekly RMM phase data; weeks with amplitude < 1.0 are excluded.',
    iod: 'Indian Ocean Dipole: a sea-surface temperature gradient between the western and eastern Indian Ocean. Positive IOD brings wetter conditions to East Africa; Negative IOD brings drier conditions. Monthly DMI-based phases: Positive, Negative, or Neutral.',
    enso: 'El Ni\u00f1o\u2013Southern Oscillation: Pacific Ocean temperature cycles affecting global weather. El Ni\u00f1o tends to bring wetter short rains (Vuli) to East Africa; La Ni\u00f1a tends to bring drier conditions. Monthly ONI-based phases: El Ni\u00f1o, La Ni\u00f1a, or Neutral.',
  };
  function updatePeriodCycleInfo() {
    const infoIcon = document.getElementById('natural-cycles-info');
    const infoTip = document.getElementById('natural-cycles-tip');
    const isOsc = state.periodCycle === 'mjo' || state.periodCycle === 'iod' || state.periodCycle === 'enso';
    infoIcon.style.display = isOsc ? '' : 'none';
    infoTip.style.display = 'none';
    infoTip.textContent = oscInfoTexts[state.periodCycle] || '';
    if (isOsc) {
      infoIcon.onmouseenter = () => { infoTip.style.display = ''; };
      infoIcon.onmouseleave = () => { infoTip.style.display = 'none'; };
    }
  }
  window.updateGroupByDropdown = function() {
    const gsel = document.getElementById('period-group-by');
    gsel.innerHTML = '';
    const opts = groupByOptionsFor(state.periodCycle);
    opts.forEach(o => gsel.add(new Option(o.label, o.value)));
    // Default: month for year, hour for day, phase for oscillations
    const defaults = {year:'month', day:'hour', mjo:'phase', iod:'phase', enso:'phase'};
    state.periodGroupBy = defaults[state.periodCycle] || (opts.length ? opts[0].value : 'hour');
    gsel.value = state.periodGroupBy;
    // Hide group-by row when only one option (climate oscillations)
    gsel.parentElement.style.display = opts.length <= 1 ? 'none' : '';
    // Show/hide oscillation info icon + tip
    updatePeriodCycleInfo();
    // Show/hide options based on cycle selected in periodic mode
    if (state.chartType === 'periodic') {
      const isYear = state.periodCycle === 'year';
      document.getElementById('cb-seasons').parentElement.style.display = isYear ? '' : 'none';
      document.getElementById('line-options-section').style.display = isYear ? '' : 'none';
      document.getElementById('line-options-divider').style.display = isYear ? '' : 'none';
    }
  }
  function fitPeriodCycleWidth() {
    const sel = document.getElementById('natural-cycles');
    const isOsc = sel.value === 'mjo' || sel.value === 'iod' || sel.value === 'enso';
    const fs = isOsc ? '10px' : '12px';
    sel.style.fontSize = fs;
    const tmp = document.createElement('select');
    tmp.style.cssText = 'position:absolute;visibility:hidden;font-size:' + fs + ';';
    tmp.add(new Option(sel.options[sel.selectedIndex].text));
    document.body.appendChild(tmp);
    sel.style.width = (tmp.offsetWidth + 8) + 'px';
    document.body.removeChild(tmp);
  }
  document.getElementById('natural-cycles').addEventListener('change', e => {
    state.periodCycle = e.target.value;
    fitPeriodCycleWidth();
    updateGroupByDropdown();
    updatePlot();
  });
  fitPeriodCycleWidth();
  document.getElementById('period-group-by').addEventListener('change', e => {
    state.periodGroupBy = e.target.value;
    updatePlot();
  });

  document.getElementById('histogram-barmode').addEventListener('change', e => {
    state.histogramBarmode = e.target.value;
    updatePlot();
  });

  function rebuildYearDropdown() {
    const ysel = document.getElementById('year-select');
    const prev = ysel.value;
    ysel.innerHTML = '';
    const m = dataset().meta;
    let years = [...m.availableYears];
    if (HISTORIC && state.historicMode) {
      const allYears = new Set(years);
      HISTORIC.series.forEach(s => s.timestamps.forEach(t => allYears.add(parseInt(t))));
      years = [...allYears].sort((a,b) => a - b);
    }
    years.forEach(y => ysel.add(new Option(y, y)));
    if (years.includes(parseInt(prev))) ysel.value = prev;
    else if (years.length) { ysel.value = years[years.length-1]; state.selectedYear = years[years.length-1]; }
  }
  // Build historic series checkboxes from HISTORIC data
  function buildHistoricSeriesCheckboxes() {
    const div = document.getElementById('historic-series-checkboxes');
    div.innerHTML = '';
    if (!HISTORIC) return;
    HISTORIC.series.forEach(s => {
      state.selectedHistoricSeries.add(s.id);
      const color = CLIMATE_COLORS[s.id] || '#999';
      const lbl = document.createElement('label');
      lbl.className = 'cb-label';
      lbl.innerHTML = `<input type="checkbox" data-series-id="${s.id}" checked> <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${color};vertical-align:middle"></span> ${s.label}`;
      lbl.querySelector('input').addEventListener('change', ev => {
        ev.target.checked ? state.selectedHistoricSeries.add(s.id) : state.selectedHistoricSeries.delete(s.id);
        updatePlot();
      });
      div.appendChild(lbl);
    });
  }

  let savedBeforeHistoric = null;
  document.getElementById('cb-historic-mode').addEventListener('change', e => {
    state.historicMode = e.target.checked;
    const cbHumidity  = document.getElementById('cb-humidity');
    const cbThreshold = document.getElementById('cb-threshold');
    const cbSeasons   = document.getElementById('cb-seasons');
    const m = dataset().meta;
    if (state.historicMode) {
      // Save current states so exiting historic mode restores them
      savedBeforeHistoric = {
        humidity:      cbHumidity.checked,
        temperature:   document.getElementById('cb-temperature').checked,
        threshold:     cbThreshold.checked,
        seasons:       cbSeasons.checked,
        loggers:       new Set(state.selectedLoggers),
        timeMode:      state.timeMode,
        selectedYear:  state.selectedYear,
        selectedMonth: state.selectedMonth,
        selectedWeek:  state.selectedWeek,
        selectedDay:   state.selectedDay,
        betweenStart:  state.betweenStart,
        betweenEnd:    state.betweenEnd,
      };
      // Always: hide humidity
      cbHumidity.checked = false; state.selectedMetrics.delete('humidity');
      document.getElementById('humidity-label').style.display = 'none';
      // Force loggers to Open-Meteo only
      state.selectedLoggers.clear();
      m.loggers.forEach(lid => { if (isOpenMeteo(lid)) state.selectedLoggers.add(lid); });
      document.getElementById('logger-checkboxes').querySelectorAll('input[type=checkbox]').forEach(cb => {
        cb.checked = state.selectedLoggers.has(cb.dataset.loggerId);
      });
      // Line-graph only: hide options section, turn off threshold/seasons
      if (state.chartType !== 'histogram') {
        cbThreshold.checked = false; state.showThreshold = false;
        cbSeasons.checked = false;   state.showSeasonLines = false;
        document.getElementById('line-options-section').style.display = 'none';
        document.getElementById('line-options-divider').style.display = 'none';
      }
      // Hide wet bulb toggle in long-term mode
      document.getElementById('wetbulb-adv-wrap').style.display = 'none';
      // Always: show series checkboxes
      buildHistoricSeriesCheckboxes();
      document.getElementById('historic-series-checkboxes').style.display = '';
    } else {
      // Restore saved states from before entering historic mode
      if (savedBeforeHistoric) {
        const s = savedBeforeHistoric;
        // Metrics
        cbHumidity.checked = s.humidity;
        s.humidity ? state.selectedMetrics.add('humidity') : state.selectedMetrics.delete('humidity');
        const cbTemp = document.getElementById('cb-temperature');
        cbTemp.checked = s.temperature;
        s.temperature ? state.selectedMetrics.add('temperature') : state.selectedMetrics.delete('temperature');
        // Options
        cbThreshold.checked = s.threshold; state.showThreshold   = s.threshold;
        cbSeasons.checked   = s.seasons;   state.showSeasonLines = s.seasons;
        // Loggers
        state.selectedLoggers.clear();
        s.loggers.forEach(id => state.selectedLoggers.add(id));
        document.getElementById('logger-checkboxes').querySelectorAll('input[type=checkbox]').forEach(cb => {
          cb.checked = state.selectedLoggers.has(cb.dataset.loggerId);
        });
        // Time mode
        state.timeMode      = s.timeMode;
        state.selectedYear  = s.selectedYear;
        state.selectedMonth = s.selectedMonth;
        state.selectedWeek  = s.selectedWeek;
        state.selectedDay   = s.selectedDay;
        state.betweenStart  = s.betweenStart;
        state.betweenEnd    = s.betweenEnd;
        document.getElementById('time-mode').value = s.timeMode;
        ['between-inputs','year-input','season-input','month-input','week-input','day-input'].forEach(id =>
          document.getElementById(id).classList.add('hidden'));
        const modeInputMap = {between:'between-inputs', year:'year-input', season:'season-input', month:'month-input', week:'week-input', day:'day-input'};
        if (modeInputMap[s.timeMode]) document.getElementById(modeInputMap[s.timeMode]).classList.remove('hidden');
      }
      // Universal: show humidity label
      document.getElementById('humidity-label').style.display = '';
      // Restore wet bulb toggle if on line/periodic chart
      const _wbChartOk = state.chartType === 'line' || state.chartType === 'periodic';
      document.getElementById('wetbulb-adv-wrap').style.display = _wbChartOk ? '' : 'none';
      // Line-graph only: show options section
      if (state.chartType !== 'histogram') {
        document.getElementById('line-options-section').style.display = '';
        document.getElementById('line-options-divider').style.display = '';
      }
      // Always: clear series checkboxes
      document.getElementById('historic-series-checkboxes').style.display = 'none';
      document.getElementById('historic-series-checkboxes').innerHTML = '';
      state.selectedHistoricSeries = new Set();
      savedBeforeHistoric = null;
    }
    rebuildYearDropdown(); _zoomReset = true; updatePlot();
  });

  document.getElementById('download-btn').addEventListener('click', () => {
    const btn = document.getElementById('download-btn');
    const spinner = document.getElementById('dl-spinner');
    function dlStart() { btn.disabled = true; spinner.style.display = 'inline-block'; }
    function dlDone()  { btn.disabled = false; spinner.style.display = 'none'; }

    const dsSel = document.getElementById('dataset-select');
    const ds = dsSel.options[dsSel.selectedIndex].text;
    const chart = state.chartType === 'line' ? 'Line' : state.chartType === 'histogram' ? 'Histogram' : state.chartType === 'periodic' ? 'PeriodicAvg' : 'AdaptiveComfort';
    let rangeStr = 'AllTime';
    const m = dataset().meta;
    const fmtDate = ms => new Date(ms).toISOString().slice(0,10);
    switch (state.timeMode) {
      case 'between': rangeStr = `${fmtDate(state.betweenStart||m.dateRange.min)}_to_${fmtDate(state.betweenEnd||m.dateRange.max)}`; break;
      case 'year': rangeStr = `${state.selectedYear}`; break;
      case 'season': if (state.selectedSeason) { const sn = ['Kiangazi-JanFeb','Masika-MarMay','Kiangazi-JunOct','Vuli-NovDec'][state.selectedSeason.season]; rangeStr = `${state.selectedSeason.year}-${sn}`; } break;
      case 'month': if (state.selectedMonth) rangeStr = `${state.selectedMonth.year}-${String(state.selectedMonth.month).padStart(2,'0')}`; break;
      case 'week': if (state.selectedWeek) rangeStr = `${state.selectedWeek.year}-W${String(state.selectedWeek.week).padStart(2,'0')}`; break;
      case 'day': if (state.selectedDay) rangeStr = fmtDate(state.selectedDay); break;
    }
    let modelStr = '';
    if (state.chartType === 'comfort') {
      const modelSel = document.getElementById('comfort-model');
      modelStr = '_' + modelSel.options[modelSel.selectedIndex].text.replace(/\(Vellei et al\.\)/gi,'').replace(/[^a-zA-Z0-9%<>≤]/g,'').slice(0,20);
    }
    if (state.chartType === 'periodic') {
      modelStr = '_' + state.periodCycle + '_' + state.periodGroupBy;
    }
    let metricStr = '';
    if (state.chartType === 'line' || state.chartType === 'histogram' || state.chartType === 'periodic') {
      const metrics = [];
      if (state.selectedMetrics.has('temperature')) metrics.push('T');
      if (state.selectedMetrics.has('humidity')) metrics.push('RH');
      metricStr = '_' + metrics.join('+');
    }
    const slug = s => s.replace(/[^a-zA-Z0-9]+/g, '_').replace(/_+$/,'');
    // Sensor selection: name 1–2 selected sensors, count if a partial subset, omit if all selected
    let sensorStr = '';
    if (state.chartType === 'line' || state.chartType === 'histogram' || state.chartType === 'periodic') {
      const selIds = [...state.selectedLoggers];
      const total = m.loggers.length;
      if (selIds.length === 0) sensorStr = '_NoSensors';
      else if (selIds.length <= 2) sensorStr = '_' + selIds.map(id => slug(ln(id))).join('+');
      else if (selIds.length < total) sensorStr = `_${selIds.length}of${total}sensors`;
    } else if (state.chartType === 'comfort') {
      const selIds = [...state.selectedRoomLoggers];
      const total = (m.comfortLoggers || m.roomLoggers).length;
      if (selIds.length === 0) sensorStr = '_NoSensors';
      else if (selIds.length <= 2) sensorStr = '_' + selIds.map(id => slug(ln(id))).join('+');
      else if (selIds.length < total) sensorStr = `_${selIds.length}of${total}sensors`;
    }
    // Local-time timestamp makes every filename unique - prevents browser appending " (2)", " (3)" etc.
    const _n = new Date(), _p = n => String(n).padStart(2,'0');
    const ts = `${_n.getFullYear()}${_p(_n.getMonth()+1)}${_p(_n.getDate())}_${_p(_n.getHours())}${_p(_n.getMinutes())}`;
    const filename = `ARC_${slug(ds)}_${chart}${metricStr}${modelStr}${sensorStr}_${rangeStr}_${ts}`;
    const chartEl = document.getElementById('chart');
    const sm = window.innerWidth < 680;
    const W = chartEl.offsetWidth;
    const H = chartEl.offsetHeight;
    const scale = 3;
    dlStart();
    // Shared: parse SVG data URL → string
    function parseSVGDataUrl(svgDataUrl) {
      const b64tag = 'data:image/svg+xml;base64,';
      if (svgDataUrl.startsWith(b64tag)) return atob(svgDataUrl.slice(b64tag.length));
      return decodeURIComponent(svgDataUrl.slice(svgDataUrl.indexOf(',') + 1));
    }
    // Shared: inject title text into SVG (for line graph which avoids relayout)
    function injectSVGTitle(doc, svgW) {
      const infolayer = doc.querySelector('.infolayer');
      const ns = 'http://www.w3.org/2000/svg';
      const marginT = (_currentLayout.margin && _currentLayout.margin.t) || 50;
      const fontSize = sm ? 12 : 14;
      function makeTxt(fill, stroke, sw) {
        const t = doc.createElementNS(ns, 'text');
        t.setAttribute('x', String(svgW / 2));
        t.setAttribute('y', String(marginT / 2));
        t.setAttribute('text-anchor', 'middle');
        t.setAttribute('dominant-baseline', 'middle');
        t.setAttribute('font-family', 'Ubuntu, sans-serif');
        t.setAttribute('font-size', String(fontSize));
        t.setAttribute('font-weight', 'bold');
        t.setAttribute('fill', fill);
        if (stroke) { t.setAttribute('stroke', stroke); t.setAttribute('stroke-width', String(sw)); t.setAttribute('stroke-linejoin', 'round'); }
        t.textContent = _currentTitle;
        return t;
      }
      const g = doc.createElementNS(ns, 'g');
      g.appendChild(makeTxt('white', 'white', 5));
      g.appendChild(makeTxt('#222', null, 0));
      (infolayer || doc.documentElement).appendChild(g);
    }
    // Shared: append grey ID codes next to legend items in an exported SVG doc.
    // If the ID is already embedded in the text (from a prior restyle), it splits
    // at that point rather than duplicating it.
    function injectLegendIDCodes(doc) {
      const chartEl = document.getElementById('chart');
      const plotData = (chartEl && chartEl.data) ? chartEl.data : [];
      const legendTraces = plotData.filter(t => t.showlegend !== false);
      const ns = 'http://www.w3.org/2000/svg';
      doc.querySelectorAll('.legendtext').forEach((textEl, idx) => {
        const trace = legendTraces[idx];
        if (!trace || !trace.meta || !trace.meta.loggerId) return;
        const lid = trace.meta.loggerId;
        if (isOpenMeteo(lid) || lid === 'govee' || lid.startsWith('climate-')) return;
        const suffix = ' \u00B7 ' + lid;
        const rawText = textEl.textContent;
        const splitAt = rawText.indexOf(suffix);
        const baseName = splitAt >= 0 ? rawText.slice(0, splitAt) : rawText;
        while (textEl.firstChild) textEl.removeChild(textEl.firstChild);
        const t1 = doc.createElementNS(ns, 'tspan');
        t1.textContent = baseName;
        textEl.appendChild(t1);
        const t2 = doc.createElementNS(ns, 'tspan');
        t2.setAttribute('fill', '#aaaaaa');
        t2.setAttribute('font-size', '0.85em');
        t2.textContent = suffix;
        textEl.appendChild(t2);
      });
    }
    // Inject per-logger ext source labels below each comfort legend item in PNG SVG
    function injectComfortLegendSources(doc, loggerSourceMap) {
      if (!loggerSourceMap || !Object.keys(loggerSourceMap).length) return;
      const chartEl = document.getElementById('chart');
      const plotData = (chartEl && chartEl.data) ? chartEl.data : [];
      const legendTraces = plotData.filter(t => t.showlegend !== false);
      const ns = 'http://www.w3.org/2000/svg';
      doc.querySelectorAll('.legendtext').forEach((textEl, idx) => {
        const trace = legendTraces[idx];
        if (!trace || !trace.meta || !trace.meta.loggerId) return;
        const lid = trace.meta.loggerId;
        const srcText = loggerSourceMap[lid];
        if (!srcText) return;
        // Add a second line below the legend text showing the ext source
        const sub = doc.createElementNS(ns, 'tspan');
        sub.setAttribute('x', textEl.getAttribute('x') || '0');
        sub.setAttribute('dy', '1.15em');
        sub.setAttribute('fill', '#999999');
        sub.setAttribute('font-size', '0.7em');
        sub.textContent = 'ext: ' + srcText;
        textEl.appendChild(sub);
      });
    }
    // Shared: finish canvas → PNG download
    function canvasToPNG(canvas) {
      canvas.toBlob(blob => {
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl; a.download = filename + '.png';
        document.body.appendChild(a); a.click();
        document.body.removeChild(a); URL.revokeObjectURL(blobUrl);
        dlDone();
      }, 'image/png');
    }

    setTimeout(() => {
    if (state.chartType === 'line' || state.chartType === 'periodic') {
      // No relayout for line/periodic graph - inject title + watermark directly into SVG.
      Plotly.toImage('chart', {format: 'svg', width: W, height: H}).then(svgDataUrl => {
        const doc = new DOMParser().parseFromString(parseSVGDataUrl(svgDataUrl), 'image/svg+xml');
        injectSVGTitle(doc, W);
        injectLegendIDCodes(doc);
        unlockLegendScroll(doc.documentElement);
        // Measure legend bottom; expand SVG height if legend overflows
        const watermarkPad = 40; // space for watermark text below legend
        let finalH = H;
        const legend = doc.querySelector('.legend');
        if (legend) {
          const items = Array.from(legend.querySelectorAll('.traces'));
          if (items.length) {
            const lastItem = items[items.length - 1];
            // Walk up transforms to get absolute Y of last item
            let absY = 0;
            let el = lastItem;
            while (el && el !== doc.documentElement) {
              const m = (el.getAttribute && el.getAttribute('transform') || '').match(/translate\(\s*([-\d.]+)[\s,]+([-\d.]+)/);
              if (m) absY += parseFloat(m[2]);
              el = el.parentNode;
            }
            const legendBottom = absY + 20; // ~20px for item height
            const needed = legendBottom + watermarkPad;
            if (needed > H) {
              finalH = needed;
              const svgRoot = doc.documentElement;
              svgRoot.setAttribute('height', String(finalH));
              const vb = svgRoot.getAttribute('viewBox');
              if (vb) {
                const parts = vb.split(/[\s,]+/);
                if (parts.length === 4) {
                  parts[3] = String(finalH);
                  svgRoot.setAttribute('viewBox', parts.join(' '));
                }
              }
            }
          }
        }
        injectSVGWatermark(doc, W, finalH, 1.0);
        return svgToCanvas(new XMLSerializer().serializeToString(doc), W, finalH, scale);
      }).then(canvasToPNG).catch(dlDone);
    } else {
      // Histogram / adaptive comfort: add title via relayout, capture as SVG,
      // inject watermark into SVG DOM, render to canvas, restore.
      const isComfort = state.chartType === 'comfort';
      const pngTopMargin = isComfort ? (sm ? 36 : 60) : (sm ? 55 : 85);
      const origAnnotations = _currentLayout.annotations || [];
      const origImages = _currentLayout.images || [];
      const origMarginT = (_currentLayout.margin && _currentLayout.margin.t) || 50;
      // For comfort chart: temporarily embed IDs into trace names so Plotly
      // computes proper horizontal legend spacing before we capture the SVG.
      const liveData = chartEl.data || [];
      const comfortIdxs = [], comfortOrigNames = [], comfortNewNames = [];
      if (isComfort) {
        liveData.forEach((trace, i) => {
          if (trace.showlegend && trace.meta && trace.meta.loggerId) {
            const lid = trace.meta.loggerId;
            if (!isOpenMeteo(lid) && lid !== 'govee' && !lid.startsWith('climate-')) {
              comfortIdxs.push(i);
              comfortOrigNames.push(trace.name);
              comfortNewNames.push(trace.name + ' \u00B7 ' + lid);
            }
          }
        });
      }
      (isComfort && comfortIdxs.length > 0
        ? Plotly.restyle('chart', {name: comfortNewNames}, comfortIdxs)
        : Promise.resolve()
      ).then(() => {
        const relayoutOpts = {
          'title.text': `<b>${_currentTitle}</b>`,
          'title.font.size': sm ? 12 : 14,
          'margin.t': pngTopMargin,
        };
        // Switch comfort legend to vertical for PNG so per-item source labels fit
        if (isComfort) {
          relayoutOpts['legend.orientation'] = 'v';
          relayoutOpts['legend.x'] = 1.12;
          relayoutOpts['legend.y'] = 1;
          relayoutOpts['legend.xanchor'] = 'left';
          relayoutOpts['legend.yanchor'] = 'top';
          relayoutOpts['margin.r'] = 280;
          // Strip running mean sources from annotation for PNG (shown per-legend-item instead)
          const pngAnnotations = (origAnnotations || []).map(a => {
            if (!a.text) return a;
            // Remove everything from the running mean source lines onward
            const cleaned = a.text.replace(/<br>Running mean source.*$/s, '');
            return {...a, text: cleaned};
          });
          relayoutOpts['annotations'] = pngAnnotations;
        }
        return Plotly.relayout('chart', relayoutOpts);
      }).then(() => {
        return Plotly.toImage('chart', {format: 'svg', width: W, height: H});
      }).then(svgDataUrl => {
        // Restore all layout changes in one call
        const restoreOpts = {
          'title.text': '', 'margin.t': origMarginT,
          images: origImages, annotations: origAnnotations,
        };
        if (isComfort) {
          restoreOpts['legend.orientation'] = 'h';
          restoreOpts['legend.x'] = 0.5;
          restoreOpts['legend.y'] = -0.22;
          restoreOpts['legend.xanchor'] = 'center';
          restoreOpts['legend.yanchor'] = 'auto';
          restoreOpts['margin.r'] = sm ? 8 : 20;
        }
        Plotly.relayout('chart', restoreOpts).then(() => unlockLegendScroll(chartEl));
        if (isComfort && comfortIdxs.length > 0) {
          Plotly.restyle('chart', {name: comfortOrigNames}, comfortIdxs);
        }
        const doc = new DOMParser().parseFromString(parseSVGDataUrl(svgDataUrl), 'image/svg+xml');
        injectSVGWatermark(doc, W, H, isComfort ? 0.8 : 1.0);
        injectLegendIDCodes(doc);
        if (isComfort) injectComfortLegendSources(doc, _comfortLoggerSources);
        if (!isComfort) unlockLegendScroll(doc.documentElement);
        return svgToCanvas(new XMLSerializer().serializeToString(doc), W, H, scale);
      }).then(canvasToPNG).catch(dlDone);
    }
    }, 0);
  });

  const toggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  function closeSidebar() { sidebar.classList.remove('open'); backdrop.classList.remove('open'); }
  toggle.addEventListener('click', () => {
    const isOpen = sidebar.classList.toggle('open');
    backdrop.classList.toggle('open', isOpen);
  });
  backdrop.addEventListener('click', closeSidebar);
  window.addEventListener('resize', () => {
    if (window.innerWidth > 680) closeSidebar();
    Plotly.relayout('chart', {autosize: true}).then(positionComfortOverlays);
  });
  // On orientation change: snap viewport back to scale 1, then resize chart.
  // iOS fires orientationchange before the resize event, so we handle it explicitly.
  window.addEventListener('orientationchange', () => {
    const m = document.querySelector('meta[name=viewport]');
    if (m) { const c = m.content; m.content = c + ',maximum-scale=1'; requestAnimationFrame(() => { m.content = c; }); }
    setTimeout(() => {
      if (window.innerWidth > 680) closeSidebar();
      Plotly.relayout('chart', {autosize: true}).then(positionComfortOverlays);
    }, 300);
  });
}

// ── Time range ────────────────────────────────────────────────────────────────
function getTimeRange() {
  let {min, max} = dataset().meta.dateRange;
  // Expand range when historic mode is active
  if (HISTORIC && state.historicMode) {
    HISTORIC.series.forEach(s => {
      const sMin = new Date(s.timestamps[0]).getTime();
      const sMax = new Date(s.timestamps[s.timestamps.length-1]).getTime();
      if (sMin < min) min = sMin;
      if (sMax > max) max = sMax;
    });
  }
  switch (state.timeMode) {
    case 'all':     return {start: min, end: max};
    case 'between': return {start: state.betweenStart || min, end: state.betweenEnd || max};
    case 'year': {
      const y = state.selectedYear; if (!y) return {start: min, end: max};
      return {start: Date.UTC(y, 0, 1), end: Date.UTC(y, 11, 31, 23, 59, 59, 999)};
    }
    case 'season': {
      if (!state.selectedSeason) return {start: min, end: max};
      const {year: y, season: si} = state.selectedSeason;
      const sm = [[0,1],[2,4],[5,9],[10,11]][si];
      return {start: Date.UTC(y, sm[0], 1), end: Date.UTC(y, sm[1]+1, 0, 23, 59, 59, 999)};
    }
    case 'month': {
      if (!state.selectedMonth) return {start: min, end: max};
      const {year: y, month: mo} = state.selectedMonth;
      return {start: Date.UTC(y, mo-1, 1), end: Date.UTC(y, mo, 0, 23, 59, 59, 999)};
    }
    case 'week': {
      if (!state.selectedWeek) return {start: min, end: max};
      const {year: y, week: w} = state.selectedWeek;
      const jan4 = new Date(Date.UTC(y, 0, 4));
      const dow = jan4.getUTCDay() || 7;
      const weekStart = jan4.getTime() - (dow-1)*86400000 + (w-1)*7*86400000;
      return {start: weekStart, end: weekStart + 7*86400000 - 1};
    }
    case 'day': {
      const ts = state.selectedDay; if (!ts) return {start: min, end: max};
      return {start: ts, end: ts + 86400000 - 1};
    }
    default: return {start: min, end: max};
  }
}

// Binary search for indices of timestamps within [startMs, endMs]. Returns null if none.
function tsRange(ts, startMs, endMs) {
  let lo = 0, hi = ts.length - 1;
  while (lo < hi) { const mid = (lo+hi)>>1; ts[mid] < startMs ? lo = mid+1 : hi = mid; }
  const s = lo;
  lo = 0; hi = ts.length - 1;
  while (lo < hi) { const mid = (lo+hi+1)>>1; ts[mid] > endMs ? hi = mid-1 : lo = mid; }
  return (s > lo || ts[s] > endMs || ts[lo] < startMs) ? null : {s, e: lo};
}

function filterSeries(series, startMs, endMs) {
  const ts = series.timestamps;
  if (!ts || ts.length === 0) return null;
  const r = tsRange(ts, startMs, endMs);
  if (!r) return null;
  const {s, e} = r;
  return {
    timestamps:  ts.slice(s, e+1),
    temperature: series.temperature.slice(s, e+1),
    humidity:    series.humidity.slice(s, e+1),
    extTemp:     series.extTemp ? series.extTemp.slice(s, e+1) : null,
  };
}

// ── Anomalous data filter ─────────────────────────────────────────────────────
function applyAnomalousFilter(filtered, loggerId) {
  if (!state.excludeAnomalous) return filtered;
  const m = dataset().meta;
  const ranges = m.anomalousRanges;
  if (!ranges || !ranges[loggerId]) return filtered;
  const rng = ranges[loggerId];
  const ts = [], temp = [], hum = [];
  const extTemp = filtered.extTemp ? [] : null;
  for (let i = 0; i < filtered.timestamps.length; i++) {
    const t = filtered.timestamps[i];
    let anomalous = false;
    if (rng.before && t < rng.before) anomalous = true;
    if (rng.after && t > rng.after) anomalous = true;
    if (!anomalous) {
      ts.push(t);
      temp.push(filtered.temperature[i]);
      hum.push(filtered.humidity[i]);
      if (extTemp) extTemp.push(filtered.extTemp[i]);
    }
  }
  if (ts.length === 0) return null;
  return { timestamps: ts, temperature: temp, humidity: hum, extTemp };
}

// ── Gap detection ─────────────────────────────────────────────────────────────
const GAP_MS = 12 * 3600 * 1000;
function buildGapArrays(timestamps, values) {
  const x = [], y = [];
  for (let i = 0; i < timestamps.length; i++) {
    if (i > 0 && timestamps[i] - timestamps[i-1] > GAP_MS) { x.push(null); y.push(null); }
    x.push(toEATString(timestamps[i])); y.push(values[i]);
  }
  return {x, y};
}

// ── Season lines ──────────────────────────────────────────────────────────────
const SEASONS = [
  {month:6,  day:1, name:'June Dry Season (Kiangazi)'},
  {month:11, day:1, name:'Short Rains (Vuli)'},
  {month:1,  day:1, name:'January Dry Season (Kiangazi)'},
  {month:3,  day:1, name:'Long Rains (Masika)'},
];
function getSeasonBoundaries(startMs, endMs) {
  const results = [];
  const sy = new Date(startMs).getFullYear(), ey = new Date(endMs).getFullYear();
  for (let y = sy-1; y <= ey+1; y++) {
    for (const s of SEASONS) {
      const ts = Date.UTC(y, s.month-1, s.day) + 3*3600000;
      if (ts >= startMs && ts <= endMs) results.push({ts, name: s.name});
    }
  }
  return results.sort((a, b) => a.ts - b.ts);
}

// ── Comfort model ─────────────────────────────────────────────────────────────
function getComfortParams() {
  const models = {
    default:  {m:0.31, c:17.3,  delta:3.0},
    rh_gt_60: {m:0.53, c:12.85, delta:2.84},
    rh_40_60: {m:0.53, c:14.16, delta:3.70},
    rh_le_40: {m:0.52, c:15.23, delta:4.40},
  };
  return models[state.comfortModel] || null;
}
function comfortSourceLabel(extSrcText) {
  const sel = document.getElementById('comfort-model');
  const parts = [];
  if (sel && state.comfortModel !== 'none') {
    parts.push(`Adaptive comfort: EN16798-1 · ${sel.options[sel.selectedIndex].text}`);
  }
  if (extSrcText) parts.push(extSrcText);
  return parts.join('<br>') || '';
}

// Returns grey "(OmniSense)" HTML suffix for Omnisense sensors, empty string otherwise.
function omniSuffix(source) {
  return source === 'Omnisense' ? '<span style="color:#aaa"> (OmniSense)</span>' : '';
}
function meteoSuffix(id) {
  return isOpenMeteo(id) ? '<span style="color:#aaa"> (Open-Meteo)</span>' : '';
}
function dsLabel() { const s = document.getElementById('dataset-select'); return s.options[s.selectedIndex].text; }
// Converts a UTC epoch ms value to an EAT local time string (YYYY-MM-DD HH:MM:SS).
// Plotly treats bare date strings as calendar-absolute (no browser-timezone conversion),
// so this ensures timestamps always display in EAT regardless of the viewer's browser timezone.
function toEATString(ms) {
  return new Date(ms + 3 * 3600 * 1000).toISOString().slice(0, 19).replace('T', ' ');
}

// ── Line graph ────────────────────────────────────────────────────────────────
function renderLineGraph() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [], shapes = [], annotations = [];
  let dataMinMs = Infinity, dataMaxMs = -Infinity;
  let yMin = Infinity, yMax = -Infinity;
  const lineSet = new Set(m.lineLoggers || m.loggers);
  const extSet = new Set(m.externalLoggers || []);

  const iterations = getCompareIterations();
  for (const iter of iterations) {
    const savedFilters = state.substratFilters;
    const savedCombine = state.substratCombine;
    state.substratFilters = iter.substratFilters;
    state.substratCombine = iter.substratCombine;
    const namePrefix = iter.setLabel ? '[' + iter.setLabel + '] ' : '';

    for (const loggerId of m.loggers) {
      const _mainSelected = iter.selectedLoggers.has(loggerId) && lineSet.has(loggerId);
      const _wbWanted = state.wetBulbEnabled && state.wetBulbLoggers.has(loggerId) && lineSet.has(loggerId) && state.selectedMetrics.has('temperature');
      if (!_mainSelected && !_wbWanted) continue;
      const series = dataset().series[loggerId];
      if (!series) continue;
      let filtered = filterSeries(series, start, end);
      if (!filtered) continue;
      filtered = applyAnomalousFilter(filtered, loggerId);
      if (!filtered) continue;

      const color = iter.colorMap[loggerId] || m.colors[loggerId];
      const isExtTT = extSet.has(loggerId) && m.loggerSources[loggerId] === 'TinyTag';
      const name = namePrefix + ln(loggerId) + (isExtTT ? ' <span style="color:#aaa">(TinyTag)</span>' : '');
      const source = m.loggerSources[loggerId] || '';
      const idLabel = (loggerId === 'govee' || isOpenMeteo(loggerId)) ? '' : ` · ID: ${loggerId}`;
      const freqLabel = state.historicMode
        ? (isOpenMeteo(loggerId) ? ' <span style="color:#aaa">(hourly avg.)</span>'
          : source === 'TinyTag' ? ' <span style="color:#aaa">(hourly avg.)</span>'
          : source === 'Omnisense' ? ' <span style="color:#aaa">(5-min avg.)</span>'
          : '') : '';
      const lgGroup = iter.setLabel ? 'compare_s' + iter.setIndex : loggerId;
      const _wbAnnotation = (_wbWanted && _mainSelected) ? ' <span style="color:#aaa">+ ' + t('wetBulbSuffix') + '</span>' : '';

      if (_mainSelected) {
        // Track actual data bounds
        if (filtered.timestamps.length) {
          const first = filtered.timestamps[0], last = filtered.timestamps[filtered.timestamps.length - 1];
          if (first < dataMinMs) dataMinMs = first;
          if (last > dataMaxMs) dataMaxMs = last;
        }
        let firstMetric = true;
        for (const metric of ['temperature','humidity']) {
          if (!state.selectedMetrics.has(metric)) continue;
          const {x, y} = buildGapArrays(filtered.timestamps, filtered[metric]);
          for (const v of y) { if (v != null) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; } }
          const unit = metric === 'temperature' ? '°C' : '%RH';
          traces.push({x, y, type:'scatter', mode:'lines', name: name + meteoSuffix(loggerId) + omniSuffix(source) + freqLabel + (firstMetric ? _wbAnnotation : ''), line:{color, width:1.4},
            opacity:0.35, connectgaps:false, legendgroup:lgGroup, showlegend:(!iter.setLabel && firstMetric), meta:{loggerId},
            hovertemplate:`${name}<br>%{x|%d/%m/%Y %H:%M}<br>${metric==='temperature'?t('tempOnly'):t('humidOnly')}: %{y:.1f}${unit}<br>${t('source')}: ${source}${idLabel}<extra></extra>`});
          firstMetric = false;
        }
      }

      // Wet bulb trace (dashed, same colour) — renders even if main logger is deselected
      if (_wbWanted) {
        const wbY = filtered.timestamps.map((_, i) => {
          const T = filtered.temperature[i], RH = filtered.humidity[i];
          if (T == null || RH == null) return null;
          const _wb = stullWetBulb(T, RH);
          return _wb != null ? +_wb.toFixed(2) : null;
        });
        const {x: wbX, y: wbYArr} = buildGapArrays(filtered.timestamps, wbY);
        for (const v of wbYArr) { if (v != null) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; } }
        // Ensure data bounds are set even when parent logger is deselected
        if (filtered.timestamps.length) {
          const first = filtered.timestamps[0], last = filtered.timestamps[filtered.timestamps.length - 1];
          if (first < dataMinMs) dataMinMs = first;
          if (last > dataMaxMs) dataMaxMs = last;
        }
        const wbName = name + ' ' + t('wetBulbSuffix');
        const _dispName = ln(loggerId);
        const _srcLabel = (source ? ' · ' + source : '') + idLabel;
        // T and RH always come from the same series; show one source line.
        // If they ever differ, fall back to two separate lines.
        const _tSrc = _dispName + _srcLabel, _rhSrc = _dispName + _srcLabel;
        const _srcHover = _tSrc === _rhSrc
          ? `${t('source')}: ${_tSrc}`
          : `${t('tempOnly')}: ${_tSrc}<br>${t('humidOnly')}: ${_rhSrc}`;
        traces.push({x: wbX, y: wbYArr, type:'scatter', mode:'lines',
          name: wbName, line:{color, width:1.4, dash:'dash'},
          opacity:0.35, connectgaps:false, legendgroup: _mainSelected ? lgGroup : lgGroup + '_wb', showlegend: !_mainSelected && !iter.setLabel, meta:{loggerId},
          hovertemplate:`${wbName}<br>%{x|%d/%m/%Y %H:%M}<br>${t('wetBulbHover')}: %{y:.1f}°C<br>${_srcHover}<extra></extra>`});
      }
    }

    // Cross-dataset loggers (other buildings in compare mode)
    if (iter.selectedCrossLoggers) {
      for (const otherKey of Object.keys(iter.selectedCrossLoggers)) {
        const crossSet = iter.selectedCrossLoggers[otherKey];
        if (!crossSet || crossSet.size === 0) continue;
        const otherDs = ALL_DATA[otherKey];
        if (!otherDs) continue;
        const otherM = otherDs.meta;
        const otherName = otherKey === 'house5' ? t('house5') : otherKey === 'schoolteacher' ? t('schoolteacher') : otherKey;
        for (const lid of crossSet) {
          const series = otherDs.series[lid];
          if (!series) continue;
          let filtered = filterSeries(series, start, end);
          if (!filtered) continue;
          if (filtered.timestamps.length) {
            const first = filtered.timestamps[0], last = filtered.timestamps[filtered.timestamps.length - 1];
            if (first < dataMinMs) dataMinMs = first;
            if (last > dataMaxMs) dataMaxMs = last;
          }
          const origColor = otherM.colors[lid] || '#999';
          // In compare mode, use set colour; otherwise use logger's own colour
          const color = iter.baseColor || origColor;
          const dispName = lnFrom(otherM, lid);
          const crossPrefix = namePrefix + otherName + ' \u2013 ';
          const source = otherM.loggerSources[lid] || '';
          const lgGroup = iter.setLabel ? 'compare_s' + iter.setIndex : 'cross_' + otherKey + '_' + lid;
          for (const metric of ['temperature','humidity']) {
            if (!state.selectedMetrics.has(metric)) continue;
            const {x, y} = buildGapArrays(filtered.timestamps, filtered[metric]);
            for (const v of y) { if (v != null) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; } }
            const unit = metric === 'temperature' ? '\u00b0C' : '%RH';
            traces.push({x, y, type:'scatter', mode:'lines',
              name: crossPrefix + dispName + (source ? ' <span style="color:#aaa">(' + source + ')</span>' : ''),
              line:{color, width:1.4}, opacity:0.35, connectgaps:false,
              legendgroup:lgGroup, showlegend:!iter.setLabel,
              hovertemplate:`${crossPrefix}${dispName}<br>%{x|%d/%m/%Y %H:%M}<br>${metric==='temperature'?t('tempOnly'):t('humidOnly')}: %{y:.1f}${unit}<br>${t('source')}: ${source}<extra></extra>`});
          }
        }
      }
    }

    // In compare mode, add a single legend entry per set
    if (iter.setLabel) {
      traces.push({x:[null], y:[null], type:'scatter', mode:'lines',
        name: iter.legendName, line:{color: iter.baseColor, width:3},
        legendgroup:'compare_s' + iter.setIndex, showlegend:true, hoverinfo:'skip'});
    }

    state.substratFilters = savedFilters;
    state.substratCombine = savedCombine;
  }

  // Fall back to time filter range if no data traces
  const _lineHasData = dataMinMs !== Infinity;
  if (dataMinMs === Infinity) { dataMinMs = start; dataMaxMs = end; }

  // Expand bounds for historic/climate data before drawing threshold/season lines
  const showingHistoric = HISTORIC && state.historicMode;
  const historicFiltered = [];
  if (showingHistoric) {
    HISTORIC.series.forEach(s => {
      const allDates = s.timestamps.map(t => new Date(t));
      const idx = [];
      for (let i = 0; i < allDates.length; i++) {
        const ms = allDates[i].getTime();
        if (ms >= start && ms <= end) idx.push(i);
      }
      const fx = idx.map(i => allDates[i]);
      const fy = idx.map(i => s.values[i]);
      if (fx.length > 0) {
        const fMin = fx[0].getTime(), fMax = fx[fx.length-1].getTime();
        if (fMin < dataMinMs) dataMinMs = fMin;
        if (fMax > dataMaxMs) dataMaxMs = fMax;
      }
      historicFiltered.push({id: s.id, label: s.label, x: fx, y: fy});
    });
  }

  // Threshold and season lines span the full visible range
  const rangeMinMs = state.timeMode === 'all' ? dataMinMs : start;
  const rangeMaxMs = state.timeMode === 'all' ? dataMaxMs : end;
  if (state.showThreshold) {
    shapes.push({type:'rect', xref:'x', yref:'y',
      x0:toEATString(rangeMinMs), x1:toEATString(rangeMaxMs), y0:32, y1:35,
      fillcolor:'rgba(231,76,60,0.12)', line:{width:0}});
    traces.push({x:[null], y:[null], type:'scatter', mode:'lines',
      name:'32–35°C Threshold', line:{color:'rgba(231,76,60,0.35)', width:8},
      hoverinfo:'skip', showlegend:true});
  }

  if (state.showSeasonLines) {
    const seasons = getSeasonBoundaries(rangeMinMs, rangeMaxMs);
    seasons.forEach(s => {
      shapes.push({type:'line', xref:'x', yref:'paper', x0:toEATString(s.ts), x1:toEATString(s.ts), y0:0, y1:1, line:{color:'#bbb', width:1, dash:'dot'}});
      annotations.push({x:toEATString(s.ts), xref:'x', yref:'paper', y:1.01, yanchor:'bottom', xanchor:'left', text:s.name, showarrow:false, font:{size:9, color:'#888'}, textangle:-30});
    });
  }

  // Climate data traces (ERA5 historic + SSP projections)
  if (showingHistoric) {
    // Narrow view (year/month/week/day or between ≤1 year): expand each annual point to span
    // Jan 1→Dec 31 so a single-year zoom shows a horizontal line instead of an invisible dot.
    // Wide view (all time, multi-year between): use original single-point-per-year connected line.
    const ONE_YEAR_MS = 365.25 * 24 * 3600 * 1000;
    const narrowView = state.timeMode === 'year' || state.timeMode === 'season' || state.timeMode === 'month' ||
      state.timeMode === 'week' || state.timeMode === 'day' ||
      (state.timeMode === 'between' && (end - start) <= ONE_YEAR_MS);
    historicFiltered.forEach(s => {
      if (s.x.length === 0) return;
      if (!state.selectedHistoricSeries.has(s.id)) return;
      for (const v of s.y) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; }
      const color = CLIMATE_COLORS[s.id] || '#999';
      const climLabel = s.label + ' <span style="color:#aaa">(annual avg.)</span>';
      let px, py, traceMode;
      if (narrowView) {
        px = []; py = [];
        for (let i = 0; i < s.x.length; i++) {
          const yr = s.x[i].getUTCFullYear();
          px.push(new Date(Date.UTC(yr, 0, 1)));
          px.push(new Date(Date.UTC(yr, 11, 31)));
          py.push(s.y[i]); py.push(s.y[i]);
        }
        traceMode = 'lines';
      } else {
        px = s.x; py = s.y; traceMode = 'lines+markers';
      }
      traces.push({x:px, y:py, type:'scatter', mode:traceMode,
        name:climLabel, line:{color, width:2},
        ...(traceMode === 'lines+markers' ? {marker:{size:3}} : {}),
        opacity:0.85, legendgroup:'climate-'+s.id, meta:{loggerId:'climate-'+s.id},
        hovertemplate:`${s.label}<br>%{x|%Y}<br>Temp: %{y:.2f}°C<extra></extra>`});
    });
  }

  // Y-axis: pad to nearest 1.5°C
  const yPad = 1.5;
  const yLo = yMin !== Infinity ? Math.floor((yMin - yPad) / yPad) * yPad : undefined;
  const yHi = yMax !== -Infinity ? Math.ceil((yMax + yPad) / yPad) * yPad : undefined;

  const hasTemp = state.selectedMetrics.has('temperature');
  const hasHum  = state.selectedMetrics.has('humidity');
  const yTitle  = hasTemp && hasHum ? t('tempHumidAxis') : hasTemp ? t('tempAxis') : t('humidAxis');
  const ySuffix = hasTemp && hasHum ? '' : hasTemp ? '\u00b0C' : '%RH';
  const chartTitle = hasTemp && hasHum ? t('tempAndHumid') : hasTemp ? t('tempOnly') : t('humidOnly');
  const dsl = dsLabel();
  const sm = window.innerWidth < 680;

  const plotTitle = state.historicMode
    ? 'Dar es Salaam \u2013 Historic and Projected Temperatures'
    : `${dsl} \u2013 ${chartTitle}`;
  const barTitle = plotTitle.replace(/&amp;/g, '&');
  return {traces, layout: {
    autosize:true, font:{family:'Ubuntu, sans-serif'}, margin:{l:sm?45:65, r:sm?8:20, t:state.showSeasonLines?(sm?70:85):(sm?6:10), b:sm?40:60},
    xaxis:{title:t('dateTime') + ' <i><span style="color:#aaa">(EAT, UTC+03:00)</span></i>', type:'date', showgrid:true, gridcolor:'#eee', range: state.timeMode === 'all' ? [toEATString(dataMinMs), toEATString(dataMaxMs)] : [toEATString(start), toEATString(end)],
      nticks:20, tickangle:-30, automargin:true},
    yaxis:{title:yTitle, ticksuffix:ySuffix, showgrid:true, gridcolor:'#eee', range: yLo !== undefined ? [yLo, yHi] : undefined},
    legend:{orientation:'v', x:1.01, y:1, xanchor:'left', ...legendStyle(state.selectedLoggers.size), itemclick:false, itemdoubleclick:false},
    plot_bgcolor:'white', paper_bgcolor:'white', shapes,
    annotations: [...annotations, ...(isFinite(dataMinMs) ? [dateRangeAnnotation(dataMinMs, dataMaxMs, true)] : [])],
    hovermode:'closest', hoverlabel:{font:{family:'Ubuntu, sans-serif'}},
  }, title: barTitle, _noData: !_lineHasData && !showingHistoric};
}

// ── Date-range annotation (visible in PNG exports) ────────────────────────────
// Returns actual [minMs, maxMs] of timestamps within [startMs, endMs], or null if none.
function actualDataRange(timestamps, startMs, endMs) {
  let lo = -1, hi = -1;
  for (let i = 0; i < timestamps.length; i++) { if (timestamps[i] >= startMs) { lo = i; break; } }
  for (let i = timestamps.length - 1; i >= 0; i--) { if (timestamps[i] <= endMs) { hi = i; break; } }
  if (lo < 0 || hi < lo) return null;
  return [timestamps[lo], timestamps[hi]];
}
function fmtDateEAT(ms, isStart) {
  // Shift to EAT (UTC+3) so UTC date/hour reflect local time
  let d = new Date(ms + 3 * 3600 * 1000);
  const hour = d.getUTCHours();
  // If a start reading falls in the last hour of the day, attribute it to the next day
  if (isStart && hour >= 23) d = new Date(d.getTime() + 24 * 3600 * 1000);
  // If an end reading falls in the first hour of the day, attribute it to the previous day
  if (!isStart && hour < 1) d = new Date(d.getTime() - 24 * 3600 * 1000);
  return `${String(d.getUTCDate()).padStart(2,'0')}/${String(d.getUTCMonth()+1).padStart(2,'0')}/${d.getUTCFullYear()}`;
}
function dateRangeAnnotation(actualStartMs, actualEndMs, atTop, extraLine) {
  let text = `${t('dataRangesFrom')} ${fmtDateEAT(actualStartMs, true)} ${t('dataRangesTo')} ${fmtDateEAT(actualEndMs, false)}`;
  if (extraLine) text += `<br>${extraLine}`;
  return {
    xref: 'paper', yref: 'paper',
    x: 1, y: atTop ? 1 : 0,
    xanchor: 'right', yanchor: atTop ? 'top' : 'bottom',
    text,
    showarrow: false,
    font: {size: 10, color: '#888'},
    bgcolor: 'rgba(255,255,255,0.75)',
    borderpad: 3,
  };
}

// ── Position running mean info icon next to x-axis title ─────────────────────
function positionComfortOverlays() {
  const chartEl = document.getElementById('chart');
  const rmIcon = document.getElementById('rm-xaxis-info-icon');
  if (state.chartType !== 'comfort') { rmIcon.style.display = 'none'; return; }
  // Use Plotly's internal layout to find the x-axis title position
  const fl = chartEl._fullLayout;
  if (fl && fl.xaxis && fl.xaxis._offset !== undefined) {
    const cr = chartEl.getBoundingClientRect();
    // _offset is the left edge of the axis, _length is its width
    // Find the actual x-axis title text element in the SVG
    const allText = chartEl.querySelectorAll('text');
    let xTitleText = null;
    const axisTitle = t('runningMeanAxis');
    for (const txt of allText) {
      if (txt.textContent && txt.textContent.includes('°C') && txt.getAttribute('data-unformatted') === axisTitle) {
        xTitleText = txt; break;
      }
    }
    // Fallback: find any text matching the axis title
    if (!xTitleText) {
      for (const txt of allText) {
        if (txt.textContent === axisTitle || (txt.getAttribute('data-unformatted') || '') === axisTitle) {
          xTitleText = txt; break;
        }
      }
    }
    if (xTitleText) {
      const xr = xTitleText.getBoundingClientRect();
      rmIcon.style.display = '';
      rmIcon.style.left = (xr.right + 4) + 'px';
      rmIcon.style.top = (xr.top + (xr.height - 14) / 2) + 'px';
    } else {
      rmIcon.style.display = 'none';
    }
  } else {
    rmIcon.style.display = 'none';
  }

  // Handled by CSS: #chart.comfort-mode .annotation:hover { opacity: 0.08 }
}

// ── Histogram ────────────────────────────────────────────────────────────────
function renderHistogram() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [];
  let globalMin = Infinity, globalMax = -Infinity;
  let actualStartMs = Infinity, actualEndMs = -Infinity;
  const histSet = new Set(m.histogramLoggers || m.loggers);

  const iterations = getCompareIterations();
  for (const iter of iterations) {
    const savedFilters = state.substratFilters;
    const savedCombine = state.substratCombine;
    state.substratFilters = iter.substratFilters;
    state.substratCombine = iter.substratCombine;
    const namePrefix = iter.setLabel ? '[' + iter.setLabel + '] ' : '';

    for (const loggerId of m.loggers) {
      if (!iter.selectedLoggers.has(loggerId)) continue;
      if (!histSet.has(loggerId)) continue;
      const series = dataset().series[loggerId];
      if (!series) continue;
      let filtered = filterSeries(series, start, end);
      if (!filtered) continue;
      filtered = applyAnomalousFilter(filtered, loggerId);
      if (!filtered) continue;
      filtered = applySubstratFilter(filtered);
      if (!filtered) continue;
      const range = actualDataRange(series.timestamps, start, end);
      if (range) { actualStartMs = Math.min(actualStartMs, range[0]); actualEndMs = Math.max(actualEndMs, range[1]); }

      const color = iter.colorMap[loggerId] || m.colors[loggerId];
      const source = m.loggerSources[loggerId] || '';
      const isExtTT = (m.externalLoggers || []).includes(loggerId) && source === 'TinyTag';
      const name = namePrefix + ln(loggerId) + (isExtTT ? ' <span style="color:#aaa">(TinyTag)</span>' : '');
      const lgGroup = iter.setLabel ? 'compare_s' + iter.setIndex : loggerId;
      let firstMetric = true;

      for (const metric of ['temperature', 'humidity']) {
        if (!state.selectedMetrics.has(metric)) continue;
        const values = filtered[metric].filter(v => v != null);
        if (values.length === 0) continue;
        for (const v of values) { if (v < globalMin) globalMin = v; if (v > globalMax) globalMax = v; }
        const unit = metric === 'temperature' ? '\u00b0C' : '%RH';
        traces.push({
          x: values,
          type: 'histogram',
          histnorm: 'probability',
          name: name + meteoSuffix(loggerId) + omniSuffix(source),
          xbins: {size: 1},
          marker: {color, opacity: state.histogramBarmode === 'overlay' ? 0.55 : 0.85},
          legendgroup: lgGroup,
          showlegend: (!iter.setLabel && firstMetric),
          meta: {loggerId, unit},
          hovertemplate: `${name}<br>%{x:.1f}${unit}: %{y:.1%} of readings<extra></extra>`,
        });
        firstMetric = false;
      }
    }

    // In compare mode, add a single legend entry per set
    if (iter.setLabel) {
      traces.push({x:[null], type:'histogram',
        name: iter.legendName, marker:{color: iter.baseColor},
        legendgroup:'compare_s' + iter.setIndex, showlegend:true, hoverinfo:'skip'});
    }

    state.substratFilters = savedFilters;
    state.substratCombine = savedCombine;
  }

  // Climate series traces (only when historic mode is active and temperature metric selected)
  if (HISTORIC && state.historicMode && state.selectedMetrics.has('temperature')) {
    HISTORIC.series.forEach(s => {
      if (!state.selectedHistoricSeries.has(s.id)) return;
      const values = s.values.filter(v => v != null);
      if (values.length === 0) return;
      for (const v of values) { if (v < globalMin) globalMin = v; if (v > globalMax) globalMax = v; }
      const color = CLIMATE_COLORS[s.id] || '#999';
      traces.push({
        x: values,
        type: 'histogram',
        histnorm: 'probability',
        name: s.label + ' (annual avg.)',
        xbins: {size: 1},
        marker: {color, opacity: state.histogramBarmode === 'overlay' ? 0.45 : 0.75, line: {width: 1.5, color}},
        legendgroup: 'climate-' + s.id,
        meta: {loggerId: 'climate-' + s.id},
        hovertemplate: `${s.label}<br>%{x:.1f}\u00b0C: %{y:.1%} of years<extra></extra>`,
      });
    });
  }

  const hasTemp = state.selectedMetrics.has('temperature');
  const hasHum  = state.selectedMetrics.has('humidity');
  const xTitle  = hasTemp && hasHum ? t('tempHumidAxis') : hasTemp ? t('tempAxis') : t('humidAxis');
  const chartTitle = hasTemp && hasHum ? t('tempAndHumidDist')
    : hasTemp ? t('tempDist') : t('humidDist');
  const dsl = dsLabel();
  const sm = window.innerWidth < 680;

  // Tick labels: stagger only when the x range exceeds 60 units (otherwise labels fit without stagger)
  const xRange = isFinite(globalMin) && isFinite(globalMax) ? globalMax - globalMin : 0;
  const useStagger = xRange > 60;
  const TICK_FONT = {size: 11, color: '#444'};

  const tickvals = [], ticktext = [], tickAnnotations = [];
  if (isFinite(globalMin) && isFinite(globalMax)) {
    for (let v = Math.floor(globalMin); v <= Math.ceil(globalMax); v++) {
      tickvals.push(v);
      if (useStagger && v % 2 !== 0) {
        // Odd values: blank built-in label + annotation slightly below even labels
        ticktext.push('');
        tickAnnotations.push({
          x: v, xref: 'x',
          y: -0.025, yref: 'paper',
          text: String(v),
          showarrow: false,
          font: TICK_FONT,
          xanchor: 'center', yanchor: 'top',
          textangle: 0,
          captureevents: false,
        });
      } else {
        ticktext.push(String(v));
      }
    }
  }

  // 32–35°C threshold range
  const shapes = [];
  if (state.showThreshold && hasTemp) {
    shapes.push({type:'rect', xref:'x', yref:'paper', x0:32, x1:35, y0:0, y1:1,
      fillcolor:'rgba(231,76,60,0.12)', line:{width:0}});
  }

  updateHistogramStats(start, end);

  const histAnnotations = [...tickAnnotations,
    ...(isFinite(actualStartMs) ? [dateRangeAnnotation(actualStartMs, actualEndMs, true)] : [])];
  return {traces, layout: {
    autosize:true, font:{family:'Ubuntu, sans-serif'}, margin:{l:sm?45:65, r:sm?8:20, t:sm?20:36, b:useStagger?(sm?80:85):(sm?60:70)},
    xaxis:{title:xTitle, showgrid:true, gridcolor:'#eee', tickangle:0,
      tickfont: TICK_FONT,
      tickmode: tickvals.length ? 'array' : undefined,
      tickvals: tickvals.length ? tickvals : undefined,
      ticktext: tickvals.length ? ticktext : undefined},
    yaxis:{title: state.histogramBarmode === 'overlay' ? t('proportionAxis') : t('sumAxis'), tickformat:'.0%', showgrid:true, gridcolor:'#eee'},
    barmode: state.histogramBarmode, shapes, annotations: histAnnotations,
    legend:{orientation:'v', x:1.01, y:1, xanchor:'left', ...legendStyle(state.selectedLoggers.size), itemclick:false, itemdoubleclick:false},
    plot_bgcolor:'white', paper_bgcolor:'white',
    hovermode:'closest',
    hoverlabel:{font:{family:'Ubuntu, sans-serif'}},
  }, title: (`${dsl} \u2013 ${chartTitle}`).replace(/&amp;/g, '&'), _noData: !isFinite(globalMin)};
}

// ── Shared stats helpers (used by both histogram and comfort stats) ───────────
function buildGapDropdown(ddId, wrapId, seriesInfo, allAvailableInfo, start, end, context) {
  const periods = findCompletePeriods(seriesInfo, start, end, allAvailableInfo);
  const hasAny = periods.primary.length > 0 || periods.secondary.length > 0 || periods.sourceGroups.length > 0;
  if (!hasAny) return;
  const dd = document.getElementById(ddId);
  dd.innerHTML = '';
  const ph = document.createElement('option');
  ph.value = ''; ph.textContent = 'Jump to a complete period\u2026'; ph.disabled = true; ph.selected = true;
  dd.appendChild(ph);
  if (periods.primary.length > 0) {
    const g1 = document.createElement('optgroup');
    g1.label = 'Complete for all selected loggers';
    periods.primary.forEach(p => { const o = document.createElement('option'); o.value = JSON.stringify(p); o.textContent = p.label; g1.appendChild(o); });
    dd.appendChild(g1);
  }
  if (periods.secondary.length > 0) {
    const g2 = document.createElement('optgroup');
    const gl = {year:'years',season:'seasons',month:'months',week:'weeks'}[state.timeMode] || 'periods';
    g2.label = `Other complete ${gl} (all loggers)`;
    periods.secondary.forEach(p => { const o = document.createElement('option'); o.value = JSON.stringify(p); o.textContent = p.label; g2.appendChild(o); });
    dd.appendChild(g2);
  }
  for (const sg of periods.sourceGroups) {
    if (sg.primary.length > 0) {
      const g = document.createElement('optgroup');
      g.label = `Complete for ${sg.source} loggers (${sg.count})`;
      sg.primary.forEach(p => { const o = document.createElement('option'); o.value = JSON.stringify(Object.assign({}, p, {sourceType: sg.source})); o.textContent = p.label; g.appendChild(o); });
      dd.appendChild(g);
    }
    if (sg.secondary.length > 0) {
      const g = document.createElement('optgroup');
      const gl = {year:'years',season:'seasons',month:'months',week:'weeks'}[state.timeMode] || 'periods';
      g.label = `Other ${gl} \u2013 ${sg.source} only`;
      sg.secondary.forEach(p => { const o = document.createElement('option'); o.value = JSON.stringify(Object.assign({}, p, {sourceType: sg.source})); o.textContent = p.label; g.appendChild(o); });
      dd.appendChild(g);
    }
  }
  dd.onchange = function() { if (!this.value) return; navigateToPeriod(JSON.parse(this.value), context); };
  document.getElementById(wrapId).classList.remove('hidden');
}

function renderStatsBoxes(grid, roomStats, gapInfoMap, gapTip, start, end) {
  const m = dataset().meta;
  roomStats.forEach(({id, name, pct, hasGap}) => {
    const div = document.createElement('div');
    div.className = 'room-item' + (hasGap ? ' has-gap' : '');
    const src = (m.loggerSources && m.loggerSources[id]) || '';
    const idStr = (id === 'govee' || isOpenMeteo(id)) ? '' : id;
    const pctStr = pct !== null ? pct.toFixed(1) + '%' : '';
    const normalHTML = pctStr ? `<div class="room-name">${name}</div><div class="room-pct">${pctStr}</div>` : `<div class="room-name">${name}</div>`;
    const hoverHTML = `<div class="room-name">${name}</div><div class="room-src">${src}${idStr ? ' \u00b7 ' + idStr : ''}</div>`;
    div.innerHTML = normalHTML;
    if (hasGap) {
      div.addEventListener('mouseenter', () => {
        gapTip.innerHTML = gapTooltipHTML(gapInfoMap[id], start, end);
        gapTip.style.display = 'block';
        const rect = div.getBoundingClientRect();
        let left = rect.right + 8;
        if (left + 280 > window.innerWidth) left = rect.left - 288;
        gapTip.style.left = Math.max(4, left) + 'px';
        gapTip.style.top = Math.max(4, rect.top) + 'px';
      });
      div.addEventListener('mouseleave', () => { gapTip.style.display = 'none'; });
    } else {
      div.addEventListener('mouseenter', () => { div.innerHTML = hoverHTML; });
      div.addEventListener('mouseleave', () => { div.innerHTML = normalHTML; });
    }
    grid.appendChild(div);
  });
}

// ── Histogram stats ──────────────────────────────────────────────────────────
function updateHistogramStats(start, end) {
  const histStatsPanel = document.getElementById('histogram-stats');
  if (!document.getElementById('cb-temperature').checked) {
    histStatsPanel.classList.add('hidden');
    return;
  }
  histStatsPanel.classList.remove('hidden');
  const overall = document.getElementById('hist-overall');
  const grid = document.getElementById('hist-room-grid');
  const statsBox = document.getElementById('hist-stats-box');
  const warnDiv = document.getElementById('hist-gap-warning');
  const dropWrap = document.getElementById('hist-gap-dropdown-wrap');
  const gapTip = document.getElementById('hist-gap-tip');
  grid.innerHTML = '';
  gapTip.style.display = 'none';
  warnDiv.classList.add('hidden');
  dropWrap.classList.add('hidden');
  statsBox.classList.remove('has-gaps');
  const m = dataset().meta;
  const extSet = new Set(m.externalLoggers || []);
  const histSet = new Set(m.histogramLoggers || m.loggers);
  let totalBelow = 0, totalAll = 0;
  const roomStats = [];
  const gapInfoMap = {};
  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    if (!histSet.has(loggerId)) continue;
    if (extSet.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series) continue;
    // Gap detection
    const gaps = detectSeriesGaps(series.timestamps, start, end);
    gapInfoMap[loggerId] = gaps;
    let filtered = filterSeries(series, start, end);
    if (!filtered) continue; // no data in range — skip
    filtered = applyAnomalousFilter(filtered, loggerId);
    if (!filtered) continue;
    filtered = applySubstratFilter(filtered);
    if (!filtered) continue;
    let below = 0, count = 0;
    for (let i = 0; i < filtered.temperature.length; i++) {
      const t = filtered.temperature[i];
      if (t == null) continue;
      if (t < 32) below++;
      count++;
    }
    if (count === 0) continue; // no temperature readings in range
    const pct = below/count*100;
    totalBelow += below; totalAll += count;
    roomStats.push({id: loggerId, name: ln(loggerId) + meteoSuffix(loggerId) + omniSuffix(m.loggerSources[loggerId] || ''), pct, hasGap: gaps.length > 0});
  }
  if (roomStats.length === 0) { histStatsPanel.classList.add('hidden'); return; }
  const overallPct = totalAll > 0 ? (totalBelow/totalAll*100).toFixed(1) : '-';
  overall.textContent = `${t('overall')}: ${overallPct}% ${t('ofTempReadingsBelow')}`;
  // Gap warning and dropdown
  const gapCount = roomStats.filter(r => r.hasGap).length;
  if (gapCount > 0) {
    statsBox.classList.add('has-gaps');
    warnDiv.classList.remove('hidden');
    warnDiv.textContent = `${t('dataCompleteness')}: ${gapCount} / ${roomStats.length} ${t('seriesHaveGaps')}`;
    const seriesInfo = roomStats.map(r => ({ts: dataset().series[r.id].timestamps, source: m.loggerSources[r.id] || 'Unknown'}));
    // Include selected external loggers in completeness check (e.g. Weather Station T&RH)
    const seriesIds = new Set(roomStats.map(r => r.id));
    for (const id of (m.externalLoggers || [])) {
      if (!seriesIds.has(id) && state.selectedLoggers.has(id) && histSet.has(id) && dataset().series[id]) {
        seriesInfo.push({ts: dataset().series[id].timestamps, source: m.loggerSources[id] || 'Unknown'});
      }
    }
    const allAvailableInfo = m.loggers.filter(id => (!extSet.has(id) || state.selectedLoggers.has(id)) && histSet.has(id) && dataset().series[id]).map(id => ({ts: dataset().series[id].timestamps, source: m.loggerSources[id] || 'Unknown'}));
    buildGapDropdown('hist-gap-dropdown', 'hist-gap-dropdown-wrap', seriesInfo, allAvailableInfo, start, end, 'histogram');
  }
  renderStatsBoxes(grid, roomStats, gapInfoMap, gapTip, start, end);
}

// ── Adaptive comfort ──────────────────────────────────────────────────────────
let _comfortExtSrcText = ''; // stored for PNG export
let _comfortLoggerSources = {}; // per-logger ext source summary for PNG legend

// Pre-parse span dates to ms for fast numeric comparison
const _spanMsCache = new WeakMap();
function _getSpanMs(spans) {
  let cached = _spanMsCache.get(spans);
  if (cached) return cached;
  cached = spans.map(sp => ({
    source: sp.source,
    fromMs: new Date(sp.from + 'T00:00:00Z').getTime(),
    toMs: new Date(sp.to + 'T23:59:59Z').getTime(),
  }));
  _spanMsCache.set(spans, cached);
  return cached;
}

function extSourcesForPoint(spans, tsMs, m) {
  if (!spans || !spans.length) return '';
  const DAY_MS = 86400000;
  const windowStart = tsMs - 7 * DAY_MS;
  const spanMs = _getSpanMs(spans);
  const sources = [];
  const seen = new Set();
  for (const sp of spanMs) {
    if (sp.toMs >= windowStart && sp.fromMs <= tsMs && !seen.has(sp.source)) {
      seen.add(sp.source);
      const name = ln(sp.source);
      const type = m.loggerSources[sp.source];
      sources.push(type ? name + ' [' + type + ']' : name);
    }
  }
  return sources.join(' + ') || '';
}

function renderAdaptiveComfort() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [], params = getComfortParams();
  const allExtTemps = [], allTemps = [];
  let actualStartMs = Infinity, actualEndMs = -Infinity;
  const seenSpans = new Map();
  const perLoggerSources = {}; // loggerId → Set of source labels
  const srcLabel = (id) => {
    const name = ln(id);
    const type = m.loggerSources[id];
    return type ? `${name} [${type}]` : name;
  };
  const iterations = getCompareIterations();
  const isCompare = state.compareEnabled && iterations.length > 1;
  for (const iter of iterations) {
    const savedFilters = state.substratFilters;
    const savedCombine = state.substratCombine;
    state.substratFilters = iter.substratFilters;
    state.substratCombine = iter.substratCombine;
    const namePrefix = iter.setLabel ? '[' + iter.setLabel + '] ' : '';

    // In compare mode, merge all loggers into one trace per set for performance
    const cmpX = [], cmpY = [], cmpHover = [], cmpColors = [];

    for (const loggerId of (m.comfortLoggers || m.roomLoggers)) {
      if (!iter.selectedLoggers.has(loggerId)) continue;
      const series = dataset().series[loggerId];
      if (!series || !series.extTemp) continue;
      let filtered = filterSeries(series, start, end);
      if (!filtered || !filtered.extTemp) continue;
      filtered = applyAnomalousFilter(filtered, loggerId);
      if (!filtered || !filtered.extTemp) continue;
      filtered = applySubstratFilter(filtered);
      if (!filtered || !filtered.extTemp) continue;
      const range = actualDataRange(series.timestamps, start, end);
      if (range) { actualStartMs = Math.min(actualStartMs, range[0]); actualEndMs = Math.max(actualEndMs, range[1]); }
      const loggerSrcSet = new Set();
      if (series.extSourceSpans) {
        for (const sp of series.extSourceSpans) {
          loggerSrcSet.add(srcLabel(sp.source));
          const prev = seenSpans.get(sp.source);
          if (!prev) seenSpans.set(sp.source, {from: sp.from, to: sp.to});
          else { if (sp.from < prev.from) prev.from = sp.from; if (sp.to > prev.to) prev.to = sp.to; }
        }
      } else if (series.extSource) {
        loggerSrcSet.add(srcLabel(series.extSource));
        if (!seenSpans.has(series.extSource)) seenSpans.set(series.extSource, null);
      }
      perLoggerSources[loggerId] = loggerSrcSet;
      for (let i = 0; i < filtered.extTemp.length; i++) {
        if (filtered.extTemp[i] != null && filtered.temperature[i] != null) {
          allExtTemps.push(filtered.extTemp[i]);
          allTemps.push(filtered.temperature[i]);
        }
      }
      const color = iter.colorMap[loggerId] || m.colors[loggerId];
      const cSource = m.loggerSources[loggerId] || '';
      const cIdLabel = loggerId === 'govee' ? '' : ` · ID: ${loggerId}`;
      const cName = namePrefix + ln(loggerId) + meteoSuffix(loggerId) + omniSuffix(cSource);

      if (isCompare) {
        // Merge into per-set arrays — skip expensive per-point customdata
        for (let i = 0; i < filtered.extTemp.length; i++) {
          cmpX.push(filtered.extTemp[i]);
          cmpY.push(filtered.temperature[i]);
          cmpHover.push(ln(loggerId));
          cmpColors.push(color);
        }
      } else {
        const lgGroup = loggerId;
        const customdata = filtered.timestamps.map(ts => extSourcesForPoint(series.extSourceSpans, ts, m));
        traces.push({x:filtered.extTemp, y:filtered.temperature, type:'scatter', mode:'markers',
          name:cName, marker:{color, size:4, opacity:0.2},
          legendgroup:lgGroup, showlegend:false, meta:{loggerId}, customdata,
          hovertemplate:`${ln(loggerId)}<br>${t('runningMean')}: %{x:.1f}°C<br>${t('roomTemp')}: %{y:.1f}°C<br>${t('extSource')}: %{customdata}<br>${t('sensor')}: ${cSource}${cIdLabel}<extra></extra>`});
        traces.push({x:[null], y:[null], type:'scatter', mode:'markers',
          name:cName, marker:{color, size:10, opacity:0.8, symbol:'square', line:{width:0}},
          legendgroup:lgGroup, showlegend:true, hoverinfo:'skip', meta:{loggerId}});
      }
    }

    if (isCompare && cmpX.length > 0) {
      // Single merged trace per compare set — much faster than one per logger
      const lgGroup = 'compare_s' + iter.setIndex;
      traces.push({x:cmpX, y:cmpY, type:'scatter', mode:'markers',
        name: iter.legendName, marker:{color: cmpColors, size:4, opacity:0.2},
        legendgroup:lgGroup, showlegend:false, customdata:cmpHover,
        hovertemplate:`[${iter.setLabel}] %{customdata}<br>Running mean: %{x:.1f}°C<br>Room temp: %{y:.1f}°C<extra></extra>`});
      // Legend-only trace
      traces.push({x:[null], y:[null], type:'scatter', mode:'markers',
        name: iter.legendName, marker:{color: iter.baseColor, size:12, opacity:0.9, symbol:'square', line:{width:0}},
        legendgroup:lgGroup, showlegend:true, hoverinfo:'skip'});
    }

    state.substratFilters = savedFilters;
    state.substratCombine = savedCombine;
  }

  if (params && allExtTemps.length > 0) {
    let xMin = Infinity, xMax = -Infinity;
    for (const v of allExtTemps) { if (v < xMin) xMin = v; if (v > xMax) xMax = v; }
    const xs = Array.from({length:80}, (_, i) => xMin + (xMax-xMin)*i/79);
    const yUp = xs.map(x => params.m*x + params.c + params.delta);
    const yLo = xs.map(x => params.m*x + params.c - params.delta);
    traces.unshift({x:[...xs,...xs.slice().reverse()], y:[...yLo,...yUp.slice().reverse()],
      fill:'toself', mode:'lines', line:{width:0}, fillcolor:'rgba(0,150,0,0.25)',
      hoverinfo:'skip', showlegend:false});
  }

  if (state.showDensity && allExtTemps.length > 30) {
    // Subsample for density heatmap if too many points (performance)
    let heatX = allExtTemps, heatY = allTemps;
    const heatLimit = isCompare ? 10000 : 20000;
    if (allExtTemps.length > heatLimit) {
      const step = Math.ceil(allExtTemps.length / heatLimit);
      heatX = []; heatY = [];
      for (let i = 0; i < allExtTemps.length; i += step) { heatX.push(allExtTemps[i]); heatY.push(allTemps[i]); }
    }
    traces.unshift({x:heatX, y:heatY, type:'histogram2dcontour',
      histnorm:'percent',
      colorscale:[[0,'rgba(220,220,220,0)'],[0.05,'rgba(190,190,190,0.2)'],[0.15,'rgba(150,150,150,0.36)'],[0.35,'rgba(110,110,110,0.5)'],[0.6,'rgba(70,70,70,0.66)'],[1,'rgba(30,30,30,0.8)']],
      showscale:true, ncontours: isCompare ? 12 : 20,
      colorbar:{
        title:{text:'% of points', side:'right', font:{size:11}},
        thickness:12, len:0.5, x:1.01,
        ticksuffix:'%', tickfont:{size:10}
      },
      line:{color:'rgba(80,80,80,0.3)', width:0.5},
      contours:{coloring:'fill', showlines:true},
      hoverinfo:'skip', showlegend:false});
  }

  updateComfortStats(start, end, params);
  const sm = window.innerWidth < 680;
  const dsl = dsLabel();

  // Build external source summary for annotation
  let extSrcText = '';
  if (seenSpans.size > 0) {
    if (seenSpans.size === 1) {
      const [sid, span] = [...seenSpans.entries()][0];
      extSrcText = `Running mean source: ${srcLabel(sid)}`;
    } else {
      const parts = [...seenSpans.entries()]
        .sort((a,b) => (a[1]&&b[1]) ? (a[1].from < b[1].from ? -1 : 1) : 0)
        .map(([sid, span]) => span ? `${srcLabel(sid)} (${span.from} → ${span.to})` : srcLabel(sid));
      extSrcText = `Running mean sources:<br>` + parts.join('<br>');
    }
  }
  _comfortExtSrcText = extSrcText;
  // Build per-logger source map: loggerId → short type label for PNG legend
  _comfortLoggerSources = {};
  for (const [lid, srcSet] of Object.entries(perLoggerSources)) {
    // Extract just the source types (e.g. "TinyTag", "Open-Meteo") for brevity
    const types = new Set();
    for (const label of srcSet) {
      const match = label.match(/\[([^\]]+)\]$/);
      types.add(match ? match[1] : label);
    }
    _comfortLoggerSources[lid] = [...types].join(' + ');
  }

  return {traces, layout: {
    autosize:true, font:{family:'Ubuntu, sans-serif'}, margin:{l:sm?45:65, r:sm?8:20, t:sm?15:30, b:sm?60:100},
    xaxis:{title:t('runningMeanAxis'), showgrid:true, gridcolor:'#eee'},
    yaxis:{title:t('airTempAxis'), showgrid:true, gridcolor:'#eee'},
    legend:{orientation:'h', x:0.5, y:-0.22, xanchor:'center', font:{size:11}, itemclick:false, itemdoubleclick:false},
    annotations: isFinite(actualStartMs) ? [dateRangeAnnotation(actualStartMs, actualEndMs, false, comfortSourceLabel(extSrcText))] : [],
    plot_bgcolor:'white', paper_bgcolor:'white', hovermode:'closest', hoverlabel:{font:{family:'Ubuntu, sans-serif'}},
  }, title: `${dsl} \u2013 ${t('adaptiveComfortTitle')}`, _noData: allExtTemps.length === 0};
}

// ── Data completeness detection ───────────────────────────────────────────────
const GAP_DETECT_MS = 24 * 3600 * 1000;

function detectSeriesGaps(ts, startMs, endMs) {
  const gaps = [];
  const wholeRange = {startMs, endMs, days: Math.max(1, Math.round((endMs - startMs) / 86400000))};
  if (!ts || ts.length === 0) { gaps.push(wholeRange); return gaps; }
  const r = tsRange(ts, startMs, endMs);
  if (!r) { gaps.push(wholeRange); return gaps; }
  const {s, e} = r;
  if (ts[s] - startMs >= GAP_DETECT_MS)
    gaps.push({startMs, endMs: ts[s], days: Math.max(1, Math.round((ts[s] - startMs) / 86400000))});
  for (let i = s + 1; i <= e; i++) {
    const diff = ts[i] - ts[i-1];
    if (diff >= GAP_DETECT_MS)
      gaps.push({startMs: ts[i-1], endMs: ts[i], days: Math.max(1, Math.round(diff / 86400000))});
  }
  if (endMs - ts[e] >= GAP_DETECT_MS)
    gaps.push({startMs: ts[e], endMs, days: Math.max(1, Math.round((endMs - ts[e]) / 86400000))});
  return gaps;
}

function hasGapsInRange(ts, startMs, endMs) {
  if (!ts || ts.length === 0) return true;
  const r = tsRange(ts, startMs, endMs);
  if (!r) return true;
  const {s, e} = r;
  if (ts[s] - startMs >= GAP_DETECT_MS) return true;
  for (let i = s + 1; i <= e; i++) { if (ts[i] - ts[i-1] >= GAP_DETECT_MS) return true; }
  return endMs - ts[e] >= GAP_DETECT_MS;
}

function formatGapRange(startMs, endMs) {
  let s = new Date(startMs + 3*3600000), e = new Date(endMs + 3*3600000);
  // Mirror fmtDateEAT rounding: last reading before gap at ≥23:00 → gap starts next day;
  // first reading after gap at <01:00 → gap ends previous day.
  if (s.getUTCHours() >= 23) s = new Date(s.getTime() + 24*3600000);
  if (e.getUTCHours() < 1)   e = new Date(e.getTime() - 24*3600000);
  const mn = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  if (s.getUTCFullYear() === e.getUTCFullYear() && s.getUTCMonth() === e.getUTCMonth())
    return `${mn[s.getUTCMonth()]} ${s.getUTCDate()}\u2013${e.getUTCDate()}, ${s.getUTCFullYear()}`;
  if (s.getUTCFullYear() === e.getUTCFullYear())
    return `${mn[s.getUTCMonth()]} ${s.getUTCDate()} \u2013 ${mn[e.getUTCMonth()]} ${e.getUTCDate()}, ${s.getUTCFullYear()}`;
  return `${mn[s.getUTCMonth()]} ${s.getUTCDate()}, ${s.getUTCFullYear()} \u2013 ${mn[e.getUTCMonth()]} ${e.getUTCDate()}, ${e.getUTCFullYear()}`;
}

function gapTooltipHTML(gaps, rangeStartMs, rangeEndMs) {
  const sorted = gaps.slice().sort((a, b) => b.days - a.days);
  const top = sorted.slice(0, 5);
  const totalDays = sorted.reduce((s, g) => s + g.days, 0);
  const rangeDays = Math.max(1, (rangeEndMs - rangeStartMs) / 86400000);
  const pct = (totalDays / rangeDays * 100).toFixed(0);
  let html = '';
  for (const g of top)
    html += `<div class="gap-entry">${formatGapRange(g.startMs, g.endMs)} (${g.days} day${g.days !== 1 ? 's' : ''})</div>`;
  if (sorted.length > 5)
    html += `<div class="gap-more">and ${sorted.length - 5} more gap${sorted.length - 5 !== 1 ? 's' : ''}\u2026</div>`;
  html += `<div class="gap-total">${totalDays} day${totalDays !== 1 ? 's' : ''} missing total (${pct}%)</div>`;
  return html;
}

function periodRangeMs(gran, info) {
  if (gran === 'year') return {s: Date.UTC(info.y, 0, 1), e: Date.UTC(info.y, 11, 31, 23, 59, 59, 999)};
  if (gran === 'season') {
    const sm = [[0,1],[2,4],[5,9],[10,11]][info.si];
    return {s: Date.UTC(info.y, sm[0], 1), e: Date.UTC(info.y, sm[1]+1, 0, 23, 59, 59, 999)};
  }
  if (gran === 'month') return {s: Date.UTC(info.y, info.m-1, 1), e: Date.UTC(info.y, info.m, 0, 23, 59, 59, 999)};
  if (gran === 'week') {
    const jan4 = new Date(Date.UTC(info.y, 0, 4));
    const dow = jan4.getUTCDay() || 7;
    const ws = jan4.getTime() - (dow-1)*86400000 + (info.w-1)*7*86400000;
    return {s: ws, e: ws + 7*86400000 - 1};
  }
  if (gran === 'day') return {s: info.ts, e: info.ts + 86400000 - 1};
  return null;
}

function _searchCompletePeriods(tsArrays, rangeStart, rangeEnd) {
  // Returns array of complete period objects at the coarsest grouping found
  const m = dataset().meta;
  const MN = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  function allOK(s, e) {
    for (const ts of tsArrays) { if (hasGapsInRange(ts, s, e)) return false; }
    return true;
  }
  const results = [];
  let found = false;
  const sY = new Date(rangeStart).getUTCFullYear(), eY = new Date(rangeEnd).getUTCFullYear();
  for (let y = sY; y <= eY; y++) {
    const r = periodRangeMs('year', {y});
    const ol = Math.min(r.e, rangeEnd) - Math.max(r.s, rangeStart);
    if (ol <= 0 || ol / (r.e - r.s) < 0.75) continue;
    if (allOK(r.s, r.e)) { results.push({label: String(y), gran: 'year', y, fi: ol/(r.e-r.s) >= 0.99}); found = true; }
  }
  if (!found) {
    const SN = ['Kiangazi (Jan\u2013Feb)','Masika (Mar\u2013May)','Kiangazi (Jun\u2013Oct)','Vuli (Nov\u2013Dec)'];
    for (const as of (m.availableSeasons || [])) {
      const r = periodRangeMs('season', {y: as.year, si: as.season});
      if (r.s > rangeEnd || r.e < rangeStart) continue;
      const ol = Math.min(r.e, rangeEnd) - Math.max(r.s, rangeStart);
      if (ol <= 0 || ol / (r.e - r.s) < 0.75) continue;
      if (allOK(r.s, r.e)) { results.push({label: `${SN[as.season]} ${as.year}`, gran: 'season', y: as.year, si: as.season, fi: ol/(r.e-r.s) >= 0.99}); found = true; }
    }
  }
  if (!found) {
    for (let y = sY; y <= eY; y++) {
      const ms = y === sY ? new Date(rangeStart).getUTCMonth() : 0;
      const me = y === eY ? new Date(rangeEnd).getUTCMonth() : 11;
      for (let mo = ms; mo <= me; mo++) {
        const r = periodRangeMs('month', {y, m: mo+1});
        const ol = Math.min(r.e, rangeEnd) - Math.max(r.s, rangeStart);
        if (ol <= 0 || ol / (r.e - r.s) < 0.75) continue;
        if (allOK(r.s, r.e)) { results.push({label: `${MN[mo]} ${y}`, gran: 'month', y, m: mo+1, fi: ol/(r.e-r.s) >= 0.99}); found = true; }
      }
    }
  }
  if (!found) {
    for (const aw of (m.availableWeeks || [])) {
      const r = periodRangeMs('week', {y: aw.year, w: aw.week});
      if (r.s > rangeEnd || r.e < rangeStart) continue;
      const ol = Math.min(r.e, rangeEnd) - Math.max(r.s, rangeStart);
      if (ol / (r.e - r.s) < 0.75) continue;
      if (allOK(r.s, r.e)) { const wd = new Date(r.s); results.push({label: `W/s ${String(wd.getUTCDate()).padStart(2,'0')}/${String(wd.getUTCMonth()+1).padStart(2,'0')}/${String(wd.getUTCFullYear()).slice(-2)}`, gran: 'week', y: aw.year, w: aw.week, fi: ol/(r.e-r.s) >= 0.99}); found = true; }
    }
  }
  if (!found && (rangeEnd - rangeStart) / 86400000 <= 366) {
    for (const ad of (m.availableDays || [])) {
      if (ad.ts < rangeStart || ad.ts + 86400000 - 1 > rangeEnd) continue;
      const r = periodRangeMs('day', {ts: ad.ts});
      if (allOK(r.s, r.e)) { results.push({label: ad.label, gran: 'day', ts: ad.ts, fi: true}); found = true; }
    }
  }
  results.sort((a, b) => (b.fi ? 1 : 0) - (a.fi ? 1 : 0));
  return results;
}

function _searchSecondary(tsArrays) {
  // Find complete periods of the same grouping as the user's selection, across the full data range
  const m = dataset().meta;
  function allOK(s, e) {
    for (const ts of tsArrays) { if (hasGapsInRange(ts, s, e)) return false; }
    return true;
  }
  const results = [];
  if (state.timeMode === 'year') {
    for (const y of (m.availableYears || [])) {
      if (y === state.selectedYear) continue;
      const r = periodRangeMs('year', {y});
      if (allOK(r.s, r.e)) results.push({label: String(y), gran: 'year', y});
    }
  } else if (state.timeMode === 'season' && state.selectedSeason) {
    for (const as of (m.availableSeasons || [])) {
      if (as.year === state.selectedSeason.year && as.season === state.selectedSeason.season) continue;
      const r = periodRangeMs('season', {y: as.year, si: as.season});
      if (allOK(r.s, r.e)) results.push({label: as.label, gran: 'season', y: as.year, si: as.season});
    }
  } else if (state.timeMode === 'month' && state.selectedMonth) {
    for (const am of (m.availableMonths || [])) {
      if (am.year === state.selectedMonth.year && am.month === state.selectedMonth.month) continue;
      const r = periodRangeMs('month', {y: am.year, m: am.month});
      if (allOK(r.s, r.e)) results.push({label: am.label, gran: 'month', y: am.year, m: am.month});
    }
  } else if (state.timeMode === 'week' && state.selectedWeek) {
    for (const aw of (m.availableWeeks || [])) {
      if (aw.year === state.selectedWeek.year && aw.week === state.selectedWeek.week) continue;
      const r = periodRangeMs('week', {y: aw.year, w: aw.week});
      if (allOK(r.s, r.e)) results.push({label: aw.label, gran: 'week', y: aw.year, w: aw.week});
    }
  }
  return results;
}

function findCompletePeriods(seriesInfo, rangeStart, rangeEnd, allAvailableInfo) {
  // seriesInfo: [{ts, source}, ...] for each enabled series
  // allAvailableInfo: [{ts, source}, ...] for ALL available loggers (used for source-group fallback)
  const allTs = seriesInfo.map(si => si.ts);
  const primary = _searchCompletePeriods(allTs, rangeStart, rangeEnd);
  const secondary = primary.length > 0 ? _searchSecondary(allTs) : [];
  // Source-group fallback: when no all-complete periods exist, search per source type across ALL available loggers
  const sourceGroups = [];
  if (primary.length === 0) {
    const fallbackInfo = allAvailableInfo || seriesInfo;
    const bySource = {};
    for (const si of fallbackInfo) {
      const src = si.source || 'Unknown';
      if (!bySource[src]) bySource[src] = [];
      bySource[src].push(si.ts);
    }
    const srcKeys = Object.keys(bySource);
    for (const src of srcKeys) {
      const grpPrimary = _searchCompletePeriods(bySource[src], rangeStart, rangeEnd);
      const grpSecondary = _searchSecondary(bySource[src]);
      if (grpPrimary.length > 0 || grpSecondary.length > 0) {
        sourceGroups.push({source: src, count: bySource[src].length, primary: grpPrimary, secondary: grpSecondary});
      }
    }
  }
  return {primary, secondary, sourceGroups};
}

function navigateToPeriod(p, context) {
  document.getElementById('gap-tip').style.display = 'none';
  document.getElementById('hist-gap-tip').style.display = 'none';
  document.getElementById('periodic-comp-tip').style.display = 'none';
  ['between-inputs','year-input','season-input','month-input','week-input','day-input'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));
  if (p.gran === 'year') {
    state.timeMode = 'year'; state.selectedYear = p.y;
    document.getElementById('time-mode').value = 'year';
    document.getElementById('year-select').value = String(p.y);
    document.getElementById('year-input').classList.remove('hidden');
  } else if (p.gran === 'season') {
    state.timeMode = 'season'; state.selectedSeason = {year: p.y, season: p.si};
    document.getElementById('time-mode').value = 'season';
    document.getElementById('season-select').value = `${p.y}-${p.si}`;
    document.getElementById('season-input').classList.remove('hidden');
  } else if (p.gran === 'month') {
    state.timeMode = 'month'; state.selectedMonth = {year: p.y, month: p.m};
    document.getElementById('time-mode').value = 'month';
    document.getElementById('month-select').value = `${p.y}-${p.m}`;
    document.getElementById('month-input').classList.remove('hidden');
  } else if (p.gran === 'week') {
    state.timeMode = 'week'; state.selectedWeek = {year: p.y, week: p.w};
    document.getElementById('time-mode').value = 'week';
    document.getElementById('week-select').value = `${p.y}-${p.w}`;
    document.getElementById('week-input').classList.remove('hidden');
  } else if (p.gran === 'day') {
    state.timeMode = 'day'; state.selectedDay = p.ts;
    document.getElementById('time-mode').value = 'day';
    document.getElementById('day-select').value = String(p.ts);
    document.getElementById('day-input').classList.remove('hidden');
  }
  // If navigating to a source-specific period, update checkboxes to match
  if (p.sourceType) {
    const m = dataset().meta;
    const extSet = new Set(m.externalLoggers || []);
    if (context === 'histogram') {
      const loggerDiv = document.getElementById('logger-checkboxes');
      const allIds = m.loggers;
      allIds.forEach(id => {
        if (extSet.has(id)) return; // leave external loggers unchanged
        const match = m.loggerSources[id] === p.sourceType;
        if (match) state.selectedLoggers.add(id); else state.selectedLoggers.delete(id);
        const cb = loggerDiv.querySelector(`input[data-logger-id="${id}"]`);
        if (cb) cb.checked = match;
      });
    } else if (context === 'comfort') {
      const roomDiv = document.getElementById('room-logger-checkboxes');
      const comfortIds = m.comfortLoggers || m.roomLoggers || [];
      comfortIds.forEach(id => {
        const match = m.loggerSources[id] === p.sourceType;
        if (match) state.selectedRoomLoggers.add(id); else state.selectedRoomLoggers.delete(id);
        const cb = roomDiv.querySelector(`input[data-logger-id="${id}"]`);
        if (cb) cb.checked = match;
      });
    } else if (context === 'periodic') {
      const loggerDiv = document.getElementById('logger-checkboxes');
      m.loggers.forEach(id => {
        const match = m.loggerSources[id] === p.sourceType;
        if (match) state.selectedLoggers.add(id); else state.selectedLoggers.delete(id);
        const cb = loggerDiv.querySelector(`input[data-logger-id="${id}"]`);
        if (cb) cb.checked = match;
      });
    }
  }
  updatePlot();
}

// ── Comfort stats ─────────────────────────────────────────────────────────────
function updateComfortStats(start, end, params) {
  const overall = document.getElementById('comfort-overall');
  const grid = document.getElementById('comfort-room-grid');
  const statsBox = document.getElementById('comfort-stats');
  const warnDiv = document.getElementById('gap-warning');
  const dropWrap = document.getElementById('gap-dropdown-wrap');
  const gapTip = document.getElementById('gap-tip');
  grid.innerHTML = '';
  gapTip.style.display = 'none';
  warnDiv.classList.add('hidden');
  dropWrap.classList.add('hidden');
  statsBox.classList.remove('has-gaps');
  if (!params) { overall.textContent = 'No comfort band selected'; statsBox.style.display = ''; return; }
  const m = dataset().meta;
  let totalIn = 0, totalAll = 0;
  const roomStats = [];
  const gapInfoMap = {};
  for (const loggerId of (m.comfortLoggers || m.roomLoggers)) {
    if (!state.selectedRoomLoggers.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series || !series.extTemp) continue;
    // Detect gaps for this series
    const gaps = detectSeriesGaps(series.timestamps, start, end);
    gapInfoMap[loggerId] = gaps;
    let filtered = filterSeries(series, start, end);
    filtered = filtered ? applyAnomalousFilter(filtered, loggerId) : null;
    filtered = filtered ? applySubstratFilter(filtered) : null;
    let pct = null;
    if (filtered && filtered.extTemp) {
      let inZone = 0, count = 0;
      const mode = state.comfortPctMode || 'below_upper';
      for (let i = 0; i < filtered.temperature.length; i++) {
        const ext = filtered.extTemp[i], temp = filtered.temperature[i];
        if (ext == null || temp == null) continue;
        const mid = params.m*ext + params.c;
        const upper = mid + params.delta;
        const lower = mid - params.delta;
        if (mode === 'below_upper' && temp <= upper) inZone++;
        else if (mode === 'within' && temp >= lower && temp <= upper) inZone++;
        else if (mode === 'above_lower' && temp >= lower) inZone++;
        count++;
      }
      pct = count > 0 ? inZone/count*100 : 0;
      totalIn += inZone; totalAll += count;
    }
    roomStats.push({id: loggerId, name: ln(loggerId) + meteoSuffix(loggerId) + omniSuffix(m.loggerSources[loggerId] || ''), pct, hasGap: gaps.length > 0});
  }
  if (roomStats.length === 0) { statsBox.style.display = 'none'; return; }
  statsBox.style.display = '';
  const overallPct = totalAll > 0 ? (totalIn/totalAll*100).toFixed(1) : '-';
  const modeLabel = {below_upper: t('belowUpper').toLowerCase(), within: t('withinComfort').toLowerCase(), above_lower: t('aboveLower').toLowerCase()}[state.comfortPctMode || 'below_upper'];
  overall.textContent = `${t('overall')}: ${overallPct}% ${modeLabel}`;
  // Gap warning and dropdown
  const gapCount = roomStats.filter(r => r.hasGap).length;
  if (gapCount > 0) {
    statsBox.classList.add('has-gaps');
    warnDiv.classList.remove('hidden');
    warnDiv.textContent = `${t('dataCompleteness')}: ${gapCount} / ${roomStats.length} ${t('seriesHaveGaps')}`;
    const seriesInfo = roomStats.map(r => ({ts: dataset().series[r.id].timestamps, source: m.loggerSources[r.id] || 'Unknown'}));
    // Include selected external loggers in completeness check (e.g. Weather Station T&RH)
    const comfortSeriesIds = new Set(roomStats.map(r => r.id));
    for (const id of (m.externalLoggers || [])) {
      if (!comfortSeriesIds.has(id) && state.selectedLoggers.has(id) && dataset().series[id]) {
        seriesInfo.push({ts: dataset().series[id].timestamps, source: m.loggerSources[id] || 'Unknown'});
      }
    }
    const allComfortLoggers = m.comfortLoggers || m.roomLoggers || [];
    const allAvailableInfo = allComfortLoggers.filter(id => dataset().series[id]).map(id => ({ts: dataset().series[id].timestamps, source: m.loggerSources[id] || 'Unknown'}));
    buildGapDropdown('gap-dropdown', 'gap-dropdown-wrap', seriesInfo, allAvailableInfo, start, end, 'comfort');
  }
  renderStatsBoxes(grid, roomStats, gapInfoMap, gapTip, start, end);
}

// ── Legend style helper - scales font/gap based on number of visible items ─────
function legendStyle(n) {
  const t = Math.max(0, Math.min(1, (n - 10) / 14)); // 0 at n≤10, 1 at n≥24
  return {font:{size: Math.round(11 - 3*t)}, tracegroupgap: Math.round(10*(1-t))};
}

// ── After Plotly renders, re-apply legend font based on actual DOM item count ───
// Re-runs unlockLegendScroll after the relayout resolves, since Plotly re-renders
// the legend SVG (restoring scroll clips) whenever legend properties change.
function applyLegendStyleFromDOM(root) {
  if (!root) return;
  const legend = root.querySelector ? root.querySelector('.legend') : null;
  if (!legend) return;
  const n = legend.querySelectorAll('.traces').length;
  if (!n) return;
  const {font, tracegroupgap} = legendStyle(n);
  Plotly.relayout(root.id, {'legend.font.size': font.size, 'legend.tracegroupgap': tracegroupgap})
    .then(() => unlockLegendScroll(root));
}

// ── Remove Plotly legend scroll clip and compact vertical spacing ───────────────
// Plotly renders every legend item in the SVG DOM but hides overflow ones with a
// clip-path. We remove it and repack items tighter so they all fit.
function unlockLegendScroll(root) {
  if (!root) return;
  const legend = root.querySelector ? root.querySelector('.legend') : null;
  if (!legend) return;
  legend.querySelectorAll('[clip-path]').forEach(el => el.removeAttribute('clip-path'));
  legend.querySelectorAll('[class*="scroll"]:not(.scrollbox)').forEach(el => el.remove());
  // Block Plotly's wheel-scroll handler on the legend (live DOM only, not SVG export docs)
  if (legend.ownerDocument === document) {
    legend.addEventListener('wheel', e => { e.stopImmediatePropagation(); e.preventDefault(); }, {capture: true, passive: false});
  }
  const items = Array.from(legend.querySelectorAll('.traces'));
  if (items.length < 2) return;
  const getXY = el => {
    const m = (el.getAttribute('transform') || '').match(/translate\(\s*([-\d.]+)[\s,]+([-\d.]+)/);
    return m ? [parseFloat(m[1]), parseFloat(m[2])] : [0, 0];
  };
  const [x0, y0] = getXY(items[0]);
  const dy = getXY(items[1])[1] - y0;
  if (dy <= 8) return; // already tight enough
  const newDy = Math.max(8, dy - 2); // reduce by 2px per item
  items.forEach((item, i) => item.setAttribute('transform', `translate(${x0}, ${y0 + i * newDy})`));
}

// Increase horizontal spacing between legend items for horizontal legends (PNG export)
function expandHorizontalLegendSpacing(root, extraGap) {
  if (!root) return;
  const legend = root.querySelector ? root.querySelector('.legend') : null;
  if (!legend) return;
  legend.querySelectorAll('[clip-path]').forEach(el => el.removeAttribute('clip-path'));
  const items = Array.from(legend.querySelectorAll('g.traces'));
  if (items.length < 2) return;
  const getTransform = el => {
    const t = el.getAttribute('transform') || '';
    const m = t.match(/translate\(([^,]+)[,\s]+([^)]+)/);
    return m ? {x: parseFloat(m[1]), y: parseFloat(m[2])} : {x: 0, y: 0};
  };
  const positions = items.map(getTransform);
  if (positions[1].x - positions[0].x <= 0) return; // vertical legend, don't adjust
  // Group items by row (same y-coordinate), then shift each row's items independently
  const rowMap = new Map();
  items.forEach((item, i) => {
    const rowKey = Math.round(positions[i].y);
    if (!rowMap.has(rowKey)) rowMap.set(rowKey, []);
    rowMap.get(rowKey).push(i);
  });
  rowMap.forEach(indices => {
    indices.sort((a, b) => positions[a].x - positions[b].x);
    let cumulative = 0;
    indices.forEach((idx, j) => {
      if (j > 0) cumulative += extraGap;
      items[idx].setAttribute('transform', `translate(${positions[idx].x + cumulative}, ${positions[idx].y})`);
    });
  });
}

// ── Average Profiles ──────────────────────────────────────────────────────────
function eatDate(ms) { return new Date(ms + 3 * 3600 * 1000); }

__CYCLE_PHASES__
// Helper: get ISO week string from ms timestamp (EAT-adjusted)
function getISOWeekStr(ms) {
  const d = eatDate(ms);
  const jan4 = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
  const dayOfYear = Math.floor((d - new Date(Date.UTC(d.getUTCFullYear(), 0, 1))) / 86400000);
  const dow = d.getUTCDay() || 7;
  let wk = Math.floor((dayOfYear + jan4.getUTCDay() - dow) / 7) + 1;
  let yr = d.getUTCFullYear();
  if (wk < 1) { yr--; wk = 52; }
  else if (wk > 52) { yr++; wk = 1; }
  return yr + '-W' + String(wk).padStart(2, '0');
}

function updatePeriodicWarnings(warningInfos) {
  const container = document.getElementById('periodic-warnings');
  container.innerHTML = '';
  if (warningInfos.length === 0) return;
  warningInfos.forEach(w => {
    const div = document.createElement('div');
    div.className = 'periodic-warning';
    if (w.pct >= 100) div.classList.add('red');
    else if (w.pct > 80) div.classList.add('orange');
    div.innerHTML = '<b>' + w.name + '</b> (' + w.metric + '): ' + w.pct.toFixed(0) + '% of categories based on single readings';
    container.appendChild(div);
  });
}

function updatePeriodicCompleteness(start, end) {
  const panel = document.getElementById('periodic-completeness');
  const box = document.getElementById('periodic-comp-box');
  const warnDiv = document.getElementById('periodic-comp-warning');
  const dropWrap = document.getElementById('periodic-comp-dropdown-wrap');
  const grid = document.getElementById('periodic-comp-grid');
  const gapTip = document.getElementById('periodic-comp-tip');
  grid.innerHTML = '';
  gapTip.style.display = 'none';
  box.classList.remove('has-gaps');
  warnDiv.textContent = '';
  dropWrap.classList.add('hidden');

  const m = dataset().meta;
  const extSet = new Set(m.externalLoggers || []);
  const lineSet = new Set(m.lineLoggers || m.loggers);
  const roomStats = [];
  const gapInfoMap = {};

  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    if (!lineSet.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series) continue;
    let filtered = filterSeries(series, start, end);
    if (!filtered) continue; // no data in range — skip
    filtered = applyAnomalousFilter(filtered, loggerId);
    if (!filtered) continue;
    const gaps = detectSeriesGaps(series.timestamps, start, end);
    gapInfoMap[loggerId] = gaps;
    roomStats.push({id: loggerId, name: ln(loggerId) + meteoSuffix(loggerId) + omniSuffix(m.loggerSources[loggerId] || ''), pct: null, hasGap: gaps.length > 0});
  }

  const gapCount = roomStats.filter(r => r.hasGap).length;
  if (gapCount === 0) { panel.classList.add('hidden'); return; }

  panel.classList.remove('hidden');
  box.classList.add('has-gaps');
  warnDiv.textContent = t('dataCompleteness') + ': ' + gapCount + ' / ' + roomStats.length + ' ' + t('seriesHaveGaps');

  // Build "jump to complete period" dropdown (same as histogram/comfort)
  const seriesInfo = roomStats.map(r => ({ts: dataset().series[r.id].timestamps, source: m.loggerSources[r.id] || 'Unknown'}));
  const allAvailableInfo = m.loggers.filter(id => (!extSet.has(id) || state.selectedLoggers.has(id)) && lineSet.has(id) && dataset().series[id]).map(id => ({ts: dataset().series[id].timestamps, source: m.loggerSources[id] || 'Unknown'}));
  buildGapDropdown('periodic-comp-dropdown', 'periodic-comp-dropdown-wrap', seriesInfo, allAvailableInfo, start, end, 'periodic');

  renderStatsBoxes(grid, roomStats, gapInfoMap, gapTip, start, end);
}

function emptyPeriodicResult(msg) {
  const sm = window.innerWidth < 680;
  return {
    traces: [],
    layout: {
      autosize: true, font: {family: 'Ubuntu, sans-serif'},
      margin: {l: sm ? 45 : 65, r: sm ? 8 : 20, t: sm ? 20 : 36, b: sm ? 60 : 80},
      xaxis: {showgrid: false, zeroline: false, showticklabels: false},
      yaxis: {showgrid: false, zeroline: false, showticklabels: false},
      annotations: [{text: msg || t('noDataSelected'), xref: 'paper', yref: 'paper', x: 0.5, y: 0.5, showarrow: false, font: {size: 16, color: '#999'}}],
      plot_bgcolor: 'white', paper_bgcolor: 'white',
    },
    title: dsLabel() + ' \u2013 ' + t('avgProfiles'),
    _noData: true,
  };
}

// ── Beta Feature: Interpolation helper ───────────────────────────────────────
// Given sorted external timestamps + temperatures, return interpolated temp at target ms
function interpolateExtTemp(extTs, extTemp, targetMs) {
  if (!extTs || extTs.length === 0) return null;
  if (targetMs <= extTs[0]) return extTemp[0];
  if (targetMs >= extTs[extTs.length - 1]) return extTemp[extTs.length - 1];
  // Binary search for bracket
  let lo = 0, hi = extTs.length - 1;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    if (extTs[mid] <= targetMs) lo = mid; else hi = mid;
  }
  const t0 = extTs[lo], t1 = extTs[hi];
  if (t1 === t0) return extTemp[lo];
  const frac = (targetMs - t0) / (t1 - t0);
  return extTemp[lo] + frac * (extTemp[hi] - extTemp[lo]);
}

// Get the primary external logger series for the current dataset
function getExternalSeries() {
  const m = dataset().meta;
  const extIds = m.externalLoggers || [];
  // Prefer the non-forecast historical logger
  for (const id of extIds) {
    if (isOpenMeteo(id) && !isForecast(id) && dataset().series[id]) return {id, series: dataset().series[id]};
  }
  // Fallback to any external logger
  for (const id of extIds) {
    if (dataset().series[id]) return {id, series: dataset().series[id]};
  }
  return null;
}

// ── Beta Feature 1: Temperature Differential ─────────────────────────────────
function renderBetaDifferential() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const ext = getExternalSeries();
  if (!ext) return {traces: [], layout: {autosize:true, font:{family:'Ubuntu, sans-serif'}, annotations:[{text:'No external temperature data available',xref:'paper',yref:'paper',x:0.5,y:0.5,showarrow:false,font:{size:16,color:'#999'}}], plot_bgcolor:'white',paper_bgcolor:'white'}, title: t('betaDiffTitle'), _noData: true};

  const extFiltered = filterSeries(ext.series, start, end);
  if (!extFiltered) return {traces:[], layout:{autosize:true, font:{family:'Ubuntu, sans-serif'}, annotations:[{text:t('noDataRange'),xref:'paper',yref:'paper',x:0.5,y:0.5,showarrow:false,font:{size:16,color:'#999'}}], plot_bgcolor:'white',paper_bgcolor:'white'}, title: t('betaDiffTitle'), _noData: true};

  const traces = [];
  const roomSet = new Set(m.roomLoggers || []);
  let hasData = false;

  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    if (!roomSet.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series) continue;
    let filtered = filterSeries(series, start, end);
    if (!filtered) continue;
    filtered = applyAnomalousFilter(filtered, loggerId);
    if (!filtered) continue;

    // Compute differential: T_indoor - T_outdoor (interpolated)
    const diffX = [], diffY = [];
    for (let i = 0; i < filtered.timestamps.length; i++) {
      const tMs = filtered.timestamps[i];
      const tIndoor = filtered.temperature[i];
      if (tIndoor == null) continue;
      const tOutdoor = interpolateExtTemp(extFiltered.timestamps, extFiltered.temperature, tMs);
      if (tOutdoor == null) continue;
      diffX.push(toEATString(tMs));
      diffY.push(+(tIndoor - tOutdoor).toFixed(2));
    }
    if (diffX.length === 0) continue;
    hasData = true;

    const color = m.colors[loggerId];
    const name = ln(loggerId);
    traces.push({
      x: diffX, y: diffY, type: 'scatter', mode: 'lines',
      name: name, line: {color, width: 1.4}, opacity: 0.6,
      hovertemplate: `${name}<br>%{x|%d/%m/%Y %H:%M}<br>\u0394T: %{y:+.1f}\u00b0C<extra></extra>`
    });
  }

  // Zero reference line
  traces.push({x:[null],y:[null], type:'scatter', mode:'lines', name:'\u0394T = 0 (' + t('noDifference') + ')', line:{color:'#999',width:1,dash:'dash'}, hoverinfo:'skip', showlegend:true});

  const sm = window.innerWidth < 680;
  const dsl = dsLabel();
  const title = `${dsl} \u2013 ${t('betaDiffTitle')}`;
  return {
    traces, title,
    layout: {
      autosize: true, font: {family: 'Ubuntu, sans-serif'},
      margin: {l: sm?45:65, r: sm?8:20, t: sm?6:10, b: sm?40:60},
      xaxis: {title: t('dateTime') + ' <i><span style="color:#aaa">(EAT, UTC+03:00)</span></i>', type: 'date', showgrid: true, gridcolor: '#eee'},
      yaxis: {title: t('betaDiffAxis'), showgrid: true, gridcolor: '#eee', zeroline: true, zerolinecolor: '#999', zerolinewidth: 1},
      legend: {orientation: 'v', x: 1.01, y: 1, xanchor: 'left', itemclick: false, itemdoubleclick: false},
      plot_bgcolor: 'white', paper_bgcolor: 'white',
      shapes: [{type:'line', xref:'paper', yref:'y', x0:0, x1:1, y0:0, y1:0, line:{color:'#999',width:1,dash:'dash'}}],
      hovermode: 'closest', hoverlabel: {font: {family: 'Ubuntu, sans-serif'}},
    },
    _noData: !hasData,
  };
}

// ── Beta Feature 2: Decrement Factor ─────────────────────────────────────────
function renderBetaDecrement() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const ext = getExternalSeries();
  if (!ext) return {traces:[], layout:{autosize:true, font:{family:'Ubuntu, sans-serif'}, annotations:[{text:'No external temperature data available',xref:'paper',yref:'paper',x:0.5,y:0.5,showarrow:false,font:{size:16,color:'#999'}}], plot_bgcolor:'white',paper_bgcolor:'white'}, title: t('betaDecrementTitle'), _noData: true};

  const extFiltered = filterSeries(ext.series, start, end);
  if (!extFiltered) return {traces:[], layout:{autosize:true, font:{family:'Ubuntu, sans-serif'}, annotations:[{text:t('noDataRange'),xref:'paper',yref:'paper',x:0.5,y:0.5,showarrow:false,font:{size:16,color:'#999'}}], plot_bgcolor:'white',paper_bgcolor:'white'}, title: t('betaDecrementTitle'), _noData: true};

  // Group external data by day (EAT)
  const extByDay = {};
  for (let i = 0; i < extFiltered.timestamps.length; i++) {
    const d = toEATString(extFiltered.timestamps[i]).slice(0, 10);
    if (!extByDay[d]) extByDay[d] = [];
    extByDay[d].push(extFiltered.temperature[i]);
  }

  const roomSet = new Set(m.roomLoggers || []);
  const loggerNames = [], loggerDecrement = [], loggerColors = [], loggerIds = [], loggerSources = [];
  let hasData = false;

  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    if (!roomSet.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series) continue;
    let filtered = filterSeries(series, start, end);
    if (!filtered) continue;
    filtered = applyAnomalousFilter(filtered, loggerId);
    if (!filtered) continue;

    // Group indoor data by day
    const indoorByDay = {};
    for (let i = 0; i < filtered.timestamps.length; i++) {
      const d = toEATString(filtered.timestamps[i]).slice(0, 10);
      if (!indoorByDay[d]) indoorByDay[d] = [];
      indoorByDay[d].push(filtered.temperature[i]);
    }

    // Compute daily decrement factors
    const factors = [];
    for (const day of Object.keys(indoorByDay)) {
      if (!extByDay[day]) continue;
      const extArr = extByDay[day];
      const indArr = indoorByDay[day];
      if (extArr.length < 4 || indArr.length < 4) continue; // need enough data points
      const extSwing = Math.max(...extArr) - Math.min(...extArr);
      const indSwing = Math.max(...indArr) - Math.min(...indArr);
      if (extSwing < 0.5) continue; // skip days with negligible outdoor swing
      factors.push(indSwing / extSwing);
    }

    if (factors.length === 0) continue;
    hasData = true;
    const avgFactor = factors.reduce((a, b) => a + b, 0) / factors.length;
    const source = m.loggerSources[loggerId] || '';
    loggerNames.push(ln(loggerId) + (source ? ' (' + source + ')' : ''));
    loggerDecrement.push(+avgFactor.toFixed(3));
    loggerColors.push(m.colors[loggerId] || '#1f77b4');
    loggerIds.push(loggerId);
    loggerSources.push(source);
  }

  const traces = [{
    x: loggerNames, y: loggerDecrement, type: 'bar',
    marker: {color: loggerColors, opacity: 0.8},
    text: loggerDecrement.map(v => v.toFixed(2)),
    textposition: 'outside',
    hovertemplate: loggerNames.map((n, i) => ln(loggerIds[i]) + ' (' + loggerSources[i] + ')<br>Decrement factor: %{y:.3f}<extra></extra>'),
  }];

  // Reference line at 1.0
  const sm = window.innerWidth < 680;
  const dsl = dsLabel();
  const title = `${dsl} \u2013 ${t('betaDecrementTitle')}`;
  return {
    traces, title,
    layout: {
      autosize: true, font: {family: 'Ubuntu, sans-serif'},
      margin: {l: sm?45:65, r: sm?8:20, t: sm?30:40, b: sm?80:100},
      xaxis: {title: 'Room Logger <span style="color:#aaa">(source type)</span>', tickangle: -30, automargin: true},
      yaxis: {title: t('betaDecrementAxis'), showgrid: true, gridcolor: '#eee', range: [0, 1.05], fixedrange: true, zeroline: true},
      shapes: [{type:'line', xref:'paper', yref:'y', x0:0, x1:1, y0:1, y1:1, line:{color:'#e74c3c',width:1.5,dash:'dash'}}],
      annotations: [{x:1, y:1, xref:'paper', yref:'y', text:'1.0 = no damping', showarrow:false, font:{size:10,color:'#e74c3c'}, xanchor:'right', yanchor:'bottom'}],
      plot_bgcolor: 'white', paper_bgcolor: 'white',
      hovermode: 'closest',
    },
    _noData: !hasData,
  };
}

// ── Beta Feature 3: Thermal Lag ──────────────────────────────────────────────
function renderBetaLag() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const ext = getExternalSeries();
  if (!ext) return {traces:[], layout:{autosize:true, font:{family:'Ubuntu, sans-serif'}, annotations:[{text:'No external temperature data available',xref:'paper',yref:'paper',x:0.5,y:0.5,showarrow:false,font:{size:16,color:'#999'}}], plot_bgcolor:'white',paper_bgcolor:'white'}, title: t('betaLagTitle'), _noData: true};

  const extFiltered = filterSeries(ext.series, start, end);
  if (!extFiltered) return {traces:[], layout:{autosize:true, font:{family:'Ubuntu, sans-serif'}, annotations:[{text:t('noDataRange'),xref:'paper',yref:'paper',x:0.5,y:0.5,showarrow:false,font:{size:16,color:'#999'}}], plot_bgcolor:'white',paper_bgcolor:'white'}, title: t('betaLagTitle'), _noData: true};

  // Group external data by day, find peak hour
  const extPeakByDay = {};
  const extByDay = {};
  for (let i = 0; i < extFiltered.timestamps.length; i++) {
    const ds = toEATString(extFiltered.timestamps[i]);
    const day = ds.slice(0, 10);
    const hour = parseInt(ds.slice(11, 13), 10) + parseInt(ds.slice(14, 16), 10) / 60;
    if (!extByDay[day]) extByDay[day] = [];
    extByDay[day].push({temp: extFiltered.temperature[i], hour});
  }
  for (const day of Object.keys(extByDay)) {
    const pts = extByDay[day];
    if (pts.length < 6) continue; // need reasonable coverage
    let maxT = -Infinity, peakH = 0;
    for (const p of pts) { if (p.temp > maxT) { maxT = p.temp; peakH = p.hour; } }
    extPeakByDay[day] = peakH;
  }

  const roomSet = new Set(m.roomLoggers || []);
  const loggerNames = [], loggerLag = [], loggerColors = [], loggerIds = [], loggerSrcArr = [];
  let hasData = false;

  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    if (!roomSet.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series) continue;
    let filtered = filterSeries(series, start, end);
    if (!filtered) continue;
    filtered = applyAnomalousFilter(filtered, loggerId);
    if (!filtered) continue;

    // Group indoor data by day, find peak hour
    const indoorByDay = {};
    for (let i = 0; i < filtered.timestamps.length; i++) {
      const ds = toEATString(filtered.timestamps[i]);
      const day = ds.slice(0, 10);
      const hour = parseInt(ds.slice(11, 13), 10) + parseInt(ds.slice(14, 16), 10) / 60;
      if (!indoorByDay[day]) indoorByDay[day] = [];
      indoorByDay[day].push({temp: filtered.temperature[i], hour});
    }

    const lags = [];
    for (const day of Object.keys(indoorByDay)) {
      if (extPeakByDay[day] === undefined) continue;
      const pts = indoorByDay[day];
      if (pts.length < 6) continue;
      let maxT = -Infinity, peakH = 0;
      for (const p of pts) { if (p.temp > maxT) { maxT = p.temp; peakH = p.hour; } }
      let lag = peakH - extPeakByDay[day];
      if (lag < -12) lag += 24; // handle day-wrap
      if (lag > 12) lag -= 24;
      if (lag >= 0) lags.push(lag); // only positive lags (indoor trails outdoor)
    }

    if (lags.length === 0) continue;
    hasData = true;
    const avgLag = lags.reduce((a, b) => a + b, 0) / lags.length;
    const source = m.loggerSources[loggerId] || '';
    loggerNames.push(ln(loggerId) + (source ? ' (' + source + ')' : ''));
    loggerLag.push(+avgLag.toFixed(1));
    loggerColors.push(m.colors[loggerId] || '#1f77b4');
    loggerIds.push(loggerId);
    loggerSrcArr.push(source);
  }

  const traces = [{
    x: loggerNames, y: loggerLag, type: 'bar',
    marker: {color: loggerColors, opacity: 0.8},
    text: loggerLag.map(v => v.toFixed(1) + 'h'),
    textposition: 'outside',
    hovertemplate: loggerNames.map((n, i) => ln(loggerIds[i]) + ' (' + loggerSrcArr[i] + ')<br>Avg thermal lag: %{y:.1f} hours<extra></extra>'),
  }];

  const sm = window.innerWidth < 680;
  const dsl = dsLabel();
  const title = `${dsl} \u2013 ${t('betaLagTitle')}`;
  const maxLag = loggerLag.length > 0 ? Math.max(...loggerLag) : 1;
  const yTop = Math.ceil((maxLag * 1.15 + 0.2) * 2) / 2; // round up to nearest 0.5, with padding for text labels
  return {
    traces, title,
    layout: {
      autosize: true, font: {family: 'Ubuntu, sans-serif'},
      margin: {l: sm?45:65, r: sm?8:20, t: sm?30:40, b: sm?80:100},
      xaxis: {title: 'Room Logger <span style="color:#aaa">(source type)</span>', tickangle: -30, automargin: true},
      yaxis: {title: t('betaLagAxis'), showgrid: true, gridcolor: '#eee', range: [0, Math.max(yTop, 1)]},
      plot_bgcolor: 'white', paper_bgcolor: 'white',
      hovermode: 'closest',
    },
    _noData: !hasData,
  };
}

// ── Beta Feature 4: Data Quality ─────────────────────────────────────────────
function renderBetaQuality() {
  const m = dataset().meta;
  const {start, end} = getTimeRange();
  const traces = [];
  let hasData = false;
  let yIdx = 0;

  const GAP_THRESH = 6 * 3600 * 1000; // 6 hours

  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series || !series.timestamps || series.timestamps.length === 0) continue;
    let filtered = filterSeries(series, start, end);
    if (!filtered) continue;

    hasData = true;
    const source = m.loggerSources[loggerId] || '';
    const name = ln(loggerId);
    const nameWithSrc = name + (source ? ' (' + source + ')' : '');
    const ts = filtered.timestamps;
    const temp = filtered.temperature;
    const y = yIdx;

    // Good data segments (green blocks)
    let segStart = 0;
    for (let i = 0; i <= ts.length; i++) {
      const isGap = i === ts.length || (i > 0 && ts[i] - ts[i-1] > GAP_THRESH);
      if (isGap) {
        if (i > segStart) {
          traces.push({
            x: [toEATString(ts[segStart]), toEATString(ts[i-1])],
            y: [y, y], type: 'scatter', mode: 'lines',
            line: {color: '#27ae60', width: 8}, showlegend: false,
            hovertemplate: `${nameWithSrc}<br>Good data<br>%{x}<extra></extra>`,
          });
        }
        if (i < ts.length && i > 0) {
          // Gap segment (orange)
          const gapHours = ((ts[i] - ts[i-1]) / 3600000).toFixed(1);
          traces.push({
            x: [toEATString(ts[i-1]), toEATString(ts[i])],
            y: [y, y], type: 'scatter', mode: 'lines',
            line: {color: '#e67e22', width: 8}, showlegend: false,
            hovertemplate: `${nameWithSrc}<br>Gap: ${gapHours}h<br>%{x}<extra></extra>`,
          });
        }
        segStart = i;
      }
    }

    // Admin-flagged anomalous ranges (from CLAUDE.md / config)
    const anomRanges = m.anomalousRanges || {};
    if (anomRanges[loggerId]) {
      const rng = anomRanges[loggerId];
      const rawReason = rng.reason || 'Flagged as anomalous by admin';
      // Word-wrap reason text for hover tooltip (max ~45 chars per line)
      const reason = rawReason.replace(/(.{1,45})(\s|$)/g, '$1<br>').replace(/<br>$/, '').trim();
      // Show anomalous region as a distinct purple band
      if (rng.before) {
        const rangeStart = ts[0];
        const rangeEnd = Math.min(rng.before, ts[ts.length - 1]);
        if (rangeStart < rangeEnd) {
          traces.push({
            x: [toEATString(rangeStart), toEATString(rangeEnd)],
            y: [y, y], type: 'scatter', mode: 'lines',
            line: {color: '#8e44ad', width: 12}, opacity: 0.35, showlegend: false,
            hoverlabel: {align: 'left'},
            hovertemplate: `${nameWithSrc}<br>${t('adminFlagged')}<br>${reason}<br>%{x}<extra></extra>`,
          });
        }
      }
      if (rng.after) {
        const rangeStart = Math.max(rng.after, ts[0]);
        const rangeEnd = ts[ts.length - 1];
        if (rangeStart < rangeEnd) {
          traces.push({
            x: [toEATString(rangeStart), toEATString(rangeEnd)],
            y: [y, y], type: 'scatter', mode: 'lines',
            line: {color: '#8e44ad', width: 12}, opacity: 0.35, showlegend: false,
            hoverlabel: {align: 'left'},
            hovertemplate: `${nameWithSrc}<br>${t('adminFlagged')}<br>${reason}<br>%{x}<extra></extra>`,
          });
        }
      }
    }

    yIdx++;
  }

  // Legend entries
  traces.push({x:[null],y:[null],type:'scatter',mode:'lines',name:t('goodData'),line:{color:'#27ae60',width:8},showlegend:true,hoverinfo:'skip'});
  traces.push({x:[null],y:[null],type:'scatter',mode:'lines',name:t('gapLegend'),line:{color:'#e67e22',width:8},showlegend:true,hoverinfo:'skip'});
  // Only show admin-flagged legend if any anomalous ranges exist
  const _anomRanges = m.anomalousRanges || {};
  if (Object.keys(_anomRanges).length > 0) {
    traces.push({x:[null],y:[null],type:'scatter',mode:'lines',name:t('adminFlagged'),line:{color:'#8e44ad',width:12},opacity:0.35,showlegend:true,hoverinfo:'skip'});
  }

  // Build y-axis tick labels
  const tickVals = [], tickText = [];
  let idx = 0;
  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series || !series.timestamps || series.timestamps.length === 0) continue;
    let filtered2 = filterSeries(series, start, end);
    if (!filtered2) continue;
    const src = m.loggerSources[loggerId] || '';
    tickVals.push(idx);
    tickText.push(ln(loggerId) + (src ? ' <span style="color:#aaa">(' + src + ')</span>' : ''));
    idx++;
  }

  const sm = window.innerWidth < 680;
  const dsl = dsLabel();
  const title = `${dsl} \u2013 ${t('betaQualityTitle')}`;
  return {
    traces, title,
    layout: {
      autosize: true, font: {family: 'Ubuntu, sans-serif'},
      margin: {l: sm?120:180, r: sm?8:20, t: sm?6:10, b: sm?40:60},
      xaxis: {title: t('dateTime') + ' <i><span style="color:#aaa">(EAT, UTC+03:00)</span></i>', type: 'date', showgrid: true, gridcolor: '#eee'},
      yaxis: {tickvals: tickVals, ticktext: tickText, showgrid: false, zeroline: false, automargin: true},
      legend: {orientation: 'h', x: 0.5, y: -0.15, xanchor: 'center', itemclick: false, itemdoubleclick: false},
      plot_bgcolor: 'white', paper_bgcolor: 'white',
      hovermode: 'closest', hoverlabel: {font: {family: 'Ubuntu, sans-serif'}},
    },
    _noData: !hasData,
  };
}

function renderPeriodicAverages() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [];
  const periodicSet = new Set(m.periodicLoggers || m.lineLoggers || m.loggers);
  const MN = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const pr = state.periodCycle, pg = state.periodGroupBy;

  // Tanzanian seasons: month → season index
  // 0=Kiangazi (Jan-Feb), 1=Masika (Mar-May), 2=Kiangazi (Jun-Oct), 3=Vuli (Nov-Dec)
  const TZ_SEASON_IDX  = [0,0,1,1,1,2,2,2,2,2,3,3]; // indexed by month 0-11
  const TZ_SEASON_LABELS = ['Kiangazi (Jan\u2013Feb)','Masika (Mar\u2013May)','Kiangazi (Jun\u2013Oct)','Vuli (Nov\u2013Dec)'];

  let nCats, categoryLabels, getCategoryIdx;
  // xPositions: numeric positions for each category on x-axis (null = use categoryLabels as-is on category axis)
  let xPositions = null;
  // isClimateOsc: use markers-only for climate oscillation phases
  let isClimateOsc = (pr === 'mjo' || pr === 'iod' || pr === 'enso');

  if (pr === 'day' && pg === 'hour') {
    nCats = 24;
    categoryLabels = Array.from({length: 24}, (_, i) => String(i).padStart(2, '0') + ':00');
    getCategoryIdx = ms => eatDate(ms).getUTCHours();
  } else if (pr === 'day' && pg === 'synoptic') {
    nCats = 4;
    categoryLabels = [t('lateNight') + ' (00\u201306)', t('morning') + ' (06\u201312)', t('afternoon') + ' (12\u201318)', t('evening') + ' (18\u201300)'];
    getCategoryIdx = ms => {
      const h = eatDate(ms).getUTCHours();
      if (h < 6) return 0; if (h < 12) return 1; if (h < 18) return 2; return 3;
    };
  } else if (pr === 'year' && pg === 'month') {
    nCats = 12;
    categoryLabels = MN;
    getCategoryIdx = ms => eatDate(ms).getUTCMonth();
  } else if (pr === 'year' && pg === 'week') {
    nCats = 53;
    categoryLabels = Array.from({length: 53}, (_, i) => 'W' + (i + 1));
    getCategoryIdx = ms => {
      const d = eatDate(ms);
      const jan1 = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
      return Math.min(52, Math.floor((d - jan1) / (7 * 86400000)));
    };
  } else if (pr === 'year' && pg === 'day') {
    nCats = 366;
    categoryLabels = [];
    const daysPerMonth = [31,29,31,30,31,30,31,31,30,31,30,31];
    for (let mo = 0; mo < 12; mo++)
      for (let d = 1; d <= daysPerMonth[mo]; d++)
        categoryLabels.push(MN[mo] + ' ' + d);
    getCategoryIdx = ms => {
      const d = eatDate(ms);
      const jan1 = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
      return Math.min(365, Math.floor((d - jan1) / 86400000));
    };
  } else if (pr === 'year' && pg === 'season') {
    // Seasons positioned at temporal midpoints on a month-scale linear axis
    nCats = 4;
    categoryLabels = TZ_SEASON_LABELS;
    // Midpoints in month-units: Kiangazi Jan-Feb=0.5, Masika Mar-May=3, Kiangazi Jun-Oct=7, Vuli Nov-Dec=10.5
    xPositions = [0.5, 3, 7, 10.5];
    getCategoryIdx = ms => TZ_SEASON_IDX[eatDate(ms).getUTCMonth()];
  } else if (pr === 'mjo') {
    nCats = 8;
    categoryLabels = MJO_LABELS;
    getCategoryIdx = ms => {
      const wk = getISOWeekStr(ms);
      const ph = MJO_PHASES[wk];
      return ph != null ? ph : -1;
    };
  } else if (pr === 'iod') {
    nCats = 3;
    categoryLabels = IOD_LABELS;
    getCategoryIdx = ms => {
      const d = eatDate(ms);
      const key = d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0');
      const ph = IOD_PHASES[key];
      return ph != null ? ph : -1;
    };
  } else if (pr === 'enso') {
    nCats = 3;
    categoryLabels = ENSO_LABELS;
    getCategoryIdx = ms => {
      const d = eatDate(ms);
      const key = d.getUTCFullYear() + '-' + String(d.getUTCMonth() + 1).padStart(2, '0');
      const ph = ENSO_PHASES[key];
      return ph != null ? ph : -1;
    };
  } else {
    nCats = 24;
    categoryLabels = Array.from({length: 24}, (_, i) => String(i).padStart(2, '0') + ':00');
    getCategoryIdx = ms => eatDate(ms).getUTCHours();
  }
  // xVal: maps category index to x-axis value (linear position or category label)
  const xVal = ci => xPositions ? xPositions[ci] : categoryLabels[ci];

  if (nCats === 0) { updatePeriodicWarnings([]); return emptyPeriodicResult(); }

  // Section accumulators (typed arrays for performance)
  const sections = {
    external: {tempSum: new Float64Array(nCats), tempN: new Int32Array(nCats), humSum: new Float64Array(nCats), humN: new Int32Array(nCats)},
    room:     {tempSum: new Float64Array(nCats), tempN: new Int32Array(nCats), humSum: new Float64Array(nCats), humN: new Int32Array(nCats)},
    structural:{tempSum: new Float64Array(nCats), tempN: new Int32Array(nCats), humSum: new Float64Array(nCats), humN: new Int32Array(nCats)},
  };
  const warningInfos = [];
  let hasAnyData = false;
  let actualStartMs = Infinity, actualEndMs = -Infinity;
  const extSet = new Set(m.externalLoggers || []);
  const roomSet = new Set(m.roomLoggers || []);
  const structSet = new Set(m.structuralLoggers || []);

  // Helper: accumulate a logger's data into section avg accumulators
  function accumulateForSection(loggerId) {
    const secKey = extSet.has(loggerId) ? 'external' : roomSet.has(loggerId) ? 'room' : 'structural';
    const sec = sections[secKey];
    const series = dataset().series[loggerId];
    if (!series) return;
    let filtered = filterSeries(series, start, end);
    if (!filtered) return;
    filtered = applyAnomalousFilter(filtered, loggerId);
    if (!filtered) return;
    filtered = applySubstratFilter(filtered);
    if (!filtered) return;
    for (let i = 0; i < filtered.timestamps.length; i++) {
      const ci = getCategoryIdx(filtered.timestamps[i]);
      if (ci < 0 || ci >= nCats) continue;
      const t = filtered.temperature[i], h = filtered.humidity[i];
      if (t != null) { sec.tempSum[ci] += t; sec.tempN[ci]++; }
      if (h != null) { sec.humSum[ci] += h; sec.humN[ci]++; }
    }
  }

  // Pre-fill locked section averages from their frozen logger sets (only in non-compare mode)
  if (!state.compareEnabled) {
    for (const sk of ['external','room','structural']) {
      if (state.lockedAvg[sk]) {
        for (const lid of state.lockedAvg[sk]) {
          if (periodicSet.has(lid)) accumulateForSection(lid);
        }
      }
    }
  }

  const iterations = getCompareIterations();
  for (const iter of iterations) {
    const savedFilters = state.substratFilters;
    const savedCombine = state.substratCombine;
    state.substratFilters = iter.substratFilters;
    state.substratCombine = iter.substratCombine;
    const namePrefix = iter.setLabel ? '[' + iter.setLabel + '] ' : '';

    for (const loggerId of m.loggers) {
      if (!iter.selectedLoggers.has(loggerId)) continue;
      if (!periodicSet.has(loggerId)) continue;
      const series = dataset().series[loggerId];
      if (!series) continue;
      let filtered = filterSeries(series, start, end);
      if (!filtered) continue;
      filtered = applyAnomalousFilter(filtered, loggerId);
      if (!filtered) continue;
      filtered = applySubstratFilter(filtered);
      if (!filtered) continue;

      // Track actual data range for annotation
      const range = actualDataRange(series.timestamps, start, end);
      if (range) { actualStartMs = Math.min(actualStartMs, range[0]); actualEndMs = Math.max(actualEndMs, range[1]); }

      const tempSum = new Float64Array(nCats), tempN = new Int32Array(nCats);
      const humSum = new Float64Array(nCats), humN = new Int32Array(nCats);
      const wbSum  = new Float64Array(nCats), wbN  = new Int32Array(nCats);
      const secKey = extSet.has(loggerId) ? 'external' : roomSet.has(loggerId) ? 'room' : 'structural';
      const sec = sections[secKey];
      const contributeToAvg = !state.compareEnabled && state.lockedAvg[secKey] === null;
      const doWb = state.wetBulbEnabled && state.wetBulbLoggers.has(loggerId);

      for (let i = 0; i < filtered.timestamps.length; i++) {
        const ci = getCategoryIdx(filtered.timestamps[i]);
        if (ci < 0 || ci >= nCats) continue;
        const t = filtered.temperature[i], h = filtered.humidity[i];
        if (t != null) { tempSum[ci] += t; tempN[ci]++; if (contributeToAvg) { sec.tempSum[ci] += t; sec.tempN[ci]++; } }
        if (h != null) { humSum[ci] += h; humN[ci]++; if (contributeToAvg) { sec.humSum[ci] += h; sec.humN[ci]++; } }
        if (doWb && t != null && h != null) { const _wb = stullWetBulb(t, h); if (_wb != null) { wbSum[ci] += _wb; wbN[ci]++; } }
      }

      const color = iter.colorMap[loggerId] || m.colors[loggerId];
      const source = m.loggerSources[loggerId] || '';
      const isExtTT = extSet.has(loggerId) && source === 'TinyTag';
      const logName = namePrefix + ln(loggerId) + (isExtTT ? ' <span style="color:#aaa">(TinyTag)</span>' : '');
      const idLabel = (loggerId === 'govee' || isOpenMeteo(loggerId)) ? '' : ' \u00b7 ID: ' + loggerId;
      const lgGroup = iter.setLabel ? 'compare_s' + iter.setIndex : loggerId;
      let firstMetric = true;
      const _wbAnnotation = doWb ? ' <span style="color:#aaa">+ ' + t('wetBulbSuffix') + '</span>' : '';

      for (const metric of ['temperature', 'humidity']) {
        if (!state.selectedMetrics.has(metric)) continue;
        const sums = metric === 'temperature' ? tempSum : humSum;
        const counts = metric === 'temperature' ? tempN : humN;
        const x = [], y = [], txt = [];
        let singlePointCats = 0, catsWithData = 0;

        for (let ci = 0; ci < nCats; ci++) {
          x.push(xVal(ci));
          txt.push(categoryLabels[ci]);
          if (counts[ci] > 0) {
            y.push(+(sums[ci] / counts[ci]).toFixed(2));
            catsWithData++; hasAnyData = true;
            if (counts[ci] === 1) singlePointCats++;
          } else {
            y.push(null);
          }
        }
        if (catsWithData === 0) { firstMetric = false; continue; }

        const unit = metric === 'temperature' ? '\u00b0C' : '%RH';
        const metricName = metric === 'temperature' ? 'Avg temp' : 'Avg humidity';
        const hoverTpl = namePrefix + ln(loggerId) + '<br>%{text}<br>' + metricName + ': %{y:.1f}' + unit + '<br>' + t('source') + ': ' + source + idLabel + '<extra></extra>';
        const trace = {
          x, y, text: txt, type: 'scatter',
          name: logName + meteoSuffix(loggerId) + omniSuffix(source) + (firstMetric ? _wbAnnotation : ''),
          legendgroup: lgGroup, showlegend: (!iter.setLabel && firstMetric),
          meta: {loggerId},
          hovertemplate: hoverTpl,
        };
        if (isClimateOsc) {
          trace.mode = 'markers';
          trace.marker = {color, size: 10, line: {color: 'white', width: 1}};
        } else {
          trace.mode = 'lines+markers';
          trace.line = {color, width: 2};
          trace.marker = {size: 5};
          trace.connectgaps = false;
        }
        traces.push(trace);
        firstMetric = false;

      // Data quality warning: >50% of categories with single-point averages
      const singlePct = nCats > 0 ? singlePointCats / nCats * 100 : 0;
      if (singlePct > 50) {
        warningInfos.push({loggerId, name: ln(loggerId), metric, pct: singlePct});
      }
    }
      // Wet bulb periodic average trace
      if (doWb && state.selectedMetrics.has('temperature') && !isClimateOsc) {
        const wbX = [], wbYArr = [], wbTxt = [];
        let wbAny = false;
        for (let ci = 0; ci < nCats; ci++) {
          wbX.push(xVal(ci)); wbTxt.push(categoryLabels[ci]);
          if (wbN[ci] > 0) { wbYArr.push(+(wbSum[ci] / wbN[ci]).toFixed(2)); wbAny = true; hasAnyData = true; }
          else wbYArr.push(null);
        }
        if (wbAny) {
          const wbName = namePrefix + ln(loggerId) + ' ' + t('wetBulbSuffix');
          traces.push({
            x: wbX, y: wbYArr, text: wbTxt, type: 'scatter', mode: 'lines+markers',
            name: wbName, legendgroup: lgGroup, showlegend: false,
            meta: {loggerId},
            line: {color, width: 2, dash: 'dash'}, marker: {size: 5}, connectgaps: false,
            hovertemplate: wbName + '<br>%{text}<br>' + t('wetBulbHover') + ': %{y:.1f}°C<extra></extra>',
          });
        }
      }
  }

    // In compare mode, add a single legend entry per set
    if (iter.setLabel) {
      if (isClimateOsc) {
        traces.push({x:[null], y:[null], type:'scatter', mode:'markers',
          name: iter.legendName, marker:{color: iter.baseColor, size:12, line:{color:'white', width:1}},
          legendgroup:'compare_s' + iter.setIndex, showlegend:true, hoverinfo:'skip'});
      } else {
        traces.push({x:[null], y:[null], type:'scatter', mode:'lines+markers',
          name: iter.legendName, line:{color: iter.baseColor, width:3}, marker:{size:6},
          legendgroup:'compare_s' + iter.setIndex, showlegend:true, hoverinfo:'skip'});
      }
    }

    state.substratFilters = savedFilters;
    state.substratCombine = savedCombine;
  }

  // Section average lines (External, Room, Structural) — hidden in compare mode
  if (!state.compareEnabled) {
  const sectionDefs = [
    {key: 'external', name: t('externalAvg'), color: '#1a1a1a'},
    {key: 'room', name: t('roomAvg'), color: '#333399'},
    {key: 'structural', name: t('structuralAvg'), color: '#663300'},
  ];
  for (const sd of sectionDefs) {
    if (!state.showSectionAvg[sd.key]) continue;
    const s = sections[sd.key];
    for (const metric of ['temperature', 'humidity']) {
      if (!state.selectedMetrics.has(metric)) continue;
      const sums = metric === 'temperature' ? s.tempSum : s.humSum;
      const counts = metric === 'temperature' ? s.tempN : s.humN;
      const x = [], y = [], txt = [];
      let anyVal = false;
      for (let ci = 0; ci < nCats; ci++) {
        x.push(xVal(ci));
        txt.push(categoryLabels[ci]);
        if (counts[ci] > 0) { y.push(+(sums[ci] / counts[ci]).toFixed(2)); anyVal = true; }
        else y.push(null);
      }
      if (!anyVal) continue;
      hasAnyData = true;
      const unit = metric === 'temperature' ? '\u00b0C' : '%RH';
      const label = state.selectedMetrics.size > 1
        ? sd.name + ' (' + (metric === 'temperature' ? 'temp' : 'humidity') + ')'
        : sd.name;
      if (isClimateOsc) {
        traces.push({
          x, y, text: txt, type: 'scatter', mode: 'markers',
          name: label, marker: {color: sd.color, size: 14, symbol: 'diamond', line: {color: 'white', width: 1.5}},
          showlegend: true,
          hovertemplate: label + '<br>%{text}<br>%{y:.1f}' + unit + '<extra></extra>',
        });
      } else {
        traces.push({
          x, y, text: txt, type: 'scatter', mode: 'lines',
          name: label, line: {color: sd.color, width: 3.5, dash: '12px 4px'},
          connectgaps: false, showlegend: true,
          hovertemplate: label + '<br>%{text}<br>%{y:.1f}' + unit + '<extra></extra>',
        });
      }
    }
  }
  } // end if (!state.compareEnabled) for section averages

  // Season boundary lines for year cycle (all sub-groupings)
  const shapes = [], annotations = [];
  if (pr === 'year' && state.showSeasonLines) {
    const seasonBounds = [{ci:0, name:'Kiangazi'},{ci:2, name:'Masika'},{ci:5, name:'Kiangazi'},{ci:10, name:'Vuli'}];
    seasonBounds.forEach(s => {
      // Convert month index to x position based on grouping
      let xPos;
      if (pg === 'day') xPos = s.ci * 30.5;
      else if (pg === 'week') xPos = s.ci * (53/12);
      else xPos = s.ci; // month and season both use month-scale
      shapes.push({type:'line', xref:'x', yref:'paper', x0:xPos-0.5, x1:xPos-0.5, y0:0, y1:1,
        line:{color:'#bbb', width:1, dash:'dot'}});
      annotations.push({x:xPos, xref:'x', yref:'paper', y:1.01, yanchor:'bottom', xanchor:'left',
        text:s.name, showarrow:false, font:{size:9, color:'#888'}, textangle:-30});
    });
  }

  // 32–35°C threshold range for periodic averages
  // Only show threshold band when data approaches it, to avoid inflating y-axis
  const showThresholdBand = state.showThreshold && state.selectedMetrics.has('temperature');
  if (showThresholdBand) {
    shapes.push({type:'rect', xref:'paper', yref:'y', x0:0, x1:1, y0:32, y1:35,
      fillcolor:'rgba(231,76,60,0.12)', line:{width:0}});
  }

  updatePeriodicWarnings(warningInfos);
  updatePeriodicCompleteness(start, end);
  if (!hasAnyData) return emptyPeriodicResult();

  const hasTemp = state.selectedMetrics.has('temperature');
  const hasHum = state.selectedMetrics.has('humidity');
  const yTitle = hasTemp && hasHum ? t('tempHumidAxis') : hasTemp ? t('tempAxis') : t('humidAxis');
  const ySuffix = hasTemp && hasHum ? '' : hasTemp ? '\u00b0C' : '%RH';
  const chartTitle = hasTemp && hasHum ? t('tempAndHumid') : hasTemp ? t('tempOnly') : t('humidOnly');

  const cycleLabels = {day:t('day'), year:t('year'), mjo:'MJO', iod:'IOD', enso:'ENSO'};
  const rangeFullLabels = {day:t('day'), year:t('year'), mjo:'Madden\u2013Julian Oscillation (MJO)', iod:'Indian Ocean Dipole (IOD)', enso:'El Ni\u00f1o\u2013Southern Oscillation (ENSO)'};
  const groupByLabels = {hour:t('hour'), synoptic:'Synoptic', month:t('month'), week:t('week'), day:t('day'), season:t('season'), phase:t('phase')};
  const isOsc = pr === 'mjo' || pr === 'iod' || pr === 'enso';
  const periodLabel = isOsc ? (cycleLabels[pr] || pr) + ' ' + t('phase') : (cycleLabels[pr] || pr) + ' / ' + (groupByLabels[pg] || pg);
  const periodFullLabel = isOsc ? (rangeFullLabels[pr] || pr) : periodLabel;
  const dsl = dsLabel();
  const sm = window.innerWidth < 680;
  let xTitle;
  if (pr === 'day' && pg === 'hour') xTitle = t('hourOfDay') + ' <i><span style="color:#aaa">(EAT, UTC+03:00)</span></i>';
  else if (pr === 'day' && pg === 'synoptic') xTitle = t('timeOfDay') + ' <i><span style="color:#aaa">(EAT)</span></i>';
  else if (pr === 'year' && pg === 'month') xTitle = t('monthOfYear');
  else if (pr === 'year' && pg === 'week') xTitle = t('weekOfYear');
  else if (pr === 'year' && pg === 'day') xTitle = t('dayOfYear');
  else if (pr === 'year' && pg === 'season') xTitle = t('tanzanianSeason');
  else if (pr === 'mjo') xTitle = 'Madden\u2013Julian Oscillation (MJO) Phase';
  else if (pr === 'iod') xTitle = 'Indian Ocean Dipole (IOD) Phase';
  else if (pr === 'enso') xTitle = 'El Ni\u00f1o\u2013Southern Oscillation (ENSO) Phase';
  else xTitle = periodLabel;

  // Build x-axis config
  let xaxisCfg;
  if (xPositions) {
    // Linear axis with month ticks (for season view)
    xaxisCfg = {title: xTitle, type: 'linear', showgrid: true, gridcolor: '#eee',
      range: [-0.5, 11.5], zeroline: false,
      tickvals: [0,1,2,3,4,5,6,7,8,9,10,11], ticktext: MN,
      automargin: true};
  } else {
    const longLabels = isOsc || nCats > 15;
    xaxisCfg = {title: xTitle, type: 'category', showgrid: true, gridcolor: '#eee',
      tickangle: longLabels ? -30 : 0, automargin: true};
  }

  return {
    traces,
    layout: {
      autosize: true, font: {family: 'Ubuntu, sans-serif'},
      margin: {l: sm ? 45 : 65, r: sm ? 8 : 20, t: sm ? 20 : 36, b: sm ? 60 : 80},
      xaxis: xaxisCfg,
      yaxis: (() => {
        const cfg = {title: yTitle, ticksuffix: ySuffix, showgrid: true, gridcolor: '#eee'};
        // Prevent threshold shape from inflating y-axis when data is well below 32°C
        if (showThresholdBand && traces.length) {
          let dMax = -Infinity;
          let dMin = Infinity;
          traces.forEach(tr => { if (tr.y) tr.y.forEach(v => { if (v != null && isFinite(v)) { if (v > dMax) dMax = v; if (v < dMin) dMin = v; }});});
          if (isFinite(dMax) && dMax < 30) {
            // Data well below threshold — set range from data only with 5% padding
            const pad = (dMax - dMin) * 0.05 || 1;
            cfg.range = [dMin - pad, dMax + pad];
          }
        }
        return cfg;
      })(),
      legend: {orientation: 'v', x: 1.01, y: 1, xanchor: 'left', ...legendStyle(state.selectedLoggers.size), itemclick: false, itemdoubleclick: false},
      plot_bgcolor: 'white', paper_bgcolor: 'white',
      hovermode: 'closest', hoverlabel: {font: {family: 'Ubuntu, sans-serif'}},
      shapes, annotations: [...annotations, ...(isFinite(actualStartMs) ? [dateRangeAnnotation(actualStartMs, actualEndMs, true)] : [])],
    },
    title: (dsl + ' \u2013 ' + chartTitle + ': ' + periodFullLabel + ' Averages').replace(/&amp;/g, '&'),
  };
}

// ── Main update ───────────────────────────────────────────────────────────────
const PLOTLY_CONFIG = {
  displayModeBar:true,
  modeBarButtonsToRemove:['zoom2d','pan2d','select2d','lasso2d','zoomIn2d','zoomOut2d',
    'resetScale2d','sendDataToCloud','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines','toImage'],
  responsive:true,
};
let _loadingTimer = null;
function showLoadingBar(durationMs) {
  const overlay = document.getElementById('chart-loading');
  const bar = document.getElementById('chart-loading-bar');
  if (_loadingTimer) clearTimeout(_loadingTimer);
  bar.style.transition = 'none';
  bar.style.width = '0%';
  overlay.style.display = 'flex';
  // Kick off the fill animation on next frame
  requestAnimationFrame(() => {
    bar.style.transition = `width ${durationMs}ms linear`;
    bar.style.width = '85%';
  });
}
function hideLoadingBar() {
  const overlay = document.getElementById('chart-loading');
  const bar = document.getElementById('chart-loading-bar');
  bar.style.transition = 'width 120ms ease-out';
  bar.style.width = '100%';
  _loadingTimer = setTimeout(() => { overlay.style.display = 'none'; }, 150);
}

function _doRender() {
  let result = state.chartType === 'line' ? renderLineGraph()
    : state.chartType === 'histogram' ? renderHistogram()
    : state.chartType === 'periodic' ? renderPeriodicAverages()
    : state.chartType === 'beta-diff' ? renderBetaDifferential()
    : state.chartType === 'beta-decrement' ? renderBetaDecrement()
    : state.chartType === 'beta-lag' ? renderBetaLag()
    : state.chartType === 'beta-quality' ? renderBetaQuality()
    : renderAdaptiveComfort();
  // Replace with empty message if no actual data
  if (result._noData) {
    _zoomReset = true; // prevent stale axis range from persisting into next render with data
    const sm = window.innerWidth < 680;
    result = {
      traces: [],
      layout: {
        autosize: true, font: {family: 'Ubuntu, sans-serif'},
        margin: {l: sm ? 45 : 65, r: sm ? 8 : 20, t: sm ? 20 : 36, b: sm ? 60 : 80},
        xaxis: {showgrid: false, zeroline: false, showticklabels: false},
        yaxis: {showgrid: false, zeroline: false, showticklabels: false},
        annotations: [{text: t('noDataRange'), xref: 'paper', yref: 'paper', x: 0.5, y: 0.5, showarrow: false, font: {size: 16, color: '#999'}}],
        plot_bgcolor: 'white', paper_bgcolor: 'white',
      },
      title: result.title,
    };
  }
  const {traces, layout, title} = result;
  _currentTitle = title || '';
  _currentLayout = layout;
  document.getElementById('bar-title').textContent = _currentTitle;
  // Show "no data" overlay when substrat filters produce empty results
  const noDataEl = document.getElementById('substrat-no-data');
  const hasActiveFilters = getActiveSubstratFilters().length > 0;
  noDataEl.style.display = (hasActiveFilters && result._noData) ? 'block' : 'none';
  // Preserve user zoom: read current axis state before re-rendering
  const chartEl_ = document.getElementById('chart');
  if (!_zoomReset && chartEl_._fullLayout && traces.length > 0) {
    const fl = chartEl_._fullLayout;
    // autorange===false means the user (or we) set an explicit range via drag-zoom
    // Skip preserving zoom if the current range looks like a garbage default (e.g. 1970 epoch)
    const xRangeValid = fl.xaxis && fl.xaxis.range && !(typeof fl.xaxis.range[0] === 'string' && fl.xaxis.range[0].startsWith('1970'));
    if (fl.xaxis && fl.xaxis.autorange === false && fl.xaxis.range && xRangeValid) {
      layout.xaxis = Object.assign(layout.xaxis || {}, {range: fl.xaxis.range.slice(), autorange: false});
    }
    if (fl.yaxis && fl.yaxis.autorange === false && fl.yaxis.range) {
      layout.yaxis = Object.assign(layout.yaxis || {}, {range: fl.yaxis.range.slice(), autorange: false});
    }
  }
  _zoomReset = false;
  chartEl_.classList.toggle('comfort-mode', state.chartType === 'comfort');
  Plotly.react('chart', traces, layout, PLOTLY_CONFIG);
  chartEl_.once('plotly_afterplot', () => setTimeout(positionComfortOverlays, 100));
  chartEl_.on('plotly_doubleclick', () => { _zoomReset = true; setTimeout(updatePlot, 0); });
  const histTip = document.getElementById('hist-hover-tip');
  histTip.style.display = 'none';

  // In overlay mode, show series count only when cursor is over multiple overlapping bars
  if (state.chartType === 'histogram' && state.histogramBarmode === 'overlay') {
    // Pre-compute per-trace bin probabilities: binProbs[traceIdx][bin] = probability
    const binProbs = [];
    for (const tr of traces) {
      const probs = {};
      if (tr.type === 'histogram' && tr.x) {
        const total = tr.x.length;
        const counts = {};
        for (const v of tr.x) { const b = Math.floor(v); counts[b] = (counts[b] || 0) + 1; }
        for (const b in counts) probs[b] = counts[b] / total;
      }
      binProbs.push(probs);
    }
    chartEl_.on('plotly_hover', function(evData) {
      if (!evData.points || !evData.points.length) return;
      const pt = evData.points[0];
      const bin = Math.floor(pt.x);
      // Get cursor y in data coordinates from plot layout
      const fl = chartEl_._fullLayout;
      const yax = fl.yaxis;
      const bbox = chartEl_.getBoundingClientRect();
      const mouseY = evData.event.clientY - bbox.top;
      const plotTop = fl.margin.t;
      const plotH = fl.height - fl.margin.t - fl.margin.b;
      const yFrac = 1 - (mouseY - plotTop) / plotH;
      const cursorY = yax.range[0] + yFrac * (yax.range[1] - yax.range[0]);
      // Count traces whose bar at this bin reaches the cursor height
      let count = 0;
      for (const probs of binProbs) {
        if ((probs[bin] || 0) >= cursorY) count++;
      }
      if (count > 1) {
        histTip.textContent = count + ' series at this point';
        histTip.style.left = (evData.event.clientX - bbox.left + 12) + 'px';
        histTip.style.top = (evData.event.clientY - bbox.top + 18) + 'px';
        histTip.style.display = 'block';
        chartEl_.querySelectorAll('.hoverlayer .hovertext').forEach(el => el.style.display = 'none');
      } else {
        histTip.style.display = 'none';
      }
    });
    chartEl_.on('plotly_unhover', function() { histTip.style.display = 'none'; });
  }

  requestAnimationFrame(setupLegendTooltips);
  requestAnimationFrame(() => {
    const chartEl = document.getElementById('chart');
    unlockLegendScroll(chartEl);
    applyLegendStyleFromDOM(chartEl);
  });
  hideLoadingBar();

  const warn = document.getElementById('ext-data-warning');
  const ext = dataset().meta.extDateRange;
  if (state.chartType === 'comfort' && ext && ext.max < dataset().meta.dateRange.max && isOpenMeteo(dataset().meta.externalLogger)) {
    document.getElementById('ext-data-end').textContent = new Date(ext.max).toLocaleDateString('en-GB', {day:'numeric',month:'short',year:'numeric'});
    warn.classList.remove('hidden');
  } else {
    warn.classList.add('hidden');
  }
}

// Tracks last rendered chart type + dataset to detect slow transitions
let _lastRenderKey = null;
let _zoomReset = false; // set true by double-click or chart switch to allow autorange
let _currentTitle = '';
let _currentLayout = {};

// ── Period dropdown sync ───────────────────────────────────────────────────────
// Rebuilds the year/season/month/week/day dropdowns to only show periods that
// have actual data for the currently selected loggers, across all chart types.
let _lastDropdownKey = '';
function syncPeriodDropdowns() {
  const isComfort = state.chartType === 'comfort';
  const activeSet = isComfort ? state.selectedRoomLoggers : state.selectedLoggers;
  const key = [...activeSet].sort().join(',') + '|' + state.datasetKey;
  if (key === _lastDropdownKey) return;
  _lastDropdownKey = key;

  const EAT = 3 * 3600 * 1000;
  const TZ_SI = [0,0,1,1,1,2,2,2,2,2,3,3];
  const TZ_SN = ['Kiangazi (Jan–Feb)','Masika (Mar–May)','Kiangazi (Jun–Oct)','Vuli (Nov–Dec)'];
  const MN_LONG = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  const MN_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  const data = dataset();
  const yearsSet = new Set();
  const seasonsMap = new Map();
  const monthsMap = new Map();
  const weeksMap = new Map();
  const daysSet = new Set();

  for (const id of activeSet) {
    const s = data.series[id];
    if (!s || !s.timestamps) continue;
    for (const ts of s.timestamps) {
      const d = new Date(ts + EAT);
      const y = d.getUTCFullYear(), mo = d.getUTCMonth();
      const wkStr = getISOWeekStr(ts);
      const dashIdx = wkStr.indexOf('-W');
      const wy = parseInt(wkStr.slice(0, dashIdx)), wk = parseInt(wkStr.slice(dashIdx + 2));
      const dayMs = Math.floor((ts + EAT) / 86400000) * 86400000 - EAT;
      yearsSet.add(y);
      seasonsMap.set(`${y}-${TZ_SI[mo]}`, {y, season: TZ_SI[mo]});
      monthsMap.set(`${y}-${mo+1}`, {y, month: mo+1});
      weeksMap.set(`${wy}-${wk}`, {wy, wk});
      daysSet.add(dayMs);
    }
  }

  if (yearsSet.size === 0) return;

  const years = [...yearsSet].sort((a,b) => a-b);
  const seasons = [...seasonsMap.values()].sort((a,b) => a.y !== b.y ? a.y-b.y : a.season-b.season);
  const months = [...monthsMap.values()].sort((a,b) => a.y !== b.y ? a.y-b.y : a.month-b.month);
  const weeks = [...weeksMap.values()].sort((a,b) => a.wy !== b.wy ? a.wy-b.wy : a.wk-b.wk).map(({wy, wk}) => {
    const jan4 = new Date(Date.UTC(wy, 0, 4));
    const dow = jan4.getUTCDay() || 7;
    const ws = new Date(jan4.getTime() - (dow-1)*86400000 + (wk-1)*7*86400000);
    const dd = String(ws.getUTCDate()).padStart(2,'0');
    const mm = String(ws.getUTCMonth()+1).padStart(2,'0');
    const yy = String(ws.getUTCFullYear()).slice(-2);
    return {label: `W/s ${dd}/${mm}/${yy}`, year: wy, week: wk};
  });
  const days = [...daysSet].sort((a,b) => a-b).map(ts => {
    const d = new Date(ts + EAT);
    return {label: `${String(d.getUTCDate()).padStart(2,'0')} ${MN_SHORT[d.getUTCMonth()]} ${d.getUTCFullYear()}`, ts};
  });

  const ysel = document.getElementById('year-select');
  const ssel = document.getElementById('season-select');
  const mosel = document.getElementById('month-select');
  const wsel = document.getElementById('week-select');
  const dsel = document.getElementById('day-select');

  ysel.innerHTML = '';
  years.forEach(y => ysel.add(new Option(y, y)));
  if (state.selectedYear !== null && years.includes(state.selectedYear)) {
    ysel.value = state.selectedYear;
  } else if (years.length) {
    state.selectedYear = years[years.length-1];
    ysel.value = state.selectedYear;
  }

  ssel.innerHTML = '';
  seasons.forEach(({y, season}) => ssel.add(new Option(`${TZ_SN[season]} ${y}`, `${y}-${season}`)));
  const curSK = state.selectedSeason ? `${state.selectedSeason.year}-${state.selectedSeason.season}` : '';
  if (state.selectedSeason && seasons.some(s => `${s.y}-${s.season}` === curSK)) {
    ssel.value = curSK;
  } else if (seasons.length) {
    const last = seasons[seasons.length-1];
    state.selectedSeason = {year: last.y, season: last.season};
    ssel.value = `${last.y}-${last.season}`;
  }

  mosel.innerHTML = '';
  months.forEach(({y, month}) => mosel.add(new Option(`${MN_LONG[month-1]} ${y}`, `${y}-${month}`)));
  const curMK = state.selectedMonth ? `${state.selectedMonth.year}-${state.selectedMonth.month}` : '';
  if (state.selectedMonth && months.some(m => `${m.y}-${m.month}` === curMK)) {
    mosel.value = curMK;
  } else if (months.length) {
    const last = months[months.length-1];
    state.selectedMonth = {year: last.y, month: last.month};
    mosel.value = `${last.y}-${last.month}`;
  }

  wsel.innerHTML = '';
  weeks.forEach(({label, year, week}) => wsel.add(new Option(label, `${year}-${week}`)));
  const curWK = state.selectedWeek ? `${state.selectedWeek.year}-${state.selectedWeek.week}` : '';
  if (state.selectedWeek && weeks.some(w => `${w.year}-${w.week}` === curWK)) {
    wsel.value = curWK;
  } else if (weeks.length) {
    const last = weeks[weeks.length-1];
    state.selectedWeek = {year: last.year, week: last.week};
    wsel.value = `${last.year}-${last.week}`;
  }

  dsel.innerHTML = '';
  days.forEach(({label, ts}) => dsel.add(new Option(label, ts)));
  if (state.selectedDay !== null && days.some(d => d.ts === state.selectedDay)) {
    dsel.value = state.selectedDay;
  } else if (days.length) {
    state.selectedDay = days[days.length-1].ts;
    dsel.value = state.selectedDay;
  }
}

function updatePlot(forceLoader) {
  syncPeriodDropdowns();
  const renderKey = state.chartType + '|' + state.datasetKey;
  const isSlowOp = forceLoader || renderKey !== _lastRenderKey;
  if (renderKey !== _lastRenderKey) _zoomReset = true; // reset zoom on chart/dataset switch
  _lastRenderKey = renderKey;
  // Always show loading bar - slower estimate for chart/dataset switches, short for other updates
  const ms = isSlowOp ? (state.chartType === 'comfort' ? 1500 : state.chartType.startsWith('beta-') ? 1000 : 800) : 350;
  showLoadingBar(ms);
  setTimeout(_doRender, 30);
}

init();
// Re-render after layout settles to fix annotation positions on first load
requestAnimationFrame(() => requestAnimationFrame(() => Plotly.relayout('chart', {autosize: true})));

// Density heatmap info icon - fixed-position tooltip to escape overflow:hidden on #main
(function() {
  const icon = document.getElementById('density-info-icon');
  const tip  = document.getElementById('info-fixed-tip');
  icon.addEventListener('mouseenter', () => {
    tip.textContent = t('infoDensity');
    const r = icon.getBoundingClientRect();
    tip.style.display = 'block';
    let left = r.right + 8;
    if (left + 228 > window.innerWidth - 8) left = window.innerWidth - 236;
    tip.style.left = left + 'px';
    tip.style.top  = r.top + 'px';
  });
  icon.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
})();

// Chart type info icon - context-aware tooltip
(function() {
  const icon = document.getElementById('chart-info-icon');
  const tip  = document.getElementById('chart-info-tip');
  const textKeys = {
    line: () => t('infoLine'),
    histogram: () => state.histogramBarmode === 'stack' ? t('infoHistogramStack') : t('infoHistogramOverlay'),
    comfort: () => t('infoComfort'),
    periodic: () => t('infoPeriodic'),
    'beta-diff': () => t('infoBetaDiff'),
    'beta-decrement': () => t('infoBetaDecrement'),
    'beta-lag': () => t('infoBetaLag'),
    'beta-quality': () => t('infoBetaQuality'),
  };
  icon.addEventListener('mouseenter', () => {
    const fn = textKeys[state.chartType];
    tip.textContent = fn ? fn() : '';
    const r = icon.getBoundingClientRect();
    tip.style.display = 'block';
    let left = r.left;
    const tipW = 328;
    if (left + tipW > window.innerWidth - 8) left = window.innerWidth - tipW - 8;
    tip.style.left = Math.max(4, left) + 'px';
    tip.style.top  = (r.bottom + 6) + 'px';
  });
  icon.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
})();

// Sidebar info tooltips — Compare Mode, Long-Term Mode, comfort band, running mean
(function() {
  const items = [
    { iconId: 'compare-info-icon', tipId: 'compare-info-tip', key: 'infoCompare' },
    { iconId: 'longterm-info-icon', tipId: 'longterm-info-tip', key: 'infoLongTerm' },
    { iconId: 'wetbulb-info-icon', tipId: 'wetbulb-info-tip', key: 'infoWetBulb' },
    { iconId: 'en16798-info-icon', tipId: 'en16798-info-tip', key: 'infoComfortBand', hasLink: true },
    { iconId: 'rm-xaxis-info-icon', tipId: 'rm-xaxis-info-tip', key: 'infoRunningMean', hasLink: true },
  ];
  items.forEach(({iconId, tipId, key, hasLink}) => {
    const icon = document.getElementById(iconId);
    const tip  = document.getElementById(tipId);
    if (!icon || !tip) return;
    if (hasLink) tip.style.pointerEvents = 'auto';
    function showTip() {
      const txt = t(key);
      if (hasLink) tip.innerHTML = txt; else tip.textContent = txt;
      const r = icon.getBoundingClientRect();
      tip.style.display = 'block';
      let left = r.right + 8;
      if (left + 328 > window.innerWidth - 8) left = window.innerWidth - 336;
      tip.style.left = Math.max(4, left) + 'px';
      tip.style.top  = r.top + 'px';
    }
    icon.addEventListener('mouseenter', showTip);
    if (hasLink) {
      let hideTimer;
      const hide = () => { hideTimer = setTimeout(() => { tip.style.display = 'none'; }, 200); };
      const cancelHide = () => clearTimeout(hideTimer);
      icon.addEventListener('mouseleave', hide);
      tip.addEventListener('mouseenter', cancelHide);
      tip.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    } else {
      icon.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    }
  });
})();

// Legend hover tooltip - attach to SVG legend elements after each render
const legendTip = document.getElementById('legend-tooltip');
document.addEventListener('mousemove', e => {
  if (legendTip.style.display === 'block') {
    legendTip.style.left = (e.clientX + 12) + 'px';
    legendTip.style.top = (e.clientY - 8) + 'px';
  }
});
function setupLegendTooltips() {
  const m = dataset().meta;
  const chartEl = document.getElementById('chart');
  const plotData = (chartEl && chartEl.data) ? chartEl.data : [];
  // Match by index: nth legend entry corresponds to nth trace where showlegend !== false
  const legendTraces = plotData.filter(t => t.showlegend !== false);
  document.querySelectorAll('#chart .legendtext').forEach((el, idx) => {
    const trace = legendTraces[idx];
    if (!trace || !trace.meta || !trace.meta.loggerId) return;
    const tip = loggerTooltip(trace.meta.loggerId, m);
    if (!tip) return;
    const group = el.closest('.traces');
    if (!group) return;
    group.addEventListener('mouseenter', () => {
      legendTip.textContent = tip;
      legendTip.style.display = 'block';
    });
    group.addEventListener('mouseleave', () => {
      legendTip.style.display = 'none';
    });
  });
}
</script>
</body>
</html>"""


# ── Sensor snapshot ─────────────────────────────────────────────────────────────
OPENMETEO_IDS = {OPENMETEO_HISTORICAL_ID, OPENMETEO_FORECAST_ID, OPENMETEO_LEGACY_ID}


def save_sensor_snapshot(datasets_dfs):
    """Save non-Open-Meteo data from all datasets to sensor_snapshot.json.
    datasets_dfs: dict of {key: DataFrame} after timezone localisation.
    Excludes Open-Meteo data (fetched automatically). Omnisense data IS included
    in the snapshot as a fallback for when the automated Omnisense fetch fails."""
    snapshot = {}
    for key, df in datasets_dfs.items():
        # Exclude Open-Meteo loggers (always fetched fresh). Keep Omnisense as fallback.
        sensor_df = df[~df["logger_id"].isin(OPENMETEO_IDS)]
        loggers = {}
        for logger_id, ldf in sensor_df.groupby("logger_id"):
            loggers[logger_id] = {
                "timestamps": [t.isoformat() for t in ldf.index],
                "temperature": ldf["temperature"].round(2).tolist(),
                "humidity": ldf["humidity"].round(2).tolist(),
            }
        snapshot[key] = {"loggers": loggers}
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, separators=(",", ":")), encoding="utf-8")
    size_mb = SNAPSHOT_PATH.stat().st_size / (1024 * 1024)
    print(f"  Saved sensor snapshot → {SNAPSHOT_PATH} ({size_mb:.1f} MB)")


def load_sensor_snapshot():
    """Load sensor snapshot and reconstruct DataFrames (without Open-Meteo data)."""
    print(f"Loading sensor snapshot from {SNAPSHOT_PATH}...")
    raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    datasets_dfs = {}
    for key, ds_data in raw.items():
        dfs = []
        for logger_id, ldata in ds_data["loggers"].items():
            idx = pd.DatetimeIndex(ldata["timestamps"], name="datetime")
            # Normalise timezone to match what load_dataset() produces
            if idx.tz is not None:
                idx = idx.tz_convert(TIMEZONE)
            ldf = pd.DataFrame({
                "temperature": ldata["temperature"],
                "humidity": ldata["humidity"],
                "logger_id": logger_id,
            }, index=idx)
            dfs.append(ldf)
        if dfs:
            df = pd.concat(dfs).sort_index()
            df["iso_year"] = df.index.isocalendar().year.astype(int)
            df["iso_week"] = df.index.isocalendar().week.astype(int)
            datasets_dfs[key] = df
            print(f"  {DATASETS[key]['label']}: {len(df):,} sensor records · {df['logger_id'].nunique()} loggers")
        else:
            datasets_dfs[key] = pd.DataFrame()

    # Import loggers across datasets (e.g. 861011 from house5 into schoolteacher)
    for key, cfg in DATASETS.items():
        for logger_id, source_key in cfg.get("import_loggers", {}).items():
            if source_key not in raw or logger_id not in raw[source_key].get("loggers", {}):
                continue
            df = datasets_dfs.get(key, pd.DataFrame())
            # Skip if already present
            if not df.empty and logger_id in df["logger_id"].values:
                continue
            ldata = raw[source_key]["loggers"][logger_id]
            idx = pd.DatetimeIndex(ldata["timestamps"], name="datetime")
            if idx.tz is not None:
                idx = idx.tz_convert(TIMEZONE)
            imported = pd.DataFrame({
                "temperature": ldata["temperature"],
                "humidity": ldata["humidity"],
                "logger_id": logger_id,
            }, index=idx)
            imported["iso_year"] = imported.index.isocalendar().year.astype(int)
            imported["iso_week"] = imported.index.isocalendar().week.astype(int)
            datasets_dfs[key] = pd.concat([df, imported]).sort_index() if not df.empty else imported
            print(f"  Imported logger {logger_id} from {source_key} into {cfg['label']}")

    return datasets_dfs


# ── Loggers manifest ───────────────────────────────────────────────────────────
def generate_loggers_manifest(all_data):
    """Generate data/loggers.json: default logger names/sections/visibility for config.html."""
    manifest = {}
    for key, ds in all_data.items():
        meta = ds["meta"]
        series = ds["series"]
        ext_set     = set(meta.get("externalLoggers", []))
        room_set    = set(meta.get("roomLoggers", []))
        comfort_set = set(meta.get("comfortLoggers", []))
        has_categories = bool(room_set or meta.get("structuralLoggers"))
        
        # Valid candidates: any external logger EXCEPT forecast
        candidates = []
        for lid in meta.get("externalLoggers", []):
            if lid == OPENMETEO_FORECAST_ID:
                continue
            lname = meta["loggerNames"].get(lid, lid)
            lsrc = meta["loggerSources"].get(lid, "Unknown")
            candidates.append({
                "id": lid,
                "label": f"{lname} ({lsrc})"
            })
        
        loggers = []
        for lid in meta["loggers"]:
            if lid in ext_set:
                section = "external"
            elif lid in room_set:
                section = "room"
            else:
                section = "structural"  # above-ceiling AND below-roof both land here
            
            logger_entry = {
                "id":             lid,
                "name":           meta["loggerNames"].get(lid, lid),
                "source":         meta["loggerSources"].get(lid, "Unknown"),
                "section":        section,
                "showInLine":     True,
                "showInHistogram": True,
                "showInPeriodic": True,
                "showInComfort":  lid in comfort_set,
            }
            
            # Add currently selected external source for this logger (if applicable)
            if lid in series and "extSource" in series[lid]:
                logger_entry["external_source"] = series[lid]["extSource"]
            elif lid in comfort_set:
                logger_entry["external_source"] = meta.get("externalLogger")

            loggers.append(logger_entry)

        manifest[key] = {
            "label":           DATASETS[key]["label"],
            "hasCategories":   has_categories,
            "externalLoggers": candidates,
            "loggers":         loggers,
        }
    return manifest


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Build ARC temperature & humidity dashboard")
    parser.add_argument("--auto", "--openmeteo-only", action="store_true",
                        dest="auto",
                        help="Rebuild using sensor snapshot + fresh Open-Meteo/Omnisense data (no .xlsx sensor files needed)")
    args = parser.parse_args()

    # Load runtime user overrides from config.json (if it exists)
    user_config = {}
    config_path = DATA_FOLDER / "config.json"
    if config_path.exists():
        try:
            user_config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  Warning: could not load config.json: {e}")

    all_data = {}

    if args.auto:
        # Load pre-processed sensor data from snapshot
        if not SNAPSHOT_PATH.exists():
            print(f"ERROR: {SNAPSHOT_PATH} not found. Run a full build first.", file=sys.stderr)
            raise SystemExit(1)
        datasets_dfs = load_sensor_snapshot()

        # Load fresh Open-Meteo data and merge into each dataset's DataFrame
        print("Loading fresh Open-Meteo data...")
        ext_df_raw = load_external_temperature()
        ext_df = pd.DataFrame()
        if not ext_df_raw.empty:
            # Localise the Open-Meteo timestamps (same as load_dataset does)
            ext_df_raw["datetime"] = (
                pd.to_datetime(ext_df_raw["datetime"], errors="coerce")
                .dt.tz_localize(TIMEZONE, nonexistent="shift_forward", ambiguous="NaT")
            )
            ext_df_raw = ext_df_raw.dropna(subset=["datetime"]).set_index("datetime").sort_index()
            ext_df_raw["iso_year"] = ext_df_raw.index.isocalendar().year.astype(int)
            ext_df_raw["iso_week"] = ext_df_raw.index.isocalendar().week.astype(int)
            ext_df = ext_df_raw
            print(f"  Open-Meteo: {len(ext_df):,} records")

        # Load fresh Omnisense data (replaces snapshot Omnisense if available)
        print("Loading fresh Omnisense data...")
        omnisense_df = pd.DataFrame()
        omnisense_files = sorted(OMNISENSE_DIR.glob("omnisense_*.csv"))
        if not omnisense_files:
            omnisense_files = sorted(DATA_FOLDER.glob("omnisense_*.csv"))
        if omnisense_files:
            print(f"  Using {omnisense_files[-1].name}")
            os_df = load_omnisense_csv(omnisense_files[-1], sensor_filter=OMNISENSE_T_H_SENSORS)
            if not os_df.empty:
                # Weather Station T&RH (320E02D1): only reliable from 2026-02-17 12:00 EAT onwards
                cutoff = pd.Timestamp("2026-02-17 12:00:00")
                os_df = os_df[~((os_df["logger_id"] == "320E02D1") & (os_df["datetime"] < cutoff))]
                os_df["datetime"] = (
                    pd.to_datetime(os_df["datetime"], errors="coerce")
                    .dt.tz_localize(TIMEZONE, nonexistent="shift_forward", ambiguous="NaT")
                )
                os_df = os_df.dropna(subset=["datetime"]).set_index("datetime").sort_index()
                os_df["iso_year"] = os_df.index.isocalendar().year.astype(int)
                os_df["iso_week"] = os_df.index.isocalendar().week.astype(int)
                omnisense_df = os_df
                print(f"  Fresh Omnisense: {len(omnisense_df):,} records (replacing snapshot Omnisense)")
        else:
            print("  No fresh Omnisense CSV found, using snapshot Omnisense data as fallback.")

        for key, cfg in DATASETS.items():
            df = datasets_dfs.get(key, pd.DataFrame())
            # Only merge Open-Meteo into datasets that use it as external logger
            if cfg["external_logger"] in OPENMETEO_IDS and not ext_df.empty:
                ext_sensors = set(cfg.get("external_sensors", []))
                filtered_ext = ext_df[ext_df["logger_id"].isin(ext_sensors)] if ext_sensors else ext_df
                df = pd.concat([df, filtered_ext]).sort_index()
            # If fresh Omnisense available, replace snapshot Omnisense for house5
            if key == "house5" and not omnisense_df.empty:
                df = df[~df["logger_id"].isin(OMNISENSE_T_H_SENSORS)]
                df = pd.concat([df, omnisense_df]).sort_index()
            # Exclude loggers not belonging to this dataset
            exclude = cfg.get("exclude_loggers", set())
            if exclude:
                df = df[~df["logger_id"].isin(exclude)]
            # Apply per-logger date filters
            for logger_id, filt in cfg.get("logger_date_filters", {}).items():
                if "before" in filt:
                    cutoff = pd.Timestamp(filt["before"]).tz_localize(TIMEZONE)
                    df = df[~((df["logger_id"] == logger_id) & (df.index >= cutoff))]
                if "from" in filt:
                    cutoff = pd.Timestamp(filt["from"]).tz_localize(TIMEZONE)
                    df = df[~((df["logger_id"] == logger_id) & (df.index < cutoff))]
            print(f"Processing {cfg['label']}...")
            print(f"  {len(df):,} records · {df['logger_id'].nunique()} loggers")
            logger_overrides = user_config.get(key, {}).get("loggers", {})
            all_data[key] = build_dataset_json(key, df, logger_overrides=logger_overrides)
    else:
        # Full build: load everything from source files
        datasets_dfs = {}
        for key, cfg in DATASETS.items():
            print(f"Loading {cfg['label']}...")
            df = load_dataset(key)
            datasets_dfs[key] = df
            print(f"  {len(df):,} records · {df['logger_id'].nunique()} loggers")
            print(f"  {df.index.min().date()} → {df.index.max().date()}")
            print("  Processing...")
            logger_overrides = user_config.get(key, {}).get("loggers", {})
            all_data[key] = build_dataset_json(key, df, logger_overrides=logger_overrides)

        # Save sensor snapshot for future --auto builds
        print("Saving sensor snapshot...")
        save_sensor_snapshot(datasets_dfs)



    print("Loading climate data...")
    historic = load_copernicus_climate_data()
    historic_str = json.dumps(historic, separators=(',', ':')) if historic else 'null'

    # Determine fetch timestamps from filenames
    fetch_times = {}
    data_freshness = {}
    om_hist_files = sorted(OPENMETEO_DIR.glob("historical_*.csv"))
    om_fc_files = sorted(OPENMETEO_DIR.glob("forecast_*.csv"))
    om_file = om_hist_files[-1] if om_hist_files else (om_fc_files[-1] if om_fc_files else None)
    if om_file:
        om_dt = parse_fetch_time(om_file)
        fetch_times["openmeteo"] = format_fetch_time(om_dt)
        if om_dt:
            data_freshness["openmeteo_fetch_ms"] = int(om_dt.timestamp() * 1000)
    os_files = sorted(OMNISENSE_DIR.glob("omnisense_*.csv"))
    if not os_files:
        os_files = sorted(DATA_FOLDER.glob("omnisense_*.csv"))
    if os_files:
        os_dt = parse_fetch_time(os_files[-1])
        fetch_times["omnisense"] = format_fetch_time(os_dt)
        if os_dt:
            data_freshness["omnisense_fetch_ms"] = int(os_dt.timestamp() * 1000)
    # Cycle data fetch timestamp
    cycle_ts_files = sorted(CYCLES_DIR.glob("cycles_fetched_*.txt"))
    if cycle_ts_files:
        m = re.search(r'_(\d{8})_(\d{4})\.txt$', cycle_ts_files[-1].name)
        if m:
            cycle_dt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M")
            fetch_times["cycles"] = format_fetch_time(cycle_dt)

    # Compute last datapoint timestamps per source category from house5 data
    if "house5" in all_data:
        h5_series = all_data["house5"]["series"]
        omnisense_ids = [lid for lid in h5_series if LOGGER_SOURCES.get(lid) == "Omnisense"]
        om_hist_id = OPENMETEO_HISTORICAL_ID
        if omnisense_ids:
            data_freshness["omnisense_last_ms"] = max(
                h5_series[lid]["timestamps"][-1] for lid in omnisense_ids if h5_series[lid]["timestamps"]
            )
        if om_hist_id in h5_series and h5_series[om_hist_id]["timestamps"]:
            data_freshness["openmeteo_last_ms"] = h5_series[om_hist_id]["timestamps"][-1]

    # Compute last cycle data dates from cycle phase lookup tables
    cycle_data_files_exist = (CYCLES_DIR / "enso" / "oni.csv").exists()
    if cycle_data_files_exist:
        try:
            enso_keys = sorted(parse_enso_oni(CYCLES_DIR / "enso" / "oni.csv").keys())
            iod_keys = sorted(parse_iod_dmi(CYCLES_DIR / "iod" / "iod_1.txt").keys())
            mjo_keys = sorted(parse_mjo_romi(CYCLES_DIR / "mjo" / "romi.cpcolr.1x.txt").keys())
            # Store as ISO strings for JS to parse
            if enso_keys:
                data_freshness["enso_last"] = enso_keys[-1]  # e.g. "2026-01"
            if iod_keys:
                data_freshness["iod_last"] = iod_keys[-1]    # e.g. "2026-03"
            if mjo_keys:
                data_freshness["mjo_last"] = mjo_keys[-1]    # e.g. "2026-W10"
        except Exception:
            pass  # Cycle freshness is best-effort

    # Generate cycle phase lookup tables from data files
    cycle_phases_js = generate_cycle_phases_js()

    print("Writing output...")
    # Embed logo as base64 for PNG watermarks
    logo_path = Path("logo/logo.png")
    if logo_path.exists():
        logo_bytes = logo_path.read_bytes()
        logo_b64 = "data:image/png;base64," + base64.b64encode(logo_bytes).decode()
        logo_w = struct.unpack('>I', logo_bytes[16:20])[0]
        logo_h = struct.unpack('>I', logo_bytes[20:24])[0]
        logo_aspect = round(logo_w / logo_h, 4)
    else:
        logo_b64 = ""
        logo_aspect = 3.0

    json_str = json.dumps(all_data, separators=(',', ':'))
    fetch_times_str = json.dumps(fetch_times)
    data_freshness_str = json.dumps(data_freshness)
    html = (HTML_TEMPLATE
            .replace('__DATA__', json_str)
            .replace('__HISTORIC__', historic_str)
            .replace('__FETCH_TIMES__', fetch_times_str)
            .replace('__DATA_FRESHNESS__', data_freshness_str)
            .replace('__CYCLE_PHASES__', cycle_phases_js)
            .replace('__LOGO_B64__', logo_b64)
            .replace('__LOGO_ASPECT__', str(logo_aspect)))
    OUTPUT_FILE.write_text(html, encoding='utf-8')

    size_kb = len(html.encode('utf-8')) / 1024
    print(f"Done → {OUTPUT_FILE.resolve()}")
    print(f"File size: {size_kb:.0f} KB ({size_kb/1024:.1f} MB)")

    # Write loggers manifest for config.html
    manifest = generate_loggers_manifest(all_data)
    loggers_path = DATA_FOLDER / "loggers.json"
    loggers_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved loggers manifest → {loggers_path}")


if __name__ == '__main__':
    main()
