# arc_temp_humid - outstanding work

Updated 6 September 2026.

Everything described below is **not yet done**. What *is* done is in
`CHANGELOG.md`; the architecture is in `CLAUDE.md`.

---

## 1. Rename the GitHub repository

`actionresearchprojects/arc_tz_temp_humid` -> `arc_temp_humid`.

**This is now safe to do at any time, with nothing else to coordinate.**

It was not safe before. The main site's `sync-embedded.yml` derives its
destination folder from the dispatch payload's `source_repo`, so a rename would
have started filling a new `embedded/arc_temp_humid/` while the published page
went on iframing the old folder, frozen - no 404, no error, just a dashboard
that silently stopped updating.

That is fixed. `sync-embedded.yml` now maps **both** names to the same folder:

```
arc_tz_temp_humid|arc_temp_humid)    FOLDER="arc_temp_humid" ;;
```

So the rename is a no-op for the site. The public pages already live at their
new addresses and already read from `embedded/arc_temp_humid/`:

| URL | Status |
|---|---|
| `/graphs/arc-temp-humid/` | live |
| `/graphs/arc-temp-humid/config` | live |
| `/explainers/arc-temp-humid/` | live |
| `/graphs/arc-tz-temp-humid/` | redirects to the new address |
| `/explainers/arc-tz-temp-humid/` | redirects to the new address |

### After renaming

Two tidy-ups, neither urgent:

1. `git remote set-url origin https://github.com/actionresearchprojects/arc_temp_humid.git`
   in any local clone. GitHub redirects the old URL, so this is cosmetic.
2. Optionally set `source_repo` to `arc_temp_humid` in both workflows here. The
   mapping accepts either, so this is cosmetic too.

Then delete `embedded/arc_tz_temp_humid/` from the site repo - a dead ~16 MB
copy, superseded by `embedded/arc_temp_humid/`. Left in place for now so there
is a fallback if anything unexpected turns up.

Note the Pages URL for this repo also changes on rename, from
`actionresearchprojects.net/arc_tz_temp_humid/` to
`.../arc_temp_humid/`. Nothing links to it - the public route is `/graphs/`.

---

## 2. Automate the ARC UK Omnisense fetch

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

## 3. Decide the UK overheating threshold

Currently **none**: the three UK datasets have `"threshold": None`, so no red
band is drawn and the sidebar control is hidden rather than offering a
meaningless toggle. Tanzania keeps 32-35 C.

No UK figure was assumed because the sensible source, CIBSE TM52 / TM59, is
**per room type**. TM59 uses 26 C for bedrooms, but Grove's sensor is a living
room and Holywell's is "Internal Ambient".

Once decided it is one line per dataset:

```python
"threshold": {"low": 26, "high": 28},
```

The label, the band on all three chart types and the sidebar control follow
automatically.

---

## 4. Confirm the UK Open-Meteo coordinates

**Done and live**, but with one assumption worth correcting.

Both UK buildings now have their own Open-Meteo feed. Each drives its own
building's adaptive comfort running mean and both appear on the ARC UK chart.
They are fetched daily alongside the Tanzanian feed.

The coordinates in `fetch_openmeteo.py` are **town-centre positions** for
Hereford and Criccieth, not the buildings themselves:

```python
"grove":    {"lat": 52.0567, "lon": -2.7160, ...}   # Hereford
"holywell": {"lat": 52.9186, "lon": -4.2372, ...}   # Criccieth
```

Open-Meteo's historical model runs on a roughly 11 km grid, so a town-centre
fix is usually the same grid cell as the building - but if the exact positions
(or postcodes) are to hand, replace the two lat/lon pairs. It is a one-line
change per site and needs no other edits; the next daily run picks it up.

As a sanity check that the two feeds are genuinely distinct: Grove averages
1.03 C warmer than Holywell across 30,497 paired hours, with only 611 hours
identical - consistent with inland Herefordshire against coastal North Wales.

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
