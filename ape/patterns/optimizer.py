"""Strategy optimization for historical Pattern Mining.

The optimizer compares multiple historical-signal strategies with walk-forward
backtesting. It can rank strategies by a configurable hit threshold, for
example the historical rate of at least 4 overlaps between a Top 10 signal set
and the target row.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from math import comb
from statistics import mean
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
    lag_offsets: tuple[int, ...] = (0,)

    @property
    def effective_lags(self) -> tuple[int, ...]:
        return tuple(sorted({max(1, self.lag + offset) for offset in self.lag_offsets}))

    @property
    def detail_label(self) -> str:
        structure = "có cấu trúc" if self.use_structure else "không cấu trúc"
        repeat = "có độ lặp" if self.use_repeat_overlap else "không độ lặp"
        lag_label = ", ".join(f"N+{lag}" for lag in self.effective_lags)
        return (
            f"{self.name} · {lag_label} · support ≥ {self.min_support} · "
            f"{structure} · {repeat}"
        )


@dataclass(slots=True, frozen=True)
class StrategyEvaluation:
    """Walk-forward evaluation result for one strategy."""

    config: StrategyConfig
    top_k: int
    target_hits: int
    tested_rows: int
    average_hits: float
    target_hit_rate: float
    one_plus_hit_rate: float
    two_plus_hit_rate: float
    zero_hit_rate: float
    max_hits: int
    total_hits: int
    hit_distribution: dict[int, int] = field(default_factory=dict)

    def sort_key(self) -> tuple[float, float, float, float, float, int]:
        """Higher is better for selecting a strategy."""
        return (
            self.target_hit_rate,
            self.average_hits,
            self.two_plus_hit_rate,
            self.one_plus_hit_rate,
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
    target_hits: int
    random_target_hit_rate: float
    random_one_plus_hit_rate: float
    random_average_hits: float

    def latest_signals(
        self,
        optimizer: "StrategyOptimizer",
        draws: Sequence[Draw],
    ) -> list[CandidateSignal]:
        if self.best is None:
            return []
        return optimizer.select_candidates(
            draws,
            self.best.config,
            top_k=self.best.top_k,
        )

    def signal_rows(
        self,
        optimizer: "StrategyOptimizer",
        draws: Sequence[Draw],
    ) -> list[tuple[str, ...]]:
        return [
            signal.to_row(rank)
            for rank, signal in enumerate(self.latest_signals(optimizer, draws), 1)
        ]

    def to_rows(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = [
            ("Chế độ", "Target-Hit Strategy Optimizer"),
            ("Mục tiêu tối ưu", f"Trùng ít nhất {self.target_hits} số"),
            ("Số phương án đã thử", str(len(self.evaluations))),
            (
                f"Baseline random - tỷ lệ ≥{self.target_hits} số",
                f"{self.random_target_hit_rate * 100:.4f}%",
            ),
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
        warning = self.warning_label(best)
        rows.extend(
            [
                ("Phương án tốt nhất", best.config.detail_label),
                ("Số kỳ kiểm định", str(best.tested_rows)),
                (
                    f"Tỷ lệ trùng ít nhất {self.target_hits} số",
                    f"{best.target_hit_rate * 100:.4f}%",
                ),
                ("Tỷ lệ trùng ít nhất 1 số", f"{best.one_plus_hit_rate * 100:.2f}%"),
                ("Tỷ lệ không trùng số nào", f"{best.zero_hit_rate * 100:.2f}%"),
                ("Tỷ lệ trùng ít nhất 2 số", f"{best.two_plus_hit_rate * 100:.2f}%"),
                ("Số khớp trung bình", f"{best.average_hits:.3f}"),
                ("Số khớp cao nhất", str(best.max_hits)),
                (
                    f"Chênh lệch ≥{self.target_hits} số so với random",
                    f"{(best.target_hit_rate - self.random_target_hit_rate) * 100:+.4f}%",
                ),
                ("Phân bố số khớp", best.distribution_label),
                ("Top 5 phương án", self.top_strategy_label(limit=5)),
            ]
        )
        if warning:
            rows.append(("Cảnh báo", warning))
        return rows

    def warning_label(self, best: StrategyEvaluation) -> str:
        if best.tested_rows < 30:
            return "Số kỳ kiểm định thấp; kết quả dễ bị nhiễu hoặc overfit."
        if best.target_hit_rate <= 0:
            return (
                f"Chưa có phương án nào đạt mốc ≥{self.target_hits} số trong backtest; "
                "nên xem đây là mục tiêu nghiên cứu, không phải kết quả có thể cam kết."
            )
        if best.target_hit_rate <= self.random_target_hit_rate:
            return (
                f"Phương án tốt nhất chưa vượt baseline random ở mốc ≥{self.target_hits} số."
            )
        return ""

    def top_strategy_label(self, *, limit: int = 5) -> str:
        if not self.evaluations:
            return "-"
        parts = []
        for index, item in enumerate(self.evaluations[:limit], 1):
            parts.append(
                f"{index}. {item.config.name} "
                f"support≥{item.config.min_support}: "
                f"≥{self.target_hits} số {item.target_hit_rate * 100:.4f}%, "
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
                max(1, base_min_support - 2),
                max(1, base_min_support - 1),
                max(1, base_min_support),
                max(1, base_min_support + 1),
                max(1, base_min_support + 2),
                max(1, base_min_support + 3),
                max(1, base_min_support + 4),
            }
        )
        modes = (
            ("Rule thuần", False, False),
            ("Rule + cấu trúc", True, False),
            ("Rule + độ lặp", False, True),
            ("Rule + cấu trúc + độ lặp", True, True),
        )
        lag_windows = (
            ("lag đơn", (0,)),
            ("ensemble gần", (-1, 0, 1)),
            ("ensemble tiến", (0, 1, 2)),
            ("ensemble rộng", (-2, -1, 0, 1, 2)),
        )
        configs: list[StrategyConfig] = []
        for support in supports:
            for mode_name, use_structure, use_repeat_overlap in modes:
                for lag_name, lag_offsets in lag_windows:
                    configs.append(
                        StrategyConfig(
                            name=f"{mode_name} / {lag_name}",
                            lag=lag,
                            min_support=support,
                            use_structure=use_structure,
                            use_repeat_overlap=use_repeat_overlap,
                            lag_offsets=lag_offsets,
                        )
                    )
        return configs

    def select_candidates(
        self,
        draws: Sequence[Draw],
        config: StrategyConfig,
        *,
        top_k: int = 10,
    ) -> list[CandidateSignal]:
        """Return Top K signals for a strategy, including optional lag ensembles."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        by_value: dict[int, dict[str, object]] = {}
        for lag in config.effective_lags:
            distance = abs(lag - config.lag)
            lag_weight = 1.0 if distance == 0 else 0.75 / distance
            signals = self.miner.current_signals(
                draws,
                lag=lag,
                min_support=config.min_support,
                top_n=max(top_k * 4, 30),
                use_structure=config.use_structure,
                use_repeat_overlap=config.use_repeat_overlap,
            )
            for signal in signals:
                bucket = by_value.setdefault(
                    signal.value,
                    {
                        "score": 0.0,
                        "support": 0,
                        "rule_count": 0,
                        "lifts": [],
                        "max_lift": 0.0,
                        "sources": set(),
                    },
                )
                bucket["score"] = float(bucket["score"]) + signal.score * lag_weight
                bucket["support"] = int(bucket["support"]) + signal.support
                bucket["rule_count"] = int(bucket["rule_count"]) + signal.rule_count
                bucket["lifts"].append(signal.average_lift)
                bucket["max_lift"] = max(float(bucket["max_lift"]), signal.max_lift)
                bucket["sources"].update(signal.matched_sources)

        combined: list[CandidateSignal] = []
        for value, bucket in by_value.items():
            lifts = list(bucket["lifts"])
            combined.append(
                CandidateSignal(
                    value=value,
                    score=float(bucket["score"]),
                    support=int(bucket["support"]),
                    rule_count=int(bucket["rule_count"]),
                    average_lift=mean(lifts) if lifts else 0.0,
                    max_lift=float(bucket["max_lift"]),
                    matched_sources=tuple(sorted(bucket["sources"])),
                )
            )

        combined.sort(
            key=lambda item: (
                item.score,
                item.support,
                item.average_lift,
                item.max_lift,
            ),
            reverse=True,
        )
        return combined[:top_k]

    def evaluate(
        self,
        draws: Sequence[Draw],
        config: StrategyConfig,
        *,
        top_k: int = 10,
        min_training_rows: int = 60,
        target_hits: int = 1,
    ) -> StrategyEvaluation:
        if config.lag < 1:
            raise ValueError("lag must be at least 1")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        if target_hits < 1:
            raise ValueError("target_hits must be at least 1")

        last_anchor = len(draws) - config.lag
        if last_anchor <= min_training_rows:
            return StrategyEvaluation(
                config=config,
                top_k=top_k,
                target_hits=target_hits,
                tested_rows=0,
                average_hits=0.0,
                target_hit_rate=0.0,
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
            candidates = self.select_candidates(
                known_draws,
                config,
                top_k=top_k,
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
        target_plus = sum(1 for hits in hits_per_row if hits >= target_hits)
        return StrategyEvaluation(
            config=config,
            top_k=top_k,
            target_hits=target_hits,
            tested_rows=tested_rows,
            average_hits=total_hits / tested_rows if tested_rows else 0.0,
            target_hit_rate=target_plus / tested_rows if tested_rows else 0.0,
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
        target_hits: int = 1,
    ) -> StrategyOptimizationResult:
        evaluations = [
            self.evaluate(
                draws,
                config,
                top_k=top_k,
                min_training_rows=min_training_rows,
                target_hits=target_hits,
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
            target_hits=target_hits,
            random_target_hit_rate=self.random_hit_rate_at(top_k=top_k, target_hits=target_hits),
            random_one_plus_hit_rate=self.random_hit_rate_at(top_k=top_k, target_hits=1),
            random_average_hits=self.random_average_hits(top_k=top_k),
        )

    def random_average_hits(self, *, top_k: int) -> float:
        return top_k * self.draw_size / self.pool_size

    def random_hit_rate_at(self, *, top_k: int, target_hits: int) -> float:
        """Hypergeometric baseline for at least target_hits overlaps."""
        if target_hits <= 0:
            return 1.0
        if top_k <= 0:
            return 0.0
        if target_hits > min(top_k, self.draw_size):
            return 0.0
        if top_k >= self.pool_size:
            return 1.0

        total = comb(self.pool_size, self.draw_size)
        max_hits = min(top_k, self.draw_size)
        probability = 0.0
        for hits in range(target_hits, max_hits + 1):
            if self.draw_size - hits > self.pool_size - top_k:
                continue
            probability += (
                comb(top_k, hits)
                * comb(self.pool_size - top_k, self.draw_size - hits)
                / total
            )
        return probability

    def random_one_plus_hit_rate(self, *, top_k: int) -> float:
        return self.random_hit_rate_at(top_k=top_k, target_hits=1)
