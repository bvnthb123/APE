"""Run the independent per-number chain gate.

Example:
    py number_chain_train.py
    py number_chain_train.py --holdout 15 --top 7 --way-top 15 --method-count 600
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ape.core.app import APEApplication
from ape.database.repositories import DrawRepository
from ape.patterns.number_chain_gate import IndependentNumberChainTrainer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="number_chain_train.py",
        description=(
            "Lùi lại N kỳ, tính 6 số độc lập theo chuỗi cách sống sót. "
            "Cách đúng ở kỳ trước mới được áp dụng cho kỳ sau."
        ),
    )
    parser.add_argument("--holdout", type=int, default=15, help="Số kỳ cuối dùng làm chuỗi kiểm định, mặc định 15.")
    parser.add_argument("--top", type=int, default=7, help="Top tín hiệu cuối cùng để xếp hạng, mặc định 7.")
    parser.add_argument(
        "--way-top",
        type=int,
        default=15,
        help="Phạm vi mỗi phương pháp được xét là kéo ra một số, mặc định 15.",
    )
    parser.add_argument("--method-count", type=int, default=600, help="Số phương pháp cần tìm ở vòng đầu, mặc định 600.")
    parser.add_argument("--ensemble-pool", type=int, default=70, help="Số phương pháp đưa vào tổ hợp ở vòng đầu, mặc định 70.")
    parser.add_argument("--max-lag", type=int, default=24, help="Lag tối đa ở vòng đầu, mặc định 24.")
    parser.add_argument("--support-max", type=int, default=9, help="Support rà đến ở vòng đầu, mặc định 9.")
    parser.add_argument("--max-rounds", type=int, default=3, help="Số vòng tự mở rộng nếu gate fail, mặc định 3.")
    parser.add_argument("--min-base-history", type=int, default=60, help="Số kỳ tối thiểu trước vùng holdout, mặc định 60.")
    parser.add_argument("--min-ways", type=int, default=1, help="Số cách tối thiểu cần kéo ra mỗi số đúng, mặc định 1.")
    parser.add_argument(
        "--min-top-hits",
        type=int,
        default=1,
        help="Số trùng Top tối thiểu mỗi kỳ cần đạt, mặc định 1.",
    )
    parser.add_argument(
        "--save-path",
        default=None,
        help="Đường dẫn file JSON để lưu bộ phương pháp sống sót khi gate pass.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    app = APEApplication()
    app.start()
    with app.database.session() as session:
        draws = DrawRepository(session).list_chronological()

    result = IndependentNumberChainTrainer().train(
        draws,
        holdout_count=args.holdout,
        top_k=args.top,
        way_top=args.way_top,
        method_count=args.method_count,
        ensemble_pool=args.ensemble_pool,
        max_lag=args.max_lag,
        support_max=args.support_max,
        max_rounds=args.max_rounds,
        min_base_history=args.min_base_history,
        min_ways=args.min_ways,
        min_top_hits=args.min_top_hits,
        save_path=Path(args.save_path) if args.save_path else None,
    )
    print("\n".join(result.to_lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
