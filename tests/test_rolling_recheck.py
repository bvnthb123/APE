from datetime import date, timedelta

from ape.database.models import Draw
from ape.patterns import StrategyRechecker


def build_draw(day_offset: int, values: list[int]) -> Draw:
    values = sorted(values)
    odd_count = sum(value % 2 for value in values)
    low_count = sum(value <= 22 for value in values)
    return Draw(
        draw_date=date(2026, 1, 1) + timedelta(days=day_offset),
        weekday_index=0,
        weekday_name="Thứ Hai",
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
        source_file="recheck.xlsx",
        source_row=day_offset + 2,
    )


def test_recheck_selects_strategy_inside_date_range():
    pattern = (
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 7, 8],
        [9, 10, 11, 12, 13, 14],
    )
    draws = [build_draw(index, pattern[index % len(pattern)]) for index in range(90)]

    result = StrategyRechecker().recheck(
        draws,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        lag_from=1,
        lag_to=3,
        top_k=7,
        base_min_support=1,
        min_training_rows=20,
        target_hits=1,
        strategy_mode="quick",
    )

    assert result.best is not None
    assert result.best.tested_rows > 0
    assert result.latest_signal_values
    assert "Top tín hiệu tham chiếu hiện tại" in dict(result.to_rows())


def test_recheck_detail_rows_include_comparison_fields():
    draws = [build_draw(index, [1, 2, 3, 4, 5, 6]) for index in range(90)]

    result = StrategyRechecker().recheck(
        draws,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        lag_from=1,
        lag_to=1,
        top_k=7,
        base_min_support=1,
        min_training_rows=20,
        target_hits=1,
    )

    detail = result.detail_rows(limit=3)

    assert len(detail) == 3
    assert all(len(row) == 9 for row in detail)
    assert all(row[6] for row in detail)
    assert all(row[7] for row in detail)
