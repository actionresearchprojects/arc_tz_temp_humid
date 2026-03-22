#!/usr/bin/env python3
"""Fetch climate oscillation cycle data (ENSO ONI, IOD DMI, MJO ROMI).

Downloads latest data files from NOAA/BoM into data/cycles/ subfolders.
Designed to be run weekly via GitHub Actions or manually.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
import requests

CYCLES_DIR = Path("data/cycles")

SOURCES = {
    "enso": {
        "url": "https://psl.noaa.gov/data/correlation/oni.csv",
        "dest": CYCLES_DIR / "enso" / "oni.csv",
    },
    "iod": {
        "url": "https://www.bom.gov.au/clim_data/IDCK000072/iod_1.txt",
        "dest": CYCLES_DIR / "iod" / "iod_1.txt",
    },
    "mjo": {
        "url": "https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt",
        "dest": CYCLES_DIR / "mjo" / "romi.cpcolr.1x.txt",
    },
}


def fetch_all():
    ok = True
    for name, src in SOURCES.items():
        print(f"Fetching {name} from {src['url']} ...")
        try:
            r = requests.get(src["url"], timeout=60, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ARC-EcovillageBot/1.0)"
            })
            r.raise_for_status()
            src["dest"].parent.mkdir(parents=True, exist_ok=True)
            src["dest"].write_text(r.text, encoding="utf-8")
            print(f"  → saved {src['dest']} ({len(r.text)} bytes)")
        except Exception as e:
            print(f"  ✗ Failed to fetch {name}: {e}", file=sys.stderr)
            ok = False

    # Write a timestamp file so build.py knows when cycles were last fetched
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    ts_file = CYCLES_DIR / f"cycles_fetched_{ts}.txt"
    # Remove old timestamp files
    for old in CYCLES_DIR.glob("cycles_fetched_*.txt"):
        old.unlink()
    ts_file.write_text(f"Fetched at {ts} UTC\n")
    print(f"Timestamp: {ts_file.name}")

    return ok


if __name__ == "__main__":
    success = fetch_all()
    sys.exit(0 if success else 1)
