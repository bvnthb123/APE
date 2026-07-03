# CHANGELOG

## v0.5.0 - Desktop GUI

### Added
- PySide6 desktop interface.
- Dashboard cards for row count, date range, database health and data quality.
- Historical data table.
- Statistics and audit table.
- Pair and triple summary panels.
- Excel file picker with validation and import confirmation.
- Open-data-folder and refresh actions.
- GUI smoke test.

### Changed
- Running `py main.py` now opens the desktop interface.
- Added `gui` and `status` commands.
- PySide6 requirement updated for Python 3.14 support.

## v0.4.0 - Statistics & Data Audit

### Added
- Descriptive analysis for values 01-45.
- Occurrence-distance analysis.
- Pair and triple co-occurrence counts.
- Structural and time-based summaries.
- Data-quality audit and automated tests.

## v0.3.0 - Excel Importer & Data Validation

### Added
- Excel sheet and column detection.
- Date, weekday and six-value normalization.
- Validation reports and SQLite upsert import.

## v0.2.0 - Database Layer

### Added
- SQLAlchemy base and SQLite manager.
- Seven core database tables.
- Repository classes and database tests.

## v0.1.1 - Core Foundation

### Added
- Project structure, settings and version metadata.
- Constants, custom exceptions and rotating logger.
- Application bootstrap and entry point.
