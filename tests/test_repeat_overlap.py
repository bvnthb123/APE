from datetime import date, timedelta

from ape.database.models import Draw
from ape.patterns import PatternMiner, RepeatOverlapSummary


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
        source_file="repeat.xlsx",
        source_row=day_offset + 2,
    )


def test_compute_repeat_overlap_for_lag_three():
    miner = PatternMiner()
    draws = [
        build_draw(0, [1, 2, 3, 4, 5, 6]),
        build_draw(1, [7, 8, 9, 10, 11, 12]),
        build_draw(2, [13, 14, 15, 16, 17, 18]),
        build_draw(3, [1, 20, 21, 22, 23, 24]),
        build_draw(4, [7, 8, 25, 26, 27, 28]),
        build_draw(5, [29, 30, 31, 32, 33, 34]),
    ]

    summary = miner.compute_repeat_overlap(draws, lag=3)

    assert isinstance(summary, RepeatOverlapSummary)
    assert summary.compared_rows == 3
    assert round(summary.average_overlap, 3) == 1.000
    assert summary.overlap_distribution == {1: 1, 2: 1, 0: 1}
    assert round(summary.one_plus_overlap_rate, 3) == 0.667
    assert round(summary.two_plus_overlap_rate, 3) == 0.333


def test_repeat_overlap_weight_boosts_latest_row_values_when_lag_repeats():
    miner = PatternMiner()
    draws = [
        build_draw(0, [1, 2, 3, 4, 5, 6]),
        build_draw(1, [10, 11, 12, 13, 14, 15]),
        build_draw(2, [20, 21, 22, 23, 24, 25]),
        build_draw(3, [1, 2, 30, 31, 32, 33]),
        build_draw(4, [10, 11, 34, 35, 36, 37]),
        build_draw(5, [20, 21, 38, 39, 40, 41]),
    ]
    overlap = miner.compute_repeat_overlap(draws, lag=3)
    latest_values = set(miner.values(draws[-1]))

    repeated_value_weight = miner.repeat_overlap_weight(20, latest_values, overlap)
    outside_value_weight = miner.repeat_overlap_weight(1, latest_values, overlap)

    assert repeated_value_weight > 1.0
    assert outside_value_weight == 1.0


def test_backtest_rows_include_repeat_overlap_learning_summary():
    miner = PatternMiner()
    draws = [
        build_draw(index, [1, 2, 3, 4, 5, 6])
        if index % 3 == 0
        else build_draw(index, [10, 11, 12, 13, 14, 15])
        for index in range(12)
    ]

    rows = miner.walk_forward_backtest(
        draws,
        lag=3,
        top_k=10,
        min_support=1,
        min_training_rows=6,
    ).to_rows()

    row_names = {name for name, _ in rows}
    assert "Học độ lặp N→N+lag" in row_names
    assert "Số trùng trung bình giữa N và N+lag" in row_names
    assert "Tỷ lệ trùng ít nhất 1 số" in row_names
