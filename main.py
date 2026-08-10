"""APE command-line and desktop entry point."""

from __future__ import annotations

import argparse

from ape.analytics.service import AnalysisService
from ape.core.app import APEApplication
from ape.core.exceptions import APEError
from ape.database.repositories import DrawRepository
from ape.importers.excel_importer import ExcelDrawImporter
from ape.patterns import StrategyAuditor, StrategyOptimizer


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

    optimize_parser = subparsers.add_parser(
        "optimize",
        help="So sánh nhiều chiến lược Pattern Mining bằng backtest.",
    )
    optimize_parser.add_argument(
        "--lag",
        type=int,
        default=3,
        help="Độ trễ kiểm định, ví dụ 3 nghĩa là N+3.",
    )
    optimize_parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Số tín hiệu lấy ra để kiểm định.",
    )
    optimize_parser.add_argument(
        "--target",
        type=int,
        default=1,
        help="Mốc số trùng cần tối ưu, ví dụ 4 nghĩa là tối ưu tỷ lệ trùng ít nhất 4 số.",
    )
    optimize_parser.add_argument(
        "--support",
        type=int,
        default=3,
        help="Support tối thiểu gốc. Optimizer sẽ thử thêm các biến thể quanh mức này.",
    )
    optimize_parser.add_argument(
        "--training-rows",
        type=int,
        default=60,
        help="Số kỳ đầu dùng làm vùng học ban đầu khi backtest walk-forward.",
    )

    audit_parser = subparsers.add_parser(
        "audit",
        help="Replay Top tín hiệu lịch sử, so với dãy đúng và tìm phương án tối ưu.",
    )
    audit_parser.add_argument(
        "--lag-from",
        type=int,
        default=1,
        help="Độ trễ bắt đầu để rà soát, mặc định N+1.",
    )
    audit_parser.add_argument(
        "--lag-to",
        type=int,
        default=3,
        help="Độ trễ kết thúc để rà soát, mặc định N+3.",
    )
    audit_parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Số tín hiệu tool trả ra ở mỗi lần replay.",
    )
    audit_parser.add_argument(
        "--target",
        type=int,
        default=4,
        help="Mốc số trùng mong muốn, mặc định tối ưu từ 4 số trở lên.",
    )
    audit_parser.add_argument(
        "--support",
        type=int,
        default=2,
        help="Support tối thiểu gốc để optimizer thử các biến thể.",
    )
    audit_parser.add_argument(
        "--training-rows",
        type=int,
        default=30,
        help="Số kỳ đầu dùng làm vùng học ban đầu trước khi replay.",
    )
    audit_parser.add_argument(
        "--detail",
        type=int,
        default=20,
        help="Số dòng replay gần nhất cần in chi tiết.",
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


def print_strategy_optimization(app: APEApplication, args: argparse.Namespace) -> None:
    with app.database.session() as session:
        draws = DrawRepository(session).list_chronological()

    optimizer = StrategyOptimizer()
    result = optimizer.optimize(
        draws,
        lag=args.lag,
        top_k=args.top,
        base_min_support=args.support,
        min_training_rows=args.training_rows,
        target_hits=args.target,
    )

    print("\n================ STRATEGY OPTIMIZER ================")
    for name, value in result.to_rows():
        print(f"{name}: {value}")

    signals = result.latest_signals(optimizer, draws)
    signal_values = " - ".join(f"{signal.value:02d}" for signal in signals)
    print("\nTop tín hiệu theo phương án tốt nhất:")
    print(signal_values or "Chưa đủ dữ liệu")
    print("====================================================\n")


def print_strategy_audit(app: APEApplication, args: argparse.Namespace) -> None:
    with app.database.session() as session:
        draws = DrawRepository(session).list_chronological()

    auditor = StrategyAuditor()
    result = auditor.audit(
        draws,
        lag_from=args.lag_from,
        lag_to=args.lag_to,
        top_k=args.top,
        base_min_support=args.support,
        min_training_rows=args.training_rows,
        target_hits=args.target,
    )

    print("\n================ STRATEGY AUDIT REPLAY ================")
    for name, value in result.to_rows():
        print(f"{name}: {value}")

    print("\nChi tiết replay gần nhất:")
    headers = (
        "#",
        "Ngày N",
        "Ngày đúng",
        "Lag",
        "TT",
        "Khớp",
        "Top tín hiệu",
        "Dãy đúng",
        "Số trùng",
    )
    print(" | ".join(headers))
    print("-" * 140)
    for row in result.detail_rows(limit=args.detail):
        print(" | ".join(row[:9]))
    print("========================================================\n")


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
        elif args.command == "optimize":
            print_strategy_optimization(app, args)
        elif args.command == "audit":
            print_strategy_audit(app, args)
        else:
            print_status(app)

        return 0
    except (APEError, ValueError) as exc:
        print(f"LỖI: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
