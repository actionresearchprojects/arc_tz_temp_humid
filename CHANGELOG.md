## Changelog

### 2026-09-07 01:12:06 CST
- **UK Open-Meteo now uses each building's own grid cell, over its own date range** - The coordinates supplied for Grove Cottage and Holywell Barn were checked against the API before being committed, and the town-centre positions already in use turned out to sit in the **same Open-Meteo grid cell** as both buildings: the weather data had been correct all along. What changed is what gets published. Both feeds now request the **model grid cell centre** (Grove 52.057774, -2.704697; Holywell 52.926643, -4.230377), which returns byte-identical data because any point in a cell resolves to that cell, while the committed number is a fixed feature of the weather model rather than a private address in a public repository. The cell centres sit 0.60 km and 0.65 km from the buildings.
- **Feeds start from each building's own record, not 2023** - `start_date` is now the first sensor reading (2026-07-31) minus a 30-day lead-in, cutting each feed from ~30,500 rows to 1,608. The lead-in is deliberate rather than padding: the EN16798-1 running mean is seeded from its first day and decays that seed by alpha=0.8 daily, so starting exactly at the first indoor reading would leave the opening fortnight of comfort points measured against a running mean still carrying an arbitrary seed. Thirty days reduces the seed's weight to roughly 0.1%, and reproduces the running means previously obtained from three and a half years of history to within 0.1-0.3 C.
- **ARC UK Omnisense fetch wired up** - `SITES["uk"]` filled in with site number 58345 ("Simmonds.Mills Retrofits"), and a `--site uk` step added to the daily workflow beside the Tanzanian one, sharing the same credentials since one login sees both sites. **Not yet exercised**: the secrets are not available locally, so the first scheduled run is the test. The step is `continue-on-error` and the hand-added export remains the fallback.

### 2026-09-07 00:54:24 CST
- **Read CIBSE TM59 (2017) and recorded what it actually requires** - The threshold question turns out to be less open than "pick a number". Compliance for a naturally ventilated home is both of: **(a)** living rooms, kitchens and bedrooms, hours where dT is at least 1 K over May to September no more than 3% of occupied hours, measured against the **adaptive** limit (TM52 Criterion 1) rather than a fixed temperature; and **(b)** bedrooms only, operative temperature between 22:00 and 07:00 not above **26 C** for more than 1% of annual hours, which TM59 counts as 32 hours so 33 is a fail. The only fixed figure in the document is therefore 26 C, bedrooms, night hours. Grove's sensor is a living room, so no fixed band applies to it; Holywell's "Internal Ambient" room type is unconfirmed and is the one thing worth checking. `OUTSTANDING.md` section 2 sets out three options and two caveats - TM59 evaluates modelled operative temperature under standard occupancy profiles, while this dashboard plots measured air temperature, and criterion (a) is adaptive against TM52 Category II rather than either band the dashboard currently offers.
- **Measured how much Open-Meteo coordinate precision actually matters** - Open-Meteo snaps a request to its model grid, and that grid is finer than the commonly quoted 11 km: a 0.5 km move lands in a different cell. Against the Hereford baseline over 2208 hours, June to August 2026, a 0.5 km offset shifts the series by 0.18 C on average, 2 km by 0.51 C (max 4.0 C) and 9 km by 1.52 C. So half a kilometre of precision is worth having, which is two decimal places of latitude and longitude. Recorded in `OUTSTANDING.md` section 3 along with the reason to round: these are private homes and this repository is public, so an exact committed coordinate is effectively a published home location, while two decimals puts the request in the right grid cell without pinpointing a dwelling.
- **`OUTSTANDING.md`: rename section removed** - The repository rename and the main-site move are complete, so they are no longer listed as outstanding; the remaining sections are renumbered. `CLAUDE.md` updated to match reality on the Open-Meteo feeds, the UK comfort sources and the TM59 position.

### 2026-09-07 00:28:15 CST
- **Main site moved to the rebranded addresses** - `/graphs/arc-temp-humid/`, its `/config` page and `/explainers/arc-temp-humid/` are live and read from `embedded/arc_temp_humid/`. The old addresses are redirects rather than removals, so existing links keep working. The explainer is regenerated from this repo's current README, and the data flow explainer from its current `dataflow.md`.
- **`sync-embedded.yml` maps both repository names to one folder** - This is what made the rename safe to do at any moment rather than something that had to be choreographed with the site. Without it the first sync after the rename would have filled a second folder while the published page went on serving the first, frozen.
- **Removed the superseded `embedded/arc_tz_temp_humid/` copy** - Roughly 16 MB, no longer referenced by anything, deleted once the new folder was confirmed serving.

### 2026-09-07 00:12:17 CST
- **Repository renamed to `arc_temp_humid`; follow-ups applied** - The rename went through cleanly because the main site now maps both the old and new names to `embedded/arc_temp_humid/`, so nothing had to change in lockstep. The git remote, both workflow `repository_dispatch` payloads and `dataflow.md` now use the new name, and `OUTSTANDING.md` section 1 records the move as done. The only remnant is the superseded `embedded/arc_tz_temp_humid/` folder on the site repo, kept as a fallback and safe to delete.

### 2026-09-06 21:42:40 CST
- **Open-Meteo for Grove Cottage and Holywell Barn, one feed each** - The two buildings are about 150 km apart, so a single UK feed would have been wrong for at least one of them. `OPENMETEO_FEEDS` now holds a feed per location, each with its own logger IDs, output directory and timezone, and `fetch_openmeteo.py` gained matching `LOCATIONS` entries fetched daily by the workflow. Each building's feed drives its own adaptive comfort running mean, and both appear on the ARC UK chart. The Tanzanian IDs keep their original names, which are baked into `config.json`, the snapshot and every saved user override.
  - Running-mean fallbacks are now scoped to the owning building. Previously the fallback list was every Open-Meteo series in the dataset, which in a region would have quietly mixed Grove and Holywell weather into one running mean on days the primary was missing.
  - Each feed is localised with its own zone rather than one global default, since the API returns local time for the location requested.
  - Verified the feeds are genuinely distinct: Grove averages 1.03 C warmer than Holywell over 30,497 paired hours, only 611 of them identical.
  - Coordinates are town-centre positions for Hereford and Criccieth, flagged in the source and in `OUTSTANDING.md` as worth replacing with the exact ones.
- **Adaptive comfort source for the UK is now Open-Meteo rather than the on-site sensor** - The on-site external ambients start in July 2026, and a running mean needs the days preceding a reading; the Open-Meteo feeds reach back to March 2023. The on-site sensors stay plotted and remain selectable per logger in config.html.
- **Drop the heating caveat from above the chart** - It is permanent for a site rather than a property of the current view, and the sidebar applicability panel already carries it in full immediately beside the chart. Only view-dependent caveats belong above the plot, so the top margin returns to its base 30px on the UK datasets. The sidebar note and the tooltips are unchanged.
- **Replace every em dash and en dash with a plain hyphen** - Across `arc_temp_humid`, `arc_tz_line` and `arc_tz_weather`: 819 replacements over 25 source files, covering the literal characters and the `\u2013` / `\u2014` escapes in the JS templates. Box-drawing characters used for section rules are a different codepoint and were deliberately left alone. All three dashboards rebuilt and their generated JS re-checked.

### 2026-09-06 20:51:29 CST
- **Fix: the rebrand broke the main-site sync** - Both workflows had their `repository_dispatch` payload changed to `"source_repo":"arc_temp_humid"` as part of the rebrand, but the repository has not been renamed yet. The main site's `sync-embedded.yml` clones the repo by that name, so the first sync after the push failed with `fatal: could not read Username for 'https://github.com'` - git prompting for credentials on a repository that does not exist. The payload now names the repo as it actually is, `arc_tz_temp_humid`, in both workflows and in `dataflow.md`, each commented to say when to flip it. Same mistake as the explainer link, caught for the same reason: a value that follows the *live* GitHub state cannot be updated ahead of that state changing.
  - The live dashboard was never at risk - the sync simply failed, leaving the previous embedded copy in place.
- **`OUTSTANDING.md`: the rename is now a strictly ordered checklist** - The payload and the repository name have to change together; either alone breaks the sync, so the gap between renaming and flipping the payload should be as short as possible. Added as item 7, with the ordering rewritten around it.

### 2026-09-06 20:47:31 CST
- **Keep the header explainer link on the old slug until the site catches up** - The rebrand changed the info-icon link to `/explainers/arc-temp-humid`, but that path does not exist yet: the explainer folder on the main site is still `explainers/arc-tz-temp-humid`. Shipping the new link would have put a live 404 behind the icon for however long the rename takes. It now points at the working path, with a comment saying why and when to switch it.
- **Add `OUTSTANDING.md` and `OUTSTANDING.pdf`** - What is left to do, why, and in what order. Covers the repository rename and the main-site changes that must accompany it, automating the UK Omnisense fetch, the undecided UK overheating threshold, an optional UK Open-Meteo feed, and the heating-status limitation that no amount of code will close. Rendered to PDF with the shared explainer stylesheet via `.explainer-tools/genviewer.py`.
  - The rename analysis is the important part. GitHub redirects the old repo URL, so nothing obvious breaks - but `sync-embedded.yml` on the main site derives its destination folder from the dispatch payload's `source_repo`, which this repo now sets to `arc_temp_humid`. The next sync would therefore write a **new** `embedded/arc_temp_humid/` while `graphs/arc-tz-temp-humid/` keeps iframing the old folder, frozen. No 404, no error - the live dashboard would simply stop updating. The document lists the six main-site changes needed and the order to make them in.

### 2026-09-06 20:20:15 CST
- **State the ASHRAE 55 criterion that cannot be verified** - Section 5.4.1(a) requires that no heating is in operation. Unlike the 10-33.5 C running-mean limits, this cannot be checked against the data: no site records heating status, and nothing in a temperature and humidity trace reliably separates a heated room from a warm one. A new per-dataset `heating_unverified` flag marks where that is true (UK yes; Mkuranga no, the buildings have no heating), and where it is, the dashboard says so in all three places a reader meets the method: a standing note on the comfort chart, a bolded line in the sidebar's applicability panel directly beneath the quoted criterion, and the tooltips that explain the band and the running mean. An unverifiable criterion passed over in silence reads as one that was met.
  - No attempt is made to infer heating status from the data, and no May-September filter is imposed. Both were considered and rejected: inferring it would invent a signal that is not there, and an inferred exclusion is harder to argue with than an acknowledged gap.
  - The chart note is deliberately terse ("ASHRAE 55's 'no heating in operation' criterion cannot be verified at this site") while the sidebar and tooltips carry the full wording - a 200-character sentence across the top of a plot was clipping at the plot edge. Annotations now also set an explicit `width` so a long line wraps instead of being cut off, and the chart's top margin grows per caveat line (30px base, 45 with one, 60 with two).
- **`adaptivecomfort.md`: document the applicability decisions** - Section 2 gains the running-mean gate (grey rather than dropped, excluded from the statistic, and why calendar-month filtering was rejected) and a new subsection on the criterion that cannot be verified, including the consequence worth stating plainly: the gate catches cold-weather readings, but a mild day with the heating on passes every test the dashboard can apply and still sits outside the standard's scope. Also added to the known-limitations list.
- Verified in headless Chrome: the caveat appears on all three UK datasets and on none of the Tanzanian ones, in both English and Kiswahili, across the sidebar panel, the chart annotation and the tooltip path; and all four caveat combinations (neither, heating only, range only, both) lay out with the correct margin.

### 2026-08-31 22:30:39 CST
- **Adaptive comfort default is now per region: ASHRAE 55 80% for ARC UK** - The Vellei et al. models exist to correct for how people adapt in humid tropical conditions, which is the case at Mkuranga and not in the UK; their 0.53 slope (against ASHRAE's 0.31) also makes the band very sensitive to the running mean at the cool end where UK data sits. Checked against the sensors before choosing: indoor RH medians are 55.0% at Grove and 59.0% at Holywell, so the previous `rh_gt_60` default was the wrong Vellei band anyway (Grove sits in 40-60% for 78% of readings). `DATASETS[key]["comfort_model"]` drives it; both remain user-selectable per session.
- **Overheating threshold is per region, and absent for the UK** - The 32-35 C band was hardcoded across the line, histogram and averages charts. It is a Mkuranga heat-stress range and means nothing against UK data peaking near 29 C, so `arc_uk`/`grove`/`holywell` declare none: no band is drawn and the sidebar control is hidden rather than offering a meaningless toggle. The label is composed from the region's own numbers instead of being a fixed string. A UK figure should come from CIBSE TM52/TM59, which is per-room-type (TM59 uses 26 C for bedrooms), so no number is assumed here.
- **Adaptive comfort marks readings the standard does not cover** - ASHRAE 55 Section 5.4.1(d) validates the method only for a prevailing mean outdoor temperature of 10-33.5 C. Points outside are drawn grey in place rather than dropped, with a note giving the proportion, and are excluded from the percentage statistic - a compliance figure must not count conditions the method was never validated on. Filtering by calendar month was considered and rejected: months are not the criterion, and a fixed "May-September" would be wrong in a cool summer and wrong again at the next site. Mkuranga is unaffected (running mean 23.2-28.9 C, entirely inside the window); UK winters will not be.
  - The other applicability criterion - no heating in operation - cannot be tested, since nothing records whether the heating was on. It is stated in the explainer rather than silently assumed.
- **Fix: region defaults never applied on a dataset switch** - `resetComfortDefaults()` is wired only to the "Reset to default" button and does not run when the dataset changes, so the per-region comfort model and threshold control were both dead on arrival. The region-dependent parts are now an `applyRegionDefaults()` called from `loadDataset()` as well.
- **Fix: comfort statistics went stale when every reading was excluded** - With no reading inside the validated range the panel hid itself and kept the previous percentage in the DOM, so a UK winter selection would have made the statistics silently disappear. It now says so explicitly, naming the range.
- Verified in headless Chrome across all six datasets: comfort model and threshold visibility follow the region on the line, histogram and comfort charts; and by narrowing the validated window at runtime to simulate winter, that the grey marking, the proportion note, the exclusion from the statistics and the all-excluded message each behave correctly and revert cleanly.

### 2026-08-31 20:07:02 CST
- **Fix: the season-label gap persisted on charts with no season lines** - The line graph reserved its tall top margin (85px) from `state.showSeasonLines` alone, so any window containing no boundary still got the blank strip the rotated labels would have occupied. The margin now follows whether a label is actually drawn, which is the thing it exists for. Tanzanian views are unaffected (13 boundaries in range, 85px); the UK views drop to the standard 10px and the plot starts directly under the title.
- **Chart type selector uses the same bespoke menu as the building selector** - The picker built for the building selector is now a reusable component driving both, plus the beta sub-menu. Each wraps its existing `<select>`, which stays in the DOM as the source of truth: picking a row writes the value and dispatches a real `change` event, so `handleChartTypeChange` and every other listener work untouched, and a `change` from anywhere re-renders the menu automatically. Beta Features is red and italic in the list, and the closed button takes the same treatment while a beta view is active - replacing the old inline `mainSel.style.color`. The beta sub-menu's visibility moved from the native select to its wrapper, since the select itself is now permanently hidden. Without JS the native selects still render normally, because the class that hides them is added by JS.
- Verified in headless Chrome: top margin is 85px on the three Tanzanian datasets and 10px on the three UK ones, matching the boundaries actually drawn; and the full chart-type path - open, pick Beta Features, sub-menu appears, pick Thermal Lag, back to Histogram - leaves the right `state.chartType`, hides the sub-menu again and clears the red accent.

### 2026-08-31 19:50:22 CST
- **Fix: season lines vanished everywhere, and the UK charts never rendered** - Both came from one mistake in the season refactor. The old `SEASONS` array carried a `day` on every entry; the `bounds` entries that replaced it carry only a `month`, so `getSeasonBoundaries` was calling `localToMs(y, month-1, undefined)` and getting `NaN`. On the Tanzanian datasets the `NaN >= startMs` comparison is simply false, so every boundary was silently discarded - no vertical lines, and the top margin Plotly reserves for their labels left a blank strip. On the UK datasets it was fatal: `Europe/London` has no fixed offset, so `tzOffsetMs` falls through to `Intl.DateTimeFormat.formatToParts`, which throws `RangeError: Invalid time value` on an invalid date, and the exception stopped the chart before it drew - hence "Loading chart…" forever. Boundaries are always the first of a month, so the call now passes `1` explicitly. `tzOffsetMs` also returns early on a non-finite input, so a bad timestamp can never again take down a render; the fixed-offset zones had been masking exactly that class of fault.
  - UK charts still show no season lines today, correctly: the data spans 31 Jul - 31 Aug 2026 and the next UK boundary is 1 Sep. Over a full year the UK scheme yields its four boundaries as expected.
- **Replace the building selector with a bespoke menu** - Chrome ignores nearly all styling on `<option>`, so the indented-text approach could not make a region read as a heading while staying selectable. The region rows are now small uppercase headings that are still clickable, with their buildings indented beneath and the current selection highlighted. The real `<select>` stays in the DOM, hidden, as the source of truth: the change event, `dsLabel()` and the `data-i18n` translation pass all keep working untouched, and the menu is re-rendered from it on dataset and language change. Opens on click or keyboard, closes on pick, outside click or Escape, with arrow-key movement between rows.
- **Verified by rendering** - All six datasets were loaded in headless Chrome: each draws its traces with no console errors and no stuck loading overlay, and the axis annotation reads "EAT, UTC+03:00" or "GMT/BST" per region. (One opaque cross-origin "Script error." appears on load; it is present on the pre-change build too and is unrelated.)

### 2026-08-31 19:09:51 CST
- **Rebrand to `arc_temp_humid` and add the ARC UK buildings** - The dashboard is no longer Tanzania-only, so the Tanzanian marker is gone from the repo name, the folder, the page URL and the title. Repo `arc_tz_temp_humid` → `arc_temp_humid`, published at `/graphs/arc-temp-humid`, header now reads "ARC - Temperature & Humidity Graphs" (Kiswahili "ARC - Grafu za Joto na Unyevunyevu"). Updated in `config.html`'s `REPO_NAME` and PAT instructions, both workflow `repository_dispatch` payloads, `check_staleness.py`'s secrets link, the explainer link, `fetch_openmeteo.py`'s User-Agent, `README.md` and `dataflow.md`. The GitHub repo rename itself is still to be done by hand, along with the main site's embed path.
- **Two new buildings: Grove Cottage (Hereford) and Holywell Barn (Criccieth)** - Omnisense-only datasets drawn from a single manual export in `data/omnisense_uk/`, each filtering the shared CSV down to its own sensors. Grove: `1C290049` External Ambient (external, adaptive comfort source) and `169502D1` Living Room (No. 57). Holywell: `19550131` External Ambient, full shade (external, comfort source) and `0E3C12EC` Internal Ambient. Names are defaults taken from the Omnisense `sensor_desc` field and are editable in config.html. Neither has an Open-Meteo feed yet; each uses its own external ambient sensor for the running mean.
- **Region datasets: ARC Tanzania and ARC UK** - Both are selectable in their own right and show every logger from the buildings beneath them. A region is the union of its members' *finished* data, so each logger arrives with its own building's date filters already applied and keeps the external source its building resolved (House 5 rooms still use `861011`/`320E02D1` inside ARC Tanzania; Schoolteacher's still uses Open-Meteo). Members are built first; regions are assembled after. Because names repeat across buildings - House 5 and the Schoolteacher's House both have a "Bedroom 1" - the sidebar gains a per-building sub-heading inside each section, in normal and compare mode. Open-Meteo carries no building heading: it is model data, not a building's sensor.
- **Building selector is now two-level** - Region rows sit flush with their buildings indented beneath them, and every row is selectable. A native `<optgroup>` label cannot be clicked, so the region *is* the row rather than a heading above it; the indent is non-breaking spaces, which survive the whitespace collapsing a `<select>` applies. `dsLabel()` strips that indent so it never reaches a chart title or an export filename. House 5 remains the default, but it is no longer the first option, so `loadDataset()` now syncs the control to the state explicitly.
- **Timezone is per-dataset instead of a fixed UTC+3** - ARC UK is `Europe/London` and observes DST, which a single global offset cannot express. Every reading still displays as wall-clock time at its own site regardless of the viewer's browser. `toEATString`/`eatDate` become `toLocalString`/`localDate`, `fmtDateEAT` becomes `fmtDateLocal`, and `localToMs` inverts the conversion for season boundary markers. `tzOffsetMs` resolves the offset with `Intl` and memoises it per UTC hour - exact, because DST transitions land on hour boundaries - while zones without DST short-circuit through `TZ_FIXED_OFFSET`, so the Tanzanian path stays plain arithmetic. Axis annotations, the CSV export header and the periodic-averages axis now read the dataset's own label ("EAT, UTC+03:00" or "GMT/BST") rather than a hardcoded string. On the Python side `dataset_tz(key)`/`localize()` replace the module-level `TIMEZONE` at every localisation and filter-cutoff site. Verified against the 2026 UK transitions and by round-tripping wall-clock readings on both sides of each.
- **Seasons are per-region** - Tanzanian season names on a Herefordshire cottage were simply wrong. `SEASON_SCHEMES` now holds `tz` (Kiangazi/Masika/Kiangazi/Vuli) and `uk` (meteorological: Winter Jan-Feb, Spring, Summer, Autumn, Winter Dec). UK winter straddles the new year, so it occupies two blocks of the calendar - exactly as Kiangazi already did - which means a scheme can have more than four seasons. The hardcoded four-element arrays and `nCats = 4` at eleven sites are replaced by scheme lookups, covering the period selector, substratification filters, auto-recommendation, periodic-average categories and boundary lines, and export filenames. The periodic axis title says "Tanzanian Season" only for the Tanzanian scheme.
- **config.html still edits buildings only** - Regions are excluded from `data/loggers.json` so no logger is editable in two places. A building's overrides are pushed into every region containing it, at build time via `region_overrides()` and at runtime via `applyUserConfig`, so a name edited once shows up everywhere. Compare mode's cross-dataset list likewise offers buildings only, since a region would repeat loggers already on the list.
- **Fetch scripts parameterised by site, ready for the UK feeds** - `fetch_omnisense.py` takes `--site` against a `SITES` dict and `fetch_openmeteo.py` takes `--location` against `LOCATIONS`; both have a commented-out `uk` entry naming exactly what to fill in. Only the Tanzanian entries are active, and their output is byte-identical to before. The UK Omnisense export is added by hand to `data/omnisense_uk/` until the site number is filled in.

### 2026-08-17 20:49:06 CST
- **Show the unadjusted upper boundary when an air speed allowance is active** - A dotted green line now traces where the upper limit would sit at the 0.3 m/s baseline, drawn alongside each band whenever a higher air speed is selected. At Mkuranga the entire band sits above the 25 °C gate, so the allowance lifts it uniformly and the chart gave no indication of how much had been added; the dotted line makes the size of the adjustment readable directly off the chart. Noted in the chart caption and the air speed tooltip, both languages. The band traces are now assembled as one block so the draw order is explicit: fills at the back, baseline markers over them, scatter points on top.

### 2026-08-17 20:25:10 CST
- **Add a 25 °C reference line to the adaptive comfort chart** - The elevated-air-speed allowance switches on where the upper boundary crosses 25 °C (Section 5.4.2.4). At Mkuranga the whole band already sits above that threshold, so raising air speed lifts the band uniformly with no visible step and no on-chart explanation for the movement. A dashed marker at 25 °C, labelled in both languages, is now drawn whenever air speed is above the 0.3 m/s baseline, and omitted at baseline where it would mark a rule that is doing nothing.
- **Add `adaptivecomfort.md` and publish it as an explainer** - Records the acceptability limits, the air speed allowance, why the 25 °C gate is an indoor rather than an outdoor temperature, what the Vellei prediction intervals actually represent, the decisions taken, the verification performed, and the known limitations. Published at `/explainers/adaptive-comfort` alongside a PDF rendering, and linked from the comfort band tooltip in both languages.

### 2026-08-17 00:00:15 CST
- **Add ASHRAE 55 acceptability limits and an elevated-air-speed adjustment to the adaptive comfort chart** - The comfort band was previously a single fixed width per model with no way to state which acceptability level it represented and no account of air movement. Both are now explicit.
- **Replace the broken "Default comfort model" with true ASHRAE 55 options** - The old default was `0.31·Tpma + 17.3 ± 3.0`, which produced a band running from `0.31·Tpma + 14.3` to `0.31·Tpma + 20.3`: the 80% lower limit paired with the 90% upper limit. That is not a band defined anywhere in ASHRAE 55, and because the comfort statistic defaults to "below upper boundary", every overheating figure that model produced was measured against the stricter 90% line. It is replaced by two correct entries built on the Section 5.4.2.2 centre line of `0.31·Tpma + 17.8`: **ASHRAE 55 - 80% acceptability** (±3.5, the compliance limits) and **ASHRAE 55 - 90% acceptability** (±2.5, informative only per the Section 5.4.2 note). Overheating percentages on the 80% option read roughly one degree more permissive than the old default.
- **Air speed selector (0.3 / 0.6 / 0.9 / 1.2 m/s)** - Applies the Δt₀ values from Table 5-13 (+1.2, +1.8, +2.2 °C) to the upper boundary only, and only where that boundary exceeds 25 °C, per Section 5.4.2.4. Kept as a dropdown rather than a free numeric field because the standard defines only these three increments and gives no basis for interpolating between them. Defaults to 0.3 m/s, which applies no adjustment, so nothing changes unless the setting is deliberately moved.
- **The 25 °C gate produces a genuine discontinuity, and it is drawn as one** - The band is sampled at 80 evenly spaced points; a step falling between two samples would render as a diagonal ramp. The crossing `x = (25 − c − delta) / m` is now injected into the sample array twice, once carrying the unelevated value and once the raised one, giving a vertical edge. For the ASHRAE models this lands at Tpma ≈ 11.9 °C (80%) and ≈ 15.2 °C (90%), matching the CBE Thermal Comfort Tool.
- **Optional nested 80%/90% pair** - A checkbox draws both ASHRAE bands at once, the wider 80% beneath the 90%, as the CBE chart does. Hidden for the Vellei models, which have no 90% variant to draw.
- **Air speed is recorded on the chart and in exports** - The assumed value is written into the chart annotation whether or not it is the baseline, and appended to the PNG filename when it is not, so two exports taken at different air speeds cannot be mistaken for each other. It is an assumption, not a measurement; no air speed is recorded at these sites.
- **Why the Vellei bands carry no acceptability toggle** - Their half-widths (±2.84, ±3.70, ±4.40) are 95% prediction intervals around each regression, not acceptability percentages. The 80% criterion is applied upstream in the paper, by discarding grid bins where fewer than 80% of votes were neutral, and the paper notes the medium-RH band comes out equal to ASHRAE's own acceptability range. They are therefore already the 80% bands, there is no 90% variant published, and none can be derived by scaling. The air speed tooltip also warns that Vellei's field data came from buildings whose occupants were already using fans, so the Table 5-13 adjustment may count that benefit twice.
- **Fix: the "Comfort band" sidebar label never translated** - `setDivLabel('comfort-model', …)` walks to the select's previous element sibling, which is the tooltip div rather than the label, so it blanked the hidden tooltip and left the label in English on every Kiswahili switch. The label now carries `data-i18n` like every other translated element, and the broken call is removed. `comfort-pct-mode` was unaffected and still uses `setDivLabel`.
- **Fix: applicability note said 1.0-1.3 met** - ASHRAE 55-2020 Section 5.4.1(b) gives 1.0 to 1.5 met; 1.0-1.3 is the EN 16798-1 figure. Corrected in `build.py`, `README.md` and `runningmean.md`, both languages.

### 2026-08-16 23:27:55 CST
- **Drop the `NOTE:` prefix from the adaptive comfort applicability text** - The panel is already headed "Applicability" and sits in an amber callout box, so the word was doing no work that the surrounding design was not already doing. Paragraph text is unchanged. Removed in both languages (`NOTE:` in English, `KUMBUKA:` in Kiswahili) and in all five places the sentence appears: the inline markup and both translation tables in `build.py`, plus the copies in `README.md` and `runningmean.md` that are the source of the linked explainers.

### 2026-08-16 22:33:53 CST
- **Add: adaptive comfort applicability note** - The adaptive comfort method is only valid for occupant-controlled naturally conditioned spaces meeting all three ASHRAE 55 conditions (no mechanical cooling installed and no heating in operation; metabolic rates of 1.0-1.3 met; occupants free to adapt clothing across at least 0.5-1.0 clo). Nothing on the dashboard said so, which left the comfort band open to being read as a comfort assessment for spaces the method does not cover. The note now appears as a standing amber panel beneath the comfort band selector - visible the whole time the comfort chart is open rather than behind a hover - and is appended to all three tooltips that explain the method: the Adaptive Comfort chart-type tooltip, the comfort band tooltip, and the running mean tooltip on the x-axis. Added to `runningmean.md` and `README.md` as well, since those are the source of the linked explainers. Both languages.
- **Fix: chart-type tooltip switched from `textContent` to `innerHTML`** - Needed so the appended note renders as formatted text rather than as literal markup, which is the same failure the statistics table hit with Plotly table cells. Checked first that none of the ten strings reachable from that tooltip contains a stray angle bracket.
- **Fix: applicability panel carries its English text inline** - `applyLanguage()` runs only when the stored language is not English (`setLanguage()` is skipped for the default), so an element relying on it to populate would have rendered blank for every English user. The panel now holds its default English text in the markup, as every other `data-i18n` element does, with the attribute driving only the Kiswahili switch.
- **Note: the exported PNG does not carry the applicability note** - Adding it means either a chart annotation, which changes the plot area on a chart whose legend already sits at `y: -0.22`, or a footer injected into the exported SVG. Both are layout changes that cannot be verified without rendering the page, so neither was made. Worth revisiting, since a PNG dropped into a report is exactly the context where the caveat is most likely to be needed and least likely to be present.

### 2026-08-16 22:04:45 CST
- **Add: XLSX export alongside CSV** - The export menu gains Export XLSX, producing the same layout as the CSV. An `.xlsx` is a ZIP of XML parts, and both are written by hand: these dashboards are single self-contained pages under a strict CSP, so no spreadsheet library can be pulled in. `zipBytes()` writes local file headers, a central directory and an EOCD record with CRC-32 computed in-page; `sheetXml()` emits the worksheet with a minimal five-part package (`[Content_Types].xml`, the two `.rels` files, `workbook.xml`, `sheet1.xml`). Compression uses the platform's `CompressionStream('deflate-raw')` where available, falling back to stored entries - worth having, since a wide "All time" export runs to tens of megabytes as XML.
- **Change: CSV and XLSX share one row builder** - `chartCsvText()` became `chartExportRows()` returning an array of rows, with `rowsToCsv()` joining them; `statsCsvText()` likewise became `statsExportRows()`. Both formats now derive from the same rows, so they cannot drift apart. Verified cell-for-cell: a statistics export round-tripped through `openpyxl` matches the CSV in every cell.
- **Note: XLSX carries the types CSV cannot** - Values that are numbers, or strings that are wholly numeric, become real numeric cells, so a spreadsheet sorts and charts them without the text-to-number step a CSV needs. Confirmed via `pandas.read_excel`, which types the statistics columns as `int64`/`float64` rather than `object`. Timestamps, percentages and signed ΔT values stay text. `colRef()` handles columns past Z, which a wide line-graph export reaches. Empty cells are omitted rather than written blank, which keeps sparse pivoted exports smaller.
- **Note: `arc_tz_line` and `arc_tz_weather` did not receive this change** - Both directories became inaccessible to tooling partway through the session (`EPERM` on read, list and git), after their export-menu commit but before XLSX was written. The change is mechanical and identical for both: replace the shared export block, add the `xlsx` option and its two i18n strings, and route it through `exportCurrentXlsx()`.

### 2026-08-15 12:46:09 CST
- **Add: export menu replacing the Download PNG button (all three dashboards)** - The single green button becomes a green `<select>` offering Download PNG and Export CSV, applied identically in `arc_tz_temp_humid`, `arc_tz_line` and `arc_tz_weather`. It acts on selection and returns to its "Download…" placeholder. The PNG routine, previously an anonymous click handler, is now a named `downloadChartPng()` the menu calls; the original button remains in the DOM but hidden, because that routine uses it as its disable/spinner target.
- **Add: CSV export of the plotted data** - `chartCsvText()` reads the traces back off the chart element (`chartEl.data`) rather than from any particular render function, so one implementation serves every chart type in all three dashboards regardless of how differently they dispatch rendering. It exports exactly what is on screen for the period currently selected, honouring the logger selection, date range and any legend toggles. Series whose x values are shared strings - timestamps or categories - pivot into one column per series, which is what a spreadsheet wants; scatter and histogram data, which have no shared x, fall back to one row per point. Legend-only placeholder traces (a single null point, used for the ΔT = 0 and threshold-band entries) are dropped, axis titles are stripped of their HTML for the column headings, fields containing commas are quoted, and a UTF-8 BOM is prepended so Excel renders °C correctly. A missing point leaves an empty cell rather than a zero.
- **Change: Summary Statistics keeps its own export** - On `beta-stats` the PNG option is hidden from the menu, since there is no plotted figure to render, and Export CSV routes to `downloadStatsCsv()` so it emits the statistics table rather than an empty chart. The duplicate `downloadCsv` i18n key introduced with that view was removed: it collided with the new menu label and, being the later definition in the object literal, was silently overriding it.

### 2026-08-14 21:02:59 CST
- **Add: Summary Statistics chart type (`beta-stats`)** - Until now the dashboard computed no descriptive statistics at all: `median`, `percentile`, `quantile` and `stdev` appeared nowhere in `build.py`, and the two panels that read like statistics boxes (`#hist-stats-box`, `#comfort-stats`) report data-completeness percentages and gap warnings, not summaries of the readings. The only aggregation anywhere was the mean-only Average Profiles chart. Added a Summary Statistics view to the Beta Features sub-dropdown. Per-logger rows report n, coverage, mean, median, min, max, SD, P5, P95 and mean diurnal swing; temperature additionally reports the share of readings at or above 32 °C and 35 °C, making the existing 32-35 °C shaded band numeric for the first time. Group rows for External, Room and Structural are interleaved after their members, and an overall row closes the table. It is the one Beta view driven by logger selection, so `handleChartTypeChange` keeps `line-controls` visible for it and stops filtering the logger list down to room sensors, while the other Beta views still do both.
- **Change: statistics render as an HTML table, not a Plotly `table` trace** - The first implementation used a Plotly table so it could reuse the Plotly render path. Two problems made that untenable. Plotly table cells render their contents as literal text, so the `<span style="color:#aaa">` markup that `ln()`/`omniSuffix()` add for sidebar colouring appeared verbatim in the header and logger cells. And Plotly tables emit no header click events, so columns could not be made sortable. The view now builds real HTML into `#stats-table-container` (the `#chart` div is hidden while it is active) and `_doRender` short-circuits the whole trace/layout path when a renderer returns `_html`, including its own `hideLoadingBar()` call since it never reaches the one at the end. `stripTags()` reduces logger labels to their words and `escHtml()` escapes every cell, so a logger name containing markup or an ampersand renders as text rather than as HTML.
- **Add: click-to-sort column headers** - Every header carries a `data-sort-key`; a delegated listener on the container toggles direction on the active column and switches column otherwise, defaulting to descending for numbers and ascending for names. Sorting reorders loggers **within** their group, so each group mean stays adjacent to the loggers it averages and the overall row stays last; blanks sink to the bottom in both directions. Sort state resets when leaving the view.
- **Change: Download PNG becomes Download CSV on this view** - An HTML table cannot go through `Plotly.toImage`, and a table of numbers is more use as data than as a picture. The button relabels itself (updating `data-i18n` so the language toggle keeps working) and `downloadStatsCsv()` writes one block per metric with the dataset, period, sort order and export time in a header. Percent signs, leading `+`, the en-dash placeholder and the thousands separators in `n` are stripped so every cell parses as a number, fields containing commas are quoted, and a UTF-8 BOM is prepended so Excel renders `°C` and `Δ` correctly. The period fragment of the filename is now shared with the PNG export via a new `exportRangeStr()` helper rather than being duplicated.
- **Change: group figures average per-logger statistics rather than pooling raw samples** - `build_dataset_json()` resamples each logger to its own configured granularity (`GRANULARITY_MAP`, default 1h), so a 15-minute logger contributes four times the samples of an hourly one over the same window. Pooling would let sampling rate stand in for physical significance, so `aggregateStats()` takes means of per-logger means and medians of per-logger medians, with every logger counting once. Group min/max remain true extremes across the group, since an average of extremes is not an extreme. A group row is only emitted where the group holds more than one logger - otherwise it would restate the logger row verbatim.
- **Change: mean diurnal swing now requires a substantially complete day** - `_meanDiurnalSwing()` originally counted any EAT calendar day holding three or more readings, which biased the figure downwards: the first and last day of any selected window are almost always partial, and a part-day cannot exhibit its full swing. A synthetic 10-day hourly sine of amplitude 5 °C (true swing 10.0 °C) returned 9.29 °C under the old guard. Days must now hold at least 80 % of the samples their logger's grid step implies, which returns exactly 10.0 °C on the same input.
- **Change: the statistics view takes its variables from the Metrics checkboxes** - A dedicated "Variable" dropdown was added first and then removed: it duplicated the existing Temperature/Humidity checkboxes, which the Beta branch of `handleChartTypeChange` had simply been hiding. The Metrics section now stays visible on this view and gains a third checkbox, Difference from external, shown only here. One table is rendered per selected metric, each with its own caption, columns and group rows, so all three can be read at once. In difference mode external loggers are dropped (a logger's difference from itself is zero) and two extra columns appear: mean ΔT by day (06:00-18:00 EAT) and by night. The split matters because a space can sit below ambient by day and above it by night, and a single mean near zero hides exactly that: in testing a room averaging +2.0 °C overall resolved to −1.1 °C by day and +5.1 °C by night.
- **Change: `displaylogo: false` in `PLOTLY_CONFIG`** - Drops the "made with Plotly" mark from the modebar on every chart.
- **Change: Temperature Differential now covers structural loggers and draws group means** - `renderBetaDifferential()` skipped everything outside `roomLoggers`, so the above-ceiling and below-roof sensors - the ones with the largest differentials - were absent from the chart built to show differentials. It now plots every non-external logger and overlays a Room and a Structural group mean line (hourly buckets, so loggers on different grids share a time base) at 2.6 px against the 1.4 px per-logger traces, so group behaviour reads against the individual spread.
- **Add: column explanations on hover** - Each of the 15 column headers shows a fixed-position box giving the statistic's formal name and a plain-English account of what it tells you - median as "the middle reading, with half above and half below", P95 as "only 1 reading in 20 sits above this", and so on - with a reminder that the header is clickable. Written for both languages. The box flips above the header when it would run off the bottom of the window, clamps horizontally to stay on screen, and hides on scroll. The `title` attribute added in the first pass was removed, since the native browser tooltip would have raced it.
- **Note: `n` counts hourly points, not raw readings** - Worth recording because the figures look contradictory at a glance. The sidebar's "589,850 readings" is `len(df)` at native logging intervals, whereas the statistics table counts the resampled series. House 5's twelve Omnisense sensors log every 5 minutes (`32760048` every 3), while the fourteen TinyTags and both Open-Meteo series are already hourly. `build_dataset_json()` averages every logger to one value per hour, which leaves the TinyTags and Open-Meteo untouched (168,350 and 30,310) but collapses Omnisense from 391,190 to 34,235 - 232,895 hourly points in total. Verified to reconcile exactly: 559,540 raw sensor readings + 30,310 Open-Meteo = 589,850. Temperature and humidity report the same `n` because they share one resampled grid per logger.
- **Note: coverage is reported alongside every statistic** - Each row carries the share of the selected window that logger actually reported, derived from the modal spacing of its samples. A mean over a series that is 40 % missing is not wrong so much as unanswerable, and the figure has to travel with the statistic rather than living in a separate panel.

### 2026-08-13 23:55:36 CST
- **Add: Omnisense 32760048 (Bedroom 4, below metal roof) enabled in House 5** - The sensor's data was already being fetched and committed - it occupies its own block in `data/omnisense/omnisense_20260813_0542.csv` under the description "House 5, Metal Roof, above Bed 4" (52,162 readings, 2026-01-25 00:03 → 2026-08-08 05:16 EAT) - but was discarded at parse time because it was absent from the `OMNISENSE_T_H_SENSORS` whitelist that `load_omnisense_csv()` filters on. Added it to the whitelist and to House 5's `structural_loggers`, placed it in `sidebar_order` directly after `32760164` so the Bedroom 4 group lists its three TinyTags then its three Omnisense sensors in the same room/above-ceiling/below-roof order, and registered it in `LOGGER_NAMES` ("Bedroom 4 (below metal roof)"), `LOGGER_NAMES_SW` ("Chumba cha kulala 4 (chini ya paa la bati)") and `LOGGER_SOURCES` ("Omnisense"). Naming deliberately mirrors TinyTag `759519` at the same location, exactly as `32760164` mirrors `759489` above the ceiling; the "(Omnisense)" source suffix distinguishes the pair in the UI. It lands in the structural section automatically - `generate_loggers_json()` assigns anything that is neither external nor a room logger to `structural` - so no external/room config was touched. House 5 goes from 26 to 27 loggers; all 52,162 readings carry into `sensor_snapshot.json` with no nulls and statistics matching the raw CSV (temperature 17.9-47.9 °C, mean 26.92; humidity 37.7-94.0 %, mean 78.06). The same change was applied to the `arc_tz_line` build. Note the sensor's readings stop at 2026-08-08 05:16 EAT, ~5 days before this fetch - as do those of every other Omnisense sensor in the same CSV, so this is a gateway-side reporting gap and not a consequence of this change.
- **Note: `surface_temp` is not plotted** - This sensor reports a wider column set than the plain T&RH units (`t_delta, t_diff, surface_temp, temperature, humidity, dew_point, gpkg, battery_voltage`). No parser change was needed, because `load_omnisense_csv()` resolves `temperature` and `humidity` by column name, but that also means only the sensor's **air** temperature and humidity are charted. The metal-roof surface reading (`surface_temp`, 17-57.9 °C - peaking 10 °C above the air temperature at the same point) is still discarded. Exposing it would need a temperature-only series path, which the pipeline does not currently have: temperature is paired with humidity throughout the histogram, comfort and wet-bulb code.

### 2026-07-26 21:58:00 CST
- **Data: Schoolteacher's House TinyTag 759498 extended to 2026-06-15** - Ingested a new TinyTag TGU-4500 offload for logger `759498` (Bedroom 1) covering 2026-03-06 10:22 → 2026-06-15 11:22 EAT, 2,426 hourly readings with no gaps. The readings are entirely new: the previous coverage ended 2025-01-08 02:42, so there is zero timestamp overlap (and a 14-month hole between the two runs, which is expected - the logger was not deployed in that period). Because the source `.xlsx` files for a full build are not present outside the offload machine, the readings were merged directly into `data/sensor_snapshot.json` for the `schoolteacher` dataset using the same normalisation `save_sensor_snapshot()` applies (EAT localisation, 2dp rounding, sorted, duplicate timestamps dropped keeping the newest), taking 759498 from 5,283 to 7,709 readings. `index.html` regenerated with `build.py --auto`; Schoolteacher's House now shows 2026 in its year selector.
- **Change: Schoolteacher's House Open-Meteo bound moved to 2026-06-16** - `logger_date_filters[OPENMETEO_HISTORICAL_ID]["before"]` in the `schoolteacher` dataset raised from `2025-10-15` to `2026-06-16`. The old bound existed to stop the external trace running past the end of the house's sensor data (Govee ends 2025-10-14) and would otherwise have truncated the external reference 8 months short of the newly ingested 759498 data. No re-fetch was needed: `fetch_openmeteo.py` already requests the full history from 2023-03-15 to yesterday on every run, so the existing `historical_*.csv` covers the period. Historical Open-Meteo for the dataset now runs 2024-06-02 → 2026-06-15 (17,856 records). Note that the external trace spans the 2025-01-08 → 2026-03-06 sensor gap, so the room traces are intentionally discontinuous across it.
- **Note: railed humidity left in place** - 574 of the 2,426 new readings sit at a humidity rail (503 at 100 %RH, 70 at 0.0 %RH; the latter produce the −32.2 °C dew-point minimum in the export's Statistics sheet). Retained as-is by decision; no `anomalous_ranges` entry added.
- **Change: Schoolteacher's House TinyTag logger ID renamed `759498` → `tinytag`** - The dataset now follows the same source-named convention as its Govee logger (`govee.xlsx` → `govee`), so its two sensor files are `data/schoolteacher/tinytag.xlsx` and `data/schoolteacher/govee.xlsx`. `logger_id` is derived from the filename stem in `load_logger_excel()`, so the rename is driven entirely by the file name. Updated the `schoolteacher` dataset's `sidebar_order`, `logger_date_filters` and `logger_name_overrides` to key off `tinytag`, and added `tinytag` entries to the global `LOGGER_NAMES` ("Bedroom 1"), `LOGGER_NAMES_SW` ("Chumba cha kulala 1") and `LOGGER_SOURCES` ("TinyTag") dicts. The snapshot key was renamed in place. **House 5's `759498` is unaffected** - it remains a separate logger with its own file and its own `before: 2024-06-01` filter, still covering 2023-03-14 → 2024-05-31 (10,657 readings). Side effect: the Kiswahili name for this logger is now correct - it previously fell through to the House 5 entry and rendered as "Chumba cha kulala 3 (chini ya paa la bati)" on Schoolteacher's House.
- **Data: consolidated `data/schoolteacher/tinytag.xlsx`** - Built a single file holding the complete Schoolteacher's House record for this logger (2024-06-01 00:42 → 2026-06-15 11:22, 7,733 readings) by appending the new offload to the existing history, written in the 7-header-row layout the dataset's `skip_rows: 7` + `usecols=[1, 2, 3]` loader expects, so it is a drop-in with no code change. Verified that a full build from it reproduces the snapshot exactly: same 7,709 readings after the `from: 2024-06-02` filter, identical timestamps, values agreeing to the snapshot's 2dp rounding. Note this replaces the previous export whose header offset did not match `skip_rows: 7` and would have silently dropped its first rows.

### 2026-07-24 21:16:47 CST
- **Fix: Adaptive comfort - empty "% time in comfort zone" boxes for loggers with no data in range** - When a selected time range contained no readings for a given room logger (e.g. a year like 2026 where the TinyTag loggers have no data but the Omnisense ones do), the logger was correctly omitted from the comfort scatter but its orange percentage box was still rendered - as an empty box with a name and no value. Root cause: `updateComfortStats` in `build.py` pushed a `roomStats` entry with `pct: null` regardless of whether `filterSeries` returned any data, unlike the histogram (`updateHistogramStats`) and periodic (`updatePeriodicCompleteness`) panels, which already `continue` past loggers with no data in range. Reworked the comfort loop to mirror those two: it now runs the range/anomalous/substrat filters up front and skips the logger entirely (no box) when there is no data in range or no paired comfort points to compute a percentage from; boxes reappear automatically when a range containing the logger's data is selected. Verified live in Chrome (adaptive comfort, House 5): 2026 renders 8 Omnisense boxes and 0 empty boxes with the 6 TinyTag loggers absent, and 2024 renders the 6 TinyTag boxes again - box count equals loggers-with-data in both cases. Regenerated `index.html` via `build.py --auto`.

### 2026-07-24 20:10:48 CST
- **Change: Alert copy rewritten to a plain, formal register** - Removed all emoji from the staleness alerts and reworded them for clarity across every surface. In `check_staleness.py`: the email subject now reads "ARC Dashboard Alert: N data source(s) out of date (…)" with correct singular/plural grammar; the email body drops the ⚠️/❌/📋 icons in favour of a plain heading, a one-line summary, and an "All sources" table whose status is a text tag ("OK" / "OUT OF DATE") rather than ✅/❌; the ntfy push is now a single plain sentence plus a bulleted list (no markdown headers or emoji). In `update-dashboard-data.yml`: removed the `Tags:` header (which rendered as emoji in the ntfy app) and the now-unused `Markdown:` header, and reworded the fallback message. In `test-alerts.yml`: the test email and test push were given the same clean styling so a test matches a real alert. No logic, thresholds, or delivery channels changed - copy and presentation only.

### 2026-05-31 09:45:00 CST
- **Add: MONITORING.md** - Documents the two-layer alerting design: the external `check_staleness.py` freshness checker (daily, with per-source thresholds and email/ntfy alerts) as the total-blackout backstop, and Omnisense's native value alarms (Total Unique Sensors / Vbatt / CSS / Tcup) as push-based detection of per-sensor and connectivity degradation. Records why polling is kept daily rather than hourly.

### 2026-05-31 09:41:00 CST
- **Fix: ENSO false-positive staleness alert** - The ENSO ONI staleness threshold was 90 days, essentially equal to NOAA PSL's own normal publishing lag (the source note itself states "up to ~3 month lag"), so a perfectly normal lag tripped the alert. NOAA's latest published ONI value is March 2026 (0.110), confirmed byte-identical to the live `oni.csv` source - the fetch pipeline is healthy; the data simply had not advanced past March. The 90-day threshold first flipped ENSO to `stale` on May 30. Raised the ENSO threshold in `check_staleness.py` to 120 days (4 months) so it tolerates normal monthly lag and only fires on a genuine multi-month stall; updated the accompanying note to match.

### 2026-05-09 14:00:00 CST
- **Fix: Omnisense fetch sending wrong input date format** - Debugged via GitHub Actions workflow with `--debug` flag capturing the step-3 form response HTML. Root cause: the Omnisense server expects input dates in American M/D/YYYY format (no leading zeros), confirmed by the form's own default values (`4/9/2026`, `5/10/2026`). The script was sending `dd/mm/yyyy`; this was undetectable until May because earlier fetches had days > 12 (e.g. `16/03/2026`) which the server could only parse as day/month. Once dates like `08/05` and `09/05` appeared, the server defaulted to month-first (M/D/YYYY), placing the entire requested range in the future and returning no data. Fixed `to_mdy()` helper in `fetch_omnisense.py`. Automated fetch now downloads 289,049 rows (16.2 MB) and dashboard is current through May 8.
- **Fix: BOM 403 for IOD cycles data** - Bureau of Meteorology was blocking the explicit `ARC-EcovillageBot/1.0` User-Agent in `fetch_cycles.py`. Switched to a standard browser User-Agent; IOD data now fetches successfully alongside ENSO and MJO.
- **Add: debug-omnisense.yml workflow** - Manual-trigger GitHub Actions workflow that runs `fetch_omnisense.py --debug` and uploads the server HTML responses as artifacts, enabling diagnosis of future Omnisense fetch failures without requiring local credential access.

### 2026-05-07 15:10:00 CST
- **Root cause analysis and final fetch hardening** - Traced the full failure chain: (1) the core architectural flaw was `--auto` replacing snapshot Omnisense wholesale so any failed fetch regressed the dashboard to the last full build (March 15); (2) the May 6 empty CSV was a transient Omnisense server-side export failure; (3) the existing validation only checked for `sensor_desc` presence, not actual data columns; (4) the row-count reported by the server before download was logged but never acted on. Added early exit in `fetch_omnisense.py` when the server reports `0 rows of data`, so CI marks the step as failed before wasting a download. Combined with the `temperature`/`humidity` column check added earlier, empty exports are now caught at two independent points. Also noted: the May 1-4 data lag was a field issue (gateway connectivity), not a code issue - the data uploaded when the gateway recovered.

### 2026-05-07 14:20:00 CST
- **Fix: Recover full Omnisense history and fix auto-build merge logic** - The previous fix replaced snapshot Omnisense wholesale with the fresh 90-day CSV, discarding all historical readings older than the lookback window. `update_snapshot_omnisense` also overwrote rather than merged. Fixed both: `--auto` now keeps snapshot Omnisense records before the fresh CSV window and merges (dedup by timestamp) within it; `update_snapshot_omnisense` similarly merges rather than replaces. Recovered `omnisense_20260415_0602.csv` from git history (Jan 25 - Apr 14) and ran a two-pass rebuild merged with the May 5 CSV (Apr 6 - May 1), restoring the full Jan 25 - May 1 range for all House 5 sensors. There is a real ~8-day sensor outage gap (Mar 29 - Apr 5) for all Omnisense units; this is genuine missing data, not a processing issue.

### 2026-05-07 13:35:00 CST
- **Fix: Omnisense data gap (March 15 → May 1)** - The May 6 automated Omnisense fetch returned an empty export (sensor metadata headers only, no column headers or readings). The existing validation in `fetch_omnisense.py` only checked for `sensor_desc` in the response, which was present in the empty file, so the bad 939-byte CSV was saved and committed, and `build.py --auto` fell back to the snapshot (last full build: March 15), reverting the dashboard 7+ weeks.
  - `fetch_omnisense.py`: Added validation that the downloaded CSV contains `temperature` and `humidity` column headers; exits with error if not, preventing empty Omnisense exports from being saved and triggering the fallback.
  - `build.py`: Added `update_snapshot_omnisense()`, called in `--auto` mode whenever fresh Omnisense data is successfully parsed. Patches the snapshot's Omnisense entries in-place so a single failed fetch loses at most one day rather than reverting to the last full build.
  - Restored `omnisense_20260505_0620.csv` from git history (last valid fetch, data through May 1, 2026) and deleted the empty May 6 file.
  - Rebuilt `index.html` and patched `sensor_snapshot.json`; Omnisense data now current through May 1.

### 2026-05-06 17:18:00 CST
- **Swahili audit & fill** - Reviewed every Kiswahili entry in the `I18N.sw` dictionary against its English counterpart. Replaced still-English-in-SW values with proper Swahili: `loggers` → `Vihisi`, `roomLoggers` → `Vihisi vya Chumba`, `barMode` → `Mtindo wa Mhimili`, `range` → `Muda:`, `comfortBand` → `Bendi ya Starehe`, `densityHeatmap` → `Ramani ya Msongamano`, `lockAvg`/`unlockAvg` → `Funga Wastani` / `Fungua Wastani`, `synopticHours` → `Saa za Sinoptiki`, `adaptiveComfort` / `adaptiveComfortTitle` → `Faraja ya Kubadilika`, `stacked` → `Imerundikwa`, `overlay` → `Imefunikwa`. Tightened `runningMean` (`Wastani` → `Wastani unaoendelea`), `sensor` (`Sensor` → `Kihisi`), `proportionAxis` / `sumAxis` (use `kihisi`/`vihisi`), and `infoRunningMean` phrasing.
- **Removed dead SW keys** - `betaCrossBuild` / `betaCrossBuildTitle` had no English counterparts and weren't referenced anywhere; removed from the SW block. EN/SW key counts now match (156 each).
- **Filled translation gaps for new UI** - Added new keys (with proper Swahili) and wired them through `applyLanguage` / `data-i18n`: `wetBulbLabel` (sidebar Wet Bulb checkbox), `comfortModelDefault` / `comfortModelNone` (Comfort band dropdown), `extDataWarningPre` / `extDataWarningPost` (Open-Meteo coverage warning), `longTermNotePre` / `longTermNotePost` (long-term historic data attribution). Added substrat-filter labels (`filterBy`, `optNone`, `dayOfMonth`, `rangeToggle`, `singleToggle`), synoptic period labels (`lateNight`, `morning`, `afternoon`, `evening`), Average-Profiles group-by labels (`phase18`, `phasePNN`, `phaseENSO`), compare-mode fragments (`noLoggers`, `noFilter`), and beta data-quality legend strings (`goodData`, `gapLegend`, `adminFlagged`, `noDifference`).
- **Hard-coded English in JS replaced with `t()` calls** - Substrat / compare filter blocks (`Filter by`, `Group By`, `None`, `Day`, `Year`, `Hour`, `Synoptic Hours`, `Day of Month`, `Week`, `Month`, `Season`, `From`, `To`, `range`/`single`); synoptic labels in `substratBuildOptions` and `describeFilters`; Average Profiles `groupByOptions` (now a `groupByOptionsFor(cycle)` getter so labels follow the language); beta Data Quality legend (`Good data`, `Gap (>6h)`, `Admin flagged`); Temperature Differential reference line (`ΔT = 0 (no difference)`). `applyLanguage` now also refreshes any open substrat-filter blocks (labels and the range/single toggle) and re-emits the period group-by dropdown via `window.updateGroupByDropdown`.

### 2026-04-27 12:56:00 CST
- **Fix: Wet bulb per-logger sub-checkboxes no longer leak visible when switching chart types** - `handleChartTypeChange` resets every child of `#logger-checkboxes` to `display: ''` (to restore visibility after beta-chart filtering), which was accidentally un-hiding the `.wb-sub-label` rows that `state.wetBulbEnabled = false` should keep hidden. The same reset already clobbered periodic-avg checkboxes and lock buttons, which were already being re-applied immediately after; the wet bulb sub-labels now receive the same treatment in that block: `if (!state.wetBulbEnabled) querySelectorAll('.wb-sub-label').forEach(hide)`.

### 2026-04-27 12:32:56 CST
- **Fix: Language switch now correctly updates all sidebar section titles** - The "External / Nje", "Room / Chumba", "Structural / Muundo" section headings in the logger list and the section average labels ("External Avg" / "Wastani wa Nje" etc.) were built once at dataset-load time with a baked-in translation and never updated when the language was subsequently changed. This caused an apparently incomplete or no-op language switch: if Swahili had been active when the dataset loaded, switching back to English would leave those labels in Swahili. Fixed by stamping a `data-i18n` attribute on these dynamically-created elements so that `applyLanguage()` picks them up via its `querySelectorAll('[data-i18n]')` pass. Applies to `addSection`, `addCmpSection` (compare mode), and `addSectionAvgCheckbox` (periodic averages). The section average labels also switch from the mixed-language `"${sectionName} Average"` pattern to the proper i18n keys (`externalAvg` / `roomAvg` / `structuralAvg`).

### 2026-04-25 15:16:49 CST
- **Fix: Period-specific dropdowns now filter to data present in selected loggers** - The year/season/month/week/day dropdowns previously listed every period ever recorded in the dataset regardless of which logger checkboxes were ticked. A new `syncPeriodDropdowns()` function runs at the start of every `updatePlot()` call, computing available periods from the union of timestamps across all currently selected loggers (EAT-adjusted). If the current selection has no data for the chosen loggers the dropdown snaps to the most recent valid period. Applies to all chart types (line, histogram, adaptive comfort, periodic averages, beta charts) and to the comfort panel's room-logger set. Results are cached by logger key so the computation only re-runs when the selection actually changes.

### 2026-04-25 16:30:00 CST
- **Fix: RH > 99% readings now clamped rather than gapped in wet bulb calculation** - Several TinyTag loggers report thousands of readings above 99% RH (sensor saturation artefact; physically impossible). The previous guard returned `null` for these, creating gaps during the wettest periods. RH is now clamped to 99% before the Stull formula runs: at saturation the formula gives Tw ≈ T − 0.03°C, within the formula's own ±0.3°C accuracy and correct to the physical truth. Values below 5% RH still produce gaps. Tooltip updated to explain the clamping behaviour. Added `wetbulb_rh_clamping.md` explaining the reasoning.

### 2026-04-25 15:50:00 CST
- **Fix: Wet bulb now shows gaps for out-of-range inputs** - `stullWetBulb` now returns `null` for T outside -20 to 50°C or RH outside 5-99% (the formula's stated valid range), producing chart gaps rather than silently inaccurate values. Both call sites (line graph and periodic averages) updated to handle the nullable return. Info tooltip updated to note the valid range and gap behaviour.

### 2026-04-25 15:30:00 CST
- **Improve: Wet bulb legend no longer adds extra entries** - When both a logger and its wet bulb are shown, the wet bulb trace is hidden from the legend (`showlegend: false`) and the parent's first-metric legend entry gains a grey `+ (Wet bulb)` annotation so the legend count never grows. When only the wet bulb is shown (parent deselected) on the line graph, it keeps its own legend entry as before. Applied to both line graph and periodic averages.

### 2026-04-25 14:15:00 CST
- **Improve: Wet bulb hover now shows Temperature and Humidity source lines separately** - Instead of `From: Logger Name T & RH`, the hover now shows two explicit lines: `Temperature: Logger Name · TinyTag · ID: 780981` and `Humidity: Logger Name · TinyTag · ID: 780981`, making it unambiguous exactly which sensor's T and RH readings were used in the Stull calculation regardless of sensor type.

### 2026-04-25 14:04:02 CST
- **Improve: Wet bulb - All/None/TinyTag/Omnisense buttons now include wet bulb sub-checkboxes** - When wet bulb is enabled, clicking any section selection button also checks/unchecks the wet bulb sub-checkbox for each logger in that section, keeping the two in sync. Uses a shared `syncWb` helper in `mkSourceBtns` and inline logic in the All/None closures.
- **Improve: Wet bulb legend and chart title now read "(Wet bulb)" instead of "(Tw)"** - Both line graph and periodic average traces now use `t('wetBulbSuffix')` for the trace name, keeping it consistent with the sidebar sub-label text and localised.
- **Fix: Wet bulb-only selections no longer show "no data"** - The `renderLineGraph` main loop now uses a combined guard: proceeds if the logger is selected OR if its wet bulb trace is requested. Wet bulb traces track `dataMinMs`/`dataMaxMs` independently so the x-axis is correctly bounded even when all main logger checkboxes are off.

### 2026-04-25 13:44:43 CST
- **Feature: Wet bulb temperature overlay on line graph and average profiles** - Added a "Wet Bulb (Tw)" master toggle inside Advanced Settings. When enabled, a dashed-line sub-checkbox appears directly below each eligible logger's existing checkbox (external and room loggers only), labelled "Logger Name (Wet bulb)" with a tiny SVG dashed-line icon in the sensor's colour instead of a colour swatch. Each sub-checkbox defaults to off. Wet bulb is calculated per-sensor using the Stull (2011) approximation, accurate to ±0.3°C in tropical/sea-level conditions. Hover shows wet bulb value plus the specific T and RH series used for the calculation. Supported on line graph and average profiles only; toggle hidden automatically in Long-Term Mode and on histogram/comfort/beta chart types. Advanced Settings now also visible on the line graph. Reset to defaults unsets all selections. Both English and Kiswahili i18n keys added.

### 2026-04-06 21:00:00 CST
- **Fix: Logger checkbox selection no longer preserves stale x-axis range in "all time" mode** - When changing logger selection (individual checkboxes, All, None, TinyTag, Omnisense source buttons) while `timeMode === 'all'`, `_zoomReset` is now set to `true` before calling `updatePlot()`. Previously the zoom-preservation logic held the old x-axis range (derived from all loggers), causing Omnisense-only selections to appear as a narrow sliver against the full TinyTag date range. For specific time-period modes (month, year, etc.), the zoom is intentionally preserved so user drag-zoom within the selected period is not lost when toggling loggers.

### 2026-04-06 19:30:00 CST
- **Improve: Sidebar data freshness section** - Removed the `i` info tooltip icon from the data freshness footer. The entire text section is now a clickable hyperlink that opens the data-flow explainer page in a new tab. Changed "last updated" labels to show the actual last date the data extends to (from `omnisense_last_ms` / `openmeteo_last_ms` timestamps) instead of the fetch timestamp, so users see e.g. "31st March 2026" rather than the date the script ran.
- **Fix: Guard against empty Omnisense CSV in build** - Added early-return in `load_omnisense_csv` when the CSV has fewer than 4 lines (empty download), and a bounds check before accessing `lines[i + 2]` for column headers. Prevents the `IndexError: list index out of range` crash that occurred on April 1 when omnisense.com returned an empty file.

### 2026-03-28 01:15:00 CST
- **Fix: Mobile viewport zoom snap on page load and orientation change** - When navigating to the dashboard from another page that is zoomed (e.g. arriving from a rotated landscape page or after a password screen on the parent site), the page could load visibly over-zoomed. Added an inline script in `<head>` that briefly sets `maximum-scale=1` on the viewport meta tag on load and then removes it, forcing iOS/Android to snap back to scale 1.0 while still allowing pinch-zoom of the Plotly chart afterwards. Also added an `orientationchange` event listener that repeats this zoom reset and triggers a Plotly resize (with a 300 ms delay for iOS to settle) whenever the device is rotated. Added `-webkit-text-size-adjust: 100%` to `body` to prevent iOS from auto-inflating text size on rotation.

### 2026-03-28 00:30:00 CST
- **Improve: Mobile layout and touch usability** - Restructured the time-bar controls for mobile viewports (≤680px): left and right control groups now stack vertically so no controls are clipped or crammed on narrow screens. Removed the period title label (`#bar-title`) on mobile to recover vertical space. Increased `select` and `input[type=date]` font-size to 16px on mobile to prevent iOS browser auto-zoom when tapping form elements (overrides inline style with `!important`). Added `min-height: 32px` to selects and date inputs for adequate touch targets. Increased checkbox size to 16×16px and `.cb-label` padding/gap for easier tapping. Made sidebar width responsive (`min(300px, 88vw)`) so it fits on very narrow screens without clipping. Cleaned up the 420px breakpoint (removed redundant date-input override, improved download button padding). Desktop layout is completely unaffected.

### 2026-03-27 23:15:00 CST
- **Fix: Long-Term Mode not resetting loggers on re-entry** - The `_historicEnteredOnce` flag caused non-Open-Meteo loggers to only be unchecked the first time Long-Term Mode was activated. Removed the flag so loggers are always reset to Open-Meteo-only on every entry into Long-Term Mode.

### 2026-03-27 22:30:00 CST
- **Fix: Periodic averages y-axis inflated by threshold band** - When TinyTag data peaked around 28°C, the 32-35°C threshold shape forced the y-axis up to 35, wasting chart space. Now computes y-axis range from actual trace data when the max value is below 30°C, so the threshold band no longer inflates the axis for cooler datasets.

### 2026-03-27 17:45:00 CST
- **Fix: Season labels and details disappearing on hover** - The CSS that fades annotations on hover was targeting all `#chart .annotation` elements, causing season labels and date-range details to disappear on hover across all chart types. Scoped the CSS to `#chart.comfort-mode .annotation` so the fade-on-hover behavior only applies to the adaptive comfort chart, where it is intended.

### 2026-03-27 14:15:00 CST
- **UI: Added explainer page links** - Added three info links to external explainer pages on the main site:
  1. Header info icon (left of language toggle) linking to `/explainers/arc-tz-temp-humid` (dashboard overview).
  2. Sidebar data freshness section info icon linking to `/explainers/data-flow` (how data is collected).
  3. Running mean tooltip now includes a "Read more" link to `/explainers/running-mean` (both English and Kiswahili).

### 2026-03-27 12:36:02 CST
- **UI: Week dropdown format changed** - Week labels in dropdowns now show `W/s dd/mm/yy` (e.g. "W/s 13/03/23") instead of `Week X, yyyy`. Updated both the Python data generation and the JS complete-period search labels.

### 2026-03-22 16:05:00 CST
- **Fix: Humidity option hidden on all beta charts** - previously Temperature Differential showed a humidity checkbox; now all beta charts hide it since they're temperature-only.
- **Fix: Zoom resets on time range changes** - added `_zoomReset = true` to all time-mode, day/week/month/year/season/between change handlers and long-term mode toggle. Previously stale zoom persisted when switching to a narrower range (e.g. day view).
- **Fix: Threshold and season shapes use EAT strings** - shapes and annotations now use `toEATString()` instead of `new Date()`, fixing a 3-hour timezone offset that could cause the 32-35°C band and season lines to misalign with data on narrow views.
- **Fix: Admin-flagged hover left-aligned** - added `hoverlabel: {align: 'left'}` to purple anomalous-range traces so multi-line reason text doesn't appear right-aligned.
- **Fix: Section average checkboxes hidden after leaving beta** - added post-restore re-hide of `.periodic-avg-cb` and `.lock-btn` elements since the section restore loop was undoing their hidden state.

### 2026-03-22 15:35:00 CST
- **Fix: Compare mode cross-building traces no longer dotted** - Schoolteacher's House (and other cross-building loggers) now render as solid lines matching same-building style.
- **Fix: Structural loggers visible in Data Quality sidebar** - structural logger section now shows in sidebar when Data Quality chart is selected; other beta charts still show room loggers only.
- **Fix: Beta checkbox restoration on re-entry** - added defensive reset of all checkbox visibility before applying beta section filter, preventing stale display:none from previous visit.
- **Fix: Thermal lag y-axis padding reduced** - changed formula from `maxLag * 1.3 + 0.5` to `maxLag * 1.15 + 0.2` for tighter fit.
- **Fix: Beta dropdown bold removed** - "Beta Features" option no longer bold, just red text.
- **Remove: Suspect readings from Data Quality** - removed outlier detection (>3σ) as readings were not accurate. Legend entry and OUTLIER_WINDOW constant also removed.
- **Fix: Admin-flagged hover tooltip word-wrapped** - long reason text now wraps at ~45 characters to prevent tooltip from going off-screen.

### 2026-03-22 13:54:26 CST
- **Fix: Cross-building compare traces now use set colour** in compare mode instead of the other dataset's original colours.
- **Fix: Beta feature checkboxes now visible** - rewrote section visibility logic to use data-attribute lookup instead of fragile text matching. Only Room loggers shown; External/Structural sections hidden.
- **Fix: Beta dropdown styling** - secondary dropdown is now plain (not red/bold). Only the "Beta Features" text in the main dropdown is red+bold. Main select element itself turns red when beta is selected.
- **Fix: Decrement Factor y-axis fixed to 0-1 range**. Rewrote info tooltip with clearer worked example (outdoor high/low, indoor high/low, swing calculation).
- **Fix: Thermal Lag y-axis now scales dynamically** to the actual data range with padding, instead of a minimum of 8.
- **Data Quality: enriched suspect reading tooltips** - now show the actual reading, local mean, standard deviation, and sigma deviation (e.g. "Suspect: 38.2C, local mean: 29.1C +/-1.2, deviation: 7.6sigma").
- **Data Quality: admin-flagged anomalous periods shown as purple bands** - the known Bedroom 4 (3276012B) anomalous range appears as a distinct purple overlay with the admin-specified reason on hover. Legend entry "Admin flagged" only appears when anomalous ranges exist.

### 2026-03-22 13:43:53 CST
- **Refined Beta Features UI**: "Beta Features" is now a single red-styled option in the main chart dropdown. Selecting it reveals a secondary dropdown to the right for choosing the specific beta chart (Temperature Differential, Decrement Factor, Thermal Lag, Data Quality).
- **Removed em dashes** from all beta info tooltips (EN and SW).
- **Beta sidebar cleanup**: When a beta chart is active, only Room logger checkboxes are shown (External and Structural sections are hidden since beta charts only use room data).
- **Decrement Factor improvements**: X-axis labels and hover detail now include source type (TinyTag/Omnisense) to distinguish same-room sensors. Each sensor gets its own bar (no stacking).
- **Thermal Lag improvements**: Same source type labelling as Decrement Factor. Y-axis now uses a fixed range to prevent jumping when switching loggers.
- **Data Quality improvements**: Y-axis tick labels and hover detail now show source type in grey (e.g. "Bedroom 1 (TinyTag)").
- **Cross-building compare moved to Compare Mode**: Removed from Beta Features. In Compare Mode, each set now shows a cross-dataset section (e.g. "Schoolteacher's House" when viewing House 5) with All/None buttons. Selected cross-building loggers appear as dotted lines on the line graph.

### 2026-03-23 00:30:00 CST
- **Merged GitHub Actions into single daily workflow**: Combined `update-cycle-data.yml` into `update-dashboard-data.yml`. One workflow now fetches cycles (ENSO/IOD/MJO), Open-Meteo, and Omnisense data daily at 04:00 UTC, then rebuilds. Deleted `update-cycle-data.yml`.
- **Dashboard data action → once daily**: Changed cron from twice daily (04:00 & 16:00 UTC) to once daily (04:00 UTC).
- **Fix cycle data action 403 failure**: Added User-Agent header to `fetch_cycles.py` requests to avoid BoM 403 Forbidden errors on IOD fetch.
- **All fetch steps use continue-on-error**: Any single fetch failure won't block the rest from being committed.
- **Bump GitHub Actions to v6**: Updated `actions/checkout` v4→v6 and `actions/setup-python` v5→v6 for Node.js 24 compatibility (Node.js 20 deprecated June 2026).

### 2026-03-23 00:00:00 CST
- **Annotation fade-on-hover working**: Pure CSS approach targeting SVG `rect` and `text` children with `fill-opacity` and `!important`. 0.5s fade transition.
- **Running mean info icon positioning fixed**: Finds the actual x-axis title `<text>` element in the SVG by matching `data-unformatted` attribute against the translated axis title. Uses `position: fixed` with viewport coordinates from `getBoundingClientRect()`. 100ms delay after `plotly_afterplot` to ensure layout is finalized.

### 2026-03-22 23:15:00 CST
- **Fix annotation fade-on-hover**: Added `pointer-events: all` to SVG annotation elements so mouse events fire properly. Annotations on the adaptive comfort chart now fade to 10% opacity on hover.
- **Fix running mean info icon positioning**: Now uses Plotly's `plotly_afterplot` event instead of `requestAnimationFrame`, so the `.g-xtitle` element is guaranteed to exist. Repositions via `.then()` after resize relayout.
- **Simplify running mean tooltip**: Removed specific "7 days" reference. Now just says "exponentially weighted average of past outdoor temperatures, where recent days count most".
- **Swahili logger names in sidebar checkboxes**: Logger names in checkbox labels now wrapped in `<span class="logger-name" data-lid="...">` so they update when switching language. Applies to line/histogram, comfort, and compare mode checkboxes.

### 2026-03-22 22:30:00 CST
- **Fix running mean tooltip**: No longer says "7 days". Now explains it as an exponentially weighted average where recent days count most but influence extends well beyond 7 days, per the EN 16798-1 formula.
- **Replace minimize button with fade-on-hover**: Removed the broken annotation toggle button. The "Data ranges from..." detail text on the adaptive comfort chart now fades to near-transparent when the mouse hovers over it, letting you see the data underneath.
- **Running mean info icon positioning**: Now dynamically positioned right next to the x-axis title text using DOM measurement after each render and resize.
- **Swahili translations for all info tooltips**: All info tooltip texts (line, histogram, comfort, periodic, density, compare mode, long-term mode, comfort band, running mean) now use `t()` translation keys and update when the language is switched. Added full Swahili translations for all nine tooltip texts.

### 2026-03-22 21:45:00 CST
- **Fix comfort band tooltip**: Corrected to reference ASHRAE-55 (not EN 16798-1) as the basis for the adaptive comfort model. Added link to Vellei et al. (2017) DOI for the humidity-aware extensions. Tooltip now explains that the default model ignores humidity and can overestimate overheating by ~30%.
- **Reposition annotation toggle and running mean info icon**: Both now dynamically position themselves relative to chart elements after each render. The minimize arrow sits next to the "Data ranges from..." annotation text. The running mean `i` icon sits next to the x-axis title. Both reposition on window resize.

### 2026-03-22 21:15:00 CST
- **Separate running mean info icon on adaptive comfort chart**: Added an info `i` button near the x-axis title that explains what the running mean represents and why the comfort band shifts with outdoor temperature. Split from the comfort band tooltip, which now focuses on the green band and humidity model selection.

### 2026-03-22 21:00:00 CST
- **Rewrite all info tooltips for clarity**: Rewrote all chart and sidebar info tooltips to focus on what the user can learn from each feature, not just mechanical descriptions. Removed em/en dashes and special characters. Fixed "side by side" wording for Compare Mode (it overlays, not splits). Added practical examples like "this month vs last month" and "dry season vs wet season".

### 2026-03-22 20:45:00 CST
- **Fix annotation toggle on adaptive comfort chart**: The minimize/maximize button for the detail text overlay was never showing because it checked `state.chartType === 'adaptive'` instead of the correct value `'comfort'`. Fixed the condition so the toggle button now appears at the bottom-right of the adaptive comfort chart.

### 2026-03-22 20:35:00 CST
- **Info buttons for Compare Mode, Long-Term Mode, and EN16798 comfort band**: Added hover info `i` icons next to each control in the sidebar. Compare Mode explains overlay functionality; Long-Term Mode describes ERA5/SSP climate data; EN16798 explains the running mean calculation and Vellei et al. humidity extensions. Uses same fixed-position tooltip pattern as existing density/chart info icons.

### 2026-03-22 20:20:00 CST
- **Simplify adaptive comfort x-axis label**: Changed from "7-day running mean external temperature (°C)" to "Running mean external temperature (°C)" in both English and Kiswahili.

### 2026-03-22 20:15:00 CST
- **Remove forecast Open-Meteo from Schoolteacher's House**: Removed `OPENMETEO_FORECAST_ID` from the schoolteacher dataset's `external_sensors` and `sidebar_order` config. Added filtering in both the full build and `--auto` build paths so only the Open-Meteo logger IDs listed in a dataset's `external_sensors` are merged. House 5 still includes forecast data as before.

### 2026-03-22 17:50:00 CST
- **Fix: no graph reload when closing Advanced Settings without changes**: Closing the Advanced Settings dropdown now only triggers `updatePlot()` if filters or compare mode were actually active. Previously, closing the panel always forced a full graph reload even when nothing had changed.

### 2026-03-22 08:56:57 CST
- **Comprehensive Kiswahili translation**: Extended Swahili translations to cover nearly all user-visible English text. Now translates: dataset names (Nyumba 5, Nyumba ya Mwalimu), all room/logger names (Sebule, Chumba cha kulala, Jikoni, etc.), chart titles, axis labels (Saa ya Siku, Tarehe/Saa, Joto/Unyevunyevu), "Data ranges from/to" annotation, "Overall"/"Data completeness" stats, section sub-headers (Nje/Chumba/Muundo), avg trace names, hover tooltip labels, time period labels, and data source notes. Added `ln()` helper for logger names with `loggerNamesSw` map in data. Charts re-render on language switch via `updatePlot()`. Scientific terms (MJO, IOD, ENSO, Vellei et al.) and brand names (Open-Meteo, TinyTag, Omnisense) kept in English.

### 2026-03-22 00:48:45 CST
- **Kiswahili language option**: Added a language selector (English/Kiswahili) in the top-right of the header bar with `t()` translation system and `data-i18n` attributes. Language preference saved to localStorage.

### 2026-03-21 22:50:00 CST
- **Adaptive comfort annotation toggle button**: Added a small ▼/▲ button at the bottom-right of the adaptive comfort chart to minimise/maximise the detail overlay text (data range, comfort model, running mean sources). Prevents long annotation text from obscuring data points. Button only appears on the adaptive comfort chart when annotations are present. State persists across re-renders within the same session.

### 2026-03-21 14:12:58 CST
- **Hide empty Advanced Settings dropdown**: The "Advanced Settings" toggle is now hidden entirely when there's nothing to show inside it (no anomalous data and no substratification controls). Fixes the Schoolteacher's House line graph showing an empty dropdown.

### 2026-03-21 13:59:07 CST
- **Data freshness validation with stale-data warnings**: Build now computes last datapoint timestamps per source category (Open-Meteo, Omnisense) and last cycle index dates (ENSO, IOD, MJO), embedded as `DATA_FRESHNESS`. At runtime, the sidebar footer checks whether actual data extends to the expected date: Open-Meteo and Omnisense data should reach the day before last fetch (2-day tolerance); cycle indices checked against their natural update cadence (MJO within 3 weeks, ENSO/IOD within 3 months). Warning triangles (⚠) with hover tooltips appear next to "last updated" lines when data is stale.

### 2026-03-22 01:00:00 CST
- **Preserve user zoom across setting changes**: When the user zooms into a graph via click-and-drag, changing settings (toggling loggers, threshold, etc.) no longer resets the viewport. Zoom is captured via `plotly_relayout` events and reapplied on re-render. Zoom resets naturally on double-click, chart type switch, or dataset change.

### 2026-03-22 00:15:00 CST
- **Fix stuck gap tooltips on period switch**: When selecting a complete period from the data completeness dropdown, the gap-detail tooltip could get permanently stuck if hovering over a percentage box during the transition. Fixed by explicitly hiding gap-tip elements when the stats grids are cleared in all three sections (adaptive comfort, histogram, average profiles).

### 2026-03-21 19:30:00 CST
- **Add date range annotation to line graph and periodic averages**: The small text overlay showing "Data ranges from DD/MM/YYYY to DD/MM/YYYY" (already present on histogram and comfort charts) now also appears in the top-right corner of the line graph and periodic averages graph.

### 2026-03-17 15:45:00 CST
- **Replace 32°C threshold line with 32-35°C shaded range**: On line graph, histogram, and average profiles, the single red dotted 32°C threshold line is now a diffuse shaded band spanning 32-35°C (`rgba(231,76,60,0.12)`). Checkbox label updated to "32-35°C Threshold". Info tooltip updated accordingly.

### 2026-03-17 03:15:00 CST
- **Add Season to data completeness hierarchy**: The auto-recommend feature for adaptive comfort, histogram, and average profiles now checks Year → Season → Month → Week → Day (previously Year → Month → Week → Day). Seasons use Tanzanian seasons: Kiangazi (Jan-Feb), Masika (Mar-May), Kiangazi (Jun-Oct), Vuli (Nov-Dec). Also added Season as a time range option in the Range dropdown, with its own select populated from available data.

### 2026-03-16 19:32:24 CST
- **Add anomalous data filter**: "Exclude anomalous data" checkbox inside Advanced Settings (unchecked by default) filters out anomalous readings from Omnisense sensor 3276012B (Bedroom 4) before 12 Feb 2026. A ⚠ warning symbol next to the Bedroom 4 checkbox shows the anomaly reason on hover via fixed-position tooltip.
- **Advanced Settings on all chart types**: Visible on line graph, histogram, average profiles, and adaptive comfort. On line graph, only the anomalous checkbox is shown (substratification controls hidden via `substrat-only` class). Placed after "Histogram Settings" / "Period Settings" respectively; dynamically moved into comfort-controls for Adaptive Comfort.

### 2026-03-17 02:30:00 CST
- **Move Advanced Settings to top of sidebar**: In Histogram and Average Profiles modes, the Advanced Settings (substratification filters) now appears at the top of the sidebar instead of at the bottom, making it more discoverable.

### 2026-03-17 02:00:00 CST
- **Rename UI labels and internal variables for Average Profiles**: Renamed chart type "Periodic Averages" → "Average Profiles", sidebar label "Natural Cycles" → "Cycle", sidebar label "Granularity" → "Group By". Updated all corresponding internal variable names (`periodRange` → `periodCycle`, `periodGranularity` → `periodGroupBy`, `granularityOptions` → `groupByOptions`, etc.), HTML element IDs (`period-granularity` → `period-group-by`), and code comments throughout build.py.

### 2026-03-17 01:15:00 CST
- **Periodic average PNG export: fix legend clipping + add datalogger IDs**: Moved periodic chart to the same no-relayout SVG export path as line graphs. After injecting legend IDs and unlocking scroll, the export now measures the actual legend bottom and expands the SVG height (+ viewBox) if the legend overflows, adding 40px padding for the watermark text. Watermark is injected at the new expanded height so it always appears below the legend with a clean gap.

### 2026-03-17 00:45:00 CST
- **Histogram overlay hover: show overlapping series count**: In overlay mode, the default Plotly hover (which only shows one random series) is replaced with a custom tooltip that shows the hovered series name, its value, and how many total series overlap at that bin (e.g. "5 series at this bin (4 others)"). Stacked mode hover is unchanged.

### 2026-03-17 00:15:00 CST (3)
- **Advanced Settings on Adaptive Comfort**: Moved Advanced Settings out of `#line-controls` into a shared sidebar position (between line-controls and comfort-controls) so it appears for Adaptive Comfort charts too. Applied `applySubstratFilter` to both the scatter plot data and the comfort stats calculations. Filters now work identically on comfort as on periodic/histogram.

### 2026-03-17 00:15:00 CST (2)
- **Advanced Settings: single-select default for filters**: Substrat filters now default to a single dropdown (e.g. pick "Mar") instead of always showing From/To range selects. A small "range" link toggles to From/To mode when a range is needed, and "single" toggles back. Reduces friction for the common case of filtering to a single month, hour, or season.

### 2026-03-17 00:15:00 CST
- **Histogram bar mode toggle**: Added "Histogram Settings" section at top of sidebar (visible when Histogram chart is selected) with a "Bar Mode" dropdown to switch between Stacked (additive) and Overlay modes. Overlay mode reduces opacity for readability. Y-axis title and info tooltip update dynamically based on the selected mode.

### 2026-03-16 17:00:00 CST
- **Adaptive comfort source attribution on chart**: The Adaptive Comfort chart bottom-right annotation now shows:
  1. The comfort model (e.g. "Adaptive comfort: EN16798-1 · RH>60% (Vellei et al.)")
  2. The running mean external temperature source(s) with type and date periods when multiple sources are used (e.g. "Running mean sources: External Ambient [TinyTag] (2024-01-01 to 2024-05-06), Historical Temperature [Open-Meteo] (2024-05-07 to 2025-03-15)")
- **build.py**: `compute_exponential_running_mean` now returns source span metadata tracking which days used the primary vs fallback logger. Stored as `extSourceSpans` in each logger's series data.

### 2026-03-16 16:30:00 CST
- **Remove structural loggers from Adaptive Comfort**: Changed `build.py` to exclude structural loggers from `comfortLoggers`, so only room loggers appear in the adaptive comfort sidebar.

### 2026-03-16 16:25:00 CST
- **Faster hover on Adaptive Comfort chart**: Switched scatter traces from `scatter` to `scattergl` (WebGL-accelerated) for dramatically faster hover/tooltip response when many data points are displayed.

### 2026-03-16 16:10:00 CST
- **Orange boxes now show source/ID on hover**: Orange (has-gap) completeness boxes in the sidebar now swap to show the monitor type and ID on hover, matching the behaviour of non-orange boxes. The gap detail tooltip still appears alongside.

### 2026-03-16 16:00:00 CST
- **Fix sticky gap tooltip on period switch**: Gap detail tooltips (on orange completeness boxes) now hide immediately when the stats grid is rebuilt - previously they could remain stuck on screen after switching to a complete period because destroying the DOM element removed the `mouseleave` listener before it could fire. Fixed in all three stat box functions (adaptive comfort, histogram, periodic averages).

### 2026-03-13 12:10:50 CST
- **Reset to default respects Long-Term Mode**: When historic mode is on, "Reset to default" now resets to the default historic mode settings (Open-Meteo loggers only, temperature only, threshold/seasons off, all historic series checked) instead of turning historic mode off.
- **Logo files moved to `logo/` folder**: Header uses `logo/logotrim.png`, PNG export watermark uses `logo/logo.png`.

### 2026-03-11 17:00:00 CST
- **"No data available" message on all chart types**: Previously only periodic averages showed this. Now line, histogram, and adaptive comfort all display "No data available in the selected range" when no actual data traces are present (e.g. all loggers unchecked, or only threshold/decoration traces showing). Each render function sets a `_noData` flag; `_doRender` intercepts it and replaces the chart with a centred annotation.

### 2026-03-11 16:49:49 CST
- **Header title font size**: Increased from 14px to 18px.
- **Advanced Settings toggle fix**: Replaced CSS class-based display toggling with `dataset.open` + `style.display` to prevent conflicts with chart-type switcher. Now defaults closed and opens/closes correctly in both Periodic Averages and Histogram modes.
- **TinyTag External Ambient (861011) truncation**: Data filtered to before 12:00 EAT on 7 May 2024 in both House 5 and Schoolteacher's House datasets (erroneous data beyond that point).

### 2026-03-11 16:42:29 CST
- **Substratification (Advanced Filtering)**: New "Advanced Settings" collapsible section in the sidebar with multi-filter data subsetting.
  - Users can create multiple independent filters combined with AND/OR logic.
  - Each filter follows a hierarchical selection: Cycle (Day/Year/MJO/IOD/ENSO) → Granularity → Subset.
  - **Day cycle**: Filter by Hour (0-23) or Synoptic Hours, with cyclic wrap-around.
  - **Year cycle**: Filter by Day of Month (1-31), Week (1-53), Month (Jan-Dec, cyclic), or Season (Tanzanian seasons, cyclic).
  - **Oscillation cycles** (MJO/IOD/ENSO): Multi-select phase checkboxes (vertical layout).
  - Filters apply as pre-filters to Histogram and Periodic Averages charts only.
  - Only visible when chart type is Periodic Averages or Histogram; hidden and cleared for Line/Comfort.
  - Invalid ranges (Day of Month/Week where From > To) shown with red border and treated as inactive.
  - "No data matches the selected filter" overlay shown when filters produce empty results.
  - Collapsing the section clears all filters automatically.
  - Placed above Logger checkboxes in sidebar.
- **Reset to default now fully resets all settings**: Threshold, season lines, historic mode, periodic settings (natural cycle, granularity), section averages (all on, all unlocked), and substratification filters.

### 2026-03-09 21:46:00 CST
- **Live cycle data for periodic averages**: Replaced hardcoded placeholder ENSO/IOD/MJO phase tables with auto-generated data parsed from real source files in `data/cycles/`.
  - ENSO: Parsed from NOAA ONI CSV (913 months, 1950-present). Thresholds: ONI ≤ -0.5 → La Niña, ≥ 0.5 → El Niño.
  - IOD: Parsed from BoM DMI weekly data (213 months, 2008-present). Weekly values averaged per month; DMI ≤ -0.4 → Negative, ≥ 0.4 → Positive.
  - MJO: Parsed from NOAA ROMI daily data (1836 weeks, 1991-present). ROMI RMM1/RMM2 converted to Wheeler-Hendon phases via angle mapping; amplitude < 1.0 → weak. Daily phases aggregated to ISO weeks by majority vote.
- **`fetch_cycles.py`**: New script to download latest ENSO/IOD/MJO data files from NOAA and BoM.
- **Weekly GitHub Action**: `update-cycle-data.yml` runs every Monday at 06:30 UTC, fetches cycle data, rebuilds dashboard.
- **Sidebar note**: Added "Cycles (ENSO/IOD/MJO) last updated" timestamp to the data freshness notes at the bottom of all sidebars.

### 2026-03-09 23:00:00 CST
- **Periodic data completeness panel**: Full data completeness section for periodic averages, matching histogram/comfort functionality. Includes gap warning message, "Jump to a complete period" dropdown with source-specific groups, and hover tooltips on orange boxes showing gap dates/durations. Dropdown navigation updates time mode and checkboxes (same as histogram/comfort). Panel auto-hides when no gaps or not in periodic mode.
- **Lock indicator**: Replaced "(locked)" text with small grey SVG lock icon next to average label.

### 2026-03-09 22:30:00 CST
- **Lock button fixes**: Button now changes text to "Unlock Avg" when locked (was staying as "Lock Avg"). Replaced tacky emoji lock indicator with small grey SVG lock icon next to average label.
- **Section averages independent of checkboxes**: Section averages now always computed from ALL loggers in the section (unlocked) or the locked set (locked), regardless of which individual logger checkboxes are checked. Average lines show even when all individual loggers are unchecked.
- **Removed `hasAnyData` gate on section averages**: Section avg traces render independently, and set `hasAnyData = true` so the chart doesn't return empty when only averages are visible.

### 2026-03-09 22:00:00 CST
- **Fixed lock buttons not appearing**: Lock buttons (and section average checkboxes) were created with `display: none` and only toggled visible by the chart type change handler. If `loadDataset()` rebuilt checkboxes while already in periodic mode, the new buttons stayed hidden. Added visibility sync at end of `loadDataset()`.

### 2026-03-09 21:30:00 CST
- **Season lines on season granularity**: Season boundary lines now show on all year sub-granularities including the season view itself (month-scale positions on linear axis).
- **Removed 32°C threshold from periodic**: Threshold checkbox hidden when periodic is active; restored for line/histogram.
- **Fixed January black line**: Added `zeroline: false` to season linear x-axis.
- **Lock Average feature**: Each logger section (External/Room/Structural) now has a lock button (🔓/🔒) next to All/None, visible only in periodic mode. When locked, the section average freezes to the loggers that were selected at lock time - subsequent checkbox changes won't affect it. A 🔒 indicator appears next to the average checkbox label. Unlock returns to normal live-tracking behavior. Locked sections pre-compute their averages from the locked set before the main loop.
- **Section avg follows All/None**: All button also checks the section average checkbox; None unchecks it.
- **Section avg line style**: Higher color:white ratio (`12px 4px` dash pattern, width 3.5).
- **MJO/IOD/ENSO climate data note**: The embedded phase lookup tables are approximate. Real data from NOAA ONI, BoM RMM, and JAMSTEC DMI would significantly improve accuracy.

### 2026-03-09 20:00:00 CST
- **Periodic Averages refinements**:
  - Removed season background shading - season spacing on linear axis is now clean without colored bands.
  - Removed 32°C threshold line from periodic averages entirely; threshold checkbox hidden in periodic mode.
  - Fixed black vertical line on January in season view (`zeroline: false` on linear x-axis).
  - Year granularity options reordered: Day, Week, Month (default), Season. Month is auto-selected when switching to Year.
  - Section average checkboxes now follow All/None button rules - clicking "All" checks the average, "None" unchecks it.
  - Section average lines use higher color:white dash ratio (`12px 4px` pattern, width 3.5) for better visibility.
  - **MJO/IOD/ENSO display overhauled**: switched from bars/lines to scatter markers only (circles for loggers, diamonds for section averages). Cleaner with many loggers on 3-8 phase categories. MJO labels simplified to "Phase 1"-"Phase 8".
  - Options section (Season Lines) only shown in periodic mode when Year period range is selected.

### 2026-03-09 18:30:00 CST
- **Periodic Averages UI and display improvements**:
  - Granularity dropdown now appears above Period Range dropdown.
  - Added **Day** granularity for Year period range (366 categories, "Jan 1"-"Dec 31").
  - **Season granularity** now uses a linear x-axis with month ticks - seasons positioned at their temporal midpoints (Kiangazi Jan-Feb at 0.5, Masika Mar-May at 3, Kiangazi Jun-Oct at 7, Vuli Nov-Dec at 10.5) instead of evenly spaced. Background shading shows each season's extent.
  - **IOD and ENSO** phases now display as **grouped bars** instead of lines, which better suits 3-category phase data.
  - All traces now use `text` arrays for accurate hover labels (critical for linear-axis modes where `%{x}` shows a number).
  - Season boundary lines now also appear for Day and Week granularities (not just Month).

### 2026-03-09 17:00:00 CST
- **Periodic Averages: Period Range + Granularity redesign**:
  - Replaced single "Period Type" dropdown with two dropdowns: "Period Range" and "Granularity".
  - **Day** period range: Hour (default, 24 categories) or Synoptic Hours (Late Night 00-06, Morning 06-12, Afternoon 12-18, Evening 18-00).
  - **Year** period range: Month (12 categories), Week (53 categories), or Season (4 Tanzanian seasons: Kiangazi Jan-Feb, Masika Mar-May, Kiangazi Jun-Oct, Vuli Nov-Dec).
  - **MJO** (Madden-Julian Oscillation): 8 phases. Uses embedded weekly RMM phase lookup table (2023-W11 through 2026-W10). Weak/inactive MJO weeks are excluded.
  - **IOD** (Indian Ocean Dipole): 3 phases (Negative, Neutral, Positive). Uses embedded monthly DMI phase lookup (2023-01 through 2026-06).
  - **ENSO**: 3 phases (La Niña, Neutral, El Niño). Uses embedded monthly ONI phase lookup (2023-01 through 2026-06).
  - 32°C threshold line now shown in periodic mode (horizontal dashed red line across all categories).
  - Season lines checkbox visible when Year period range is selected. Season boundary lines drawn at correct month positions on year/month charts.
  - Options section (32°C Threshold, Season Lines) now visible in periodic mode instead of hidden.

### 2026-03-09 15:30:00 CST
- **Periodic Averages refinements (v2)**:
  - Period Settings now at the very top of the sidebar (before Loggers section).
  - Section averages (External, Room, Structural) are now individual checkboxes in their respective logger sections, visible only in periodic mode. Each controls its own dashed average line.
  - Removed Custom period type entirely (along with `buildCustomCategories`, `roundToMonday`, all custom range state/inputs).
  - Fixed legend scrollbar reappearing after PNG export - `doRestore()` now chains `unlockLegendScroll(chartEl)` after the Plotly relayout promise resolves.
  - Only Hour of Day and Month of Year period types remain.

### 2026-03-08 22:45:00 CST
- **Periodic Averages refinements**:
  - Removed "Day of Week" and "Day of Month" period type options.
  - Added info tooltip text for the periodic chart type.
  - Fixed periodic-options visibility toggling (style.display instead of classList.toggle).

### 2026-03-08 21:51:17 CST
- **New chart type: Periodic Averages** - Added a fourth chart type "Periodic Averages" accessible from the chart-type dropdown. Shows average values per periodic category (hour of day, month of year, or custom ranges). Key features:
  - **Period Type selector** in sidebar with 3 options: Hour of Day (default), Month of Year, and Custom.
  - **Custom period type** expands to show Granularity (Day/Week/Month) and range pickers. Day uses date pickers, Week uses date pickers with Monday-rounding, Month uses `<input type="month">`.
  - **Section average lines** (dashed) for External, Room, and Structural groups. Controlled by "Overall Average" checkbox (default: on).
  - **Data quality warnings** in sidebar when >50% of a series' categories are based on single data points. Orange at >80%, red at 100%.
  - **EAT timezone handling** - all timestamp bucketing uses `eatDate(ms)` helper (UTC+3 shift) matching the existing `toEATString()` convention.
  - Uses Plotly `type:'category'` x-axis for clean categorical display. Shares logger checkboxes and metric toggles with line/histogram graphs. Hides threshold/seasons/historic options when active.
  - PNG export uses the relayout+capture path (same as histogram/comfort). Filename includes period type (e.g. `PeriodicAvg_HourOfDay`).
  - Changes in `build.py` HTML_TEMPLATE: new CSS (`.periodic-warning`), sidebar HTML (`#periodic-options`), state vars (`periodType`, `showOverallAvg`, custom range vars), event listeners, `renderPeriodicAverages()`, `buildCustomCategories()`, `updatePeriodicWarnings()`, `emptyPeriodicResult()`, `eatDate()`, `roundToMonday()` helper functions.

### 2026-03-08 18:30:00 CST
- **Fixed x-axis ticks exceeding date range** - Line graph x-axis ticks no longer go beyond the selected date range (e.g. "Jan 2027" no longer appears when 2026 is selected). Root cause: Plotly's `nticks` auto-generates "nice" monthly tick positions in UTC space, and because the EAT-shifted range for year 2026 ends at "2027-01-01 02:59:59", Plotly included a Jan 2027 tick. Fix: replaced `nticks:20` with a new `makeXTicks(startMs, endMs)` helper that generates explicit `tickvals`/`ticktext` placed at noon EAT (09:00 UTC) on each tick boundary - guaranteeing all ticks fall strictly within `endMs`. Tick granularity adapts to range: yearly (>730d), monthly (>50d), daily with variable step (>1.5d), or hourly (≤1.5d).

### 2026-03-08 17:30:00 CST
- **PNG export: ID codes in legend** - On PNG download for all chart types (Line, Histogram, Adaptive Comfort), each legend item now shows the sensor ID code in grey text (e.g. "Living Room · 780981"). Implemented via a new `injectLegendIDCodes(doc)` function in `build.py` that post-processes the exported SVG DOM: wraps the existing text content in a `<tspan>`, then appends a second grey `<tspan fill="#aaaaaa">` with ` · <id>` to each `.legendtext` element whose trace has a real sensor ID (Open-Meteo, govee, and `climate-*` series are skipped). Called in all three export paths after `Plotly.toImage()`. The live chart is unaffected. Run `python build.py` to apply.

### 2026-03-09 00:00:00 CST
- **Fixed x-axis range snapping on line graph** - When a specific time range (day/week/month/year/between) is selected, the x-axis now always spans the full selected period even if data doesn't cover it. Only the "All time" mode continues to snap to the actual data bounds. Change is in `build.py` (JS template, `renderLineGraph()`): x-axis `range` now uses `[start, end]` from `getTimeRange()` for non-"all" modes, and `[dataMinMs, dataMaxMs]` only for "all" mode.

### 2026-03-08 23:30:00 CST
- **Code cleanup & refactoring** - Major deduplication pass across the codebase:
  - **`tsRange()` shared helper** - Extracted binary search logic into a single reusable function; `filterSeries`, `detectSeriesGaps`, and `hasGapsInRange` all now use it.
  - **`addCheckbox()` / `addSection()` / `mkSourceBtns()`** - Merged the separate `addLoggerCheckbox`/`addComfortCheckbox` and `addLoggerSection`/`addComfortSection` pairs into generic builders used by all views.
  - **`buildGapDropdown()` / `renderStatsBoxes()`** - Extracted shared dropdown-building and room-box-rendering logic from both `updateHistogramStats` and `updateComfortStats`, eliminating ~70 lines of duplicated code.
  - **`dsLabel()`** - Short helper replacing verbose `document.getElementById('dataset-select').options[...].text` calls.
  - **Removed dead code** - `toggleAllCheckboxes` (unused function), `NON_ROOM_SENSORS` (unused Python set), `order_map_rl` (duplicate of `order_map`).
  - **Watermark cleanup** - Removed unused `atTop` parameter and `logoTopPad`/`txtBaseline` constants from `injectSVGWatermark`.

### 2026-03-08 14:45:00 CST
- **Comfort stats default green** - Changed `#comfort-stats` default from blue (`#f0f7ff`) to green (`#eef6ee`) to match histogram.
- **"Reset to default"** - Changed button text from "Reset defaults" to "Reset to default" across all views.
- **Source-group fallback uses all available loggers** - `findCompletePeriods` now accepts an `allAvailableInfo` parameter. When the primary all-complete search fails, the source-group fallback searches across ALL available loggers in the dataset (not just the currently selected ones). E.g. if only TinyTag is selected and has gaps, it will still offer complete Omnisense periods as alternatives (and vice versa). Removed the `srcKeys.length > 1` restriction so single-source-type selections also get fallback suggestions.

### 2026-03-08 13:30:00 CST
- **Dropdown navigation updates checkboxes** - When selecting a source-group-specific period (e.g. "Complete for TinyTag loggers") from the gap dropdown, the sidebar checkboxes now update to only select loggers of that source type. Works for both histogram (`state.selectedLoggers` + `#logger-checkboxes`) and comfort (`state.selectedRoomLoggers` + `#room-logger-checkboxes`). External loggers left unchanged in histogram view.
- **Histogram stats styling fixes** - Box default color changed from blue to green (`#eef6ee`); turns orange on gaps via `.has-gaps` CSS. Moved panel above Open-Meteo reference note. Overall text now includes "temperature" ("X% of temperature readings below 32°C").

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
- **Gap tooltip: add percentage** - The "X days missing total" line now shows `(Y%)` of the selected range.
- **Source-group dropdown fallback** - When no periods are complete for ALL enabled loggers (common when TinyTag + Omnisense are both on, since they cover different date ranges), the dropdown now falls back to per-source-type results. Shows separate `<optgroup>` sections like "Complete for TinyTag loggers (8)" and "Complete for Omnisense loggers (6)", each with their own primary and secondary suggestions. Refactored `findCompletePeriods` into `_searchCompletePeriods` (primary search) and `_searchSecondary` (same-granularity search) to enable reuse across the all-complete path and each source group.

### 2026-03-08 11:01:12 CST
- **Adaptive data completeness indicator**: Added gap detection (≥24h) to the comfort stats percentage boxes in the Adaptive Comfort view.
  - Individual `.room-item` boxes turn dark orange (`#f5d4a0`) when the series has gaps in the selected time range.
  - Container `#comfort-stats` turns light orange (`#fff5e6`) when any series has gaps.
  - Summary message shows count of series with gaps (e.g. "3 of 8 series have gaps of 24h+").
  - Hover tooltip on orange boxes lists up to 5 largest gaps sorted by size (start-end dates, days), with "and X more…" overflow and a visually separated total missing days line.
  - Dropdown suggests alternative gap-free periods: primary section (coarsest complete granularity within range: year > month > week > day), secondary section (same granularity as user's selection, outside range). Clicking a period navigates the view.
  - Series with no data in the selected range show "-" instead of a percentage and are flagged as having gaps.
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
- `config.html`: section dropdown (Room/Structural, hasCat datasets only) + three checkbox columns (Line, Histogram, Adaptive Comfort). External loggers show "-" in all editable columns.

### 2026-03-07 16:47:03 CST
- **Config admin UI**: Added `config.html` - a GitHub Pages admin page for editing logger display names and categories without rebuilding.
- `build.py` changes:
  - `build_dataset_json`: Added `ext_sensor_set` derived from `cfg["external_sensors"]`. Changed extTemp computation from `if logger_id in comfort_logger_set` to `if logger_id not in ext_sensor_set`, so all non-external loggers get extTemp precomputed (enables any logger to be moved to adaptive comfort via config).
  - Added `generate_loggers_manifest(all_data)`: builds a manifest of all loggers with their default names, sources, and categories (room/structural/other/external).
  - `main()`: writes `data/loggers.json` after each build (full or `--auto`).
- `index.html` template changes:
  - `init()` made `async`. Calls `await loadUserConfig()` then `applyUserConfig(config)` before `loadDataset()`.
  - `loadUserConfig()`: fetches `data/config.json` at runtime (no-cache). Returns null on any error (graceful degradation).
  - `applyUserConfig(config)`: patches `ALL_DATA` meta in-place - overrides `loggerNames`, and rebuilds `roomLoggers`/`structuralLoggers`/`comfortLoggers` from category overrides.
- `config.html` (new): standalone admin page. Reads `data/loggers.json` for defaults, reads/writes `data/config.json` via GitHub Contents API (PUT). Requires GitHub PAT with Contents: Read & Write. Shows logger tables per dataset with editable name inputs and category dropdowns (Room/Structural/Other). Save/Reset buttons commit to GitHub. Changes reflected on dashboard immediately on next page load.
- `data/config.json` (new): initial empty `{}` - tracked in git.
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
  - `External Historical (Open-Meteo)` - recorded data from 2023-03-15 to yesterday; used for adaptive comfort running mean.
  - `External Forecast (Open-Meteo)` - predicted data for next 16 days; shown as dashed line on line graph/histogram only; excluded from adaptive comfort.
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
  - **Adaptive Comfort**: explains EN16798-1 running mean, green comfort zone, humidity model selection.
- Uses same fixed-position JS tooltip pattern as the density heatmap info icon (Georgia serif, z-index 9999, viewport-clamped). Tooltip opens below the icon. Width 280px.
- Rebuilt index.html.

### 2026-03-02 00:25:16 CST
- Restored Georgia serif font on density heatmap info tooltip (`#info-fixed-tip`). Was lost when switching from CSS `::after` (which inherited from `.info-i`) to JS-generated div. Rebuilt index.html.

### 2026-03-01 18:21:02 CST
- Overhauled state management for chart-type switching and long-term mode:
  - **Chart switching preserves selections**: switching between Line, Histogram, and Adaptive Comfort no longer resets logger checkboxes, threshold, or other settings. Whatever you have selected carries over. Removed the non-historic histogram "all loggers selected + threshold forced on" reset.
  - **Long-term mode persists across chart switches**: entering Adaptive Comfort while Long-Term Mode is active suspends it (not available on adaptive comfort), but returning to Line or Histogram automatically re-applies long-term mode effects (humidity hidden, options hidden on line, series checkboxes rebuilt/shown).
  - **First-entry-only logger reset**: entering Long-Term Mode for the first time in a session forces loggers to Open-Meteo only (sensible default). Subsequent toggles of Long-Term Mode keep whatever loggers are currently selected - the user's manual selections are preserved.
  - Exiting Long-Term Mode still restores the pre-entry state snapshot (loggers, metrics, time mode, threshold, seasons).
- Rebuilt index.html.

### 2026-03-01 18:14:09 CST
- Density heatmap info icon tooltip: replaced CSS `::after` pseudo-element approach with a JS fixed-position tooltip (`#info-fixed-tip`, `position:fixed`, `z-index:9999`). The old approach was clipped by `overflow:hidden` on `#main`; the fixed approach escapes all overflow constraints and positions to the right of the icon, clamping to viewport width.
- Sidebar logger ordering: updated House 5 `sidebar_order` to interleave TinyTag and Omnisense loggers by room (Living Room → Kitchen → Study → Bedroom 1-4 → Washrooms) instead of all-TinyTag-first then all-Omnisense. Applies to all checkbox lists (line graph, histogram, adaptive comfort) since they all derive order from `sidebar_order`.
- Rebuilt index.html.

### 2026-03-01 18:07:53 CST
- Density heatmap: restored full fill opacities (reverted the halving from 18:01). Changed from `coloring:'heatmap'` back to `coloring:'fill'` (discrete bands) with `showlines:true` and `line:{color:'rgba(80,80,80,0.3)', width:0.5}` - contour outline lines now drawn at ~half opacity rather than hidden.
- Info (i) tooltip: repositioned to open rightward-from-right (`right:-4px; left:auto`) so it stays within the sidebar instead of overflowing the right edge.
- Loading progress bar: now shown on every `updatePlot()` call, not just chart-type/dataset switches. Fast updates (checkbox toggles etc.) use a 350ms estimated duration; slow switches keep their existing estimates (1500ms comfort, 800ms line).
- Rebuilt index.html.

### 2026-03-01 18:01:16 CST
- Density heatmap: reverted from blue back to grey/black colorscale; all opacity values halved (~0→0, 0.1→0.05, 0.18→0.09, 0.25→0.13, 0.33→0.17, 0.4→0.2).
- Info (i) tooltip: box widened to 230px, font-size 12px, padding 6×9px, line-height 1.5 for better readability.
- Download filename: stripped "(Vellei et al.)" from adaptive comfort model label - filename now shows just the RH% portion (e.g. `RH60`).
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
- Download filenames now encode sensor selection: if 1-2 loggers are selected their slugified display names are included; if a partial subset (3+), the count is included (e.g. `_5of24sensors`); if all are selected nothing extra is added (keeps the common case clean).
- Rebuilt index.html.

### 2026-03-01 17:33:07 CST
- Fixed line graph x-axis timezone display: timestamps were showing in browser local time (UTC+8) instead of EAT.
  - Root cause: x values were passed as UTC epoch ms (`new Date(timestamps[i])`); Plotly converts these using the viewer's browser timezone, shifting times by UTC+8 offset for users in China/Taiwan.
  - Fix 1 (Python): reverted Weather Station cutoff back to `pd.Timestamp("2026-02-17 12:00:00")` (naive EAT, correct). Previous `09:00:00` was wrong - Omnisense CSV timestamps are EAT, not UTC.
  - Fix 2 (JS): added `toEATString(ms)` helper that converts UTC epoch to EAT local time string (`new Date(ms + 3h).toISOString().slice(0,19)`). Plotly treats bare date strings as calendar-absolute (no timezone conversion), so viewers in any timezone always see EAT.
  - Applied: `buildGapArrays` now pushes `toEATString(timestamps[i])` for x values; `renderLineGraph` xaxis range uses `toEATString(dataMinMs/dataMaxMs)` and `type:'date'`.
- Rebuilt index.html.

### 2026-03-01 17:19:53 CST
- Fixed weather station cutoff timezone: Omnisense CSV timestamps are UTC, so midday EAT (12:00 UTC+3) = 09:00 UTC. Cutoff corrected from `2026-02-17 12:00:00` to `2026-02-17 09:00:00` (naive UTC). Previous cutoff was removing data from 09:00-12:00 UTC (12:00-15:00 EAT), causing the graph to start from the next available reading at 14:00 UTC = 17:00 EAT (5pm).
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
- Fixed adaptive comfort checkbox sections: now splits into Structural (unchecked by default) and Room (checked by default), matching the line graph/histogram sidebar - not TinyTag/OmniSense as incorrectly done in previous commit.
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
- Line graph PNG download now skips `Plotly.relayout` entirely - title is injected directly into the SVG string after capture, so the on-screen chart margin never changes and season labels never shift during download.
- White title halo stroke-width reduced from 10 to 5 (half as thick).
- Rebuilt index.html.

### 2026-03-01 14:37:15 CST
- Fixed three bugs in the graph title bar feature:
  1. **Season labels cut off on initial load**: added double `requestAnimationFrame` after `init()` so `Plotly.relayout({autosize:true})` fires after the flexbox layout has fully settled, correcting annotation positions on first render.
  2. **No-shift during PNG download**: unified line graph top margin between screen render and PNG export (`t:sm?35:50` for both), so `margin.t` stays constant when title is temporarily added back - season labels no longer jump.
  3. **White title halo in line graph PNG**: replaced `paint-order` SVG attribute approach (unreliable when SVG is drawn to canvas) with a clone/halo method - a white-filled, white-stroked clone of the `.g-gtitle` group is inserted before the original in `.infolayer`, giving a thick white outline behind each character. Both clone and original are moved to the end of `.infolayer` so the title renders above season-label annotations.
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
- Historic Mode toggle: when in histogram mode, toggling Historic Mode only shows/hides the climate series checkboxes - no logger reset (stays all-selected), no humidity hiding, no options hiding. When in line graph mode, full save/restore logic is unchanged. Rebuilt index.html.

### 2026-02-28 17:03:58 CST
- Histogram normalised by probability (histnorm:'probability'): bars now show fraction of each logger's readings in each bin rather than raw counts. Fixes bias where high-frequency loggers (Omnisense at 5-min) would appear 12× taller than hourly TinyTag loggers for the same temperature distribution. Y-axis title changed to "Fraction of readings" with % tick format. Hover updated to show e.g. "28°C: 12.3% of readings". Rebuilt index.html.

### 2026-02-28 16:53:27 CST
- Histogram tick stagger: only applied when x-axis range exceeds 60 units; narrower ranges use plain labels without stagger. Lower-row annotation y moved from -0.055 to -0.04 (closer to axis). Unified TICK_FONT={size:11, color:'#444'} applied to both xaxis tickfont and annotations so both rows match. Bottom margin reduced for non-stagger case (60/70px) vs stagger case (80/85px). Rebuilt index.html.

### 2026-02-28 16:49:16 CST
- Histogram: 32°C threshold checkbox now forced on when entering histogram mode (was defaulting to its current state, which could be off).
- Histogram x-axis stagger redesigned: use tickmode:'array' with even values as built-in tick labels (at their natural position just below the axis) and odd values as blank tick text + custom annotation at y=-0.055 paper coords (one row lower). Tick marks still appear at every degree. Bottom margin reduced to 80/85px (was 100/110). This prevents the previous large gaps caused by all labels being pushed to paper-coord annotations. Rebuilt index.html.

### 2026-02-28 16:42:29 CST
- Histogram: all logger checkboxes now selected by default when switching to histogram mode.
- Histogram x-axis stagger: replaced \n-prefix approach (which was producing left-right shift instead of up-down) with custom Plotly annotations. Built-in tick labels hidden (showticklabels:false); dtick:1 keeps per-degree tick marks. Custom annotations place even values at y=-0.04 and odd values at y=-0.14 (paper coordinates) - true up-down stagger, horizontal text. Bottom margin increased to 100/110px to accommodate two-row label layout.
- Historic mode climate traces: wide view (all time, or between-dates spanning >1 year) uses original lines+markers through annual data points (smooth). Narrow view (year/month/week/day, or between-dates ≤1 year) expands each point to span Jan 1-Dec 31 (visible horizontal line). Prevents blocky appearance on the multi-decade overview while keeping single-year zoom working. Rebuilt index.html.

### 2026-02-28 16:30:12 CST
- Histogram: Season Lines checkbox hidden when chart type is histogram (not applicable); restored when switching back to line graph.
- Historic mode isolation: switching to histogram no longer turns off historic mode. Instead, its UI effects (humidity hidden) are suspended - humidity is restored for histogram use. Switching back to line graph re-applies historic mode effects (hides humidity again, hides Options section). Historic mode state is fully preserved across chart-type switches. Rebuilt index.html.

### 2026-02-28 16:13:11 CST
- Historic mode: each annual climate data point now expanded to span Jan 1-Dec 31 as a horizontal line, so selecting a single year (e.g. "Year 1970") shows a visible horizontal line at the annual mean rather than an invisible 3px dot. Trace mode changed from 'lines+markers' to 'lines'.
- Season lines on line graph reverted to grey (#bbb, dot) - only 32°C threshold is red dotted.
- Line graph y-axis title now includes units: "Temperature (°C) / Humidity (%RH)" when both selected, "Temperature (°C)" or "Humidity (%RH)" when only one. Tick suffix unchanged.
- Histogram x-axis tick stagger increased from \n to \n\n\n offset for alternate labels; forced horizontal (tickangle:0). Rebuilt index.html.

### 2026-02-28 16:09:53 CST
- Histogram: fixed x-axis title to "Temperature (°C) / Humidity (%RH)" when both metrics selected. Added staggered tick labels (alternate labels offset downward with \n prefix) so all per-degree labels show without overlap. Added 32°C vertical dotted red line (same checkbox as line graph) when temperature metric is active. Line graph threshold line style changed to red dotted (#e74c3c, dash:dot) to match. Season lines changed to red dotted (#e74c3c) from grey (#bbb).
- Sidebar logger checkboxes split into three labelled sections with independent All/None buttons: External (All/None), Structural (All/None - below-metal loggers that are neither external nor room), Room (All/None + TinyTag/Omnisense if applicable). Structural section only appears when such loggers exist (House 5 only). Static All/None/TinyTag/Omnisense button row removed; replaced by dynamically injected per-section buttons. Rebuilt index.html.

### 2026-02-28 15:59:03 CST
- Added Histogram chart type to chart-type dropdown. Shows distribution of time spent in temperature/humidity ranges with 1-bin-per-degree (°C) or 1-bin-per-%RH. Reuses line graph logger checkboxes, metric toggles, and time range controls. Multiple loggers overlay translucently (barmode:'overlay', opacity:0.6). Options section (threshold/season lines) and Historic section hidden when histogram is active. Download filename includes "Histogram". Rebuilt index.html.

### 2026-02-28 15:47:46 CST
- Hover detail on line graph: Open-Meteo (like Govee) no longer shows redundant `· ID: External (Open-Meteo)` since the source is already displayed. Rebuilt index.html.

### 2026-02-28 15:46:26 CST
- Fixed capitalisation: "Dar Es Salaam" → "Dar es Salaam" in Historic Mode chart title. Rebuilt index.html.

### 2026-02-28 15:45:52 CST
- Added loading overlay with progress bar on chart area for slow operations (chart type switch and dataset switch). Bar animates over ~1.5s for adaptive comfort, ~0.8s for line graph, then snaps to 100% and fades. Detected by comparing `chartType|datasetKey` before/after - fast interactions (logger toggles, time range changes) render immediately without the overlay. Overlay is semi-transparent white so the previous chart remains visible underneath. Rebuilt index.html.

### 2026-02-28 15:41:05 CST
- Updated frequency labels in Historic Mode legend: all now end with " avg." - "(hourly avg.)" for TinyTag and Open-Meteo, "(5-min avg.)" for Omnisense, "(annual avg.)" for climate series. Rebuilt index.html.

### 2026-02-28 15:36:54 CST
- Corrected frequency labels in Historic Mode legend: TinyTag is "(hourly)" (~1 hr interval), Omnisense is "(5-min)" (~5 min interval), Open-Meteo is "(hourly)", climate series are "(yearly avg.)". Full state save/restore on Historic Mode toggle now includes time mode (year/month/week/day/between selection) and temperature metric, so exiting Historic Mode returns to exactly the time range and checkbox state that was set before entering. Rebuilt index.html.

### 2026-02-28 15:33:03 CST
- In Historic Mode, legend entries now show grey frequency suffix: sensor loggers get "(hourly)" for Open-Meteo or "(15-min)" for TinyTag/Omnisense; climate series get "(yearly)". Suffix only shown in Historic Mode. Rebuilt index.html.

### 2026-02-28 15:31:32 CST
- Historic Mode now defaults to Open-Meteo only for logger selection (all others deselected on enable, restored on disable). Six climate series (ERA5 + 5 SSPs) now have individual checkboxes shown in the sidebar when Historic Mode is on, each with colour swatch, all checked by default. Chart title changes to "Dar Es Salaam - Historic and Projected Temperatures" in Historic Mode. Logger and series checkbox state fully saved and restored on mode toggle. Rebuilt index.html.

### 2026-02-28 15:26:36 CST
- SSP projection data truncated to start from 2022 (was 2024). All 5 scenarios now cover 2022-2100. Rebuilt index.html.

### 2026-02-28 15:20:15 CST
- When Historic Mode is enabled: humidity checkbox is hidden and deselected (temperature only makes sense against climate projections); threshold and season line checkboxes already hidden. All three states (humidity, threshold, season lines) are saved before hiding and fully restored when Historic Mode is turned back off. Rebuilt index.html.

### 2026-02-28 15:18:17 CST
- Climate data files moved to `data/hist_proj/` - updated loader path. SSP projection data now truncated to start from 2024 (year after ERA5 ends at 2023), so ERA5 and projections connect cleanly without overlap. Fixed double-click on y-axis resetting to 0-100 instead of data range - intercept `plotly_doubleclick` event and call `updatePlot()` to restore computed range. When Historic Mode is checked, the Options section (32°C Threshold + Season Lines) is hidden as they are not meaningful over the historic/projection date range. Rebuilt index.html.

### 2026-02-28 15:09:33 CST
- Replaced World Bank historic data with Copernicus Climate Change Service data (ERA5 + CMIP6 SSP projections). Two old checkboxes replaced with single "Historic Mode" toggle. When active, shows 6 colour-coded traces: ERA5 Historic (dark grey, 1940-2023), SSP1-1.9 (green), SSP1-2.6 (light green), SSP2-4.5 (yellow), SSP3-7.0 (orange), SSP5-8.5 (red) - each 1850-2100, ensemble mean across all models. Year dropdown expands to 1850-2100 when historic mode is on. Source credit updated to Copernicus with hyperlink. Rebuilt index.html.

### 2026-02-28 13:41:27 CST
- Added source attribution below historic data checkboxes: "Source: World Bank Climate Knowledge Portal" with hyperlink. Rebuilt index.html.

### 2026-02-28 13:40:48 CST
- Fixed historic data: threshold line and season lines now extend across the full range when historic is active (bounds expansion moved before threshold/season code). Historic traces now filtered by the active time range (between dates, year, etc.) instead of always showing all 124 years. Year dropdown dynamically includes historic years (1901-2024) when either historic checkbox is checked, and reverts to sensor-only years when unchecked. "All time" mode expands to cover historic range when active. Rebuilt index.html.

### 2026-02-28 13:28:51 CST
- Fixed historic data not visible when toggled on - x-axis range was snapped to sensor data (2023-2026), hiding the 1901-2024 historic traces off-screen. Now expands `dataMinMs`/`dataMaxMs` and y-axis bounds to include historic data when either checkbox is active. Rebuilt index.html.

### 2026-02-28 13:26:37 CST
- Added Dar es Salaam historic temperature data (1901-2024) to line graphs. Two series: "DSM Historic Mean" (annual mean, pink) and "DSM 5-yr Smooth" (Gaussian smooth, grey). Both defaulted to OFF. Loaded from `data/Daressalaamhistoric.csv`, embedded as separate JSON blob. New "Dar es Salaam Historic" sidebar section with two checkboxes, visible only when data file exists. Line graph only - not shown on adaptive comfort. Rebuilt index.html.

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
- Reverted legend names (removed grey suffix text), reverted adaptive comfort marker size/opacity back to size:4 opacity:0.2. Added floating tooltip on legend item hover via plotly_legendhover event - shows source + ID (same style as checkbox tooltips). Disabled legend click/doubleclick (itemclick:false, itemdoubleclick:false) since checkboxes handle selection. Download button reverted to simple button defaulting to high quality (3× scale). Season labels restored to y:1.01 yanchor:bottom, top margin increased (t:55/85) to prevent clipping. Rebuilt index.html.

### 2026-02-28 12:49:48 CST
- Legend entries now show source and sensor ID as grey suffix text (e.g. "Living Room (Omnisense · 327601CD)"). Adaptive comfort legend markers increased from size 4/opacity 0.2 to size 6/opacity 0.5. Line graph legend items widened (itemwidth:40) for more visible colour lines. Season line labels moved inside the plot area (y:0.99, yanchor:'top') to prevent clipping at the top edge. Logo wrapped in hyperlink to actionresearchprojects.net (same tab). Rebuilt index.html.

### 2026-02-28 12:47:02 CST
- Download: merged quality dropdown + button into a single green select ("Download PNG" → Original quality / High quality). Original exports at 1× scale (exactly what's on screen), High exports at 3× scale (same proportions, higher pixel density). Removed Plotly's default camera/toImage mode bar button. Uses actual chart element dimensions so text and proportions stay identical at any quality. Descriptive filenames retained. Rebuilt index.html.

### 2026-02-28 12:41:20 CST
- Download button replaced with quality dropdown (Low 800×450, Medium 1600×900, High 3200×1800×3x, Original) + Download button, styled as a connected button group. Filename now encodes current settings: dataset, chart type, metrics/model, and time range - e.g. `ARC_House_5_Line_T+RH_AllTime.png` or `ARC_House_5_AdaptiveComfort_RH60Velleiet_2025-01_to_2025-06.png`. Rebuilt index.html.

### 2026-02-28 12:36:56 CST
- Adaptive comfort y-axis label updated to "Air temperature (°C)  [≈ operative temp.]". Rebuilt index.html.

### 2026-02-28 12:36:27 CST
- Adaptive comfort stat boxes: replaced clipped tooltip with in-box hover behaviour - box tints blue on hover and the percentage swaps to show source + sensor ID, reverting on mouseout. Removed data-tooltip from stat boxes. Rebuilt index.html.

### 2026-02-28 12:35:16 CST
- Adaptive comfort y-axis label updated to "Room air temperature ≈ operative temperature (°C)" to clarify the approximation. Rebuilt index.html.

### 2026-02-28 12:28:03 CST
- Replaced native `title` tooltips with CSS `data-tooltip` tooltips (instant on hover, dark box) for all checkbox labels and adaptive comfort stat boxes. Sorted room loggers on adaptive comfort panel by `sidebar_order` to match line graph ordering. Fixed stale data warning incorrectly appearing on Schoolteacher's House - now only shows for datasets using Open-Meteo as external logger. Rebuilt index.html.

### 2026-02-28 12:11:23 CST
- Hover tooltips added to all checkbox labels (line graph and adaptive comfort panels) and adaptive comfort percentage stat boxes, showing sensor source and ID (e.g. "Omnisense · 327601CB"). Govee and Open-Meteo show source only (no redundant ID). Rebuilt index.html.

### 2026-02-28 12:09:40 CST
- Added TinyTag / Omnisense source toggle buttons to the adaptive comfort Room Loggers panel (mirrors the line graph panel). Hidden for Schoolteacher's House. Rebuilt index.html.

### 2026-02-28 12:08:42 CST
- Adaptive comfort legend moved down slightly (y: -0.18 → -0.22) to avoid overlapping x-axis title. Rebuilt index.html.

### 2026-02-28 12:07:42 CST
- Title changed from comma to hyphen: "ARC Tanzania - Temperature & Humidity Graphs". Logger sidebar now ordered by area (Living Room, Kitchen, Study, Mother's Bedroom, Washrooms, Bed 1-4) with TinyTag and Omnisense versions of each room grouped together. Ordering controlled by `sidebar_order` config per dataset. Rebuilt index.html.

### 2026-02-28 12:05:12 CST
- Replaced logo placeholder div with `<img id="logo" src="logo.png">`, height 32px, natural aspect ratio. Rebuilt index.html.

### 2026-02-28 11:59:39 CST
- Fixed "External" sidebar sub-section to only contain truly outdoor loggers (Open-Meteo, External Ambient 861011, Weather Station T&RH 320E02D1). Above-ceiling and below-metal loggers (32760164, 759519, 861968) now correctly appear in the room section. Added `external_sensors` config key per dataset to explicitly control this. Restructured header: top bar now shows logo placeholder + "ARC Tanzania, Temperature & Humidity Graphs" title only; graph controls (dataset, chart type, model, download) moved into the Range/time bar, separated by a divider. Rebuilt index.html.

### 2026-02-28 11:49:48 CST
- Added TinyTag / Omnisense source toggle buttons to the line graph logger panel - visible only for House 5 (hidden for Schoolteacher's House which has no Omnisense loggers). Logger checkboxes now split into "External" sub-section (weather station, ambient, Open-Meteo) above a divider, and room loggers below. Buttons use data-logger-id attributes for reliable matching. Moved page title from the top header bar into the time/range bar. Rebuilt index.html.

### 2026-02-28 11:40:19 CST
- Removed 861968 (Living Room below metal) and 759519 (Bed 4 below metal) from room_loggers - they still appear in the line graph but no longer in adaptive comfort scatter or stats. Removed 6-item cap on comfort stats - all checked room loggers now shown. Rebuilt index.html.

### 2026-02-28 11:30:34 CST
- Govee hover popup no longer shows "ID: govee" - source line shows "Govee Smart Hygrometer" only. Rebuilt index.html.

### 2026-02-28 11:29:39 CST
- Removed hover highlight (restyle on hover/unhover) - too slow with 245k records. Kept default opacity at 0.35. Rebuilt index.html.

### 2026-02-28 11:27:21 CST
- Increased x-axis label density (nticks:20) with -30° angle to prevent overlap. Labels auto-adapt resolution to zoom level. Rebuilt index.html.

### 2026-02-28 11:26:45 CST
- Line graph: default trace opacity lowered to 0.35 so overlapping lines blend visibly. Hover highlight: hovered logger group jumps to full opacity while all others dim to 0.07, restores on unhover. Threshold and season lines unaffected. Rebuilt index.html.

### 2026-02-28 11:24:31 CST
- Anonymised the second dataset's label to "Schoolteacher's House" everywhere (dataset label, dropdown, docs). Logger 759498 display name → "Bedroom 1", govee → "Living Space". Govee source type shows "Govee Smart Hygrometer" in hover popup. Updated all MD files. Rebuilt index.html.

### 2026-02-28 11:21:04 CST
- Fixed Open-Meteo color to light cyan (#17becf), swapped with Omnisense 32760371 (Bed 3). Removed hardcoded x-axis tick format/dtick - Plotly now auto-formats labels based on zoom level (shows hours when zoomed in, days/months when zoomed out). Added "Date / Time" x-axis title. Rebuilt index.html.

### 2026-02-28 11:16:43 CST
- X-axis now snaps to the actual data range of selected loggers (not the full dataset/time-filter range). Y-axis padded to nearest 1.5 units for breathing room. Season lines and 32°C threshold adapt to the snapped range. Removed "OS:" prefix from Omnisense logger names. Moved light cyan (#17becf) color to Bed 3 (above ceiling) / 861004. Rebuilt index.html.

### 2026-02-28 11:13:27 CST
- Removed 759498 (Schoolteacher's House logger) from House 5 dataset via `exclude_loggers` - it remains in Schoolteacher's House dataset only. Open-Meteo color changed to light cyan (#17becf) with swap logic to avoid clashes. House 5 now 24 loggers. Rebuilt index.html.

### 2026-02-28 11:11:42 CST
- Fixed x-axis overshooting data range - now snaps to actual data bounds. Removed season label thinning so all four season boundaries (June Dry, Short Rains, January Dry, Long Rains) show labels. Rebuilt index.html.

### 2026-02-28 11:10:48 CST
- Removed sensor IDs from logger display names (checkboxes, legend). ID and data source (Omnisense/TinyTag) now shown in hover popup instead. Added Select All / Deselect All buttons for both logger and room logger checkbox lists. Rebuilt index.html.

### 2026-02-28 03:02:37 CST
- **Merged omnisense_t_h into this project.** Omnisense CSV sensors (10 T&H loggers) and Open-Meteo external temperature now load alongside TinyTag .xlsx loggers in the House 5 dataset. Added `load_omnisense_csv()` and `load_external_temperature()` functions. Open-Meteo replaces TinyTag 861011 as the adaptive comfort running mean source (861011 stays as a regular logger). Brought across density heatmap (`histogram2dcontour`) on adaptive comfort chart, and stale data warning banner when Open-Meteo coverage is shorter than sensor data. Title updated to "Ecovillage - Temperature & Humidity". Omnisense loggers prefixed "OS:" in legend. Schoolteacher's House dataset unchanged. Rebuilt index.html (256k House 5 records / 25 loggers).

### 2026-02-27 14:07:16 CST
- Changed default comfort model to Vellei RH>60%. Rebuilt index.html.

### 2026-02-27 13:47:22 CST
- Adaptive comfort: reduced scatter marker opacity 0.6→0.2 for density visualisation. Rebuilt index.html.

### 2026-02-27 12:45:40 CST
- Fixed JS spread operator stack overflow on large arrays in adaptive comfort graph. Replaced `Math.min(...allExtTemps)` / `Math.max(...allExtTemps)` and `push(...array)` with explicit `for...of` loops - fixes House 5 (174k records) silently failing to render adaptive comfort. Rebuilt index.html.

### 2026-02-27 (time not recorded)
- Created `build.py` and `index.html`: static HTML dashboard for House 5 and Schoolteacher's House TinyTag Excel loggers. Reads .xlsx files from data/house5/ and data/schoolteacher/, embeds both datasets as separate JSON blobs. Dataset switcher in header reloads all controls instantly client-side. EN16798-1 exponential running mean (alpha=0.8) for adaptive comfort. All features from omnisense_t_h preserved: line graph, adaptive comfort, time range filtering, logger/metric selection, season lines, 32°C threshold, comfort stats, PNG download, full responsive layout.
CLAUDE.md
### 2026-03-21 23:XX:XX CST
- Removed "Adaptive source: X" line from logger hover tooltips - not enough space in the tooltip box.
