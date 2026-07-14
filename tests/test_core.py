from datetime import date

from ape.core.app import APEApplication
from ape.database.models import Draw
from ape.gui import filter_draws, format_numbers
from ape.gui.preferences import GuiPreferences


def build_draw(draw_date: date, values: list[int], source_file: str = "test.xlsx") -> Draw:
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
        source_file=source_file,
        source_row=2,
    )


def test_app_summary_contains_version():
    app = APEApplication()
    summary = app.summary()
    assert "version" in summary
    assert summary["app_code"] == "APE"


def test_gui_number_formatting():
    assert format_numbers([1, 8, 17, 25, 36, 45]) == (
        "01 - 08 - 17 - 25 - 36 - 45"
    )


def test_gui_filter_draws_by_date_and_query():
    draws = [
        build_draw(date(2026, 1, 1), [1, 2, 3, 4, 5, 6], "alpha.xlsx"),
        build_draw(date(2026, 1, 8), [7, 8, 9, 10, 11, 12], "beta.xlsx"),
    ]

    result = filter_draws(
        draws,
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 10),
        query="beta",
    )

    assert len(result) == 1
    assert result[0].source_file == "beta.xlsx"


def test_gui_preferences_round_trip(tmp_path):
    path = tmp_path / "gui_preferences.json"
    preferences = GuiPreferences(
        window_width=1400,
        window_height=900,
        last_excel_dir="D:/Excel",
        last_report_dir="D:/Reports",
    )
    preferences.save(path)

    loaded = GuiPreferences.load(path)

    assert loaded.window_width == 1400
    assert loaded.window_height == 900
    assert loaded.last_excel_dir == "D:/Excel"
    assert loaded.last_report_dir == "D:/Reports"
