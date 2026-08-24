"""Clean holdout forecasting for a user-supplied unseen target row.

This module is intentionally different from target learning. Target learning is
allowed to fit methods against a known row. Holdout forecasting is stricter: it
selects a strategy only from historical walk-forward performance, then compares
that forecast with the target row after the forecast is produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from ape.database.models import Draw
from ape.patterns.audit import format_values
from ape.patterns.optimizer import StrategyOptimizer, StrategyOptimizationResult
from ape.patterns.target_learning import next_auto_draw_date, parse_target_numbers


@dataclass(slots=True, frozen=True)
class ForecastDepthResult:
    """Hit result for one forecast depth."""

    depth: int
    values: tuple[int, ...]
    matched_values: tuple[int, ...]

    @property
    def hit_count(self) -> int:
        return len(self.matched_values)


@dataclass(slots=True, frozen=True)
class HoldoutForecastResult:
    """Clean forecast result for one held-out target row."""

    target_values: tuple[int, ...]
    forecast_date: date
    train_rows: int
    train_first_date: date | None
    train_last_date: date | None
    optimization: StrategyOptimizationResult
    depth_results: tuple[ForecastDepthResult, ...]

    @property
    def best_depth_result(self) -> ForecastDepthResult | None:
        return self.depth_results[0] if self.depth_results else None

    @property
    def best_signal_values(self) -> tuple[int, ...]:
        best = self.best_depth_result
        return best.values if best else tuple()

    @property
    def best_matched_values(self) -> tuple[int, ...]:
        best = self.best_depth_result
        return best.matched_values if best else tuple()

    @property
    def best_hit_count(self) -> int:
        best = self.best_depth_result
        return best.hit_count if best else 0

    def to_lines(self) -> list[str]:
        lines = [
            "================ CLEAN HOLDOUT FORECAST TEST ================",
            "Chế độ: DỰ BÁO SẠCH - không dùng dãy kiểm định để chọn phương pháp.",
            f"Dữ liệu dùng để chọn phương pháp: {self.train_rows} kỳ"
            + (
                f" · từ {self.train_first_date:%d/%m/%Y} đến {self.train_last_date:%d/%m/%Y}"
                if self.train_first_date and self.train_last_date
                else ""
            ),
            f"Ngày kiểm định giả định: {self.forecast_date:%d/%m/%Y}",
            f"Dãy kiểm định: {format_values(self.target_values)}",
            "",
        ]

        best = self.optimization.best
        if best is None:
            lines.append("Không đủ dữ liệu để chọn phương pháp bằng backtest.")
            return lines

        lines.extend(
            [
                "PHƯƠNG ÁN ĐƯỢC CHỌN TRƯỚC KHI BIẾT KẾT QUẢ",
                f"Cách tính: {best.config.detail_label}",
                f"Số kỳ backtest: {best.tested_rows}",
                f"Tỷ lệ ≥1 số lịch sử: {best.one_plus_hit_rate * 100:.2f}%",
                f"Tỷ lệ ≥2 số lịch sử: {best.two_plus_hit_rate * 100:.2f}%",
                f"Tỷ lệ 0 số lịch sử: {best.zero_hit_rate * 100:.2f}%",
                f"Số khớp trung bình lịch sử: {best.average_hits:.3f}",
                f"Số khớp cao nhất lịch sử: {best.max_hits}",
                f"Phân bố lịch sử: {best.distribution_label}",
                "",
                "KẾT QUẢ SO VỚI DÃY KIỂM ĐỊNH",
            ]
        )

        for row in self.depth_results:
            matched = format_values(row.matched_values) if row.matched_values else "-"
            lines.append(
                f"Top {row.depth:02d}: {format_values(row.values)} · khớp {row.hit_count}/6 · {matched}"
            )

        lines.extend(
            [
                "",
                "KẾT LUẬN",
                self.conclusion_label(),
                "",
                "Ghi chú: Đây mới là phép kiểm định độ chính xác sạch. Target Learning có thể khớp cao hơn vì nó được phép nhìn dãy đã biết để fit phương pháp.",
            ]
        )
        return lines

    def conclusion_label(self) -> str:
        if self.best_hit_count <= 0:
            return "Top chính không trùng số nào. Không nên xem bộ tín hiệu này là đạt yêu cầu cho kỳ kiểm định."
        if self.best_hit_count == 1:
            return "Top chính chỉ khớp 1/6. Tín hiệu yếu, cần thêm backtest hoặc đổi phương án."
        if self.best_hit_count == 2:
            return "Top chính khớp 2/6. Có tín hiệu nhưng chưa đủ mạnh."
        return f"Top chính khớp {self.best_hit_count}/6. Có tín hiệu đáng theo dõi nhưng vẫn không bảo đảm kỳ sau."


class HoldoutForecaster:
    """Select a strategy from historical backtest, then test against a hidden row."""

    def __init__(self, optimizer: StrategyOptimizer | None = None) -> None:
        self.optimizer = optimizer or StrategyOptimizer()

    def forecast(
        self,
        draws: Sequence[Draw],
        target_values: Sequence[int] | str,
        *,
        top_k: int = 7,
        lag: int = 1,
        base_min_support: int = 3,
        min_training_rows: int = 60,
        target_hits: int = 1,
        strategy_mode: str = "full",
        max_history_rows: int | None = None,
        depths: Sequence[int] = (7, 10, 15, 20, 30),
    ) -> HoldoutForecastResult:
        source_draws = list(draws)
        if len(source_draws) < min_training_rows + lag + 5:
            raise ValueError("Chưa đủ dữ liệu lịch sử để chạy clean holdout forecast.")

        target = (
            parse_target_numbers(target_values)
            if isinstance(target_values, str)
            else tuple(sorted(int(value) for value in target_values))
        )
        if len(target) != 6:
            raise ValueError("Dãy kiểm định phải có đúng 6 số.")

        optimization = self.optimizer.optimize(
            source_draws,
            lag=lag,
            top_k=top_k,
            base_min_support=base_min_support,
            min_training_rows=min_training_rows,
            target_hits=target_hits,
            strategy_mode=strategy_mode,
            max_history_rows=max_history_rows,
        )

        depth_results: list[ForecastDepthResult] = []
        if optimization.best is not None:
            for depth in depths:
                signals = self.optimizer.select_candidates(
                    self.optimizer.recent_draws(source_draws, optimization.history_rows_used or None),
                    optimization.best.config,
                    top_k=depth,
                )
                values = tuple(signal.value for signal in signals)
                matched = tuple(sorted(set(values) & set(target)))
                depth_results.append(
                    ForecastDepthResult(
                        depth=depth,
                        values=values,
                        matched_values=matched,
                    )
                )

        return HoldoutForecastResult(
            target_values=target,
            forecast_date=next_auto_draw_date(source_draws),
            train_rows=len(source_draws),
            train_first_date=source_draws[0].draw_date if source_draws else None,
            train_last_date=source_draws[-1].draw_date if source_draws else None,
            optimization=optimization,
            depth_results=tuple(depth_results),
        )
