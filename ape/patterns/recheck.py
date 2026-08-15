"""Rolling date-range recheck for historical signal strategies.

The rechecker walks through a selected historical period, replays what APE
would have shown before each target row, compares the Top K signal set with the
actual row, and selects the most stable strategy for the period.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Sequence

from ape.database.models import Draw
from ape.patterns.audit import format_values
from ape.patterns.optimizer import StrategyConfig, StrategyOptimizer


@dataclass(slots=True, frozen=True)
class RecheckRow:
    """One rolling recheck comparison row."""

    source_date: str
    target_date: str
    lag: int
    selected_values: tuple[int, ...]
    actual_values: tuple[int, ...]
    matched_values: tuple[int, ...]

    @property
    def hit_count(self) -> int:
        return len(self.matched_values)

    @property
    def status(self) -> str:
        return "HIT" if self.hit_count else "MISS"

    def to_row(self, rank: int) -> tuple[str, ...]:
        return (
            str(rank),
            self.source_date,
            self.target_date,
            f"N+{self.lag}",
            self.status,
            str(self.hit_count),
            format_values(self.selected_values),
            format_values(self.actual_values),
            format_values(self.matched_values),
        )


@dataclass(slots=True, frozen=True)
class RecheckEvaluation:
    """Measured result for one strategy in the selected period."""

    config: StrategyConfig
    rows: tuple[RecheckRow, ...]
    target_hits: int

    @property
    def tested_rows(self) -> int:
        return len(self.rows)

    @property
    def target_hit_rate(self) -> float:
        if not self.rows:
            return 0.0
        return sum(1 for row in self.rows if row.hit_count >= self.target_hits) / len(self.rows)

    @property
    def one_plus_hit_rate(self) -> float:
        if not self.rows:
            return 0.0
        return sum(1 for row in self.rows if row.hit_count >= 1) / len(self.rows)

    @property
    def zero_hit_rate(self) -> float:
        if not self.rows:
            return 0.0
        return sum(1 for row in self.rows if row.hit_count == 0) / len(self.rows)

    @property
    def average_hits(self) -> float:
        if not self.rows:
            return 0.0
        return sum(row.hit_count for row in self.rows) / len(self.rows)

    @property
    def max_hits(self) -> int:
        return max((row.hit_count for row in self.rows), default=0)

    @property
    def hit_distribution(self) -> dict[int, int]:
        return dict(Counter(row.hit_count for row in self.rows))

    @property
    def distribution_label(self) -> str:
        if not self.hit_distribution:
            return "-"
        return ", ".join(
            f"{hits} số: {count} kỳ"
            for hits, count in sorted(self.hit_distribution.items())
        )

    def sort_key(self) -> tuple[float, float, float, float, int]:
        return (
            self.target_hit_rate,
            self.average_hits,
            self.one_plus_hit_rate,
            -self.zero_hit_rate,
            self.tested_rows,
        )


@dataclass(slots=True, frozen=True)
class RecheckResult:
    """Best rolling recheck result for a selected date range."""

    start_date: date
    end_date: date
    top_k: int
    target_hits: int
    strategy_mode: str
    evaluations: tuple[RecheckEvaluation, ...]
    best: RecheckEvaluation | None
    latest_signal_values: tuple[int, ...]
    random_target_hit_rate: float
    random_one_plus_hit_rate: float
    random_average_hits: float
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_rows(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = [
            ("Chế độ", "Rolling Recheck"),
            ("Khoảng đối chiếu", f"{self.start_date.strftime('%d/%m/%Y')} đến {self.end_date.strftime('%d/%m/%Y')}"),
            ("Top tín hiệu", str(self.top_k)),
            ("Mục tiêu tối ưu", f"Trùng ít nhất {self.target_hits} số"),
            ("Mode", self.strategy_mode),
            ("Số phương án đã rà", str(len(self.evaluations))),
            (f"Baseline random - tỷ lệ ≥{self.target_hits} số", f"{self.random_target_hit_rate * 100:.2f}%"),
            ("Baseline random - tỷ lệ ≥1 số", f"{self.random_one_plus_hit_rate * 100:.2f}%"),
            ("Baseline random - số khớp TB", f"{self.random_average_hits:.3f}"),
        ]
        if self.best is None:
            rows.append(("Kết luận", "Chưa đủ dữ liệu trong khoảng đối chiếu."))
            return rows

        rows.extend(
            [
                ("Phương án ổn định nhất", self.best.config.detail_label),
                ("Số kỳ đã đối chiếu", str(self.best.tested_rows)),
                (f"Tỷ lệ đạt ≥{self.target_hits} số", f"{self.best.target_hit_rate * 100:.2f}%"),
                ("Tỷ lệ đạt ≥1 số", f"{self.best.one_plus_hit_rate * 100:.2f}%"),
                ("Tỷ lệ miss 0 số", f"{self.best.zero_hit_rate * 100:.2f}%"),
                ("Số khớp trung bình", f"{self.best.average_hits:.3f}"),
                ("Số khớp cao nhất", str(self.best.max_hits)),
                ("Phân bố số khớp", self.best.distribution_label),
                ("Top tín hiệu tham chiếu hiện tại", format_values(self.latest_signal_values)),
                ("Top 5 phương án", self.top_evaluations_label()),
            ]
        )
        for index, warning in enumerate(self.warnings, 1):
            rows.append((f"Cảnh báo {index}", warning))
        return rows

    def top_evaluations_label(self, *, limit: int = 5) -> str:
        if not self.evaluations:
            return "-"
        labels: list[str] = []
        for index, item in enumerate(self.evaluations[:limit], 1):
            labels.append(
                f"{index}. {item.config.detail_label}: "
                f"≥{self.target_hits} số {item.target_hit_rate * 100:.2f}%, "
                f"≥1 số {item.one_plus_hit_rate * 100:.2f}%, "
                f"TB {item.average_hits:.2f}"
            )
        return " | ".join(labels)

    def detail_rows(self, *, limit: int | None = 30) -> list[tuple[str, ...]]:
        if self.best is None:
            return []
        rows = list(self.best.rows)
        if limit is not None and limit > 0:
            rows = rows[-limit:]
        return [row.to_row(index) for index, row in enumerate(rows, 1)]


class StrategyRechecker:
    """Run a date-range rolling recheck over historical draws."""

    def __init__(self, optimizer: StrategyOptimizer | None = None) -> None:
        self.optimizer = optimizer or StrategyOptimizer()

    def recheck(
        self,
        draws: Sequence[Draw],
        *,
        start_date: date,
        end_date: date,
        lag_from: int = 1,
        lag_to: int = 3,
        top_k: int = 7,
        base_min_support: int = 2,
        min_training_rows: int = 30,
        target_hits: int = 1,
        strategy_mode: str = "quick",
    ) -> RecheckResult:
        if start_date > end_date:
            raise ValueError("start_date must be less than or equal to end_date")
        if lag_from < 1 or lag_to < 1 or lag_from > lag_to:
            raise ValueError("lag range must be valid and start at 1 or greater")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        if target_hits < 1:
            raise ValueError("target_hits must be at least 1")

        chronological = list(draws)
        evaluations: list[RecheckEvaluation] = []
        for lag in range(lag_from, lag_to + 1):
            for config in self.optimizer.generate_configs(
                lag=lag,
                base_min_support=base_min_support,
                strategy_mode=strategy_mode,
            ):
                evaluation = self.evaluate_config(
                    chronological,
                    config,
                    start_date=start_date,
                    end_date=end_date,
                    top_k=top_k,
                    min_training_rows=min_training_rows,
                    target_hits=target_hits,
                )
                if evaluation.tested_rows > 0:
                    evaluations.append(evaluation)

        evaluations.sort(key=lambda item: item.sort_key(), reverse=True)
        best = evaluations[0] if evaluations else None
        latest_signal_values = self.latest_signals(chronological, best.config, top_k=top_k) if best else ()
        random_target = self.optimizer.random_hit_rate_at(top_k=top_k, target_hits=target_hits)
        warnings = self.build_warnings(best, target_hits=target_hits, random_target_hit_rate=random_target)
        return RecheckResult(
            start_date=start_date,
            end_date=end_date,
            top_k=top_k,
            target_hits=target_hits,
            strategy_mode=strategy_mode,
            evaluations=tuple(evaluations),
            best=best,
            latest_signal_values=latest_signal_values,
            random_target_hit_rate=random_target,
            random_one_plus_hit_rate=self.optimizer.random_hit_rate_at(top_k=top_k, target_hits=1),
            random_average_hits=self.optimizer.random_average_hits(top_k=top_k),
            warnings=tuple(warnings),
        )

    def evaluate_config(
        self,
        draws: Sequence[Draw],
        config: StrategyConfig,
        *,
        start_date: date,
        end_date: date,
        top_k: int,
        min_training_rows: int,
        target_hits: int,
    ) -> RecheckEvaluation:
        rows: list[RecheckRow] = []
        last_anchor = len(draws) - config.lag
        if last_anchor <= min_training_rows:
            return RecheckEvaluation(config=config, rows=tuple(), target_hits=target_hits)

        for anchor_index in range(min_training_rows, last_anchor):
            target_draw = draws[anchor_index + config.lag]
            if target_draw.draw_date < start_date or target_draw.draw_date > end_date:
                continue

            known_draws = list(draws[: anchor_index + 1])
            candidates = self.optimizer.select_candidates(known_draws, config, top_k=top_k)
            selected = tuple(candidate.value for candidate in candidates)
            actual = tuple(self.optimizer.miner.values(target_draw))
            matched = tuple(sorted(set(selected) & set(actual)))
            rows.append(
                RecheckRow(
                    source_date=draws[anchor_index].draw_date.strftime("%d/%m/%Y"),
                    target_date=target_draw.draw_date.strftime("%d/%m/%Y"),
                    lag=config.lag,
                    selected_values=selected,
                    actual_values=actual,
                    matched_values=matched,
                )
            )
        return RecheckEvaluation(config=config, rows=tuple(rows), target_hits=target_hits)

    def latest_signals(
        self,
        draws: Sequence[Draw],
        config: StrategyConfig,
        *,
        top_k: int,
    ) -> tuple[int, ...]:
        signals = self.optimizer.select_candidates(draws, config, top_k=top_k)
        return tuple(signal.value for signal in signals)

    @staticmethod
    def build_warnings(
        best: RecheckEvaluation | None,
        *,
        target_hits: int,
        random_target_hit_rate: float,
    ) -> list[str]:
        if best is None:
            return ["Chưa đủ dữ liệu để rà soát trong khoảng ngày đã chọn."]
        warnings: list[str] = []
        if best.tested_rows < 20:
            warnings.append("Số kỳ đối chiếu còn thấp; kết quả dễ nhiễu.")
        if best.target_hit_rate <= random_target_hit_rate:
            warnings.append(
                f"Phương án tốt nhất chưa vượt baseline random ở mốc ≥{target_hits} số."
            )
        return warnings
