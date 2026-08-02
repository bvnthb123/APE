from datetime import date, timedelta

from ape.database.models import Draw
from ape.patterns import StrategyOptimizer


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
        source_file="target_hit.xlsx",
        source_row=day_offset + 2,
    )


def test_random_target_hit_rate_is_lower_for_four_hits_than_one_hit():
    optimizer = StrategyOptimizer()

    one_plus = optimizer.random_hit_rate_at(top_k=10, target_hits=1)
    four_plus = optimizer.random_hit_rate_at(top_k=10, target_hits=4)

    assert 0 < four_plus < one_plus < 1


def test_optimizer_can_rank_by_four_plus_hits_on_repeating_pattern():
    optimizer = StrategyOptimizer()
    draws = [build_draw(index, [1, 2, 3, 4, 5, 6]) for index in range(24)]

    result = optimizer.optimize(
        draws,
        lag=1,
        top_k=10,
        base_min_support=1,
        min_training_rows=6,
        target_hits=4,
    )

    assert result.best is not None
    assert result.target_hits == 4
    assert result.best.target_hit_rate == 1.0
    assert result.best.max_hits == 6


def test_optimization_rows_include_target_hit_metrics():
    optimizer = StrategyOptimizer()
    draws = [build_draw(index, [1, 2, 3, 4, 5, 6]) for index in range(18)]

    result = optimizer.optimize(
        draws,
        lag=1,
        top_k=10,
        base_min_support=1,
        min_training_rows=6,
        target_hits=4,
    )
    row_names = {name for name, _ in result.to_rows()}

    assert "Mục tiêu tối ưu" in row_names
    assert "Tỷ lệ trùng ít nhất 4 số" in row_names
    assert "Baseline random - tỷ lệ ≥4 số" in row_names
