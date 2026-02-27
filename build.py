#!/usr/bin/env python3
"""
Build script for House 5 TinyTag logger dashboard.

To update with new data:
  1. Add/replace .xlsx files in data/house5/ or data/dauda/
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

# ── Configuration ──────────────────────────────────────────────────────────────
TIMEZONE = pytz.timezone("Africa/Dar_es_Salaam")
OUTPUT_FILE = Path("index.html")

DATASETS = {
    "house5": {
        "label": "House 5",
        "folder": Path("data/house5"),
        "skip_rows": 350,
        "external_logger": "861011",
        "room_loggers": ["780981","639148","759522","759521","759209","759492",
                         "861968","759493","759498","861004","861034","759519","759489"],
    },
    "dauda": {
        "label": "Dauda's House",
        "folder": Path("data/dauda"),
        "skip_rows": 7,
        "external_logger": "861011",
        "room_loggers": None,  # auto-detect from data
    },
}

LOGGER_NAMES = {
    "861011": "External Ambient (861011)",
    "780981": "Living Room (780981)",
    "639148": "Study (639148)",
    "759522": "Bed 1 (759522)",
    "759521": "Bed 2 (759521)",
    "759209": "Bed 3 (759209)",
    "759492": "Bed 4 (759492)",
    "861968": "Living Room (below metal) (861968)",
    "759493": "Living Room (above ceiling) (759493)",
    "759498": "Dauda's House (759498)",
    "861004": "Bed 3 (above ceiling) (861004)",
    "861034": "Bed 3 (above ceiling) (861034)",
    "759519": "Bed 4 (below metal) (759519)",
    "759489": "Bed 4 (above ceiling) (759489)",
    "govee":  "Govee Smart Hygrometer",
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

    df = pd.concat(dfs, ignore_index=True).sort_values("datetime")
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

    # Validate external logger exists in data
    if external_logger not in unique_loggers:
        external_logger = None

    # Room loggers
    if cfg["room_loggers"] is not None:
        room_loggers = [l for l in cfg["room_loggers"] if l in unique_loggers]
    else:
        room_loggers = [l for l in unique_loggers if l != external_logger]

    color_map = {l: COLORS[i % len(COLORS)] for i, l in enumerate(unique_loggers)}
    logger_names = {l: LOGGER_NAMES.get(l, l) for l in unique_loggers}

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
            "externalLogger": external_logger,
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
<title>House 5 TinyTag Loggers</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 13px; background: #f8f9fa; color: #333; display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
#header { background: white; border-bottom: 1px solid #ddd; padding: 6px 12px; display: flex; align-items: center; gap: 8px; flex-shrink: 0; flex-wrap: wrap; min-height: 40px; }
#header h1 { font-size: 14px; font-weight: 600; color: #222; margin-right: 2px; }
#main { display: flex; flex: 1; overflow: hidden; position: relative; }
#sidebar { width: 220px; background: white; border-right: 1px solid #ddd; overflow-y: auto; padding: 10px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px; transition: transform 0.2s ease; z-index: 10; }
#chart-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
#time-bar { background: white; border-bottom: 1px solid #ddd; padding: 6px 10px; display: flex; align-items: center; gap: 8px; flex-shrink: 0; flex-wrap: wrap; }
#chart { flex: 1; min-height: 0; }
.section-title { font-weight: 600; font-size: 11px; color: #666; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
.section { display: flex; flex-direction: column; gap: 2px; }
select { font-size: 12px; padding: 3px 5px; border: 1px solid #ccc; border-radius: 4px; background: white; cursor: pointer; max-width: 100%; }
select:focus { outline: none; border-color: #4a90d9; }
.cb-label { display: flex; align-items: center; gap: 5px; padding: 1px 0; cursor: pointer; line-height: 1.4; font-size: 12px; }
.cb-label:hover { color: #1f77b4; }
.cb-label input[type=checkbox] { cursor: pointer; margin: 0; flex-shrink: 0; }
.control-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.control-row label { font-size: 12px; color: #666; white-space: nowrap; }
input[type=date] { font-size: 12px; padding: 3px 5px; border: 1px solid #ccc; border-radius: 4px; max-width: 130px; }
#comfort-stats { background: #f0f7ff; border: 1px solid #b8d4f0; border-radius: 6px; padding: 8px; }
#comfort-overall { font-weight: 600; font-size: 12px; margin-bottom: 6px; }
.room-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 4px; }
.room-item { background: white; border: 1px solid #ddd; border-radius: 4px; padding: 4px 6px; }
.room-name { font-size: 10px; color: #666; line-height: 1.2; }
.room-pct { font-weight: 600; font-size: 12px; }
.hidden { display: none !important; }
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
  #sidebar { position: absolute; top: 0; left: 0; height: 100%; width: 220px; transform: translateX(-100%); box-shadow: 2px 0 8px rgba(0,0,0,0.15); }
  #sidebar.open { transform: translateX(0); }
  #sidebar-backdrop.open { display: block; }
  #header { padding: 5px 8px; gap: 6px; }
  #header h1 { font-size: 12px; }
  #time-bar { padding: 5px 8px; gap: 6px; }
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
  <h1>House 5 — TinyTag Loggers</h1>
  <select id="dataset-select">
    <option value="house5">House 5</option>
    <option value="dauda">Dauda's House</option>
  </select>
  <select id="chart-type">
    <option value="line">Line Graph</option>
    <option value="comfort">Adaptive Comfort</option>
  </select>
  <select id="comfort-model" class="hidden">
    <option value="rh_gt_60" selected>RH&gt;60% (Vellei et al.)</option>
    <option value="rh_40_60">40%&lt;RH≤60% (Vellei et al.)</option>
    <option value="rh_le_40">RH≤40% (Vellei et al.)</option>
    <option value="default">Default comfort model</option>
    <option value="none">No comfort band</option>
  </select>
  <button id="download-btn">Download Chart</button>
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
        <label class="cb-label"><input type="checkbox" id="cb-humidity" checked> Humidity</label>
      </div>
      <hr class="divider">
      <div class="section">
        <div class="section-title">Options</div>
        <label class="cb-label"><input type="checkbox" id="cb-threshold" checked> 32°C Threshold</label>
        <label class="cb-label"><input type="checkbox" id="cb-seasons" checked> Season Lines</label>
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
    </div>
    <div id="chart"></div>
  </div>
</div>

<script>
const ALL_DATA = __DATA__;

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
  comfortModel: 'rh_gt_60',
  betweenStart: null,
  betweenEnd: null,
  selectedYear: null,
  selectedMonth: null,
  selectedWeek: null,
  selectedDay: null,
};

function dataset() { return ALL_DATA[state.datasetKey]; }

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

  // Rebuild logger checkboxes
  const loggerDiv = document.getElementById('logger-checkboxes');
  loggerDiv.innerHTML = '';
  m.loggers.forEach(id => {
    const lbl = document.createElement('label');
    lbl.className = 'cb-label';
    lbl.innerHTML = `<input type="checkbox" checked> <span style="color:${m.colors[id]};font-weight:600">■</span> ${m.loggerNames[id]}`;
    lbl.querySelector('input').addEventListener('change', e => {
      e.target.checked ? state.selectedLoggers.add(id) : state.selectedLoggers.delete(id);
      updatePlot();
    });
    loggerDiv.appendChild(lbl);
  });

  // Rebuild room logger checkboxes
  const roomDiv = document.getElementById('room-logger-checkboxes');
  roomDiv.innerHTML = '';
  m.roomLoggers.forEach(id => {
    const lbl = document.createElement('label');
    lbl.className = 'cb-label';
    lbl.innerHTML = `<input type="checkbox" checked> <span style="color:${m.colors[id]};font-weight:600">■</span> ${m.loggerNames[id]}`;
    lbl.querySelector('input').addEventListener('change', e => {
      e.target.checked ? state.selectedRoomLoggers.add(id) : state.selectedRoomLoggers.delete(id);
      updatePlot();
    });
    roomDiv.appendChild(lbl);
  });

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
function setupStaticListeners() {
  document.getElementById('dataset-select').addEventListener('change', e => {
    loadDataset(e.target.value);
  });

  document.getElementById('chart-type').addEventListener('change', e => {
    state.chartType = e.target.value;
    const isLine = state.chartType === 'line';
    document.getElementById('line-controls').classList.toggle('hidden', !isLine);
    document.getElementById('comfort-controls').classList.toggle('hidden', isLine);
    document.getElementById('comfort-model').classList.toggle('hidden', isLine);
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

  document.getElementById('download-btn').addEventListener('click', () => {
    const ds = document.getElementById('dataset-select').options[document.getElementById('dataset-select').selectedIndex].text;
    Plotly.downloadImage('chart', {format: 'png', width: 1600, height: 900, filename: `tinytag_${ds.toLowerCase().replace(/\s+/g,'_')}`});
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
  const {min, max} = dataset().meta.dateRange;
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

// ── Line graph ────────────────────────────────────────────────────────────────
function renderLineGraph() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [], shapes = [], annotations = [];

  for (const loggerId of m.loggers) {
    if (!state.selectedLoggers.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series) continue;
    const filtered = filterSeries(series, start, end);
    if (!filtered) continue;
    const color = m.colors[loggerId], name = m.loggerNames[loggerId];
    let firstMetric = true;
    for (const metric of ['temperature','humidity']) {
      if (!state.selectedMetrics.has(metric)) continue;
      const {x, y} = buildGapArrays(filtered.timestamps, filtered[metric]);
      const unit = metric === 'temperature' ? '°C' : '%RH';
      traces.push({x, y, type:'scatter', mode:'lines', name, line:{color, width:1.4},
        connectgaps:false, legendgroup:loggerId, showlegend:firstMetric,
        hovertemplate:`${name}<br>%{x|%d/%m/%Y %H:%M}<br>${metric==='temperature'?'Temp':'Humidity'}: %{y:.1f}${unit}<extra></extra>`});
      firstMetric = false;
    }
  }

  if (state.showThreshold) {
    traces.push({x:[new Date(start),new Date(end)], y:[32,32], type:'scatter', mode:'lines',
      name:'32°C Threshold', line:{color:'#2ca02c', width:2},
      hovertemplate:'32°C Threshold<extra></extra>'});
  }

  if (state.showSeasonLines) {
    const seasons = getSeasonBoundaries(start, end);
    const rangeMs = end - start;
    const maxLabels = rangeMs > 365*86400000 ? 8 : rangeMs > 180*86400000 ? 6 : rangeMs > 90*86400000 ? 4 : 3;
    const step = Math.max(1, Math.ceil(seasons.length / maxLabels));
    seasons.forEach((s, i) => {
      shapes.push({type:'line', xref:'x', yref:'paper', x0:new Date(s.ts), x1:new Date(s.ts), y0:0, y1:1, line:{color:'#bbb', width:1, dash:'dot'}});
      if (i % step === 0) annotations.push({x:new Date(s.ts), xref:'x', yref:'paper', y:1.01, yanchor:'bottom', xanchor:'left', text:s.name, showarrow:false, font:{size:9, color:'#888'}, textangle:-30});
    });
  }

  const rangeMs = end - start;
  let xTickFormat, xDtick;
  if      (rangeMs <= 86400000)       { xTickFormat='%H:%M';    xDtick=3600000; }
  else if (rangeMs <= 7*864e5)        { xTickFormat='%a %d/%m'; xDtick=6*3600000; }
  else if (rangeMs <= 31*864e5)       { xTickFormat='%d %b';    xDtick=86400000; }
  else if (rangeMs <= 366*864e5)      { xTickFormat='%b %Y';    xDtick='M1'; }
  else                                { xTickFormat='%b %Y';    xDtick='M3'; }

  const hasTemp = state.selectedMetrics.has('temperature');
  const hasHum  = state.selectedMetrics.has('humidity');
  const yTitle  = hasTemp && hasHum ? 'Temperature / Humidity' : hasTemp ? 'Temperature' : 'Humidity';
  const ySuffix = hasTemp && hasHum ? '' : hasTemp ? '°C' : '%RH';
  const chartTitle = hasTemp && hasHum ? 'Temperature &amp; Humidity' : hasTemp ? 'Temperature' : 'Humidity';
  const dsLabel = document.getElementById('dataset-select').options[document.getElementById('dataset-select').selectedIndex].text;
  const sm = window.innerWidth < 680;

  return {traces, layout: {
    title: {text:`<b>${dsLabel} \u2013 ${chartTitle}</b>`, font:{size: sm?12:14}},
    autosize:true, margin:{l:sm?45:65, r:sm?8:20, t:sm?40:70, b:sm?40:60},
    xaxis:{tickformat:xTickFormat, dtick:xDtick, showgrid:true, gridcolor:'#eee'},
    yaxis:{title:yTitle, ticksuffix:ySuffix, showgrid:true, gridcolor:'#eee'},
    legend:{orientation:'v', x:1.01, y:1, xanchor:'left', font:{size:11}},
    plot_bgcolor:'white', paper_bgcolor:'white', shapes, annotations, hovermode:'closest',
  }};
}

// ── Adaptive comfort ──────────────────────────────────────────────────────────
function renderAdaptiveComfort() {
  const {start, end} = getTimeRange();
  const m = dataset().meta;
  const traces = [], params = getComfortParams();
  const allExtTemps = [];

  for (const loggerId of m.roomLoggers) {
    if (!state.selectedRoomLoggers.has(loggerId)) continue;
    const series = dataset().series[loggerId];
    if (!series || !series.extTemp) continue;
    const filtered = filterSeries(series, start, end);
    if (!filtered || !filtered.extTemp) continue;
    for (const v of filtered.extTemp) { if (v != null) allExtTemps.push(v); }
    traces.push({x:filtered.extTemp, y:filtered.temperature, type:'scatter', mode:'markers',
      name:m.loggerNames[loggerId], marker:{color:m.colors[loggerId], size:4, opacity:0.2},
      legendgroup:loggerId,
      hovertemplate:`${m.loggerNames[loggerId]}<br>Running mean: %{x:.1f}°C<br>Room temp: %{y:.1f}°C<extra></extra>`});
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

  updateComfortStats(start, end, params);
  const sm = window.innerWidth < 680;
  const dsLabel = document.getElementById('dataset-select').options[document.getElementById('dataset-select').selectedIndex].text;

  return {traces, layout: {
    title: {text:`<b>${dsLabel} \u2013 Adaptive Comfort</b>`, font:{size:sm?12:14}},
    autosize:true, margin:{l:sm?45:65, r:sm?8:20, t:sm?36:60, b:sm?60:100},
    xaxis:{title:'Running mean external temperature (°C)', showgrid:true, gridcolor:'#eee'},
    yaxis:{title:'Room air temperature (°C)', showgrid:true, gridcolor:'#eee'},
    legend:{orientation:'h', x:0.5, y:-0.18, xanchor:'center', font:{size:11}},
    plot_bgcolor:'white', paper_bgcolor:'white', hovermode:'closest',
  }};
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
      const mid = params.m*ext + params.c;
      if (temp >= mid - params.delta && temp <= mid + params.delta) inZone++;
      count++;
    }
    const pct = count > 0 ? inZone/count*100 : 0;
    totalIn += inZone; totalAll += count;
    roomStats.push({name: m.loggerNames[loggerId], pct});
  }
  const overallPct = totalAll > 0 ? (totalIn/totalAll*100).toFixed(1) : '—';
  overall.textContent = `Overall: ${overallPct}% in comfort zone`;
  roomStats.slice(0,6).forEach(({name, pct}) => {
    const div = document.createElement('div');
    div.className = 'room-item';
    div.innerHTML = `<div class="room-name">${name}</div><div class="room-pct">${pct.toFixed(1)}%</div>`;
    grid.appendChild(div);
  });
}

// ── Main update ───────────────────────────────────────────────────────────────
const PLOTLY_CONFIG = {
  displayModeBar:true,
  modeBarButtonsToRemove:['zoom2d','pan2d','select2d','lasso2d','zoomIn2d','zoomOut2d',
    'resetScale2d','sendDataToCloud','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],
  responsive:true,
};
function updatePlot() {
  const {traces, layout} = state.chartType === 'line' ? renderLineGraph() : renderAdaptiveComfort();
  Plotly.react('chart', traces, layout, PLOTLY_CONFIG);
}

init();
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

    print("Writing output...")
    json_str = json.dumps(all_data, separators=(',', ':'))
    html = HTML_TEMPLATE.replace('__DATA__', json_str)
    OUTPUT_FILE.write_text(html, encoding='utf-8')

    size_kb = len(html.encode('utf-8')) / 1024
    print(f"Done → {OUTPUT_FILE.resolve()}")
    print(f"File size: {size_kb:.0f} KB ({size_kb/1024:.1f} MB)")


if __name__ == '__main__':
    main()
