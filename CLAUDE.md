# house_5_tinytag

House 5 TinyTag (Excel) logger dashboard — static HTML build.

## Primary files
- `build.py` — run to regenerate `index.html` from data
- `index.html` — output served by GitHub Pages

## Instructions for Claude
Whenever changes are made to `build.py` or `index.html`, append a brief entry to the Changelog below. Each entry heading must include the date and time to the second in CST (Taiwan/China Standard Time, UTC+8) — always run `date` first to get the real time, e.g. `### 2026-02-27 14:32:05 CST`.

## To update data
1. Add/replace `.xlsx` files in `data/house5/` and/or `data/dauda/`
2. Run: `python build.py`
3. `git add index.html && git commit -m "update data" && git push`

## Changelog

### 2026-02-27 13:47:22 CST
- Adaptive comfort: reduced scatter marker opacity 0.6→0.2 for density visualisation. Rebuilt index.html.

### 2026-02-27 12:45:40 CST
- Fixed JS spread operator stack overflow on large arrays in adaptive comfort graph. Replaced `Math.min(...allExtTemps)` / `Math.max(...allExtTemps)` and `push(...array)` with explicit `for...of` loops — fixes House 5 (174k records) silently failing to render adaptive comfort. Rebuilt index.html.

### 2026-02-27 (time not recorded)
- Created `build.py` and `index.html`: static HTML dashboard for House 5 and Dauda's House TinyTag Excel loggers. Reads .xlsx files from data/house5/ and data/dauda/, embeds both datasets as separate JSON blobs. Dataset switcher in header reloads all controls instantly client-side. EN 15251 exponential running mean (alpha=0.8) for adaptive comfort. All features from omnisense_t_h preserved: line graph, adaptive comfort, time range filtering, logger/metric selection, season lines, 32°C threshold, comfort stats, PNG download, full responsive layout.
