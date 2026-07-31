"""Historical transition-pattern mining and walk-forward backtesting.

This module intentionally describes historical signals only. It does not label
outputs as predictions and does not claim future results are knowable.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import mean
from typing import Iterable, Sequence

from ape.database.models import Draw


@dataclass(slots=True, frozen=True)
class PatternRule:
    """A historical transition rule from one value to another after a lag."""

    source_value: int
    target_value: int
    lag: int
    source_count: int
    cooccurrence_count: int
    conditional_rate: float
    baseline_rate: float
    lift: float
    delta: float
    score: float

    def to_row(self, rank: int) -> tuple[str, ...]:
        return (
            str(rank),
            f"{self.source_value:02d}",
            f"{self.target_value:02d}",
            f"N+{self.lag}",
            str(self.source_count),
            str(self.cooccurrence_count),
            f"{self.conditional_rate * 100:.2f}%",
            f"{self.baseline_rate * 100:.2f}%",
            f"{self.lift:.2f}",
            f"{self.score:.4f}",
        )


@dataclass(slots=True, frozen=True)
class CandidateSignal:
    """Aggregated historical signal for a target value from a reference draw."""

    value: int
    score: float
    support: int
    rule_count: int
    average_lift: float
    max_lift: float
    matched_sources: tuple[int, ...]

    def to_row(self, rank: int) -> tuple[str, ...]:
        sources = ", ".join(f"{value:02d}" for value in self.matched_sources)
        return (
            str(rank),
            f"{self.value:02d}",
            f"{self.score:.4f}",
            str(self.support),
            str(self.rule_count),
            f"{self.average_lift:.2f}",
            f"{self.max_lift:.2f}",
            sources,
        )


@dataclass(slots=True, frozen=True)
class BacktestSummary:
    """Walk-forward backtest summary for historical signal ranking."""

    lag: int
    top_k: int
    tested_rows: int
    average_hits: float
    one_plus_hit_rate: float
    two_plus_hit_rate: float
    max_hits: int
    total_hits: int
    hit_distribution: dict[int, int] = field(default_factory=dict)

    def to_rows(self) -> list[tuple[str, str]]:
        return [
            ("Độ trễ", f"N+{self.lag}"),
            ("Top K", str(self.top_k)),
            ("Số kỳ kiểm định", str(self.tested_rows)),
            ("Số khớp trung bình", f"{self.average_hits:.3f}"),
            ("Tỷ lệ có ít nhất 1 số khớp", f"{self.one_plus_hit_rate * 100:.2f}%"),
            ("Tỷ lệ có ít nhất 2 số khớp", f"{self.two_plus_hit_rate * 100:.2f}%"),
            ("Số khớp cao nhất", str(self.max_hits)),
            ("Tổng số khớp", str(self.total_hits)),
            (
                "Phân bố số khớp",
                ", ".join(
                    f"{hits} số: {count} kỳ"
                    for hits, count in sorted(self.hit_distribution.items())
                ),
            ),
        ]


class PatternMiner:
    """Mine lagged value-to-value relationships in historical draw data."""

    def __init__(self, value_min: int = 1, value_max: int = 45) -> None:
        self.value_min = value_min
        self.value_max = value_max

    @staticmethod
    def values(draw: Draw) -> tuple[int, ...]:
        return tuple(int(value) for value in draw.numbers)

    def compute_rules(
        self,
        draws: Sequence[Draw],
        *,
        lag: int = 3,
        min_support: int = 2,
        top_n: int | None = 50,
    ) -> list[PatternRule]:
        """Compute historical transition rules for a fixed lag.

        A rule A -> B at lag L means that A appeared in draw N and B appeared
        in draw N+L in the historical dataset.
        """
        if lag < 1:
            raise ValueError("lag must be at least 1")
        if min_support < 1:
            raise ValueError("min_support must be at least 1")
        if len(draws) <= lag:
            return []

        source_counts: Counter[int] = Counter()
        target_counts: Counter[int] = Counter()
        pair_counts: Counter[tuple[int, int]] = Counter()

        transition_count = len(draws) - lag
        for index in range(transition_count):
            source_values = self.values(draws[index])
            target_values = self.values(draws[index + lag])

            for source in source_values:
                source_counts[source] += 1
                for target in target_values:
                    pair_counts[(source, target)] += 1
            for target in target_values:
                target_counts[target] += 1

        rules: list[PatternRule] = []
        for (source, target), count in pair_counts.items():
            if count < min_support:
                continue
            source_count = source_counts[source]
            conditional_rate = count / source_count if source_count else 0.0
            baseline_rate = target_counts[target] / transition_count
            lift = conditional_rate / baseline_rate if baseline_rate else 0.0
            delta = conditional_rate - baseline_rate
            score = max(delta, 0.0) * lift * count
            rules.append(
                PatternRule(
                    source_value=source,
                    target_value=target,
                    lag=lag,
                    source_count=source_count,
                    cooccurrence_count=count,
                    conditional_rate=conditional_rate,
                    baseline_rate=baseline_rate,
                    lift=lift,
                    delta=delta,
                    score=score,
                )
            )

        rules.sort(
            key=lambda item: (
                item.score,
                item.lift,
                item.cooccurrence_count,
                item.conditional_rate,
            ),
            reverse=True,
        )
        return rules[:top_n] if top_n is not None else rules

    def current_signals(
        self,
        draws: Sequence[Draw],
        *,
        lag: int = 3,
        min_support: int = 2,
        top_n: int = 10,
    ) -> list[CandidateSignal]:
        """Aggregate historical rules that match the latest known draw."""
        if not draws:
            return []

        latest_values = set(self.values(draws[-1]))
        rules = self.compute_rules(
            draws,
            lag=lag,
            min_support=min_support,
            top_n=None,
        )

        score_by_target: defaultdict[int, float] = defaultdict(float)
        support_by_target: Counter[int] = Counter()
        lifts_by_target: defaultdict[int, list[float]] = defaultdict(list)
        sources_by_target: defaultdict[int, set[int]] = defaultdict(set)

        for rule in rules:
            if rule.source_value not in latest_values:
                continue
            score_by_target[rule.target_value] += rule.score
            support_by_target[rule.target_value] += rule.cooccurrence_count
            lifts_by_target[rule.target_value].append(rule.lift)
            sources_by_target[rule.target_value].add(rule.source_value)

        signals: list[CandidateSignal] = []
        for target, score in score_by_target.items():
            lifts = lifts_by_target[target]
            signals.append(
                CandidateSignal(
                    value=target,
                    score=score,
                    support=support_by_target[target],
                    rule_count=len(lifts),
                    average_lift=mean(lifts) if lifts else 0.0,
                    max_lift=max(lifts) if lifts else 0.0,
                    matched_sources=tuple(sorted(sources_by_target[target])),
                )
            )

        signals.sort(
            key=lambda item: (
                item.score,
                item.support,
                item.average_lift,
                item.max_lift,
            ),
            reverse=True,
        )
        return signals[:top_n]

    def walk_forward_backtest(
        self,
        draws: Sequence[Draw],
        *,
        lag: int = 3,
        top_k: int = 10,
        min_support: int = 2,
        min_training_rows: int = 60,
    ) -> BacktestSummary:
        """Walk-forward backtest using only data known at each historical point."""
        if lag < 1:
            raise ValueError("lag must be at least 1")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        last_anchor = len(draws) - lag
        if last_anchor <= min_training_rows:
            return BacktestSummary(
                lag=lag,
                top_k=top_k,
                tested_rows=0,
                average_hits=0.0,
                one_plus_hit_rate=0.0,
                two_plus_hit_rate=0.0,
                max_hits=0,
                total_hits=0,
                hit_distribution={},
            )

        hits_per_row: list[int] = []
        for anchor_index in range(min_training_rows, last_anchor):
            known_draws = list(draws[: anchor_index + 1])
            candidates = self.current_signals(
                known_draws,
                lag=lag,
                min_support=min_support,
                top_n=top_k,
            )
            selected = {candidate.value for candidate in candidates}
            actual = set(self.values(draws[anchor_index + lag]))
            hits_per_row.append(len(selected & actual))

        tested_rows = len(hits_per_row)
        distribution = dict(Counter(hits_per_row))
        total_hits = sum(hits_per_row)
        one_plus = sum(1 for hits in hits_per_row if hits >= 1)
        two_plus = sum(1 for hits in hits_per_row if hits >= 2)
        return BacktestSummary(
            lag=lag,
            top_k=top_k,
            tested_rows=tested_rows,
            average_hits=total_hits / tested_rows if tested_rows else 0.0,
            one_plus_hit_rate=one_plus / tested_rows if tested_rows else 0.0,
            two_plus_hit_rate=two_plus / tested_rows if tested_rows else 0.0,
            max_hits=max(hits_per_row) if hits_per_row else 0,
            total_hits=total_hits,
            hit_distribution=distribution,
        )

    def signal_rows(
        self,
        draws: Sequence[Draw],
        *,
        lag: int = 3,
        min_support: int = 2,
        top_n: int = 10,
    ) -> list[tuple[str, ...]]:
        return [
            signal.to_row(rank)
            for rank, signal in enumerate(
                self.current_signals(
                    draws,
                    lag=lag,
                    min_support=min_support,
                    top_n=top_n,
                ),
                1,
            )
        ]

    def rule_rows(
        self,
        draws: Sequence[Draw],
        *,
        lag: int = 3,
        min_support: int = 2,
        top_n: int = 50,
    ) -> list[tuple[str, ...]]:
        return [
            rule.to_row(rank)
            for rank, rule in enumerate(
                self.compute_rules(
                    draws,
                    lag=lag,
                    min_support=min_support,
                    top_n=top_n,
                ),
                1,
            )
        ]
