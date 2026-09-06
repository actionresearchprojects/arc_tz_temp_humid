# arc_temp_humid - outstanding work

Updated 6 September 2026. The repository rename and the main-site move are
complete and are no longer listed here; see `CHANGELOG.md` for what was done.

Everything described below is **not yet done**. What *is* done is in
`CHANGELOG.md`; the architecture is in `CLAUDE.md`.

---

## 1. UK overheating threshold - RESOLVED, no band applies

Both UK datasets keep `"threshold": None`. That is now a decision rather than a
placeholder.

CIBSE TM59 (2017) section 4.2 requires **both** of:

- **(a) Living rooms, kitchens and bedrooms.** Hours where dT is at least 1 K,
  May to September, no more than 3% of occupied hours. dT is measured against
  the **adaptive** limit (TM52 Criterion 1), not a fixed temperature.
- **(b) Bedrooms only.** Operative temperature between 22:00 and 07:00 not above
  **26 C** for more than 1% of annual hours - TM59 counts that as 32 hours, so
  33 or more is a fail.

The only fixed figure in TM59 is that 26 C, and it applies to bedrooms at night.
Both UK sensors are in **living rooms** (Grove `169502D1`, and Holywell
`0E3C12EC`, confirmed and renamed from "Internal Ambient"), so criterion (b)
does not apply to either and there is no fixed band to draw. Criterion (a) is
the adaptive test, which the comfort chart already serves.

If a bedroom sensor is added later, the threshold is currently per-region, so a
per-logger threshold would be needed to draw 26 C for that sensor alone.

### Two caveats before quoting TM59 numbers from this dashboard

- TM59 is a **design and modelling** methodology: standard occupancy profiles,
  dynamic simulation, and **operative** temperature. This dashboard plots
  **measured air** temperature, already listed as a known limitation in
  `adaptivecomfort.md`. Numbers from here are indicative of TM59, not a TM59
  assessment.
- Criterion (a) is adaptive against **TM52 Category II**
  (`0.33 x Trm + 18.8 + 3`), which is not a band the dashboard currently offers.
  See section 2.

---

## 2. Decide whether to add the TM52 / EN 16798-1 bands

The UK datasets currently default to **ASHRAE 55 80%**
(`0.31 x Trm + 17.8 +/- 3.5`). TM59 criterion (a) is defined against **TM52 /
EN 16798-1 Category II** (`0.33 x Trm + 18.8 +/- 3`), a different line fitted to
European rather than global field data.

Across the UK running-mean range the TM52 Cat II upper limit sits about 0.7 to
0.9 K above ASHRAE's, so ASHRAE is the more conservative of the two:

| Upper limit at | Trm 10 C | Trm 15 C | Trm 20 C |
|---|---|---|---|
| ASHRAE 55 80% (current) | 24.4 | 26.0 | 27.5 |
| TM52 / EN 16798-1 Cat II | 25.1 | 26.8 | 28.4 |
| TM52 / EN 16798-1 Cat III | 26.1 | 27.8 | 29.4 |

On the data as it stands the choice changes nothing that matters. TM59
criterion (a) exceedance is 0.00% at Grove under every model, and at Holywell
0.53% on ASHRAE against 0.27% on Cat II - both far inside the 3% allowance.

It matters only if a TM59 result is to be **stated**, because then the line has
to be the one TM59 names. Worth noting that EN 16798-1 designates **Category III
for existing buildings**, which these retrofits are, so Cat III may be more
defensible than Cat II. That is a reporting decision rather than a technical
one.

Adding both is small: two entries in `COMFORT_MODELS` plus labels.

## 3. Open-Meteo coordinates and date ranges - DONE

All three feeds now publish a coordinate that is not the building, and start
from the building's own record rather than an arbitrary date.

| Feed | Committed coordinate | Distance from building | Feed starts |
|---|---|---|---|
| `tz` | `-7.07, 39.30` | 0.56 km | 2023-02-12 |
| `grove` | `52.057774, -2.704697` | 0.60 km | 2026-07-01 |
| `holywell` | `52.926643, -4.230377` | 0.65 km | 2026-07-01 |

**The UK values are Open-Meteo model grid cell centres.** Requesting any point
inside a cell returns that cell's series, so this is byte-identical data while
the published number is a fixed feature of the weather model rather than a
private address. The town-centre coordinates used before were already in the
same cells, so the weather data was correct all along - what changed is what
gets published.

**Tanzania is rounded to 2dp instead**, because Open-Meteo serves that region
from a coarser global model and echoes the requested point rather than snapping
to a grid. Rounding costs nothing there: even 1dp (3.9 km away) returns
byte-identical data. The previous value carried seven decimals, which is
centimetre-level precision on a children's facility in a public repository.

### The 30-day lead-in, and a bug it fixed

Each `start_date` is the building's first sensor reading minus 30 days. The
lead-in is not padding: the EN 16798-1 running mean is seeded from its own first
day and decays that seed by alpha = 0.8 daily, so without a run-up the opening
fortnight of comfort points are measured against a running mean still carrying
an arbitrary starting value. Thirty days reduces the seed's weight to about 0.1%.

This turned out to matter for Tanzania, not just the UK. House 5's first sensor
reading is **2023-03-14**, while the Open-Meteo feed began **2023-03-15** - a day
*after* the data it exists to contextualise. Every House 5 comfort point in the
first couple of weeks of the record was being measured against a running mean
with no history behind it. The feed now starts 2023-02-12.

If sensors are ever installed earlier than the current start dates, move
`start_date` back to 30 days before the new earliest reading.

## 4. ARC UK Omnisense fetch - DONE, untested in CI

`SITES["uk"]` is filled in with site number **58345**
("Simmonds.Mills Retrofits") and a `--site uk` step runs in
`update-dashboard-data.yml` alongside the Tanzanian one, using the same
`OMNISENSE_USERNAME` / `OMNISENSE_PASSWORD` secrets.

**It has not run yet.** The credentials live in repository secrets and are not
available locally, so the login and download path could not be exercised here.
The first scheduled run (04:00 UTC) is the test. The step is
`continue-on-error`, so a failure will not block the rest of the build; check
the run log, and the sidebar's "Omnisense (UK) last updated" note, afterwards.

Until it succeeds the hand-added export in `data/omnisense_uk/` remains the
source, and nothing breaks if the fetch fails.

---

## 5. Known limitation, not a task

ASHRAE 55 Section 5.4.1(a) requires that no heating is in operation. Nothing at
any site records heating status, and nothing in a temperature and humidity trace
reliably separates a heated room from a merely warm one.

The dashboard states this rather than inferring it: a bolded line in the sidebar
applicability panel directly beneath the quoted criterion, and in the tooltips
explaining the method. The 10-33.5 C running-mean gate is enforced
automatically and greys out readings the standard does not cover.

That gate now has teeth it did not have before, because the UK Open-Meteo feeds
reach back to March 2023: once UK winter indoor data exists, cold-weather
readings will be greyed and excluded from the comfort percentage. But **a mild
day with the heating on will still pass every test the dashboard can apply**.

Closing this properly needs a heating-status input, not a cleverer algorithm.
See `adaptivecomfort.md` section 2 for the full reasoning, including why
calendar-month filtering was considered and rejected.
