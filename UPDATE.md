# Updating ecovillage_t_h

Open a terminal in this folder (see `SETUP.md` if unsure how), then:

## Full update workflow

### 1. Add/update data files

**TinyTag loggers:** Drop new `.xlsx` files into `data/house5/` or `data/dauda/` (Schoolteacher's House).

**Omnisense sensors:** Follow `OMNISENSE_DATA_UPDATE_GUIDE.md` (one level up) to download and organise the Omnisense CSV. The same CSV file is shared with `omnisense_w_p_s`.

**Open-Meteo external temperature:** Follow Step 1b in `OMNISENSE_DATA_UPDATE_GUIDE.md` to update the `open-meteo*.csv` if the stale data warning appears.

### 2. Rebuild the dashboard
```
python build.py
```

### 3. Push to GitHub
> `data/` is gitignored — the data files are local only. Only `index.html` needs pushing.
```
git add index.html && git commit -m "update data" && git push
```

---

## Data folder structure

```
data/
  house5/                        ← TinyTag .xlsx files (House 5 loggers)
  dauda/                         ← TinyTag .xlsx files (Schoolteacher's House loggers)
  omnisense_270226.csv           ← Omnisense CSV (T&H sensors loaded for House 5)
  open-meteo-7.07S39.30E81m.csv  ← Open-Meteo external temperature
  legacy/                        ← old Omnisense CSVs
```

---

## Push code changes (build.py edits etc.)
```
git add build.py CLAUDE.md && git commit -m "describe your change" && git push
```
