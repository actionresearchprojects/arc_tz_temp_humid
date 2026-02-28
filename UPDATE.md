# Updating ecovillage_t_h

## Manual Update Process

Run the update script manually when you want fresh Open-Meteo forecast data:

```bash
# Install dependencies (if not already installed)
pip install pandas requests pytz

# Update Open-Meteo forecast data
python daily_update.py

# Rebuild the dashboard with updated data
python build.py

# Commit and push the updated dashboard
git add index.html
git commit -m "update: fresh Open-Meteo forecast"
git push
```

## Data Update Workflow

### 1. Update Open-Meteo forecast
The `daily_update.py` script:
- Fetches 7-day forecast from Open-Meteo API
- Appends it to your existing `open-meteo*.csv` file
- Removes any old forecast data to avoid duplicates
- **Does NOT fetch historical data** (maintain your historical CSV locally)

### 2. Rebuild the dashboard
```bash
python build.py
```
This reads all data sources (Excel files, Omnisense CSV, Open-Meteo CSV) and generates a new `index.html`.

### 3. Push to GitHub
```bash
git add index.html
git commit -m "update data"
git push
```

## Data Sources

- **TinyTag .xlsx** – `data/house5/` (14 loggers) and `data/dauda/` (3 loggers)
- **Omnisense CSV** – `data/omnisense_*.csv` (10 T&H sensors)
- **Open-Meteo CSV** – `data/open-meteo*.csv` (external temperature)

## Important Notes

1. **Historical Open-Meteo data**: The free API only provides ~4 months of historical data. Maintain your complete historical CSV file locally (from 2023-03-15 onward).

2. **Forecast updates**: The script only fetches forecast data (next 7 days) and appends it to your existing CSV.

3. **Manual process**: Run updates when convenient. No automation is configured.

## Data Folder Structure

```
data/
  house5/                        # TinyTag .xlsx files (House 5 loggers)
  dauda/                         # TinyTag .xlsx files (Schoolteacher's House)
  omnisense_270226.csv           # Omnisense CSV (T&H sensors)
  open-meteo-7.12S39.25E61m.csv  # Open-Meteo external temperature
  legacy/                        # Old Omnisense CSVs (optional)
```

## Troubleshooting

If the update fails:
- Check your internet connection
- Verify Open-Meteo API is accessible
- Ensure your existing CSV file is in the correct format (3 header lines)

To see detailed output:
```bash
python daily_update.py 2>&1 | tee update.log
```
