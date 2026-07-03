"""Validation and normalization for historical draw rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import math
import re
import unicodedata
from typing import Any, Iterable

import pandas as pd

from ape.database.models import Draw

WEEKDAY_NAMES = {
    0: "Thứ Hai",
    1: "Thứ Ba",
    2: "Thứ Tư",
    3: "Thứ Năm",
    4: "Thứ Sáu",
    5: "Thứ Bảy",
    6: "Chủ Nhật",
}


@dataclass(slots=True, frozen=True)
class ValidationIssue:
    """One validation error or warning with source-row context."""

    row: int | None
    code: str
    message: str
    field: str | None = None
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "value": self.value,
        }


@dataclass(slots=True, frozen=True)
class NormalizedDraw:
    """A validated row ready to be stored in the database."""

    draw_date: date
    weekday_index: int
    weekday_name: str
    numbers: tuple[int, int, int, int, int, int]
    source_row: int | None = None

    def to_model(self, source_file: str | None = None) -> Draw:
        odd_count = sum(number % 2 for number in self.numbers)
        low_count = sum(number <= 22 for number in self.numbers)

        return Draw(
            draw_date=self.draw_date,
            weekday_index=self.weekday_index,
            weekday_name=self.weekday_name,
            n1=self.numbers[0],
            n2=self.numbers[1],
            n3=self.numbers[2],
            n4=self.numbers[3],
            n5=self.numbers[4],
            n6=self.numbers[5],
            total_sum=sum(self.numbers),
            odd_count=odd_count,
            even_count=6 - odd_count,
            low_count=low_count,
            high_count=6 - low_count,
            source_file=source_file,
            source_row=self.source_row,
        )


@dataclass(slots=True)
class RowValidationResult:
    """Validation result for one spreadsheet row."""

    draw: NormalizedDraw | None = None
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.draw is not None and not self.errors


class DrawValidator:
    """Normalize dates, weekday labels and six-number values."""

    def validate(
        self,
        date_value: Any,
        weekday_value: Any,
        numbers_value: Any,
        source_row: int | None = None,
    ) -> RowValidationResult:
        result = RowValidationResult()

        try:
            draw_date = self.parse_date(date_value)
        except ValueError as exc:
            result.errors.append(
                ValidationIssue(
                    source_row,
                    "invalid_date",
                    str(exc),
                    "date",
                    self.safe_value(date_value),
                )
            )
            return result

        try:
            numbers = self.parse_numbers(numbers_value)
        except ValueError as exc:
            result.errors.append(
                ValidationIssue(
                    source_row,
                    "invalid_numbers",
                    str(exc),
                    "numbers",
                    self.safe_value(numbers_value),
                )
            )
            return result

        expected_weekday = WEEKDAY_NAMES[draw_date.weekday()]
        if (
            not self.is_blank(weekday_value)
            and self.normalize_text(weekday_value)
            != self.normalize_text(expected_weekday)
        ):
            result.warnings.append(
                ValidationIssue(
                    source_row,
                    "weekday_mismatch",
                    (
                        f"Thứ trong file là '{weekday_value}' nhưng ngày "
                        f"{draw_date:%d/%m/%Y} là '{expected_weekday}'. "
                        "Hệ thống dùng thứ theo ngày."
                    ),
                    "weekday",
                    self.safe_value(weekday_value),
                )
            )

        result.draw = NormalizedDraw(
            draw_date=draw_date,
            weekday_index=draw_date.weekday(),
            weekday_name=expected_weekday,
            numbers=numbers,
            source_row=source_row,
        )
        return result

    @staticmethod
    def parse_date(value: Any) -> date:
        """Parse Excel, datetime or text date values."""
        if DrawValidator.is_blank(value):
            raise ValueError("Ngày quay bị trống.")

        if isinstance(value, pd.Timestamp):
            return value.date()
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(float(value)) or value <= 0:
                raise ValueError(f"Ngày Excel không hợp lệ: {value!r}.")
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()

        parsed = pd.to_datetime(
            str(value).strip(),
            dayfirst=True,
            errors="coerce",
        )
        if pd.isna(parsed):
            raise ValueError(f"Không đọc được ngày: {value!r}.")
        return parsed.date()

    @staticmethod
    def parse_numbers(value: Any) -> tuple[int, int, int, int, int, int]:
        """Parse and validate exactly six unique numbers from 01 to 45."""
        if DrawValidator.is_blank(value):
            raise ValueError("Bộ số bị trống.")

        if isinstance(value, str):
            raw_numbers = re.findall(r"\d+", value)
        elif isinstance(value, Iterable) and not isinstance(
            value,
            (bytes, bytearray, dict),
        ):
            raw_numbers = list(value)
        else:
            raise ValueError("Bộ số phải là chuỗi hoặc danh sách gồm 6 số.")

        try:
            numbers = [int(item) for item in raw_numbers]
        except (TypeError, ValueError) as exc:
            raise ValueError("Bộ số chứa giá trị không phải số nguyên.") from exc

        if len(numbers) != 6:
            raise ValueError(
                f"Cần đúng 6 số, nhưng nhận được {len(numbers)} số."
            )
        if len(set(numbers)) != 6:
            raise ValueError("Bộ số có giá trị trùng nhau.")

        out_of_range = [number for number in numbers if not 1 <= number <= 45]
        if out_of_range:
            raise ValueError(f"Số ngoài phạm vi 01-45: {out_of_range}.")

        ordered = tuple(sorted(numbers))
        return ordered  # type: ignore[return-value]

    @staticmethod
    def normalize_text(value: Any) -> str:
        text = unicodedata.normalize("NFD", str(value).strip().lower())
        text = "".join(
            char for char in text if unicodedata.category(char) != "Mn"
        )
        return re.sub(r"[^a-z0-9]+", "", text)

    @staticmethod
    def is_blank(value: Any) -> bool:
        if value is None:
            return True
        try:
            if bool(pd.isna(value)):
                return True
        except (TypeError, ValueError):
            pass
        return isinstance(value, str) and not value.strip()

    @staticmethod
    def safe_value(value: Any) -> Any:
        if isinstance(value, (date, datetime, pd.Timestamp)):
            return str(value)
        if isinstance(value, (list, tuple)):
            return [DrawValidator.safe_value(item) for item in value]
        return value
