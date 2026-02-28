# Updating ecovillage_t_h

## Daily Automatic Updates

For automatic daily updates of Open-Meteo forecast/historical data:

### 1. Set up the daily update script

First, install required packages:
```bash
pip install pandas requests pytz
```

### 2. Test the update script
```bash
python daily_update.py
```

### 3. Set up a cron job (Linux/macOS) or scheduled task (Windows)

**On macOS/Linux:**
```bash
# Edit crontab
crontab -e

# Add this line to run daily at 2 AM (adjust timezone as needed)
0 2 * * * cd /path/to/arc_tz_temp_humid && /usr/bin/python3 daily_update.py >> /path/to/arc_tz_temp_humid/update.log 2>&1
```

**On Windows:**
Use Task Scheduler to run `daily_update.py` daily.

### 4. Manual update workflow (if needed)

**TinyTag loggers:** Drop new `.xlsx` files into `data/house5/` or `data/dauda/` (Schoolteacher's House).

**Omnisense sensors:** Follow `OMNISENSE_DATA_UPDATE_GUIDE.md` (one level up) to download and organise the Omnisense CSV. The same CSV file is shared with `omnisense_w_p_s`.

**Open-Meteo external temperature:** The daily script handles this automatically, but you can manually update by running:
```bash
python daily_update.py
```

### 5. Rebuild the dashboard
```bash
python build.py
```

### 6. Push to GitHub
> `data/` is gitignored — the data files are local only. Only `index.html` needs pushing.
```bash
git add index.html && git commit -m "update data" && git push
```

---

## Data folder structure

```
data/
  house5/                        ← TinyTag .xlsx files (House 5 loggers)
  dauda/                         ← TinyTag .xlsx files (Schoolteacher's House loggers)
  omnisense_270226.csv           ← Omnisense CSV (T&H sensors loaded for House 5)
  open-meteo-7.07S39.30E81m.csv  ← Open-Meteo external temperature (auto-updated)
  legacy/                        ← old Omnisense CSVs
```

---

## Push code changes (build.py edits etc.)
```bash
git add build.py CLAUDE.md daily_update.py && git commit -m "describe your change" && git push
```

---

## How the daily update works

1. **Fetches fresh forecast data** from Open-Meteo API (next 3 days)
2. **Updates the CSV file** with new forecast data
3. **Maintains historical data** in the same CSV (all past dates remain)
4. **Rebuilds the dashboard** automatically
5. **Optionally pushes to GitHub** (commented out by default)

The script intelligently merges new data with existing data, avoiding duplicates and filling gaps.
