"""Run a clean holdout forecast test from the command line.

Example:
    py forecast_test.py "06 15 18 33 40 43"
"""

from __future__ import annotations

import argparse

from ape.core.app import APEApplication
from ape.database.repositories import DrawRepository
from ape.patterns.holdout_forecast import HoldoutForecaster


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forecast_test.py",
        description="Clean holdout forecast test: choose strategy from history only, then compare with a hidden target row.",
    )
    parser.add_argument("target", help="Dãy kiểm định, ví dụ: \"06 15 18 33 40 43\"")
    parser.add_argument("--top", type=int, default=7, help="Top tín hiệu chính, mặc định 7.")
    parser.add_argument("--lag", type=int, default=1, help="Độ trễ dự báo, mặc định N+1.")
    parser.add_argument("--support", type=int, default=3, help="Support tối thiểu gốc.")
    parser.add_argument("--training-rows", type=int, default=60, help="Số kỳ đầu dùng làm vùng học backtest.")
    parser.add_argument("--target", type=int, default=1, help="Mốc tối ưu trong backtest, mặc định ≥1 số.")
    parser.add_argument("--mode", choices=("quick", "full"), default="full", help="Chế độ rà strategy.")
    parser.add_argument("--max-history", type=int, default=0, help="Số kỳ gần nhất dùng để tối ưu; 0 nghĩa là toàn bộ.")
    return parser


def normalized_history_limit(value: int) -> int | None:
    return None if value <= 0 else value


def main() -> int:
    args = build_parser().parse_args()
    app = APEApplication()
    app.start()
    with app.database.session() as session:
        draws = DrawRepository(session).list_chronological()

    result = HoldoutForecaster().forecast(
        draws,
        args.target,
        top_k=args.top,
        lag=args.lag,
        base_min_support=args.support,
        min_training_rows=args.training_rows,
        target_hits=args.target,
        strategy_mode=args.mode,
        max_history_rows=normalized_history_limit(args.max_history),
    )
    print("\n".join(result.to_lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
