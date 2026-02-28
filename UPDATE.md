# Updating ecovillage_t_h

## Data Update Options

### Option 1: Manual Update (Recommended for now)
Run the update script manually when you want fresh Open-Meteo data:

```bash
# Install dependencies (if not already installed)
pip install pandas requests pytz

# Run the update
python daily_update.py

# Check the changes
git status

# Commit and push if everything looks good
git add index.html
git commit -m "update: fresh Open-Meteo data"
git push
```

### Option 2: GitHub Actions (Automatic, runs on GitHub's servers)
The `.github/workflows/daily-update.yml` file is already set up to run daily at 2 AM UTC. You can also trigger it manually from the GitHub repository's Actions tab.

**What GitHub Actions does:**
1. Fetches fresh Open-Meteo forecast data
2. Updates the `open-meteo*.csv` file
3. Commits and pushes the updated CSV to GitHub
4. **Does NOT rebuild the dashboard** (requires Excel files that are local only)

**After GitHub Actions runs:**
1. Pull the updated CSV to your local machine:
   ```bash
   git pull origin main
   ```
2. Run `python build.py` locally to rebuild the dashboard with fresh Open-Meteo data
3. Push the updated `index.html` to GitHub

**To test GitHub Actions:**
1. Go to your GitHub repository: `https://github.com/actionresearchprojects/arc_tz_temp_humid`
2. Click on the "Actions" tab
3. Select "Daily Data Update" workflow
4. Click "Run workflow" to manually trigger it

**Troubleshooting GitHub Actions failures:**
- Check the Actions log for error messages
- The workflow should complete in about 30-60 seconds
- If it fails, check that the CSV format is correct (3 header lines, proper column names)

**Note:** GitHub Actions has free minutes for public repositories. This approach doesn't require your computer to be on.

### Option 3: Local Automation (Only if computer is always on)
If you want to run updates locally, you can use cron (macOS/Linux) or Task Scheduler (Windows). However, this requires your computer to be running at the scheduled time.

---

## Important Notes

1. **Open-Meteo API Limits**: The free API has rate limits (10,000 calls/day). Our script makes 1 call per day, which is well within limits.
2. **No API Key Required**: Basic weather data doesn't require an API key.
3. **Data Persistence**: The CSV file is updated locally and pushed to GitHub. GitHub Pages serves the latest `index.html`.
4. **Manual Review**: Even with automation, it's good to occasionally check that the data looks correct.

### 4. Complete Workflow After GitHub Actions Update

When GitHub Actions has updated the Open-Meteo CSV:

```bash
# 1. Pull the updated CSV from GitHub
git pull origin main

# 2. Rebuild the dashboard locally (requires your Excel files)
python build.py

# 3. Push the updated dashboard
git add index.html
git commit -m "update: rebuild with fresh Open-Meteo data"
git push
```

**Important Note about Historical Data:**
- Open-Meteo's free API only provides about 4 months of historical data
- Data from 2023-03-15 must be maintained in your local CSV file
- The GitHub Actions workflow will only update forecast data and recent historical data
- Your local CSV file with full historical data should be committed to Git once
- After that, the daily updates will append new forecast data to it

**Tip:** To capture terminal output that scrolls off screen, use:
```bash
python daily_update.py 2>&1 | tee update.log
# Then view the log:
cat update.log
```

### 5. Manual update workflow (if needed)

**TinyTag loggers:** Drop new `.xlsx` files into `data/house5/` or `data/dauda/` (Schoolteacher's House).

**Omnisense sensors:** Follow `OMNISENSE_DATA_UPDATE_GUIDE.md` (one level up) to download and organise the Omnisense CSV. The same CSV file is shared with `omnisense_w_p_s`.

**Open-Meteo external temperature:** The daily script handles this automatically, but you can manually update by running:
```bash
python daily_update.py
```

### 6. Rebuild the dashboard
```bash
python build.py
```

### 7. Push to GitHub
> Most data files are gitignored — only `open-meteo*.csv` and `omnisense_*.csv` are tracked.
```bash
git add index.html data/open-meteo*.csv
git commit -m "update data"
git push
```

---

## Data folder structure

```
data/
  house5/                        ← TinyTag .xlsx files (House 5 loggers)
  dauda/                         ← TinyTag .xlsx files (Schoolteacher's House loggers)
  omnisense_270226.csv           ← Omnisense CSV (T&H sensors loaded for House 5)
  open-meteo-7.12S39.25E61m.csv  ← Open-Meteo external temperature (auto-updated)
  legacy/                        ← old Omnisense CSVs
```

---

## Push code changes (build.py edits etc.)
```bash
git add build.py CLAUDE.md daily_update.py && git commit -m "describe your change" && git push
```

---

## How the daily update works

1. **Maintains complete historical data** from 2023-03-15 (when House 5 monitoring began) up to yesterday
2. **Fetches fresh forecast data** from Open-Meteo API (next 7 days)
3. **Updates the CSV file** with any missing historical data and fresh forecast
4. **Rebuilds the dashboard** automatically
5. **Optionally pushes to GitHub** (commented out by default)

### Data Strategy:
- **Historical data (2023-03-15 to yesterday)**: Fetched once and maintained continuously
- **Forecast data (today to +7 days)**: Updated daily with fresh forecasts
- **Gap filling**: Automatically detects and fills any missing dates in the historical record
- **Duplicate prevention**: Removes old forecast data before adding new forecast

The script ensures your dashboard always shows:
- Complete historical temperature/humidity from when monitoring started
- The most up-to-date forecast for the coming week
