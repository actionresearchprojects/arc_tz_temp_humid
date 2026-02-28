#!/usr/bin/env python3
"""
Daily update script for Open-Meteo temperature/humidity data.
Run this daily via cron to:
1. Fetch fresh forecast data from Open-Meteo API
2. Update the open-meteo CSV file
3. Archive yesterday's forecast as historical data
4. Rebuild the dashboard
5. Push to GitHub (optional)

Usage: python daily_update.py
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
from pathlib import Path
import json
import subprocess
import sys

# Configuration
DATA_FOLDER = Path("data")
TIMEZONE = pytz.timezone("Africa/Dar_es_Salaam")
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# Coordinates for the house location - using values from existing CSV
LATITUDE = -7.12  # From existing CSV filename
LONGITUDE = 39.25
ELEVATION = 61  # meters

def fetch_open_meteo_data(start_date=None, end_date=None):
    """Fetch temperature and humidity data from Open-Meteo API."""
    # If no dates specified, get next 7 days of forecast
    if start_date is None:
        start_date = datetime.now(TIMEZONE).date()
    if end_date is None:
        end_date = start_date + timedelta(days=7)
    
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": ["temperature_2m", "relative_humidity_2m"],
        "timezone": "Africa/Dar_es_Salaam",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    
    print(f"Fetching Open-Meteo data from {start_date} to {end_date}...")
    response = requests.get(OPEN_METEO_BASE_URL, params=params)
    
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code}")
        print(response.text)
        return None
    
    data = response.json()
    
    # Parse the data
    times = data["hourly"]["time"]
    temperatures = data["hourly"]["temperature_2m"]
    humidities = data["hourly"]["relative_humidity_2m"]
    
    records = []
    for time_str, temp, hum in zip(times, temperatures, humidities):
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        dt_tz = dt.astimezone(TIMEZONE)
        records.append({
            "datetime": dt_tz,
            "temperature": temp,
            "humidity": hum,
        })
    
    return pd.DataFrame(records)

def update_open_meteo_csv():
    """Update the Open-Meteo CSV file with fresh data."""
    # Find existing CSV file - use the most recent one
    csv_files = list(DATA_FOLDER.glob("open-meteo*.csv"))
    
    # Create a standard filename to avoid issues with spaces/parentheses
    standard_csv_path = DATA_FOLDER / f"open-meteo-{LATITUDE}S{LONGITUDE}E{ELEVATION}m.csv"
    
    # If we have existing files, read the data from them
    existing_df = pd.DataFrame()
    if csv_files:
        # Try to read data from all existing files and combine them
        all_dfs = []
        for csv_path in csv_files:
            print(f"  Reading data from: {csv_path.name}")
            try:
                # Try different reading strategies
                # First, check if it's in the format we write (with 3 header lines)
                try:
                    df = pd.read_csv(csv_path, skiprows=3)
                    # Check if it has the expected columns
                    if 'datetime' in df.columns:
                        df["datetime"] = pd.to_datetime(df["datetime"])
                        df = df.set_index("datetime")
                        all_dfs.append(df)
                        continue
                except:
                    pass
                
                # Try without skipping rows
                try:
                    df = pd.read_csv(csv_path)
                    # Look for datetime column (case insensitive)
                    datetime_col = None
                    for col in df.columns:
                        if 'datetime' in col.lower() or 'time' in col.lower():
                            datetime_col = col
                            break
                    
                    if datetime_col:
                        df = df.rename(columns={datetime_col: "datetime"})
                        df["datetime"] = pd.to_datetime(df["datetime"])
                        # Look for temperature and humidity columns
                        temp_col = None
                        hum_col = None
                        for col in df.columns:
                            if 'temperature' in col.lower() or 'temp' in col.lower():
                                temp_col = col
                            elif 'humidity' in col.lower() or 'hum' in col.lower():
                                hum_col = col
                        
                        if temp_col and hum_col:
                            df = df.rename(columns={temp_col: "temperature", hum_col: "humidity"})
                            df = df[["datetime", "temperature", "humidity"]]
                            df = df.set_index("datetime")
                            all_dfs.append(df)
                except Exception as e:
                    print(f"    Could not read {csv_path.name}: {e}")
                    
            except Exception as e:
                print(f"    Error processing {csv_path.name}: {e}")
        
        # Combine all dataframes
        if all_dfs:
            existing_df = pd.concat(all_dfs)
            existing_df = existing_df[~existing_df.index.duplicated(keep='last')]
            existing_df = existing_df.sort_index()
            print(f"  Combined {len(existing_df)} records from existing files")
    
    # Determine date range for new data
    today = datetime.now(TIMEZONE).date()
    
    if not existing_df.empty:
        # Get the last date in existing data
        last_date = existing_df.index.max().date()
        
        # If we already have data up to today, we might need to update
        # the forecast portion (last few days)
        if last_date >= today:
            # We already have today's data, fetch next 3 days for forecast
            start_date = today + timedelta(days=1)
            end_date = today + timedelta(days=3)
            new_data = fetch_open_meteo_data(start_date, end_date)
            
            if new_data is not None:
                # Remove any existing forecast data for these dates
                new_data = new_data.set_index("datetime")
                mask = existing_df.index.date >= start_date
                existing_df = existing_df[~mask]
                
                # Combine
                combined_df = pd.concat([existing_df, new_data])
                combined_df = combined_df.sort_index()
        else:
            # We're missing data between last_date+1 and today+3
            start_date = last_date + timedelta(days=1)
            end_date = today + timedelta(days=3)
            new_data = fetch_open_meteo_data(start_date, end_date)
            
            if new_data is not None:
                new_data = new_data.set_index("datetime")
                combined_df = pd.concat([existing_df, new_data])
                combined_df = combined_df.sort_index()
    else:
        # No existing data, fetch last 30 days + next 7 days
        start_date = today - timedelta(days=30)
        end_date = today + timedelta(days=7)
        new_data = fetch_open_meteo_data(start_date, end_date)
        
        if new_data is not None:
            combined_df = new_data.set_index("datetime")
    
    # Write updated CSV
    if 'combined_df' in locals() and not combined_df.empty:
        # Create header with metadata
        header_lines = [
            f"# Open-Meteo data for {LATITUDE},{LONGITUDE}",
            f"# Elevation: {ELEVATION}m",
            f"# Timezone: Africa/Dar_es_Salaam",
            "time,temperature_2m (°C),relative_humidity_2m (%)",
        ]
        
        # Reset index for CSV writing
        output_df = combined_df.reset_index()
        # Rename columns to match what build.py expects
        output_df = output_df.rename(columns={
            "datetime": "time",
            "temperature": "temperature_2m (°C)",
            "humidity": "relative_humidity_2m (%)",
        })
        
        # Write to standard filename
        csv_path = standard_csv_path
        
        # Write file
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(header_lines) + "\n")
            output_df.to_csv(f, index=False, date_format="%Y-%m-%d %H:%M")
        
        print(f"Updated {csv_path.name} with {len(combined_df)} records")
        print(f"Date range: {combined_df.index.min()} to {combined_df.index.max()}")
        
        # Archive old files by moving them to a backup folder
        backup_folder = DATA_FOLDER / "backup"
        backup_folder.mkdir(exist_ok=True)
        for old_csv in csv_files:
            if old_csv != csv_path:
                backup_path = backup_folder / old_csv.name
                old_csv.rename(backup_path)
                print(f"  Archived {old_csv.name} to backup/")
        
        return True
    
    return False
    
    # Determine date range for new data
    today = datetime.now(TIMEZONE).date()
    
    if not existing_df.empty:
        # Get the last date in existing data
        last_date = existing_df.index.max().date()
        
        # If we already have data up to today, we might need to update
        # the forecast portion (last few days)
        if last_date >= today:
            # We already have today's data, fetch next 3 days for forecast
            start_date = today + timedelta(days=1)
            end_date = today + timedelta(days=3)
            new_data = fetch_open_meteo_data(start_date, end_date)
            
            if new_data is not None:
                # Remove any existing forecast data for these dates
                new_data = new_data.set_index("datetime")
                mask = existing_df.index.date >= start_date
                existing_df = existing_df[~mask]
                
                # Combine
                combined_df = pd.concat([existing_df, new_data])
                combined_df = combined_df.sort_index()
        else:
            # We're missing data between last_date+1 and today+3
            start_date = last_date + timedelta(days=1)
            end_date = today + timedelta(days=3)
            new_data = fetch_open_meteo_data(start_date, end_date)
            
            if new_data is not None:
                new_data = new_data.set_index("datetime")
                combined_df = pd.concat([existing_df, new_data])
                combined_df = combined_df.sort_index()
    else:
        # No existing data, fetch last 30 days + next 7 days
        start_date = today - timedelta(days=30)
        end_date = today + timedelta(days=7)
        new_data = fetch_open_meteo_data(start_date, end_date)
        
        if new_data is not None:
            combined_df = new_data.set_index("datetime")
    
    # Write updated CSV
    if 'combined_df' in locals() and not combined_df.empty:
        # Create header with metadata
        header_lines = [
            f"# Open-Meteo data for {LATITUDE},{LONGITUDE}",
            f"# Elevation: {ELEVATION}m",
            f"# Timezone: Africa/Dar_es_Salaam",
            "datetime,temperature_2m (°C),relative_humidity_2m (%)",
        ]
        
        # Reset index for CSV writing
        output_df = combined_df.reset_index()
        output_df = output_df.rename(columns={
            "temperature": "temperature_2m (°C)",
            "humidity": "relative_humidity_2m (%)",
        })
        
        # Write file
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(header_lines) + "\n")
            output_df.to_csv(f, index=False, date_format="%Y-%m-%d %H:%M")
        
        print(f"Updated {csv_path.name} with {len(combined_df)} records")
        print(f"Date range: {combined_df.index.min()} to {combined_df.index.max()}")
        return True
    
    return False

def archive_historical_data():
    """Archive yesterday's forecast data as permanent historical data."""
    # This would depend on your historical data storage system
    # For now, we'll just ensure the CSV has the complete historical record
    print("Historical data archiving would be implemented here.")
    print("Currently, all data is kept in the main CSV file.")
    return True

def rebuild_dashboard():
    """Run build.py to regenerate index.html."""
    print("Rebuilding dashboard...")
    try:
        result = subprocess.run(
            [sys.executable, "build.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            print("Dashboard rebuilt successfully")
            print(result.stdout)
            return True
        else:
            print("Error rebuilding dashboard:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"Exception running build.py: {e}")
        return False

def git_commit_and_push():
    """Commit changes and push to GitHub."""
    print("Committing changes to Git...")
    
    try:
        # Add index.html
        subprocess.run(["git", "add", "index.html"], check=True)
        
        # Add any updated data files (optional - data/ is usually gitignored)
        # subprocess.run(["git", "add", "data/open-meteo*.csv"], check=True)
        
        # Commit
        commit_message = f"Daily update {datetime.now(TIMEZONE).strftime('%Y-%m-%d')}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        
        # Push
        subprocess.run(["git", "push"], check=True)
        
        print("Changes pushed to GitHub")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
        return False
    except Exception as e:
        print(f"Exception during Git operations: {e}")
        return False

def main():
    """Main update routine."""
    print(f"=== Daily Update {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')} ===")
    
    # Ensure data directory exists
    DATA_FOLDER.mkdir(exist_ok=True)
    
    # Step 1: Update Open-Meteo CSV
    if not update_open_meteo_csv():
        print("Failed to update Open-Meteo data")
        return 1
    
    # Step 2: Archive historical data (placeholder)
    archive_historical_data()
    
    # Step 3: Rebuild dashboard
    if not rebuild_dashboard():
        print("Failed to rebuild dashboard")
        return 1
    
    # Step 4: Push to GitHub (optional - comment out if not wanted)
    # if not git_commit_and_push():
    #     print("Git push failed (but dashboard was rebuilt)")
    #     return 1
    
    print("=== Daily update completed successfully ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
