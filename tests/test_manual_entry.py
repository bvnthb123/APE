from datetime import date

import pytest

from ape.manual_entry import build_manual_draw, parse_manual_numbers


def test_parse_manual_numbers_accepts_common_separators():
    values = parse_manual_numbers("03, 11;18/24-36|42")

    assert values == (3, 11, 18, 24, 36, 42)


def test_parse_manual_numbers_rejects_duplicate_values():
    with pytest.raises(ValueError, match="không được trùng"):
        parse_manual_numbers("03 11 18 24 36 36")


def test_build_manual_draw_computes_structural_fields():
    draw = build_manual_draw(date(2026, 8, 13), (3, 11, 18, 24, 36, 42))

    assert draw.draw_date == date(2026, 8, 13)
    assert draw.numbers == [3, 11, 18, 24, 36, 42]
    assert draw.total_sum == 134
    assert draw.odd_count == 2
    assert draw.even_count == 4
    assert draw.low_count == 3
    assert draw.high_count == 3
    assert draw.source_file == "manual_entry"
