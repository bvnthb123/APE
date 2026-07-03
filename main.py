"""APE command-line entry point."""

from __future__ import annotations

import argparse

from ape.core.app import APEApplication
from ape.core.exceptions import APEError
from ape.importers.excel_importer import ExcelDrawImporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="APE",
        description="Adaptive Prediction Engine",
    )
    subparsers = parser.add_subparsers(dest="command")

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
    return parser


def print_status(app: APEApplication) -> None:
    summary = app.summary()

    print("\n====================================================")
    print("APE - Adaptive Prediction Engine")
    print("Version :", summary["version"])
    print("Build   :", summary["build"])
    print("Status  : Excel Importer Ready")
    print("====================================================\n")

    for key, value in summary.items():
        print(f"{key}: {value}")


def main() -> int:
    args = build_parser().parse_args()
    app = APEApplication()
    app.start()

    try:
        importer = ExcelDrawImporter(app.database)

        if args.command == "validate":
            report = importer.validate_file(args.file, args.sheet)
            print(report.to_json())
        elif args.command == "import":
            report = importer.import_file(args.file, args.sheet)
            print(report.to_json())
        else:
            print_status(app)

        return 0
    except APEError as exc:
        print(f"LỖI: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
