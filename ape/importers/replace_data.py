"""Replace all APE database data from a selected Excel workbook.

This module is for a controlled full refresh: back up the current SQLite file,
drop and recreate APE tables, then import a clean Excel workbook. It is safer
than manually deleting rows because it also clears stale predictions, scores,
rules and generated features that were based on the previous dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil

from ape.core.exceptions import ImporterError
from ape.core.settings import SETTINGS
from ape.database.database import DATABASE, DatabaseManager
from ape.importers.excel_importer import ExcelDrawImporter, ImportReport
from ape.importers.latest_excel import find_latest_excel_file

METHOD_MEMORY_FILES = (
    "learned_methods.json",
    "saved_strategy.json",
)


@dataclass(slots=True, frozen=True)
class ReplaceDataResult:
    """Result of a full database replacement from Excel."""

    source_path: Path
    backup_path: Path | None
    report: ImportReport
    archived_method_files: tuple[Path, ...]

    def to_rows(self) -> list[tuple[str, str]]:
        return [
            ("File nhập mới", str(self.source_path)),
            ("Backup database", str(self.backup_path) if self.backup_path else "Không có database cũ"),
            ("Sheet", self.report.sheet_name),
            ("Dòng đã đọc", str(self.report.rows_read)),
            ("Dòng hợp lệ", str(self.report.valid_rows)),
            ("Thêm mới", str(self.report.inserted_rows)),
            ("Cập nhật", str(self.report.updated_rows)),
            ("Bỏ qua", str(self.report.skipped_rows)),
            ("Dòng lỗi", str(self.report.invalid_rows)),
            ("Ngày đầu trong file", self.report.first_date.strftime("%d/%m/%Y") if self.report.first_date else "-"),
            ("Ngày cuối trong file", self.report.last_date.strftime("%d/%m/%Y") if self.report.last_date else "-"),
            (
                "File phương pháp cũ đã lưu riêng",
                ", ".join(str(path) for path in self.archived_method_files) if self.archived_method_files else "Không có",
            ),
        ]


def timestamp_label() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_database_file(database: DatabaseManager) -> Path | None:
    """Create a timestamped copy of the current SQLite database file."""
    source = database.database_file
    if not source.exists():
        return None
    backup = source.with_name(f"{source.stem}_before_replace_{timestamp_label()}{source.suffix}")
    shutil.copy2(source, backup)
    return backup


def archive_method_memory_files(*, data_dir: Path | None = None) -> tuple[Path, ...]:
    """Move stale learned-method files aside so a new dataset starts cleanly."""
    root = data_dir or SETTINGS.data_dir
    archived: list[Path] = []
    label = timestamp_label()
    for name in METHOD_MEMORY_FILES:
        source = root / name
        if not source.exists():
            continue
        target = root / f"{source.stem}_before_replace_{label}{source.suffix}"
        source.replace(target)
        archived.append(target)
    return tuple(archived)


def resolve_replacement_file(
    file_path: Path | str | None = None,
    *,
    folder: Path | str | None = None,
    latest: bool = False,
    recursive: bool = False,
) -> Path:
    """Resolve the workbook to use for replacement."""
    if file_path:
        path = Path(file_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ImporterError(f"Không tìm thấy file Excel: {path}")
        return path
    if latest:
        return find_latest_excel_file(folder, recursive=recursive)
    raise ImporterError(
        "Thiếu file Excel. Dùng --file <đường_dẫn> hoặc --latest để lấy file mới nhất."
    )


def replace_database_from_excel(
    *,
    file_path: Path | str | None = None,
    folder: Path | str | None = None,
    sheet_name: str | None = None,
    database: DatabaseManager | None = None,
    latest: bool = False,
    recursive: bool = False,
    clear_method_memory: bool = True,
) -> ReplaceDataResult:
    """Back up, reset all APE tables, then import a clean workbook."""
    db = database or DATABASE
    source_path = resolve_replacement_file(
        file_path,
        folder=folder,
        latest=latest,
        recursive=recursive,
    )

    db.initialize()
    db.dispose()
    backup_path = backup_database_file(db)

    # Re-open and rebuild from a clean schema.
    db.drop_all()
    db.initialize()

    archived_method_files = (
        archive_method_memory_files() if clear_method_memory else tuple()
    )

    importer = ExcelDrawImporter(db)
    report = importer.import_file(source_path, sheet_name=sheet_name, dry_run=False)
    return ReplaceDataResult(
        source_path=source_path,
        backup_path=backup_path,
        report=report,
        archived_method_files=archived_method_files,
    )
