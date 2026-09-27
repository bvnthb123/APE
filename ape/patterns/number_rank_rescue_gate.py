"""Number ranking lab with missing-number rescue.

This module extends the ranking lab with a repair loop. If a walkback chain
fails because a target value has no independent method left, the trainer learns
extra methods against the full failed target row, keeps only methods that can
pull the missing values, merges them into the initial method pool, and restarts
validation from the first holdout row.
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


RANKING_MODES: tuple[str, ...] = (
    "vote",
    "weighted",
    "ranked_vote",
    "recent_score",
    "coverage_balanced",
    "missing_first",
)


@dataclass(slots=True, frozen=True)
class RescueAttemptConfig:
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
class RescueStepResult:
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
class RescueModeResult:
    passed: bool
    ranking_mode: str
    attempt: RescueAttemptConfig
    holdout_count: int
    top_k: int
    way_top: int
    min_ways: int
    min_top_hits: int
    repair_rounds: int
    repair_used: int
    base_history_rows: int
    steps: tuple[RescueStepResult, ...]
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

    @property
    def zero_top_steps(self) -> int:
        return sum(1 for step in self.steps if step.hit_count == 0)

    def sort_key(self) -> tuple[int, int, int, int, int, int]:
        return (
            self.passed_steps,
            self.total_coverage,
            self.total_hits,
            -self.zero_top_steps,
            -self.repair_used,
            self.survivor_count,
        )

    def summary_line(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"{self.ranking_mode:<18} {status:<4} · pass {self.passed_steps:02d}/{self.holdout_count} · "
            f"trùng Top {self.total_hits:02d}/{self.holdout_count * 6} · "
            f"đủ cách {self.total_coverage:02d}/{self.holdout_count * 6} · "
            f"Top 0/6: {self.zero_top_steps} kỳ · rescue {self.repair_used}/{self.repair_rounds} · "
            f"sống sót {self.survivor_count}"
        )

    def detail_lines(self) -> list[str]:
        title = "PASS - RANKING RESCUE ĐỦ GATE" if self.passed else "FAIL - RANKING RESCUE CHƯA ĐỦ GATE"
        lines = [
            "================ NUMBER RANKING RESCUE LAB ================",
            title,
            f"Ranking mode     : {self.ranking_mode}",
            f"Cấu hình         : {self.attempt.label}",
            f"Số kỳ holdout    : {self.holdout_count}",
            f"Top tín hiệu     : {self.top_k}",
            f"Way Top/cách     : {self.way_top}",
            f"Ngưỡng cách/số   : {self.min_ways}",
            f"Ngưỡng Top/kỳ    : {self.min_top_hits}",
            f"Rescue đã dùng   : {self.repair_used}/{self.repair_rounds}",
            f"Vùng học gốc     : {self.base_history_rows} kỳ",
            f"Kỳ đã pass       : {self.passed_steps}/{self.holdout_count}",
            f"Tổng trùng Top   : {self.total_hits}/{self.holdout_count * 6}",
            f"Tổng đủ cách     : {self.total_coverage}/{self.holdout_count * 6}",
            f"Số kỳ Top 0/6    : {self.zero_top_steps}",
            f"Cách còn sống    : {self.survivor_count}",
            "",
        ]
        for step in self.steps:
            lines.extend(step.to_lines())
            lines.append("-" * 60)
        if self.passed:
            lines.extend(
                [
                    "TÍN HIỆU KỲ MỚI ĐƯỢC PHÉP XUẤT",
                    format_values(self.final_signal_values),
                    f"File lưu bộ ranking rescue sống sót: {self.saved_path}" if self.saved_path else "File lưu bộ ranking rescue sống sót: -",
                ]
            )
        else:
            lines.extend(
                [
                    "KẾT LUẬN",
                    self.fail_reason or "Chưa có ranking/rescue nào vượt đủ chuỗi kiểm định.",
                    "Tool không ép kết quả. Nếu vẫn fail, số thiếu không giữ được chuỗi cách sống sót ổn định.",
                ]
            )
        lines.append("============================================================")
        return lines


@dataclass(slots=True, frozen=True)
class RescueEvaluation:
    result: RescueModeResult
    survivors: list[LearnedMethod]
    method_scores: dict[tuple[object, ...], float]
    fail_history: tuple[Draw, ...]
    fail_target_values: tuple[int, ...]
    fail_missing_values: tuple[int, ...]


@dataclass(slots=True, frozen=True)
class RescueLabResult:
    results: tuple[RescueModeResult, ...]
    best: RescueModeResult

    def to_lines(self) -> list[str]:
        lines = [
            "================ NUMBER RANKING RESCUE SUMMARY ================",
            "So sánh ranking + rescue số thiếu trên cùng chuỗi walkback.",
            "",
        ]
        for result in sorted(self.results, key=lambda item: item.sort_key(), reverse=True):
            lines.append(result.summary_line())
        lines.extend(["", f"Ranking tốt nhất: {self.best.ranking_mode}", ""])
        lines.extend(self.best.detail_lines())
        return lines


class NumberRankingRescueTrainer:
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
        repair_rounds: int = 5,
        ranking_modes: Sequence[str] = RANKING_MODES,
        save_path: Path | None = None,
    ) -> RescueLabResult:
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
        if repair_rounds < 0:
            raise ValueError("repair_rounds must be at least 0")
        if len(source_draws) <= holdout_count + min_base_history:
            raise ValueError(
                f"Cần ít nhất {holdout_count + min_base_history + 1} kỳ để kiểm định ranking rescue. "
                f"Hiện có {len(source_draws)} kỳ."
            )

        allowed_modes = tuple(mode for mode in ranking_modes if mode in RANKING_MODES) or RANKING_MODES
        evaluated: list[RescueModeResult] = []
        for attempt in self.attempt_configs(
            method_count=method_count,
            ensemble_pool=ensemble_pool,
            max_lag=max_lag,
            support_max=support_max,
            max_rounds=max_rounds,
        ):
            for mode in allowed_modes:
                result, survivors, scores = self.run_mode_with_rescue(
                    source_draws,
                    attempt=attempt,
                    ranking_mode=mode,
                    holdout_count=holdout_count,
                    top_k=top_k,
                    way_top=effective_way_top,
                    min_base_history=min_base_history,
                    min_ways=min_ways,
                    min_top_hits=min_top_hits,
                    repair_rounds=repair_rounds,
                    save_path=save_path,
                )
                if result.passed:
                    saved = self.save_survivors(survivors, method_scores=scores, result=result, path=save_path)
                    result = self.copy_result_with_saved_path(result, saved)
                evaluated.append(result)

        best = max(evaluated, key=lambda item: item.sort_key())
        return RescueLabResult(results=tuple(evaluated), best=best)

    def run_mode_with_rescue(
        self,
        draws: list[Draw],
        *,
        attempt: RescueAttemptConfig,
        ranking_mode: str,
        holdout_count: int,
        top_k: int,
        way_top: int,
        min_base_history: int,
        min_ways: int,
        min_top_hits: int,
        repair_rounds: int,
        save_path: Path | None,
    ) -> tuple[RescueModeResult, list[LearnedMethod], dict[tuple[object, ...], float]]:
        base_history = draws[:-holdout_count]
        holdouts = draws[-holdout_count:]
        first_target = self.draw_values(holdouts[0])
        method_pool = self.engine.learn_methods(
            base_history,
            first_target,
            top_k=way_top,
            max_lag=attempt.max_lag,
            support_values=tuple(range(1, attempt.support_max + 1)),
            strategy_mode="full",
            limit=attempt.method_count,
            ensemble_pool=attempt.ensemble_pool,
        )
        method_pool = self.dedupe_methods(method_pool)
        method_scores: dict[tuple[object, ...], float] = {
            self.method_key(method): float(max(1, method.fit_match_count))
            for method in method_pool
        }

        best_eval: RescueEvaluation | None = None
        for repair_used in range(repair_rounds + 1):
            evaluation = self.evaluate_pool(
                draws,
                base_history=base_history,
                holdouts=holdouts,
                method_pool=method_pool,
                method_scores=dict(method_scores),
                attempt=attempt,
                ranking_mode=ranking_mode,
                holdout_count=holdout_count,
                top_k=top_k,
                way_top=way_top,
                min_ways=min_ways,
                min_top_hits=min_top_hits,
                repair_rounds=repair_rounds,
                repair_used=repair_used,
                save_path=save_path,
            )
            if best_eval is None or evaluation.result.sort_key() > best_eval.result.sort_key():
                best_eval = evaluation
            if evaluation.result.passed:
                return evaluation.result, evaluation.survivors, evaluation.method_scores
            if repair_used >= repair_rounds or not evaluation.fail_missing_values:
                break

            rescue_methods = self.learn_rescue_methods(
                evaluation.fail_history,
                evaluation.fail_target_values,
                evaluation.fail_missing_values,
                attempt=attempt,
                way_top=way_top,
            )
            before = len(method_pool)
            method_pool = self.dedupe_methods([*method_pool, *rescue_methods])
            for method in rescue_methods:
                method_scores.setdefault(self.method_key(method), float(max(1, method.fit_match_count)) + 5.0)
            if len(method_pool) <= before:
                break

        assert best_eval is not None
        return best_eval.result, best_eval.survivors, best_eval.method_scores

    def evaluate_pool(
        self,
        draws: list[Draw],
        *,
        base_history: list[Draw],
        holdouts: list[Draw],
        method_pool: list[LearnedMethod],
        method_scores: dict[tuple[object, ...], float],
        attempt: RescueAttemptConfig,
        ranking_mode: str,
        holdout_count: int,
        top_k: int,
        way_top: int,
        min_ways: int,
        min_top_hits: int,
        repair_rounds: int,
        repair_used: int,
        save_path: Path | None,
    ) -> RescueEvaluation:
        available_methods = self.dedupe_methods(method_pool)
        steps: list[RescueStepResult] = []
        history = list(base_history)
        for index, target_draw in enumerate(holdouts, 1):
            target = self.draw_values(target_draw)
            method_count_before = len(available_methods)
            signal_values = self.rank_signal_values(
                history,
                available_methods,
                method_scores=method_scores,
                ranking_mode=ranking_mode,
                top_k=top_k,
                way_top=way_top,
            )
            matched = tuple(sorted(set(signal_values) & set(target)))
            value_pools: dict[int, list[LearnedMethod]] = {}
            per_value_counts: Counter[int] = Counter()
            for value in target:
                value_methods = self.methods_that_pull_value(available_methods, history, value, way_top=way_top)
                value_pools[value] = value_methods
                per_value_counts[value] = len(value_methods)
            covered = tuple(value for value in target if per_value_counts.get(value, 0) >= min_ways)
            missing = tuple(value for value in target if value not in set(covered))
            next_methods = self.dedupe_methods(method for value in target for method in value_pools.get(value, []))
            passed = (
                len(covered) == len(target)
                and len(next_methods) > 0
                and (min_top_hits <= 0 or len(matched) >= min_top_hits)
            )
            self.update_method_scores(
                history,
                available_methods,
                target,
                method_scores=method_scores,
                way_top=way_top,
                step_index=index,
            )
            steps.append(
                RescueStepResult(
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
                        f"Ranking {ranking_mode} dừng ở kỳ {index:02d} ({target_draw.draw_date.strftime('%d/%m/%Y')}). "
                        f"Thiếu cách độc lập: {format_values(missing)}. "
                        f"Đủ cách {len(covered)}/6, trùng Top {len(matched)}/6. "
                        f"Đã rescue {repair_used}/{repair_rounds} vòng."
                    )
                else:
                    reason = (
                        f"Ranking {ranking_mode} dừng ở kỳ {index:02d} ({target_draw.draw_date.strftime('%d/%m/%Y')}). "
                        f"Đủ cách độc lập 6/6 nhưng Top {top_k} chỉ trùng {len(matched)}/6, "
                        f"thấp hơn ngưỡng {min_top_hits}. Đã rescue {repair_used}/{repair_rounds} vòng."
                    )
                result = RescueModeResult(
                    passed=False,
                    ranking_mode=ranking_mode,
                    attempt=attempt,
                    holdout_count=holdout_count,
                    top_k=top_k,
                    way_top=way_top,
                    min_ways=min_ways,
                    min_top_hits=min_top_hits,
                    repair_rounds=repair_rounds,
                    repair_used=repair_used,
                    base_history_rows=len(base_history),
                    steps=tuple(steps),
                    final_signal_values=tuple(),
                    survivor_count=len(next_methods),
                    saved_path=None,
                    fail_reason=reason,
                )
                return RescueEvaluation(
                    result=result,
                    survivors=next_methods,
                    method_scores=method_scores,
                    fail_history=tuple(history),
                    fail_target_values=target,
                    fail_missing_values=missing,
                )
            available_methods = next_methods
            history.append(target_draw)

        final_signal = self.rank_signal_values(
            draws,
            available_methods,
            method_scores=method_scores,
            ranking_mode=ranking_mode,
            top_k=top_k,
            way_top=way_top,
        )
        result = RescueModeResult(
            passed=True,
            ranking_mode=ranking_mode,
            attempt=attempt,
            holdout_count=holdout_count,
            top_k=top_k,
            way_top=way_top,
            min_ways=min_ways,
            min_top_hits=min_top_hits,
            repair_rounds=repair_rounds,
            repair_used=repair_used,
            base_history_rows=len(base_history),
            steps=tuple(steps),
            final_signal_values=final_signal,
            survivor_count=len(available_methods),
            saved_path=save_path or SETTINGS.data_dir / "number_rank_rescue_survivors.json",
            fail_reason="",
        )
        return RescueEvaluation(result, available_methods, method_scores, tuple(history), tuple(), tuple())

    def learn_rescue_methods(
        self,
        history: Sequence[Draw],
        target_values: tuple[int, ...],
        missing_values: tuple[int, ...],
        *,
        attempt: RescueAttemptConfig,
        way_top: int,
    ) -> list[LearnedMethod]:
        if not missing_values or len(target_values) != 6:
            return []
        missing = set(missing_values)
        methods = self.engine.learn_methods(
            history,
            target_values,
            top_k=way_top,
            max_lag=attempt.max_lag,
            support_values=tuple(range(1, attempt.support_max + 1)),
            strategy_mode="full",
            limit=max(120, min(attempt.method_count, attempt.method_count // 2)),
            ensemble_pool=max(20, min(attempt.ensemble_pool, 80)),
        )
        result: list[LearnedMethod] = []
        for method in methods:
            values = self.engine.signal_values_from_method(history, method, top_k=way_top)
            if set(values) & missing:
                result.append(method)
        return self.dedupe_methods(result)

    def rank_signal_values(
        self,
        draws: Sequence[Draw],
        methods: Sequence[LearnedMethod],
        *,
        method_scores: dict[tuple[object, ...], float],
        ranking_mode: str,
        top_k: int,
        way_top: int,
    ) -> tuple[int, ...]:
        counts: Counter[int] = Counter()
        scores: defaultdict[int, float] = defaultdict(float)
        first_seen_rank: dict[int, int] = {}
        for method_index, method in enumerate(methods):
            values = self.engine.signal_values_from_method(draws, method, top_k=way_top)
            base_score = method_scores.get(self.method_key(method), float(max(1, method.fit_match_count)))
            for rank, value in enumerate(values, 1):
                counts[value] += 1
                first_seen_rank[value] = min(first_seen_rank.get(value, rank), rank)
                if ranking_mode == "vote":
                    value_score = 1.0
                elif ranking_mode == "weighted":
                    value_score = base_score * (way_top - rank + 1)
                elif ranking_mode == "ranked_vote":
                    value_score = way_top - rank + 1
                elif ranking_mode == "recent_score":
                    value_score = (base_score + method_index + 1) / rank
                elif ranking_mode == "coverage_balanced":
                    value_score = (way_top - rank + 1) / max(1.0, counts[value] ** 0.35)
                elif ranking_mode == "missing_first":
                    value_score = base_score * ((way_top - rank + 1) / way_top) / max(1.0, counts[value] ** 0.15)
                else:
                    value_score = 1.0
                scores[value] += value_score
        ranked = sorted(
            counts,
            key=lambda value: (scores[value], counts[value], -first_seen_rank.get(value, way_top + 1), value),
            reverse=True,
        )
        return tuple(ranked[:top_k])

    def update_method_scores(
        self,
        draws: Sequence[Draw],
        methods: Sequence[LearnedMethod],
        target: tuple[int, ...],
        *,
        method_scores: dict[tuple[object, ...], float],
        way_top: int,
        step_index: int,
    ) -> None:
        target_set = set(target)
        recency_bonus = 1.0 + step_index / 10.0
        for method in methods:
            key = self.method_key(method)
            values = self.engine.signal_values_from_method(draws, method, top_k=way_top)
            hits = target_set & set(values)
            if not hits:
                method_scores[key] = method_scores.get(key, 1.0) * 0.95
                continue
            best_rank = min(values.index(value) + 1 for value in hits)
            rank_bonus = (way_top - best_rank + 1) / way_top
            method_scores[key] = method_scores.get(key, 1.0) + recency_bonus + rank_bonus + len(hits) * 0.25

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
    ) -> list[RescueAttemptConfig]:
        rounds = max(1, max_rounds)
        return [
            RescueAttemptConfig(
                round_index=index,
                method_count=min(1800, method_count * index),
                ensemble_pool=min(240, ensemble_pool + (index - 1) * 40),
                max_lag=min(45, max_lag + (index - 1) * 8),
                support_max=min(12, support_max + (index - 1) * 2),
            )
            for index in range(1, rounds + 1)
        ]

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
    def copy_result_with_saved_path(result: RescueModeResult, saved_path: Path) -> RescueModeResult:
        return RescueModeResult(
            passed=result.passed,
            ranking_mode=result.ranking_mode,
            attempt=result.attempt,
            holdout_count=result.holdout_count,
            top_k=result.top_k,
            way_top=result.way_top,
            min_ways=result.min_ways,
            min_top_hits=result.min_top_hits,
            repair_rounds=result.repair_rounds,
            repair_used=result.repair_used,
            base_history_rows=result.base_history_rows,
            steps=result.steps,
            final_signal_values=result.final_signal_values,
            survivor_count=result.survivor_count,
            saved_path=saved_path,
            fail_reason=result.fail_reason,
        )

    @staticmethod
    def save_survivors(
        methods: Sequence[LearnedMethod],
        *,
        method_scores: dict[tuple[object, ...], float],
        result: RescueModeResult,
        path: Path | None = None,
    ) -> Path:
        target_path = path or SETTINGS.data_dir / "number_rank_rescue_survivors.json"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "number_ranking_rescue_lab",
            "passed": result.passed,
            "ranking_mode": result.ranking_mode,
            "holdout_count": result.holdout_count,
            "top_k": result.top_k,
            "way_top": result.way_top,
            "min_ways": result.min_ways,
            "min_top_hits": result.min_top_hits,
            "repair_rounds": result.repair_rounds,
            "repair_used": result.repair_used,
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
