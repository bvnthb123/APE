"""Run the strict walk-back survivor gate.

Example:
    py walkback_train.py
    py walkback_train.py --holdout 10 --top 7 --way-top 12 --method-count 600 --min-ways 1 --repair-rounds 5
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ape.core.app import APEApplication
from ape.database.repositories import DrawRepository
from ape.patterns.audit import format_values
from ape.patterns.walkback_gate import WalkbackGateResult, WalkbackGateTrainer


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
    parser.add_argument("--top", type=int, default=6, help="Top tín hiệu cuối cùng để xếp hạng, mặc định 6.")
    parser.add_argument(
        "--way-top",
        type=int,
        default=None,
        help="Phạm vi mỗi phương pháp được xét là kéo ra một số, mặc định bằng --top. Ví dụ: --top 7 --way-top 12.",
    )
    parser.add_argument("--method-count", type=int, default=200, help="Số phương pháp cần tìm ở vòng đầu, mặc định 200.")
    parser.add_argument("--ensemble-pool", type=int, default=30, help="Số phương pháp đưa vào tổ hợp ở vòng đầu, mặc định 30.")
    parser.add_argument("--max-lag", type=int, default=12, help="Lag tối đa ở vòng đầu, mặc định 12.")
    parser.add_argument("--support-max", type=int, default=5, help="Support rà đến ở vòng đầu, mặc định 5.")
    parser.add_argument("--max-rounds", type=int, default=3, help="Số vòng tự mở rộng nếu gate fail, mặc định 3.")
    parser.add_argument("--min-base-history", type=int, default=60, help="Số kỳ tối thiểu trước vùng holdout, mặc định 60.")
    parser.add_argument("--min-ways", type=int, default=1, help="Số cách tối thiểu cần kéo ra mỗi số đúng, mặc định 1.")
    parser.add_argument(
        "--min-top-hits",
        type=int,
        default=1,
        help="Số trùng Top tối thiểu mỗi kỳ walkback cần đạt. Mặc định 1 để tránh xuất tín hiệu khi Top lịch sử từng có kỳ 0/6.",
    )
    parser.add_argument("--repair-rounds", type=int, default=3, help="Số vòng học bổ sung số thiếu rồi chạy lại từ kỳ 01, mặc định 3.")
    parser.add_argument(
        "--save-path",
        default=None,
        help="Đường dẫn file JSON để lưu bộ phương pháp sống sót khi gate pass.",
    )
    return parser


def remove_saved_file_if_needed(result: WalkbackGateResult) -> None:
    """Remove a survivor file if final top gate blocks the result."""
    if not result.saved_path:
        return
    try:
        Path(result.saved_path).unlink(missing_ok=True)
    except OSError:
        pass


def final_top_gate_lines(result: WalkbackGateResult, min_top_hits: int) -> list[str] | None:
    """Return blocking lines when per-number gate passed but final Top gate failed."""
    if not result.passed or min_top_hits <= 0:
        return None

    weak_steps = [step for step in result.steps if step.hit_count < min_top_hits]
    if not weak_steps:
        return None

    first = weak_steps[0]
    remove_saved_file_if_needed(result)
    lines = [
        "================ WALK-BACK 10 KỲ GATE ================",
        "FAIL - CHƯA ĐỦ FINAL TOP GATE",
        f"Cấu hình       : {result.attempt.label}",
        f"Số kỳ holdout  : {result.holdout_count}",
        f"Top tín hiệu   : {result.top_k}",
        f"Way Top/cách   : {result.way_top}",
        f"Ngưỡng cách/số : {result.min_ways}",
        f"Ngưỡng Top/kỳ  : {min_top_hits}",
        f"Repair đã dùng : {result.repair_used}/{result.repair_rounds}",
        f"Vùng học gốc   : {result.base_history_rows} kỳ",
        f"Kỳ pass cách   : {result.passed_steps}/{result.holdout_count}",
        f"Tổng trùng Top : {result.total_hits}/{result.holdout_count * 6}",
        f"Tổng đủ cách   : {result.total_coverage}/{result.holdout_count * 6}",
        f"Kỳ yếu Top     : {len(weak_steps)} kỳ",
        "",
    ]
    for step in result.steps:
        lines.extend(step.to_lines())
        lines.append("-" * 58)
    lines.extend(
        [
            "KẾT LUẬN",
            (
                f"Per-number gate đã qua, nhưng Final Top Gate dừng ở kỳ {first.index:02d} "
                f"({first.draw_date.strftime('%d/%m/%Y')}). Top {result.top_k} chỉ trùng "
                f"{first.hit_count}/6, thấp hơn ngưỡng {min_top_hits}."
            ),
            f"Dãy đúng kỳ yếu: {format_values(first.target_values)}",
            f"Top tín hiệu kỳ yếu: {format_values(first.signal_values)}",
            "Không xuất tín hiệu kỳ mới vì Top xếp hạng lịch sử chưa đủ lực kiểm chứng.",
            "=======================================================",
        ]
    )
    return lines


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
        way_top=args.way_top,
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
    lines = final_top_gate_lines(result, args.min_top_hits) or result.to_lines()
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
