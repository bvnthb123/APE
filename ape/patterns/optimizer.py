"""Strategy optimization for historical Pattern Mining.

The optimizer compares multiple historical-signal strategies with walk-forward
backtesting. It ranks strategies by the historical rate of at least one overlap
between the Top K signal set and the target row.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import comb
from typing import Sequence

from ape.database.models import Draw
from ape.patterns.mining import CandidateSignal, PatternMiner


@dataclass(slots=True, frozen=True)
class StrategyConfig:
    """One historical-signal strategy configuration."""

    name: str
    lag: int
    min_support: int
    use_structure: bool
    use_repeat_overlap: bool

    @property
    def detail_label(self) -> str:
        structure = "có cấu trúc" if self.use_structure else "không cấu trúc"
        repeat = "có độ lặp" if self.use_repeat_overlap else "không độ lặp"
        return (
            f"{self.name} · N+{self.lag} · support ≥ {self.min_support} · "
            f"{structure} · {repeat}"
        )


@dataclass(slots=True, frozen=True)
class StrategyEvaluation:
    """Walk-forward evaluation result for one strategy."""

    config: StrategyConfig
    top_k: int
    tested_rows: int
    average_hits: float
    one_plus_hit_rate: float
    two_plus_hit_rate: float
    zero_hit_rate: float
    max_hits: int
    total_hits: int
    hit_distribution: dict[int, int] = field(default_factory=dict)

    def sort_key(self) -> tuple[float, float, float, float, int]:
        """Higher is better for selecting a strategy."""
        return (
            self.one_plus_hit_rate,
            self.average_hits,
            self.two_plus_hit_rate,
            -self.zero_hit_rate,
            self.tested_rows,
        )

    @property
    def distribution_label(self) -> str:
        if not self.hit_distribution:
            return "-"
        return ", ".join(
            f"{hits} số: {count} kỳ"
            for hits, count in sorted(self.hit_distribution.items())
        )


@dataclass(slots=True, frozen=True)
class StrategyOptimizationResult:
    """Best strategy plus all strategy evaluations."""

    best: StrategyEvaluation | None
    evaluations: tuple[StrategyEvaluation, ...]
    random_one_plus_hit_rate: float
    random_average_hits: float

    def latest_signals(
        self,
        miner: PatternMiner,
        draws: Sequence[Draw],
    ) -> list[CandidateSignal]:
        if self.best is None:
            return []
        config = self.best.config
        return miner.current_signals(
            draws,
            lag=config.lag,
            min_support=config.min_support,
            top_n=self.best.top_k,
            use_structure=config.use_structure,
            use_repeat_overlap=config.use_repeat_overlap,
        )

    def signal_rows(
        self,
        miner: PatternMiner,
        draws: Sequence[Draw],
    ) -> list[tuple[str, ...]]:
        return [
            signal.to_row(rank)
            for rank, signal in enumerate(self.latest_signals(miner, draws), 1)
        ]

    def to_rows(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = [
            ("Chế độ", "Strategy Optimizer"),
            ("Số phương án đã thử", str(len(self.evaluations))),
            (
                "Baseline random - tỷ lệ ≥1 số",
                f"{self.random_one_plus_hit_rate * 100:.2f}%",
            ),
            (
                "Baseline random - số khớp TB",
                f"{self.random_average_hits:.3f}",
            ),
        ]
        if self.best is None:
            rows.append(("Kết luận", "Chưa đủ dữ liệu để kiểm định chiến lược."))
            return rows

        best = self.best
        rows.extend(
            [
                ("Phương án tốt nhất", best.config.detail_label),
                ("Số kỳ kiểm định", str(best.tested_rows)),
                ("Tỷ lệ trùng ít nhất 1 số", f"{best.one_plus_hit_rate * 100:.2f}%"),
                ("Tỷ lệ không trùng số nào", f"{best.zero_hit_rate * 100:.2f}%"),
                ("Tỷ lệ trùng ít nhất 2 số", f"{best.two_plus_hit_rate * 100:.2f}%"),
                ("Số khớp trung bình", f"{best.average_hits:.3f}"),
                ("Số khớp cao nhất", str(best.max_hits)),
                (
                    "Chênh lệch ≥1 số so với random",
                    f"{(best.one_plus_hit_rate - self.random_one_plus_hit_rate) * 100:+.2f}%",
                ),
                ("Phân bố số khớp", best.distribution_label),
                ("Top 3 phương án", self.top_strategy_label(limit=3)),
            ]
        )
        return rows

    def top_strategy_label(self, *, limit: int = 3) -> str:
        if not self.evaluations:
            return "-"
        parts = []
        for index, item in enumerate(self.evaluations[:limit], 1):
            parts.append(
                f"{index}. {item.config.name} "
                f"support≥{item.config.min_support}: "
                f"≥1 số {item.one_plus_hit_rate * 100:.2f}%, "
                f"TB {item.average_hits:.2f}"
            )
        return " | ".join(parts)


class StrategyOptimizer:
    """Compare multiple historical strategies and select the best backtest result."""

    def __init__(
        self,
        miner: PatternMiner | None = None,
        *,
        value_min: int = 1,
        value_max: int = 45,
        draw_size: int = 6,
    ) -> None:
        self.miner = miner or PatternMiner(value_min=value_min, value_max=value_max)
        self.value_min = value_min
        self.value_max = value_max
        self.draw_size = draw_size

    @property
    def pool_size(self) -> int:
        return self.value_max - self.value_min + 1

    def generate_configs(
        self,
        *,
        lag: int,
        base_min_support: int,
    ) -> list[StrategyConfig]:
        supports = sorted(
            {
                1,
                max(1, base_min_support - 1),
                max(1, base_min_support),
                max(1, base_min_support + 1),
                max(1, base_min_support + 2),
            }
        )
        modes = (
            ("Rule thuần", False, False),
            ("Rule + cấu trúc", True, False),
            ("Rule + độ lặp", False, True),
            ("Rule + cấu trúc + độ lặp", True, True),
        )
        return [
            StrategyConfig(
                name=name,
                lag=lag,
                min_support=support,
                use_structure=use_structure,
                use_repeat_overlap=use_repeat_overlap,
            )
            for support in supports
            for name, use_structure, use_repeat_overlap in modes
        ]

    def evaluate(
        self,
        draws: Sequence[Draw],
        config: StrategyConfig,
        *,
        top_k: int = 10,
        min_training_rows: int = 60,
    ) -> StrategyEvaluation:
        if config.lag < 1:
            raise ValueError("lag must be at least 1")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        last_anchor = len(draws) - config.lag
        if last_anchor <= min_training_rows:
            return StrategyEvaluation(
                config=config,
                top_k=top_k,
                tested_rows=0,
                average_hits=0.0,
                one_plus_hit_rate=0.0,
                two_plus_hit_rate=0.0,
                zero_hit_rate=0.0,
                max_hits=0,
                total_hits=0,
                hit_distribution={},
            )

        hits_per_row: list[int] = []
        for anchor_index in range(min_training_rows, last_anchor):
            known_draws = list(draws[: anchor_index + 1])
            candidates = self.miner.current_signals(
                known_draws,
                lag=config.lag,
                min_support=config.min_support,
                top_n=top_k,
                use_structure=config.use_structure,
                use_repeat_overlap=config.use_repeat_overlap,
            )
            selected = {candidate.value for candidate in candidates}
            actual = set(self.miner.values(draws[anchor_index + config.lag]))
            hits_per_row.append(len(selected & actual))

        tested_rows = len(hits_per_row)
        distribution = dict(Counter(hits_per_row))
        total_hits = sum(hits_per_row)
        zero_hits = sum(1 for hits in hits_per_row if hits == 0)
        one_plus = sum(1 for hits in hits_per_row if hits >= 1)
        two_plus = sum(1 for hits in hits_per_row if hits >= 2)
        return StrategyEvaluation(
            config=config,
            top_k=top_k,
            tested_rows=tested_rows,
            average_hits=total_hits / tested_rows if tested_rows else 0.0,
            one_plus_hit_rate=one_plus / tested_rows if tested_rows else 0.0,
            two_plus_hit_rate=two_plus / tested_rows if tested_rows else 0.0,
            zero_hit_rate=zero_hits / tested_rows if tested_rows else 0.0,
            max_hits=max(hits_per_row) if hits_per_row else 0,
            total_hits=total_hits,
            hit_distribution=distribution,
        )

    def optimize(
        self,
        draws: Sequence[Draw],
        *,
        lag: int = 3,
        top_k: int = 10,
        base_min_support: int = 3,
        min_training_rows: int = 60,
    ) -> StrategyOptimizationResult:
        evaluations = [
            self.evaluate(
                draws,
                config,
                top_k=top_k,
                min_training_rows=min_training_rows,
            )
            for config in self.generate_configs(
                lag=lag,
                base_min_support=base_min_support,
            )
        ]
        evaluations.sort(key=lambda item: item.sort_key(), reverse=True)
        best = evaluations[0] if evaluations and evaluations[0].tested_rows > 0 else None
        return StrategyOptimizationResult(
            best=best,
            evaluations=tuple(evaluations),
            random_one_plus_hit_rate=self.random_one_plus_hit_rate(top_k=top_k),
            random_average_hits=self.random_average_hits(top_k=top_k),
        )

    def random_average_hits(self, *, top_k: int) -> float:
        return top_k * self.draw_size / self.pool_size

    def random_one_plus_hit_rate(self, *, top_k: int) -> float:
        if top_k <= 0:
            return 0.0
        if top_k >= self.pool_size:
            return 1.0
        misses = comb(self.pool_size - top_k, self.draw_size)
        total = comb(self.pool_size, self.draw_size)
        return 1 - misses / total
