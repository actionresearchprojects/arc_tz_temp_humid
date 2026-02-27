# Updating house_5_tinytag

## Update the dashboard with new data

```bash
cd '/Users/archwrth/Downloads/ipynb_graphs/house_5_tinytag'
python build.py
git add index.html && git commit -m "update data" && git push
```

## Add/update data files
Drop new `.xlsx` files into `data/house5/` or `data/dauda/` before running `build.py`.

## Push any other changed files (e.g. build.py edits)
```bash
git add . && git commit -m "describe your change" && git push
```
