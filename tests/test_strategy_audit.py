from datetime import date, timedelta

from ape.database.models import Draw
from ape.patterns import StrategyAuditResult, StrategyAuditor


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
        source_file="audit.xlsx",
        source_row=day_offset + 2,
    )


def build_repeating_draws(length: int = 45) -> list[Draw]:
    draws: list[Draw] = []
    pattern = (
        [1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12],
        [13, 14, 15, 16, 17, 18],
    )
    for index in range(length):
        draws.append(build_draw(index, pattern[index % len(pattern)]))
    return draws


def test_strategy_audit_selects_best_and_replays_rows():
    auditor = StrategyAuditor()
    result = auditor.audit(
        build_repeating_draws(),
        lag_from=1,
        lag_to=3,
        top_k=10,
        base_min_support=1,
        min_training_rows=9,
        target_hits=4,
    )

    assert isinstance(result, StrategyAuditResult)
    assert result.best_evaluation is not None
    assert result.replay_rows
    assert result.max_hits >= 4
    assert result.target_hit_rate > 0


def test_strategy_audit_detail_rows_show_selected_actual_and_matches():
    auditor = StrategyAuditor()
    result = auditor.audit(
        build_repeating_draws(),
        lag_from=1,
        lag_to=3,
        top_k=10,
        base_min_support=1,
        min_training_rows=9,
        target_hits=4,
    )

    detail = result.detail_rows(limit=3)

    assert len(detail) == 3
    assert all(len(row) == 10 for row in detail)
    assert all(row[6] for row in detail)  # Top signals
    assert all(row[7] for row in detail)  # Actual values
