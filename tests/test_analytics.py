from datetime import date

from ape.analytics.analyzer import EventSequenceAnalyzer
from ape.database.models import Draw


def make_draw(row_date: date, values: list[int]) -> Draw:
    values = sorted(values)
    odd_count = sum(value % 2 for value in values)
    low_count = sum(value <= 22 for value in values)
    return Draw(
        draw_date=row_date,
        weekday_index=row_date.weekday(),
        weekday_name=(
            "Thứ Hai",
            "Thứ Ba",
            "Thứ Tư",
            "Thứ Năm",
            "Thứ Sáu",
            "Thứ Bảy",
            "Chủ Nhật",
        )[row_date.weekday()],
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
        source_file="test.xlsx",
        source_row=2,
    )


def test_analyzer_counts_values_and_groups():
    rows = [
        make_draw(date(2026, 1, 1), [1, 2, 3, 4, 5, 6]),
        make_draw(date(2026, 1, 3), [1, 2, 7, 8, 9, 10]),
        make_draw(date(2026, 1, 5), [1, 3, 7, 11, 12, 13]),
    ]

    report = EventSequenceAnalyzer(recent_window=2).analyze(rows, limit=3)
    metric_1 = next(item for item in report.event_metrics if item["event_id"] == 1)
    metric_2 = next(item for item in report.event_metrics if item["event_id"] == 2)

    assert report.dataset["total_rows"] == 3
    assert metric_1["count"] == 3
    assert metric_1["latest_distance"] == 0
    assert metric_2["count"] == 2
    assert metric_2["latest_distance"] == 1
    assert report.common_pairs[0]["values"] == "01-02"
    assert report.common_pairs[0]["count"] == 2
    assert report.audit["quality_score"] == 100.0


def test_analyzer_reports_structure_patterns():
    rows = [
        make_draw(date(2026, 1, 1), [1, 2, 3, 20, 30, 40]),
        make_draw(date(2026, 1, 3), [2, 4, 6, 21, 31, 41]),
    ]

    report = EventSequenceAnalyzer().analyze(rows, limit=2)

    assert report.structure["total"]["minimum"] == 96
    assert report.structure["total"]["maximum"] == 105
    assert report.structure["shared_with_previous_row"]["1"] == 1
    assert report.time_summary["year_counts"]["2026"] == 2
