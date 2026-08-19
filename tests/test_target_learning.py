from datetime import date, timedelta

from ape.database.models import Draw
from ape.patterns.target_learning import (
    LearnedMethodStore,
    TargetLearningEngine,
    build_target_draw,
    next_auto_draw_date,
    parse_target_numbers,
)


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
        source_file="target_learning.xlsx",
        source_row=day_offset + 2,
    )


def build_draws(length: int = 55) -> list[Draw]:
    pattern = (
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 7, 8],
        [9, 10, 11, 12, 13, 14],
    )
    return [build_draw(index, pattern[index % len(pattern)]) for index in range(length)]


def test_parse_target_numbers_accepts_common_separators():
    assert parse_target_numbers("03,11,18,24,36,42") == (3, 11, 18, 24, 36, 42)
    assert parse_target_numbers("03-11-18-24-36-42") == (3, 11, 18, 24, 36, 42)


def test_target_learning_saves_and_loads_methods(tmp_path):
    draws = build_draws()
    target = (1, 2, 3, 4, 5, 6)
    engine = TargetLearningEngine()

    methods = engine.learn_methods(
        draws,
        target,
        top_k=7,
        max_lag=2,
        support_values=(1,),
        strategy_mode="quick",
        limit=5,
        ensemble_pool=4,
    )

    assert methods
    assert methods[0].fit_target_values == target
    assert methods[0].top_k == 7

    store = LearnedMethodStore(tmp_path / "learned_methods.json")
    store.save(methods)
    loaded = store.load()

    assert loaded
    assert loaded[0].label == methods[0].label

    next_values = engine.combined_signal_values(draws, loaded, top_k=7)
    assert next_values
    assert len(next_values) <= 7


def test_target_learning_can_build_next_auto_draw():
    draws = build_draws(5)
    next_date = next_auto_draw_date(draws)
    new_draw = build_target_draw(next_date, (1, 2, 3, 4, 5, 6))

    assert new_draw.draw_date == draws[-1].draw_date + timedelta(days=1)
    assert new_draw.n1 == 1
    assert new_draw.n6 == 6
