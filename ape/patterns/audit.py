"""Walk-forward strategy audit and replay for Pattern Mining.

This module replays what APE would have returned at each historical point,
compares those Top K signals with the later actual row, and selects the best
historical strategy across a lag range.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

from ape.database.models import Draw
from ape.patterns.optimizer import StrategyConfig, StrategyEvaluation, StrategyOptimizer


def format_values(values: Sequence[int]) -> str:
    """Format numeric values as a stable 2-digit signal string."""
    return " - ".join(f"{int(value):02d}" for value in values)


@dataclass(slots=True, frozen=True)
class StrategyAuditRow:
    """One replayed historical decision and its later actual result."""

    source_date: str
    target_date: str
    lag: int
    strategy_label: str
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
            self.strategy_label,
        )


@dataclass(slots=True, frozen=True)
class StrategyAuditResult:
    """Best audit result and detailed replay rows."""

    best_evaluation: StrategyEvaluation | None
    lag_evaluations: tuple[StrategyEvaluation, ...]
    replay_rows: tuple[StrategyAuditRow, ...]
    target_hits: int
    top_k: int
    lag_from: int
    lag_to: int
    random_target_hit_rate: float
    random_one_plus_hit_rate: float
    random_average_hits: float
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def hit_distribution(self) -> dict[int, int]:
        return dict(Counter(row.hit_count for row in self.replay_rows))

    @property
    def average_hits(self) -> float:
        if not self.replay_rows:
            return 0.0
        return sum(row.hit_count for row in self.replay_rows) / len(self.replay_rows)

    @property
    def target_hit_rate(self) -> float:
        if not self.replay_rows:
            return 0.0
        return sum(1 for row in self.replay_rows if row.hit_count >= self.target_hits) / len(self.replay_rows)

    @property
    def one_plus_hit_rate(self) -> float:
        if not self.replay_rows:
            return 0.0
        return sum(1 for row in self.replay_rows if row.hit_count >= 1) / len(self.replay_rows)

    @property
    def zero_hit_rate(self) -> float:
        if not self.replay_rows:
            return 0.0
        return sum(1 for row in self.replay_rows if row.hit_count == 0) / len(self.replay_rows)

    @property
    def max_hits(self) -> int:
        return max((row.hit_count for row in self.replay_rows), default=0)

    @property
    def distribution_label(self) -> str:
        distribution = self.hit_distribution
        if not distribution:
            return "-"
        return ", ".join(
            f"{hits} số: {count} kỳ" for hits, count in sorted(distribution.items())
        )

    def to_rows(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = [
            ("Chế độ", "Strategy Audit Replay"),
            ("Khoảng độ trễ rà soát", f"N+{self.lag_from} đến N+{self.lag_to}"),
            ("Top tín hiệu", str(self.top_k)),
            ("Mục tiêu", f"Trùng ít nhất {self.target_hits} số"),
            ("Số phương án lag tốt nhất đã so", str(len(self.lag_evaluations))),
            (
                f"Baseline random - tỷ lệ ≥{self.target_hits} số",
                f"{self.random_target_hit_rate * 100:.4f}%",
            ),
            ("Baseline random - tỷ lệ ≥1 số", f"{self.random_one_plus_hit_rate * 100:.2f}%"),
            ("Baseline random - số khớp TB", f"{self.random_average_hits:.3f}"),
        ]
        if self.best_evaluation is None:
            rows.append(("Kết luận", "Chưa đủ dữ liệu để audit chiến lược."))
            return rows

        best = self.best_evaluation
        rows.extend(
            [
                ("Phương án tối ưu", best.config.detail_label),
                ("Số kỳ replay", str(len(self.replay_rows))),
                (
                    f"Tỷ lệ replay đạt ≥{self.target_hits} số",
                    f"{self.target_hit_rate * 100:.4f}%",
                ),
                ("Tỷ lệ replay đạt ≥1 số", f"{self.one_plus_hit_rate * 100:.2f}%"),
                ("Tỷ lệ replay miss 0 số", f"{self.zero_hit_rate * 100:.2f}%"),
                ("Số khớp trung bình replay", f"{self.average_hits:.3f}"),
                ("Số khớp cao nhất replay", str(self.max_hits)),
                ("Phân bố số khớp replay", self.distribution_label),
                (
                    f"Chênh lệch ≥{self.target_hits} số so với random",
                    f"{(self.target_hit_rate - self.random_target_hit_rate) * 100:+.4f}%",
                ),
                ("Top lag/phương án", self.top_lag_label()),
            ]
        )
        for index, warning in enumerate(self.warnings, 1):
            rows.append((f"Cảnh báo {index}", warning))
        return rows

    def top_lag_label(self, *, limit: int = 5) -> str:
        if not self.lag_evaluations:
            return "-"
        labels = []
        for index, item in enumerate(self.lag_evaluations[:limit], 1):
            labels.append(
                f"{index}. {item.config.detail_label}: "
                f"≥{self.target_hits} số {item.target_hit_rate * 100:.4f}%, "
                f"≥1 số {item.one_plus_hit_rate * 100:.2f}%, "
                f"TB {item.average_hits:.2f}"
            )
        return " | ".join(labels)

    def detail_rows(self, *, limit: int | None = 20) -> list[tuple[str, ...]]:
        rows = list(self.replay_rows)
        if limit is not None and limit > 0:
            rows = rows[-limit:]
        return [row.to_row(index) for index, row in enumerate(rows, 1)]


class StrategyAuditor:
    """Replay and audit historical Strategy Optimizer outputs."""

    def __init__(self, optimizer: StrategyOptimizer | None = None) -> None:
        self.optimizer = optimizer or StrategyOptimizer()

    def audit(
        self,
        draws: Sequence[Draw],
        *,
        lag_from: int = 1,
        lag_to: int = 3,
        top_k: int = 10,
        base_min_support: int = 2,
        min_training_rows: int = 30,
        target_hits: int = 4,
    ) -> StrategyAuditResult:
        if lag_from < 1 or lag_to < 1:
            raise ValueError("lag range must start at 1 or greater")
        if lag_from > lag_to:
            raise ValueError("lag_from must be less than or equal to lag_to")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        if target_hits < 1:
            raise ValueError("target_hits must be at least 1")

        best_by_lag: list[StrategyEvaluation] = []
        for lag in range(lag_from, lag_to + 1):
            result = self.optimizer.optimize(
                draws,
                lag=lag,
                top_k=top_k,
                base_min_support=base_min_support,
                min_training_rows=min_training_rows,
                target_hits=target_hits,
            )
            if result.best is not None:
                best_by_lag.append(result.best)

        best_by_lag.sort(key=lambda item: item.sort_key(), reverse=True)
        best = best_by_lag[0] if best_by_lag else None
        replay_rows = self.replay_rows(
            draws,
            best.config,
            top_k=top_k,
            min_training_rows=min_training_rows,
        ) if best is not None else []

        random_target = self.optimizer.random_hit_rate_at(
            top_k=top_k,
            target_hits=target_hits,
        )
        warnings = self.build_warnings(
            best,
            replay_rows,
            target_hits=target_hits,
            random_target_hit_rate=random_target,
        )
        return StrategyAuditResult(
            best_evaluation=best,
            lag_evaluations=tuple(best_by_lag),
            replay_rows=tuple(replay_rows),
            target_hits=target_hits,
            top_k=top_k,
            lag_from=lag_from,
            lag_to=lag_to,
            random_target_hit_rate=random_target,
            random_one_plus_hit_rate=self.optimizer.random_hit_rate_at(top_k=top_k, target_hits=1),
            random_average_hits=self.optimizer.random_average_hits(top_k=top_k),
            warnings=tuple(warnings),
        )

    def replay_rows(
        self,
        draws: Sequence[Draw],
        config: StrategyConfig,
        *,
        top_k: int,
        min_training_rows: int,
    ) -> list[StrategyAuditRow]:
        rows: list[StrategyAuditRow] = []
        last_anchor = len(draws) - config.lag
        if last_anchor <= min_training_rows:
            return rows

        for anchor_index in range(min_training_rows, last_anchor):
            known_draws = list(draws[: anchor_index + 1])
            candidates = self.optimizer.select_candidates(
                known_draws,
                config,
                top_k=top_k,
            )
            selected = tuple(candidate.value for candidate in candidates)
            actual_draw = draws[anchor_index + config.lag]
            actual = tuple(self.optimizer.miner.values(actual_draw))
            matched = tuple(sorted(set(selected) & set(actual)))
            rows.append(
                StrategyAuditRow(
                    source_date=draws[anchor_index].draw_date.strftime("%d/%m/%Y"),
                    target_date=actual_draw.draw_date.strftime("%d/%m/%Y"),
                    lag=config.lag,
                    strategy_label=config.detail_label,
                    selected_values=selected,
                    actual_values=actual,
                    matched_values=matched,
                )
            )
        return rows

    @staticmethod
    def build_warnings(
        best: StrategyEvaluation | None,
        replay_rows: Sequence[StrategyAuditRow],
        *,
        target_hits: int,
        random_target_hit_rate: float,
    ) -> list[str]:
        if best is None:
            return ["Chưa đủ dữ liệu để chọn phương án tối ưu."]
        warnings: list[str] = []
        if len(replay_rows) < 30:
            warnings.append("Số kỳ replay thấp; kết quả dễ bị nhiễu hoặc overfit.")
        target_rate = (
            sum(1 for row in replay_rows if row.hit_count >= target_hits) / len(replay_rows)
            if replay_rows
            else 0.0
        )
        if target_rate <= 0:
            warnings.append(
                f"Trong replay chưa có kỳ nào đạt ≥{target_hits} số; cần hạ kỳ vọng hoặc tăng dữ liệu."
            )
        elif target_rate <= random_target_hit_rate:
            warnings.append(
                f"Phương án replay chưa vượt baseline random ở mốc ≥{target_hits} số."
            )
        return warnings
