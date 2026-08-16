from datetime import date, timedelta

from ape.database.models import Draw
from ape.patterns import SavedStrategyStore, StrategyChoiceEngine


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
        source_file="choice.xlsx",
        source_row=day_offset + 2,
    )


def test_strategy_choice_engine_generates_multiple_choices():
    pattern = (
        [1, 2, 3, 4, 5, 6],
        [1, 2, 3, 4, 7, 8],
        [9, 10, 11, 12, 13, 14],
    )
    draws = [build_draw(index, pattern[index % len(pattern)]) for index in range(90)]

    choices = StrategyChoiceEngine().generate_choices(
        draws,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        top_k=7,
        base_min_support=1,
        min_training_rows=20,
        target_hits=1,
        strategy_mode="quick",
        limit=5,
    )

    assert choices
    assert len(choices) <= 5
    assert choices[0].signal_values
    assert choices[0].tested_rows > 0


def test_saved_strategy_store_round_trips_choice(tmp_path):
    draws = [build_draw(index, [1, 2, 3, 4, 5, 6]) for index in range(90)]
    choice = StrategyChoiceEngine().generate_choices(
        draws,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
        top_k=7,
        base_min_support=1,
        min_training_rows=20,
        target_hits=1,
        limit=1,
    )[0]

    store = SavedStrategyStore(tmp_path / "saved_strategy.json")
    store.save(choice.to_saved_strategy())
    loaded = store.load()

    assert loaded is not None
    assert loaded.label == choice.config.detail_label
    assert loaded.config == choice.config
    assert loaded.top_k == 7
