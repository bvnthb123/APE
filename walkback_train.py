"""Run the strict walk-back survivor gate.

Example:
    py walkback_train.py
    py walkback_train.py --holdout 10 --top 7 --method-count 600 --min-ways 1 --repair-rounds 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ape.core.app import APEApplication
from ape.database.repositories import DrawRepository
from ape.patterns.walkback_gate import WalkbackGateTrainer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="walkback_train.py",
        description=(
            "Lùi lại N kỳ cuối, tìm bộ phương pháp sống sót qua từng kỳ. "
            "Một kỳ pass khi cả 6 số đều có đủ số cách tính sống sót kéo ra. "
            "Nếu fail, repair loop sẽ học bổ sung số thiếu rồi quay lại kỳ 01."
        ),
    )
    parser.add_argument("--holdout", type=int, default=10, help="Số kỳ cuối dùng làm vùng kiểm định, mặc định 10.")
    parser.add_argument("--top", type=int, default=6, help="Top mỗi phương pháp dùng để xét, mặc định 6.")
    parser.add_argument("--method-count", type=int, default=200, help="Số phương pháp cần tìm ở vòng đầu, mặc định 200.")
    parser.add_argument("--ensemble-pool", type=int, default=30, help="Số phương pháp đưa vào tổ hợp ở vòng đầu, mặc định 30.")
    parser.add_argument("--max-lag", type=int, default=12, help="Lag tối đa ở vòng đầu, mặc định 12.")
    parser.add_argument("--support-max", type=int, default=5, help="Support rà đến ở vòng đầu, mặc định 5.")
    parser.add_argument("--max-rounds", type=int, default=3, help="Số vòng tự mở rộng nếu gate fail, mặc định 3.")
    parser.add_argument("--min-base-history", type=int, default=60, help="Số kỳ tối thiểu trước vùng holdout, mặc định 60.")
    parser.add_argument("--min-ways", type=int, default=1, help="Số cách tối thiểu cần kéo ra mỗi số đúng, mặc định 1.")
    parser.add_argument("--repair-rounds", type=int, default=3, help="Số vòng học bổ sung số thiếu rồi chạy lại từ kỳ 01, mặc định 3.")
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

    result = WalkbackGateTrainer().train(
        draws,
        holdout_count=args.holdout,
        top_k=args.top,
        method_count=args.method_count,
        ensemble_pool=args.ensemble_pool,
        max_lag=args.max_lag,
        support_max=args.support_max,
        max_rounds=args.max_rounds,
        min_base_history=args.min_base_history,
        min_ways=args.min_ways,
        repair_rounds=args.repair_rounds,
        save_path=Path(args.save_path) if args.save_path else None,
    )
    print("\n".join(result.to_lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
