import sqlite3

from ape.release.backup import BackupManager


def create_sqlite_file(path):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO sample (name) VALUES ('APE')")
        connection.commit()


def count_rows(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT COUNT(*) FROM sample").fetchone()[0]


def test_backup_manager_creates_restoreable_copy(tmp_path):
    database_file = tmp_path / "ape.db"
    backup_dir = tmp_path / "backups"
    create_sqlite_file(database_file)

    manager = BackupManager(database_file, backup_dir)
    result = manager.backup()

    backup_file = backup_dir / result.target.split("backups")[-1].strip("\\/")
    assert backup_file.exists()
    assert result.bytes_copied > 0
    assert count_rows(backup_file) == 1


def test_backup_manager_restores_database(tmp_path):
    database_file = tmp_path / "ape.db"
    backup_file = tmp_path / "restore.db"
    create_sqlite_file(database_file)
    create_sqlite_file(backup_file)

    with sqlite3.connect(database_file) as connection:
        connection.execute("DELETE FROM sample")
        connection.commit()
    assert count_rows(database_file) == 0

    result = BackupManager(database_file, tmp_path / "backups").restore(backup_file)

    assert result.bytes_copied > 0
    assert count_rows(database_file) == 1
