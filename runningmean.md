# Running Mean & Fallback Logic - Code Explainer

This document explains exactly how the adaptive comfort running mean is calculated and how the external data source fallback works, relating each part of the code to the underlying maths.

---

## 1. The EN16798-1 Formula

The running mean external temperature is defined in EN 16798-1 as:

```
θ_rm(n) = (1 - α) × θ_ed(n-1) + α × θ_rm(n-1)
```

Where:
- **θ_rm(n)** = running mean external temperature for day *n* (the value plotted on the x-axis of the adaptive comfort chart)
- **θ_ed(n-1)** = daily mean external temperature for *yesterday* (day n-1)
- **θ_rm(n-1)** = running mean from *yesterday*
- **α = 0.8** (the standard weighting constant)

In plain English: today's running mean = 20% of yesterday's actual external temperature + 80% of yesterday's running mean.

### Why people say "7-day" running mean

If you expand the recursion, the running mean is really a weighted sum of all past days:

```
θ_rm(n) = 0.2 × θ_ed(n-1)
         + 0.2 × 0.8   × θ_ed(n-2)     = 0.16
         + 0.2 × 0.8²  × θ_ed(n-3)     = 0.128
         + 0.2 × 0.8³  × θ_ed(n-4)     = 0.1024
         + 0.2 × 0.8⁴  × θ_ed(n-5)     = 0.08192
         + 0.2 × 0.8⁵  × θ_ed(n-6)     = 0.06554
         + 0.2 × 0.8⁶  × θ_ed(n-7)     = 0.05243
         + ...
```

The past 7 days account for ~79% of the total weight. Days further back contribute the remaining ~21%, with rapidly diminishing influence. That's why it's often called a "7-day" running mean - it's not a strict 7-day average, but an exponential weighting where ~7 days dominate.

---

## 2. The Code - Step by Step

The function lives in `build.py`:

```python
def compute_exponential_running_mean(df, primary_logger, fallback_loggers, alpha=0.8):
```

### Step 1: Get daily mean temperatures from the chosen source

```python
prim_df = df[df["logger_id"] == primary_logger]
prim_daily = prim_df["temperature"].resample("D").mean().dropna()
```

This filters the full dataset to only the chosen external source (e.g. `"861011"` for the TinyTag external sensor), then computes one temperature value per day by averaging all readings for that day. Days with no data become gaps.

### Step 2: Get daily means from the fallback source (always Open-Meteo)

```python
fb_df = df[df["logger_id"].isin(fallback_loggers)]
fb_daily = fb_df["temperature"].resample("D").mean().dropna()
```

Same thing, but for the Open-Meteo historical data. This runs regardless - the fallback data is always prepared.

### Step 3: Combine - chosen source takes priority, gaps filled by Open-Meteo

```python
all_days = prim_daily.index.union(fb_daily.index)
combined = pd.Series(index=all_days, dtype=float)

# Fill with fallback first, then overwrite with primary where available
combined.update(fb_daily)        # ← Open-Meteo fills all days it has
combined.update(prim_daily)      # ← Chosen source overwrites where it has data
```

This is the fallback mechanism. Think of it as:
1. Start with a blank calendar
2. Write Open-Meteo temperatures on every day Open-Meteo has data
3. Now go back and overwrite with TinyTag temperatures on every day TinyTag has data

Result: any day the chosen source has data → that data is used. Any day it doesn't → Open-Meteo fills the gap. If neither has data for a day, that day is dropped.

The code also tracks *which source was used for each day* (the `day_sources` series) so the dashboard can show this information on hover and in the legend.

### Step 4: Compute the running mean (the actual EN16798-1 formula)

```python
trm = [combined.iloc[0]]                                        # Seed: first day's temp
for i in range(1, len(combined)):
    trm.append((1 - alpha) * combined.iloc[i - 1] + alpha * trm[-1])
```

Line by line:
- `trm[0] = combined[0]` - the very first running mean value is seeded with the first available day's temperature (standard practice; EN16798-1 doesn't specify initialisation, and the seed's influence decays to near-zero within a few weeks)
- For every subsequent day: `trm[i] = 0.2 × combined[i-1] + 0.8 × trm[i-1]`

This is exactly: **θ_rm(n) = (1 - α) × θ_ed(n-1) + α × θ_rm(n-1)** ✓

Note: `combined[i-1]` is the *previous day's* temperature (θ_ed(n-1)), and `trm[-1]` = `trm[i-1]` is the *previous day's* running mean (θ_rm(n-1)). The formula uses yesterday's values to compute today's running mean, which is correct per EN16798-1.

### Step 5: Upsample to hourly and record source spans

```python
return trm_series.resample("h").ffill(), source_spans
```

The running mean is computed once per day, then forward-filled to hourly resolution so it can be matched against the hourly indoor temperature readings on the comfort scatter plot.

The `source_spans` list records consecutive date ranges showing which source was used, e.g.:
```json
[
  {"source": "861011",                          "from": "2024-01-15", "to": "2024-05-31"},
  {"source": "External Historical (Open-Meteo)", "from": "2024-06-01", "to": "2024-06-15"},
  {"source": "861011",                          "from": "2024-06-16", "to": "2024-12-31"}
]
```

---

## 3. How It's Called

In `build_dataset_json()`:

```python
source_id = logger_overrides.get(logger_id, {}).get("external_source", default_external_logger)
```

For each indoor logger, it looks up which external source the user chose in `config.html`. If none was chosen, it defaults to `"External Historical (Open-Meteo)"`.

```python
running_mean_cache[source_id] = compute_exponential_running_mean(df, source_id, fallback_loggers)
```

The `fallback_loggers` are always the Open-Meteo IDs:
```python
fallback_loggers = [l for l in cfg.get("external_sensors", []) if l in OPENMETEO_IDS]
```

So regardless of which primary source is chosen, **Open-Meteo always serves as the fallback**.

---

## 4. Summary of Guarantees

| Scenario | What happens |
|---|---|
| Chosen source has data for every day | 100% chosen source used |
| Chosen source has gaps on some days | Those days filled by Open-Meteo, rest uses chosen source |
| Chosen source has no data at all | 100% Open-Meteo used |
| Neither source has data for a day | That day is skipped (running mean continues from next available day) |

The running mean formula is applied identically regardless of which source provided each day's temperature. The blending is at the daily temperature level - the running mean doesn't "know" or care where each day's temperature came from.

---

## 5. What the User Sees

- **Hover tooltip**: shows all sources that contributed to the 7-day window for that specific data point (e.g. "TinyTag + Open-Meteo" when the window spans a source boundary)
- **Bottom-right annotation**: lists all sources used across the entire visible date range, with their date spans
- **PNG export legend**: each indoor logger shows which external source type(s) were used for its running mean
- **Config page**: notes that gaps in the chosen source are filled with Open-Meteo
