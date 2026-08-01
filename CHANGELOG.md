# CHANGELOG

## v1.4.0 - Strategy Optimizer

### Added
- Strategy Optimizer for Pattern Mining.
- Walk-forward comparison of multiple historical calculation methods.
- Strategy toggles for rule-only, structure learning, repeat-overlap learning and combined scoring.
- Automatic support-variant search around the selected minimum support.
- Baseline comparison against random Top K selection.
- CMD command: `py main.py optimize --lag 3 --top 10`.
- Automated tests for strategy generation, evaluation and optimized signal output.

### Changed
- Version updated to v1.4.0.
- Pattern optimization now ranks strategies by historical rate of at least one matched value.

## v1.3.0 - Repeat Overlap Learning

### Added
- Repeat-overlap learning for `N -> N+lag`.
- Average overlap, modal overlap and overlap distribution metrics.
- Zero-overlap, one-plus-overlap and two-plus-overlap rates.
- Repeat-overlap scoring weight for values from the latest row when the selected lag historically repeats values.
- Backtest rows now show repeat-overlap learning details.
- Automated tests for repeat overlap and repeat-weight behavior.

### Changed
- Version updated to v1.3.0.
- Pattern Mining now uses value rules, structure learning and repeat-overlap learning together.

## v1.2.0 - Structural Pattern Learning

### Added
- Row-level structural profile for historical draws.
- Odd/even structure learning for Pattern Mining.
- Number-zone learning for `01-09`, `10-20`, `21-30`, `31-40`, `41-45`.
- Structure-adjusted signal scoring.
- Structure-balanced Top K selection.
- Backtest rows now show the reference parity and range-zone pattern.
- Automated tests for structural profile, range weighting and quota balancing.

### Changed
- Version updated to v1.2.0.
- Pattern Mining signal ranking now uses both value-to-value rules and learned row structure.

## v1.1.0 - Pattern Mining & Backtest

### Added
- Historical lagged pattern-mining engine.
- Value-to-value transition rules for `N -> N+lag`.
- Aggregated Top signal ranking from the latest known historical row.
- Walk-forward backtest summary for historical signal ranking.
- Pattern Mining tab in the desktop GUI.
- GUI controls for lag, minimum support and Top K signals.
- Automated tests for pattern rules, current signals and backtest execution.

### Changed
- Version updated to v1.1.0.
- About dialog now clarifies that Pattern Mining describes historical signals only.

## v1.0.0 - Portable Release & QA

### Added
- Portable release ZIP builder.
- `make_release_zip.bat` one-command release packaging script.
- User-facing quick-start guide.
- Release notes.
- Release QA checklist.
- Release ZIP smoke tests.

### Changed
- Version updated to v1.0.0.
- `.gitignore` now excludes generated release ZIP output.

## v0.9.0 - Release Polish & Backup

### Added
- SVG application icon.
- Desktop shortcut helper scripts.
- Database backup and restore manager.
- GUI buttons for backup, restore, application folder and About dialog.
- Safer SQLite backup using the SQLite backup API.
- Restore validation for SQLite backup files.
- Automated backup and restore tests.

### Changed
- Version updated to v0.9.0.
- PyInstaller spec now includes release assets.

## v0.8.0 - Interface Refinement

### Added
- Date-range filters for the historical data tab.
- Free-text search across date, weekday, values, sum and source file.
- Filtered-row count card on the overview dashboard.
- Persistent GUI preferences in `data/gui_preferences.json`.
- Saved last Excel folder, last report folder and window size.
- Total-sum chart for the latest 60 rows.
- Odd-even distribution chart.
- Automated tests for filtering and GUI preferences.

### Changed
- Recent rows now follow the active data filter.
- Version updated to v0.8.0.

## v0.7.0 - Windows Portable Packaging

### Added
- PyInstaller packaging dependency file.
- `APE.spec` portable-folder build configuration.
- `build_windows.bat` one-command Windows build script.
- `run_ape.bat` quick source-run script.
- `PACKAGING.md` Windows build guide.

### Changed
- Version updated to v0.7.0.
- `.gitignore` now excludes build outputs, `dist`, and packaging virtual environment.

## v0.6.0 - Report Export & Charts

### Added
- Excel report exporter.
- Export button in the desktop GUI.
- Report folder shortcut.
- Charts tab in the desktop GUI.
- Frequency bar chart for values 01-45.
- Current-gap line chart.
- Excel workbook sheets for overview, history, metrics, pairs, triples, audit and charts.

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
