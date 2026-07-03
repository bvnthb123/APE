# CHANGELOG

## v0.2.0 - Database Layer

### Added
- SQLAlchemy base and timestamp support.
- SQLite manager with transactions and health checks.
- Database tables for draws, features, predictions, engine scores, rules, experiments and run records.
- Repository classes for draws, predictions and rules.
- Automated database tests.

### Changed
- Version updated to v0.2.0.
- Startup now creates and verifies the local database.
- Added pytest dependency.

## v0.1.1 - Core Foundation

### Added
- Core package structure.
- Version metadata.
- Immutable settings system.
- Global constants.
- Custom exceptions.
- Rotating file logger.
- Application bootstrap.
- Compatibility config.py.
- Runnable main.py.
