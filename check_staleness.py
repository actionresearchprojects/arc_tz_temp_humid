"""
check_staleness.py – Data freshness checker for ARC monitoring.

Reads all fetched data files under data/ and evaluates whether each source
is current. Writes data/status.json on every run. When one or more sources
are stale also writes:
  /tmp/alert_subject.txt  – one-line email subject
  /tmp/alert_body.html    – HTML email body
  /tmp/ntfy_body.txt      – short push-notification message

In a GitHub Actions environment ($GITHUB_OUTPUT is set) writes:
  stale=true|false
  stale_count=N
  checked_date=YYYY-MM-DD

Exit 0 if all sources are within tolerance, exit 1 if any are stale.

status.json schema per source:
  key, label, status        – overall ok/stale/unknown
  fetch_date, fetch_age_hours, fetch_status  – when the action last fetched
  data_date,  data_age_hours,  data_status   – latest timestamp in the data
  note                      – human note about expected lag
"""

import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
NOW = datetime.now(timezone.utc)

# ── thresholds ─────────────────────────────────────────────────────────────────

FETCH_THRESHOLD_H = 36  # all sources: flag if action hasn't refreshed in >36h

DATA_THRESHOLD_H = {
    "omnisense":      24,        # flag if no new sensor reading in over a day
    "openmeteo_hist": 36,        # historical goes to yesterday; 36h gives margin
    "openmeteo_fc":   None,      # forecast always extends into the future; no data check
    "enso":           120 * 24,  # NOAA ONI is monthly with up to ~3 month lag; 120d tolerates normal lag, fires only on a genuine stall
    "iod":            14 * 24,   # BoM IOD is weekly
    "mjo":             7 * 24,   # NOAA MJO ROMI updated daily with short lag
}

LABELS = {
    "omnisense":      "Omnisense",
    "openmeteo_hist": "Open-Meteo historical",
    "openmeteo_fc":   "Open-Meteo forecast",
    "enso":           "ENSO ONI (NOAA PSL)",
    "iod":            "IOD DMI (Bureau of Meteorology)",
    "mjo":            "MJO ROMI (NOAA PSL)",
}

NOTES = {
    "enso": "Monthly index; NOAA publishes with up to ~3 month lag — alerts only if data is >120 days old",
    "iod":  "Weekly index from BoM; up to 14 days lag is normal",
    "mjo":  "Daily index; NOAA typically lags 2–5 days",
    "openmeteo_fc": "Latest data shows forecast horizon (~16 days out); fetch date is the freshness signal",
}

STATUS_PAGE = "https://actionresearchprojects.net/status"

# The Omnisense CSV holds readings from multiple sensors (indoor temp/humidity
# units plus the ARC weather station). Restrict the omnisense freshness check
# to the weather station sensor specifically, so a dead weather station isn't
# masked by other sensors in the same file still reporting fine.
WEATHER_STATION_SENSOR_ID = "30B40014"


# ── helpers ────────────────────────────────────────────────────────────────────

def utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def file_date_from_glob(pattern: str):
    """Return the datetime encoded in the newest filename matching DATA/pattern."""
    files = sorted(glob.glob(os.path.join(DATA, pattern)))
    if not files:
        return None
    m = re.search(r"(\d{8})_(\d{4})", os.path.basename(files[-1]))
    if not m:
        return None
    return utc(datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M"))


def latest_iso_in_file(path: str, col: int = 0, match_col: int = None, match_val: str = None):
    """Return the latest ISO-style datetime found in a delimited file column.

    If match_col/match_val are given, only rows where that column equals
    match_val are considered (e.g. restrict to one sensor ID in a CSV shared
    by multiple sensors, so an active sensor doesn't mask a dead one)."""
    if not path or not os.path.exists(path):
        return None
    fmts = ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")
    latest = None
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                sep = "," if "," in line else None
                parts = line.strip().split(sep) if sep else line.strip().split()
                if len(parts) <= col:
                    continue
                if match_col is not None and (len(parts) <= match_col or parts[match_col].strip() != match_val):
                    continue
                val = parts[col].strip()
                for fmt in fmts:
                    try:
                        ts = utc(datetime.strptime(val, fmt))
                        if latest is None or ts > latest:
                            latest = ts
                        break
                    except ValueError:
                        pass
    except OSError:
        pass
    return latest


def latest_yyyymmdd_in_file(path: str, col: int = 0):
    """Return latest YYYYMMDD date found in a file column."""
    if not path or not os.path.exists(path):
        return None
    latest = None
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split(",") if "," in line else line.strip().split()
                if len(parts) <= col:
                    continue
                try:
                    ts = utc(datetime.strptime(parts[col].strip(), "%Y%m%d"))
                    if latest is None or ts > latest:
                        latest = ts
                except ValueError:
                    pass
    except OSError:
        pass
    return latest


def latest_ymd_cols(path: str, yr=0, mo=1, dy=2):
    """Return latest date from separate year/month/day columns (e.g. MJO file)."""
    if not path or not os.path.exists(path):
        return None
    latest = None
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) <= max(yr, mo, dy):
                    continue
                try:
                    ts = utc(datetime(int(parts[yr]), int(parts[mo]), int(parts[dy])))
                    if latest is None or ts > latest:
                        latest = ts
                except (ValueError, IndexError):
                    pass
    except OSError:
        pass
    return latest


def latest_oni_date(path: str):
    """Latest non-fill date from NOAA ONI CSV (skips -9999 rows)."""
    if not path or not os.path.exists(path):
        return None
    latest = None
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 2 or "-9999" in parts[1]:
                    continue
                try:
                    ts = utc(datetime.strptime(parts[0].strip(), "%Y-%m-%d"))
                    if latest is None or ts > latest:
                        latest = ts
                except ValueError:
                    pass
    except OSError:
        pass
    return latest


# ── entry builder ──────────────────────────────────────────────────────────────

def age_status(dt, threshold_h):
    """Return (status, age_hours) for a datetime against a threshold (None = no check).
    Future dates (negative age) return age_hours=None so display omits the age label."""
    if dt is None:
        return "unknown", None
    age_h = (NOW - dt).total_seconds() / 3600
    if threshold_h is None:
        return "ok", round(age_h, 1) if age_h >= 0 else None
    return ("ok" if age_h <= threshold_h else "stale"), round(age_h, 1)


def entry(key: str, fetch_dt, data_dt) -> dict:
    label = LABELS[key]
    note = NOTES.get(key, "")

    fetch_status, fetch_age = age_status(fetch_dt, FETCH_THRESHOLD_H)
    data_status,  data_age  = age_status(data_dt,  DATA_THRESHOLD_H[key])

    if fetch_status == "stale" or data_status == "stale":
        overall = "stale"
    elif fetch_status == "unknown" and data_status == "unknown":
        overall = "unknown"
    else:
        overall = "ok"

    return dict(
        key=key,
        label=label,
        status=overall,
        fetch_date=fetch_dt.strftime("%Y-%m-%d %H:%M UTC") if fetch_dt else None,
        fetch_age_hours=fetch_age,
        fetch_status=fetch_status,
        data_date=data_dt.strftime("%Y-%m-%d %H:%M UTC") if data_dt else None,
        data_age_hours=data_age,
        data_status=data_status,
        note=note,
    )


# ── main ───────────────────────────────────────────────────────────────────────

def run():
    sources = []

    # Omnisense – timestamped filenames → fetch date available
    omni_files = sorted(glob.glob(os.path.join(DATA, "omnisense", "omnisense_*.csv")))
    sources.append(entry("omnisense",
        fetch_dt=file_date_from_glob("omnisense/omnisense_*.csv"),
        data_dt=latest_iso_in_file(omni_files[-1] if omni_files else None, col=2,
                                    match_col=0, match_val=WEATHER_STATION_SENSOR_ID)))

    # Open-Meteo – timestamped filenames → fetch date available
    hist_files = sorted(glob.glob(os.path.join(DATA, "openmeteo", "historical_*.csv")))
    sources.append(entry("openmeteo_hist",
        fetch_dt=file_date_from_glob("openmeteo/historical_*.csv"),
        data_dt=latest_iso_in_file(hist_files[-1] if hist_files else None, col=0)))
    fc_files = sorted(glob.glob(os.path.join(DATA, "openmeteo", "forecast_*.csv")))
    sources.append(entry("openmeteo_fc",
        fetch_dt=file_date_from_glob("openmeteo/forecast_*.csv"),
        data_dt=latest_iso_in_file(fc_files[-1] if fc_files else None, col=0)))

    # Climate cycles – files are overwritten in-place (no timestamp in name)
    # so only data currency is tracked
    sources.append(entry("enso",
        fetch_dt=None,
        data_dt=latest_oni_date(os.path.join(DATA, "cycles", "enso", "oni.csv"))))
    sources.append(entry("iod",
        fetch_dt=None,
        data_dt=latest_yyyymmdd_in_file(os.path.join(DATA, "cycles", "iod", "iod_1.txt"))))
    sources.append(entry("mjo",
        fetch_dt=None,
        data_dt=latest_ymd_cols(os.path.join(DATA, "cycles", "mjo", "romi.cpcolr.1x.txt"))))

    stale = [s for s in sources if s["status"] == "stale"]
    overall = "ok" if not stale else "stale"

    result = {
        "checked_at": NOW.strftime("%Y-%m-%d %H:%M UTC"),
        "overall": overall,
        "sources": sources,
    }

    with open(os.path.join(DATA, "status.json"), "w") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))

    # GitHub Actions outputs
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"stale={'true' if stale else 'false'}\n")
            f.write(f"stale_count={len(stale)}\n")
            f.write(f"checked_date={NOW.strftime('%Y-%m-%d')}\n")

    if stale:
        n = len(stale)
        noun = "source" if n == 1 else "sources"
        subject = (
            f"ARC Dashboard Alert: {n} data {noun} out of date "
            f"({NOW.strftime('%Y-%m-%d %H:%M UTC')})"
        )

        def fmt_li(label, date_val, age_h, threshold_h):
            if date_val is None:
                return f"<li>{label}: <strong>MISSING</strong></li>"
            limit = f" (limit {threshold_h}h)" if threshold_h else ""
            return f"<li>{label}: {date_val} &mdash; {age_h}h ago{limit}</li>"

        stale_items = []
        for s in stale:
            rows = []
            if s["fetch_status"] == "stale" or s["fetch_date"]:
                rows.append(fmt_li("Last fetched", s["fetch_date"],
                                   s["fetch_age_hours"], FETCH_THRESHOLD_H))
            if s["data_date"] or s["data_status"] == "stale":
                rows.append(fmt_li("Latest data",  s["data_date"],
                                   s["data_age_hours"], DATA_THRESHOLD_H[s["key"]]))
            note_html = f"<em style='color:#6b7280;font-size:12px'>{s['note']}</em><br>" if s["note"] else ""
            stale_items.append(
                f"<li><strong>{s['label']}</strong><br>{note_html}<ul>{''.join(rows)}</ul></li>"
            )
        stale_li = "\n    ".join(stale_items)

        def status_tag(st):
            colour = {"ok": "#15803d", "stale": "#b91c1c"}.get(st, "#6b7280")
            text = {"ok": "OK", "stale": "OUT OF DATE"}.get(st, "UNKNOWN")
            return (f"<span style='display:inline-block;min-width:96px;font-size:12px;"
                    f"font-weight:600;color:{colour};'>{text}</span>")

        all_rows = "\n    ".join(
            "<tr style='border-top:1px solid #e5e7eb;'>"
            f"<td style='padding:6px 12px 6px 0;vertical-align:top;'>{status_tag(s['status'])}</td>"
            f"<td style='padding:6px 0;vertical-align:top;'>"
            f"<strong>{s['label']}</strong>"
            + (f"<br><span style='color:#6b7280;font-size:12px;'>Last fetched {s['fetch_date']}</span>" if s["fetch_date"] else "")
            + (f"<br><span style='color:#6b7280;font-size:12px;'>Latest data {s['data_date']}</span>" if s["data_date"] else "")
            + "</td></tr>"
            for s in sources
        )

        html_body = f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:system-ui,-apple-system,sans-serif;color:#111827;line-height:1.5;max-width:600px;margin:0 auto;padding:24px;">
  <h2 style="font-size:18px;margin:0 0 4px;">ARC Data Pipeline Alert</h2>
  <p style="color:#6b7280;margin:0 0 20px;">
    {len(stale)} data {noun} {'has' if len(stale) == 1 else 'have'} not updated within the expected window.
    Checked {NOW.strftime('%Y-%m-%d %H:%M UTC')}.
  </p>

  <h3 style="font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:#b91c1c;margin:0 0 8px;">Out of date</h3>
  <ul style="margin:0 0 24px;padding-left:18px;">
    {stale_li}
  </ul>

  <h3 style="font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:#374151;margin:0 0 8px;">All sources</h3>
  <table style="border-collapse:collapse;width:100%;font-size:14px;margin:0 0 24px;">
    {all_rows}
  </table>

  <p style="margin:0 0 24px;">
    <a href="{STATUS_PAGE}"
       style="display:inline-block;background:#111827;color:#ffffff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;">
      View the status page
    </a>
  </p>

  <hr style="border:none;border-top:1px solid #e5e7eb;">
  <p style="color:#9ca3af;font-size:12px;">
    Sent automatically by the ARC monitoring workflow.
    To change who receives these alerts, edit the ALERT_EMAILS secret in the
    <a href="https://github.com/actionresearchprojects/arc_tz_temp_humid/settings/secrets/actions"
       style="color:#9ca3af;">arc_tz_temp_humid repository settings</a>.
  </p>
</body>
</html>"""

        stale_md = "\n".join(
            f"- {s['label']}"
            + (f": last fetched {s['fetch_date']} ({s['fetch_age_hours']}h ago)"
               if s["fetch_status"] == "stale" else "")
            + (f"; latest data {s['data_date']} ({s['data_age_hours']}h ago)"
               if s["data_status"] == "stale" else "")
            for s in stale
        )
        ntfy = (
            f"{len(stale)} data {noun} out of date, checked "
            f"{NOW.strftime('%Y-%m-%d %H:%M UTC')}.\n\n"
            f"{stale_md}\n\n"
            f"Status page: {STATUS_PAGE}"
        )

        with open("/tmp/alert_subject.txt", "w") as f:
            f.write(subject)
        with open("/tmp/alert_body.html", "w") as f:
            f.write(html_body)
        with open("/tmp/ntfy_body.txt", "w") as f:
            f.write(ntfy)

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"STALE: {len(stale)} source(s) flagged", file=sys.stderr)
        for s in stale:
            print(f"  {s['label']}: fetch={s['fetch_date'] or 'N/A'} "
                  f"data={s['data_date'] or 'MISSING'}", file=sys.stderr)

        sys.exit(1)

    print("\nAll sources OK.")


if __name__ == "__main__":
    run()
