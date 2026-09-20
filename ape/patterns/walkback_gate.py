"""Walk-back survivor gate for strict historical validation.

The gate works on the latest N historical rows. It first fits methods on the
first holdout row, then only keeps methods that continue to produce correct
numbers in the next holdout rows. A future signal is released only when every
holdout row passes the strict all-target-numbers gate.

This is a validation and method-selection workflow. It is intentionally strict
and may fail when the historical data does not contain a stable signal.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Sequence

from ape.core.settings import SETTINGS
from ape.database.models import Draw
from ape.patterns.audit import format_values
from ape.patterns.target_learning import LearnedMethod, LearnedMethodStore, TargetLearningEngine


@dataclass(slots=True, frozen=True)
class WalkbackAttemptConfig:
    """Search size for one automatic walk-back attempt."""

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
class WalkbackStepResult:
    """One holdout-period result."""

    index: int
    draw_date: object
    target_values: tuple[int, ...]
    signal_values: tuple[int, ...]
    matched_values: tuple[int, ...]
    passed: bool
    survivor_count_before: int
    survivor_count_after: int
    per_value_way_counts: dict[int, int]

    @property
    def hit_count(self) -> int:
        return len(self.matched_values)

    def to_lines(self) -> list[str]:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"Kỳ {self.index:02d} · {self.draw_date.strftime('%d/%m/%Y')} · {status}",
            f"  Dãy đúng      : {format_values(self.target_values)}",
            f"  Tín hiệu      : {format_values(self.signal_values)}",
            f"  Trùng         : {self.hit_count}/6" + (f" · {format_values(self.matched_values)}" if self.matched_values else ""),
            f"  Cách còn sống : {self.survivor_count_before} → {self.survivor_count_after}",
            "  Số cách kéo từng số:",
        ]
        for value in self.target_values:
            lines.append(f"    - {value:02d}: {self.per_value_way_counts.get(value, 0)} cách")
        return lines


@dataclass(slots=True, frozen=True)
class WalkbackGateResult:
    """Final result of the walk-back survivor gate."""

    passed: bool
    attempt: WalkbackAttemptConfig
    holdout_count: int
    top_k: int
    base_history_rows: int
    steps: tuple[WalkbackStepResult, ...]
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

    def sort_key(self) -> tuple[int, int, int]:
        return (self.passed_steps, self.total_hits, self.survivor_count)

    def to_lines(self) -> list[str]:
        title = "PASS - ĐỦ GATE WALK-BACK" if self.passed else "FAIL - CHƯA ĐỦ GATE WALK-BACK"
        lines = [
            "================ WALK-BACK 10 KỲ GATE ================",
            title,
            f"Cấu hình       : {self.attempt.label}",
            f"Số kỳ holdout  : {self.holdout_count}",
            f"Top tín hiệu   : {self.top_k}",
            f"Vùng học gốc   : {self.base_history_rows} kỳ",
            f"Kỳ đã pass     : {self.passed_steps}/{self.holdout_count}",
            f"Tổng số trùng  : {self.total_hits}/{self.holdout_count * 6}",
            f"Cách còn sống  : {self.survivor_count}",
            "",
        ]
        for step in self.steps:
            lines.extend(step.to_lines())
            lines.append("-" * 58)
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
                    self.fail_reason or "Chưa vượt đủ 10 kỳ kiểm định nên không xuất tín hiệu kỳ mới.",
                    "Tool không ép kết quả. Khi gate fail, cần cập nhật dữ liệu hoặc mở rộng/đổi nhóm phương pháp rồi chạy lại.",
                ]
            )
        lines.append("=======================================================")
        return lines


class WalkbackGateTrainer:
    """Strict walk-back trainer that only releases signals after all holdout rows pass."""

    def __init__(self, engine: TargetLearningEngine | None = None) -> None:
        self.engine = engine or TargetLearningEngine()

    def train(
        self,
        draws: Sequence[Draw],
        *,
        holdout_count: int = 10,
        top_k: int = 6,
        method_count: int = 200,
        ensemble_pool: int = 30,
        max_lag: int = 12,
        support_max: int = 5,
        max_rounds: int = 3,
        min_base_history: int = 60,
        save_path: Path | None = None,
    ) -> WalkbackGateResult:
        source_draws = list(draws)
        if holdout_count < 1:
            raise ValueError("holdout_count must be at least 1")
        if top_k < 6:
            raise ValueError("top_k must be at least 6 because each target row has 6 numbers")
        if len(source_draws) <= holdout_count + min_base_history:
            raise ValueError(
                f"Cần ít nhất {holdout_count + min_base_history + 1} kỳ để walk-back đúng. "
                f"Hiện có {len(source_draws)} kỳ."
            )

        best_result: WalkbackGateResult | None = None
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
                min_base_history=min_base_history,
                save_path=save_path,
            )
            if result.passed:
                saved = self.save_survivors(
                    survivors,
                    result=result,
                    path=save_path,
                )
                return WalkbackGateResult(
                    passed=True,
                    attempt=result.attempt,
                    holdout_count=result.holdout_count,
                    top_k=result.top_k,
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
        attempt: WalkbackAttemptConfig,
        holdout_count: int,
        top_k: int,
        min_base_history: int,
        save_path: Path | None,
    ) -> tuple[WalkbackGateResult, list[LearnedMethod]]:
        base_history = draws[:-holdout_count]
        holdouts = draws[-holdout_count:]
        if len(base_history) < min_base_history:
            raise ValueError("Không đủ dữ liệu trước vùng holdout để huấn luyện.")

        first_target = self.draw_values(holdouts[0])
        survivors = self.engine.learn_methods(
            base_history,
            first_target,
            top_k=top_k,
            max_lag=attempt.max_lag,
            support_values=tuple(range(1, attempt.support_max + 1)),
            strategy_mode="full",
            limit=attempt.method_count,
            ensemble_pool=attempt.ensemble_pool,
        )
        survivors = self.dedupe_methods(survivors)

        steps: list[WalkbackStepResult] = []
        history = list(base_history)
        fail_reason = ""

        for index, target_draw in enumerate(holdouts, 1):
            target = self.draw_values(target_draw)
            signal_values = self.engine.combined_signal_values(history, survivors, top_k=top_k)
            matched = tuple(sorted(set(signal_values) & set(target)))
            next_survivors, per_value_way_counts = self.survivors_that_hit(
                survivors,
                history,
                target,
                top_k=top_k,
            )
            passed = set(target).issubset(set(signal_values)) and len(next_survivors) > 0
            steps.append(
                WalkbackStepResult(
                    index=index,
                    draw_date=target_draw.draw_date,
                    target_values=target,
                    signal_values=signal_values,
                    matched_values=matched,
                    passed=passed,
                    survivor_count_before=len(survivors),
                    survivor_count_after=len(next_survivors),
                    per_value_way_counts=dict(per_value_way_counts),
                )
            )
            if not passed:
                missing = tuple(sorted(set(target) - set(signal_values)))
                fail_reason = (
                    f"Gate dừng ở kỳ {index:02d} ({target_draw.draw_date.strftime('%d/%m/%Y')}). "
                    f"Thiếu: {format_values(missing)}. "
                    f"Chỉ trùng {len(matched)}/6 trong Top {top_k}."
                )
                return (
                    WalkbackGateResult(
                        passed=False,
                        attempt=attempt,
                        holdout_count=holdout_count,
                        top_k=top_k,
                        base_history_rows=len(base_history),
                        steps=tuple(steps),
                        final_signal_values=tuple(),
                        survivor_count=len(next_survivors),
                        saved_path=None,
                        fail_reason=fail_reason,
                    ),
                    next_survivors,
                )
            survivors = next_survivors
            history.append(target_draw)

        final_signal = self.engine.combined_signal_values(draws, survivors, top_k=top_k)
        return (
            WalkbackGateResult(
                passed=True,
                attempt=attempt,
                holdout_count=holdout_count,
                top_k=top_k,
                base_history_rows=len(base_history),
                steps=tuple(steps),
                final_signal_values=final_signal,
                survivor_count=len(survivors),
                saved_path=save_path or SETTINGS.data_dir / "walkback_survivors.json",
                fail_reason="",
            ),
            survivors,
        )

    def survivors_that_hit(
        self,
        methods: Sequence[LearnedMethod],
        draws: Sequence[Draw],
        target_values: tuple[int, ...],
        *,
        top_k: int,
    ) -> tuple[list[LearnedMethod], Counter[int]]:
        target = set(target_values)
        survivors: list[LearnedMethod] = []
        per_value_counts: Counter[int] = Counter()
        for method in methods:
            values = self.engine.signal_values_from_method(draws, method, top_k=top_k)
            hits = set(values) & target
            if not hits:
                continue
            survivors.append(method)
            for value in hits:
                per_value_counts[value] += 1
        return self.dedupe_methods(survivors), per_value_counts

    @staticmethod
    def attempt_configs(
        *,
        method_count: int,
        ensemble_pool: int,
        max_lag: int,
        support_max: int,
        max_rounds: int,
    ) -> list[WalkbackAttemptConfig]:
        rounds = max(1, max_rounds)
        configs: list[WalkbackAttemptConfig] = []
        for index in range(1, rounds + 1):
            multiplier = index
            configs.append(
                WalkbackAttemptConfig(
                    round_index=index,
                    method_count=min(1000, method_count * multiplier),
                    ensemble_pool=min(150, ensemble_pool + (index - 1) * 20),
                    max_lag=min(30, max_lag + (index - 1) * 6),
                    support_max=min(10, support_max + (index - 1) * 2),
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

    def dedupe_methods(self, methods: Sequence[LearnedMethod]) -> list[LearnedMethod]:
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
        result: WalkbackGateResult,
        path: Path | None = None,
    ) -> Path:
        target_path = path or SETTINGS.data_dir / "walkback_survivors.json"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "mode": "walkback_survivor_gate",
            "passed": result.passed,
            "holdout_count": result.holdout_count,
            "top_k": result.top_k,
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
