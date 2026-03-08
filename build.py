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
import re
import struct
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytz

DATA_FOLDER = Path("data")
OPENMETEO_DIR = DATA_FOLDER / "openmeteo"
OMNISENSE_DIR = DATA_FOLDER / "omnisense"
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
    "dauda": {
        "label": "Schoolteacher's House",
        "folder": Path("data/dauda"),
        "skip_rows": 7,
        "external_logger": "861011",
        "external_sensors": ["861011"],
        "room_loggers": None,
        "sidebar_order": ["861011", "759498", "govee"],
        # Per-logger date filters
        "logger_date_filters": {
            "759498": {"from": "2024-06-02"},  # arrived from House 5 on 2 Jun; drop Jun 1 entirely
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
    all_dfs = []
    i = 0
    while i < len(lines):
        if "sensor_desc,site_name" in lines[i]:
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

    # For House 5: also load Omnisense CSV sensors + Open-Meteo external temp
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
        ext_df = load_external_temperature()
        if not ext_df.empty:
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
    """EN 15251 exponential running mean of daily external temperatures.
    Uses primary_logger for daily means, falling back to fallback_loggers for missing days."""
    
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
        return pd.Series(dtype=float)

    # Combine: use primary if available, else fallback
    # Join on index to ensure we have all possible days
    if prim_daily.empty:
        combined = fb_daily
    elif fb_daily.empty:
        combined = prim_daily
    else:
        all_days = prim_daily.index.union(fb_daily.index)
        combined = pd.Series(index=all_days, dtype=float)
        # Fill with fallback first, then overwrite with primary where available
        combined.update(fb_daily)
        combined.update(prim_daily)
    
    combined = combined.dropna()

    if len(combined) == 0:
        return pd.Series(dtype=float)

    trm = [combined.iloc[0]]
    for i in range(1, len(combined)):
        trm.append((1 - alpha) * combined.iloc[i - 1] + alpha * trm[-1])

    trm_series = pd.Series(trm, index=combined.index, name="running_mean")
    return trm_series.resample("h").ffill()


# ── JSON builder ───────────────────────────────────────────────────────────────
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

    # comfort_loggers = room + structural (for adaptive comfort graph)
    comfort_logger_set = set(room_loggers) | set(structural_loggers)
    comfort_loggers = [l for l in unique_loggers if l in comfort_logger_set]

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

    series = {}
    for logger_id in unique_loggers:
        ldf = df[df["logger_id"] == logger_id].copy()
        if ldf.empty:
            continue
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

                rm = running_mean_cache[source_id]
                if not rm.empty:
                    merged = pd.merge_asof(
                        ldf[[]].reset_index().rename(columns={"datetime": "dt"}),
                        rm.reset_index().rename(columns={"datetime": "dt", "running_mean": "ext"}),
                        on="dt", direction="nearest",
                    )
                    entry["extTemp"] = merged["ext"].round(2).tolist()
                    entry["extSource"] = source_id

        series[logger_id] = entry

    return {
        "meta": {
            "loggers":      unique_loggers,
            "loggerNames":  logger_names,
            "loggerSources": logger_sources,
            "externalLogger": default_external_logger,
            "externalLoggers": [l for l in unique_loggers if l in ext_sensor_set],
            "forecastLoggers": [l for l in unique_loggers if l == OPENMETEO_FORECAST_ID],
            "roomLoggers":  room_loggers,
            "structuralLoggers": structural_loggers,
            "comfortLoggers": comfort_loggers,
            "lineLoggers":  unique_loggers,
            "histogramLoggers": unique_loggers,
            "colors":       color_map,
            "availableYears": available_years,
            "availableMonths": [
                {"label": f"{MONTH_NAMES[m-1]} {y}", "year": y, "month": m}
                for y, m in available_months
            ],
            "availableWeeks": [
                {"label": f"Week {w}, {y}", "year": y, "week": w}
                for y, w in available_weeks
            ],
            "availableDays": [
                {"label": d.strftime("%d %b %Y"), "ts": int(d.timestamp() * 1000)}
                for d in available_days
            ],
            "dateRange": {
                "min": int(df.index.min().timestamp() * 1000),
                "max": int(df.index.max().timestamp() * 1000),
            },
            "extDateRange": ext_date_range,
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
<title>Ecovillage Temperature &amp; Humidity</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Ubuntu:ital,wght@0,300;0,400;0,500;0,700;1,400&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Ubuntu', sans-serif; font-size: 13px; background: #f8f9fa; color: #333; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
#header { background: white; border-bottom: 1px solid #ddd; padding: 6px 12px; display: flex; align-items: center; gap: 8px; flex-shrink: 0; flex-wrap: wrap; min-height: 40px; }
#header h1 { font-size: 14px; font-weight: 600; color: #222; margin-right: 2px; white-space: nowrap; }
#logo { height: 32px; width: auto; flex-shrink: 0; }
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
.section-title { font-weight: 600; font-size: 11px; color: #666; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
.section { display: flex; flex-direction: column; gap: 2px; }
select, button, input { font-family: inherit; }
select { font-size: 12px; padding: 3px 5px; border: 1px solid #ccc; border-radius: 4px; background: white; cursor: pointer; max-width: 100%; }
select:focus { outline: none; border-color: #4a90d9; }
.cb-label { display: flex; align-items: center; gap: 5px; padding: 1px 0; cursor: pointer; line-height: 1.4; font-size: 12px; }
.cb-label:hover { color: #1f77b4; }
[data-tooltip] { position: relative; }
[data-tooltip]:hover::after { content: attr(data-tooltip); position: absolute; left: 16px; top: 100%; background: #333; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; white-space: nowrap; z-index: 100; pointer-events: none; }
.info-i { display: inline-flex; align-items: center; justify-content: center; width: 14px; height: 14px; border-radius: 50%; background: #999; color: white; font-size: 9px; font-style: italic; font-weight: 700; cursor: help; flex-shrink: 0; line-height: 1; font-family: Georgia, 'Times New Roman', serif; }
.info-i:hover { background: #666; }
#info-fixed-tip, #chart-info-tip { display:none; position:fixed; background:#333; color:white; font-size:12px; font-family:'Ubuntu',sans-serif; padding:6px 9px; border-radius:4px; line-height:1.5; width:280px; z-index:9999; pointer-events:none; white-space:normal; }
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
.room-item.has-gap { background: #f5d4a0; border-color: #d4a040; }
.room-item.has-gap:hover { background: #f0c880; border-color: #c89030; }
#gap-warning { font-size: 11px; color: #8a6d20; line-height: 1.4; margin-bottom: 6px; }
#gap-dropdown-wrap { margin-bottom: 6px; }
#gap-dropdown { font-size: 11px; width: 100%; padding: 3px 5px; border: 1px solid #d4a040; border-radius: 4px; background: #fffaf0; cursor: pointer; color: #6a5020; }
.gap-tip { display: none; position: fixed; background: #333; color: white; font-size: 11px; padding: 8px 10px; border-radius: 5px; line-height: 1.5; max-width: 280px; z-index: 9999; pointer-events: none; white-space: normal; }
.gap-tip .gap-entry { margin-bottom: 2px; }
.gap-tip .gap-more { color: #ccc; font-style: italic; margin-top: 2px; }
.gap-tip .gap-total { border-top: 1px solid #555; margin-top: 4px; padding-top: 4px; color: #f0c060; font-weight: 600; font-size: 10px; }
.hidden { display: none !important; }
.sel-btn { font-size: 10px; padding: 1px 6px; border: 1px solid #ccc; border-radius: 3px; background: #f5f5f5; cursor: pointer; color: #555; }
.sel-btn:hover { background: #e8e8e8; }
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
#sidebar-backdrop { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 9; }
@media (max-width: 900px) {
  #sidebar { width: 190px; padding: 8px; }
  #header h1 { font-size: 13px; }
}
@media (max-width: 680px) {
  #sidebar-toggle { display: block; }
  #sidebar { position: absolute; top: 0; left: 0; height: 100%; width: 300px; transform: translateX(-100%); box-shadow: 2px 0 8px rgba(0,0,0,0.15); }
  #sidebar.open { transform: translateX(0); }
  #sidebar-backdrop.open { display: block; }
  #header { padding: 5px 8px; gap: 6px; }
  #header h1 { font-size: 12px; }
  #time-bar { padding: 5px 8px; gap: 3px; }
  #time-bar-top { gap: 5px; }
  #bar-title { font-size: 12px; }
  select { font-size: 11px; }
  .cb-label { font-size: 11px; }
}
@media (max-width: 420px) {
  #header h1 { display: none; }
  #download-btn { font-size: 11px; padding: 3px 7px; }
  input[type=date] { font-size: 11px; max-width: 110px; }
}
</style>
</head>
<body>

<div id="sidebar-backdrop"></div>
<div id="header">
  <button id="sidebar-toggle" aria-label="Toggle controls">☰</button>
  <a href="https://actionresearchprojects.net"><img id="logo" src="logo.png" alt="ARC logo"></a>
  <h1>ARC Tanzania - Temperature &amp; Humidity Graphs</h1>
</div>

<div id="main">
  <div id="sidebar">
    <div id="line-controls">
      <div class="section">
        <div class="section-title" style="display:flex;align-items:center;justify-content:space-between;">Loggers<button class="sel-btn" id="reset-line-btn">Reset to default</button></div>
        <div id="logger-checkboxes"></div>
      </div>
      <hr class="divider">
      <div class="section">
        <div class="section-title">Metrics</div>
        <label class="cb-label"><input type="checkbox" id="cb-temperature" checked> Temperature</label>
        <label class="cb-label" id="humidity-label"><input type="checkbox" id="cb-humidity" checked> Humidity</label>
      </div>
      <hr class="divider">
      <div class="section" id="line-options-section">
        <div class="section-title">Options</div>
        <label class="cb-label"><input type="checkbox" id="cb-threshold" checked> 32°C Threshold</label>
        <label class="cb-label"><input type="checkbox" id="cb-seasons" checked> Season Lines</label>
      </div>
      <hr class="divider" id="line-options-divider">
      <div class="section" id="historic-section" style="display:none">
        <label class="cb-label"><input type="checkbox" id="cb-historic-mode"> <b>Long-Term Mode</b></label>
        <div id="historic-series-checkboxes" style="display:none;margin-top:4px"></div>
        <div style="font-size:10px;color:#888;margin-top:4px;line-height:1.3">Long-term historic and projected future data generated from <a href="https://atlas.climate.copernicus.eu/atlas" target="_blank" style="color:#6a9fd8">Copernicus Climate Change Service</a> information 2026.</div>
      </div>
      <hr class="divider">
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
        Hourly external temperature from <a href="https://open-meteo.com/" target="_blank" style="color:#6a9fd8">Open-Meteo</a>. Historical series drives the adaptive comfort running mean; forecast shows the next 16 days.
      </div>
    </div>

    <div id="comfort-controls" class="hidden">
      <div class="section">
        <div class="section-title">Options</div>
        <label class="cb-label"><input type="checkbox" id="cb-density" checked> Density Heatmap <span class="info-i" id="density-info-icon">i</span></label>
        <div id="info-fixed-tip"></div>
        <div style="margin-top:6px;margin-bottom:4px;">
          <div style="font-size:11px;color:#666;margin-bottom:3px;">Comfort band</div>
          <select id="comfort-model" style="width:100%;font-size:12px;">
            <option value="rh_gt_60" selected>RH&gt;60% (Vellei et al.)</option>
            <option value="rh_40_60">40%&lt;RH≤60% (Vellei et al.)</option>
            <option value="rh_le_40">RH≤40% (Vellei et al.)</option>
            <option value="default">Default comfort model</option>
            <option value="none">No comfort band</option>
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
          <option value="below_upper" selected>Below upper boundary</option>
          <option value="within">Within comfort zone</option>
          <option value="above_lower">Above lower boundary</option>
        </select>
      </div>
    </div>

    <div id="fetch-time-notes" style="font-size:10px;color:#888;line-height:1.6;margin-top:auto;padding-top:8px;border-top:1px solid #eee"></div>
  </div>

  <div id="chart-area">
    <div id="time-bar">
      <div id="time-bar-top">
        <div id="time-bar-left">
          <select id="dataset-select">
            <option value="house5">House 5</option>
            <option value="dauda">Schoolteacher's House</option>
          </select>
          <select id="chart-type">
            <option value="line">Line Graph</option>
            <option value="comfort">Adaptive Comfort</option>
            <option value="histogram">Histogram</option>
          </select>
          <span class="info-i" id="chart-info-icon">i</span>
          <div id="chart-info-tip"></div>
        </div>
        <span id="bar-title"></span>
        <div id="time-bar-right">
          <div class="control-row">
            <label>Range:</label>
            <select id="time-mode">
              <option value="all">All time</option>
              <option value="between">Between dates</option>
              <option value="year">Year</option>
              <option value="month">Month</option>
              <option value="week">Week</option>
              <option value="day">Day</option>
            </select>
          </div>
          <div id="between-inputs" class="control-row hidden">
            <label>From <input type="date" id="date-start"></label>
            <label>To <input type="date" id="date-end"></label>
          </div>
          <div id="year-input"  class="hidden"><select id="year-select"></select></div>
          <div id="month-input" class="hidden"><select id="month-select"></select></div>
          <div id="week-input"  class="hidden"><select id="week-select"></select></div>
          <div id="day-input"   class="hidden"><select id="day-select"></select></div>
          <button id="download-btn">Download PNG</button>
          <div id="dl-spinner"></div>
        </div>
      </div>
    </div>
    <div id="ext-data-warning" class="hidden" style="background:#fff3cd;border:1px solid #ffc107;border-radius:4px;padding:6px 10px;margin:4px 10px;font-size:12px;color:#856404;flex-shrink:0;">
      &#9888; Open-Meteo external temperature data only covers to <b id="ext-data-end"></b>. Update <code>open-meteo</code> CSV to see adaptive comfort for recent dates.
    </div>
    <div id="chart"></div>
    <div id="chart-loading" style="display:none;position:absolute;inset:0;background:rgba(255,255,255,0.82);z-index:50;flex-direction:column;align-items:center;justify-content:center;gap:10px;pointer-events:none;">
      <div style="font-size:12px;color:#555;font-family:'Ubuntu',sans-serif">Loading chart…</div>
      <div style="width:160px;height:5px;background:#e0e0e0;border-radius:3px;overflow:hidden;">
        <div id="chart-loading-bar" style="height:100%;width:0%;background:#4a90d9;border-radius:3px;transition:none;"></div>
      </div>
    </div>
    <div id="legend-tooltip" style="display:none;position:fixed;background:#333;color:white;padding:3px 8px;border-radius:3px;font-size:10px;white-space:nowrap;z-index:200;pointer-events:none;"></div>
  </div>
</div>

<script>
const ALL_DATA = __DATA__;
const HISTORIC = __HISTORIC__;
const FETCH_TIMES = __FETCH_TIMES__;
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
  betweenStart: null,
  betweenEnd: null,
  selectedYear: null,
  selectedMonth: null,
  selectedWeek: null,
  selectedDay: null,
};

function dataset() { return ALL_DATA[state.datasetKey]; }

function isOpenMeteo(id) { return id && id.indexOf('(Open-Meteo)') !== -1; }
function isForecast(id) { return id && id.indexOf('Forecast') !== -1 && isOpenMeteo(id); }

function loggerTooltip(id, m) {
  const src = (m.loggerSources && m.loggerSources[id]) || '';
  let tip = (id === 'govee' || isOpenMeteo(id)) ? src : (src ? `${src} · ${id}` : id);
  const series = dataset().series[id];
  if (series && series.extSource) {
    const sName = m.loggerNames[series.extSource] || series.extSource;
    tip += `\nAdaptive source: ${sName}`;
  }
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
        if (ov.section === 'room') meta.roomLoggers.push(lid);
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
    }
  }
}

// ── Initialise ────────────────────────────────────────────────────────────────
async function init() {
  // Load runtime user config (logger name/category overrides)
  const userConfig = await loadUserConfig();
  applyUserConfig(userConfig);

  // Populate data freshness notes
  const ftDiv = document.getElementById('fetch-time-notes');
  if (ftDiv && (FETCH_TIMES.openmeteo || FETCH_TIMES.omnisense)) {
    const lines = [];
    if (FETCH_TIMES.openmeteo) lines.push(`Open-Meteo last updated: ${FETCH_TIMES.openmeteo}`);
    if (FETCH_TIMES.omnisense) lines.push(`Omnisense last updated: ${FETCH_TIMES.omnisense}`);
    ftDiv.innerHTML = lines.join('<br>');
  }
  setupStaticListeners();
  loadDataset('house5');
}

function loadDataset(key) {
  state.datasetKey = key;
  const m = dataset().meta;

  // Reset selections
  state.selectedLoggers = new Set(m.lineLoggers || m.loggers);
  state.selectedRoomLoggers = new Set(m.roomLoggers);
  state.timeMode = 'all';
  document.getElementById('time-mode').value = 'all';
  ['between-inputs','year-input','month-input','week-input','day-input'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));

  // Rebuild logger checkboxes: External / Structural / Room - each with their own buttons
  const loggerDiv = document.getElementById('logger-checkboxes');
  loggerDiv.innerHTML = '';
  function mkSelBtn(label, onClick) {
    const b = document.createElement('button');
    b.className = 'sel-btn'; b.textContent = label;
    b.addEventListener('click', onClick); return b;
  }
  // Generic checkbox + section builder for both line/histogram and comfort sidebars
  function addCheckbox(container, stateSet, id, extraLabel) {
    const lbl = document.createElement('label');
    lbl.className = 'cb-label';
    lbl.dataset.tooltip = loggerTooltip(id, m);
    lbl.innerHTML = `<input type="checkbox" data-logger-id="${id}" ${stateSet.has(id) ? 'checked' : ''}> <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${m.colors[id]};vertical-align:middle"></span> ${m.loggerNames[id]}${meteoSuffix(id)}${omniSuffix(m.loggerSources[id] || '')}${extraLabel || ''}`;
    lbl.querySelector('input').addEventListener('change', e => {
      e.target.checked ? stateSet.add(id) : stateSet.delete(id);
      updatePlot();
    });
    container.appendChild(lbl);
  }
  function addSection(container, stateSet, title, ids, extraBtns, extraLabelFn) {
    if (ids.length === 0) return;
    const titleEl = document.createElement('div');
    titleEl.className = 'sub-section-title';
    titleEl.textContent = title;
    container.appendChild(titleEl);
    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex;gap:4px;margin-bottom:4px;flex-wrap:wrap;';
    btnRow.appendChild(mkSelBtn('All', () => {
      ids.forEach(id => { stateSet.add(id); container.querySelector(`input[data-logger-id="${id}"]`).checked = true; });
      updatePlot();
    }));
    btnRow.appendChild(mkSelBtn('None', () => {
      ids.forEach(id => { stateSet.delete(id); container.querySelector(`input[data-logger-id="${id}"]`).checked = false; });
      updatePlot();
    }));
    if (extraBtns) extraBtns.forEach(b => btnRow.appendChild(b));
    container.appendChild(btnRow);
    ids.forEach(id => addCheckbox(container, stateSet, id, extraLabelFn ? extraLabelFn(id) : ''));
  }
  function mkSourceBtns(container, stateSet, ids) {
    const hasTT = ids.some(id => m.loggerSources[id] === 'TinyTag');
    const hasOS = ids.some(id => m.loggerSources[id] === 'Omnisense');
    if (!hasTT || !hasOS) return null;
    return [
      mkSelBtn('TinyTag',  () => { ids.forEach(id => { const is = m.loggerSources[id]==='TinyTag';  is ? stateSet.add(id) : stateSet.delete(id); container.querySelector(`input[data-logger-id="${id}"]`).checked = is; }); updatePlot(); }),
      mkSelBtn('Omnisense',() => { ids.forEach(id => { const is = m.loggerSources[id]==='Omnisense'; is ? stateSet.add(id) : stateSet.delete(id); container.querySelector(`input[data-logger-id="${id}"]`).checked = is; }); updatePlot(); }),
    ];
  }
  const extSet   = new Set(m.externalLoggers || []);
  const roomSet  = new Set(m.roomLoggers || []);
  const lineSet  = new Set(m.lineLoggers || m.loggers);
  const midLoggers  = m.loggers.filter(id => !extSet.has(id) && !roomSet.has(id) && lineSet.has(id));
  const roomLoggers = m.loggers.filter(id => !extSet.has(id) &&  roomSet.has(id) && lineSet.has(id));
  const extTTLabel = id => (extSet.has(id) && m.loggerSources[id] === 'TinyTag') ? '<span style="color:#aaa"> (TinyTag)</span>' : '';
  // External section
  if (m.externalLoggers && m.externalLoggers.length > 0) {
    addSection(loggerDiv, state.selectedLoggers, 'External', m.externalLoggers, null, extTTLabel);
    const hr = document.createElement('hr'); hr.className = 'divider'; loggerDiv.appendChild(hr);
  }
  // Room loggers section
  if (roomLoggers.length > 0) {
    addSection(loggerDiv, state.selectedLoggers, 'Room', roomLoggers, mkSourceBtns(loggerDiv, state.selectedLoggers, roomLoggers));
  }
  // Structural section
  if (midLoggers.length > 0) {
    if (roomLoggers.length > 0) { const hr = document.createElement('hr'); hr.className = 'divider'; loggerDiv.appendChild(hr); }
    addSection(loggerDiv, state.selectedLoggers, 'Structural', midLoggers, mkSourceBtns(loggerDiv, state.selectedLoggers, midLoggers));
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
  addSection(roomDiv, state.selectedRoomLoggers, 'Room', comfortRoomIds, mkSourceBtns(roomDiv, state.selectedRoomLoggers, comfortRoomIds));
  if (comfortStructIds.length > 0) {
    if (comfortRoomIds.length > 0) { const hr = document.createElement('hr'); hr.className = 'divider'; roomDiv.appendChild(hr); }
    addSection(roomDiv, state.selectedRoomLoggers, 'Structural', comfortStructIds, mkSourceBtns(roomDiv, state.selectedRoomLoggers, comfortStructIds));
  }

  // Show historic section if data available
  document.getElementById('historic-section').style.display = HISTORIC ? '' : 'none';

  // Rebuild time dropdowns
  const ysel = document.getElementById('year-select');
  const mosel = document.getElementById('month-select');
  const wsel = document.getElementById('week-select');
  const dsel = document.getElementById('day-select');
  ysel.innerHTML = ''; mosel.innerHTML = ''; wsel.innerHTML = ''; dsel.innerHTML = '';

  m.availableYears.forEach(y => ysel.add(new Option(y, y)));
  m.availableMonths.forEach(({label, year, month}) => mosel.add(new Option(label, `${year}-${month}`)));
  m.availableWeeks.forEach(({label, year, week}) => wsel.add(new Option(label, `${year}-${week}`)));
  m.availableDays.forEach(({label, ts}) => dsel.add(new Option(label, ts)));

  // Set defaults to last available
  const fmt = ms => new Date(ms).toISOString().slice(0, 10);
  document.getElementById('date-start').value = fmt(m.dateRange.min);
  document.getElementById('date-end').value = fmt(m.dateRange.max);
  state.betweenStart = m.dateRange.min;
  state.betweenEnd = m.dateRange.max;

  if (m.availableYears.length) {
    state.selectedYear = m.availableYears[m.availableYears.length - 1];
    ysel.value = state.selectedYear;
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

  updatePlot();
}

// ── Default-reset helpers ──────────────────────────────────────────────────────
function resetTimeMode() {
  state.timeMode = 'all';
  document.getElementById('time-mode').value = 'all';
  ['between-inputs','year-input','month-input','week-input','day-input'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));
}

function resetLineDefaults() {
  const m = dataset().meta;
  if (state.historicMode) {
    state.selectedLoggers = new Set();
    m.loggers.forEach(lid => { if (isOpenMeteo(lid)) state.selectedLoggers.add(lid); });
  } else {
    state.selectedLoggers = new Set(m.lineLoggers || m.loggers);
  }
  document.getElementById('logger-checkboxes').querySelectorAll('input[data-logger-id]').forEach(cb => {
    cb.checked = state.selectedLoggers.has(cb.dataset.loggerId);
  });
  resetTimeMode();
  updatePlot();
}

function resetComfortDefaults() {
  const m = dataset().meta;
  state.selectedRoomLoggers = new Set(m.roomLoggers);
  document.getElementById('room-logger-checkboxes').querySelectorAll('input[data-logger-id]').forEach(cb => {
    cb.checked = state.selectedRoomLoggers.has(cb.dataset.loggerId);
  });
  state.comfortModel = 'rh_gt_60';
  document.getElementById('comfort-model').value = 'rh_gt_60';
  state.comfortPctMode = 'below_upper';
  document.getElementById('comfort-pct-mode').value = 'below_upper';
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
  const line1 = 'Graph generated by ARC (architecture.resilience.community).';
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

  document.getElementById('dataset-select').addEventListener('change', e => {
    loadDataset(e.target.value);
  });

  document.getElementById('chart-type').addEventListener('change', e => {
    const prevType = state.chartType;
    state.chartType = e.target.value;
    const isLine = state.chartType === 'line';
    const isHistogram = state.chartType === 'histogram';
    const isComfort = state.chartType === 'comfort';
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
    document.getElementById('line-controls').classList.toggle('hidden', isComfort);
    document.getElementById('comfort-controls').classList.toggle('hidden', !isComfort);
    document.getElementById('histogram-stats').classList.toggle('hidden', !isHistogram);
    if (isHistogram) {
      // Show options but hide season lines checkbox (not applicable to histogram)
      document.getElementById('line-options-section').style.display = '';
      document.getElementById('line-options-divider').style.display = '';
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
    updatePlot();
  });

  document.getElementById('comfort-model').addEventListener('change', e => {
    state.comfortModel = e.target.value; updatePlot();
  });

  document.getElementById('comfort-pct-mode').addEventListener('change', e => {
    state.comfortPctMode = e.target.value; updatePlot();
  });

  document.getElementById('time-mode').addEventListener('change', e => {
    state.timeMode = e.target.value;
    ['between-inputs','year-input','month-input','week-input','day-input'].forEach(id =>
      document.getElementById(id).classList.add('hidden'));
    const map = {between:'between-inputs',year:'year-input',month:'month-input',week:'week-input',day:'day-input'};
    if (map[state.timeMode]) document.getElementById(map[state.timeMode]).classList.remove('hidden');
    updatePlot();
  });

  document.getElementById('date-start').addEventListener('change', e => {
    state.betweenStart = new Date(e.target.value + 'T00:00:00').getTime(); updatePlot();
  });
  document.getElementById('date-end').addEventListener('change', e => {
    state.betweenEnd = new Date(e.target.value + 'T23:59:59').getTime(); updatePlot();
  });
  document.getElementById('year-select').addEventListener('change', e => {
    state.selectedYear = parseInt(e.target.value); updatePlot();
  });
  document.getElementById('month-select').addEventListener('change', e => {
    const [y, mo] = e.target.value.split('-').map(Number);
    state.selectedMonth = {year: y, month: mo}; updatePlot();
  });
  document.getElementById('week-select').addEventListener('change', e => {
    const [y, w] = e.target.value.split('-').map(Number);
    state.selectedWeek = {year: y, week: w}; updatePlot();
  });
  document.getElementById('day-select').addEventListener('change', e => {
    state.selectedDay = parseInt(e.target.value); updatePlot();
  });

  document.getElementById('cb-temperature').addEventListener('change', e => {
    e.target.checked ? state.selectedMetrics.add('temperature') : state.selectedMetrics.delete('temperature');
    updatePlot();
  });
  document.getElementById('cb-humidity').addEventListener('change', e => {
    e.target.checked ? state.selectedMetrics.add('humidity') : state.selectedMetrics.delete('humidity');
    updatePlot();
  });
  document.getElementById('cb-threshold').addEventListener('change', e => {
    state.showThreshold = e.target.checked; updatePlot();
  });
  document.getElementById('cb-seasons').addEventListener('change', e => {
    state.showSeasonLines = e.target.checked; updatePlot();
  });
  document.getElementById('cb-density').addEventListener('change', e => {
    state.showDensity = e.target.checked; updatePlot();
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
  let _historicEnteredOnce = false;
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
      // First entry only: force loggers to Open-Meteo only
      if (!_historicEnteredOnce) {
        _historicEnteredOnce = true;
        state.selectedLoggers = new Set();
        m.loggers.forEach(lid => { if (isOpenMeteo(lid)) state.selectedLoggers.add(lid); });
        document.getElementById('logger-checkboxes').querySelectorAll('input[type=checkbox]').forEach(cb => {
          cb.checked = state.selectedLoggers.has(cb.dataset.loggerId);
        });
      }
      // Line-graph only: hide options section, turn off threshold/seasons
      if (state.chartType !== 'histogram') {
        cbThreshold.checked = false; state.showThreshold = false;
        cbSeasons.checked = false;   state.showSeasonLines = false;
        document.getElementById('line-options-section').style.display = 'none';
        document.getElementById('line-options-divider').style.display = 'none';
      }
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
        state.selectedLoggers = s.loggers;
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
        ['between-inputs','year-input','month-input','week-input','day-input'].forEach(id =>
          document.getElementById(id).classList.add('hidden'));
        const modeInputMap = {between:'between-inputs', year:'year-input', month:'month-input', week:'week-input', day:'day-input'};
        if (modeInputMap[s.timeMode]) document.getElementById(modeInputMap[s.timeMode]).classList.remove('hidden');
      }
      // Universal: show humidity label
      document.getElementById('humidity-label').style.display = '';
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
    rebuildYearDropdown(); updatePlot();
  });

  document.getElementById('download-btn').addEventListener('click', () => {
    const btn = document.getElementById('download-btn');
    const spinner = document.getElementById('dl-spinner');
    function dlStart() { btn.disabled = true; spinner.style.display = 'inline-block'; }
    function dlDone()  { btn.disabled = false; spinner.style.display = 'none'; }

    const dsSel = document.getElementById('dataset-select');
    const ds = dsSel.options[dsSel.selectedIndex].text;
    const chart = state.chartType === 'line' ? 'Line' : state.chartType === 'histogram' ? 'Histogram' : 'AdaptiveComfort';
    let rangeStr = 'AllTime';
    const m = dataset().meta;
    const fmtDate = ms => new Date(ms).toISOString().slice(0,10);
    switch (state.timeMode) {
      case 'between': rangeStr = `${fmtDate(state.betweenStart||m.dateRange.min)}_to_${fmtDate(state.betweenEnd||m.dateRange.max)}`; break;
      case 'year': rangeStr = `${state.selectedYear}`; break;
      case 'month': if (state.selectedMonth) rangeStr = `${state.selectedMonth.year}-${String(state.selectedMonth.month).padStart(2,'0')}`; break;
      case 'week': if (state.selectedWeek) rangeStr = `${state.selectedWeek.year}-W${String(state.selectedWeek.week).padStart(2,'0')}`; break;
      case 'day': if (state.selectedDay) rangeStr = fmtDate(state.selectedDay); break;
    }
    let modelStr = '';
    if (state.chartType === 'comfort') {
      const modelSel = document.getElementById('comfort-model');
      modelStr = '_' + modelSel.options[modelSel.selectedIndex].text.replace(/\(Vellei et al\.\)/gi,'').replace(/[^a-zA-Z0-9%<>≤]/g,'').slice(0,20);
    }
    let metricStr = '';
    if (state.chartType === 'line' || state.chartType === 'histogram') {
      const metrics = [];
      if (state.selectedMetrics.has('temperature')) metrics.push('T');
      if (state.selectedMetrics.has('humidity')) metrics.push('RH');
      metricStr = '_' + metrics.join('+');
    }
    const slug = s => s.replace(/[^a-zA-Z0-9]+/g, '_').replace(/_+$/,'');
    // Sensor selection: name 1–2 selected sensors, count if a partial subset, omit if all selected
    let sensorStr = '';
    if (state.chartType === 'line' || state.chartType === 'histogram') {
      const selIds = [...state.selectedLoggers];
      const total = m.loggers.length;
      if (selIds.length === 0) sensorStr = '_NoSensors';
      else if (selIds.length <= 2) sensorStr = '_' + selIds.map(id => slug(m.loggerNames[id] || id)).join('+');
      else if (selIds.length < total) sensorStr = `_${selIds.length}of${total}sensors`;
    } else if (state.chartType === 'comfort') {
      const selIds = [...state.selectedRoomLoggers];
      const total = (m.comfortLoggers || m.roomLoggers).length;
      if (selIds.length === 0) sensorStr = '_NoSensors';
      else if (selIds.length <= 2) sensorStr = '_' + selIds.map(id => slug(m.loggerNames[id] || id)).join('+');
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
    // Shared: append grey ID codes next to legend items in an exported SVG doc
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
        // Convert existing plain-text content into a tspan so we can append alongside it
        const existing = textEl.textContent;
        while (textEl.firstChild) textEl.removeChild(textEl.firstChild);
        const t1 = doc.createElementNS(ns, 'tspan');
        t1.textContent = existing;
        textEl.appendChild(t1);
        const t2 = doc.createElementNS(ns, 'tspan');
        t2.setAttribute('fill', '#aaaaaa');
        t2.setAttribute('font-size', '0.85em');
        t2.textContent = ' \u00B7 ' + lid;
        textEl.appendChild(t2);
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
    if (state.chartType === 'line') {
      // No relayout for line graph - inject title + watermark directly into SVG.
      Plotly.toImage('chart', {format: 'svg', width: W, height: H}).then(svgDataUrl => {
        const doc = new DOMParser().parseFromString(parseSVGDataUrl(svgDataUrl), 'image/svg+xml');
        injectSVGTitle(doc, W);
        injectSVGWatermark(doc, W, H, 1.0);
        injectLegendIDCodes(doc);
        unlockLegendScroll(doc.documentElement);
        return svgToCanvas(new XMLSerializer().serializeToString(doc), W, H, scale);
      }).then(canvasToPNG).catch(dlDone);
    } else {
      // Histogram / adaptive comfort: add title via relayout, capture as SVG,
      // inject watermark into SVG DOM, render to canvas, restore.
      const isComfort = state.chartType === 'comfort';
      const pngTopMargin = isComfort ? (sm ? 36 : 60) : (sm ? 55 : 85);
      const origAnnotations = _currentLayout.annotations || [];
      const origImages = _currentLayout.images || [];
      const origMarginT = (_currentLayout.margin && _currentLayout.margin.t) || 50;
      function doRestore() {
        Plotly.relayout('chart', {
          'title.text': '', 'margin.t': origMarginT,
          images: origImages, annotations: origAnnotations,
        });
      }
      Plotly.relayout('chart', {
        'title.text': `<b>${_currentTitle}</b>`,
        'title.font.size': sm ? 12 : 14,
        'margin.t': pngTopMargin,
      }).then(() => {
        return Plotly.toImage('chart', {format: 'svg', width: W, height: H});
      }).then(svgDataUrl => {
        doRestore();
        const doc = new DOMParser().parseFromString(parseSVGDataUrl(svgDataUrl), 'image/svg+xml');
        injectSVGWatermark(doc, W, H, isComfort ? 0.8 : 1.0);
        if (!isComfort) {
          injectLegendIDCodes(doc);
          unlockLegendScroll(doc.documentElement);
        } else {
          injectLegendIDCodes(doc);
          expandHorizontalLegendSpacing(doc.documentElement, 80);
        }
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
    Plotly.relayout('chart', {autosize: true});
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

  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    if (!lineSet.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series) continue;
    const filtered = filterSeries(series, start, end);
    if (!filtered) continue;

    // Track actual data bounds
    if (filtered.timestamps.length) {
      const first = filtered.timestamps[0], last = filtered.timestamps[filtered.timestamps.length - 1];
      if (first < dataMinMs) dataMinMs = first;
      if (last > dataMaxMs) dataMaxMs = last;
    }

    const color = m.colors[loggerId];
    const isExtTT = extSet.has(loggerId) && m.loggerSources[loggerId] === 'TinyTag';
    const name = m.loggerNames[loggerId] + (isExtTT ? ' <span style="color:#aaa">(TinyTag)</span>' : '');
    const source = m.loggerSources[loggerId] || '';
    const idLabel = (loggerId === 'govee' || isOpenMeteo(loggerId)) ? '' : ` · ID: ${loggerId}`;
    const freqLabel = state.historicMode
      ? (isOpenMeteo(loggerId) ? ' <span style="color:#aaa">(hourly avg.)</span>'
        : source === 'TinyTag' ? ' <span style="color:#aaa">(hourly avg.)</span>'
        : source === 'Omnisense' ? ' <span style="color:#aaa">(5-min avg.)</span>'
        : '') : '';
    let firstMetric = true;
    for (const metric of ['temperature','humidity']) {
      if (!state.selectedMetrics.has(metric)) continue;
      const {x, y} = buildGapArrays(filtered.timestamps, filtered[metric]);
      for (const v of y) { if (v != null) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; } }
      const unit = metric === 'temperature' ? '°C' : '%RH';
      traces.push({x, y, type:'scatter', mode:'lines', name: name + meteoSuffix(loggerId) + omniSuffix(source) + freqLabel, line:{color, width:1.4},
        opacity:0.35, connectgaps:false, legendgroup:loggerId, showlegend:firstMetric, meta:{loggerId},
        hovertemplate:`${name}<br>%{x|%d/%m/%Y %H:%M}<br>${metric==='temperature'?'Temp':'Humidity'}: %{y:.1f}${unit}<br>Source: ${source}${idLabel}<extra></extra>`});
      firstMetric = false;
    }
  }

  // Fall back to time filter range if no data traces
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

  // Threshold and season lines adapt to the full data range
  if (state.showThreshold) {
    traces.push({x:[new Date(dataMinMs),new Date(dataMaxMs)], y:[32,32], type:'scatter', mode:'lines',
      name:'32°C Threshold', line:{color:'#e74c3c', width:1.5, dash:'dot'},
      hovertemplate:'32°C Threshold<extra></extra>'});
  }

  if (state.showSeasonLines) {
    const seasons = getSeasonBoundaries(dataMinMs, dataMaxMs);
    seasons.forEach(s => {
      shapes.push({type:'line', xref:'x', yref:'paper', x0:new Date(s.ts), x1:new Date(s.ts), y0:0, y1:1, line:{color:'#bbb', width:1, dash:'dot'}});
      annotations.push({x:new Date(s.ts), xref:'x', yref:'paper', y:1.01, yanchor:'bottom', xanchor:'left', text:s.name, showarrow:false, font:{size:9, color:'#888'}, textangle:-30});
    });
  }

  // Climate data traces (ERA5 historic + SSP projections)
  if (showingHistoric) {
    // Narrow view (year/month/week/day or between ≤1 year): expand each annual point to span
    // Jan 1→Dec 31 so a single-year zoom shows a horizontal line instead of an invisible dot.
    // Wide view (all time, multi-year between): use original single-point-per-year connected line.
    const ONE_YEAR_MS = 365.25 * 24 * 3600 * 1000;
    const narrowView = state.timeMode === 'year' || state.timeMode === 'month' ||
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
  const yTitle  = hasTemp && hasHum ? 'Temperature (\u00b0C) / Humidity (%RH)' : hasTemp ? 'Temperature (\u00b0C)' : 'Humidity (%RH)';
  const ySuffix = hasTemp && hasHum ? '' : hasTemp ? '\u00b0C' : '%RH';
  const chartTitle = hasTemp && hasHum ? 'Temperature &amp; Humidity' : hasTemp ? 'Temperature' : 'Humidity';
  const dsl = dsLabel();
  const sm = window.innerWidth < 680;

  const plotTitle = state.historicMode
    ? 'Dar es Salaam \u2013 Historic and Projected Temperatures'
    : `${dsl} \u2013 ${chartTitle}`;
  const barTitle = plotTitle.replace(/&amp;/g, '&');
  return {traces, layout: {
    autosize:true, font:{family:'Ubuntu, sans-serif'}, margin:{l:sm?45:65, r:sm?8:20, t:state.showSeasonLines?(sm?70:85):(sm?6:10), b:sm?40:60},
    xaxis:{title:'Date / Time <i><span style="color:#aaa">(EAT, UTC+03:00)</span></i>', type:'date', showgrid:true, gridcolor:'#eee', range: state.timeMode === 'all' ? [toEATString(dataMinMs), toEATString(dataMaxMs)] : [toEATString(start), toEATString(end)],
      nticks:20, tickangle:-30, automargin:true},
    yaxis:{title:yTitle, ticksuffix:ySuffix, showgrid:true, gridcolor:'#eee', range: yLo !== undefined ? [yLo, yHi] : undefined},
    legend:{orientation:'v', x:1.01, y:1, xanchor:'left', ...legendStyle(state.selectedLoggers.size), itemclick:false, itemdoubleclick:false},
    plot_bgcolor:'white', paper_bgcolor:'white', shapes, annotations, hovermode:'closest', hoverlabel:{font:{family:'Ubuntu, sans-serif'}},
  }, title: barTitle};
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
function dateRangeAnnotation(actualStartMs, actualEndMs, atTop) {
  return {
    xref: 'paper', yref: 'paper',
    x: 1, y: atTop ? 1 : 0,
    xanchor: 'right', yanchor: atTop ? 'top' : 'bottom',
    text: `Data ranges from ${fmtDateEAT(actualStartMs, true)} to ${fmtDateEAT(actualEndMs, false)}`,
    showarrow: false,
    font: {size: 10, color: '#888'},
    bgcolor: 'rgba(255,255,255,0.75)',
    borderpad: 3,
  };
}

// ── Histogram ────────────────────────────────────────────────────────────────
function renderHistogram() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [];
  let globalMin = Infinity, globalMax = -Infinity;
  let actualStartMs = Infinity, actualEndMs = -Infinity;
  const histSet = new Set(m.histogramLoggers || m.loggers);

  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    if (!histSet.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series) continue;
    const filtered = filterSeries(series, start, end);
    if (!filtered) continue;
    const range = actualDataRange(series.timestamps, start, end);
    if (range) { actualStartMs = Math.min(actualStartMs, range[0]); actualEndMs = Math.max(actualEndMs, range[1]); }

    const color = m.colors[loggerId];
    const source = m.loggerSources[loggerId] || '';
    const isExtTT = (m.externalLoggers || []).includes(loggerId) && source === 'TinyTag';
    const name = m.loggerNames[loggerId] + (isExtTT ? ' <span style="color:#aaa">(TinyTag)</span>' : '');
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
        marker: {color, opacity: 0.85},
        legendgroup: loggerId,
        showlegend: firstMetric,
        meta: {loggerId},
        hovertemplate: `${name}<br>%{x:.1f}${unit}: %{y:.1%} of readings<extra></extra>`,
      });
      firstMetric = false;
    }
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
        marker: {color, opacity: 0.75, line: {width: 1.5, color}},
        legendgroup: 'climate-' + s.id,
        meta: {loggerId: 'climate-' + s.id},
        hovertemplate: `${s.label}<br>%{x:.1f}\u00b0C: %{y:.1%} of years<extra></extra>`,
      });
    });
  }

  const hasTemp = state.selectedMetrics.has('temperature');
  const hasHum  = state.selectedMetrics.has('humidity');
  const xTitle  = hasTemp && hasHum ? 'Temperature (\u00b0C) / Humidity (%RH)' : hasTemp ? 'Temperature (\u00b0C)' : 'Humidity (%RH)';
  const chartTitle = hasTemp && hasHum ? 'Temperature &amp; Humidity Distribution'
    : hasTemp ? 'Temperature Distribution' : 'Humidity Distribution';
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

  // 32°C threshold vertical line
  const shapes = [];
  if (state.showThreshold && hasTemp) {
    shapes.push({type:'line', xref:'x', yref:'paper', x0:32, x1:32, y0:0, y1:1,
      line:{color:'#e74c3c', width:1.5, dash:'dot'}});
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
    yaxis:{title:'Sum of reading distribution across sensors', tickformat:'.0%', showgrid:true, gridcolor:'#eee'},
    barmode:'stack', shapes, annotations: histAnnotations,
    legend:{orientation:'v', x:1.01, y:1, xanchor:'left', ...legendStyle(state.selectedLoggers.size), itemclick:false, itemdoubleclick:false},
    plot_bgcolor:'white', paper_bgcolor:'white', hovermode:'closest', hoverlabel:{font:{family:'Ubuntu, sans-serif'}},
  }, title: (`${dsl} \u2013 ${chartTitle}`).replace(/&amp;/g, '&')};
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
    const gl = {year:'years',month:'months',week:'weeks'}[state.timeMode] || 'periods';
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
      const gl = {year:'years',month:'months',week:'weeks'}[state.timeMode] || 'periods';
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
    const pctStr = pct !== null ? pct.toFixed(1) + '%' : '\u2014';
    const normalHTML = `<div class="room-name">${name}</div><div class="room-pct">${pctStr}</div>`;
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
    const filtered = filterSeries(series, start, end);
    let pct = null;
    if (filtered) {
      let below = 0, count = 0;
      for (let i = 0; i < filtered.temperature.length; i++) {
        const t = filtered.temperature[i];
        if (t == null) continue;
        if (t < 32) below++;
        count++;
      }
      pct = count > 0 ? below/count*100 : 0;
      totalBelow += below; totalAll += count;
    }
    roomStats.push({id: loggerId, name: m.loggerNames[loggerId] + meteoSuffix(loggerId) + omniSuffix(m.loggerSources[loggerId] || ''), pct, hasGap: gaps.length > 0});
  }
  if (roomStats.length === 0) { histStatsPanel.classList.add('hidden'); return; }
  const overallPct = totalAll > 0 ? (totalBelow/totalAll*100).toFixed(1) : '-';
  overall.textContent = `Overall: ${overallPct}% of temperature readings below 32\u00b0C`;
  // Gap warning and dropdown
  const gapCount = roomStats.filter(r => r.hasGap).length;
  if (gapCount > 0) {
    statsBox.classList.add('has-gaps');
    warnDiv.classList.remove('hidden');
    warnDiv.textContent = `Data completeness: ${gapCount} of ${roomStats.length} series have gaps of 24h+. Hover orange boxes for details.`;
    const seriesInfo = roomStats.map(r => ({ts: dataset().series[r.id].timestamps, source: m.loggerSources[r.id] || 'Unknown'}));
    const allAvailableInfo = m.loggers.filter(id => !extSet.has(id) && histSet.has(id) && dataset().series[id]).map(id => ({ts: dataset().series[id].timestamps, source: m.loggerSources[id] || 'Unknown'}));
    buildGapDropdown('hist-gap-dropdown', 'hist-gap-dropdown-wrap', seriesInfo, allAvailableInfo, start, end, 'histogram');
  }
  renderStatsBoxes(grid, roomStats, gapInfoMap, gapTip, start, end);
}

// ── Adaptive comfort ──────────────────────────────────────────────────────────
function renderAdaptiveComfort() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [], params = getComfortParams();
  const allExtTemps = [], allTemps = [];
  let actualStartMs = Infinity, actualEndMs = -Infinity;
  for (const loggerId of (m.comfortLoggers || m.roomLoggers)) {
    if (!state.selectedRoomLoggers.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series || !series.extTemp) continue;
    const filtered = filterSeries(series, start, end);
    if (!filtered || !filtered.extTemp) continue;
    const range = actualDataRange(series.timestamps, start, end);
    if (range) { actualStartMs = Math.min(actualStartMs, range[0]); actualEndMs = Math.max(actualEndMs, range[1]); }
    for (let i = 0; i < filtered.extTemp.length; i++) {
      if (filtered.extTemp[i] != null && filtered.temperature[i] != null) {
        allExtTemps.push(filtered.extTemp[i]);
        allTemps.push(filtered.temperature[i]);
      }
    }
    const cSource = m.loggerSources[loggerId] || '';
    const cIdLabel = loggerId === 'govee' ? '' : ` · ID: ${loggerId}`;
    const cName = m.loggerNames[loggerId] + meteoSuffix(loggerId) + omniSuffix(cSource);
    traces.push({x:filtered.extTemp, y:filtered.temperature, type:'scatter', mode:'markers',
      name:cName, marker:{color:m.colors[loggerId], size:4, opacity:0.2},
      legendgroup:loggerId, showlegend:false, meta:{loggerId},
      hovertemplate:`${m.loggerNames[loggerId]}<br>Running mean: %{x:.1f}°C<br>Room temp: %{y:.1f}°C<br>Source: ${cSource}${cIdLabel}<extra></extra>`});
    // Legend-only trace with larger, visible marker
    traces.push({x:[null], y:[null], type:'scatter', mode:'markers',
      name:cName, marker:{color:m.colors[loggerId], size:10, opacity:0.8, symbol:'square', line:{width:0}},
      legendgroup:loggerId, showlegend:true, hoverinfo:'skip', meta:{loggerId}});
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
    if (allExtTemps.length > 20000) {
      const step = Math.ceil(allExtTemps.length / 20000);
      heatX = []; heatY = [];
      for (let i = 0; i < allExtTemps.length; i += step) { heatX.push(allExtTemps[i]); heatY.push(allTemps[i]); }
    }
    traces.unshift({x:heatX, y:heatY, type:'histogram2dcontour',
      histnorm:'percent',
      colorscale:[[0,'rgba(220,220,220,0)'],[0.05,'rgba(190,190,190,0.2)'],[0.15,'rgba(150,150,150,0.36)'],[0.35,'rgba(110,110,110,0.5)'],[0.6,'rgba(70,70,70,0.66)'],[1,'rgba(30,30,30,0.8)']],
      showscale:true, ncontours:20,
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

  return {traces, layout: {
    autosize:true, font:{family:'Ubuntu, sans-serif'}, margin:{l:sm?45:65, r:sm?8:20, t:sm?15:30, b:sm?60:100},
    xaxis:{title:'Running mean external temperature (°C)', showgrid:true, gridcolor:'#eee'},
    yaxis:{title:'Air temperature (°C)  [≈ operative temp.]', showgrid:true, gridcolor:'#eee'},
    legend:{orientation:'h', x:0.5, y:-0.22, xanchor:'center', font:{size:11}, itemclick:false, itemdoubleclick:false},
    annotations: isFinite(actualStartMs) ? [dateRangeAnnotation(actualStartMs, actualEndMs, false)] : [],
    plot_bgcolor:'white', paper_bgcolor:'white', hovermode:'closest', hoverlabel:{font:{family:'Ubuntu, sans-serif'}},
  }, title: `${dsl} \u2013 Adaptive Comfort`};
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
  const s = new Date(startMs + 3*3600000), e = new Date(endMs + 3*3600000);
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
  // Returns array of complete period objects at the coarsest granularity found
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
      if (allOK(r.s, r.e)) { results.push({label: `Week ${aw.week}, ${aw.year}`, gran: 'week', y: aw.year, w: aw.week, fi: ol/(r.e-r.s) >= 0.99}); found = true; }
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
  // Find complete periods of the same granularity as the user's selection, across the full data range
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
  ['between-inputs','year-input','month-input','week-input','day-input'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));
  if (p.gran === 'year') {
    state.timeMode = 'year'; state.selectedYear = p.y;
    document.getElementById('time-mode').value = 'year';
    document.getElementById('year-select').value = String(p.y);
    document.getElementById('year-input').classList.remove('hidden');
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
    const filtered = filterSeries(series, start, end);
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
    roomStats.push({id: loggerId, name: m.loggerNames[loggerId] + meteoSuffix(loggerId) + omniSuffix(m.loggerSources[loggerId] || ''), pct, hasGap: gaps.length > 0});
  }
  if (roomStats.length === 0) { statsBox.style.display = 'none'; return; }
  statsBox.style.display = '';
  const overallPct = totalAll > 0 ? (totalIn/totalAll*100).toFixed(1) : '-';
  const modeLabel = {below_upper: 'below upper boundary', within: 'within comfort zone', above_lower: 'above lower boundary'}[state.comfortPctMode || 'below_upper'];
  overall.textContent = `Overall: ${overallPct}% ${modeLabel}`;
  // Gap warning and dropdown
  const gapCount = roomStats.filter(r => r.hasGap).length;
  if (gapCount > 0) {
    statsBox.classList.add('has-gaps');
    warnDiv.classList.remove('hidden');
    warnDiv.textContent = `Data completeness: ${gapCount} of ${roomStats.length} series have gaps of 24h+. Hover orange boxes for details.`;
    const seriesInfo = roomStats.map(r => ({ts: dataset().series[r.id].timestamps, source: m.loggerSources[r.id] || 'Unknown'}));
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
  const first = getTransform(items[0]);
  const second = getTransform(items[1]);
  const dx = second.x - first.x;
  const dy = second.y - first.y;
  if (dx <= 0) return;
  const newDx = dx + extraGap;
  items.forEach((item, i) => {
    item.setAttribute('transform', `translate(${first.x + i * newDx}, ${first.y})`);
  });
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
  const {traces, layout, title} = state.chartType === 'line' ? renderLineGraph()
    : state.chartType === 'histogram' ? renderHistogram()
    : renderAdaptiveComfort();
  _currentTitle = title || '';
  _currentLayout = layout;
  document.getElementById('bar-title').textContent = _currentTitle;
  Plotly.react('chart', traces, layout, PLOTLY_CONFIG);
  document.getElementById('chart').on('plotly_doubleclick', () => { setTimeout(updatePlot, 0); });
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
let _currentTitle = '';
let _currentLayout = {};
function updatePlot(forceLoader) {
  const renderKey = state.chartType + '|' + state.datasetKey;
  const isSlowOp = forceLoader || renderKey !== _lastRenderKey;
  _lastRenderKey = renderKey;
  // Always show loading bar - slower estimate for chart/dataset switches, short for other updates
  const ms = isSlowOp ? (state.chartType === 'comfort' ? 1500 : 800) : 350;
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
  tip.textContent = 'Darker areas = more readings concentrated there. Scale shows % of all plotted points in each region.';
  icon.addEventListener('mouseenter', () => {
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
  const texts = {
    line: 'Time series of selected loggers. Vertical lines mark seasonal boundaries; red dotted line is the 32\u00b0C overheating threshold.',
    histogram: 'Distribution of readings per 1\u00b0C or 1%RH bin. Normalised by each logger\u2019s total, so different sampling rates (hourly vs 5-min) are comparable. Bars are stacked \u2014 hover to see individual logger values.',
    comfort: 'Adaptive comfort per EN 15251. X-axis is the 7-day exponential running mean of outdoor temperature (\u03b1=0.8). Y-axis is air temperature, used here as an approximation of operative temperature. Green band = comfort zone for the selected humidity model.'
  };
  icon.addEventListener('mouseenter', () => {
    tip.textContent = texts[state.chartType] || '';
    const r = icon.getBoundingClientRect();
    tip.style.display = 'block';
    let left = r.left;
    if (left + 288 > window.innerWidth - 8) left = window.innerWidth - 296;
    tip.style.left = left + 'px';
    tip.style.top  = (r.bottom + 6) + 'px';
  });
  icon.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
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
                df = pd.concat([df, ext_df]).sort_index()
            # If fresh Omnisense available, replace snapshot Omnisense for house5
            if key == "house5" and not omnisense_df.empty:
                df = df[~df["logger_id"].isin(OMNISENSE_T_H_SENSORS)]
                df = pd.concat([df, omnisense_df]).sort_index()
            # Exclude loggers not belonging to this dataset
            exclude = cfg.get("exclude_loggers", set())
            if exclude:
                df = df[~df["logger_id"].isin(exclude)]
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
    om_hist_files = sorted(OPENMETEO_DIR.glob("historical_*.csv"))
    om_fc_files = sorted(OPENMETEO_DIR.glob("forecast_*.csv"))
    om_file = om_hist_files[-1] if om_hist_files else (om_fc_files[-1] if om_fc_files else None)
    if om_file:
        fetch_times["openmeteo"] = format_fetch_time(parse_fetch_time(om_file))
    os_files = sorted(OMNISENSE_DIR.glob("omnisense_*.csv"))
    if not os_files:
        os_files = sorted(DATA_FOLDER.glob("omnisense_*.csv"))
    if os_files:
        fetch_times["omnisense"] = format_fetch_time(parse_fetch_time(os_files[-1]))

    print("Writing output...")
    # Embed logo as base64 for PNG watermarks
    logo_path = Path("logo.png")
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
    html = (HTML_TEMPLATE
            .replace('__DATA__', json_str)
            .replace('__HISTORIC__', historic_str)
            .replace('__FETCH_TIMES__', fetch_times_str)
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
