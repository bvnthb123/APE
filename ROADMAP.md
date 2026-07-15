# ROADMAP

## Sprint 1 - Foundation

### M1 - Config & Core Foundation
Status: Completed in v0.1.1

### M2 - Database Layer
Status: Completed in v0.2.0

### M3 - Excel Importer & Data Validation
Status: Completed in v0.3.0

### M4 - Statistics & Data Audit
Status: Completed in v0.4.0

## Sprint 2 - Desktop Application

### Sprint 2.1 - Desktop GUI
Status: Completed in v0.5.0

Delivered:
- PySide6 desktop window.
- Excel selection, validation and import.
- Overview dashboard.
- Historical data table.
- Statistics and data-audit workspace.
- Default GUI startup from `main.py`.

### Sprint 2.2 - Report Export & Charts
Status: Completed in v0.6.0

Delivered:
- Excel report export.
- Workbook sheets for overview, history, metrics, pairs, triples, audit and charts.
- GUI export button.
- Report folder shortcut.
- GUI charts tab.
- Frequency and current-gap charts.

### Sprint 2.3 - Windows Portable Packaging
Status: Completed in v0.7.0

Delivered:
- PyInstaller spec file.
- Packaging dependency file.
- One-command Windows build script.
- Source-run batch script.
- Portable-folder release output at `dist/APE/APE.exe`.
- Packaging guide.

### Sprint 2.4 - Interface Refinement
Status: Completed in v0.8.0

Delivered:
- Date-range filtering.
- Free-text search in historical data.
- Filtered-row dashboard card.
- Persistent GUI preferences.
- Saved last Excel/report folders and window size.
- Additional total-sum and odd-even charts.
- Filtering and preferences tests.

### Sprint 2.5 - Release Polish & Backup
Status: Completed in v0.9.0

Delivered:
- SVG application icon.
- Desktop shortcut helper.
- About dialog.
- Application folder shortcut.
- GUI database backup and restore.
- Safe SQLite backup API.
- Restore validation and pre-restore safety backup.
- Backup and restore tests.

### Sprint 2.6 - Release ZIP & QA
Status: Next

Planned scope:
- Build portable release zip.
- Add build verification checklist.
- Add user-facing quick-start guide.
- Test launch flow on a clean Windows folder.
- Add optional sample dataset workflow.

## Sprint 3 - Data Management
Status: Pending

Planned scope:
- Import history log.
- Duplicate import review.
- Dataset merge tools.
- Data dictionary and validation dashboard.
