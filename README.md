# APE v0.3.0

Adaptive Prediction Engine.

Completed modules:
- M1 Core Foundation
- M2 Database Layer
- M3 Excel Importer and Data Validation

Commands:

```text
py main.py
py main.py validate FILE.xlsx
py main.py import FILE.xlsx
py -m pytest -q
```

The importer detects date, weekday and number columns, validates six unique values in the configured range, reports invalid rows and upserts valid records into `data/ape.db`.

Next module: M4 Statistics and Data Audit.
