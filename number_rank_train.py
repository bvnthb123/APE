"""Run the number ranking top-rescue lab.

Example:
    py number_rank_train.py
    py number_rank_train.py --holdout 15 --top 7 --way-top 20 --method-count 800 --repair-rounds 3
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ape.core.app import APEApplication
from ape.database.repositories import DrawRepository
from ape.patterns.number_rank_top_rescue_gate import NumberRankingTopRescueTrainer, RANKING_MODES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="number_rank_train.py",
        description=(
            "Kiểm tra Top 7 trên chuỗi walkback. "
            "Nếu thiếu riêng một số hoặc đủ cách 6/6 nhưng Top không trúng, "
            "tool sẽ rescue rồi chạy lại từ kỳ 01."
        ),
    )
    parser.add_argument("--holdout", type=int, default=15, help="Số kỳ cuối dùng làm chuỗi kiểm định, mặc định 15.")
    parser.add_argument("--top", type=int, default=7, help="Top tín hiệu cuối cùng để xếp hạng, mặc định 7.")
    parser.add_argument("--way-top", type=int, default=15, help="Phạm vi mỗi phương pháp được xét là kéo ra một số, mặc định 15.")
    parser.add_argument("--method-count", type=int, default=250, help="Số phương pháp cần tìm ở vòng đầu, mặc định 250 để tránh chạy quá nặng.")
    parser.add_argument("--ensemble-pool", type=int, default=40, help="Số phương pháp đưa vào tổ hợp ở vòng đầu, mặc định 40.")
    parser.add_argument("--max-lag", type=int, default=16, help="Lag tối đa ở vòng đầu, mặc định 16.")
    parser.add_argument("--support-max", type=int, default=6, help="Support rà đến ở vòng đầu, mặc định 6.")
    parser.add_argument("--max-rounds", type=int, default=1, help="Số vòng tự mở rộng, mặc định 1 để tránh treo.")
    parser.add_argument("--min-base-history", type=int, default=60, help="Số kỳ tối thiểu trước vùng holdout, mặc định 60.")
    parser.add_argument("--min-ways", type=int, default=1, help="Số cách tối thiểu cần kéo ra mỗi số đúng, mặc định 1.")
    parser.add_argument("--min-top-hits", type=int, default=1, help="Số trùng Top tối thiểu mỗi kỳ cần đạt, mặc định 1.")
    parser.add_argument("--repair-rounds", type=int, default=2, help="Số vòng rescue rồi chạy lại từ kỳ 01, mặc định 2.")
    parser.add_argument(
        "--rank-modes",
        default="missing_first,coverage_balanced",
        help="Danh sách ranking cần thử, cách nhau bởi dấu phẩy. Mặc định chỉ chạy 2 mode nhẹ nhất.",
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

    print("[NUMBER RANK TOP RESCUE] cấu hình chạy:")
    print(f"  holdout={args.holdout}, top={args.top}, way_top={args.way_top}")
    print(f"  method_count={args.method_count}, ensemble_pool={args.ensemble_pool}, max_lag={args.max_lag}, support_max={args.support_max}")
    print(f"  max_rounds={args.max_rounds}, repair_rounds={args.repair_rounds}, rank_modes={','.join(rank_modes)}")

    app = APEApplication()
    app.start()
    with app.database.session() as session:
        draws = DrawRepository(session).list_chronological()

    result = NumberRankingTopRescueTrainer().train(
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
        repair_rounds=args.repair_rounds,
        ranking_modes=rank_modes,
        save_path=Path(args.save_path) if args.save_path else None,
    )
    print("\n".join(result.to_lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
