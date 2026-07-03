"""Data-quality checks for stored event rows."""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from ape.database.models import Draw


def audit_draws(
    draws: Sequence[Draw],
    min_value: int,
    max_value: int,
    values_per_row: int,
) -> dict[str, Any]:
    invalid_rows: list[dict[str, Any]] = []
    weekday_mismatches: list[dict[str, Any]] = []
    missing_source_metadata = 0
    date_counter = Counter(draw.draw_date for draw in draws)

    for draw in draws:
        values = draw.numbers
        reasons: list[str] = []

        if len(values) != values_per_row:
            reasons.append("wrong_value_count")
        if len(set(values)) != len(values):
            reasons.append("duplicate_value")
        if values != sorted(values):
            reasons.append("values_not_sorted")
        if any(value < min_value or value > max_value for value in values):
            reasons.append("value_out_of_range")
        if draw.total_sum != sum(values):
            reasons.append("incorrect_total_sum")
        if draw.odd_count != sum(value % 2 for value in values):
            reasons.append("incorrect_odd_count")
        if draw.low_count != sum(value <= 22 for value in values):
            reasons.append("incorrect_low_count")

        if reasons:
            invalid_rows.append(
                {"date": draw.draw_date.isoformat(), "reasons": reasons}
            )

        if draw.weekday_index != draw.draw_date.weekday():
            weekday_mismatches.append(
                {
                    "date": draw.draw_date.isoformat(),
                    "stored_weekday_index": draw.weekday_index,
                    "actual_weekday_index": draw.draw_date.weekday(),
                }
            )

        if not draw.source_file or draw.source_row is None:
            missing_source_metadata += 1

    duplicate_dates = sorted(
        row_date.isoformat()
        for row_date, count in date_counter.items()
        if count > 1
    )

    long_date_gaps = sorted(
        (
            {
                "from": left.draw_date.isoformat(),
                "to": right.draw_date.isoformat(),
                "days": (right.draw_date - left.draw_date).days,
            }
            for left, right in zip(draws, draws[1:])
            if (right.draw_date - left.draw_date).days > 14
        ),
        key=lambda item: item["days"],
        reverse=True,
    )[:20]

    severe_count = len(invalid_rows) + len(duplicate_dates)
    warning_count = len(weekday_mismatches)
    denominator = max(len(draws), 1)
    penalty = (severe_count + warning_count * 0.25) / denominator * 100

    return {
        "quality_score": round(max(0.0, 100.0 - penalty), 2),
        "invalid_row_count": len(invalid_rows),
        "invalid_rows": invalid_rows[:50],
        "duplicate_date_count": len(duplicate_dates),
        "duplicate_dates": duplicate_dates[:50],
        "weekday_mismatch_count": len(weekday_mismatches),
        "weekday_mismatches": weekday_mismatches[:50],
        "missing_source_metadata_count": missing_source_metadata,
        "long_date_gaps_over_14_days": long_date_gaps,
    }
