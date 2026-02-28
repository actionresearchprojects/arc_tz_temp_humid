#!/usr/bin/env python3
"""
Simple script to update Open-Meteo forecast data.
Appends fresh forecast (next 7 days) to existing CSV file.
Run manually when you want to update the forecast.
"""

import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
from pathlib import Path

# Configuration
DATA_FOLDER = Path("data")
TIMEZONE = pytz.timezone("Africa/Dar_es_Salaam")
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# Coordinates for the house location
LATITUDE = -7.12
LONGITUDE = 39.25
ELEVATION = 61  # meters

def fetch_forecast():
    """Fetch 7-day forecast from Open-Meteo API."""
    today = datetime.now(TIMEZONE).date()
    forecast_end = today + timedelta(days=7)
    
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": ["temperature_2m", "relative_humidity_2m"],
        "timezone": "Africa/Dar_es_Salaam",
        "start_date": today.isoformat(),
        "end_date": forecast_end.isoformat(),
    }
    
    print(f"Fetching Open-Meteo forecast from {today} to {forecast_end}...")
    
    try:
        response = requests.get(OPEN_METEO_BASE_URL, params=params, timeout=30)
        
        if response.status_code != 200:
            print(f"Error fetching data: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return None
        
        data = response.json()
        
        if "hourly" not in data:
            print("Unexpected response format: no 'hourly' key")
            return None
        
        times = data["hourly"].get("time", [])
        temperatures = data["hourly"].get("temperature_2m", [])
        humidities = data["hourly"].get("relative_humidity_2m", [])
        
        if not times:
            print("No time data returned")
            return None
        
        records = []
        for time_str, temp, hum in zip(times, temperatures, humidities):
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                dt_tz = dt.astimezone(TIMEZONE)
                records.append({
                    "datetime": dt_tz,
                    "temperature": temp,
                    "humidity": hum,
                })
            except Exception as e:
                print(f"Warning: Could not parse time {time_str}: {e}")
                continue
        
        if not records:
            print("No valid records parsed")
            return None
        
        df = pd.DataFrame(records)
        print(f"Retrieved {len(df)} forecast records")
        return df
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def update_csv():
    """Update Open-Meteo CSV with fresh forecast data."""
    # Find existing CSV file
    csv_files = list(DATA_FOLDER.glob("open-meteo*.csv"))
    
    if not csv_files:
        print("No existing Open-Meteo CSV found. Creating new file...")
        # Create standard filename
        lat_str = f"{abs(LATITUDE):.2f}S"
        lon_str = f"{LONGITUDE:.2f}E"
        csv_path = DATA_FOLDER / f"open-meteo-{lat_str}{lon_str}{ELEVATION}m.csv"
        
        # Fetch forecast data
        forecast_df = fetch_forecast()
        if forecast_df is None or forecast_df.empty:
            print("Failed to fetch forecast data")
            return False
        
        # Create header
        header_lines = [
            f"# Open-Meteo data for {LATITUDE},{LONGITUDE}",
            f"# Elevation: {ELEVATION}m",
            f"# Timezone: Africa/Dar_es_Salaam",
            "time,temperature_2m (°C),relative_humidity_2m (%)",
        ]
        
        # Prepare output
        output_df = forecast_df.rename(columns={
            "datetime": "time",
            "temperature": "temperature_2m (°C)",
            "humidity": "relative_humidity_2m (%)",
        })
        output_df = output_df[["time", "temperature_2m (°C)", "relative_humidity_2m (%)"]]
        
        # Write file
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(header_lines) + "\n")
            output_df.to_csv(f, index=False, date_format="%Y-%m-%d %H:%M")
        
        print(f"Created new CSV: {csv_path.name} with {len(forecast_df)} records")
        return True
    
    # Use the most recent CSV
    csv_path = csv_files[0]
    print(f"Updating existing CSV: {csv_path.name}")
    
    try:
        # Read existing data
        existing_df = pd.read_csv(csv_path, skiprows=3)
        existing_df = existing_df.rename(columns={'time': 'datetime'})
        existing_df["datetime"] = pd.to_datetime(existing_df["datetime"])
        existing_df = existing_df.set_index("datetime")
        
        print(f"Existing data: {existing_df.index.min().date()} to {existing_df.index.max().date()}")
        print(f"Total records: {len(existing_df)}")
        
    except Exception as e:
        print(f"Error reading existing CSV: {e}")
        return False
    
    # Fetch new forecast
    forecast_df = fetch_forecast()
    if forecast_df is None or forecast_df.empty:
        print("Failed to fetch forecast data")
        return False
    
    forecast_df = forecast_df.set_index("datetime")
    
    # Remove any existing forecast data (today onward) to avoid duplicates
    today = datetime.now(TIMEZONE).date()
    mask = existing_df.index.date >= today
    existing_df = existing_df[~mask]
    
    # Combine existing historical data with new forecast
    combined_df = pd.concat([existing_df, forecast_df])
    combined_df = combined_df.sort_index()
    
    # Prepare for writing
    output_df = combined_df.reset_index()
    output_df = output_df.rename(columns={
        "datetime": "time",
        "temperature": "temperature_2m (°C)",
        "humidity": "relative_humidity_2m (%)",
    })
    output_df = output_df[["time", "temperature_2m (°C)", "relative_humidity_2m (%)"]]
    
    # Write back to same file
    header_lines = [
        f"# Open-Meteo data for {LATITUDE},{LONGITUDE}",
        f"# Elevation: {ELEVATION}m",
        f"# Timezone: Africa/Dar_es_Salaam",
        "time,temperature_2m (°C),relative_humidity_2m (%)",
    ]
    
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(header_lines) + "\n")
        output_df.to_csv(f, index=False, date_format="%Y-%m-%d %H:%M")
    
    print(f"Updated {csv_path.name} with {len(combined_df)} total records")
    print(f"Date range: {combined_df.index.min()} to {combined_df.index.max()}")
    
    # Show what was added
    new_records = len(forecast_df)
    print(f"Added {new_records} new forecast records")
    
    return True

def main():
    """Main function."""
    print(f"=== Open-Meteo Forecast Update {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')} ===")
    
    # Ensure data directory exists
    DATA_FOLDER.mkdir(exist_ok=True)
    
    # Update CSV
    if update_csv():
        print("\n=== Update completed successfully ===")
        return 0
    else:
        print("\n=== Update failed ===")
        return 1

if __name__ == "__main__":
    sys.exit(main())
