# ARC Ecovillage Temperature & Humidity Dashboard

Interactive environmental monitoring dashboard for the **Architecture for Resilient Communities (ARC) Cool Buildings Programme**. Tracks temperature and humidity inside buildings at the Al-Mizan Children's Ecovillage (CEV) near Mkuranga, Tanzania.

The dashboard is a self-contained HTML page that updates automatically and works offline once loaded.

**Live dashboard:** [actionresearchprojects.net/graphs/arc-tz-temp-humid](https://actionresearchprojects.net/graphs/arc-tz-temp-humid)

---

## What This Project Does

This project collects temperature and humidity data from sensors placed inside and around two buildings at the ecovillage. It combines that data with external weather information and climate patterns, then builds an interactive dashboard where you can explore it all visually.

The main goals are:

- **Monitor indoor conditions** in House 5 and the Schoolteacher's House over time
- **Assess thermal comfort** using the EN16798-1 adaptive comfort standard for naturally ventilated buildings
- **Compare indoor vs outdoor temperatures** to understand how building design affects conditions inside
- **Track climate patterns** like El Nino, the Indian Ocean Dipole, and the Madden-Julian Oscillation that influence local weather
- **Share findings** through a public, interactive web dashboard that anyone can explore

---

## Data Sources

The dashboard pulls data from four different sources:

| Source | What It Measures | How It Gets Updated |
|---|---|---|
| **TinyTag loggers** | Indoor temperature and humidity at 24+ locations (rooms, ceilings, exterior walls) | Manually downloaded as Excel files from physical sensors |
| **Omnisense sensors** | Indoor temperature and humidity from 10 wireless IoT sensors | Automatically fetched twice daily by GitHub Actions |
| **Open-Meteo API** | Outdoor temperature and humidity (historical + 7-day forecast) | Automatically fetched twice daily by GitHub Actions |
| **Climate indices** | ENSO (El Nino/La Nina), IOD (Indian Ocean Dipole), MJO (Madden-Julian Oscillation) | Automatically fetched weekly by GitHub Actions |

---

## How It Works

### Build Process

A Python script (`build.py`) does all the heavy lifting:

1. Reads sensor data from all sources
2. Aligns timestamps to East African Time (UTC+3)
3. Calculates adaptive comfort using the EN16798-1 exponential running mean
4. Processes climate cycle data into phase indicators
5. Packages everything into a single `index.html` file with embedded data and interactive Plotly.js charts

The output is a completely self-contained HTML file. No database, no backend, no API calls at runtime (except loading a small config file for custom logger names).

### Automation

Three GitHub Actions workflows keep the dashboard current without any manual work:

- **Dashboard data update** (runs at 04:00 and 16:00 UTC daily) - fetches fresh Omnisense and Open-Meteo data, rebuilds the dashboard, and pushes changes
- **Climate cycle update** (runs every Monday at 06:30 UTC) - fetches the latest ENSO, IOD, and MJO data
- **Main site notification** (runs on any push) - tells the main ARC website to pull the updated dashboard

---

## Dashboard Features

- **Interactive line graphs** for temperature and humidity over time
- **Adaptive comfort scatter plot** showing indoor temperature vs the EN16798-1 running mean, with comfort band overlays
- **Density heatmap** showing how indoor temperatures are distributed
- **32C thermal threshold marker** for quick visual reference
- **Climate cycle overlays** showing ENSO, IOD, and MJO phases alongside the data
- **Time range selection** to zoom into specific periods
- **Logger filtering** to show or hide individual sensors
- **Metric toggle** to switch between temperature and humidity views
- **Long-term mode** that shows extended climate trends and projections
- **PNG export** for use in reports and presentations
- **Admin config page** (`config.html`) for renaming loggers and changing categories without rebuilding

---

## Project Structure

```
arc_tz_temp_humid/
|
|-- build.py                 Core build script (generates index.html)
|-- fetch_openmeteo.py       Downloads weather data from Open-Meteo API
|-- fetch_omnisense.py       Scrapes sensor data from Omnisense platform
|-- fetch_cycles.py          Fetches climate cycle indices (ENSO, IOD, MJO)
|-- index.html               Generated dashboard (do not edit directly)
|-- config.html              Admin page for editing logger names
|
|-- data/
|   |-- config.json          User overrides for logger names (tracked)
|   |-- loggers.json         Logger manifest (generated, tracked)
|   |-- sensor_snapshot.json Pre-processed TinyTag data for fast rebuilds
|   |-- openmeteo/           Weather API data files (tracked)
|   |-- omnisense/           IoT sensor data files (tracked)
|   |-- cycles/              Climate index data (tracked)
|   |-- hist_proj/           Long-term climate projection data (tracked)
|   |-- house5/              TinyTag Excel files for House 5 (local only)
|   |-- schoolteacher/               TinyTag Excel files for Schoolteacher's House (local only)
|
|-- .github/workflows/      GitHub Actions automation
|-- UPDATE.md                Instructions for data updates and git workflow
|-- CHANGELOG.md             Record of all changes
|-- runningmean.md           Technical explanation of the adaptive comfort algorithm
```

---

## Buildings Monitored

### House 5

The primary building being monitored. Has 24 sensor locations covering:

- Living room, kitchen, bedrooms, study, washrooms
- Above-ceiling spaces (to measure heat transfer through the roof)
- Exterior walls
- Both TinyTag (wired) and Omnisense (wireless) sensors

### Schoolteacher's House

A second building with 3 TinyTag sensors for comparison. Uses a nearby TinyTag outdoor sensor as its reference for adaptive comfort calculations.

---

## How Data Flows

```
TinyTag Excel files -----+
(added manually)         |
                         v
Omnisense sensors ----> build.py ----> index.html ----> actionresearchprojects.net
(auto-fetched)           ^                              (live dashboard)
                         |
Open-Meteo API ----------+
(auto-fetched)           |
                         |
Climate indices ---------+
(auto-fetched weekly)
```

**Automated path:** GitHub Actions runs the fetch scripts on a schedule, then runs `build.py --auto` (which uses cached TinyTag data from `sensor_snapshot.json` plus fresh online data), and pushes the updated `index.html`.

**Manual path:** When new TinyTag Excel files are available, place them in the appropriate `data/` subfolder and run `python build.py` for a full rebuild.

---

## Adaptive Comfort

The dashboard uses the **EN16798-1** standard to assess thermal comfort in naturally ventilated buildings. This works by calculating an "exponential running mean" of outdoor temperature, which represents what occupants have been experiencing recently and have adapted to.

The formula is:

```
running_mean(today) = 0.2 * yesterday's_mean_temp + 0.8 * running_mean(yesterday)
```

This gives more weight to recent days while still accounting for the past week or two. The dashboard then plots indoor temperature against this running mean, with comfort bands showing acceptable ranges.

The default comfort model is the Vellei model for high humidity (RH > 60%), which is appropriate for the tropical climate near Mkuranga.

For full technical details, see `runningmean.md`.

---

## Key Technical Details

- **All timestamps are in East African Time (EAT, UTC+3)**
- **The dashboard is a single self-contained HTML file** with all data embedded as JSON in script tags
- **`index.html` is generated by `build.py`** and should never be edited directly
- **The `--auto` flag** lets `build.py` skip reading Excel files and use the cached `sensor_snapshot.json` instead, making automated rebuilds much faster
- **`config.json`** stores user-customized logger names and is fetched by the dashboard at load time, so name changes show up without needing a rebuild

---

## Technologies Used

| Category | Tools |
|---|---|
| Languages | Python, JavaScript, HTML, CSS |
| Data processing | pandas, openpyxl |
| Visualization | Plotly.js |
| Hosting | GitHub Pages, actionresearchprojects.net |
| Automation | GitHub Actions |
| Data sources | Open-Meteo API, Omnisense platform, TinyTag loggers, NOAA/BoM climate data |

---

## Documentation

| File | What It Covers |
|---|---|
| `UPDATE.md` | Full data update workflow including git commands |
| `CHANGELOG.md` | History of all changes made to the project |
| `runningmean.md` | Technical explanation of the adaptive comfort algorithm |

---

## License

This project is part of the Architecture for Resilient Communities Cool Buildings Programme, a research initiative focused on sustainable building design in tropical climates.
