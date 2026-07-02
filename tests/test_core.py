from ape.core.app import APEApplication

def test_app_summary_contains_version():
    app = APEApplication()
    summary = app.summary()
    assert "version" in summary
    assert summary["app_code"] == "APE"
