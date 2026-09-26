"""Run the number ranking lab.

Example:
    py number_rank_train.py
    py number_rank_train.py --holdout 15 --top 7 --way-top 20 --method-count 800
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ape.core.app import APEApplication
from ape.database.repositories import DrawRepository
from ape.patterns.number_rank_gate import NumberRankingLabTrainer, RANKING_MODES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="number_rank_train.py",
        description=(
            "Kiểm tra nhiều kiểu xếp Top 7 trên chuỗi walkback. "
            "Tool chỉ xuất tín hiệu khi một ranking vượt đủ gate."
        ),
    )
    parser.add_argument("--holdout", type=int, default=15, help="Số kỳ cuối dùng làm chuỗi kiểm định, mặc định 15.")
    parser.add_argument("--top", type=int, default=7, help="Top tín hiệu cuối cùng để xếp hạng, mặc định 7.")
    parser.add_argument("--way-top", type=int, default=15, help="Phạm vi mỗi phương pháp được xét là kéo ra một số, mặc định 15.")
    parser.add_argument("--method-count", type=int, default=600, help="Số phương pháp cần tìm ở vòng đầu, mặc định 600.")
    parser.add_argument("--ensemble-pool", type=int, default=70, help="Số phương pháp đưa vào tổ hợp ở vòng đầu, mặc định 70.")
    parser.add_argument("--max-lag", type=int, default=24, help="Lag tối đa ở vòng đầu, mặc định 24.")
    parser.add_argument("--support-max", type=int, default=9, help="Support rà đến ở vòng đầu, mặc định 9.")
    parser.add_argument("--max-rounds", type=int, default=3, help="Số vòng tự mở rộng, mặc định 3.")
    parser.add_argument("--min-base-history", type=int, default=60, help="Số kỳ tối thiểu trước vùng holdout, mặc định 60.")
    parser.add_argument("--min-ways", type=int, default=1, help="Số cách tối thiểu cần kéo ra mỗi số đúng, mặc định 1.")
    parser.add_argument("--min-top-hits", type=int, default=1, help="Số trùng Top tối thiểu mỗi kỳ cần đạt, mặc định 1.")
    parser.add_argument(
        "--rank-modes",
        default=",".join(RANKING_MODES),
        help="Danh sách ranking cần thử, cách nhau bởi dấu phẩy.",
    )
    parser.add_argument(
        "--save-path",
        default=None,
        help="Đường dẫn file JSON để lưu ranking sống sót khi gate pass.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    rank_modes = tuple(mode.strip() for mode in args.rank_modes.split(",") if mode.strip())

    app = APEApplication()
    app.start()
    with app.database.session() as session:
        draws = DrawRepository(session).list_chronological()

    result = NumberRankingLabTrainer().train(
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
        ranking_modes=rank_modes,
        save_path=Path(args.save_path) if args.save_path else None,
    )
    print("\n".join(result.to_lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
