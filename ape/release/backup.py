"""Backup and restore utilities for the local APE SQLite database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import sqlite3

from ape.core.exceptions import APEError
from ape.core.settings import SETTINGS


class BackupError(APEError):
    """Raised when backup or restore cannot be completed safely."""


@dataclass(slots=True, frozen=True)
class BackupResult:
    source: str
    target: str
    bytes_copied: int
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "target": self.target,
            "bytes_copied": self.bytes_copied,
            "created_at": self.created_at,
        }


class BackupManager:
    """Create timestamped database backups and restore selected backups."""

    def __init__(
        self,
        database_file: Path | str | None = None,
        backup_dir: Path | str | None = None,
    ) -> None:
        self.database_file = Path(database_file or SETTINGS.database_file)
        self.backup_dir = Path(backup_dir or SETTINGS.data_dir / "backups")

    def backup(self, output_file: Path | str | None = None) -> BackupResult:
        source = self.database_file.resolve()
        if not source.exists():
            raise BackupError(f"Không tìm thấy database để sao lưu: {source}")
        if not source.is_file():
            raise BackupError(f"Đường dẫn database không phải file: {source}")

        target = (
            Path(output_file).expanduser().resolve()
            if output_file
            else self.default_backup_path()
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.resolve() == source:
            raise BackupError("Không thể sao lưu đè lên chính file database đang dùng.")

        # Use SQLite's backup API so WAL-mode databases are copied consistently.
        with sqlite3.connect(source) as source_connection:
            with sqlite3.connect(target) as target_connection:
                source_connection.backup(target_connection)

        return BackupResult(
            source=str(source),
            target=str(target),
            bytes_copied=target.stat().st_size,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )

    def restore(self, backup_file: Path | str) -> BackupResult:
        source = Path(backup_file).expanduser().resolve()
        if not source.exists():
            raise BackupError(f"Không tìm thấy file sao lưu: {source}")
        if not source.is_file():
            raise BackupError(f"File sao lưu không hợp lệ: {source}")
        if source.suffix.lower() not in {".db", ".sqlite", ".backup"}:
            raise BackupError("Chỉ hỗ trợ khôi phục file .db, .sqlite hoặc .backup.")
        self._validate_sqlite_file(source)

        target = self.database_file.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        if source == target:
            raise BackupError("File sao lưu đang trùng với database hiện tại.")

        if target.exists():
            safety_file = self.default_backup_path(prefix="before_restore")
            safety_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, safety_file)

        shutil.copy2(source, target)
        return BackupResult(
            source=str(source),
            target=str(target),
            bytes_copied=target.stat().st_size,
            created_at=datetime.now().isoformat(timespec="seconds"),
        )

    def default_backup_path(self, prefix: str = "ape_backup") -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.backup_dir / f"{prefix}_{timestamp}.db"

    def list_backups(self) -> list[Path]:
        if not self.backup_dir.exists():
            return []
        allowed = {".db", ".sqlite", ".backup"}
        return sorted(
            [path for path in self.backup_dir.iterdir() if path.suffix.lower() in allowed],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    @staticmethod
    def _validate_sqlite_file(path: Path) -> None:
        try:
            with sqlite3.connect(path) as connection:
                connection.execute("PRAGMA schema_version").fetchone()
        except sqlite3.DatabaseError as exc:
            raise BackupError(f"File sao lưu không phải SQLite hợp lệ: {path}") from exc
