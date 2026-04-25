# Period Dropdown Sync — Implementation Guide

This document describes exactly what was changed to make the year/season/month/week/day
period-specific dropdowns only show options that have actual data for the currently
selected logger checkboxes, on all chart types.

---

## Background / Problem

The dashboard has a two-level time selector in the sidebar:
1. **Granularity** (`time-mode` select): All / Between dates / Year / Season / Month / Week / Day
2. **Specific period** (`year-select`, `season-select`, `month-select`, `week-select`,
   `day-select`): the second dropdown that lets you pick *which* year, which month, etc.

The five specific-period dropdowns were populated once at page load (or dataset switch) from
`m.availableYears`, `m.availableMonths`, etc. — Python-generated lists that cover **all**
loggers in the dataset combined. When the user unticked loggers, the dropdowns still showed
every period ever recorded by any logger, including periods with no data for the selected
subset (e.g. "Day" could show any day in 3 years even if only one short-running logger was
ticked).

---

## What Was Done

**One self-contained JavaScript function** (`syncPeriodDropdowns`) was added to `build.py`
inside the HTML template. It is called at the very start of `updatePlot()` on every render.

No other code was changed. No Python was changed. No HTML structure was changed.

---

## Prerequisites — things that must already exist in `build.py`

Before applying this change, verify these already exist in the JS template:

| What | Where (search string) |
|---|---|
| `state.selectedLoggers` — `Set` of active logger IDs | around `state = {` initialisation |
| `state.selectedRoomLoggers` — `Set` for comfort panel | same block |
| `state.datasetKey` — string key of the active dataset | same block |
| `state.selectedYear`, `state.selectedSeason`, `state.selectedMonth`, `state.selectedWeek`, `state.selectedDay` | same block |
| `state.chartType` — `'line'`, `'histogram'`, `'comfort'`, `'periodic'`, etc. | same block |
| `dataset()` — function returning `ALL_DATA[state.datasetKey]` | search `function dataset()` |
| `ALL_DATA[key].series[loggerId].timestamps` — array of UTC ms integers | series data structure |
| `getISOWeekStr(ms)` — returns `"YYYY-WNN"` for a UTC ms timestamp (EAT-adjusted) | search `function getISOWeekStr` |
| HTML elements: `year-select`, `season-select`, `month-select`, `week-select`, `day-select` | search `id="year-select"` |
| `updatePlot(forceLoader)` function — the main render trigger | search `function updatePlot` |
| `let _lastRenderKey` — the existing render-key cache variable | just before `updatePlot` |

---

## Exact Edit to `build.py`

### Find this block (just before `function updatePlot`)

```javascript
// Tracks last rendered chart type + dataset to detect slow transitions
let _lastRenderKey = null;
let _zoomReset = false; // set true by double-click or chart switch to allow autorange
let _currentTitle = '';
let _currentLayout = {};
function updatePlot(forceLoader) {
  const renderKey = state.chartType + '|' + state.datasetKey;
  const isSlowOp = forceLoader || renderKey !== _lastRenderKey;
  if (renderKey !== _lastRenderKey) _zoomReset = true; // reset zoom on chart/dataset switch
  _lastRenderKey = renderKey;
  // Always show loading bar - slower estimate for chart/dataset switches, short for other updates
  const ms = isSlowOp ? (state.chartType === 'comfort' ? 1500 : state.chartType.startsWith('beta-') ? 1000 : 800) : 350;
  showLoadingBar(ms);
  setTimeout(_doRender, 30);
}
```

### Replace with this block

```javascript
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
```

---

## Line-by-line explanation of `syncPeriodDropdowns`

### Cache check (runs every `updatePlot` call)

```javascript
const isComfort = state.chartType === 'comfort';
const activeSet = isComfort ? state.selectedRoomLoggers : state.selectedLoggers;
const key = [...activeSet].sort().join(',') + '|' + state.datasetKey;
if (key === _lastDropdownKey) return;
_lastDropdownKey = key;
```

- Comfort chart uses `selectedRoomLoggers`; everything else uses `selectedLoggers`.
- The key is a sorted, comma-joined list of logger IDs plus the dataset key. If it hasn't
  changed since the last call (zoom, pan, metric toggle, etc.), the function returns
  immediately — no work done.

### EAT timezone and label constants

```javascript
const EAT = 3 * 3600 * 1000;   // East African Time offset in ms (UTC+3)
const TZ_SI = [0,0,1,1,1,2,2,2,2,2,3,3];   // month 0–11 → season index
```

Season indices: 0 = Kiangazi Jan–Feb, 1 = Masika Mar–May, 2 = Kiangazi Jun–Oct, 3 = Vuli Nov–Dec.

### Timestamp iteration

For every timestamp `ts` (UTC ms integer) from every active logger:

```javascript
const d = new Date(ts + EAT);          // shift to EAT so .getUTC* methods give local values
const y  = d.getUTCFullYear();
const mo = d.getUTCMonth();             // 0–11
```

**ISO week** — delegates to the existing `getISOWeekStr(ts)` helper (defined elsewhere in
the same JS, returns `"YYYY-WNN"`):

```javascript
const wkStr   = getISOWeekStr(ts);
const dashIdx = wkStr.indexOf('-W');
const wy = parseInt(wkStr.slice(0, dashIdx));   // ISO week year
const wk = parseInt(wkStr.slice(dashIdx + 2));  // ISO week number
```

**EAT midnight** — the day timestamp is the UTC epoch for 00:00:00 EAT, matching exactly
what Python's `int(d.timestamp() * 1000)` produces for `d = pandas midnight in EAT`:

```javascript
const dayMs = Math.floor((ts + EAT) / 86400000) * 86400000 - EAT;
```

### Building sorted period arrays

- `years` — sorted numeric array
- `seasons` — sorted by year then season index; each entry has `{y, season}`
- `months` — sorted by year then month (1-based); each entry has `{y, month}`
- `weeks` — sorted by ISO week year then week number; label computed from ISO week Monday
  using the same formula as `getTimeRange` (case `'week'`)
- `days` — sorted by timestamp; label is `"DD Mon YYYY"` (zero-padded day, 3-char month)

### Dropdown rebuild + selection preservation

For each dropdown the logic is:
1. Clear `innerHTML`
2. Add one `<Option>` per available period
3. If the current `state.selected*` value is still in the new list → restore it
4. Otherwise → snap to the **last** (most recent) available period and update `state`

This means if you uncheck loggers that remove the currently selected month from the list,
the month dropdown will silently move to the most recent month that does have data, and the
chart re-renders against that corrected range.

---

## After making the edit

Run the build to regenerate `index.html`:

```
python build.py --auto
```

Or for a full rebuild (when TinyTag `.xlsx` files are present):

```
python build.py
```

Then log the change in `CHANGELOG.md` with a CST timestamp.

---

## Adaptation notes for sibling dashboards

If a sibling dashboard uses **different season definitions**, update `TZ_SI` and `TZ_SN`:

```javascript
// Example: Northern Hemisphere seasons
const TZ_SI = [3,3,0,0,0,1,1,1,2,2,2,3];   // DJF=winter=3, MAM=spring=0, JJA=summer=1, SON=autumn=2
const TZ_SN = ['Spring (Mar–May)','Summer (Jun–Aug)','Autumn (Sep–Nov)','Winter (Dec–Feb)'];
```

If a sibling dashboard uses a **different timezone**, change:

```javascript
const EAT = 3 * 3600 * 1000;   // ← change this offset in ms
```

and update `TZ_SI`/`TZ_SN` if the seasons are month-defined and need shifting.

If a sibling dashboard does **not have a comfort chart** (no `state.selectedRoomLoggers`),
simplify the first two lines to:

```javascript
const activeSet = state.selectedLoggers;
const key = [...activeSet].sort().join(',') + '|' + state.datasetKey;
```

If a sibling dashboard does **not have seasons** (no `season-select` element), remove the
`ssel` block entirely.
