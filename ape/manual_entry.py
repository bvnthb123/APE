"""Manual draw entry and recalculation helpers.

This module accepts a newly known historical row, stores it in the database,
and recalculates the next Top historical signals using the current audit logic.
The output is descriptive historical signal research, not a guarantee of a
future result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re

from ape.database.database import DATABASE, DatabaseManager
from ape.database.models import Draw
from ape.database.repositories import DrawRepository
from ape.patterns import StrategyAuditor

WEEKDAY_NAMES = (
    "Thứ Hai",
    "Thứ Ba",
    "Thứ Tư",
    "Thứ Năm",
    "Thứ Sáu",
    "Thứ Bảy",
    "Chủ Nhật",
)


@dataclass(slots=True, frozen=True)
class ManualRecalculationResult:
    """Result returned after saving one manual row and recalculating signals."""

    draw_date: date
    numbers: tuple[int, ...]
    created: bool
    top_k: int
    signal_values: tuple[int, ...]
    audit_summary_rows: tuple[tuple[str, str], ...]

    @property
    def saved_label(self) -> str:
        return "Đã thêm kỳ mới" if self.created else "Đã cập nhật kỳ đã có"

    @property
    def numbers_label(self) -> str:
        return format_values(self.numbers)

    @property
    def signals_label(self) -> str:
        return format_values(self.signal_values) if self.signal_values else "Chưa đủ dữ liệu"



def format_values(values: tuple[int, ...] | list[int]) -> str:
    """Format values as a stable 2-digit string."""
    return " - ".join(f"{int(value):02d}" for value in values)



def parse_manual_numbers(raw_text: str) -> tuple[int, ...]:
    """Parse six values from free text.

    Accepts spaces, commas, semicolons, slashes, pipes, and hyphens as
    separators. Values must be unique integers from 1 to 45.
    """
    cleaned = re.sub(r"[,;|/\\-]+", " ", raw_text.strip())
    tokens = [token for token in cleaned.split() if token]
    if len(tokens) != 6:
        raise ValueError("Dãy số phải có đúng 6 số.")

    try:
        values = tuple(sorted(int(token) for token in tokens))
    except ValueError as exc:
        raise ValueError("Dãy số chỉ được chứa số nguyên.") from exc

    if any(value < 1 or value > 45 for value in values):
        raise ValueError("Mỗi số phải nằm trong khoảng 01 đến 45.")
    if len(set(values)) != 6:
        raise ValueError("6 số trong một kỳ không được trùng nhau.")
    return values



def build_manual_draw(draw_date: date, values: tuple[int, ...]) -> Draw:
    """Build a Draw ORM object from a manual date and six sorted values."""
    odd_count = sum(value % 2 for value in values)
    low_count = sum(value <= 22 for value in values)
    weekday_index = draw_date.weekday()
    return Draw(
        draw_date=draw_date,
        weekday_index=weekday_index,
        weekday_name=WEEKDAY_NAMES[weekday_index],
        n1=values[0],
        n2=values[1],
        n3=values[2],
        n4=values[3],
        n5=values[4],
        n6=values[5],
        total_sum=sum(values),
        odd_count=odd_count,
        even_count=6 - odd_count,
        low_count=low_count,
        high_count=6 - low_count,
        source_file="manual_entry",
        source_row=None,
    )



def save_manual_draw_and_recalculate(
    draw_date: date,
    raw_numbers: str,
    *,
    database: DatabaseManager | None = None,
    top_k: int = 7,
    lag_from: int = 1,
    lag_to: int = 3,
    support: int = 2,
    target_hits: int = 4,
    training_rows: int = 30,
    max_history_rows: int | None = 140,
) -> ManualRecalculationResult:
    """Save one manual historical row and recalculate Top historical signals."""
    if top_k != 7:
        raise ValueError("Luồng nhập thủ công đang cố định Top tín hiệu = 7.")

    db = database or DATABASE
    db.initialize()
    values = parse_manual_numbers(raw_numbers)
    draw = build_manual_draw(draw_date, values)

    with db.session() as session:
        _, created = DrawRepository(session).upsert(draw)

    with db.session() as session:
        draws = DrawRepository(session).list_chronological()

    auditor = StrategyAuditor()
    audit_result = auditor.audit(
        draws,
        lag_from=lag_from,
        lag_to=lag_to,
        top_k=top_k,
        base_min_support=support,
        min_training_rows=training_rows,
        target_hits=target_hits,
        strategy_mode="quick",
        max_history_rows=max_history_rows,
    )

    signals = (
        auditor.optimizer.select_candidates(
            draws,
            audit_result.best_evaluation.config,
            top_k=top_k,
        )
        if audit_result.best_evaluation is not None
        else []
    )

    return ManualRecalculationResult(
        draw_date=draw_date,
        numbers=values,
        created=created,
        top_k=top_k,
        signal_values=tuple(signal.value for signal in signals),
        audit_summary_rows=tuple(audit_result.to_rows()),
    )
