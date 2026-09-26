"""Independent per-number walk-back chain gate.

This workflow validates the latest N historical rows as a sequential chain.
Each target number is handled independently: a method survives for a number only
when that method can pull that exact number inside the configured way-top range.
The surviving methods from one holdout row become the only candidate methods for
the next holdout row.

Ranking is weighted by chain reliability. Methods that repeatedly pull correct
numbers in prior holdout rows receive stronger weight when ranking the next row.
This prevents a large but weak vote cluster from dominating the final Top list.

A future signal is released only when every holdout row passes the independent
number-chain gate and the final Top gate.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Iterable, Sequence

from ape.core.settings import SETTINGS
from ape.database.models import Draw
from ape.patterns.audit import format_values
from ape.patterns.target_learning import LearnedMethod, LearnedMethodStore, TargetLearningEngine


@dataclass(slots=True, frozen=True)
class NumberChainAttemptConfig:
    """Search size for one automatic independent-chain attempt."""

    round_index: int
    method_count: int
    ensemble_pool: int
    max_lag: int
    support_max: int

    @property
    def label(self) -> str:
        return (
            f"round={self.round_index} · methods={self.method_count} · "
            f"ensemble_pool={self.ensemble_pool} · max_lag={self.max_lag} · "
            f"support=1→{self.support_max}"
        )


@dataclass(slots=True, frozen=True)
class NumberChainStepResult:
    """One holdout-row result in the independent number chain."""

    index: int
    draw_date: object
    target_values: tuple[int, ...]
    signal_values: tuple[int, ...]
    matched_values: tuple[int, ...]
    covered_values: tuple[int, ...]
    missing_values: tuple[int, ...]
    passed: bool
    method_count_before: int
    method_count_after: int
    per_value_way_counts: dict[int, int]
    min_ways: int
    min_top_hits: int

    @property
    def hit_count(self) -> int:
        return len(self.matched_values)

    @property
    def coverage_count(self) -> int:
        return len(self.covered_values)

    def to_lines(self) -> list[str]:
        status = "PASS" if self.passed else "FAIL"
        top_status = "ĐỦ" if self.hit_count >= self.min_top_hits else "thiếu"
        lines = [
            f"Kỳ {self.index:02d} · {self.draw_date.strftime('%d/%m/%Y')} · {status}",
            f"  Dãy đúng              : {format_values(self.target_values)}",
            f"  Top tín hiệu          : {format_values(self.signal_values)}",
            f"  Trùng Top             : {self.hit_count}/6" + (f" · {format_values(self.matched_values)}" if self.matched_values else ""),
            f"  Final Top Gate        : {top_status} · ngưỡng {self.min_top_hits}",
            f"  Đủ cách độc lập       : {self.coverage_count}/6" + (f" · {format_values(self.covered_values)}" if self.covered_values else ""),
            f"  Thiếu cách độc lập    : {format_values(self.missing_values) if self.missing_values else '-'}",
            f"  Cách sống sót         : {self.method_count_before} → {self.method_count_after}",
            "  Số cách kéo độc lập từng số:",
        ]
        for value in self.target_values:
            count = self.per_value_way_counts.get(value, 0)
            ok = "ĐỦ" if count >= self.min_ways else "thiếu"
            lines.append(f"    - {value:02d}: {count} cách ({ok}, ngưỡng {self.min_ways})")
        return lines


@dataclass(slots=True, frozen=True)
class NumberChainGateResult:
    """Final result of independent number-chain validation."""

    passed: bool
    attempt: NumberChainAttemptConfig
    holdout_count: int
    top_k: int
    way_top: int
    min_ways: int
    min_top_hits: int
    base_history_rows: int
    steps: tuple[NumberChainStepResult, ...]
    final_signal_values: tuple[int, ...]
    survivor_count: int
    saved_path: Path | None
    fail_reason: str

    @property
    def passed_steps(self) -> int:
        return sum(1 for step in self.steps if step.passed)

    @property
    def total_hits(self) -> int:
        return sum(step.hit_count for step in self.steps)

    @property
    def total_coverage(self) -> int:
        return sum(step.coverage_count for step in self.steps)

    def sort_key(self) -> tuple[int, int, int, int]:
        return (
            self.passed_steps,
            self.total_coverage,
            self.total_hits,
            self.survivor_count,
        )

    def to_lines(self) -> list[str]:
        title = "PASS - ĐỦ INDEPENDENT NUMBER CHAIN" if self.passed else "FAIL - CHƯA ĐỦ INDEPENDENT NUMBER CHAIN"
        lines = [
            "================ INDEPENDENT NUMBER CHAIN 15 KỲ ================",
            title,
            f"Cấu hình         : {self.attempt.label}",
            f"Số kỳ holdout    : {self.holdout_count}",
            f"Top tín hiệu     : {self.top_k}",
            f"Way Top/cách     : {self.way_top}",
            f"Ngưỡng cách/số   : {self.min_ways}",
            f"Ngưỡng Top/kỳ    : {self.min_top_hits}",
            f"Vùng học gốc     : {self.base_history_rows} kỳ",
            f"Kỳ đã pass       : {self.passed_steps}/{self.holdout_count}",
            f"Tổng trùng Top   : {self.total_hits}/{self.holdout_count * 6}",
            f"Tổng đủ cách     : {self.total_coverage}/{self.holdout_count * 6}",
            f"Cách còn sống    : {self.survivor_count}",
            "",
        ]
        for step in self.steps:
            lines.extend(step.to_lines())
            lines.append("-" * 64)
        if self.passed:
            lines.extend(
                [
                    "TÍN HIỆU KỲ MỚI ĐƯỢC PHÉP XUẤT",
                    format_values(self.final_signal_values),
                    f"File lưu bộ cách sống sót: {self.saved_path}" if self.saved_path else "File lưu bộ cách sống sót: -",
                ]
            )
        else:
            lines.extend(
                [
                    "KẾT LUẬN",
                    self.fail_reason or "Chưa vượt đủ chuỗi 15 kỳ nên không xuất tín hiệu kỳ mới.",
                    "Tool không ép kết quả. Nếu gate fail, cần mở rộng cách tính hoặc chấp nhận rằng tín hiệu Top hiện tại chưa đủ lực kiểm chứng.",
                ]
            )
        lines.append("=================================================================")
        return lines


class IndependentNumberChainTrainer:
    """Validate methods as independent per-number survivor chains."""

    def __init__(self, engine: TargetLearningEngine | None = None) -> None:
        self.engine = engine or TargetLearningEngine()

    def train(
        self,
        draws: Sequence[Draw],
        *,
        holdout_count: int = 15,
        top_k: int = 7,
        way_top: int | None = None,
        method_count: int = 600,
        ensemble_pool: int = 70,
        max_lag: int = 24,
        support_max: int = 9,
        max_rounds: int = 3,
        min_base_history: int = 60,
        min_ways: int = 1,
        min_top_hits: int = 1,
        save_path: Path | None = None,
    ) -> NumberChainGateResult:
        source_draws = list(draws)
        effective_way_top = max(top_k, way_top or top_k)
        if holdout_count < 1:
            raise ValueError("holdout_count must be at least 1")
        if top_k < 6:
            raise ValueError("top_k must be at least 6 because each row has 6 numbers")
        if min_ways < 1:
            raise ValueError("min_ways must be at least 1")
        if min_top_hits < 0:
            raise ValueError("min_top_hits must be at least 0")
        if len(source_draws) <= holdout_count + min_base_history:
            raise ValueError(
                f"Cần ít nhất {holdout_count + min_base_history + 1} kỳ để kiểm định chuỗi. "
                f"Hiện có {len(source_draws)} kỳ."
            )

        best_result: NumberChainGateResult | None = None
        for attempt in self.attempt_configs(
            method_count=method_count,
            ensemble_pool=ensemble_pool,
            max_lag=max_lag,
            support_max=support_max,
            max_rounds=max_rounds,
        ):
            result, survivors = self.run_attempt(
                source_draws,
                attempt=attempt,
                holdout_count=holdout_count,
                top_k=top_k,
                way_top=effective_way_top,
                min_base_history=min_base_history,
                min_ways=min_ways,
                min_top_hits=min_top_hits,
                save_path=save_path,
            )
            if result.passed:
                saved = self.save_survivors(survivors, result=result, path=save_path)
                return NumberChainGateResult(
                    passed=True,
                    attempt=result.attempt,
                    holdout_count=result.holdout_count,
                    top_k=result.top_k,
                    way_top=result.way_top,
                    min_ways=result.min_ways,
                    min_top_hits=result.min_top_hits,
                    base_history_rows=result.base_history_rows,
                    steps=result.steps,
                    final_signal_values=result.final_signal_values,
                    survivor_count=result.survivor_count,
                    saved_path=saved,
                    fail_reason="",
                )
            if best_result is None or result.sort_key() > best_result.sort_key():
                best_result = result

        assert best_result is not None
        return best_result

    def run_attempt(
        self,
        draws: list[Draw],
        *,
        attempt: NumberChainAttemptConfig,
        holdout_count: int,
        top_k: int,
        way_top: int,
        min_base_history: int,
        min_ways: int,
        min_top_hits: int,
        save_path: Path | None,
    ) -> tuple[NumberChainGateResult, list[LearnedMethod]]:
        base_history = draws[:-holdout_count]
        holdouts = draws[-holdout_count:]
        if len(base_history) < min_base_history:
            raise ValueError("Không đủ dữ liệu trước vùng holdout để học chuỗi.")

        first_target = self.draw_values(holdouts[0])
        available_methods = self.engine.learn_methods(
            base_history,
            first_target,
            top_k=way_top,
            max_lag=attempt.max_lag,
            support_values=tuple(range(1, attempt.support_max + 1)),
            strategy_mode="full",
            limit=attempt.method_count,
            ensemble_pool=attempt.ensemble_pool,
        )
        available_methods = self.dedupe_methods(available_methods)

        method_weights: defaultdict[tuple[object, ...], float] = defaultdict(lambda: 1.0)
        method_streaks: Counter[tuple[object, ...]] = Counter()
        chain_groups: dict[int, list[LearnedMethod]] = {}
        steps: list[NumberChainStepResult] = []
        history = list(base_history)

        for index, target_draw in enumerate(holdouts, 1):
            target = self.draw_values(target_draw)
            method_count_before = len(available_methods)
            signal_values = self.weighted_chain_signal_values(
                history,
                available_methods,
                method_weights=method_weights,
                method_streaks=method_streaks,
                chain_groups=chain_groups,
                top_k=top_k,
                way_top=way_top,
            )
            matched = tuple(sorted(set(signal_values) & set(target)))

            value_pools: dict[int, list[LearnedMethod]] = {}
            per_value_counts: Counter[int] = Counter()
            method_hits: dict[tuple[object, ...], int] = defaultdict(int)
            method_best_rank: dict[tuple[object, ...], int] = {}

            for value in target:
                value_methods = self.methods_that_pull_value(
                    available_methods,
                    history,
                    value,
                    way_top=way_top,
                )
                value_pools[value] = value_methods
                per_value_counts[value] = len(value_methods)
                for method in value_methods:
                    key = self.method_key(method)
                    method_hits[key] += 1
                    values = self.engine.signal_values_from_method(history, method, top_k=way_top)
                    if value in values:
                        rank = values.index(value) + 1
                        method_best_rank[key] = min(method_best_rank.get(key, way_top + 1), rank)

            covered = tuple(value for value in target if per_value_counts.get(value, 0) >= min_ways)
            missing = tuple(value for value in target if value not in set(covered))
            next_methods = self.dedupe_methods(
                method for value in target for method in value_pools.get(value, [])
            )
            passed = (
                len(covered) == len(target)
                and len(next_methods) > 0
                and (min_top_hits <= 0 or len(matched) >= min_top_hits)
            )
            steps.append(
                NumberChainStepResult(
                    index=index,
                    draw_date=target_draw.draw_date,
                    target_values=target,
                    signal_values=signal_values,
                    matched_values=matched,
                    covered_values=covered,
                    missing_values=missing,
                    passed=passed,
                    method_count_before=method_count_before,
                    method_count_after=len(next_methods),
                    per_value_way_counts=dict(per_value_counts),
                    min_ways=min_ways,
                    min_top_hits=min_top_hits,
                )
            )
            if not passed:
                if missing:
                    reason = (
                        f"Gate dừng ở kỳ {index:02d} ({target_draw.draw_date.strftime('%d/%m/%Y')}). "
                        f"Thiếu cách độc lập: {format_values(missing)}. "
                        f"Đủ cách {len(covered)}/6, trùng Top {len(matched)}/6."
                    )
                else:
                    reason = (
                        f"Gate dừng ở kỳ {index:02d} ({target_draw.draw_date.strftime('%d/%m/%Y')}). "
                        f"Đủ cách độc lập 6/6 nhưng Top {top_k} chỉ trùng {len(matched)}/6, "
                        f"thấp hơn ngưỡng {min_top_hits}."
                    )
                return (
                    NumberChainGateResult(
                        passed=False,
                        attempt=attempt,
                        holdout_count=holdout_count,
                        top_k=top_k,
                        way_top=way_top,
                        min_ways=min_ways,
                        min_top_hits=min_top_hits,
                        base_history_rows=len(base_history),
                        steps=tuple(steps),
                        final_signal_values=tuple(),
                        survivor_count=len(next_methods),
                        saved_path=None,
                        fail_reason=reason,
                    ),
                    next_methods,
                )

            self.update_method_reliability(
                method_weights,
                method_streaks,
                available_methods=available_methods,
                method_hits=method_hits,
                method_best_rank=method_best_rank,
                way_top=way_top,
            )
            available_methods = next_methods
            chain_groups = value_pools
            history.append(target_draw)

        final_signal = self.weighted_chain_signal_values(
            draws,
            available_methods,
            method_weights=method_weights,
            method_streaks=method_streaks,
            chain_groups=chain_groups,
            top_k=top_k,
            way_top=way_top,
        )
        return (
            NumberChainGateResult(
                passed=True,
                attempt=attempt,
                holdout_count=holdout_count,
                top_k=top_k,
                way_top=way_top,
                min_ways=min_ways,
                min_top_hits=min_top_hits,
                base_history_rows=len(base_history),
                steps=tuple(steps),
                final_signal_values=final_signal,
                survivor_count=len(available_methods),
                saved_path=save_path or SETTINGS.data_dir / "number_chain_survivors.json",
                fail_reason="",
            ),
            available_methods,
        )

    def update_method_reliability(
        self,
        method_weights: defaultdict[tuple[object, ...], float],
        method_streaks: Counter[tuple[object, ...]],
        *,
        available_methods: Sequence[LearnedMethod],
        method_hits: dict[tuple[object, ...], int],
        method_best_rank: dict[tuple[object, ...], int],
        way_top: int,
    ) -> None:
        """Update method weights after a holdout row is revealed."""
        hit_keys = set(method_hits)
        for method in available_methods:
            key = self.method_key(method)
            old_weight = method_weights[key]
            if key in hit_keys:
                best_rank = method_best_rank.get(key, way_top)
                rank_bonus = max(1.0, (way_top - best_rank + 1) / max(1.0, way_top / 4))
                hit_bonus = 1.0 + method_hits[key]
                method_streaks[key] += 1
                streak_bonus = 1.0 + min(method_streaks[key], 5) * 0.18
                method_weights[key] = old_weight * 0.92 + hit_bonus * rank_bonus * streak_bonus
            else:
                method_streaks[key] = 0
                method_weights[key] = max(0.15, old_weight * 0.72)

    def weighted_chain_signal_values(
        self,
        draws: Sequence[Draw],
        methods: Sequence[LearnedMethod],
        *,
        method_weights: dict[tuple[object, ...], float],
        method_streaks: Counter[tuple[object, ...]],
        chain_groups: dict[int, list[LearnedMethod]],
        top_k: int,
        way_top: int,
    ) -> tuple[int, ...]:
        """Rank values by weighted reliability across independent survivor chains."""
        methods = self.dedupe_methods(methods)
        if not methods:
            return tuple()

        scores: defaultdict[int, float] = defaultdict(float)
        vote_counts: Counter[int] = Counter()
        group_support: defaultdict[int, set[int]] = defaultdict(set)
        weighted_groups = chain_groups or {0: list(methods)}

        for group_value, group_methods in weighted_groups.items():
            group_methods = self.dedupe_methods(group_methods)
            if not group_methods:
                continue
            group_normalizer = max(1.0, len(group_methods) ** 0.5)
            for method in group_methods:
                key = self.method_key(method)
                values = self.engine.signal_values_from_method(draws, method, top_k=way_top)
                weight = method_weights.get(key, 1.0)
                streak = method_streaks.get(key, 0)
                reliability = weight * (1.0 + min(streak, 5) * 0.12)
                for rank, value in enumerate(values, 1):
                    rank_weight = (way_top - rank + 1) / max(1, way_top)
                    scores[value] += reliability * rank_weight / group_normalizer
                    vote_counts[value] += 1
                    group_support[value].add(group_value)

        ranked = sorted(
            scores,
            key=lambda value: (
                len(group_support[value]),
                scores[value],
                vote_counts[value],
                value,
            ),
            reverse=True,
        )
        return tuple(ranked[:top_k])

    def methods_that_pull_value(
        self,
        methods: Sequence[LearnedMethod],
        draws: Sequence[Draw],
        value: int,
        *,
        way_top: int,
    ) -> list[LearnedMethod]:
        result: list[LearnedMethod] = []
        for method in methods:
            values = self.engine.signal_values_from_method(draws, method, top_k=way_top)
            if value in set(values):
                result.append(method)
        return self.dedupe_methods(result)

    @staticmethod
    def attempt_configs(
        *,
        method_count: int,
        ensemble_pool: int,
        max_lag: int,
        support_max: int,
        max_rounds: int,
    ) -> list[NumberChainAttemptConfig]:
        rounds = max(1, max_rounds)
        configs: list[NumberChainAttemptConfig] = []
        for index in range(1, rounds + 1):
            configs.append(
                NumberChainAttemptConfig(
                    round_index=index,
                    method_count=min(1500, method_count * index),
                    ensemble_pool=min(200, ensemble_pool + (index - 1) * 30),
                    max_lag=min(40, max_lag + (index - 1) * 8),
                    support_max=min(12, support_max + (index - 1) * 2),
                )
            )
        return configs

    @staticmethod
    def draw_values(draw: Draw) -> tuple[int, ...]:
        return tuple(sorted(int(value) for value in draw.numbers))

    @staticmethod
    def method_key(method: LearnedMethod) -> tuple[object, ...]:
        config_key = tuple(
            (
                config.name,
                config.lag,
                config.min_support,
                config.use_structure,
                config.use_repeat_overlap,
                config.lag_offsets,
            )
            for config in method.configs
        )
        return (method.method_type, method.label, method.top_k, config_key)

    def dedupe_methods(self, methods: Iterable[LearnedMethod]) -> list[LearnedMethod]:
        seen: set[tuple[object, ...]] = set()
        result: list[LearnedMethod] = []
        for method in methods:
            key = self.method_key(method)
            if key in seen:
                continue
            seen.add(key)
            result.append(method)
        return result

    @staticmethod
    def save_survivors(
        methods: Sequence[LearnedMethod],
        *,
        result: NumberChainGateResult,
        path: Path | None = None,
    ) -> Path:
        target_path = path or SETTINGS.data_dir / "number_chain_survivors.json"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "independent_number_chain_gate_weighted",
            "passed": result.passed,
            "holdout_count": result.holdout_count,
            "top_k": result.top_k,
            "way_top": result.way_top,
            "min_ways": result.min_ways,
            "min_top_hits": result.min_top_hits,
            "base_history_rows": result.base_history_rows,
            "attempt": {
                "round_index": result.attempt.round_index,
                "method_count": result.attempt.method_count,
                "ensemble_pool": result.attempt.ensemble_pool,
                "max_lag": result.attempt.max_lag,
                "support_max": result.attempt.support_max,
            },
            "survivor_count": len(methods),
            "final_signal_values": list(result.final_signal_values),
            "methods": [LearnedMethodStore.method_to_dict(method) for method in methods],
        }
        target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return target_path
