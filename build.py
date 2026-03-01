#!/usr/bin/env python3
"""
Build script for House 5 TinyTag logger dashboard.

To update with new data:
  1. Add/replace .xlsx files in data/house5/ or data/schoolteacher/
  2. Run: python build.py
  3. git add index.html && git commit -m "update data" && git push

Output: index.html

NOTE FOR CLAUDE: After making any changes to this file or index.html,
add an entry to the Changelog in CLAUDE.md. The heading must include
date and time to the second in CST (Taiwan, UTC+8) — always run `date`
first to get the real time: ### YYYY-MM-DD HH:MM:SS CST
"""

import json
from pathlib import Path

import pandas as pd
import pytz

DATA_FOLDER = Path("data")

# ── Configuration ──────────────────────────────────────────────────────────────
TIMEZONE = pytz.timezone("Africa/Dar_es_Salaam")
OUTPUT_FILE = Path("index.html")

OMNISENSE_T_H_SENSORS = {
    "320E02D1", "327601CB", "32760371", "3276012B", "32760164",
    "3276003D", "327601CD", "32760205", "3276028A", "32760208",
}
NON_ROOM_SENSORS = {"320E02D1", "32760164"}  # outdoor / above-ceiling

DATASETS = {
    "house5": {
        "label": "House 5",
        "folder": Path("data/house5"),
        "skip_rows": 350,
        "external_logger": "External (Open-Meteo)",
        "external_sensors": ["External (Open-Meteo)", "861011", "320E02D1"],
        "exclude_loggers": {"759498"},
        "room_loggers": ["780981","759493","639148","759522","759521","759209",
                         "759492","861004","861034","759489",
                         "327601CD","3276003D","3276028A","32760205",
                         "32760208","327601CB","32760371","3276012B"],
        # Sidebar display order: external, then TinyTag rooms, then Omnisense rooms
        "sidebar_order": [
            "External (Open-Meteo)", "861011", "320E02D1",       # external
            # TinyTag room loggers
            "780981",                                             # Living Room
            "759493",                                             # Living Room (above ceiling)
            "861968",                                             # Living Room (below metal)
            "639148",                                             # Study
            "759522",                                             # Bedroom 1
            "759521",                                             # Bedroom 2
            "759209",                                             # Bedroom 3
            "861004",                                             # Bedroom 3 (above ceiling)
            "861034",                                             # Bedroom 3 (above ceiling)
            "759492",                                             # Bedroom 4
            "759489",                                             # Bedroom 4 (above ceiling)
            "759519",                                             # Bedroom 4 (below metal)
            # Omnisense room loggers
            "327601CD",                                           # Living Room
            "3276003D",                                           # Kitchen
            "3276028A",                                           # Study
            "32760205",                                           # Bedroom 1
            "32760208",                                           # Washrooms area
            "327601CB",                                           # Bedroom 2
            "32760371",                                           # Bedroom 3
            "3276012B",                                           # Bedroom 4
            "32760164",                                           # Bedroom 4 above ceiling
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
    "861968": "Living Room (below metal)",
    "759493": "Living Room (above ceiling)",
    "759498": "Bedroom 1",
    "861004": "Bedroom 3 (above ceiling)",
    "861034": "Bedroom 3 (above ceiling)",
    "759519": "Bedroom 4 (below metal)",
    "759489": "Bedroom 4 (above ceiling)",
    "govee":  "Living Space",
    # Omnisense sensors
    "320E02D1": "Weather Station T&RH",
    "327601CB": "Bedroom 2",
    "32760371": "Bedroom 3",
    "3276012B": "Bedroom 4",
    "32760164": "Bedroom 4 above ceiling",
    "3276003D": "Kitchen",
    "327601CD": "Living Room",
    "32760205": "Bedroom 1",
    "3276028A": "Study",
    "32760208": "Washrooms area",
    "External (Open-Meteo)": "External Temperature (Open-Meteo)",
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
    "External (Open-Meteo)": "Open-Meteo",
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

    # Load SSP projection files — truncated to start after ERA5 ends
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


def load_external_temperature():
    """Load Open-Meteo external temperature CSV from DATA_FOLDER."""
    matches = sorted(DATA_FOLDER.glob("open-meteo*.csv"))
    if not matches:
        print(f"  Warning: no open-meteo*.csv found in {DATA_FOLDER}, skipping external temperature")
        return pd.DataFrame()
    if len(matches) > 1:
        print(f"  Warning: multiple Open-Meteo files found — using {matches[-1].name}")
    ext_file = matches[-1]
    print(f"  Using external temperature: {ext_file.name}")
    df = pd.read_csv(ext_file, skiprows=3)
    df = df.rename(columns={
        "time": "datetime",
        "temperature_2m (°C)": "temperature",
        "relative_humidity_2m (%)": "humidity",
    })
    df["logger_id"] = "External (Open-Meteo)"
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
    df["humidity"] = pd.to_numeric(df["humidity"], errors="coerce")
    df = df.dropna(subset=["datetime", "temperature", "humidity"])
    return df[["datetime", "temperature", "humidity", "logger_id"]]


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
        omnisense_files = sorted(DATA_FOLDER.glob("omnisense_*.csv"))
        if omnisense_files:
            print(f"  Loading Omnisense CSV: {omnisense_files[-1].name}")
            os_df = load_omnisense_csv(omnisense_files[-1], sensor_filter=OMNISENSE_T_H_SENSORS)
            if not os_df.empty:
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
    iso = df.index.isocalendar()
    df["iso_year"] = iso.year.astype(int)
    df["iso_week"] = iso.week.astype(int)
    return df


# ── Running mean ───────────────────────────────────────────────────────────────
def compute_exponential_running_mean(df, external_logger, alpha=0.8):
    """EN 15251 exponential running mean of daily external temperatures."""
    ext = df[df["logger_id"] == external_logger][["temperature"]].copy()
    if ext.empty:
        return pd.Series(dtype=float)

    daily = ext.resample("D").mean()["temperature"].dropna()
    if len(daily) == 0:
        return pd.Series(dtype=float)

    trm = [daily.iloc[0]]
    for i in range(1, len(daily)):
        trm.append((1 - alpha) * daily.iloc[i - 1] + alpha * trm[-1])

    trm_series = pd.Series(trm, index=daily.index, name="running_mean")
    return trm_series.resample("h").ffill()


# ── JSON builder ───────────────────────────────────────────────────────────────
def build_dataset_json(key, df):
    cfg = DATASETS[key]
    external_logger = cfg["external_logger"]
    unique_loggers = sorted(df["logger_id"].unique())
    sidebar_order = cfg.get("sidebar_order", [])
    if sidebar_order:
        order_map = {l: i for i, l in enumerate(sidebar_order)}
        unique_loggers = sorted(unique_loggers, key=lambda l: order_map.get(l, 9999))

    # Validate external logger exists in data
    if external_logger not in unique_loggers:
        external_logger = None

    # Room loggers (ordered by sidebar_order if available)
    if cfg["room_loggers"] is not None:
        room_loggers = [l for l in cfg["room_loggers"] if l in unique_loggers]
    else:
        room_loggers = [l for l in unique_loggers if l != external_logger]
    if sidebar_order:
        order_map_rl = {l: i for i, l in enumerate(sidebar_order)}
        room_loggers = sorted(room_loggers, key=lambda l: order_map_rl.get(l, 9999))

    color_map = {l: COLORS[i % len(COLORS)] for i, l in enumerate(unique_loggers)}
    # Give Open-Meteo the light cyan
    om_key = "External (Open-Meteo)"
    cyan = "#17becf"
    if om_key in color_map:
        for k, v in list(color_map.items()):
            if v == cyan and k != om_key:
                color_map[k] = color_map[om_key]
                break
        color_map[om_key] = cyan
    logger_names = {l: LOGGER_NAMES.get(l, l) for l in unique_loggers}
    logger_sources = {l: LOGGER_SOURCES.get(l, "Unknown") for l in unique_loggers}

    # External data date range (for stale-data warning)
    ext_data = df[df["logger_id"] == external_logger] if external_logger else pd.DataFrame()
    ext_date_range = None
    if not ext_data.empty:
        ext_date_range = {
            "min": int(ext_data.index.min().timestamp() * 1000),
            "max": int(ext_data.index.max().timestamp() * 1000),
        }

    running_mean = (
        compute_exponential_running_mean(df, external_logger)
        if external_logger else pd.Series(dtype=float)
    )

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
        if logger_id in room_loggers and not running_mean.empty:
            merged = pd.merge_asof(
                ldf[[]].reset_index().rename(columns={"datetime": "dt"}),
                running_mean.reset_index().rename(columns={"datetime": "dt", "running_mean": "ext"}),
                on="dt", direction="nearest",
            )
            entry["extTemp"] = merged["ext"].round(2).tolist()
        series[logger_id] = entry

    return {
        "meta": {
            "loggers":      unique_loggers,
            "loggerNames":  logger_names,
            "loggerSources": logger_sources,
            "externalLogger": external_logger,
            "externalLoggers": [l for l in unique_loggers if l in set(cfg.get("external_sensors", [external_logger] if external_logger else []))],
            "roomLoggers":  room_loggers,
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
     date and time to the second in CST (Taiwan, UTC+8) — always run `date`
     first to get the real time: ### YYYY-MM-DD HH:MM:SS CST -->
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ecovillage Temperature &amp; Humidity</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 13px; background: #f8f9fa; color: #333; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
#header { background: white; border-bottom: 1px solid #ddd; padding: 6px 12px; display: flex; align-items: center; gap: 8px; flex-shrink: 0; flex-wrap: wrap; min-height: 40px; }
#header h1 { font-size: 14px; font-weight: 600; color: #222; margin-right: 2px; white-space: nowrap; }
#logo { height: 32px; width: auto; flex-shrink: 0; }
.bar-divider { border-left: 1px solid #ccc; height: 20px; flex-shrink: 0; margin: 0 2px; }
#main { display: flex; flex: 1; overflow: hidden; position: relative; }
#sidebar { width: 240px; background: white; border-right: 1px solid #ddd; overflow-y: auto; padding: 10px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; transition: transform 0.2s ease; z-index: 10; }
#chart-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; position: relative; }
#time-bar { background: white; border-bottom: 1px solid #ddd; padding: 6px 10px; display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
#time-bar-top { display: flex; align-items: center; width: 100%; gap: 8px; }
#time-bar-left { flex: 1; display: flex; align-items: center; gap: 8px; }
#bar-title { font-size: 14px; font-weight: 600; color: #222; white-space: nowrap; text-align: center; padding: 0 8px; overflow: hidden; text-overflow: ellipsis; }
#time-bar-right { flex: 1; display: flex; align-items: center; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }
#chart { flex: 1; min-height: 0; }
.section-title { font-weight: 600; font-size: 11px; color: #666; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
.section { display: flex; flex-direction: column; gap: 2px; }
select { font-size: 12px; padding: 3px 5px; border: 1px solid #ccc; border-radius: 4px; background: white; cursor: pointer; max-width: 100%; }
select:focus { outline: none; border-color: #4a90d9; }
.cb-label { display: flex; align-items: center; gap: 5px; padding: 1px 0; cursor: pointer; line-height: 1.4; font-size: 12px; }
.cb-label:hover { color: #1f77b4; }
[data-tooltip] { position: relative; }
[data-tooltip]:hover::after { content: attr(data-tooltip); position: absolute; left: 16px; top: 100%; background: #333; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; white-space: nowrap; z-index: 100; pointer-events: none; }
.cb-label input[type=checkbox] { cursor: pointer; margin: 0; flex-shrink: 0; }
.control-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.control-row label { font-size: 12px; color: #666; white-space: nowrap; }
input[type=date] { font-size: 12px; padding: 3px 5px; border: 1px solid #ccc; border-radius: 4px; max-width: 130px; }
#comfort-stats { background: #f0f7ff; border: 1px solid #b8d4f0; border-radius: 6px; padding: 8px; }
#comfort-overall { font-weight: 600; font-size: 12px; margin-bottom: 6px; }
.room-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 4px; }
.room-item { background: white; border: 1px solid #ddd; border-radius: 4px; padding: 4px 6px; cursor: default; transition: background 0.15s; }
.room-item:hover { background: #eef4ff; border-color: #b8d4f0; }
.room-name { font-size: 10px; color: #666; line-height: 1.2; }
.room-pct { font-weight: 600; font-size: 12px; }
.room-src { font-size: 9px; color: #888; line-height: 1.3; }
.hidden { display: none !important; }
.sel-btn { font-size: 10px; padding: 1px 6px; border: 1px solid #ccc; border-radius: 3px; background: #f5f5f5; cursor: pointer; color: #555; }
.sel-btn:hover { background: #e8e8e8; }
.sub-section-title { font-size: 10px; font-weight: 600; color: #999; text-transform: uppercase; letter-spacing: 0.05em; margin: 6px 0 2px; }
#download-btn { padding: 4px 10px; font-size: 12px; border: none; border-radius: 4px; cursor: pointer; background: #28a745; color: white; font-weight: 500; white-space: nowrap; }
#download-btn:hover { background: #218838; }
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
  #sidebar { position: absolute; top: 0; left: 0; height: 100%; width: 240px; transform: translateX(-100%); box-shadow: 2px 0 8px rgba(0,0,0,0.15); }
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
        <div class="section-title">Loggers</div>
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
        <div style="font-size:10px;color:#888;margin-top:4px;line-height:1.3">Generated using <a href="https://atlas.climate.copernicus.eu/atlas" target="_blank" style="color:#6a9fd8">Copernicus Climate Change Service</a> information 2026</div>
      </div>
    </div>

    <div id="comfort-controls" class="hidden">
      <div class="section">
        <div class="section-title">Room Loggers</div>
        <div id="room-logger-checkboxes"></div>
      </div>
      <hr class="divider">
      <div id="comfort-stats">
        <div id="comfort-overall">—</div>
        <div class="room-grid" id="comfort-room-grid"></div>
      </div>
    </div>
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
            <option value="histogram">Histogram</option>
            <option value="comfort">Adaptive Comfort</option>
          </select>
          <select id="comfort-model" class="hidden">
            <option value="rh_gt_60" selected>RH&gt;60% (Vellei et al.)</option>
            <option value="rh_40_60">40%&lt;RH≤60% (Vellei et al.)</option>
            <option value="rh_le_40">RH≤40% (Vellei et al.)</option>
            <option value="default">Default comfort model</option>
            <option value="none">No comfort band</option>
          </select>
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
        </div>
      </div>
    </div>
    <div id="ext-data-warning" class="hidden" style="background:#fff3cd;border:1px solid #ffc107;border-radius:4px;padding:6px 10px;margin:4px 10px;font-size:12px;color:#856404;flex-shrink:0;">
      &#9888; Open-Meteo external temperature data only covers to <b id="ext-data-end"></b>. Update <code>open-meteo</code> CSV to see adaptive comfort for recent dates.
    </div>
    <div id="chart"></div>
    <div id="chart-loading" style="display:none;position:absolute;inset:0;background:rgba(255,255,255,0.82);z-index:50;display:none;flex-direction:column;align-items:center;justify-content:center;gap:10px;pointer-events:none;">
      <div style="font-size:12px;color:#555;font-family:sans-serif">Loading chart…</div>
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
  historicMode: false,
  selectedHistoricSeries: new Set(),
  comfortModel: 'rh_gt_60',
  betweenStart: null,
  betweenEnd: null,
  selectedYear: null,
  selectedMonth: null,
  selectedWeek: null,
  selectedDay: null,
};

function dataset() { return ALL_DATA[state.datasetKey]; }

function loggerTooltip(id, m) {
  const src = (m.loggerSources && m.loggerSources[id]) || '';
  if (id === 'govee' || id === 'External (Open-Meteo)') return src;
  return src ? `${src} · ${id}` : id;
}

// ── Initialise ────────────────────────────────────────────────────────────────
function init() {
  setupStaticListeners();
  loadDataset('house5');
}

function loadDataset(key) {
  state.datasetKey = key;
  const m = dataset().meta;

  // Reset selections
  state.selectedLoggers = new Set(m.loggers);
  state.selectedRoomLoggers = new Set(m.roomLoggers);
  state.timeMode = 'all';
  document.getElementById('time-mode').value = 'all';
  ['between-inputs','year-input','month-input','week-input','day-input'].forEach(id =>
    document.getElementById(id).classList.add('hidden'));

  // Rebuild logger checkboxes: External / Structural / Room — each with their own buttons
  const loggerDiv = document.getElementById('logger-checkboxes');
  loggerDiv.innerHTML = '';
  function mkSelBtn(label, onClick) {
    const b = document.createElement('button');
    b.className = 'sel-btn'; b.textContent = label;
    b.addEventListener('click', onClick); return b;
  }
  function addLoggerCheckbox(id) {
    const lbl = document.createElement('label');
    lbl.className = 'cb-label';
    lbl.dataset.tooltip = loggerTooltip(id, m);
    lbl.innerHTML = `<input type="checkbox" data-logger-id="${id}" checked> <span style="color:${m.colors[id]};font-weight:600">■</span> ${m.loggerNames[id]}${omniSuffix(m.loggerSources[id] || '')}`;
    lbl.querySelector('input').addEventListener('change', e => {
      e.target.checked ? state.selectedLoggers.add(id) : state.selectedLoggers.delete(id);
      updatePlot();
    });
    loggerDiv.appendChild(lbl);
  }
  function addLoggerSection(title, ids, extraBtns) {
    if (ids.length === 0) return;
    const titleEl = document.createElement('div');
    titleEl.className = 'sub-section-title';
    titleEl.textContent = title;
    loggerDiv.appendChild(titleEl);
    const btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex;gap:4px;margin-bottom:4px;flex-wrap:wrap;';
    btnRow.appendChild(mkSelBtn('All', () => {
      ids.forEach(id => { state.selectedLoggers.add(id); loggerDiv.querySelector(`input[data-logger-id="${id}"]`).checked = true; });
      updatePlot();
    }));
    btnRow.appendChild(mkSelBtn('None', () => {
      ids.forEach(id => { state.selectedLoggers.delete(id); loggerDiv.querySelector(`input[data-logger-id="${id}"]`).checked = false; });
      updatePlot();
    }));
    if (extraBtns) extraBtns.forEach(b => btnRow.appendChild(b));
    loggerDiv.appendChild(btnRow);
    ids.forEach(addLoggerCheckbox);
  }
  const extSet  = new Set(m.externalLoggers || []);
  const roomSet = new Set(m.roomLoggers || []);
  const midLoggers  = m.loggers.filter(id => !extSet.has(id) && !roomSet.has(id));
  const roomLoggers = m.loggers.filter(id => !extSet.has(id) &&  roomSet.has(id));
  // External section
  if (m.externalLoggers && m.externalLoggers.length > 0) {
    addLoggerSection('External', m.externalLoggers);
    const hr = document.createElement('hr'); hr.className = 'divider'; loggerDiv.appendChild(hr);
  }
  // Structural/below-metal section (loggers that aren't external and aren't room)
  if (midLoggers.length > 0) {
    addLoggerSection('Structural', midLoggers);
    const hr = document.createElement('hr'); hr.className = 'divider'; loggerDiv.appendChild(hr);
  }
  // Room loggers section with optional TinyTag/Omnisense buttons
  if (roomLoggers.length > 0) {
    const hasTT = roomLoggers.some(id => m.loggerSources[id] === 'TinyTag');
    const hasOS = roomLoggers.some(id => m.loggerSources[id] === 'Omnisense');
    const extraBtns = (hasTT && hasOS) ? [
      mkSelBtn('TinyTag',  () => { roomLoggers.forEach(id => { const is = m.loggerSources[id]==='TinyTag';  is ? state.selectedLoggers.add(id) : state.selectedLoggers.delete(id); loggerDiv.querySelector(`input[data-logger-id="${id}"]`).checked = is; }); updatePlot(); }),
      mkSelBtn('Omnisense',() => { roomLoggers.forEach(id => { const is = m.loggerSources[id]==='Omnisense'; is ? state.selectedLoggers.add(id) : state.selectedLoggers.delete(id); loggerDiv.querySelector(`input[data-logger-id="${id}"]`).checked = is; }); updatePlot(); }),
    ] : null;
    addLoggerSection('Room', roomLoggers, extraBtns);
  } else if (midLoggers.length === 0) {
    // Fallback: dataset has no room/structural split — show all non-external flat
    const allNonExt = m.loggers.filter(id => !extSet.has(id));
    if (allNonExt.length > 0) addLoggerSection('Loggers', allNonExt);
  }

  // Rebuild adaptive comfort room logger checkboxes (flat list — room loggers only)
  const roomDiv = document.getElementById('room-logger-checkboxes');
  roomDiv.innerHTML = '';
  m.roomLoggers.forEach(id => {
    const lbl = document.createElement('label');
    lbl.className = 'cb-label';
    lbl.dataset.tooltip = loggerTooltip(id, m);
    lbl.innerHTML = `<input type="checkbox" data-logger-id="${id}" checked> <span style="color:${m.colors[id]};font-weight:600">■</span> ${m.loggerNames[id]}${omniSuffix(m.loggerSources[id] || '')}`;
    lbl.querySelector('input').addEventListener('change', e => {
      e.target.checked ? state.selectedRoomLoggers.add(id) : state.selectedRoomLoggers.delete(id);
      updatePlot();
    });
    roomDiv.appendChild(lbl);
  });

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

  // Reset comfort stats
  document.getElementById('comfort-overall').textContent = '—';
  document.getElementById('comfort-room-grid').innerHTML = '';

  updatePlot();
}

// ── Static event listeners (survive dataset changes) ──────────────────────────
function toggleAllCheckboxes(containerId, stateSet, loggerList, selectAll) {
  const container = document.getElementById(containerId);
  container.querySelectorAll('input[type=checkbox]').forEach(cb => { cb.checked = selectAll; });
  stateSet.clear();
  if (selectAll) loggerList.forEach(id => stateSet.add(id));
  updatePlot();
}

function setupStaticListeners() {
  document.getElementById('dataset-select').addEventListener('change', e => {
    loadDataset(e.target.value);
  });

  document.getElementById('chart-type').addEventListener('change', e => {
    state.chartType = e.target.value;
    const isLine = state.chartType === 'line';
    const isHistogram = state.chartType === 'histogram';
    const isComfort = state.chartType === 'comfort';
    document.getElementById('line-controls').classList.toggle('hidden', isComfort);
    document.getElementById('comfort-controls').classList.toggle('hidden', !isComfort);
    document.getElementById('comfort-model').classList.toggle('hidden', !isComfort);
    if (isHistogram) {
      // Show options but hide season lines checkbox (not applicable to histogram)
      document.getElementById('line-options-section').style.display = '';
      document.getElementById('line-options-divider').style.display = '';
      document.getElementById('cb-seasons').parentElement.style.display = 'none';
      if (HISTORIC) document.getElementById('historic-section').style.display = '';
      if (state.historicMode) {
        // Historic mode on: humidity stays hidden, loggers already Open-Meteo only
        // Ensure series checkboxes are built/visible
        if (!document.getElementById('historic-series-checkboxes').children.length) {
          buildHistoricSeriesCheckboxes();
        }
        document.getElementById('historic-series-checkboxes').style.display = '';
      } else {
        // Non-historic histogram: all loggers selected, humidity available, threshold on
        const m = dataset().meta;
        state.selectedLoggers = new Set(m.loggers);
        document.getElementById('logger-checkboxes').querySelectorAll('input[type=checkbox]').forEach(cb => { cb.checked = true; });
        if (!state.showThreshold) {
          state.showThreshold = true;
          document.getElementById('cb-threshold').checked = true;
        }
      }
    } else if (isLine) {
      document.getElementById('cb-seasons').parentElement.style.display = '';
      document.getElementById('line-options-section').style.display = '';
      document.getElementById('line-options-divider').style.display = '';
      if (HISTORIC) document.getElementById('historic-section').style.display = '';
      // Re-apply historic mode visual effects now that we're back on line graph
      if (state.historicMode) {
        const cbHum = document.getElementById('cb-humidity');
        cbHum.checked = false;
        state.selectedMetrics.delete('humidity');
        document.getElementById('humidity-label').style.display = 'none';
        document.getElementById('line-options-section').style.display = 'none';
        document.getElementById('line-options-divider').style.display = 'none';
      }
    }
    updatePlot();
  });

  document.getElementById('comfort-model').addEventListener('change', e => {
    state.comfortModel = e.target.value; updatePlot();
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
      lbl.innerHTML = `<input type="checkbox" data-series-id="${s.id}" checked> <span style="color:${color};font-weight:600">■</span> ${s.label}`;
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
      // Save ALL current states (universal — any chart type)
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
      // Universal: hide humidity, reset loggers to Open-Meteo only
      cbHumidity.checked = false; state.selectedMetrics.delete('humidity');
      document.getElementById('humidity-label').style.display = 'none';
      state.selectedLoggers = new Set();
      const openMeteoId = 'External (Open-Meteo)';
      if (m.loggers.includes(openMeteoId)) state.selectedLoggers.add(openMeteoId);
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
      // Always: show series checkboxes
      buildHistoricSeriesCheckboxes();
      document.getElementById('historic-series-checkboxes').style.display = '';
    } else {
      // Restore ALL saved states (universal — any chart type)
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
      modelStr = '_' + modelSel.options[modelSel.selectedIndex].text.replace(/[^a-zA-Z0-9%<>≤]/g,'').slice(0,20);
    }
    let metricStr = '';
    if (state.chartType === 'line' || state.chartType === 'histogram') {
      const metrics = [];
      if (state.selectedMetrics.has('temperature')) metrics.push('T');
      if (state.selectedMetrics.has('humidity')) metrics.push('RH');
      metricStr = '_' + metrics.join('+');
    }
    const slug = s => s.replace(/[^a-zA-Z0-9]+/g, '_').replace(/_+$/,'');
    const filename = `ARC_${slug(ds)}_${chart}${metricStr}${modelStr}_${rangeStr}`;
    const chartEl = document.getElementById('chart');
    const sm = window.innerWidth < 680;
    const W = chartEl.offsetWidth;
    const H = chartEl.offsetHeight;
    const scale = 3;
    if (state.chartType === 'line') {
      // No relayout for line graph — insert title directly into the captured SVG so the
      // on-screen chart never changes and season labels never shift position.
      Plotly.toImage('chart', {format: 'svg', width: W, height: H}).then(svgDataUrl => {
        let svgStr;
        const b64tag = 'data:image/svg+xml;base64,';
        if (svgDataUrl.startsWith(b64tag)) {
          svgStr = atob(svgDataUrl.slice(b64tag.length));
        } else {
          svgStr = decodeURIComponent(svgDataUrl.slice(svgDataUrl.indexOf(',') + 1));
        }
        const doc = new DOMParser().parseFromString(svgStr, 'image/svg+xml');
        const infolayer = doc.querySelector('.infolayer');
        const ns = 'http://www.w3.org/2000/svg';
        const marginT = (_currentLayout.margin && _currentLayout.margin.t) || 50;
        const fontSize = sm ? 12 : 14;
        const titleY = marginT / 2;
        function makeTxt(fill, stroke, sw) {
          const t = doc.createElementNS(ns, 'text');
          t.setAttribute('x', String(W / 2));
          t.setAttribute('y', String(titleY));
          t.setAttribute('text-anchor', 'middle');
          t.setAttribute('dominant-baseline', 'middle');
          t.setAttribute('font-family', '"Open Sans", verdana, arial, sans-serif');
          t.setAttribute('font-size', String(fontSize));
          t.setAttribute('font-weight', 'bold');
          t.setAttribute('fill', fill);
          if (stroke) {
            t.setAttribute('stroke', stroke);
            t.setAttribute('stroke-width', String(sw));
            t.setAttribute('stroke-linejoin', 'round');
          }
          t.textContent = _currentTitle;
          return t;
        }
        const g = doc.createElementNS(ns, 'g');
        g.appendChild(makeTxt('white', 'white', 5));
        g.appendChild(makeTxt('#222', null, 0));
        (infolayer || doc.documentElement).appendChild(g);
        const modSvg = new XMLSerializer().serializeToString(doc);
        return new Promise((resolve, reject) => {
          const canvas = document.createElement('canvas');
          canvas.width = W * scale;
          canvas.height = H * scale;
          const ctx = canvas.getContext('2d');
          ctx.scale(scale, scale);
          const img = new Image();
          img.onload = () => { ctx.drawImage(img, 0, 0, W, H); resolve(canvas); };
          img.onerror = reject;
          img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(modSvg);
        });
      }).then(canvas => {
        canvas.toBlob(blob => {
          const blobUrl = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = blobUrl;
          a.download = filename + '.png';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(blobUrl);
        }, 'image/png');
      });
    } else {
      // Histogram / adaptive comfort: briefly add title via relayout, capture PNG, restore.
      const pngTopMargin = state.chartType === 'comfort' ? (sm ? 36 : 60) : (sm ? 55 : 85);
      function doRestore() {
        Plotly.relayout('chart', {'title.text': '', 'margin.t': _currentLayout.margin.t});
      }
      Plotly.relayout('chart', {
        'title.text': `<b>${_currentTitle}</b>`,
        'title.font.size': sm ? 12 : 14,
        'margin.t': pngTopMargin,
      }).then(() => {
        return Plotly.toImage('chart', {format: 'png', width: W, height: H, scale}).then(imgData => {
          doRestore();
          const a = document.createElement('a');
          a.href = imgData;
          a.download = filename + '.png';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
        });
      });
    }
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

function filterSeries(series, startMs, endMs) {
  const ts = series.timestamps;
  if (!ts || ts.length === 0) return null;
  let lo = 0, hi = ts.length - 1;
  while (lo < hi) { const mid = (lo+hi)>>1; ts[mid] < startMs ? lo = mid+1 : hi = mid; }
  const s = lo;
  lo = 0; hi = ts.length - 1;
  while (lo < hi) { const mid = (lo+hi+1)>>1; ts[mid] > endMs ? hi = mid-1 : lo = mid; }
  const e = lo;
  if (s > e || ts[s] > endMs || ts[e] < startMs) return null;
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
    x.push(new Date(timestamps[i])); y.push(values[i]);
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

// ── Line graph ────────────────────────────────────────────────────────────────
function renderLineGraph() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [], shapes = [], annotations = [];
  let dataMinMs = Infinity, dataMaxMs = -Infinity;
  let yMin = Infinity, yMax = -Infinity;

  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
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

    const color = m.colors[loggerId], name = m.loggerNames[loggerId];
    const source = m.loggerSources[loggerId] || '';
    const idLabel = (loggerId === 'govee' || loggerId === 'External (Open-Meteo)') ? '' : ` · ID: ${loggerId}`;
    const freqLabel = state.historicMode
      ? (loggerId === 'External (Open-Meteo)' ? ' <span style="color:#aaa">(hourly avg.)</span>'
        : source === 'TinyTag' ? ' <span style="color:#aaa">(hourly avg.)</span>'
        : source === 'Omnisense' ? ' <span style="color:#aaa">(5-min avg.)</span>'
        : '') : '';
    let firstMetric = true;
    for (const metric of ['temperature','humidity']) {
      if (!state.selectedMetrics.has(metric)) continue;
      const {x, y} = buildGapArrays(filtered.timestamps, filtered[metric]);
      for (const v of y) { if (v != null) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; } }
      const unit = metric === 'temperature' ? '°C' : '%RH';
      traces.push({x, y, type:'scatter', mode:'lines', name: name + omniSuffix(source) + freqLabel, line:{color, width:1.4},
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
  const dsLabel = document.getElementById('dataset-select').options[document.getElementById('dataset-select').selectedIndex].text;
  const sm = window.innerWidth < 680;

  const plotTitle = state.historicMode
    ? 'Dar es Salaam \u2013 Historic and Projected Temperatures'
    : `${dsLabel} \u2013 ${chartTitle}`;
  const barTitle = plotTitle.replace(/&amp;/g, '&');
  return {traces, layout: {
    autosize:true, margin:{l:sm?45:65, r:sm?8:20, t:sm?70:85, b:sm?40:60},
    xaxis:{title:'Date / Time', showgrid:true, gridcolor:'#eee', range:[new Date(dataMinMs), new Date(dataMaxMs)],
      nticks:20, tickangle:-30, automargin:true},
    yaxis:{title:yTitle, ticksuffix:ySuffix, showgrid:true, gridcolor:'#eee', range: yLo !== undefined ? [yLo, yHi] : undefined},
    legend:{orientation:'v', x:1.01, y:1, xanchor:'left', font:{size:11}, itemclick:false, itemdoubleclick:false},
    plot_bgcolor:'white', paper_bgcolor:'white', shapes, annotations, hovermode:'closest',
  }, title: barTitle};
}

// ── Histogram ────────────────────────────────────────────────────────────────
function renderHistogram() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [];
  let globalMin = Infinity, globalMax = -Infinity;

  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series) continue;
    const filtered = filterSeries(series, start, end);
    if (!filtered) continue;

    const color = m.colors[loggerId];
    const name = m.loggerNames[loggerId];
    const source = m.loggerSources[loggerId] || '';
    let firstMetric = true;

    for (const metric of ['temperature', 'humidity']) {
      if (!state.selectedMetrics.has(metric)) continue;
      const values = filtered[metric].filter(v => v != null);
      if (values.length === 0) continue;
      for (const v of values) { if (v < globalMin) globalMin = v; if (v > globalMax) globalMax = v; }
      const unit = metric === 'temperature' ? '\u00b0C' : '%RH';
      const suffix = (state.selectedMetrics.size > 1) ? ` (${unit})` : '';
      traces.push({
        x: values,
        type: 'histogram',
        histnorm: 'probability',
        name: name + omniSuffix(source) + suffix,
        xbins: {size: 1},
        marker: {color, opacity: 0.6},
        legendgroup: loggerId,
        showlegend: firstMetric,
        meta: {loggerId},
        hovertemplate: `${name}<br>%{x}${unit}: %{y:.1%} of readings<extra></extra>`,
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
        hovertemplate: `${s.label}<br>%{x}\u00b0C: %{y:.1%} of years<extra></extra>`,
      });
    });
  }

  const hasTemp = state.selectedMetrics.has('temperature');
  const hasHum  = state.selectedMetrics.has('humidity');
  const xTitle  = hasTemp && hasHum ? 'Temperature (\u00b0C) / Humidity (%RH)' : hasTemp ? 'Temperature (\u00b0C)' : 'Humidity (%RH)';
  const chartTitle = hasTemp && hasHum ? 'Temperature &amp; Humidity Distribution'
    : hasTemp ? 'Temperature Distribution' : 'Humidity Distribution';
  const dsLabel = document.getElementById('dataset-select').options[document.getElementById('dataset-select').selectedIndex].text;
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

  return {traces, layout: {
    autosize:true, margin:{l:sm?45:65, r:sm?8:20, t:sm?20:36, b:useStagger?(sm?80:85):(sm?60:70)},
    xaxis:{title:xTitle, showgrid:true, gridcolor:'#eee', tickangle:0,
      tickfont: TICK_FONT,
      tickmode: tickvals.length ? 'array' : undefined,
      tickvals: tickvals.length ? tickvals : undefined,
      ticktext: tickvals.length ? ticktext : undefined},
    yaxis:{title:'Percentage of total readings for given dataseries', tickformat:'.0%', showgrid:true, gridcolor:'#eee'},
    barmode:'overlay', shapes, annotations: tickAnnotations,
    legend:{orientation:'v', x:1.01, y:1, xanchor:'left', font:{size:11}, itemclick:false, itemdoubleclick:false},
    plot_bgcolor:'white', paper_bgcolor:'white', hovermode:'closest',
  }, title: (`${dsLabel} \u2013 ${chartTitle}`).replace(/&amp;/g, '&')};
}

// ── Adaptive comfort ──────────────────────────────────────────────────────────
function renderAdaptiveComfort() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [], params = getComfortParams();
  const allExtTemps = [], allTemps = [];
  for (const loggerId of m.roomLoggers) {
    if (!state.selectedRoomLoggers.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series || !series.extTemp) continue;
    const filtered = filterSeries(series, start, end);
    if (!filtered || !filtered.extTemp) continue;
    for (let i = 0; i < filtered.extTemp.length; i++) {
      if (filtered.extTemp[i] != null && filtered.temperature[i] != null) {
        allExtTemps.push(filtered.extTemp[i]);
        allTemps.push(filtered.temperature[i]);
      }
    }
    const cSource = m.loggerSources[loggerId] || '';
    const cIdLabel = loggerId === 'govee' ? '' : ` · ID: ${loggerId}`;
    traces.push({x:filtered.extTemp, y:filtered.temperature, type:'scatter', mode:'markers',
      name:m.loggerNames[loggerId] + omniSuffix(cSource), marker:{color:m.colors[loggerId], size:4, opacity:0.2},
      legendgroup:loggerId, meta:{loggerId},
      hovertemplate:`${m.loggerNames[loggerId]}<br>Running mean: %{x:.1f}°C<br>Room temp: %{y:.1f}°C<br>Source: ${cSource}${cIdLabel}<extra></extra>`});
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

  if (allExtTemps.length > 30) {
    // Subsample for density heatmap if too many points (performance)
    let heatX = allExtTemps, heatY = allTemps;
    if (allExtTemps.length > 20000) {
      const step = Math.ceil(allExtTemps.length / 20000);
      heatX = []; heatY = [];
      for (let i = 0; i < allExtTemps.length; i += step) { heatX.push(allExtTemps[i]); heatY.push(allTemps[i]); }
    }
    traces.unshift({x:heatX, y:heatY, type:'histogram2dcontour',
      colorscale:[[0,'rgba(200,200,200,0)'],[0.35,'rgba(160,160,160,0.3)'],[1,'rgba(50,50,50,0.55)']],
      showscale:false, ncontours:10,
      contours:{coloring:'fill', showlines:false},
      hoverinfo:'skip', showlegend:false});
  }

  updateComfortStats(start, end, params);
  const sm = window.innerWidth < 680;
  const dsLabel = document.getElementById('dataset-select').options[document.getElementById('dataset-select').selectedIndex].text;

  return {traces, layout: {
    autosize:true, margin:{l:sm?45:65, r:sm?8:20, t:sm?15:30, b:sm?60:100},
    xaxis:{title:'Running mean external temperature (°C)', showgrid:true, gridcolor:'#eee'},
    yaxis:{title:'Air temperature (°C)  [≈ operative temp.]', showgrid:true, gridcolor:'#eee'},
    legend:{orientation:'h', x:0.5, y:-0.22, xanchor:'center', font:{size:11}, itemclick:false, itemdoubleclick:false},
    plot_bgcolor:'white', paper_bgcolor:'white', hovermode:'closest',
  }, title: `${dsLabel} \u2013 Adaptive Comfort`};
}

// ── Comfort stats ─────────────────────────────────────────────────────────────
function updateComfortStats(start, end, params) {
  const overall = document.getElementById('comfort-overall');
  const grid = document.getElementById('comfort-room-grid');
  grid.innerHTML = '';
  if (!params) { overall.textContent = 'No comfort band selected'; return; }
  const m = dataset().meta;
  let totalIn = 0, totalAll = 0;
  const roomStats = [];
  for (const loggerId of m.roomLoggers) {
    if (!state.selectedRoomLoggers.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series || !series.extTemp) continue;
    const filtered = filterSeries(series, start, end);
    if (!filtered || !filtered.extTemp) continue;
    let inZone = 0, count = 0;
    for (let i = 0; i < filtered.temperature.length; i++) {
      const ext = filtered.extTemp[i], temp = filtered.temperature[i];
      if (ext == null || temp == null) continue;
      const upper = params.m*ext + params.c + params.delta;
      if (temp <= upper) inZone++;
      count++;
    }
    const pct = count > 0 ? inZone/count*100 : 0;
    totalIn += inZone; totalAll += count;
    roomStats.push({id: loggerId, name: m.loggerNames[loggerId] + omniSuffix(m.loggerSources[loggerId] || ''), pct});
  }
  const overallPct = totalAll > 0 ? (totalIn/totalAll*100).toFixed(1) : '—';
  overall.textContent = `Overall: ${overallPct}% below upper comfort boundary`;
  roomStats.forEach(({id, name, pct}) => {
    const div = document.createElement('div');
    div.className = 'room-item';
    const src = (m.loggerSources && m.loggerSources[id]) || '';
    const idStr = (id === 'govee' || id === 'External (Open-Meteo)') ? '' : id;
    const normalHTML = `<div class="room-name">${name}</div><div class="room-pct">${pct.toFixed(1)}%</div>`;
    const hoverHTML  = `<div class="room-name">${name}</div><div class="room-src">${src}${idStr ? ' · ' + idStr : ''}</div>`;
    div.innerHTML = normalHTML;
    div.addEventListener('mouseenter', () => { div.innerHTML = hoverHTML; });
    div.addEventListener('mouseleave', () => { div.innerHTML = normalHTML; });
    grid.appendChild(div);
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
  hideLoadingBar();

  const warn = document.getElementById('ext-data-warning');
  const ext = dataset().meta.extDateRange;
  if (state.chartType === 'comfort' && ext && ext.max < dataset().meta.dateRange.max && dataset().meta.externalLogger === 'External (Open-Meteo)') {
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
  if (isSlowOp) {
    // Estimated render time: adaptive comfort ~1.5s, line ~0.8s
    const ms = state.chartType === 'comfort' ? 1500 : 800;
    showLoadingBar(ms);
    setTimeout(_doRender, 30); // give browser time to paint the overlay
  } else {
    _doRender();
  }
}

init();
// Re-render after layout settles to fix annotation positions on first load
requestAnimationFrame(() => requestAnimationFrame(() => Plotly.relayout('chart', {autosize: true})));

// Legend hover tooltip — attach to SVG legend elements after each render
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


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    all_data = {}
    for key, cfg in DATASETS.items():
        print(f"Loading {cfg['label']}...")
        df = load_dataset(key)
        print(f"  {len(df):,} records · {df['logger_id'].nunique()} loggers")
        print(f"  {df.index.min().date()} → {df.index.max().date()}")
        print("  Processing...")
        all_data[key] = build_dataset_json(key, df)

    print("Loading climate data...")
    historic = load_copernicus_climate_data()
    historic_str = json.dumps(historic, separators=(',', ':')) if historic else 'null'

    print("Writing output...")
    json_str = json.dumps(all_data, separators=(',', ':'))
    html = HTML_TEMPLATE.replace('__DATA__', json_str).replace('__HISTORIC__', historic_str)
    OUTPUT_FILE.write_text(html, encoding='utf-8')

    size_kb = len(html.encode('utf-8')) / 1024
    print(f"Done → {OUTPUT_FILE.resolve()}")
    print(f"File size: {size_kb:.0f} KB ({size_kb/1024:.1f} MB)")


if __name__ == '__main__':
    main()
