from datetime import date, timedelta

from ape.database.models import Draw
from ape.patterns import CandidateSignal, PatternMiner


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
        source_file="pattern.xlsx",
        source_row=day_offset + 2,
    )


def test_draw_structure_counts_parity_and_ranges():
    miner = PatternMiner()
    structure = miner.draw_structure(build_draw(0, [1, 2, 10, 21, 34, 45]))

    assert structure.odd_count == 3
    assert structure.even_count == 3
    assert structure.band_counts == (2, 1, 1, 1, 1)


def test_structure_profile_learns_modal_and_average_patterns():
    miner = PatternMiner()
    draws = [
        build_draw(0, [1, 2, 3, 11, 21, 31]),
        build_draw(1, [1, 4, 5, 12, 22, 32]),
        build_draw(2, [6, 8, 10, 20, 30, 44]),
    ]

    profile = miner.build_structure_profile(draws)

    assert profile.draw_count == 3
    assert profile.modal_odd_even == (4, 2)
    assert profile.modal_band_counts == (3, 1, 1, 1, 0)
    assert round(profile.average_odd, 2) == 3.00
    assert round(profile.average_band_counts[0], 2) == 2.33


def test_structure_weight_boosts_overrepresented_ranges():
    miner = PatternMiner()
    draws = [build_draw(index, [1, 2, 3, 4, 5, 6]) for index in range(12)]
    profile = miner.build_structure_profile(draws)

    assert miner.structure_weight(5, profile) > miner.structure_weight(25, profile)


def test_balance_signals_by_structure_respects_learned_band_quota_first():
    miner = PatternMiner()
    profile = miner.build_structure_profile(
        [build_draw(index, [1, 2, 3, 10, 21, 31]) for index in range(8)]
    )
    signals = [
        CandidateSignal(value=1, score=10, support=5, rule_count=1, average_lift=1, max_lift=1, matched_sources=(1,)),
        CandidateSignal(value=2, score=9, support=5, rule_count=1, average_lift=1, max_lift=1, matched_sources=(1,)),
        CandidateSignal(value=3, score=8, support=5, rule_count=1, average_lift=1, max_lift=1, matched_sources=(1,)),
        CandidateSignal(value=10, score=7, support=5, rule_count=1, average_lift=1, max_lift=1, matched_sources=(1,)),
        CandidateSignal(value=21, score=6, support=5, rule_count=1, average_lift=1, max_lift=1, matched_sources=(1,)),
        CandidateSignal(value=31, score=5, support=5, rule_count=1, average_lift=1, max_lift=1, matched_sources=(1,)),
    ]

    selected = miner.balance_signals_by_structure(signals, profile, top_n=6)

    assert [item.value for item in selected] == [1, 2, 3, 10, 21, 31]
