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
Create a `.github/workflows/daily-update.yml` file to run the update daily:

```yaml
name: Daily Data Update
on:
  schedule:
    - cron: '0 2 * * *'  # Run daily at 2 AM UTC
  workflow_dispatch:      # Allow manual trigger

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: pip install pandas requests pytz
        
      - name: Run daily update
        run: python daily_update.py
        
      - name: Commit and push if changed
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add index.html
          git diff --quiet && git diff --staged --quiet || git commit -m "chore: auto-update Open-Meteo data"
          git push
```

**Note:** GitHub Actions has free minutes for public repositories. This approach doesn't require your computer to be on.

### Option 3: Local Automation (Only if computer is always on)
If you want to run updates locally, you can use cron (macOS/Linux) or Task Scheduler (Windows). However, this requires your computer to be running at the scheduled time.

---

## Important Notes

1. **Open-Meteo API Limits**: The free API has rate limits (10,000 calls/day). Our script makes 1 call per day, which is well within limits.
2. **No API Key Required**: Basic weather data doesn't require an API key.
3. **Data Persistence**: The CSV file is updated locally and pushed to GitHub. GitHub Pages serves the latest `index.html`.
4. **Manual Review**: Even with automation, it's good to occasionally check that the data looks correct.

### 5. Manual update workflow (if needed)

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
