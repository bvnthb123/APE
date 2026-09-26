"""Ranking lab for independent number-chain validation.

The independent chain gate can prove that methods exist for every target number,
but a separate ranking layer must still choose the public Top-N signal before the
future row is known. This module tests several ranking modes on the same
walk-back chain and keeps the mode that survives farthest.
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
)


@dataclass(slots=True, frozen=True)
class RankingAttemptConfig:
    """Search size for one ranking-lab attempt."""

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
class RankingStepResult:
    """One holdout step for one ranking mode."""

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
class RankingModeResult:
    """Result for one ranking mode."""

    passed: bool
    ranking_mode: str
    attempt: RankingAttemptConfig
    holdout_count: int
    top_k: int
    way_top: int
    min_ways: int
    min_top_hits: int
    base_history_rows: int
    steps: tuple[RankingStepResult, ...]
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

    def sort_key(self) -> tuple[int, int, int, int, int]:
        return (
            self.passed_steps,
            self.total_hits,
            self.total_coverage,
            -self.zero_top_steps,
            self.survivor_count,
        )

    def summary_line(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"{self.ranking_mode:<18} {status:<4} · pass {self.passed_steps:02d}/{self.holdout_count} · "
            f"trùng Top {self.total_hits:02d}/{self.holdout_count * 6} · "
            f"đủ cách {self.total_coverage:02d}/{self.holdout_count * 6} · "
            f"Top 0/6: {self.zero_top_steps} kỳ · sống sót {self.survivor_count}"
        )

    def detail_lines(self) -> list[str]:
        title = "PASS - RANKING ĐỦ GATE" if self.passed else "FAIL - RANKING CHƯA ĐỦ GATE"
        lines = [
            "================ NUMBER RANKING LAB ================",
            title,
            f"Ranking mode     : {self.ranking_mode}",
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
                    f"File lưu bộ ranking sống sót: {self.saved_path}" if self.saved_path else "File lưu bộ ranking sống sót: -",
                ]
            )
        else:
            lines.extend(
                [
                    "KẾT LUẬN",
                    self.fail_reason or "Chưa có ranking nào vượt đủ chuỗi kiểm định.",
                    "Tool không ép kết quả. Nếu tất cả ranking đều fail, Top hiện tại chưa đủ lực kiểm chứng.",
                ]
            )
        lines.append("=====================================================")
        return lines


@dataclass(slots=True, frozen=True)
class RankingLabResult:
    """Comparison of all ranking modes."""

    results: tuple[RankingModeResult, ...]
    best: RankingModeResult

    @property
    def passed(self) -> bool:
        return self.best.passed

    def to_lines(self) -> list[str]:
        lines = [
            "================ NUMBER RANKING LAB SUMMARY ================",
            "So sánh các kiểu xếp Top 7 trên cùng chuỗi walkback.",
            "",
        ]
        for result in sorted(self.results, key=lambda item: item.sort_key(), reverse=True):
            lines.append(result.summary_line())
        lines.extend(
            [
                "",
                f"Ranking tốt nhất: {self.best.ranking_mode}",
                "",
            ]
        )
        lines.extend(self.best.detail_lines())
        return lines


class NumberRankingLabTrainer:
    """Run several ranking modes and keep the strongest validated one."""

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
        ranking_modes: Sequence[str] = RANKING_MODES,
        save_path: Path | None = None,
    ) -> RankingLabResult:
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
                f"Cần ít nhất {holdout_count + min_base_history + 1} kỳ để kiểm định ranking. "
                f"Hiện có {len(source_draws)} kỳ."
            )

        evaluated: list[RankingModeResult] = []
        allowed_modes = tuple(mode for mode in ranking_modes if mode in RANKING_MODES)
        if not allowed_modes:
            allowed_modes = RANKING_MODES

        for attempt in self.attempt_configs(
            method_count=method_count,
            ensemble_pool=ensemble_pool,
            max_lag=max_lag,
            support_max=support_max,
            max_rounds=max_rounds,
        ):
            for mode in allowed_modes:
                result, survivors, method_scores = self.run_mode(
                    source_draws,
                    attempt=attempt,
                    ranking_mode=mode,
                    holdout_count=holdout_count,
                    top_k=top_k,
                    way_top=effective_way_top,
                    min_base_history=min_base_history,
                    min_ways=min_ways,
                    min_top_hits=min_top_hits,
                    save_path=save_path,
                )
                if result.passed:
                    saved = self.save_survivors(
                        survivors,
                        method_scores=method_scores,
                        result=result,
                        path=save_path,
                    )
                    result = RankingModeResult(
                        passed=True,
                        ranking_mode=result.ranking_mode,
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
                evaluated.append(result)

        best = max(evaluated, key=lambda item: item.sort_key())
        return RankingLabResult(results=tuple(evaluated), best=best)

    def run_mode(
        self,
        draws: list[Draw],
        *,
        attempt: RankingAttemptConfig,
        ranking_mode: str,
        holdout_count: int,
        top_k: int,
        way_top: int,
        min_base_history: int,
        min_ways: int,
        min_top_hits: int,
        save_path: Path | None,
    ) -> tuple[RankingModeResult, list[LearnedMethod], dict[tuple[object, ...], float]]:
        base_history = draws[:-holdout_count]
        holdouts = draws[-holdout_count:]
        if len(base_history) < min_base_history:
            raise ValueError("Không đủ dữ liệu trước vùng holdout để học ranking.")

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
        method_scores: dict[tuple[object, ...], float] = {
            self.method_key(method): float(max(1, method.fit_match_count))
            for method in available_methods
        }

        steps: list[RankingStepResult] = []
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
                value_methods = self.methods_that_pull_value(
                    available_methods,
                    history,
                    value,
                    way_top=way_top,
                )
                value_pools[value] = value_methods
                per_value_counts[value] = len(value_methods)

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
            self.update_method_scores(
                history,
                available_methods,
                target,
                method_scores=method_scores,
                way_top=way_top,
                step_index=index,
            )
            steps.append(
                RankingStepResult(
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
                        f"Đủ cách {len(covered)}/6, trùng Top {len(matched)}/6."
                    )
                else:
                    reason = (
                        f"Ranking {ranking_mode} dừng ở kỳ {index:02d} ({target_draw.draw_date.strftime('%d/%m/%Y')}). "
                        f"Đủ cách độc lập 6/6 nhưng Top {top_k} chỉ trùng {len(matched)}/6, "
                        f"thấp hơn ngưỡng {min_top_hits}."
                    )
                return (
                    RankingModeResult(
                        passed=False,
                        ranking_mode=ranking_mode,
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
                    method_scores,
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
        return (
            RankingModeResult(
                passed=True,
                ranking_mode=ranking_mode,
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
                saved_path=save_path or SETTINGS.data_dir / "number_rank_survivors.json",
                fail_reason="",
            ),
            available_methods,
            method_scores,
        )

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
        if not methods:
            return tuple()

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
                    value_score = (way_top - rank + 1)
                elif ranking_mode == "recent_score":
                    value_score = (base_score + method_index + 1) / rank
                elif ranking_mode == "coverage_balanced":
                    value_score = (way_top - rank + 1) / max(1.0, counts[value] ** 0.35)
                else:
                    value_score = 1.0
                scores[value] += value_score

        if ranking_mode == "coverage_balanced":
            ranked = sorted(
                counts,
                key=lambda value: (scores[value], -abs(counts[value] - 3), -first_seen_rank.get(value, way_top + 1), value),
                reverse=True,
            )
        else:
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
    ) -> list[RankingAttemptConfig]:
        rounds = max(1, max_rounds)
        configs: list[RankingAttemptConfig] = []
        for index in range(1, rounds + 1):
            configs.append(
                RankingAttemptConfig(
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
        method_scores: dict[tuple[object, ...], float],
        result: RankingModeResult,
        path: Path | None = None,
    ) -> Path:
        target_path = path or SETTINGS.data_dir / "number_rank_survivors.json"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "number_ranking_lab",
            "passed": result.passed,
            "ranking_mode": result.ranking_mode,
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
