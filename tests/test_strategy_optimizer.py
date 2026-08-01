from datetime import date, timedelta

from ape.database.models import Draw
from ape.patterns import StrategyConfig, StrategyOptimizer


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
        source_file="optimizer.xlsx",
        source_row=day_offset + 2,
    )


def build_patterned_draws(count: int = 90) -> list[Draw]:
    draws: list[Draw] = []
    for index in range(count):
        base = 1 + (index % 20)
        values = [base, base + 1, base + 2, 30, 31, 32]
        values = [((value - 1) % 45) + 1 for value in values]
        draws.append(build_draw(index, values))
    return draws


def test_optimizer_generates_multiple_true_false_strategy_choices():
    optimizer = StrategyOptimizer()
    configs = optimizer.generate_configs(lag=3, base_min_support=3)

    assert len(configs) >= 12
    assert any(not item.use_structure and not item.use_repeat_overlap for item in configs)
    assert any(item.use_structure and not item.use_repeat_overlap for item in configs)
    assert any(not item.use_structure and item.use_repeat_overlap for item in configs)
    assert any(item.use_structure and item.use_repeat_overlap for item in configs)


def test_optimizer_evaluates_one_plus_hit_rate():
    optimizer = StrategyOptimizer()
    config = StrategyConfig(
        name="Rule + cấu trúc + độ lặp",
        lag=3,
        min_support=1,
        use_structure=True,
        use_repeat_overlap=True,
    )

    evaluation = optimizer.evaluate(
        build_patterned_draws(),
        config,
        top_k=10,
        min_training_rows=30,
    )

    assert evaluation.tested_rows > 0
    assert 0 <= evaluation.one_plus_hit_rate <= 1
    assert 0 <= evaluation.zero_hit_rate <= 1
    assert sum(evaluation.hit_distribution.values()) == evaluation.tested_rows


def test_optimizer_selects_best_strategy_and_outputs_latest_signals():
    optimizer = StrategyOptimizer()
    draws = build_patterned_draws()

    result = optimizer.optimize(
        draws,
        lag=3,
        top_k=10,
        base_min_support=2,
        min_training_rows=30,
    )

    assert result.best is not None
    assert result.random_one_plus_hit_rate > 0
    assert result.random_average_hits > 0
    assert len(result.latest_signals(optimizer.miner, draws)) <= 10

    row_names = {name for name, _ in result.to_rows()}
    assert "Phương án tốt nhất" in row_names
    assert "Tỷ lệ trùng ít nhất 1 số" in row_names
    assert "Chênh lệch ≥1 số so với random" in row_names
