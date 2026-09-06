# arc_temp_humid — outstanding work

Written 6 September 2026, at the end of the rebrand and ARC UK build-out.

Everything described below is **not yet done**. What *is* done is recorded in
`CHANGELOG.md`; the architecture is in `CLAUDE.md`.

---

## 1. Rename the GitHub repository

`actionresearchprojects/arc_tz_temp_humid` → `arc_temp_humid`.

The local folder, the git remote and every in-repo reference are already
updated. The rename itself has not been done, because it is outward-facing.

### What the rename will and will not break

GitHub permanently redirects the old repository URL, for both web and git, so
clones, fetches, existing PATs and repository secrets all keep working. Actions
and their secrets survive a rename untouched.

**The damage is elsewhere, and it is silent.** The live dashboard reaches the
public site through this chain:

```
actionresearchprojects.net/graphs/arc-tz-temp-humid/
    └── iframe → ../../embedded/arc_tz_temp_humid/index.html
                     ↑ written by sync-embedded.yml on the main site,
                       into a folder named after the source repo
```

`sync-embedded.yml` derives the destination folder straight from the
`source_repo` value in the dispatch payload. **That payload deliberately still
says `arc_tz_temp_humid`** — it names the repo as it exists on GitHub, and it
was briefly set to the new name during the rebrand, which broke the very first
sync after the push (`fatal: could not read Username for 'https://github.com'`
— the clone of a repo that does not exist yet). Both workflows are commented to
say so. Once the payload does say `arc_temp_humid`, the next sync will:

1. clone `github.com/actionresearchprojects/arc_temp_humid.git` — fine;
2. write into a **new** folder, `embedded/arc_temp_humid/`;
3. leave `embedded/arc_tz_temp_humid/` in place, frozen at whatever it held
   on the day of the rename.

The public page still iframes the **old** folder. So nothing 404s and nothing
errors — the dashboard simply stops updating, showing stale data indefinitely.
That is the worst failure mode available, because nobody notices.

### The main-site changes that must accompany the rename

All in `actionresearchprojects/actionresearchprojects.github.io`:

| # | Change | Why |
|---|---|---|
| 1 | `graphs/arc-tz-temp-humid/` → `graphs/arc-temp-humid/` | Public URL drops "tz" to match the rebrand |
| 2 | In that page, iframe `src` → `../../embedded/arc_temp_humid/index.html` | Otherwise it keeps pointing at the frozen folder |
| 3 | Delete `embedded/arc_tz_temp_humid/` once the first new sync has run | Dead copy, ~16 MB |
| 4 | `explainers/arc-tz-temp-humid/` → `explainers/arc-temp-humid/`, then flip the header info-icon link in `build.py` to match | The dashboard's info icon deliberately still points at the **old** slug, so nothing 404s in the meantime |
| 5 | Redirect the old `/graphs/arc-tz-temp-humid/` URL to the new one | Existing links and any published references |
| 7 | **In this repo**: flip `source_repo` to `arc_temp_humid` in both workflows, and `git remote set-url origin` to the new URL | Until this, syncs keep filling the old folder; flip it *before* the rename and every sync fails |
| 6 | Update remaining mentions: `README.md`, `explainers/data-flow/viewer.html`, `explainers/arc-tz-weather/viewer.html` | Stale cross-links |

Item 4 is deliberately two-sided. The dashboard's header info icon was left
pointing at the old explainer slug, because that path still works and switching
it early would have shipped a live 404. Rename the explainer folder first, then
change the one link in `build.py` (it is commented to say so) and rebuild.

### Recommended order

The ordering matters more than it looks, because the payload and the repo name
have to change together — either one alone breaks the sync.

1. Make the main-site changes 1, 2, 5 and 6 **first**, pointing at the new
   folder names before they exist. The site briefly serves the old embedded
   copy from a new path, which is harmless.
2. Rename the repository on GitHub.
3. Immediately do item 7: flip `source_repo` in both workflows and update the
   git remote. Between steps 2 and 3 the sync is broken, so keep the gap short.
4. Rename the explainer folder (item 4) and flip the info-icon link in
   `build.py`, then rebuild.
5. Push, and confirm the sync run on the main site succeeds and that
   `embedded/arc_temp_humid/` appears.
6. Delete `embedded/arc_tz_temp_humid/` (item 3).

Also check that the Pages URL change is acceptable: this repo publishes to
`actionresearchprojects.net/arc_tz_temp_humid/`, which becomes
`actionresearchprojects.net/arc_temp_humid/`.

---

## 2. Automate the ARC UK Omnisense fetch

The UK export is currently added **by hand** to
`data/omnisense_uk/omnisense_uk_YYYYMMDD_HHMM.csv`. The timestamp in the
filename is the fetch time and is what the sidebar's freshness note reads, so
keep the format.

`fetch_omnisense.py` is already parameterised by site. To switch it on:

1. Fill in the commented-out `SITES["uk"]` entry, in particular **`site_nbr`**.
2. Add a `--site uk` step to `.github/workflows/update-dashboard-data.yml`,
   alongside the existing Omnisense step and with the same `continue-on-error`.

### Finding the site number

It is not in the CSV export — the export carries site *names*, not ids, and the
`download_935909450.csv` filename is a download-job id, not a site number.

Log in at omnisense.com, select the site, and read `siteNbr=` from the address
bar. That is exactly where the Tanzanian value came from: `152865`, visible in
`fetch_omnisense.py` as `dnld_rqst.asp?siteNbr=152865`.

The site to look for is named **"Simmonds.Mills Retrofits"** — that is the
`site_name` on every block of the UK export.

### Credentials are probably already correct

The UK export contains a sensor labelled `House 5 Metal Roof S.E` alongside the
Grove, Holywell, Chestnuts and No. 59 sensors. A single login therefore already
sees both the Tanzanian and the UK material, which strongly suggests the
existing `OMNISENSE_USERNAME` / `OMNISENSE_PASSWORD` secrets will work and only
`site_nbr` differs.

If that turns out to be wrong, `SITES["uk"]` accepts `username_env` and
`password_env` naming its own secrets; the code already falls back to the
shared pair when they are absent.

### One thing to check when it runs

The UK export is a single CSV covering several sites — Grove, Holywell,
Chestnuts, No. 59 — of which this dashboard uses four sensors. `GROVE_SENSORS`
and `HOLYWELL_SENSORS` in `build.py` filter it by sensor id, so unrelated
sensors are ignored rather than plotted. If sensors are added or swapped at
those sites, those two sets are what needs updating.

---

## 3. Decide the UK overheating threshold

Currently **none**: `DATASETS["grove"]["threshold"]` and the other two UK
datasets are `None`, so no red band is drawn and the sidebar control is hidden
rather than offering a meaningless toggle.

Tanzania keeps 32–35 °C, which is a Mkuranga heat-stress range and means
nothing against UK data peaking near 29 °C.

No UK figure was assumed, because the sensible source — CIBSE TM52 / TM59 — is
**per room type**. TM59 uses 26 °C for bedrooms, but Grove's sensor is a living
room and Holywell's is "Internal Ambient", so a single number cannot be picked
without deciding which criterion applies to which sensor.

Once decided it is one line per dataset:

```python
"threshold": {"low": 26, "high": 28},   # or whatever the criterion gives
```

The label, the band on all three chart types and the sidebar control all follow
from that automatically.

---

## 4. Optional: a UK Open-Meteo feed

Not needed for correctness — each UK building carries its own external ambient
sensor, and that is what its adaptive comfort running mean uses. Adding
Open-Meteo would give the UK datasets an external reference series and a
forecast, as Tanzania has.

`fetch_openmeteo.py` has a commented-out `LOCATIONS["uk"]` entry with the shape
required. Beyond filling it in and adding a `--location uk` workflow step, the
UK datasets would need an Open-Meteo id in their `external_sensors` and the new
CSVs loaded from the new output directory.

Note the coordinates in that template are a placeholder for Grove Cottage,
Hereford. Grove and Holywell are about 150 km apart, so one location cannot
serve both — Holywell Barn (Criccieth) would need its own entry.

---

## 5. Known limitation, not a task

ASHRAE 55 Section 5.4.1(a) requires that no heating is in operation. Nothing at
any site records heating status, and nothing in a temperature and humidity trace
reliably separates a heated room from a merely warm one.

The dashboard states this rather than inferring it: a note on the UK comfort
chart, a bolded line in the sidebar applicability panel directly beneath the
quoted criterion, and the tooltips explaining the method. The 10–33.5 °C
running-mean gate is enforced automatically and will grey out cold-weather
readings once UK winter data exists — but **a mild day with the heating on will
pass every test the dashboard can apply and still sit outside the standard's
scope**.

Closing this properly needs a heating-status input, not a cleverer algorithm.
See `adaptivecomfort.md` §2 for the full reasoning, including why calendar-month
filtering was considered and rejected.
