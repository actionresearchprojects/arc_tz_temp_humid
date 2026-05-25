"""
check_staleness.py – Data freshness checker for ARC monitoring.

Reads all fetched data files under data/ and evaluates whether each source
is current. Writes data/status.json on every run. When one or more sources
are stale also writes:
  /tmp/alert_subject.txt  – one-line email subject
  /tmp/alert_body.txt     – plain-text email body
  /tmp/ntfy_body.txt      – short push-notification message

In a GitHub Actions environment ($GITHUB_OUTPUT is set) writes:
  stale=true|false
  stale_count=N
  checked_date=YYYY-MM-DD

Exit 0 if all sources are within tolerance, exit 1 if any are stale.
"""

import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
NOW = datetime.now(timezone.utc)

# ── thresholds (hours) ─────────────────────────────────────────────────────────

THRESHOLDS_H = {
    "omnisense_fetch":  36,        # how recently did the action successfully fetch?
    "omnisense_data":   36,        # how recent is the newest sensor reading inside the CSV?
    "openmeteo_hist":   36,        # historical data goes to yesterday; 36h gives comfortable margin
    "openmeteo_fc":     36,        # checks fetch date (forecast end is always ~16 days out)
    "enso":             90 * 24,   # NOAA ONI is monthly with up to ~3 month publication lag
    "iod":              14 * 24,   # BoM IOD is weekly
    "mjo":               7 * 24,   # NOAA MJO ROMI is updated daily with a short lag
}

LABELS = {
    "omnisense_fetch": "Omnisense (action fetch date)",
    "omnisense_data":  "Omnisense (sensor data currency)",
    "openmeteo_hist":  "Open-Meteo historical",
    "openmeteo_fc":    "Open-Meteo forecast",
    "enso":            "ENSO ONI (NOAA PSL)",
    "iod":             "IOD DMI (Bureau of Meteorology)",
    "mjo":             "MJO ROMI (NOAA PSL)",
}

NOTES = {
    "enso": "Monthly index; NOAA publishes with up to ~3 month lag — alerts only if data is >90 days old",
    "iod":  "Weekly index from BoM; up to 14 days lag is normal",
    "mjo":  "Daily index; NOAA typically lags 2–5 days",
}

STATUS_PAGE = "https://actionresearchprojects.github.io/status.html"


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


def latest_iso_in_file(path: str, col: int = 0):
    """Return the latest ISO-style datetime found in a delimited file column."""
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

def entry(key: str, latest) -> dict:
    label = LABELS[key]
    threshold_h = THRESHOLDS_H[key]
    note = NOTES.get(key, "")
    if latest is None:
        return dict(key=key, label=label, status="unknown", latest=None,
                    age_hours=None, threshold_hours=threshold_h, note=note)
    age_h = (NOW - latest).total_seconds() / 3600
    return dict(
        key=key, label=label,
        status="ok" if age_h <= threshold_h else "stale",
        latest=latest.strftime("%Y-%m-%d %H:%M UTC"),
        age_hours=round(age_h, 1),
        threshold_hours=threshold_h,
        note=note,
    )


# ── main ───────────────────────────────────────────────────────────────────────

def run():
    sources = []

    # Omnisense
    omni_files = sorted(glob.glob(os.path.join(DATA, "omnisense", "omnisense_*.csv")))
    omni_latest = omni_files[-1] if omni_files else None
    sources.append(entry("omnisense_fetch", file_date_from_glob("omnisense/omnisense_*.csv")))
    sources.append(entry("omnisense_data",  latest_iso_in_file(omni_latest, col=2)))

    # Open-Meteo
    hist_files = sorted(glob.glob(os.path.join(DATA, "openmeteo", "historical_*.csv")))
    sources.append(entry("openmeteo_hist", latest_iso_in_file(hist_files[-1], col=0) if hist_files else None))
    sources.append(entry("openmeteo_fc",   file_date_from_glob("openmeteo/forecast_*.csv")))

    # Climate cycles
    sources.append(entry("enso", latest_oni_date(os.path.join(DATA, "cycles", "enso", "oni.csv"))))
    sources.append(entry("iod",  latest_yyyymmdd_in_file(os.path.join(DATA, "cycles", "iod", "iod_1.txt"))))
    sources.append(entry("mjo",  latest_ymd_cols(os.path.join(DATA, "cycles", "mjo", "romi.cpcolr.1x.txt"))))

    stale = [s for s in sources if s["status"] != "ok"]
    overall = "ok" if not stale else "stale"

    result = {
        "checked_at": NOW.strftime("%Y-%m-%d %H:%M UTC"),
        "overall": overall,
        "sources": sources,
    }

    # Always write status.json
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
        stale_bullets = "\n".join(
            f"  • {s['label']}: last data {s['latest'] or 'MISSING'}"
            + (f" ({s['age_hours']}h ago, limit {s['threshold_hours']}h)" if s['age_hours'] is not None else "")
            + (f"\n    ({s['note']})" if s['note'] else "")
            for s in stale
        )
        all_lines = "\n".join(
            f"  {'✓' if s['status'] == 'ok' else '✗'} {s['label']}: {s['latest'] or 'MISSING'}"
            for s in sources
        )

        subject = (
            f"⚠ ARC Dashboard: {len(stale)} data source(s) stale "
            f"({NOW.strftime('%Y-%m-%d %H:%M UTC')})"
        )
        body = f"""\
ARC Data Pipeline Alert
=======================
Checked: {NOW.strftime('%Y-%m-%d %H:%M UTC')}
Overall: STALE – {len(stale)} source(s) need attention

Stale sources:
{stale_bullets}

All sources:
{all_lines}

Status page: {STATUS_PAGE}

---
This alert was generated automatically by the ARC monitoring workflow.
To add or remove alert recipients, edit the ALERT_EMAILS secret in the
arc_tz_temp_humid GitHub repo settings.
"""
        ntfy = (
            f"ARC Dashboard: {len(stale)} source(s) stale\n"
            + "\n".join(f"{s['label']}: {s['age_hours']}h ago" for s in stale)
            + f"\n{STATUS_PAGE}"
        )

        with open("/tmp/alert_subject.txt", "w") as f:
            f.write(subject)
        with open("/tmp/alert_body.txt", "w") as f:
            f.write(body)
        with open("/tmp/ntfy_body.txt", "w") as f:
            f.write(ntfy)

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"STALE: {len(stale)} source(s) flagged", file=sys.stderr)
        for s in stale:
            print(f"  {s['label']}: {s['latest'] or 'MISSING'}", file=sys.stderr)

        sys.exit(1)

    print("\nAll sources OK.")


if __name__ == "__main__":
    run()
