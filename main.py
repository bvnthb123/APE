"""APE command-line and desktop entry point."""

from __future__ import annotations

import argparse

from ape.analytics.service import AnalysisService
from ape.core.app import APEApplication
from ape.core.exceptions import APEError
from ape.importers.excel_importer import ExcelDrawImporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="APE",
        description="Adaptive Prediction Engine",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "gui",
        help="Mở giao diện desktop.",
    )
    subparsers.add_parser(
        "status",
        help="Hiển thị trạng thái hệ thống trong CMD.",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Kiểm tra file Excel nhưng không ghi database.",
    )
    validate_parser.add_argument("file", help="Đường dẫn file Excel.")
    validate_parser.add_argument(
        "--sheet",
        help="Tên sheet, mặc định tự nhận diện.",
    )

    import_parser = subparsers.add_parser(
        "import",
        help="Kiểm tra và import file Excel vào database.",
    )
    import_parser.add_argument("file", help="Đường dẫn file Excel.")
    import_parser.add_argument(
        "--sheet",
        help="Tên sheet, mặc định tự nhận diện.",
    )

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Phân tích mô tả dữ liệu đã lưu trong database.",
    )
    analyze_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Số lượng mục hiển thị trong mỗi nhóm.",
    )
    analyze_parser.add_argument(
        "--json",
        action="store_true",
        help="In toàn bộ báo cáo dưới dạng JSON.",
    )
    return parser


def print_status(app: APEApplication) -> None:
    summary = app.summary()

    print("\n====================================================")
    print("APE - Adaptive Prediction Engine")
    print("Version :", summary["version"])
    print("Build   :", summary["build"])
    print("Status  : Desktop GUI Ready")
    print("====================================================\n")

    for key, value in summary.items():
        print(f"{key}: {value}")


def print_analysis(report) -> None:
    leaders = ", ".join(
        f"{item['event_id']:02d}({item['count']})"
        for item in report.count_leaders
    )
    distances = ", ".join(
        f"{item['event_id']:02d}({item['latest_distance']})"
        for item in report.longest_distances
    )
    pairs = ", ".join(
        f"{item['values']}({item['count']})"
        for item in report.common_pairs
    )

    print("\n================ DATA ANALYSIS ================")
    print("Số kỳ                 :", report.dataset["total_rows"])
    print("Ngày đầu              :", report.dataset["first_date"])
    print("Ngày cuối             :", report.dataset["last_date"])
    print("Giá trị xuất hiện nhiều:", leaders)
    print("Khoảng vắng hiện tại  :", distances)
    print("Nhóm đôi phổ biến     :", pairs)
    print("Chất lượng dữ liệu    :", report.audit["quality_score"], "/ 100")
    print("================================================\n")


def launch_gui() -> int:
    try:
        from ape.gui import run_gui
    except ImportError as exc:
        print("Không thể khởi động giao diện APE.")
        print("Hãy chạy: py -m pip install -r requirements.txt")
        print(f"Chi tiết: {exc}")
        return 1
    return run_gui()


def main() -> int:
    args = build_parser().parse_args()

    if args.command in {None, "gui"}:
        return launch_gui()

    app = APEApplication()
    app.start()

    try:
        if args.command == "validate":
            report = ExcelDrawImporter(app.database).validate_file(
                args.file,
                args.sheet,
            )
            print(report.to_json())
        elif args.command == "import":
            report = ExcelDrawImporter(app.database).import_file(
                args.file,
                args.sheet,
            )
            print(report.to_json())
        elif args.command == "analyze":
            report = AnalysisService(app.database).generate(args.limit)
            if args.json:
                print(report.to_json())
            else:
                print_analysis(report)
        else:
            print_status(app)

        return 0
    except APEError as exc:
        print(f"LỖI: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
