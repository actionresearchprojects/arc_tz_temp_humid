# Wet Bulb Temperature Overlay - Implementation Guide

Complete specification for implementing the wet bulb temperature overlay feature in a `build.py`-style Plotly dashboard. Copy this to a new chat alongside the target `build.py`.

---

## Feature Summary

- A **master toggle** ("Wet Bulb (Tw)") inside the Advanced Settings sidebar section.
- When enabled, a **per-logger sub-checkbox** appears directly below each eligible logger's existing checkbox in the Loggers panel.
- Eligible loggers: external + room loggers only (not structural, not comfort-panel-only loggers).
- Each sub-checkbox defaults to **off**.
- Wet bulb is calculated using the **Stull (2011)** approximation, with a range guard that returns `null` (gap) for T outside -20 to 50°C or RH outside 5-99%.
- Wet bulb traces shown as **dashed lines** in the **same colour** as the parent sensor.
- Supported on **line graph** and **periodic averages** chart types only; hidden in Long-Term/Historic mode and on all other chart types.
- **Legend**: when both main logger and its wet bulb are shown → grey `+ (Wet bulb)` annotation is appended to the parent's legend entry; no separate wb legend item. When only wb is shown (parent deselected) → wb gets its own legend entry.
- **All/None/TinyTag/Omnisense** section buttons also toggle wet bulb sub-checkboxes when wb is enabled.
- **Bilingual**: English + Swahili i18n keys.

---

## 1. State Object

Add to the central `state` object (wherever `wetBulbEnabled` and `wetBulbLoggers` need to live):

```javascript
wetBulbEnabled: false,
wetBulbLoggers: new Set(),
```

---

## 2. CSS

Add to the stylesheet:

```css
.wb-sub-label { padding-left: 14px; }
```

---

## 3. Sidebar HTML - Advanced Settings body

Inside the Advanced Settings collapsible body, add this block (hidden by default):

```html
<div id="wetbulb-adv-wrap" style="display:none">
  <hr class="divider">
  <label class="cb-label">
    <input type="checkbox" id="cb-wetbulb">
    Wet Bulb (Tw)
    <span class="info-i" id="wetbulb-info-icon">i</span>
  </label>
  <div class="info-tip-fixed" id="wetbulb-info-tip"></div>
</div>
```

---

## 4. i18n Keys

### English

```javascript
wetBulb:       'Wet Bulb',
wetBulbSuffix: '(Wet bulb)',
wetBulbHover:  'Wet bulb (Tw)',
infoWetBulb:   'Wet bulb temperature (Tw) is the lowest temperature achievable by evaporative cooling, a key heat stress indicator. When Tw exceeds 32°C, cooling by sweating becomes difficult; above 35°C it is dangerous for prolonged exposure. Calculated using the Stull (2011) approximation, accurate to ±0.3°C in tropical conditions. Valid range: -20 to 50°C and 5-99% RH; values outside this range are shown as gaps. Shown as a dashed line in the same colour as the parent sensor.',
```

### Swahili

```javascript
wetBulb:       'Joto la Mvua (Tw)',
wetBulbSuffix: '(Joto la mvua)',
wetBulbHover:  'Joto la mvua (Tw)',
infoWetBulb:   'Joto la mvua (Tw) ni joto la chini kabisa linaloweza kufikiwa kwa kupoa kwa uvukizi, kiashiria muhimu cha msongo wa joto. Imehesabiwa kwa kutumia mkaribisho wa Stull (2011). Masafa halali: -20 hadi 50°C na 5-99% RH; maadili nje ya masafa haya yanaonyeshwa kama mapengo. Inaonyeshwa kama mstari wa nukta katika rangi ile ile ya sensor.',
```

---

## 5. Stull (2011) Formula

Add near your other utility functions (e.g. near `isOpenMeteo`, `isForecast`):

```javascript
function stullWetBulb(T, RH) {
  if (T < -20 || T > 50 || RH < 5 || RH > 99) return null;
  return T * Math.atan(0.151977 * Math.pow(RH + 8.313659, 0.5))
    + Math.atan(T + RH)
    - Math.atan(RH - 1.676331)
    + 0.00391838 * Math.pow(RH, 1.5) * Math.atan(0.023101 * RH)
    - 4.686035;
}
```

Returns `null` for out-of-range inputs - callers must check for `null`.

---

## 6. Eligible Logger Set

At the top of `loadDataset` (or wherever you build the sidebar logger checkboxes), define which loggers get a wet bulb sub-checkbox. Exclude structural loggers:

```javascript
const wbEligibleSet = new Set([
  ...(m.externalLoggers || []),
  ...m.loggers.filter(id => (new Set(m.roomLoggers || [])).has(id))
]);
```

Adapt to match your dataset's logger categorisation. The rule is: external + room loggers only.

---

## 7. `addCheckbox` - Inject wb Sub-Label

`addCheckbox` is the function that builds each logger's `<label>` element and appends it to a container. Add the wet bulb sub-label injection **after** `container.appendChild(lbl)`:

```javascript
function addCheckbox(container, stateSet, id, extraLabel, skipWb) {
  // ... existing label build code ...
  container.appendChild(lbl);

  // Inject wet bulb sub-checkbox directly below (only in logger panel, not comfort panel)
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
```

Key notes:
- `skipWb` is a new 5th parameter - pass `true` when calling `addCheckbox` for the adaptive comfort logger panel.
- `ln(id)` is whatever your logger-name lookup function is called.
- `t('wetBulbSuffix')` is your i18n function.

---

## 8. `addSection` - Signature + All/None wb Sync

`addSection` wraps `addCheckbox` calls and adds All/None buttons. Two changes:

### 8a. Add `skipWb` parameter and forward it

```javascript
function addSection(container, stateSet, title, ids, extraBtns, extraLabelFn, sectionKey, skipWb) {
  // ... existing code ...
  ids.forEach(id => addCheckbox(container, stateSet, id, extraLabelFn ? extraLabelFn(id) : '', skipWb));
  // ↑ skipWb forwarded to addCheckbox
}
```

### 8b. All button - also check wb sub-checkboxes

Inside the All button click handler, after `stateSet.add(id)`:

```javascript
if (state.wetBulbEnabled && wbEligibleSet.has(id)) {
  state.wetBulbLoggers.add(id);
  const wbCb = container.querySelector(`input[data-wb-logger="${id}"]`);
  if (wbCb) wbCb.checked = true;
}
```

### 8c. None button - also uncheck wb sub-checkboxes

Inside the None button click handler, after `stateSet.delete(id)`:

```javascript
if (state.wetBulbEnabled && wbEligibleSet.has(id)) {
  state.wetBulbLoggers.delete(id);
  const wbCb = container.querySelector(`input[data-wb-logger="${id}"]`);
  if (wbCb) wbCb.checked = false;
}
```

---

## 9. `mkSourceBtns` - TinyTag/Omnisense wb Sync

If your dashboard has TinyTag/Omnisense source-filter buttons, add a `syncWb` helper inside `mkSourceBtns` and call it from each button's handler:

```javascript
function syncWb(id, checked) {
  if (state.wetBulbEnabled && wbEligibleSet.has(id)) {
    checked ? state.wetBulbLoggers.add(id) : state.wetBulbLoggers.delete(id);
    const wbCb = container.querySelector(`input[data-wb-logger="${id}"]`);
    if (wbCb) wbCb.checked = checked;
  }
}
// Then in TinyTag button:
mkSelBtn('TinyTag', () => {
  ids.forEach(id => {
    const is = m.loggerSources[id] === 'TinyTag';
    is ? stateSet.add(id) : stateSet.delete(id);
    container.querySelector(`input[data-logger-id="${id}"]`).checked = is;
    syncWb(id, is);  // ← add this
  });
  updatePlot();
})
// Same pattern for Omnisense button
```

---

## 10. Comfort Panel - Pass `skipWb = true`

When calling `addSection` for the adaptive comfort logger panel (not the main logger panel), pass `true` as the final argument so no wb sub-checkboxes are injected there:

```javascript
addSection(roomDiv, state.selectedRoomLoggers, t('sectionRoom'), comfortRoomIds,
  mkSourceBtns(roomDiv, state.selectedRoomLoggers, comfortRoomIds), null, null, true);
// ↑ skipWb = true
```

---

## 11. Reset `wetBulbLoggers` Before Building Sections

In `loadDataset`, reset the set **before** the `addSection` calls (not after), because `addCheckbox` runs during `addSection` and reads `state.wetBulbLoggers`:

```javascript
// Reset wet bulb logger set; sub-checkboxes are injected by addCheckbox below
state.wetBulbLoggers = new Set();
// External section
addSection(loggerDiv, state.selectedLoggers, t('sectionExternal'), m.externalLoggers, ...);
// Room section
addSection(loggerDiv, state.selectedLoggers, t('sectionRoom'), roomLoggers, ...);
// Structural section (no skipWb needed - structural not in wbEligibleSet anyway)
addSection(loggerDiv, state.selectedLoggers, t('sectionStructural'), midLoggers, ...);
```

---

## 12. Show/Hide `wetbulb-adv-wrap`

### In `loadDataset` (after dataset switch):

```javascript
const isLineChart  = state.chartType === 'line';
const isPeriodicChart = state.chartType === 'periodic';
const _wbOk = (isLineChart || isPeriodicChart) && !state.historicMode;
document.getElementById('wetbulb-adv-wrap').style.display = _wbOk ? '' : 'none';
```

### In `handleChartTypeChange` (when chart type selector changes):

```javascript
const _showWb = (isLine || isPeriodic) && !state.historicMode;
document.getElementById('wetbulb-adv-wrap').style.display = _showWb ? '' : 'none';
```

### In the historic/long-term mode toggle:

When **entering** long-term/historic mode:
```javascript
document.getElementById('wetbulb-adv-wrap').style.display = 'none';
```

When **leaving** long-term/historic mode:
```javascript
const _wbChartOk = state.chartType === 'line' || state.chartType === 'periodic';
document.getElementById('wetbulb-adv-wrap').style.display = _wbChartOk ? '' : 'none';
```

---

## 13. `cb-wetbulb` Event Listener

```javascript
document.getElementById('cb-wetbulb').addEventListener('change', e => {
  state.wetBulbEnabled = e.target.checked;
  document.querySelectorAll('.wb-sub-label').forEach(el => {
    el.style.display = e.target.checked ? '' : 'none';
  });
  updatePlot();
});
```

---

## 14. Reset Defaults

In your "reset to defaults" function, add:

```javascript
state.wetBulbEnabled = false;
state.wetBulbLoggers = new Set();
document.getElementById('cb-wetbulb').checked = false;
document.querySelectorAll('.wb-sub-label').forEach(el => { el.style.display = 'none'; });
document.querySelectorAll('input[data-wb-logger]').forEach(cb => { cb.checked = false; });
```

---

## 15. `setLanguage` - Update wb-suffix Spans

In your language-switching function (e.g. `setLanguage`), add:

```javascript
document.querySelectorAll('.wb-suffix').forEach(span => {
  span.textContent = ' ' + t('wetBulbSuffix');
});
```

---

## 16. Info Tooltip Registration

In your info-tooltip registration array/loop, add:

```javascript
{ iconId: 'wetbulb-info-icon', tipId: 'wetbulb-info-tip', key: 'infoWetBulb' },
```

---

## 17. `renderLineGraph` Changes

### 17a. Loop guard - proceed if main selected OR wb wanted

Replace the original `if (!selectedLoggers.has(loggerId)) continue;` with:

```javascript
const _mainSelected = iter.selectedLoggers.has(loggerId) && lineSet.has(loggerId);
const _wbWanted = state.wetBulbEnabled
  && state.wetBulbLoggers.has(loggerId)
  && lineSet.has(loggerId)
  && state.selectedMetrics.has('temperature');
if (!_mainSelected && !_wbWanted) continue;
```

### 17b. Compute `_wbAnnotation` (after `lgGroup` definition)

```javascript
const lgGroup = iter.setLabel ? 'compare_s' + iter.setIndex : loggerId;
const _wbAnnotation = (_wbWanted && _mainSelected)
  ? ' <span style="color:#aaa">+ ' + t('wetBulbSuffix') + '</span>'
  : '';
```

### 17c. Main trace - append annotation to first-metric name

In the metric loop inside `if (_mainSelected)`, change the trace name from:
```javascript
name: name + meteoSuffix(loggerId) + omniSuffix(source) + freqLabel,
```
to:
```javascript
name: name + meteoSuffix(loggerId) + omniSuffix(source) + freqLabel + (firstMetric ? _wbAnnotation : ''),
```

### 17d. Build the wet bulb trace

After the `if (_mainSelected)` block:

```javascript
if (_wbWanted) {
  const wbY = filtered.timestamps.map((_, i) => {
    const T = filtered.temperature[i], RH = filtered.humidity[i];
    if (T == null || RH == null) return null;
    const _wb = stullWetBulb(T, RH);
    return _wb != null ? +_wb.toFixed(2) : null;
  });
  const { x: wbX, y: wbYArr } = buildGapArrays(filtered.timestamps, wbY);
  for (const v of wbYArr) { if (v != null) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; } }

  // Ensure data bounds are set even when parent logger is deselected
  if (filtered.timestamps.length) {
    const first = filtered.timestamps[0], last = filtered.timestamps[filtered.timestamps.length - 1];
    if (first < dataMinMs) dataMinMs = first;
    if (last > dataMaxMs)  dataMaxMs = last;
  }

  const wbName = name + ' ' + t('wetBulbSuffix');
  const _dispName = ln(loggerId);
  const _srcLabel = (source ? ' · ' + source : '') + idLabel;
  // T and RH always from the same series → one source line.
  // If they ever differ, fall back to two separate lines.
  const _tSrc = _dispName + _srcLabel, _rhSrc = _dispName + _srcLabel;
  const _srcHover = _tSrc === _rhSrc
    ? `${t('source')}: ${_tSrc}`
    : `${t('tempOnly')}: ${_tSrc}<br>${t('humidOnly')}: ${_rhSrc}`;

  traces.push({
    x: wbX, y: wbYArr, type: 'scatter', mode: 'lines',
    name: wbName,
    line: { color, width: 1.4, dash: 'dash' },
    opacity: 0.35, connectgaps: false,
    // Key legend logic:
    // • if parent is also shown → share legendgroup, hide from legend (parent's click controls both)
    // • if parent is deselected → own legendgroup so it appears as its own legend entry
    legendgroup: _mainSelected ? lgGroup : lgGroup + '_wb',
    showlegend: !_mainSelected && !iter.setLabel,
    meta: { loggerId },
    hovertemplate: `${wbName}<br>%{x|%d/%m/%Y %H:%M}<br>${t('wetBulbHover')}: %{y:.1f}°C<br>${_srcHover}<extra></extra>`
  });
}
```

---

## 18. `renderPeriodicAverages` Changes

### 18a. Accumulators and `doWb` flag (inside the per-logger loop, before the data accumulation loop)

```javascript
const wbSum = new Float64Array(nCats), wbN = new Int32Array(nCats);
const doWb = state.wetBulbEnabled && state.wetBulbLoggers.has(loggerId);
```

### 18b. Accumulate wet bulb values in the data loop

Inside the `for (let i = 0; i < filtered.timestamps.length; i++)` loop:

```javascript
if (doWb && t != null && h != null) {
  const _wb = stullWetBulb(t, h);
  if (_wb != null) { wbSum[ci] += _wb; wbN[ci]++; }
}
```

(`t` and `h` are your per-point temperature and humidity values.)

### 18c. Compute `_wbAnnotation` (after `lgGroup` and `firstMetric`)

```javascript
const lgGroup = iter.setLabel ? 'compare_s' + iter.setIndex : loggerId;
let firstMetric = true;
const _wbAnnotation = doWb
  ? ' <span style="color:#aaa">+ ' + t('wetBulbSuffix') + '</span>'
  : '';
```

### 18d. Append annotation to first-metric trace name

In the metric loop, change the trace name from:
```javascript
name: logName + meteoSuffix(loggerId) + omniSuffix(source),
```
to:
```javascript
name: logName + meteoSuffix(loggerId) + omniSuffix(source) + (firstMetric ? _wbAnnotation : ''),
```

### 18e. Build the wet bulb periodic trace

After the metric loop (and any per-metric `firstMetric = false` bookkeeping):

```javascript
if (doWb && state.selectedMetrics.has('temperature') && !isClimateOsc) {
  const wbX = [], wbYArr = [], wbTxt = [];
  let wbAny = false;
  for (let ci = 0; ci < nCats; ci++) {
    wbX.push(xVal(ci));
    wbTxt.push(categoryLabels[ci]);
    if (wbN[ci] > 0) {
      wbYArr.push(+(wbSum[ci] / wbN[ci]).toFixed(2));
      wbAny = true; hasAnyData = true;
    } else {
      wbYArr.push(null);
    }
  }
  if (wbAny) {
    const wbName = namePrefix + ln(loggerId) + ' ' + t('wetBulbSuffix');
    traces.push({
      x: wbX, y: wbYArr, text: wbTxt, type: 'scatter', mode: 'lines+markers',
      name: wbName,
      // In periodic averages the parent is always present (we only iterate selectedLoggers),
      // so always share legendgroup and hide from legend - annotated on parent instead.
      legendgroup: lgGroup,
      showlegend: false,
      meta: { loggerId },
      line: { color, width: 2, dash: 'dash' },
      marker: { size: 5 },
      connectgaps: false,
      hovertemplate: wbName + '<br>%{text}<br>' + t('wetBulbHover') + ': %{y:.1f}°C<extra></extra>',
    });
  }
}
```

---

## Dependency Notes

- `buildGapArrays(timestamps, values)` - your existing gap-aware array builder. If you don't have one, use `{ x: timestamps.map(ms => toEATString(ms)), y: values }` (no gap splitting).
- `meteoSuffix(id)`, `omniSuffix(source)` - your existing suffix helpers. If your dashboard doesn't have these, just omit them from the trace name.
- `ln(id)` - your logger display-name lookup.
- `t(key)` - your i18n lookup function.
- `iter.setLabel`, `iter.setIndex` - compare-mode props. If your dashboard has no compare mode, use `loggerId` directly as `lgGroup` and `false` for `iter.setLabel`.
- `isClimateOsc` - flag for climate oscillation loggers (Long-Term mode). If not applicable, just treat it as `false`.
- `namePrefix` - prefix string for trace names (usually empty string or a compare-set label). Use `''` if not applicable.

---

## What Not to Do

- **Do not** add wb sub-checkboxes to the adaptive comfort logger panel - pass `skipWb: true` to those `addSection` calls.
- **Do not** show `wetbulb-adv-wrap` in Long-Term/Historic mode - it must be hidden there.
- **Do not** show `wetbulb-adv-wrap` on histogram, scatter (comfort), density, or beta chart types - line and periodic only.
- **Do not** call `stullWetBulb` without handling its `null` return - the range guard returns `null` for invalid inputs.
- **Do not** reset `state.wetBulbLoggers` after the `addSection` calls - reset it **before**, because `addCheckbox` reads it to set initial checkbox state.
