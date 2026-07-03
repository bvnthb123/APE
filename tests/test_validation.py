from ape.validation.draw_validator import DrawValidator


def test_valid_row_is_normalized():
    result = DrawValidator().validate(
        "03/01/2024",
        "Thứ Tư",
        "38 - 12 - 20 - 27 - 31 - 13",
        2,
    )
    assert result.is_valid
    assert result.draw is not None
    assert result.draw.numbers == (12, 13, 20, 27, 31, 38)
    assert not result.warnings


def test_out_of_range_number_is_rejected():
    result = DrawValidator().validate(
        "03/01/2024",
        "Thứ Tư",
        "01 - 02 - 03 - 04 - 05 - 46",
        2,
    )
    assert not result.is_valid
    assert result.errors[0].code == "invalid_numbers"


def test_weekday_mismatch_is_warning():
    result = DrawValidator().validate(
        "03/01/2024",
        "Thứ Sáu",
        "01 - 02 - 03 - 04 - 05 - 06",
        2,
    )
    assert result.is_valid
    assert result.warnings[0].code == "weekday_mismatch"
