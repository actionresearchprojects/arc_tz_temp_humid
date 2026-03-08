## Changelog

### 2026-03-09 00:00:00 CST
- **Fixed x-axis range snapping on line graph** — When a specific time range (day/week/month/year/between) is selected, the x-axis now always spans the full selected period even if data doesn't cover it. Only the "All time" mode continues to snap to the actual data bounds. Change is in `build.py` (JS template, `renderLineGraph()`): x-axis `range` now uses `[start, end]` from `getTimeRange()` for non-"all" modes, and `[dataMinMs, dataMaxMs]` only for "all" mode.

### 2026-03-08 23:30:00 CST
- **Code cleanup & refactoring** — Major deduplication pass across the codebase:
  - **`tsRange()` shared helper** — Extracted binary search logic into a single reusable function; `filterSeries`, `detectSeriesGaps`, and `hasGapsInRange` all now use it.
  - **`addCheckbox()` / `addSection()` / `mkSourceBtns()`** — Merged the separate `addLoggerCheckbox`/`addComfortCheckbox` and `addLoggerSection`/`addComfortSection` pairs into generic builders used by all views.
  - **`buildGapDropdown()` / `renderStatsBoxes()`** — Extracted shared dropdown-building and room-box-rendering logic from both `updateHistogramStats` and `updateComfortStats`, eliminating ~70 lines of duplicated code.
  - **`dsLabel()`** — Short helper replacing verbose `document.getElementById('dataset-select').options[...].text` calls.
  - **Removed dead code** — `toggleAllCheckboxes` (unused function), `NON_ROOM_SENSORS` (unused Python set), `order_map_rl` (duplicate of `order_map`).
  - **Watermark cleanup** — Removed unused `atTop` parameter and `logoTopPad`/`txtBaseline` constants from `injectSVGWatermark`.

### 2026-03-08 14:45:00 CST
- **Comfort stats default green** — Changed `#comfort-stats` default from blue (`#f0f7ff`) to green (`#eef6ee`) to match histogram.
- **"Reset to default"** — Changed button text from "Reset defaults" to "Reset to default" across all views.
- **Source-group fallback uses all available loggers** — `findCompletePeriods` now accepts an `allAvailableInfo` parameter. When the primary all-complete search fails, the source-group fallback searches across ALL available loggers in the dataset (not just the currently selected ones). E.g. if only TinyTag is selected and has gaps, it will still offer complete Omnisense periods as alternatives (and vice versa). Removed the `srcKeys.length > 1` restriction so single-source-type selections also get fallback suggestions.

### 2026-03-08 13:30:00 CST
- **Dropdown navigation updates checkboxes** — When selecting a source-group-specific period (e.g. "Complete for TinyTag loggers") from the gap dropdown, the sidebar checkboxes now update to only select loggers of that source type. Works for both histogram (`state.selectedLoggers` + `#logger-checkboxes`) and comfort (`state.selectedRoomLoggers` + `#room-logger-checkboxes`). External loggers left unchanged in histogram view.
- **Histogram stats styling fixes** — Box default color changed from blue to green (`#eef6ee`); turns orange on gaps via `.has-gaps` CSS. Moved panel above Open-Meteo reference note. Overall text now includes "temperature" ("X% of temperature readings below 32°C").

### 2026-03-08 12:05:00 CST
- **Histogram data completeness indicator**: Ported the adaptive comfort gap detection system to the Histogram view.
  - New `#histogram-stats` panel in sidebar with per-logger percentage boxes showing % of temperature readings below 32°C.
  - Includes structural/below-roof loggers (excluded from comfort view but relevant for histogram).
  - Same gap detection, orange indicators, hover tooltips, and source-group-aware dropdown as comfort stats.
  - Temperature-only: humidity data excluded from histogram stats.
  - Overall percentage shown at top of panel.
  - Panel visibility toggled with chart type; resets on dataset switch.
  - New function: `updateHistogramStats(start, end)`, called from `renderHistogram()`.

### 2026-03-08 11:17:11 CST
- **Gap tooltip: add percentage** — The "X days missing total" line now shows `(Y%)` of the selected range.
- **Source-group dropdown fallback** — When no periods are complete for ALL enabled loggers (common when TinyTag + Omnisense are both on, since they cover different date ranges), the dropdown now falls back to per-source-type results. Shows separate `<optgroup>` sections like "Complete for TinyTag loggers (8)" and "Complete for Omnisense loggers (6)", each with their own primary and secondary suggestions. Refactored `findCompletePeriods` into `_searchCompletePeriods` (primary search) and `_searchSecondary` (same-granularity search) to enable reuse across the all-complete path and each source group.

### 2026-03-08 11:01:12 CST
- **Adaptive data completeness indicator**: Added gap detection (≥24h) to the comfort stats percentage boxes in the Adaptive Comfort view.
  - Individual `.room-item` boxes turn dark orange (`#f5d4a0`) when the series has gaps in the selected time range.
  - Container `#comfort-stats` turns light orange (`#fff5e6`) when any series has gaps.
  - Summary message shows count of series with gaps (e.g. "3 of 8 series have gaps of 24h+").
  - Hover tooltip on orange boxes lists up to 5 largest gaps sorted by size (start–end dates, days), with "and X more…" overflow and a visually separated total missing days line.
  - Dropdown suggests alternative gap-free periods: primary section (coarsest complete granularity within range: year > month > week > day), secondary section (same granularity as user's selection, outside range). Clicking a period navigates the view.
  - Series with no data in the selected range show "—" instead of a percentage and are flagged as having gaps.
  - New functions: `detectSeriesGaps()`, `hasGapsInRange()`, `formatGapRange()`, `gapTooltipHTML()`, `periodRangeMs()`, `findCompletePeriods()`, `navigateToPeriod()`.
  - CSS: `.has-gaps`, `.has-gap`, `#gap-warning`, `#gap-dropdown`, `.gap-tip` styles.
  - HTML: `#gap-warning`, `#gap-dropdown-wrap`, `#gap-tip` elements added to comfort sidebar.
  - Completeness state resets properly on dataset switch and when comfort band is "none".

### 2026-03-07 20:57:13 CST
- **PNG watermark fix**: rewrote to use SVG DOM injection for ALL three chart types (histogram and adaptive comfort now also go through SVG → canvas path, not `format: 'png'`). Fixes logo not appearing and text position issues on histogram/comfort.
- Logo size increased from 28px to 56px. Text updated to two lines: "Graph generated by ARC (architecture.resilience.community)." and "Find out more about what we do at actionresearchprojects.net." in Georgia 9px.
- Extracted shared helpers: `parseSVGDataUrl()`, `injectSVGTitle()`, `svgToCanvas()`, `canvasToPNG()`, `injectSVGWatermark()`. Download handler is now much cleaner.
- Histogram/comfort: title still added via relayout, SVG captured immediately after, then `doRestore()` called before canvas render. Watermark injected into SVG at correct position (bottom-right/top-right).

### 2026-03-07 20:47:53 CST
- **PNG watermark**: ARC logo + "actionresearchprojects.net" in Georgia serif injected into all PNG exports (only in export, not on screen).
  - `build.py` (Python): reads `logo.png`, base64-encodes it, extracts pixel dimensions from PNG IHDR header, embeds `LOGO_B64` and `LOGO_ASPECT` as JS constants via template placeholders. Adds `import base64, struct`.
  - **Line graph** (SVG DOM approach): after title injection, appends `<image>` (logo, 28px tall × aspect-correct width) and `<text>` (URL, Georgia 10px, fill #555) at bottom-right with 10px margin. Logo sits above URL text.
  - **Histogram** (Plotly relayout): adds logo `images` entry (bottom-right, full opacity, pixel-sized) and URL annotation (yanchor='top' at y=0, flows into bottom margin) to the pre-capture relayout. Restores `images` and `annotations` to originals after capture.
  - **Adaptive Comfort** (Plotly relayout): logo at top-right (yanchor='top'), URL annotation at yanchor='bottom' flowing into top margin. Both at 80% opacity. Same restore pattern.

### 2026-03-07 16:59:30 CST
- **Config UI rework**: replaced single category dropdown with three visibility checkboxes (Line Graph / Histogram / Adaptive Comfort) per logger in config.html.
- Below-roof loggers (861968, 759519, 759498) now correctly get `section: "structural"` in loggers.json (previously "other"). All have `showInLine: true`, `showInHistogram: true`, `showInComfort: false` as defaults.
- `generate_loggers_manifest`: uses `section` (not `category`); all non-external non-room loggers → section="structural"; `showInComfort` derived from `comfortLoggers` set.
- `build_dataset_json`: added `lineLoggers` and `histogramLoggers` to meta (both default to all `unique_loggers`).
- `applyUserConfig`: handles `section`, `showInLine`, `showInHistogram`, `showInComfort` overrides independently. `section` moves logger between `roomLoggers`. `showInLine`/`showInHistogram` filter `lineLoggers`/`histogramLoggers`. `showInComfort` filters `comfortLoggers`.
- `loadDataset`: sidebar now filters Room/Structural sections by `m.lineLoggers`; `state.selectedLoggers` initialised from `m.lineLoggers` (not all loggers).
- `resetLineDefaults`: uses `m.lineLoggers` as default selection.
- `renderLineGraph`: skips loggers not in `m.lineLoggers`. `renderHistogram`: skips loggers not in `m.histogramLoggers`.
- `config.html`: section dropdown (Room/Structural, hasCat datasets only) + three checkbox columns (Line, Histogram, Adaptive Comfort). External loggers show "—" in all editable columns.

### 2026-03-07 16:47:03 CST
- **Config admin UI**: Added `config.html` — a GitHub Pages admin page for editing logger display names and categories without rebuilding.
- `build.py` changes:
  - `build_dataset_json`: Added `ext_sensor_set` derived from `cfg["external_sensors"]`. Changed extTemp computation from `if logger_id in comfort_logger_set` to `if logger_id not in ext_sensor_set`, so all non-external loggers get extTemp precomputed (enables any logger to be moved to adaptive comfort via config).
  - Added `generate_loggers_manifest(all_data)`: builds a manifest of all loggers with their default names, sources, and categories (room/structural/other/external).
  - `main()`: writes `data/loggers.json` after each build (full or `--auto`).
- `index.html` template changes:
  - `init()` made `async`. Calls `await loadUserConfig()` then `applyUserConfig(config)` before `loadDataset()`.
  - `loadUserConfig()`: fetches `data/config.json` at runtime (no-cache). Returns null on any error (graceful degradation).
  - `applyUserConfig(config)`: patches `ALL_DATA` meta in-place — overrides `loggerNames`, and rebuilds `roomLoggers`/`structuralLoggers`/`comfortLoggers` from category overrides.
- `config.html` (new): standalone admin page. Reads `data/loggers.json` for defaults, reads/writes `data/config.json` via GitHub Contents API (PUT). Requires GitHub PAT with Contents: Read & Write. Shows logger tables per dataset with editable name inputs and category dropdowns (Room/Structural/Other). Save/Reset buttons commit to GitHub. Changes reflected on dashboard immediately on next page load.
- `data/config.json` (new): initial empty `{}` — tracked in git.
- `.gitignore`: added `!data/config.json` and `!data/loggers.json`.
- `CLAUDE.md` and `UPDATE.md` updated to document new files.

### 2026-03-07 11:08:26 CST
- **Omnisense automation** (Phase 2): Automated Omnisense sensor data fetching alongside Open-Meteo.
- New `fetch_omnisense.py` (stdlib only): authenticates with Omnisense portal, downloads CSV for last 90 days (or `--full-history`), saves to `data/omnisense/`, rotates old files to `data/omnisense/legacy/`. Credentials via `OMNISENSE_USERNAME`/`OMNISENSE_PASSWORD` env vars.
- `build.py` changes:
  - Added `OMNISENSE_DIR` constant for new `data/omnisense/` location (falls back to `data/omnisense_*.csv` in data root).
  - Renamed `--openmeteo-only` to `--auto` (old flag still works as alias). Now loads fresh Omnisense data in addition to Open-Meteo.
  - `AUTO_FETCHED_IDS` = Open-Meteo IDs + Omnisense sensor IDs. Sensor snapshot now excludes both (contains only TinyTag/Govee data).
- GitHub Actions workflow updated: runs twice daily (04:00 & 16:00 UTC), fetches both Open-Meteo and Omnisense, rebuilds with `--auto`. Omnisense credentials passed via GitHub Secrets.
- `.gitignore` updated: tracks `data/omnisense/`, ignores `data/omnisense/legacy/`.
- Updated `CLAUDE.md`, `UPDATE.md` with new workflows and setup instructions.
- **User action required**: Add GitHub Secrets (`OMNISENSE_USERNAME`, `OMNISENSE_PASSWORD`), then run one full local `python build.py` to regenerate the snapshot without Omnisense data, and push.

### 2026-03-02 00:43:00 CST
- **Open-Meteo automation**: Split single `External (Open-Meteo)` logger into two series:
  - `External Historical (Open-Meteo)` — recorded data from 2023-03-15 to yesterday; used for adaptive comfort running mean.
  - `External Forecast (Open-Meteo)` — predicted data for next 16 days; shown as dashed line on line graph/histogram only; excluded from adaptive comfort.
- New `fetch_openmeteo.py` (stdlib only, no pip): fetches historical + forecast from Open-Meteo API, writes timestamped CSVs to `data/openmeteo/`, rotates old files to `data/openmeteo/legacy/`.
- New `--openmeteo-only` mode for `build.py`: loads `data/sensor_snapshot.json` (pre-processed sensor data) + fresh Open-Meteo CSVs + climate data → rebuilds `index.html` without needing .xlsx/.csv sensor files.
- Full builds now save `data/sensor_snapshot.json` (~10 MB) containing all non-Open-Meteo logger data.
- New GitHub Actions workflow (`.github/workflows/update-dashboard-data.yml`): runs daily at 04:00 UTC, fetches fresh Open-Meteo data, rebuilds dashboard, commits and pushes.
- Updated `.gitignore`: selectively un-ignores `data/openmeteo/`, `data/sensor_snapshot.json`, `data/hist_proj/`.
- JS changes: `isOpenMeteo(id)` / `isForecast(id)` helpers replace hardcoded ID checks. Forecast trace uses dashed line. `forecastLoggers` metadata field added.
- Updated `CLAUDE.md`, `UPDATE.md` with new workflows.
- Rebuilt index.html.

### 2026-03-02 00:29:39 CST
- Added Open-Meteo data source note at bottom of line-controls sidebar, matching the Copernicus attribution style. Links to open-meteo.com and explains it provides hourly external temperature for Dar es Salaam, used as the adaptive comfort running mean source and the "External Temperature" logger. Rebuilt index.html.

### 2026-03-02 00:28:05 CST
- Added chart-type info (i) icon next to the chart-type dropdown. Tooltip text updates dynamically based on the currently selected chart type:
  - **Line Graph**: explains time series, gap detection, season lines, 32°C threshold.
  - **Histogram**: explains per-degree/percent bins, normalised fractions, comparable across different sampling rates.
  - **Adaptive Comfort**: explains EN 15251 running mean, green comfort zone, humidity model selection.
- Uses same fixed-position JS tooltip pattern as the density heatmap info icon (Georgia serif, z-index 9999, viewport-clamped). Tooltip opens below the icon. Width 280px.
- Rebuilt index.html.

### 2026-03-02 00:25:16 CST
- Restored Georgia serif font on density heatmap info tooltip (`#info-fixed-tip`). Was lost when switching from CSS `::after` (which inherited from `.info-i`) to JS-generated div. Rebuilt index.html.

### 2026-03-01 18:21:02 CST
- Overhauled state management for chart-type switching and long-term mode:
  - **Chart switching preserves selections**: switching between Line, Histogram, and Adaptive Comfort no longer resets logger checkboxes, threshold, or other settings. Whatever you have selected carries over. Removed the non-historic histogram "all loggers selected + threshold forced on" reset.
  - **Long-term mode persists across chart switches**: entering Adaptive Comfort while Long-Term Mode is active suspends it (not available on adaptive comfort), but returning to Line or Histogram automatically re-applies long-term mode effects (humidity hidden, options hidden on line, series checkboxes rebuilt/shown).
  - **First-entry-only logger reset**: entering Long-Term Mode for the first time in a session forces loggers to Open-Meteo only (sensible default). Subsequent toggles of Long-Term Mode keep whatever loggers are currently selected — the user's manual selections are preserved.
  - Exiting Long-Term Mode still restores the pre-entry state snapshot (loggers, metrics, time mode, threshold, seasons).
- Rebuilt index.html.

### 2026-03-01 18:14:09 CST
- Density heatmap info icon tooltip: replaced CSS `::after` pseudo-element approach with a JS fixed-position tooltip (`#info-fixed-tip`, `position:fixed`, `z-index:9999`). The old approach was clipped by `overflow:hidden` on `#main`; the fixed approach escapes all overflow constraints and positions to the right of the icon, clamping to viewport width.
- Sidebar logger ordering: updated House 5 `sidebar_order` to interleave TinyTag and Omnisense loggers by room (Living Room → Kitchen → Study → Bedroom 1–4 → Washrooms) instead of all-TinyTag-first then all-Omnisense. Applies to all checkbox lists (line graph, histogram, adaptive comfort) since they all derive order from `sidebar_order`.
- Rebuilt index.html.

### 2026-03-01 18:07:53 CST
- Density heatmap: restored full fill opacities (reverted the halving from 18:01). Changed from `coloring:'heatmap'` back to `coloring:'fill'` (discrete bands) with `showlines:true` and `line:{color:'rgba(80,80,80,0.3)', width:0.5}` — contour outline lines now drawn at ~half opacity rather than hidden.
- Info (i) tooltip: repositioned to open rightward-from-right (`right:-4px; left:auto`) so it stays within the sidebar instead of overflowing the right edge.
- Loading progress bar: now shown on every `updatePlot()` call, not just chart-type/dataset switches. Fast updates (checkbox toggles etc.) use a 350ms estimated duration; slow switches keep their existing estimates (1500ms comfort, 800ms line).
- Rebuilt index.html.

### 2026-03-01 18:01:16 CST
- Density heatmap: reverted from blue back to grey/black colorscale; all opacity values halved (~0→0, 0.1→0.05, 0.18→0.09, 0.25→0.13, 0.33→0.17, 0.4→0.2).
- Info (i) tooltip: box widened to 230px, font-size 12px, padding 6×9px, line-height 1.5 for better readability.
- Download filename: stripped "(Vellei et al.)" from adaptive comfort model label — filename now shows just the RH% portion (e.g. `RH60`).
- Rebuilt index.html.

### 2026-03-01 17:56:08 CST
- Density heatmap visibility fix: switched from grey colorscale to blue-tinted gradient (`rgba(25,55,130,0.8)` at peak) with 6 colorscale stops and more aggressive opacity ramp at low values. Changed from `contours.coloring:'fill'` (discrete bands) to `'heatmap'` (smooth continuous gradient). Increased `ncontours` from 10 to 20 for finer granularity. Now visible on House 5 (large dataset) as well as Schoolteacher's House.
- Added All/None/TinyTag/Omnisense buttons to adaptive comfort room logger checkboxes (mirrors line graph sidebar pattern). TinyTag/Omnisense buttons only appear when both sources exist (House 5).
- Added (i) info icon next to "Density Heatmap" checkbox with tooltip explaining what the heatmap shows in plain English ("Shows where readings are concentrated...").
- Rebuilt index.html.

### 2026-03-01 17:48:14 CST
- Density heatmap on adaptive comfort chart is now toggleable via a "Density Heatmap" checkbox in a new Options section of the comfort sidebar (checked/on by default). Unchecking hides the `histogram2dcontour` trace; scatter points remain.
- Added colour scale bar to the density heatmap showing percentage of data points in each density region (`histnorm:'percent'`, `showscale:true`, colorbar with `ticksuffix:'%'`). Colorscale opacities slightly increased for better scale bar readability.
- Rebuilt index.html.

### 2026-03-01 17:41:49 CST
- Download filename timestamp now uses the viewer's browser local time (`new Date()` with `getFullYear/Month/Date/Hours/Minutes`) rather than EAT, so the timestamp reflects what time it is on the user's machine. Rebuilt index.html.

### 2026-03-01 17:38:20 CST
- Download spinner: green rotating circle (`#dl-spinner`) appears next to the Download PNG button while export is in progress. Button is disabled during export and re-enables on completion or error. Spinner is purely CSS (`@keyframes dlspin`, `border-top-color` trick), no JS libraries.
- Download filenames now include an EAT timestamp (`YYYYMMDD_HHmm`) at the end to prevent browser appending `(2)`, `(3)` etc. for repeat downloads of the same graph.
- Download filenames now encode sensor selection: if 1–2 loggers are selected their slugified display names are included; if a partial subset (3+), the count is included (e.g. `_5of24sensors`); if all are selected nothing extra is added (keeps the common case clean).
- Rebuilt index.html.

### 2026-03-01 17:33:07 CST
- Fixed line graph x-axis timezone display: timestamps were showing in browser local time (UTC+8) instead of EAT.
  - Root cause: x values were passed as UTC epoch ms (`new Date(timestamps[i])`); Plotly converts these using the viewer's browser timezone, shifting times by UTC+8 offset for users in China/Taiwan.
  - Fix 1 (Python): reverted Weather Station cutoff back to `pd.Timestamp("2026-02-17 12:00:00")` (naive EAT, correct). Previous `09:00:00` was wrong — Omnisense CSV timestamps are EAT, not UTC.
  - Fix 2 (JS): added `toEATString(ms)` helper that converts UTC epoch to EAT local time string (`new Date(ms + 3h).toISOString().slice(0,19)`). Plotly treats bare date strings as calendar-absolute (no timezone conversion), so viewers in any timezone always see EAT.
  - Applied: `buildGapArrays` now pushes `toEATString(timestamps[i])` for x values; `renderLineGraph` xaxis range uses `toEATString(dataMinMs/dataMaxMs)` and `type:'date'`.
- Rebuilt index.html.

### 2026-03-01 17:19:53 CST
- Fixed weather station cutoff timezone: Omnisense CSV timestamps are UTC, so midday EAT (12:00 UTC+3) = 09:00 UTC. Cutoff corrected from `2026-02-17 12:00:00` to `2026-02-17 09:00:00` (naive UTC). Previous cutoff was removing data from 09:00–12:00 UTC (12:00–15:00 EAT), causing the graph to start from the next available reading at 14:00 UTC = 17:00 EAT (5pm).
- Line graph x-axis title updated to `Date / Time <i>(EAT, UTC+03:00)</i>` with grey italic styling via Plotly HTML subset.
- External Temperature (Open-Meteo) logger: base display name changed to "External Temperature" (parenthetical removed from Python). Added `meteoSuffix(id)` JS helper (parallel to `omniSuffix`) that appends a grey `(Open-Meteo)` label. Applied to all display sites: sidebar checkboxes (both line graph and adaptive comfort lists), line graph/histogram/adaptive comfort trace names, adaptive comfort stats panel.
- Rebuilt index.html.

### 2026-03-01 17:10:55 CST
- Weather Station T&RH (Omnisense 320E02D1): data truncated to 2026-02-17 12:00 EAT onwards. Applied immediately after `load_omnisense_csv()` in `load_dataset()` using a pd.Timestamp cutoff. Omnisense record count dropped from 80,844 to 73,386.
- Line graph x-axis title updated to "Date / Time (EAT)" to make clear all timestamps are East African Time.
- Rebuilt index.html.

### 2026-03-01 15:13:21 CST
- Reverted adaptive comfort sidebar back to flat list of room loggers only (structural loggers were not part of adaptive comfort and should not appear there). renderAdaptiveComfort and stats loops reverted to iterate over m.roomLoggers. Sidebar width change (240px) from the previous commit is kept. Rebuilt index.html.

### 2026-03-01 15:10:31 CST
- Fixed adaptive comfort checkbox sections: now splits into Structural (unchecked by default) and Room (checked by default), matching the line graph/histogram sidebar — not TinyTag/OmniSense as incorrectly done in previous commit.
- renderAdaptiveComfort scatter and stats now iterate over all non-external loggers (not just m.roomLoggers), so structural loggers appear on the scatter and in stats when their checkbox is ticked.
- Rebuilt index.html.

### 2026-03-01 15:04:26 CST
- Sidebar width increased from 220px to 240px (desktop and mobile overlay) so "Washrooms area (OmniSense)" fits without wrapping. The width value is in the `#sidebar` CSS rule on the `#sidebar { width: 240px; ... }` line near the top of the CSS block.
- Adaptive comfort "Room Loggers" checkbox list now sections by source like the line graph sidebar: TinyTag loggers under a "TinyTag" sub-header with All/None buttons, then a divider, then Omnisense loggers under an "OmniSense" sub-header with All/None buttons. Falls back to a single "Room" section if only one source present. Static HTML buttons (All/None/TinyTag/Omnisense) and their static event listeners removed; replaced by the same dynamically-built pattern used by the line graph (`addRoomSection` helper inside `initDataset`). Rebuilt index.html.

### 2026-03-01 14:58:01 CST
- "Historic Mode" renamed to "**Long-Term Mode**" (bold) in the sidebar checkbox label.
- Sensor display names updated everywhere (LOGGER_NAMES dict, all graphs, legend keys, sidebar checkboxes, adaptive comfort stats panel):
  - "Bed 1/2/3/4" → "Bedroom 1/2/3/4" (TinyTag loggers 759522/759521/759209/759492)
  - "Bed 3/4 (above/below ceiling/metal)" → "Bedroom 3/4 ..." (TinyTag loggers 861004, 861034, 759519, 759489)
  - "Bed 2/3/4" Omnisense → "Bedroom 2/3/4" (327601CB, 32760371, 3276012B)
  - "Bed 4 above ceiling" Omnisense → "Bedroom 4 above ceiling" (32760164)
  - "Mother's Bedroom" → "Bedroom 1" (Omnisense 32760205, privacy)
- Omnisense sensors now show a grey "(OmniSense)" suffix everywhere they appear (legend, checkboxes, adaptive comfort stats). Added `omniSuffix(source)` JS helper; applied to line graph, histogram, and adaptive comfort traces, both sidebar checkbox lists, and the adaptive comfort stats panel.
- Rebuilt index.html.

### 2026-03-01 14:45:45 CST
- Line graph top margin restored to t=50/65 (was incorrectly reduced to t=35/50 in previous fix attempt).
- Line graph PNG download now skips `Plotly.relayout` entirely — title is injected directly into the SVG string after capture, so the on-screen chart margin never changes and season labels never shift during download.
- White title halo stroke-width reduced from 10 to 5 (half as thick).
- Rebuilt index.html.

### 2026-03-01 14:37:15 CST
- Fixed three bugs in the graph title bar feature:
  1. **Season labels cut off on initial load**: added double `requestAnimationFrame` after `init()` so `Plotly.relayout({autosize:true})` fires after the flexbox layout has fully settled, correcting annotation positions on first render.
  2. **No-shift during PNG download**: unified line graph top margin between screen render and PNG export (`t:sm?35:50` for both), so `margin.t` stays constant when title is temporarily added back — season labels no longer jump.
  3. **White title halo in line graph PNG**: replaced `paint-order` SVG attribute approach (unreliable when SVG is drawn to canvas) with a clone/halo method — a white-filled, white-stroked clone of the `.g-gtitle` group is inserted before the original in `.infolayer`, giving a thick white outline behind each character. Both clone and original are moved to the end of `.infolayer` so the title renders above season-label annotations.
- Rebuilt index.html.

### 2026-03-01 14:27:39 CST
- Fixed season labels being cut off on line graph: top margin on screen increased from t=20/36 to t=50/65 (season labels sit at y=1.01 paper coords and need ~50px headroom).
- Fixed white title stroke not appearing on line graph PNG downloads: `Plotly.toImage` with `scale:3` internally re-renders the chart, discarding any manual SVG DOM changes made before the call. Fix: request SVG format from Plotly (which serialises the current DOM including the title), then patch the `.gtitle text` element in the SVG string via DOMParser (adding `stroke=white`, `stroke-width=6`, `paint-order=stroke fill`), render the modified SVG to a canvas at 3× scale, and export as a PNG blob. Histogram and adaptive comfort PNG downloads continue to use the direct `Plotly.toImage` png path. Rebuilt index.html.

### 2026-03-01 14:15:22 CST
- Graph title moved from Plotly chart area into the controls bar (`#time-bar`) for on-screen display only. Title is now centred between the left controls (dataset, chart-type, model dropdowns) and the right controls (Range selector + Download PNG button). Plotly chart top margin reduced accordingly for all three chart types (line: t=20/36, histogram: t=20/36, adaptive comfort: t=15/30).
- PNG downloads: title is temporarily added back to the Plotly chart via `Plotly.relayout` before `Plotly.toImage` captures it, then removed after. For line graph PNGs only, a thick white stroke (`strokeWidth: 5px`, `paintOrder: stroke fill`) is applied to the SVG title text element before capture so the title is legible even when overlapping season labels. Download handler converted from `Plotly.downloadImage` to `Plotly.toImage` + manual `<a>` click to support the async relayout/restore flow. Rebuilt index.html.

### 2026-02-28 17:30:27 CST
- Historic mode now applies its effects universally (both line graph and histogram): enables "Historic Mode" checkbox in histogram mode → hides humidity, resets loggers to Open-Meteo only, shows climate series checkboxes. Previously these effects only applied on the line graph.
- State save/restore (savedBeforeHistoric) is now universal: triggered when historic mode is toggled regardless of which chart type is active. Turning off historic mode in histogram restores the exact pre-historic settings, and switching back to line graph uses those same restored settings.
- Options section (threshold/season lines) hiding on historic mode ON, and showing on historic mode OFF, remains line-graph-only (threshold stays visible in histogram historic mode since 32°C line is useful there).
- Switching to histogram in non-historic mode still resets to all loggers + threshold on (existing default). Switching to histogram in historic mode keeps the historic state intact (Open-Meteo only, humidity hidden). Rebuilt index.html.

### 2026-02-28 17:21:23 CST
- Histogram + Historic Mode integration: ERA5 and SSP climate series now appear as histogram traces when Historic Mode is enabled on the histogram chart. Each selected series (ERA5, SSP1-1.9, etc.) adds a probability-normalised histogram of annual mean temperatures (1 bin per °C), coloured by CLIMATE_COLORS, with outline marker style to visually distinguish from sensor data. Shows fraction of years at each temperature (e.g. "27°C: 8.3% of years").
- Historic section now visible in sidebar when chart type is histogram (previously hidden). Switching to histogram with Historic Mode already active rebuilds the series checkboxes.
- Historic Mode toggle: when in histogram mode, toggling Historic Mode only shows/hides the climate series checkboxes — no logger reset (stays all-selected), no humidity hiding, no options hiding. When in line graph mode, full save/restore logic is unchanged. Rebuilt index.html.

### 2026-02-28 17:03:58 CST
- Histogram normalised by probability (histnorm:'probability'): bars now show fraction of each logger's readings in each bin rather than raw counts. Fixes bias where high-frequency loggers (Omnisense at 5-min) would appear 12× taller than hourly TinyTag loggers for the same temperature distribution. Y-axis title changed to "Fraction of readings" with % tick format. Hover updated to show e.g. "28°C: 12.3% of readings". Rebuilt index.html.

### 2026-02-28 16:53:27 CST
- Histogram tick stagger: only applied when x-axis range exceeds 60 units; narrower ranges use plain labels without stagger. Lower-row annotation y moved from -0.055 to -0.04 (closer to axis). Unified TICK_FONT={size:11, color:'#444'} applied to both xaxis tickfont and annotations so both rows match. Bottom margin reduced for non-stagger case (60/70px) vs stagger case (80/85px). Rebuilt index.html.

### 2026-02-28 16:49:16 CST
- Histogram: 32°C threshold checkbox now forced on when entering histogram mode (was defaulting to its current state, which could be off).
- Histogram x-axis stagger redesigned: use tickmode:'array' with even values as built-in tick labels (at their natural position just below the axis) and odd values as blank tick text + custom annotation at y=-0.055 paper coords (one row lower). Tick marks still appear at every degree. Bottom margin reduced to 80/85px (was 100/110). This prevents the previous large gaps caused by all labels being pushed to paper-coord annotations. Rebuilt index.html.

### 2026-02-28 16:42:29 CST
- Histogram: all logger checkboxes now selected by default when switching to histogram mode.
- Histogram x-axis stagger: replaced \n-prefix approach (which was producing left-right shift instead of up-down) with custom Plotly annotations. Built-in tick labels hidden (showticklabels:false); dtick:1 keeps per-degree tick marks. Custom annotations place even values at y=-0.04 and odd values at y=-0.14 (paper coordinates) — true up-down stagger, horizontal text. Bottom margin increased to 100/110px to accommodate two-row label layout.
- Historic mode climate traces: wide view (all time, or between-dates spanning >1 year) uses original lines+markers through annual data points (smooth). Narrow view (year/month/week/day, or between-dates ≤1 year) expands each point to span Jan 1–Dec 31 (visible horizontal line). Prevents blocky appearance on the multi-decade overview while keeping single-year zoom working. Rebuilt index.html.

### 2026-02-28 16:30:12 CST
- Histogram: Season Lines checkbox hidden when chart type is histogram (not applicable); restored when switching back to line graph.
- Historic mode isolation: switching to histogram no longer turns off historic mode. Instead, its UI effects (humidity hidden) are suspended — humidity is restored for histogram use. Switching back to line graph re-applies historic mode effects (hides humidity again, hides Options section). Historic mode state is fully preserved across chart-type switches. Rebuilt index.html.

### 2026-02-28 16:13:11 CST
- Historic mode: each annual climate data point now expanded to span Jan 1–Dec 31 as a horizontal line, so selecting a single year (e.g. "Year 1970") shows a visible horizontal line at the annual mean rather than an invisible 3px dot. Trace mode changed from 'lines+markers' to 'lines'.
- Season lines on line graph reverted to grey (#bbb, dot) — only 32°C threshold is red dotted.
- Line graph y-axis title now includes units: "Temperature (°C) / Humidity (%RH)" when both selected, "Temperature (°C)" or "Humidity (%RH)" when only one. Tick suffix unchanged.
- Histogram x-axis tick stagger increased from \n to \n\n\n offset for alternate labels; forced horizontal (tickangle:0). Rebuilt index.html.

### 2026-02-28 16:09:53 CST
- Histogram: fixed x-axis title to "Temperature (°C) / Humidity (%RH)" when both metrics selected. Added staggered tick labels (alternate labels offset downward with \n prefix) so all per-degree labels show without overlap. Added 32°C vertical dotted red line (same checkbox as line graph) when temperature metric is active. Line graph threshold line style changed to red dotted (#e74c3c, dash:dot) to match. Season lines changed to red dotted (#e74c3c) from grey (#bbb).
- Sidebar logger checkboxes split into three labelled sections with independent All/None buttons: External (All/None), Structural (All/None — below-metal loggers that are neither external nor room), Room (All/None + TinyTag/Omnisense if applicable). Structural section only appears when such loggers exist (House 5 only). Static All/None/TinyTag/Omnisense button row removed; replaced by dynamically injected per-section buttons. Rebuilt index.html.

### 2026-02-28 15:59:03 CST
- Added Histogram chart type to chart-type dropdown. Shows distribution of time spent in temperature/humidity ranges with 1-bin-per-degree (°C) or 1-bin-per-%RH. Reuses line graph logger checkboxes, metric toggles, and time range controls. Multiple loggers overlay translucently (barmode:'overlay', opacity:0.6). Options section (threshold/season lines) and Historic section hidden when histogram is active. Download filename includes "Histogram". Rebuilt index.html.

### 2026-02-28 15:47:46 CST
- Hover detail on line graph: Open-Meteo (like Govee) no longer shows redundant `· ID: External (Open-Meteo)` since the source is already displayed. Rebuilt index.html.

### 2026-02-28 15:46:26 CST
- Fixed capitalisation: "Dar Es Salaam" → "Dar es Salaam" in Historic Mode chart title. Rebuilt index.html.

### 2026-02-28 15:45:52 CST
- Added loading overlay with progress bar on chart area for slow operations (chart type switch and dataset switch). Bar animates over ~1.5s for adaptive comfort, ~0.8s for line graph, then snaps to 100% and fades. Detected by comparing `chartType|datasetKey` before/after — fast interactions (logger toggles, time range changes) render immediately without the overlay. Overlay is semi-transparent white so the previous chart remains visible underneath. Rebuilt index.html.

### 2026-02-28 15:41:05 CST
- Updated frequency labels in Historic Mode legend: all now end with " avg." — "(hourly avg.)" for TinyTag and Open-Meteo, "(5-min avg.)" for Omnisense, "(annual avg.)" for climate series. Rebuilt index.html.

### 2026-02-28 15:36:54 CST
- Corrected frequency labels in Historic Mode legend: TinyTag is "(hourly)" (~1 hr interval), Omnisense is "(5-min)" (~5 min interval), Open-Meteo is "(hourly)", climate series are "(yearly avg.)". Full state save/restore on Historic Mode toggle now includes time mode (year/month/week/day/between selection) and temperature metric, so exiting Historic Mode returns to exactly the time range and checkbox state that was set before entering. Rebuilt index.html.

### 2026-02-28 15:33:03 CST
- In Historic Mode, legend entries now show grey frequency suffix: sensor loggers get "(hourly)" for Open-Meteo or "(15-min)" for TinyTag/Omnisense; climate series get "(yearly)". Suffix only shown in Historic Mode. Rebuilt index.html.

### 2026-02-28 15:31:32 CST
- Historic Mode now defaults to Open-Meteo only for logger selection (all others deselected on enable, restored on disable). Six climate series (ERA5 + 5 SSPs) now have individual checkboxes shown in the sidebar when Historic Mode is on, each with colour swatch, all checked by default. Chart title changes to "Dar Es Salaam – Historic and Projected Temperatures" in Historic Mode. Logger and series checkbox state fully saved and restored on mode toggle. Rebuilt index.html.

### 2026-02-28 15:26:36 CST
- SSP projection data truncated to start from 2022 (was 2024). All 5 scenarios now cover 2022–2100. Rebuilt index.html.

### 2026-02-28 15:20:15 CST
- When Historic Mode is enabled: humidity checkbox is hidden and deselected (temperature only makes sense against climate projections); threshold and season line checkboxes already hidden. All three states (humidity, threshold, season lines) are saved before hiding and fully restored when Historic Mode is turned back off. Rebuilt index.html.

### 2026-02-28 15:18:17 CST
- Climate data files moved to `data/hist_proj/` — updated loader path. SSP projection data now truncated to start from 2024 (year after ERA5 ends at 2023), so ERA5 and projections connect cleanly without overlap. Fixed double-click on y-axis resetting to 0–100 instead of data range — intercept `plotly_doubleclick` event and call `updatePlot()` to restore computed range. When Historic Mode is checked, the Options section (32°C Threshold + Season Lines) is hidden as they are not meaningful over the historic/projection date range. Rebuilt index.html.

### 2026-02-28 15:09:33 CST
- Replaced World Bank historic data with Copernicus Climate Change Service data (ERA5 + CMIP6 SSP projections). Two old checkboxes replaced with single "Historic Mode" toggle. When active, shows 6 colour-coded traces: ERA5 Historic (dark grey, 1940–2023), SSP1-1.9 (green), SSP1-2.6 (light green), SSP2-4.5 (yellow), SSP3-7.0 (orange), SSP5-8.5 (red) — each 1850–2100, ensemble mean across all models. Year dropdown expands to 1850–2100 when historic mode is on. Source credit updated to Copernicus with hyperlink. Rebuilt index.html.

### 2026-02-28 13:41:27 CST
- Added source attribution below historic data checkboxes: "Source: World Bank Climate Knowledge Portal" with hyperlink. Rebuilt index.html.

### 2026-02-28 13:40:48 CST
- Fixed historic data: threshold line and season lines now extend across the full range when historic is active (bounds expansion moved before threshold/season code). Historic traces now filtered by the active time range (between dates, year, etc.) instead of always showing all 124 years. Year dropdown dynamically includes historic years (1901–2024) when either historic checkbox is checked, and reverts to sensor-only years when unchecked. "All time" mode expands to cover historic range when active. Rebuilt index.html.

### 2026-02-28 13:28:51 CST
- Fixed historic data not visible when toggled on — x-axis range was snapped to sensor data (2023–2026), hiding the 1901–2024 historic traces off-screen. Now expands `dataMinMs`/`dataMaxMs` and y-axis bounds to include historic data when either checkbox is active. Rebuilt index.html.

### 2026-02-28 13:26:37 CST
- Added Dar es Salaam historic temperature data (1901–2024) to line graphs. Two series: "DSM Historic Mean" (annual mean, pink) and "DSM 5-yr Smooth" (Gaussian smooth, grey). Both defaulted to OFF. Loaded from `data/Daressalaamhistoric.csv`, embedded as separate JSON blob. New "Dar es Salaam Historic" sidebar section with two checkboxes, visible only when data file exists. Line graph only — not shown on adaptive comfort. Rebuilt index.html.

### 2026-02-28 13:18:20 CST
- Reordered sidebar checkboxes (line graph + adaptive comfort): external loggers first, then all TinyTag room loggers grouped by room, then all Omnisense room loggers grouped by room. Previously TinyTag and Omnisense were interleaved by room, making source-toggle buttons produce a scattered checklist. Rebuilt index.html.

### 2026-02-28 13:16:55 CST
- Adaptive comfort stats now show percentage of points **below the upper comfort boundary** instead of within the comfort zone. Calculation changed from `temp >= mid - delta && temp <= mid + delta` to `temp <= mid + delta`. Overall label updated to "Overall: X.X% below upper comfort boundary". Graph visuals unchanged. Rebuilt index.html.

### 2026-02-28 13:11:06 CST
- Fixed legend hover tooltips showing wrong sensor (e.g. "Bed 2" showing Omnisense tooltip when TinyTag was the actual trace). Root cause: name-based lookup in `setupLegendTooltips()` was overwritten by the last logger with that display name. Fixed by adding `meta:{loggerId}` to all scatter traces and rewriting `setupLegendTooltips()` to match legend entries by index against `chart.data` (filtered to showlegend!==false), then reading `trace.meta.loggerId` for the correct tooltip. Rebuilt index.html.

### 2026-02-28 13:04:59 CST
- Fixed blank page caused by missing `init()` call (accidentally deleted during legend hover refactor). Reverted `scattergl` back to `scatter` for compatibility. Legend hover tooltips now use direct DOM listeners on SVG elements (working). Density heatmap subsampled to 20k points max for performance. Rebuilt index.html.

### 2026-02-28 13:01:44 CST
- Fixed legend hover tooltips: replaced unreliable `plotly_legendhover` event with direct DOM mouseenter/mouseleave listeners on SVG `.traces` elements, attached via `requestAnimationFrame` after each render. Hover shows source + ID tooltip following cursor. Performance: switched all data traces from `scatter` to `scattergl` (WebGL-accelerated rendering, handles 200k+ points smoothly). Density heatmap data subsampled to 20k points max for faster contour computation. Rebuilt index.html.

### 2026-02-28 12:55:46 CST
- Reverted legend names (removed grey suffix text), reverted adaptive comfort marker size/opacity back to size:4 opacity:0.2. Added floating tooltip on legend item hover via plotly_legendhover event — shows source + ID (same style as checkbox tooltips). Disabled legend click/doubleclick (itemclick:false, itemdoubleclick:false) since checkboxes handle selection. Download button reverted to simple button defaulting to high quality (3× scale). Season labels restored to y:1.01 yanchor:bottom, top margin increased (t:55/85) to prevent clipping. Rebuilt index.html.

### 2026-02-28 12:49:48 CST
- Legend entries now show source and sensor ID as grey suffix text (e.g. "Living Room (Omnisense · 327601CD)"). Adaptive comfort legend markers increased from size 4/opacity 0.2 to size 6/opacity 0.5. Line graph legend items widened (itemwidth:40) for more visible colour lines. Season line labels moved inside the plot area (y:0.99, yanchor:'top') to prevent clipping at the top edge. Logo wrapped in hyperlink to actionresearchprojects.net (same tab). Rebuilt index.html.

### 2026-02-28 12:47:02 CST
- Download: merged quality dropdown + button into a single green select ("Download PNG" → Original quality / High quality). Original exports at 1× scale (exactly what's on screen), High exports at 3× scale (same proportions, higher pixel density). Removed Plotly's default camera/toImage mode bar button. Uses actual chart element dimensions so text and proportions stay identical at any quality. Descriptive filenames retained. Rebuilt index.html.

### 2026-02-28 12:41:20 CST
- Download button replaced with quality dropdown (Low 800×450, Medium 1600×900, High 3200×1800×3x, Original) + Download button, styled as a connected button group. Filename now encodes current settings: dataset, chart type, metrics/model, and time range — e.g. `ARC_House_5_Line_T+RH_AllTime.png` or `ARC_House_5_AdaptiveComfort_RH60Velleiet_2025-01_to_2025-06.png`. Rebuilt index.html.

### 2026-02-28 12:36:56 CST
- Adaptive comfort y-axis label updated to "Air temperature (°C)  [≈ operative temp.]". Rebuilt index.html.

### 2026-02-28 12:36:27 CST
- Adaptive comfort stat boxes: replaced clipped tooltip with in-box hover behaviour — box tints blue on hover and the percentage swaps to show source + sensor ID, reverting on mouseout. Removed data-tooltip from stat boxes. Rebuilt index.html.

### 2026-02-28 12:35:16 CST
- Adaptive comfort y-axis label updated to "Room air temperature ≈ operative temperature (°C)" to clarify the approximation. Rebuilt index.html.

### 2026-02-28 12:28:03 CST
- Replaced native `title` tooltips with CSS `data-tooltip` tooltips (instant on hover, dark box) for all checkbox labels and adaptive comfort stat boxes. Sorted room loggers on adaptive comfort panel by `sidebar_order` to match line graph ordering. Fixed stale data warning incorrectly appearing on Schoolteacher's House — now only shows for datasets using Open-Meteo as external logger. Rebuilt index.html.

### 2026-02-28 12:11:23 CST
- Hover tooltips added to all checkbox labels (line graph and adaptive comfort panels) and adaptive comfort percentage stat boxes, showing sensor source and ID (e.g. "Omnisense · 327601CB"). Govee and Open-Meteo show source only (no redundant ID). Rebuilt index.html.

### 2026-02-28 12:09:40 CST
- Added TinyTag / Omnisense source toggle buttons to the adaptive comfort Room Loggers panel (mirrors the line graph panel). Hidden for Schoolteacher's House. Rebuilt index.html.

### 2026-02-28 12:08:42 CST
- Adaptive comfort legend moved down slightly (y: -0.18 → -0.22) to avoid overlapping x-axis title. Rebuilt index.html.

### 2026-02-28 12:07:42 CST
- Title changed from comma to hyphen: "ARC Tanzania - Temperature & Humidity Graphs". Logger sidebar now ordered by area (Living Room, Kitchen, Study, Mother's Bedroom, Washrooms, Bed 1–4) with TinyTag and Omnisense versions of each room grouped together. Ordering controlled by `sidebar_order` config per dataset. Rebuilt index.html.

### 2026-02-28 12:05:12 CST
- Replaced logo placeholder div with `<img id="logo" src="logo.png">`, height 32px, natural aspect ratio. Rebuilt index.html.

### 2026-02-28 11:59:39 CST
- Fixed "External" sidebar sub-section to only contain truly outdoor loggers (Open-Meteo, External Ambient 861011, Weather Station T&RH 320E02D1). Above-ceiling and below-metal loggers (32760164, 759519, 861968) now correctly appear in the room section. Added `external_sensors` config key per dataset to explicitly control this. Restructured header: top bar now shows logo placeholder + "ARC Tanzania, Temperature & Humidity Graphs" title only; graph controls (dataset, chart type, model, download) moved into the Range/time bar, separated by a divider. Rebuilt index.html.

### 2026-02-28 11:49:48 CST
- Added TinyTag / Omnisense source toggle buttons to the line graph logger panel — visible only for House 5 (hidden for Schoolteacher's House which has no Omnisense loggers). Logger checkboxes now split into "External" sub-section (weather station, ambient, Open-Meteo) above a divider, and room loggers below. Buttons use data-logger-id attributes for reliable matching. Moved page title from the top header bar into the time/range bar. Rebuilt index.html.

### 2026-02-28 11:40:19 CST
- Removed 861968 (Living Room below metal) and 759519 (Bed 4 below metal) from room_loggers — they still appear in the line graph but no longer in adaptive comfort scatter or stats. Removed 6-item cap on comfort stats — all checked room loggers now shown. Rebuilt index.html.

### 2026-02-28 11:30:34 CST
- Govee hover popup no longer shows "ID: govee" — source line shows "Govee Smart Hygrometer" only. Rebuilt index.html.

### 2026-02-28 11:29:39 CST
- Removed hover highlight (restyle on hover/unhover) — too slow with 245k records. Kept default opacity at 0.35. Rebuilt index.html.

### 2026-02-28 11:27:21 CST
- Increased x-axis label density (nticks:20) with -30° angle to prevent overlap. Labels auto-adapt resolution to zoom level. Rebuilt index.html.

### 2026-02-28 11:26:45 CST
- Line graph: default trace opacity lowered to 0.35 so overlapping lines blend visibly. Hover highlight: hovered logger group jumps to full opacity while all others dim to 0.07, restores on unhover. Threshold and season lines unaffected. Rebuilt index.html.

### 2026-02-28 11:24:31 CST
- Renamed "Dauda's House" → "Schoolteacher's House" everywhere (dataset label, dropdown, docs). Logger 759498 display name → "Bedroom 1", govee → "Living Space". Govee source type shows "Govee Smart Hygrometer" in hover popup. Updated all MD files. Rebuilt index.html.

### 2026-02-28 11:21:04 CST
- Fixed Open-Meteo color to light cyan (#17becf), swapped with Omnisense 32760371 (Bed 3). Removed hardcoded x-axis tick format/dtick — Plotly now auto-formats labels based on zoom level (shows hours when zoomed in, days/months when zoomed out). Added "Date / Time" x-axis title. Rebuilt index.html.

### 2026-02-28 11:16:43 CST
- X-axis now snaps to the actual data range of selected loggers (not the full dataset/time-filter range). Y-axis padded to nearest 1.5 units for breathing room. Season lines and 32°C threshold adapt to the snapped range. Removed "OS:" prefix from Omnisense logger names. Moved light cyan (#17becf) color to Bed 3 (above ceiling) / 861004. Rebuilt index.html.

### 2026-02-28 11:13:27 CST
- Removed 759498 (Schoolteacher's House logger) from House 5 dataset via `exclude_loggers` — it remains in Schoolteacher's House dataset only. Open-Meteo color changed to light cyan (#17becf) with swap logic to avoid clashes. House 5 now 24 loggers. Rebuilt index.html.

### 2026-02-28 11:11:42 CST
- Fixed x-axis overshooting data range — now snaps to actual data bounds. Removed season label thinning so all four season boundaries (June Dry, Short Rains, January Dry, Long Rains) show labels. Rebuilt index.html.

### 2026-02-28 11:10:48 CST
- Removed sensor IDs from logger display names (checkboxes, legend). ID and data source (Omnisense/TinyTag) now shown in hover popup instead. Added Select All / Deselect All buttons for both logger and room logger checkbox lists. Rebuilt index.html.

### 2026-02-28 03:02:37 CST
- **Merged omnisense_t_h into this project.** Omnisense CSV sensors (10 T&H loggers) and Open-Meteo external temperature now load alongside TinyTag .xlsx loggers in the House 5 dataset. Added `load_omnisense_csv()` and `load_external_temperature()` functions. Open-Meteo replaces TinyTag 861011 as the adaptive comfort running mean source (861011 stays as a regular logger). Brought across density heatmap (`histogram2dcontour`) on adaptive comfort chart, and stale data warning banner when Open-Meteo coverage is shorter than sensor data. Title updated to "Ecovillage — Temperature & Humidity". Omnisense loggers prefixed "OS:" in legend. Schoolteacher's House dataset unchanged. Rebuilt index.html (256k House 5 records / 25 loggers).

### 2026-02-27 14:07:16 CST
- Changed default comfort model to Vellei RH>60%. Rebuilt index.html.

### 2026-02-27 13:47:22 CST
- Adaptive comfort: reduced scatter marker opacity 0.6→0.2 for density visualisation. Rebuilt index.html.

### 2026-02-27 12:45:40 CST
- Fixed JS spread operator stack overflow on large arrays in adaptive comfort graph. Replaced `Math.min(...allExtTemps)` / `Math.max(...allExtTemps)` and `push(...array)` with explicit `for...of` loops — fixes House 5 (174k records) silently failing to render adaptive comfort. Rebuilt index.html.

### 2026-02-27 (time not recorded)
- Created `build.py` and `index.html`: static HTML dashboard for House 5 and Schoolteacher's House TinyTag Excel loggers. Reads .xlsx files from data/house5/ and data/schoolteacher/, embeds both datasets as separate JSON blobs. Dataset switcher in header reloads all controls instantly client-side. EN 15251 exponential running mean (alpha=0.8) for adaptive comfort. All features from omnisense_t_h preserved: line graph, adaptive comfort, time range filtering, logger/metric selection, season lines, 32°C threshold, comfort stats, PNG download, full responsive layout.
CLAUDE.md