"""Historical transition-pattern mining and walk-forward backtesting.

This module intentionally describes historical signals only. It does not label
outputs as predictions and does not claim future results are knowable.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from math import floor
from statistics import mean
from typing import Sequence

from ape.database.models import Draw

RANGE_BANDS: tuple[tuple[int, int, str], ...] = (
    (1, 9, "01-09"),
    (10, 20, "10-20"),
    (21, 30, "21-30"),
    (31, 40, "31-40"),
    (41, 45, "41-45"),
)
DRAW_SIZE = 6


@dataclass(slots=True, frozen=True)
class DrawStructure:
    """Structural fingerprint of one historical row."""

    odd_count: int
    even_count: int
    band_counts: tuple[int, ...]

    @property
    def parity_label(self) -> str:
        return f"{self.odd_count} lẻ / {self.even_count} chẵn"

    @property
    def band_label(self) -> str:
        return " | ".join(
            f"{label}: {count}"
            for (_, _, label), count in zip(RANGE_BANDS, self.band_counts)
        )


@dataclass(slots=True, frozen=True)
class StructureProfile:
    """Historical distribution of row-level structures."""

    draw_count: int
    average_odd: float
    average_even: float
    average_band_counts: tuple[float, ...]
    modal_odd_even: tuple[int, int]
    modal_band_counts: tuple[int, ...]
    parity_distribution: dict[tuple[int, int], int] = field(default_factory=dict)
    band_distribution: dict[tuple[int, ...], int] = field(default_factory=dict)

    @property
    def parity_label(self) -> str:
        odd, even = self.modal_odd_even
        return f"{odd} lẻ / {even} chẵn"

    @property
    def band_label(self) -> str:
        return " | ".join(
            f"{label}: {count}"
            for (_, _, label), count in zip(RANGE_BANDS, self.modal_band_counts)
        )

    def to_rows(self) -> list[tuple[str, str]]:
        return [
            ("Số kỳ học cấu trúc", str(self.draw_count)),
            ("Mẫu lẻ/chẵn lặp nhiều", self.parity_label),
            ("Trung bình lẻ/chẵn", f"{self.average_odd:.2f} lẻ / {self.average_even:.2f} chẵn"),
            ("Mẫu phân vùng lặp nhiều", self.band_label),
            (
                "Trung bình phân vùng",
                " | ".join(
                    f"{label}: {value:.2f}"
                    for (_, _, label), value in zip(RANGE_BANDS, self.average_band_counts)
                ),
            ),
        ]


@dataclass(slots=True, frozen=True)
class RepeatOverlapSummary:
    """How often values in draw N appear again in draw N+lag."""

    lag: int
    compared_rows: int
    average_overlap: float
    modal_overlap: int
    zero_overlap_rate: float
    one_plus_overlap_rate: float
    two_plus_overlap_rate: float
    overlap_distribution: dict[int, int] = field(default_factory=dict)

    @property
    def distribution_label(self) -> str:
        if not self.overlap_distribution:
            return "-"
        return ", ".join(
            f"{overlap} số: {count} kỳ"
            for overlap, count in sorted(self.overlap_distribution.items())
        )

    def to_rows(self) -> list[tuple[str, str]]:
        return [
            ("Độ lặp đang học", f"N+{self.lag}"),
            ("Số cặp kỳ đã so sánh", str(self.compared_rows)),
            ("Số trùng trung bình giữa N và N+lag", f"{self.average_overlap:.3f}"),
            ("Mức trùng lặp lại nhiều nhất", f"{self.modal_overlap} số"),
            ("Tỷ lệ không trùng số nào", f"{self.zero_overlap_rate * 100:.2f}%"),
            ("Tỷ lệ trùng ít nhất 1 số", f"{self.one_plus_overlap_rate * 100:.2f}%"),
            ("Tỷ lệ trùng ít nhất 2 số", f"{self.two_plus_overlap_rate * 100:.2f}%"),
            ("Phân bố độ trùng", self.distribution_label),
        ]


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
    structure_weight: float = 1.0
    repeat_weight: float = 1.0

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
    structure_enabled: bool = True
    repeat_enabled: bool = True
    parity_reference: str = ""
    band_reference: str = ""
    repeat_overlap: RepeatOverlapSummary | None = None

    def to_rows(self) -> list[tuple[str, str]]:
        rows = [
            ("Độ trễ", f"N+{self.lag}"),
            ("Top K", str(self.top_k)),
            ("Cân bằng cấu trúc", "Có" if self.structure_enabled else "Không"),
            ("Học độ lặp N→N+lag", "Có" if self.repeat_enabled else "Không"),
            ("Mẫu lẻ/chẵn tham chiếu", self.parity_reference or "-"),
            ("Mẫu phân vùng tham chiếu", self.band_reference or "-"),
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
        if self.repeat_overlap is not None:
            rows.extend(self.repeat_overlap.to_rows())
        return rows


class PatternMiner:
    """Mine lagged value-to-value relationships in historical draw data."""

    def __init__(self, value_min: int = 1, value_max: int = 45) -> None:
        self.value_min = value_min
        self.value_max = value_max

    @staticmethod
    def values(draw: Draw) -> tuple[int, ...]:
        return tuple(int(value) for value in draw.numbers)

    @staticmethod
    def band_index(value: int) -> int:
        for index, (start, end, _) in enumerate(RANGE_BANDS):
            if start <= value <= end:
                return index
        raise ValueError(f"value is outside supported range: {value}")

    def draw_structure(self, draw: Draw) -> DrawStructure:
        values = self.values(draw)
        odd_count = sum(value % 2 for value in values)
        band_counts = [0 for _ in RANGE_BANDS]
        for value in values:
            band_counts[self.band_index(value)] += 1
        return DrawStructure(
            odd_count=odd_count,
            even_count=len(values) - odd_count,
            band_counts=tuple(band_counts),
        )

    def build_structure_profile(
        self,
        draws: Sequence[Draw],
        *,
        lag: int = 0,
    ) -> StructureProfile:
        """Learn repeated odd/even and number-zone structures from history."""
        if lag < 0:
            raise ValueError("lag must not be negative")
        target_draws = list(draws[lag:]) if lag else list(draws)
        if not target_draws:
            return StructureProfile(
                draw_count=0,
                average_odd=0.0,
                average_even=0.0,
                average_band_counts=tuple(0.0 for _ in RANGE_BANDS),
                modal_odd_even=(0, 0),
                modal_band_counts=tuple(0 for _ in RANGE_BANDS),
            )

        structures = [self.draw_structure(draw) for draw in target_draws]
        parity_counter: Counter[tuple[int, int]] = Counter(
            (item.odd_count, item.even_count) for item in structures
        )
        band_counter: Counter[tuple[int, ...]] = Counter(item.band_counts for item in structures)
        modal_odd_even = parity_counter.most_common(1)[0][0]
        modal_band_counts = band_counter.most_common(1)[0][0]
        average_bands = tuple(
            mean(item.band_counts[index] for item in structures)
            for index in range(len(RANGE_BANDS))
        )
        return StructureProfile(
            draw_count=len(structures),
            average_odd=mean(item.odd_count for item in structures),
            average_even=mean(item.even_count for item in structures),
            average_band_counts=average_bands,
            modal_odd_even=modal_odd_even,
            modal_band_counts=modal_band_counts,
            parity_distribution=dict(parity_counter),
            band_distribution=dict(band_counter),
        )

    def compute_repeat_overlap(
        self,
        draws: Sequence[Draw],
        *,
        lag: int = 3,
    ) -> RepeatOverlapSummary:
        """Compute how many values repeat from draw N to draw N+lag."""
        if lag < 1:
            raise ValueError("lag must be at least 1")
        if len(draws) <= lag:
            return RepeatOverlapSummary(
                lag=lag,
                compared_rows=0,
                average_overlap=0.0,
                modal_overlap=0,
                zero_overlap_rate=0.0,
                one_plus_overlap_rate=0.0,
                two_plus_overlap_rate=0.0,
                overlap_distribution={},
            )

        overlaps: list[int] = []
        for index in range(len(draws) - lag):
            source_values = set(self.values(draws[index]))
            target_values = set(self.values(draws[index + lag]))
            overlaps.append(len(source_values & target_values))

        distribution = Counter(overlaps)
        highest_frequency = max(distribution.values())
        modal_overlap = min(
            overlap
            for overlap, count in distribution.items()
            if count == highest_frequency
        )
        compared_rows = len(overlaps)
        return RepeatOverlapSummary(
            lag=lag,
            compared_rows=compared_rows,
            average_overlap=sum(overlaps) / compared_rows if compared_rows else 0.0,
            modal_overlap=modal_overlap,
            zero_overlap_rate=distribution.get(0, 0) / compared_rows,
            one_plus_overlap_rate=sum(1 for value in overlaps if value >= 1) / compared_rows,
            two_plus_overlap_rate=sum(1 for value in overlaps if value >= 2) / compared_rows,
            overlap_distribution=dict(distribution),
        )

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
        use_structure: bool = True,
        use_repeat_overlap: bool = True,
    ) -> list[CandidateSignal]:
        """Aggregate historical rules that match the latest known draw.

        When structure learning is enabled, scores are adjusted by historical
        odd/even and number-zone tendencies, then the final Top K list is
        balanced toward the learned structural profile. When repeat-overlap
        learning is enabled, values from the latest row receive a conservative
        boost if the selected lag historically tends to repeat values from N.
        """
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

        profile = self.build_structure_profile(draws, lag=lag)
        overlap = self.compute_repeat_overlap(draws, lag=lag)
        signals: list[CandidateSignal] = []
        for target, score in score_by_target.items():
            lifts = lifts_by_target[target]
            structure_weight = (
                self.structure_weight(target, profile) if use_structure else 1.0
            )
            repeat_weight = (
                self.repeat_overlap_weight(target, latest_values, overlap)
                if use_repeat_overlap
                else 1.0
            )
            signals.append(
                CandidateSignal(
                    value=target,
                    score=score * structure_weight * repeat_weight,
                    support=support_by_target[target],
                    rule_count=len(lifts),
                    average_lift=mean(lifts) if lifts else 0.0,
                    max_lift=max(lifts) if lifts else 0.0,
                    matched_sources=tuple(sorted(sources_by_target[target])),
                    structure_weight=structure_weight,
                    repeat_weight=repeat_weight,
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
        if not use_structure:
            return signals[:top_n]
        return self.balance_signals_by_structure(signals, profile, top_n=top_n)

    def repeat_overlap_weight(
        self,
        value: int,
        latest_values: set[int],
        overlap: RepeatOverlapSummary,
    ) -> float:
        """Boost latest-row values when the chosen lag historically repeats."""
        if value not in latest_values or overlap.compared_rows <= 0:
            return 1.0
        expected_overlap_ratio = overlap.average_overlap / DRAW_SIZE
        base_boost = min(0.35, expected_overlap_ratio * 1.5)
        consistency_boost = min(
            0.15,
            max(0.0, overlap.one_plus_overlap_rate - 0.50) * 0.30,
        )
        return 1.0 + base_boost + consistency_boost

    def structure_weight(self, value: int, profile: StructureProfile) -> float:
        """Return a conservative score weight from parity and band tendency."""
        if profile.draw_count <= 0:
            return 1.0

        odd_ratio = profile.average_odd / DRAW_SIZE
        even_ratio = profile.average_even / DRAW_SIZE
        parity_ratio = odd_ratio if value % 2 else even_ratio
        parity_uniform = 0.5

        band = self.band_index(value)
        band_start, band_end, _ = RANGE_BANDS[band]
        band_size = band_end - band_start + 1
        band_ratio = profile.average_band_counts[band] / DRAW_SIZE
        band_uniform = band_size / (self.value_max - self.value_min + 1)

        parity_factor = (parity_ratio - parity_uniform) / parity_uniform
        band_factor = (band_ratio - band_uniform) / band_uniform if band_uniform else 0.0
        weight = 1.0 + 0.20 * parity_factor + 0.30 * band_factor
        return min(1.8, max(0.5, weight))

    def balance_signals_by_structure(
        self,
        signals: Sequence[CandidateSignal],
        profile: StructureProfile,
        *,
        top_n: int,
    ) -> list[CandidateSignal]:
        """Select Top K while approximating learned parity and band quotas."""
        if top_n <= 0:
            return []
        if not signals or profile.draw_count <= 0:
            return list(signals[:top_n])

        parity_quota = self.integer_quota(
            top_n,
            (profile.average_odd, profile.average_even),
        )
        band_quota = self.integer_quota(top_n, profile.average_band_counts)

        selected: list[CandidateSignal] = []
        selected_values: set[int] = set()
        parity_counts = [0, 0]  # index 0 = odd, index 1 = even
        band_counts = [0 for _ in RANGE_BANDS]

        for signal in signals:
            if len(selected) >= top_n:
                break
            parity_index = 0 if signal.value % 2 else 1
            band = self.band_index(signal.value)
            if parity_counts[parity_index] >= parity_quota[parity_index]:
                continue
            if band_counts[band] >= band_quota[band]:
                continue
            selected.append(signal)
            selected_values.add(signal.value)
            parity_counts[parity_index] += 1
            band_counts[band] += 1

        for signal in signals:
            if len(selected) >= top_n:
                break
            if signal.value in selected_values:
                continue
            selected.append(signal)
            selected_values.add(signal.value)

        return selected

    @staticmethod
    def integer_quota(total: int, weights: Sequence[float]) -> list[int]:
        """Convert fractional weights into integer quotas that sum to total."""
        if total <= 0:
            return [0 for _ in weights]
        weight_sum = sum(weights)
        if weight_sum <= 0:
            base = total // len(weights)
            quotas = [base for _ in weights]
            for index in range(total - sum(quotas)):
                quotas[index % len(quotas)] += 1
            return quotas

        raw = [total * weight / weight_sum for weight in weights]
        quotas = [floor(value) for value in raw]
        remainder = total - sum(quotas)
        fractions = sorted(
            enumerate(raw),
            key=lambda item: item[1] - floor(item[1]),
            reverse=True,
        )
        for index, _ in fractions[:remainder]:
            quotas[index] += 1
        return quotas

    def walk_forward_backtest(
        self,
        draws: Sequence[Draw],
        *,
        lag: int = 3,
        top_k: int = 10,
        min_support: int = 2,
        min_training_rows: int = 60,
        use_structure: bool = True,
        use_repeat_overlap: bool = True,
    ) -> BacktestSummary:
        """Walk-forward backtest using only data known at each historical point."""
        if lag < 1:
            raise ValueError("lag must be at least 1")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        profile = self.build_structure_profile(draws, lag=lag)
        overlap = self.compute_repeat_overlap(draws, lag=lag)
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
                structure_enabled=use_structure,
                repeat_enabled=use_repeat_overlap,
                parity_reference=profile.parity_label,
                band_reference=profile.band_label,
                repeat_overlap=overlap,
            )

        hits_per_row: list[int] = []
        for anchor_index in range(min_training_rows, last_anchor):
            known_draws = list(draws[: anchor_index + 1])
            candidates = self.current_signals(
                known_draws,
                lag=lag,
                min_support=min_support,
                top_n=top_k,
                use_structure=use_structure,
                use_repeat_overlap=use_repeat_overlap,
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
            structure_enabled=use_structure,
            repeat_enabled=use_repeat_overlap,
            parity_reference=profile.parity_label,
            band_reference=profile.band_label,
            repeat_overlap=overlap,
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

    def repeat_overlap_rows(
        self,
        draws: Sequence[Draw],
        *,
        max_lag: int = 10,
    ) -> list[tuple[str, ...]]:
        rows: list[tuple[str, ...]] = []
        for lag in range(1, max_lag + 1):
            summary = self.compute_repeat_overlap(draws, lag=lag)
            rows.append(
                (
                    f"N+{lag}",
                    str(summary.compared_rows),
                    f"{summary.average_overlap:.3f}",
                    str(summary.modal_overlap),
                    f"{summary.zero_overlap_rate * 100:.2f}%",
                    f"{summary.one_plus_overlap_rate * 100:.2f}%",
                    f"{summary.two_plus_overlap_rate * 100:.2f}%",
                    summary.distribution_label,
                )
            )
        return rows
