# Monitoring & Alerting

How the ARC dashboard knows when data has stopped arriving, and who gets told.
There are two complementary layers: an **external freshness checker** (this repo)
and **Omnisense's native alarms** (configured on omnisense.com). Each covers a
gap the other cannot.

## Layer 1 — External freshness checker (`check_staleness.py`)

Runs inside the `update-dashboard-data.yml` workflow (daily, 04:00 UTC) after all
the fetch steps. It reads the fetched files under `data/` and decides whether each
source is current, then writes `data/status.json` (published to the status page).

When one or more sources are stale it also emits an email + ntfy push:

- **Email** via `send_alert_email.py` → recipients in the `ALERT_EMAILS` secret.
- **ntfy push** → topic `arc-ecovillage-status-7k3m` (subscribe in the ntfy app).
- `test-alerts.yml` (manual trigger) verifies both channels work.

### Thresholds

Tuned to each source's real update cadence so alerts fire on genuine stalls, not
on normal publishing lag:

| Source | Data threshold | Why |
|---|---|---|
| Omnisense | 24h | Sensors report ~daily |
| Open-Meteo historical | 36h | Goes to yesterday; 36h gives margin |
| Open-Meteo forecast | — | Always extends into the future; fetch date is the signal |
| ENSO ONI (NOAA PSL) | 120 days | Monthly index; NOAA lags up to ~3 months. **Must stay > 90d** — 90d equals NOAA's own normal lag and produced false alerts (see CHANGELOG 2026-05-31). |
| IOD DMI (BoM) | 14 days | Weekly index |
| MJO ROMI (NOAA PSL) | 7 days | Daily index, typically 2–5 day lag |

A separate 36h **fetch** threshold flags when the workflow itself hasn't refreshed.

### What this layer is good at

The **total-blackout** case: if the Omnisense gateway goes fully offline and
uploads stop entirely, Omnisense sends *nothing* — only an external watcher
notices the data stopped arriving. This layer is that watcher, and it is the one
thing Omnisense's own alarms structurally cannot cover.

## Layer 2 — Omnisense native alarms (configured on omnisense.com)

Omnisense can email directly when a sensor reading crosses a threshold — push
based, server side, **no scraping required**. Configure under *Alarm Thresholds →
Add A New Threshold*, and set recipients via *Edit Alarm Notification E-mail*.

These are **value** alarms (evaluated when a reading arrives), so they catch
per-sensor and connectivity *degradation* quickly, but cannot fire during a total
gateway blackout (no incoming reading = no evaluation). That blackout case is
Layer 1's job.

Recommended thresholds for uptime/liveness (in addition to any heat-event alarms):

| Field type | Alarm | Catches |
|---|---|---|
| **Total Unique Sensors seen by gateway** | Low, just below the real sensor count | A sensor dropping off the gateway |
| **Sensor Battery Voltage (Vbatt)** | Low (per sensor) | A dying sensor *before* it goes silent |
| **Cellular Signal Strength (CSS, 0–31)** | Low (e.g. < ~8) | Degrading gateway connectivity |
| **Cellular data connection uptime (Tcup)** | Low / zero | Gateway lost its cell connection |

> The May 1–4 2026 data gap was a gateway-connectivity field issue (see CHANGELOG).
> The CSS / Tcup alarms above are intended to catch that failure mode in real time.

## Why not poll more often

The freshness check only reflects what the fetch step pulled, and no source updates
faster than daily (climate indices are daily/weekly/monthly; Omnisense reports
~daily). Polling Omnisense hourly would mean 24× the logins for no fresher data,
risks looking abusive, and would re-send the same alert every run. The split above
keeps fast/granular detection on Omnisense's push side and uses the daily external
check purely as the blackout backstop.
