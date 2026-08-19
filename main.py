"""APE command-line and desktop entry point."""

from __future__ import annotations

import argparse
from datetime import date

from ape.analytics.service import AnalysisService
from ape.core.app import APEApplication
from ape.core.exceptions import APEError
from ape.database.repositories import DrawRepository
from ape.importers.excel_importer import ExcelDrawImporter
from ape.importers.latest_excel import import_latest_excel_file
from ape.importers.replace_data import replace_database_from_excel
from ape.patterns import StrategyAuditor, StrategyOptimizer, StrategyRechecker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="APE", description="Adaptive Prediction Engine")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("gui", help="Mở giao diện desktop ban đầu.")
    subparsers.add_parser("manual", help="Mở cửa sổ nhập dữ liệu lịch sử và cập nhật Top 7 ổn định.")
    subparsers.add_parser("lab", help="Mở cửa sổ tính lại nhiều cách và lưu cách tính.")
    subparsers.add_parser("learn", help="Mở cửa sổ học từ 1 dãy số mới và tính kỳ tiếp theo.")
    subparsers.add_parser("status", help="Hiển thị trạng thái hệ thống trong CMD.")

    validate_parser = subparsers.add_parser("validate", help="Kiểm tra file Excel nhưng không ghi database.")
    validate_parser.add_argument("file", help="Đường dẫn file Excel.")
    validate_parser.add_argument("--sheet", help="Tên sheet, mặc định tự nhận diện.")

    import_parser = subparsers.add_parser("import", help="Kiểm tra và import file Excel vào database.")
    import_parser.add_argument("file", help="Đường dẫn file Excel.")
    import_parser.add_argument("--sheet", help="Tên sheet, mặc định tự nhận diện.")

    update_latest_parser = subparsers.add_parser(
        "update-latest",
        help="Tự tìm file Excel mới nhất trong thư mục dữ liệu và cập nhật database.",
    )
    update_latest_parser.add_argument(
        "--folder",
        default=None,
        help="Thư mục chứa file Excel; mặc định là thư mục data của APE.",
    )
    update_latest_parser.add_argument("--sheet", help="Tên sheet, mặc định tự nhận diện.")
    update_latest_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ kiểm tra file mới nhất, không ghi database.",
    )
    update_latest_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Tìm cả trong các thư mục con.",
    )

    replace_parser = subparsers.add_parser(
        "replace-data",
        help="Backup, xóa sạch database hiện tại và import lại từ file Excel mới.",
    )
    replace_parser.add_argument(
        "--file",
        default=None,
        help="Đường dẫn file Excel dùng để nạp lại toàn bộ dữ liệu.",
    )
    replace_parser.add_argument(
        "--latest",
        action="store_true",
        help="Tự lấy file Excel mới nhất trong thư mục data hoặc --folder.",
    )
    replace_parser.add_argument(
        "--folder",
        default=None,
        help="Thư mục chứa file Excel khi dùng --latest; mặc định là thư mục data của APE.",
    )
    replace_parser.add_argument("--sheet", help="Tên sheet, mặc định tự nhận diện.")
    replace_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Khi dùng --latest, tìm cả trong các thư mục con.",
    )
    replace_parser.add_argument(
        "--keep-methods",
        action="store_true",
        help="Không reset các file learned_methods/saved_strategy cũ. Mặc định sẽ lưu riêng các file này để học lại từ dữ liệu mới.",
    )
    replace_parser.add_argument(
        "--yes",
        action="store_true",
        help="Xác nhận thao tác xóa sạch dữ liệu cũ và nạp lại từ file mới.",
    )

    analyze_parser = subparsers.add_parser("analyze", help="Phân tích mô tả dữ liệu đã lưu trong database.")
    analyze_parser.add_argument("--limit", type=int, default=10, help="Số lượng mục hiển thị trong mỗi nhóm.")
    analyze_parser.add_argument("--json", action="store_true", help="In toàn bộ báo cáo dưới dạng JSON.")

    optimize_parser = subparsers.add_parser("optimize", help="So sánh nhiều chiến lược Pattern Mining bằng backtest.")
    optimize_parser.add_argument("--lag", type=int, default=3, help="Độ trễ kiểm định, ví dụ 3 nghĩa là N+3.")
    optimize_parser.add_argument("--top", type=int, default=10, help="Số tín hiệu lấy ra để kiểm định.")
    optimize_parser.add_argument("--target", type=int, default=1, help="Mốc số trùng cần tối ưu; mặc định ≥1 để ưu tiên ổn định.")
    optimize_parser.add_argument("--support", type=int, default=3, help="Support tối thiểu gốc.")
    optimize_parser.add_argument("--training-rows", type=int, default=60, help="Số kỳ đầu dùng làm vùng học ban đầu.")
    optimize_parser.add_argument("--mode", choices=("quick", "full"), default="quick", help="quick chạy nhanh, full rà sâu hơn.")
    optimize_parser.add_argument("--max-history", type=int, default=160, help="Số kỳ gần nhất dùng để tối ưu; 0 nghĩa là dùng toàn bộ.")

    audit_parser = subparsers.add_parser("audit", help="Replay Top tín hiệu lịch sử, so với dãy đúng và tìm phương án tối ưu.")
    audit_parser.add_argument("--lag-from", type=int, default=1, help="Độ trễ bắt đầu, mặc định N+1.")
    audit_parser.add_argument("--lag-to", type=int, default=3, help="Độ trễ kết thúc, mặc định N+3.")
    audit_parser.add_argument("--top", type=int, default=10, help="Số tín hiệu tool trả ra ở mỗi lần replay.")
    audit_parser.add_argument("--target", type=int, default=1, help="Mốc số trùng mong muốn; mặc định ≥1 để tránh overfit.")
    audit_parser.add_argument("--support", type=int, default=2, help="Support tối thiểu gốc.")
    audit_parser.add_argument("--training-rows", type=int, default=30, help="Số kỳ đầu dùng làm vùng học ban đầu.")
    audit_parser.add_argument("--detail", type=int, default=20, help="Số dòng replay gần nhất cần in chi tiết.")
    audit_parser.add_argument("--mode", choices=("quick", "full"), default="quick", help="quick chạy nhanh, full rà sâu hơn.")
    audit_parser.add_argument("--max-history", type=int, default=140, help="Số kỳ gần nhất dùng để audit; 0 nghĩa là dùng toàn bộ.")

    recheck_parser = subparsers.add_parser(
        "recheck",
        help="Đối chiếu liên tục từ một ngày bắt đầu để tìm phương án lịch sử ổn định nhất.",
    )
    recheck_parser.add_argument("--from-date", default="2026-03-01", help="Ngày bắt đầu đối chiếu, dạng YYYY-MM-DD.")
    recheck_parser.add_argument("--to-date", default=None, help="Ngày kết thúc đối chiếu, mặc định hôm nay.")
    recheck_parser.add_argument("--lag-from", type=int, default=1, help="Độ trễ bắt đầu, mặc định N+1.")
    recheck_parser.add_argument("--lag-to", type=int, default=3, help="Độ trễ kết thúc, mặc định N+3.")
    recheck_parser.add_argument("--top", type=int, default=7, help="Số tín hiệu tham chiếu, mặc định 7.")
    recheck_parser.add_argument("--target", type=int, default=1, help="Mốc số trùng cần ưu tiên, mặc định ≥1 số.")
    recheck_parser.add_argument("--support", type=int, default=2, help="Support tối thiểu gốc.")
    recheck_parser.add_argument("--training-rows", type=int, default=30, help="Số kỳ đầu dùng làm vùng học ban đầu.")
    recheck_parser.add_argument("--mode", choices=("quick", "full"), default="quick", help="quick chạy nhanh, full rà sâu hơn.")
    recheck_parser.add_argument("--detail", type=int, default=40, help="Số dòng đối chiếu gần nhất cần in chi tiết.")
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
    leaders = ", ".join(f"{item['event_id']:02d}({item['count']})" for item in report.count_leaders)
    distances = ", ".join(f"{item['event_id']:02d}({item['latest_distance']})" for item in report.longest_distances)
    pairs = ", ".join(f"{item['values']}({item['count']})" for item in report.common_pairs)
    print("\n================ DATA ANALYSIS ================")
    print("Số kỳ                 :", report.dataset["total_rows"])
    print("Ngày đầu              :", report.dataset["first_date"])
    print("Ngày cuối             :", report.dataset["last_date"])
    print("Giá trị xuất hiện nhiều:", leaders)
    print("Khoảng vắng hiện tại  :", distances)
    print("Nhóm đôi phổ biến     :", pairs)
    print("Chất lượng dữ liệu    :", report.audit["quality_score"], "/ 100")
    print("================================================\n")


def normalized_history_limit(value: int) -> int | None:
    return None if value <= 0 else value


def parse_iso_date(value: str | None, *, default: date | None = None) -> date:
    if value is None:
        if default is None:
            raise ValueError("Thiếu ngày cần xử lý.")
        return default
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Ngày phải nhập theo dạng YYYY-MM-DD, ví dụ 2026-03-01.") from exc


def print_latest_excel_update(app: APEApplication, args: argparse.Namespace) -> None:
    result = import_latest_excel_file(
        folder=args.folder,
        sheet_name=args.sheet,
        database=app.database,
        dry_run=args.dry_run,
        recursive=args.recursive,
    )
    title = "KIỂM TRA FILE EXCEL MỚI NHẤT" if args.dry_run else "CẬP NHẬT TỪ FILE EXCEL MỚI NHẤT"
    print(f"\n================ {title} ================")
    for name, value in result.to_rows():
        print(f"{name}: {value}")
    print("====================================================\n")


def print_replace_data(app: APEApplication, args: argparse.Namespace) -> None:
    if not args.yes:
        raise ValueError(
            "replace-data sẽ xóa sạch dữ liệu cũ trước khi nạp file mới. "
            "Hãy thêm --yes nếu anh chắc chắn muốn thực hiện."
        )
    result = replace_database_from_excel(
        file_path=args.file,
        folder=args.folder,
        sheet_name=args.sheet,
        database=app.database,
        latest=args.latest,
        recursive=args.recursive,
        clear_method_memory=not args.keep_methods,
    )
    print("\n================ THAY THẾ TOÀN BỘ DỮ LIỆU ================")
    for name, value in result.to_rows():
        print(f"{name}: {value}")
    print("==========================================================\n")


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
        strategy_mode=args.mode,
        max_history_rows=normalized_history_limit(args.max_history),
    )
    print("\n================ STRATEGY OPTIMIZER ================")
    for name, value in result.to_rows():
        print(f"{name}: {value}")
    signals = result.latest_signals(optimizer, draws)
    print("\nTop tín hiệu theo phương án tốt nhất:")
    print(" - ".join(f"{signal.value:02d}" for signal in signals) or "Chưa đủ dữ liệu")
    print("====================================================\n")


def print_strategy_audit(app: APEApplication, args: argparse.Namespace) -> None:
    with app.database.session() as session:
        draws = DrawRepository(session).list_chronological()
    print(
        "\nĐang chạy audit: "
        f"lag N+{args.lag_from}→N+{args.lag_to}, top {args.top}, "
        f"target ≥{args.target}, mode {args.mode}, "
        f"max-history {args.max_history if args.max_history > 0 else 'all'}..."
    )
    auditor = StrategyAuditor()
    result = auditor.audit(
        draws,
        lag_from=args.lag_from,
        lag_to=args.lag_to,
        top_k=args.top,
        base_min_support=args.support,
        min_training_rows=args.training_rows,
        target_hits=args.target,
        strategy_mode=args.mode,
        max_history_rows=normalized_history_limit(args.max_history),
    )
    print("\n================ STRATEGY AUDIT REPLAY ================")
    for name, value in result.to_rows():
        print(f"{name}: {value}")
    print("\nChi tiết replay gần nhất:")
    print("# | Ngày N | Ngày đúng | Lag | TT | Khớp | Top tín hiệu | Dãy đúng | Số trùng")
    print("-" * 140)
    for row in result.detail_rows(limit=args.detail):
        print(" | ".join(row[:9]))
    print("========================================================\n")


def print_rolling_recheck(app: APEApplication, args: argparse.Namespace) -> None:
    with app.database.session() as session:
        draws = DrawRepository(session).list_chronological()
    start_date = parse_iso_date(args.from_date)
    end_date = parse_iso_date(args.to_date, default=date.today())
    print(
        "\nĐang recheck liên tục: "
        f"{start_date.strftime('%d/%m/%Y')} → {end_date.strftime('%d/%m/%Y')}, "
        f"lag N+{args.lag_from}→N+{args.lag_to}, top {args.top}, "
        f"target ≥{args.target}, mode {args.mode}..."
    )
    rechecker = StrategyRechecker()
    result = rechecker.recheck(
        draws,
        start_date=start_date,
        end_date=end_date,
        lag_from=args.lag_from,
        lag_to=args.lag_to,
        top_k=args.top,
        base_min_support=args.support,
        min_training_rows=args.training_rows,
        target_hits=args.target,
        strategy_mode=args.mode,
    )
    print("\n================ ROLLING RECHECK ================")
    for name, value in result.to_rows():
        print(f"{name}: {value}")
    print("\nChi tiết đối chiếu gần nhất:")
    print("# | Ngày N | Ngày đúng | Lag | TT | Khớp | Top tín hiệu | Dãy đúng | Số trùng")
    print("-" * 140)
    for row in result.detail_rows(limit=args.detail):
        print(" | ".join(row))
    print("=================================================\n")


def launch_gui() -> int:
    try:
        from ape.gui import run_gui
    except ImportError as exc:
        print("Không thể khởi động giao diện APE.")
        print("Hãy chạy: py -m pip install -r requirements.txt")
        print(f"Chi tiết: {exc}")
        return 1
    return run_gui()


def launch_manual_entry() -> int:
    try:
        from ape.gui.manual_entry import run_manual_entry
    except ImportError as exc:
        print("Không thể khởi động cửa sổ nhập dữ liệu lịch sử.")
        print("Hãy chạy: py -m pip install -r requirements.txt")
        print(f"Chi tiết: {exc}")
        return 1
    return run_manual_entry()


def launch_strategy_lab() -> int:
    try:
        from ape.gui.strategy_lab import run_strategy_lab
    except ImportError as exc:
        print("Không thể khởi động cửa sổ tính lại nhiều cách.")
        print("Hãy chạy: py -m pip install -r requirements.txt")
        print(f"Chi tiết: {exc}")
        return 1
    return run_strategy_lab()


def launch_target_learning() -> int:
    try:
        from ape.gui.target_learning import run_target_learning
    except ImportError as exc:
        print("Không thể khởi động cửa sổ học từ dãy số mới.")
        print("Hãy chạy: py -m pip install -r requirements.txt")
        print(f"Chi tiết: {exc}")
        return 1
    return run_target_learning()


def main() -> int:
    args = build_parser().parse_args()
    if args.command in {None, "gui"}:
        return launch_gui()
    if args.command == "manual":
        return launch_manual_entry()
    if args.command == "lab":
        return launch_strategy_lab()
    if args.command == "learn":
        return launch_target_learning()

    app = APEApplication()
    app.start()
    try:
        if args.command == "validate":
            report = ExcelDrawImporter(app.database).validate_file(args.file, args.sheet)
            print(report.to_json())
        elif args.command == "import":
            report = ExcelDrawImporter(app.database).import_file(args.file, args.sheet)
            print(report.to_json())
        elif args.command == "update-latest":
            print_latest_excel_update(app, args)
        elif args.command == "replace-data":
            print_replace_data(app, args)
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
        elif args.command == "recheck":
            print_rolling_recheck(app, args)
        else:
            print_status(app)
        return 0
    except (APEError, ValueError) as exc:
        print(f"LỖI: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
