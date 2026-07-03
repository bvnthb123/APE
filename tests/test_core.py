from ape.core.app import APEApplication
from ape.gui import format_numbers


def test_app_summary_contains_version():
    app = APEApplication()
    summary = app.summary()
    assert "version" in summary
    assert summary["app_code"] == "APE"


def test_gui_number_formatting():
    assert format_numbers([1, 8, 17, 25, 36, 45]) == (
        "01 - 08 - 17 - 25 - 36 - 45"
    )
