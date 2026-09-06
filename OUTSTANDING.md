# arc_temp_humid - outstanding work

Updated 6 September 2026. The repository rename and the main-site move are
complete and are no longer listed here; see `CHANGELOG.md` for what was done.

Everything described below is **not yet done**. What *is* done is in
`CHANGELOG.md`; the architecture is in `CLAUDE.md`.

---

## 1. Automate the ARC UK Omnisense fetch

**This is the only item still blocked on information I do not have.**

The UK export is added **by hand** to
`data/omnisense_uk/omnisense_uk_YYYYMMDD_HHMM.csv`. The timestamp is the fetch
time and is what the sidebar's freshness note reads, so keep the format.

`fetch_omnisense.py` is already parameterised by site. To switch it on:

1. Fill in the commented-out `SITES["uk"]` entry, in particular **`site_nbr`**.
2. Add a `--site uk` step to `.github/workflows/update-dashboard-data.yml`,
   next to the existing Omnisense step, with the same `continue-on-error`.

### Finding the site number

It is not in the CSV: the export carries site *names*, not ids, and the
`download_935909450.csv` filename was a download-job id.

Log in at omnisense.com, select the site, and read `siteNbr=` from the address
bar. That is where the Tanzanian `152865` came from - it appears in
`fetch_omnisense.py` as `dnld_rqst.asp?siteNbr=152865`.

The site is named **"Simmonds.Mills Retrofits"** - the `site_name` on every
block of the UK export.

### Credentials are probably already correct

The UK export contains a sensor labelled `House 5 Metal Roof S.E` alongside the
Grove, Holywell, Chestnuts and No. 59 sensors, so one login already sees both
the Tanzanian and UK material. The existing `OMNISENSE_USERNAME` /
`OMNISENSE_PASSWORD` secrets will very likely work, with only `site_nbr`
differing.

If not, `SITES["uk"]` accepts `username_env` / `password_env` naming its own
secrets, falling back to the shared pair when absent.

### When it runs

The UK export is one CSV covering several sites - Grove, Holywell, Chestnuts,
No. 59 - of which this dashboard uses four sensors. `GROVE_SENSORS` and
`HOLYWELL_SENSORS` in `build.py` filter by sensor id, so the rest are ignored
rather than plotted. Those two sets are what to update if sensors change.

---

## 2. Decide the UK overheating threshold

Currently **none**: the three UK datasets have `"threshold": None`, so no red
band is drawn and the sidebar control is hidden. Tanzania keeps 32-35 C.

Having now read CIBSE TM59 (2017), the position is clearer than "pick a
number", and leaving it off may well be the right answer.

### What TM59 actually requires

Compliance for a naturally ventilated home is **both** of (section 4.2):

- **(a) Living rooms, kitchens and bedrooms.** The hours where dT is at least
  1 K, May to September, must be no more than 3% of occupied hours. This is
  TM52 Criterion 1, and dT is measured against the **adaptive** comfort limit,
  not a fixed temperature.
- **(b) Bedrooms only.** Operative temperature between 22:00 and 07:00 must not
  exceed **26 C** for more than 1% of annual hours. TM59 spells out the count:
  32 hours, so 33 or more is a fail.

So the only fixed number in TM59 is 26 C, and it applies **to bedrooms, at
night, counted over the year**. For a living room or kitchen there is no fixed
threshold at all - the test is the adaptive one, which the adaptive comfort
chart already serves.

### What that means for the two UK sensors

| Logger | Name | Room type | Fixed threshold applies? |
|---|---|---|---|
| `169502D1` | Living Room (No. 57), Grove | living room | **no** - criterion (a) only |
| `0E3C12EC` | Internal Ambient, Holywell | **unknown** | only if it is a bedroom |

Grove's sensor is a living room, so TM59 gives it no fixed band. Holywell's is
labelled only "Internal Ambient"; **that is the room type worth confirming**.

### Three honest options

1. **Leave the threshold off** (current state). Defensible: neither sensor is a
   confirmed bedroom, and criterion (a) is already covered by the adaptive
   chart.
2. **Add 26 C only where a logger is a bedroom.** Correct, but the threshold is
   currently per-region, so this needs a per-logger threshold - a real change,
   though not a large one.
3. **Draw 26 C across the UK region as a rough reference.** Quickest, and the
   least honest: TM59's 26 C is night-only and bedroom-only, so a permanent band
   across a 24-hour living-room chart misrepresents the standard.

### Two caveats before quoting TM59 numbers from this dashboard

- TM59 is a **design and modelling** methodology. It assumes standard occupancy
  profiles and dynamic simulation, and evaluates **operative** temperature. This
  dashboard plots **measured air** temperature, which is already listed as a
  known limitation in `adaptivecomfort.md`. Numbers taken from here are
  indicative of TM59, not a TM59 assessment.
- Criterion (a) is adaptive against **TM52 Category II**, whose upper limit is
  `0.33 x Trm + 18.8 + 3`. The dashboard currently offers ASHRAE 55 and the
  Vellei models, neither of which is that line. If the UK datasets are ever to
  be read against TM52/TM59, adding a TM52 Cat II band to the comfort model
  dropdown is the change that would do it - and is probably worth more than the
  threshold band.

## 3. Confirm the UK Open-Meteo coordinates

**Working and live**, on one assumption worth correcting.

Both UK buildings have their own Open-Meteo feed, fetched daily. Each drives its
own building's adaptive comfort running mean and both appear on the ARC UK
chart. The coordinates in `fetch_openmeteo.py` are **town-centre positions**:

```python
"grove":    {"lat": 52.0567, "lon": -2.7160, ...}   # Hereford
"holywell": {"lat": 52.9186, "lon": -4.2372, ...}   # Criccieth
```

### How much the precision matters

Measured, not assumed. Open-Meteo snaps a request to its model grid, and that
grid is finer than the 11 km often quoted. Comparing the returned hourly series
against the town-centre baseline, June to August 2026 (2208 hours):

| Offset from baseline | Mean difference | Max | Hours differing by >0.5 C |
|---|---|---|---|
| ~0.5 km | 0.18 C | 1.6 C | 4.9% |
| ~2 km | 0.51 C | 4.0 C | 32.8% |
| ~9 km | 1.52 C | 4.9 C | 95.6% |
| ~20 km | 1.63 C | 8.0 C | 83.0% |

So getting within roughly half a kilometre is worth doing; beyond about two
kilometres the series starts to drift meaningfully from the site.

### The privacy point

These are private homes and **this repository is public**, so an exact
coordinate committed here is effectively a published home location.

Half a kilometre of precision is enough, and that is about **two decimal
places**: 0.01 degrees of latitude is around 1.1 km, and of longitude at these
latitudes around 0.7 km. So the resolution to commit is two decimals - it puts
the request in the right grid cell without pinpointing a dwelling.

If exact positions or postcodes are supplied, round them to two decimals before
they go in the file. It is a one-line change per site and the next daily run
picks it up.

As a check that the two feeds are genuinely distinct: Grove averages 1.03 C
warmer than Holywell across 30 497 paired hours, only 611 of them identical -
consistent with inland Herefordshire against coastal North Wales.

## 4. Known limitation, not a task

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
