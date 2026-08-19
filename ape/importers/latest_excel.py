"""Import the newest Excel workbook from a selected local folder.

This helper is for the common workflow where the user downloads or copies the
latest historical-data workbook into APE's data folder and wants APE to refresh
SQLite from that newest file. Existing draw dates are updated through the normal
Excel importer; new draw dates are inserted. It does not duplicate rows by date.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ape.core.exceptions import ImporterError
from ape.core.settings import SETTINGS
from ape.database.database import DATABASE, DatabaseManager
from ape.importers.excel_importer import ExcelDrawImporter, ImportReport

EXCEL_SUFFIXES = {".xlsx", ".xls"}


@dataclass(slots=True, frozen=True)
class LatestExcelImportResult:
    """Result of finding and importing the newest workbook."""

    source_path: Path
    report: ImportReport

    def to_rows(self) -> list[tuple[str, str]]:
        return [
            ("File đã chọn", str(self.source_path)),
            ("Sheet", self.report.sheet_name),
            ("Dòng đã đọc", str(self.report.rows_read)),
            ("Dòng hợp lệ", str(self.report.valid_rows)),
            ("Thêm mới", str(self.report.inserted_rows)),
            ("Cập nhật", str(self.report.updated_rows)),
            ("Bỏ qua", str(self.report.skipped_rows)),
            ("Dòng lỗi", str(self.report.invalid_rows)),
            ("Ngày đầu trong file", self.report.first_date.strftime("%d/%m/%Y") if self.report.first_date else "-"),
            ("Ngày cuối trong file", self.report.last_date.strftime("%d/%m/%Y") if self.report.last_date else "-"),
        ]


def is_candidate_excel(path: Path) -> bool:
    """Return True when a path should be considered for latest-file import."""
    name = path.name
    return (
        path.is_file()
        and path.suffix.lower() in EXCEL_SUFFIXES
        and not name.startswith("~$")
        and not name.startswith(".")
    )


def candidate_excel_files(folder: Path, *, recursive: bool = False) -> Iterable[Path]:
    """Yield importable workbook candidates from a folder."""
    pattern = "**/*" if recursive else "*"
    for path in folder.glob(pattern):
        if is_candidate_excel(path):
            yield path


def find_latest_excel_file(
    folder: Path | str | None = None,
    *,
    recursive: bool = False,
) -> Path:
    """Find the newest Excel workbook in a folder by modified time."""
    root = Path(folder or SETTINGS.data_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ImporterError(f"Không tìm thấy thư mục dữ liệu: {root}")

    candidates = list(candidate_excel_files(root, recursive=recursive))
    if not candidates:
        raise ImporterError(
            f"Không tìm thấy file Excel .xlsx/.xls trong thư mục: {root}"
        )

    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name.lower()))


def import_latest_excel_file(
    *,
    folder: Path | str | None = None,
    sheet_name: str | None = None,
    database: DatabaseManager | None = None,
    dry_run: bool = False,
    recursive: bool = False,
) -> LatestExcelImportResult:
    """Import the newest workbook from a folder using the normal Excel importer."""
    latest_path = find_latest_excel_file(folder, recursive=recursive)
    importer = ExcelDrawImporter(database or DATABASE)
    report = importer.import_file(
        latest_path,
        sheet_name=sheet_name,
        dry_run=dry_run,
    )
    return LatestExcelImportResult(source_path=latest_path, report=report)
