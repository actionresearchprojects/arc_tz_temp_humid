# arc_temp_humid - outstanding work

Updated 6 September 2026. The repository rename and the main-site move are
complete and are no longer listed here; see `CHANGELOG.md` for what was done.

Everything described below is **not yet done**. What *is* done is in
`CHANGELOG.md`; the architecture is in `CLAUDE.md`.

---

## 1. Confirm the Holywell room type

**The only thing still genuinely blocked.** See section 2 - if `0E3C12EC`
("Internal Ambient", Holywell Barn) is a bedroom, TM59's 26 C night criterion
applies to it; if it is a living space, no fixed threshold does.

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

## 3. UK Open-Meteo coordinates - DONE

Both feeds now use the **Open-Meteo model grid cell centre** for their building:

```python
"grove":    {"lat": 52.057774, "lon": -2.704697, "start_date": "2026-07-01"}
"holywell": {"lat": 52.926643, "lon": -4.230377, "start_date": "2026-07-01"}
```

Requesting any point inside a grid cell returns that cell's series, so asking
for the centre gives byte-identical data to asking for the building, while the
number committed to this public repository is a fixed feature of the weather
model rather than a private address. The cell centres sit 0.60 km (Grove) and
0.65 km (Holywell) from the buildings.

Worth recording: the town-centre coordinates used before were **already in the
same grid cell** as both buildings, so the weather data was correct all along.
The change is about what gets published, not about accuracy.

`start_date` is each building's first sensor reading (2026-07-31) minus a
30-day lead-in. The lead-in is not padding: the EN16798-1 running mean is seeded
from its first day and decays that seed by alpha=0.8 per day, so without a
run-up the first fortnight of comfort points would be measured against a running
mean still carrying an arbitrary starting value. Thirty days reduces the seed's
weight to about 0.1%, and in practice reproduces the running means obtained from
three and a half years of history to within 0.1-0.3 C.

If sensors are ever installed earlier than July 2026, move `start_date` back to
30 days before the new earliest reading.

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
