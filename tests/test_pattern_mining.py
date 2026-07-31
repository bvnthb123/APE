from datetime import date, timedelta

from ape.database.models import Draw
from ape.patterns.mining import PatternMiner


def build_draw(draw_date: date, values: list[int]) -> Draw:
    values = sorted(values)
    odd_count = sum(value % 2 for value in values)
    low_count = sum(value <= 22 for value in values)
    return Draw(
        draw_date=draw_date,
        weekday_index=draw_date.weekday(),
        weekday_name="Thứ Tư",
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
        source_file="pattern_test.xlsx",
        source_row=2,
    )


def build_pattern_draws(count: int = 90) -> list[Draw]:
    base = date(2026, 1, 1)
    draws: list[Draw] = []
    for index in range(count):
        if index % 4 == 0:
            values = [1, 2, 3, 4, 5, 6]
        elif index % 4 == 2:
            values = [7, 8, 9, 10, 11, 12]
        elif index % 4 == 1:
            values = [20, 21, 22, 23, 24, 25]
        else:
            values = [30, 31, 32, 33, 34, 35]
        draws.append(build_draw(base + timedelta(days=index), values))
    return draws


def test_pattern_miner_detects_lagged_rule():
    miner = PatternMiner()
    rules = miner.compute_rules(build_pattern_draws(), lag=2, min_support=3, top_n=20)

    assert any(
        rule.source_value == 1 and rule.target_value == 7 and rule.lift > 1
        for rule in rules
    )


def test_pattern_miner_current_signals_include_expected_value():
    miner = PatternMiner()
    draws = build_pattern_draws(89)
    signals = miner.current_signals(draws, lag=2, min_support=3, top_n=10)

    assert signals
    assert any(signal.value == 7 for signal in signals)


def test_pattern_miner_walk_forward_backtest_runs():
    miner = PatternMiner()
    summary = miner.walk_forward_backtest(
        build_pattern_draws(),
        lag=2,
        top_k=10,
        min_support=3,
        min_training_rows=20,
    )

    assert summary.tested_rows > 0
    assert summary.total_hits >= 0
    assert isinstance(summary.hit_distribution, dict)
