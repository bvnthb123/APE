"""Excel importer for historical draw data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

import pandas as pd

from ape.core.exceptions import ImporterError
from ape.database.database import DATABASE, DatabaseManager
from ape.database.repositories import DrawRepository
from ape.utils.logger import logger
from ape.validation.draw_validator import DrawValidator, ValidationIssue


@dataclass(slots=True, frozen=True)
class ColumnMap:
    """Detected source columns."""

    date_column: str
    weekday_column: str | None
    numbers_column: str | None
    number_columns: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "date_column": self.date_column,
            "weekday_column": self.weekday_column,
            "numbers_column": self.numbers_column,
            "number_columns": list(self.number_columns),
        }


@dataclass(slots=True)
class ImportReport:
    """Detailed result of validation or import."""

    source_file: str
    sheet_name: str
    columns: dict[str, Any]
    dry_run: bool
    rows_read: int = 0
    valid_rows: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0
    skipped_rows: int = 0
    invalid_rows: int = 0
    duplicate_dates_in_file: int = 0
    first_date: date | None = None
    last_date: date | None = None
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.invalid_rows == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "source_file": self.source_file,
            "sheet_name": self.sheet_name,
            "columns": self.columns,
            "dry_run": self.dry_run,
            "rows_read": self.rows_read,
            "valid_rows": self.valid_rows,
            "inserted_rows": self.inserted_rows,
            "updated_rows": self.updated_rows,
            "skipped_rows": self.skipped_rows,
            "invalid_rows": self.invalid_rows,
            "duplicate_dates_in_file": self.duplicate_dates_in_file,
            "first_date": self.first_date.isoformat() if self.first_date else None,
            "last_date": self.last_date.isoformat() if self.last_date else None,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )


class ExcelDrawImporter:
    """Detect, validate and import historical rows from Excel."""

    DATE_ALIASES = {
        "ngay",
        "ngayquay",
        "date",
        "drawdate",
        "kyquay",
        "ngayxoso",
    }
    WEEKDAY_ALIASES = {
        "thu",
        "thutrongtuan",
        "weekday",
        "dayofweek",
    }
    NUMBERS_ALIASES = {
        "boso",
        "dayso",
        "ketqua",
        "numbers",
        "number",
        "winningnumbers",
        "result",
    }

    def __init__(
        self,
        database: DatabaseManager | None = None,
        validator: DrawValidator | None = None,
    ) -> None:
        self.database = database or DATABASE
        self.validator = validator or DrawValidator()

    def validate_file(
        self,
        file_path: Path | str,
        sheet_name: str | None = None,
    ) -> ImportReport:
        """Validate a workbook without writing to SQLite."""
        return self.import_file(
            file_path,
            sheet_name=sheet_name,
            dry_run=True,
        )

    def import_file(
        self,
        file_path: Path | str,
        sheet_name: str | None = None,
        dry_run: bool = False,
    ) -> ImportReport:
        """Validate a workbook and upsert every valid row."""
        path = Path(file_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ImporterError(f"Không tìm thấy file Excel: {path}")
        if path.suffix.lower() not in {".xlsx", ".xls"}:
            raise ImporterError(f"Định dạng không hỗ trợ: {path.suffix}")

        selected_sheet, frame, column_map = self._read_and_detect(
            path,
            sheet_name,
        )
        report = ImportReport(
            source_file=path.name,
            sheet_name=selected_sheet,
            columns=column_map.to_dict(),
            dry_run=dry_run,
        )

        valid_draws = []
        seen_dates: set[date] = set()

        for index, row in frame.iterrows():
            source_row = int(index) + 2
            if self._row_is_blank(row):
                continue

            report.rows_read += 1
            numbers_value = (
                row[column_map.numbers_column]
                if column_map.numbers_column
                else [row[column] for column in column_map.number_columns]
            )
            weekday_value = (
                row[column_map.weekday_column]
                if column_map.weekday_column
                else None
            )

            result = self.validator.validate(
                row[column_map.date_column],
                weekday_value,
                numbers_value,
                source_row,
            )
            report.errors.extend(result.errors)
            report.warnings.extend(result.warnings)

            if not result.is_valid or result.draw is None:
                report.invalid_rows += 1
                report.skipped_rows += 1
                continue

            if result.draw.draw_date in seen_dates:
                report.errors.append(
                    ValidationIssue(
                        source_row,
                        "duplicate_date_in_file",
                        (
                            f"Ngày {result.draw.draw_date:%d/%m/%Y} "
                            "xuất hiện nhiều lần trong cùng file."
                        ),
                        "date",
                        result.draw.draw_date.isoformat(),
                    )
                )
                report.invalid_rows += 1
                report.skipped_rows += 1
                report.duplicate_dates_in_file += 1
                continue

            seen_dates.add(result.draw.draw_date)
            valid_draws.append(result.draw)
            report.valid_rows += 1

        if valid_draws:
            report.first_date = min(item.draw_date for item in valid_draws)
            report.last_date = max(item.draw_date for item in valid_draws)

        if dry_run:
            return report

        self.database.initialize()
        try:
            with self.database.session() as session:
                repository = DrawRepository(session)
                for item in valid_draws:
                    _, created = repository.upsert(
                        item.to_model(path.name)
                    )
                    if created:
                        report.inserted_rows += 1
                    else:
                        report.updated_rows += 1
        except Exception as exc:
            logger.exception("Excel import failed for %s", path)
            raise ImporterError(f"Không thể import dữ liệu: {exc}") from exc

        logger.info(
            (
                "Imported %s: read=%s valid=%s inserted=%s "
                "updated=%s invalid=%s"
            ),
            path.name,
            report.rows_read,
            report.valid_rows,
            report.inserted_rows,
            report.updated_rows,
            report.invalid_rows,
        )
        return report

    def _read_and_detect(
        self,
        path: Path,
        requested_sheet: str | None,
    ) -> tuple[str, pd.DataFrame, ColumnMap]:
        try:
            workbook = pd.read_excel(
                path,
                sheet_name=requested_sheet if requested_sheet else None,
                dtype=object,
                engine="openpyxl",
            )
        except Exception as exc:
            raise ImporterError(f"Không đọc được file Excel: {exc}") from exc

        sheets = (
            {requested_sheet or "Sheet1": workbook}
            if isinstance(workbook, pd.DataFrame)
            else workbook
        )
        detection_errors = []

        for name, frame in sheets.items():
            frame = frame.dropna(how="all").reset_index(drop=True)
            if frame.empty:
                continue
            try:
                return (
                    str(name),
                    frame,
                    self.detect_columns(list(frame.columns)),
                )
            except ImporterError as exc:
                detection_errors.append(f"{name}: {exc}")

        details = (
            "; ".join(detection_errors)
            if detection_errors
            else "Không có sheet chứa dữ liệu."
        )
        raise ImporterError(
            f"Không tìm thấy cấu trúc cột phù hợp. {details}"
        )

    @classmethod
    def detect_columns(cls, columns: list[Any]) -> ColumnMap:
        """Detect common Vietnamese or English source-column names."""
        normalized = {
            str(column): cls.normalize_header(column)
            for column in columns
        }
        date_column = cls._find_alias(normalized, cls.DATE_ALIASES)
        weekday_column = cls._find_alias(
            normalized,
            cls.WEEKDAY_ALIASES,
        )
        numbers_column = cls._find_alias(
            normalized,
            cls.NUMBERS_ALIASES,
        )

        number_columns: list[tuple[int, str]] = []
        if numbers_column is None:
            for original, clean in normalized.items():
                match = re.fullmatch(
                    r"(?:n|so|number)([1-6])",
                    clean,
                )
                if match:
                    number_columns.append((int(match.group(1)), original))
            number_columns.sort()

        if date_column is None:
            raise ImporterError(
                f"Thiếu cột ngày. Các cột hiện có: {list(normalized)}"
            )
        if numbers_column is None and len(number_columns) != 6:
            raise ImporterError(
                "Thiếu cột 'Bộ Số' hoặc sáu cột số N1-N6."
            )

        return ColumnMap(
            date_column=date_column,
            weekday_column=weekday_column,
            numbers_column=numbers_column,
            number_columns=tuple(
                column for _, column in number_columns
            ),
        )

    @staticmethod
    def _find_alias(
        columns: dict[str, str],
        aliases: set[str],
    ) -> str | None:
        for original, normalized in columns.items():
            if normalized in aliases:
                return original
        return None

    @staticmethod
    def normalize_header(value: Any) -> str:
        text = unicodedata.normalize(
            "NFD",
            str(value).strip().lower(),
        )
        text = "".join(
            char for char in text if unicodedata.category(char) != "Mn"
        )
        return re.sub(r"[^a-z0-9]+", "", text)

    @staticmethod
    def _row_is_blank(row: pd.Series) -> bool:
        return bool(row.isna().all())
