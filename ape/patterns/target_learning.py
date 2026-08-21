"""Target learning engine for fitting known rows and saving methods.

This module lets APE accept a newly known historical row, try many calculation
methods and method ensembles against that known row, save the best-fitting
methods, then reuse those learned methods for the next signal run.

The learning step fits a known historical target. It is useful for error
analysis and method selection, but it does not make future results knowable or
guaranteed.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import combinations
import json
import re
from pathlib import Path
from typing import Any, Sequence

from ape.core.settings import SETTINGS
from ape.database.models import Draw
from ape.patterns.audit import format_values
from ape.patterns.optimizer import StrategyConfig, StrategyOptimizer

WEEKDAY_NAMES = (
    "Thứ Hai",
    "Thứ Ba",
    "Thứ Tư",
    "Thứ Năm",
    "Thứ Sáu",
    "Thứ Bảy",
    "Chủ Nhật",
)
NUMBER_MIN = 1
NUMBER_MAX = 45


@dataclass(slots=True, frozen=True)
class LearnedMethod:
    """One method or method ensemble that was fitted to a known target row."""

    method_type: str
    label: str
    configs: tuple[StrategyConfig, ...]
    top_k: int
    fit_signal_values: tuple[int, ...]
    fit_target_values: tuple[int, ...]
    fit_matched_values: tuple[int, ...]
    fit_score: float
    saved_at: str

    @property
    def fit_match_count(self) -> int:
        return len(self.fit_matched_values)

    @property
    def fit_signal_label(self) -> str:
        return format_values(self.fit_signal_values)

    @property
    def fit_target_label(self) -> str:
        return format_values(self.fit_target_values)

    @property
    def fit_match_label(self) -> str:
        return format_values(self.fit_matched_values) if self.fit_matched_values else "-"

    @property
    def type_label(self) -> str:
        if self.method_type == "ensemble":
            return "Tổ hợp"
        if self.method_type == "rescue":
            return "Rescue"
        return "Đơn lẻ"

    def to_row(self, rank: int, next_values: Sequence[int] = ()) -> tuple[str, ...]:
        return (
            str(rank),
            self.type_label,
            self.label,
            self.fit_signal_label,
            str(self.fit_match_count),
            self.fit_match_label,
            f"{self.fit_score:.3f}",
            format_values(next_values) if next_values else "-",
        )


@dataclass(slots=True, frozen=True)
class TargetLearningResult:
    """Result of fitting methods to one known target row."""

    target_values: tuple[int, ...]
    learned_methods: tuple[LearnedMethod, ...]
    next_signal_values: tuple[int, ...]
    saved_path: Path
    stored_draw_date: date | None = None
    stored_draw_created: bool | None = None

    @property
    def target_label(self) -> str:
        return format_values(self.target_values)

    @property
    def next_signal_label(self) -> str:
        return format_values(self.next_signal_values) if self.next_signal_values else "Chưa đủ dữ liệu"

    @property
    def best_match_count(self) -> int:
        return max((method.fit_match_count for method in self.learned_methods), default=0)

    @property
    def exact_fit_count(self) -> int:
        return sum(1 for method in self.learned_methods if method.fit_match_count >= 6)

    def summary_rows(self) -> list[tuple[str, str]]:
        rows = [
            ("Chế độ", "Target Learning Lab"),
            ("Dãy số dùng để học", self.target_label),
            ("Số phương pháp đã lưu", str(len(self.learned_methods))),
            ("Số khớp cao nhất khi fit", str(self.best_match_count)),
            ("Số phương pháp khớp đủ 6 số", str(self.exact_fit_count)),
            ("Top tín hiệu kỳ tiếp theo", self.next_signal_label),
            ("File lưu phương pháp", str(self.saved_path)),
        ]
        if self.stored_draw_date is not None:
            status = "thêm mới" if self.stored_draw_created else "cập nhật"
            rows.append(("Đã đưa vào dữ liệu lịch sử", f"{self.stored_draw_date.strftime('%d/%m/%Y')} ({status})"))
        return rows


class LearnedMethodStore:
    """Persist the best target-fitted methods for later signal runs."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or SETTINGS.data_dir / "learned_methods.json"

    def save(self, methods: Sequence[LearnedMethod]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "methods": [self.method_to_dict(method) for method in methods],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.path

    def load(self) -> tuple[LearnedMethod, ...]:
        if not self.path.exists():
            return ()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return tuple(self.method_from_dict(item) for item in payload.get("methods", []))

    @staticmethod
    def config_to_dict(config: StrategyConfig) -> dict[str, Any]:
        return {
            "name": config.name,
            "lag": config.lag,
            "min_support": config.min_support,
            "use_structure": config.use_structure,
            "use_repeat_overlap": config.use_repeat_overlap,
            "lag_offsets": list(config.lag_offsets),
        }

    @staticmethod
    def config_from_dict(payload: dict[str, Any]) -> StrategyConfig:
        return StrategyConfig(
            name=str(payload["name"]),
            lag=int(payload["lag"]),
            min_support=int(payload["min_support"]),
            use_structure=bool(payload["use_structure"]),
            use_repeat_overlap=bool(payload["use_repeat_overlap"]),
            lag_offsets=tuple(int(value) for value in payload.get("lag_offsets", [0])),
        )

    @classmethod
    def method_to_dict(cls, method: LearnedMethod) -> dict[str, Any]:
        return {
            "method_type": method.method_type,
            "label": method.label,
            "top_k": method.top_k,
            "fit_signal_values": list(method.fit_signal_values),
            "fit_target_values": list(method.fit_target_values),
            "fit_matched_values": list(method.fit_matched_values),
            "fit_score": method.fit_score,
            "saved_at": method.saved_at,
            "configs": [cls.config_to_dict(config) for config in method.configs],
        }

    @classmethod
    def method_from_dict(cls, payload: dict[str, Any]) -> LearnedMethod:
        return LearnedMethod(
            method_type=str(payload["method_type"]),
            label=str(payload["label"]),
            configs=tuple(cls.config_from_dict(item) for item in payload.get("configs", [])),
            top_k=int(payload.get("top_k", 7)),
            fit_signal_values=tuple(int(value) for value in payload.get("fit_signal_values", [])),
            fit_target_values=tuple(int(value) for value in payload.get("fit_target_values", [])),
            fit_matched_values=tuple(int(value) for value in payload.get("fit_matched_values", [])),
            fit_score=float(payload.get("fit_score", 0.0)),
            saved_at=str(payload.get("saved_at", "")),
        )


class TargetLearningEngine:
    """Fit many calculation methods to a known target row and reuse them."""

    def __init__(self, optimizer: StrategyOptimizer | None = None) -> None:
        self.optimizer = optimizer or StrategyOptimizer()

    def learn_methods(
        self,
        draws: Sequence[Draw],
        target_values: Sequence[int],
        *,
        top_k: int = 7,
        max_lag: int = 10,
        support_values: Sequence[int] = (1, 2, 3),
        strategy_mode: str = "full",
        limit: int = 20,
        ensemble_pool: int = 14,
    ) -> list[LearnedMethod]:
        if not draws:
            return []
        target = tuple(sorted(int(value) for value in target_values))
        if len(target) != 6:
            raise ValueError("Target row must contain exactly 6 values.")

        individual_methods = self.evaluate_individual_methods(
            draws,
            target,
            top_k=top_k,
            max_lag=max_lag,
            support_values=support_values,
            strategy_mode=strategy_mode,
        )
        rescue_methods = self.evaluate_rescue_methods(
            draws,
            target,
            top_k=top_k,
            max_lag=max_lag,
        )
        ensemble_methods = self.evaluate_ensemble_methods(
            draws,
            target,
            individual_methods[:ensemble_pool],
            top_k=top_k,
        )
        methods = individual_methods + rescue_methods + ensemble_methods
        methods.sort(key=lambda item: (item.fit_match_count, item.fit_score), reverse=True)
        return methods[:limit]

    def evaluate_individual_methods(
        self,
        draws: Sequence[Draw],
        target: tuple[int, ...],
        *,
        top_k: int,
        max_lag: int,
        support_values: Sequence[int],
        strategy_mode: str,
    ) -> list[LearnedMethod]:
        methods: list[LearnedMethod] = []
        seen: set[str] = set()
        for lag in range(1, max_lag + 1):
            for support in support_values:
                for config in self.optimizer.generate_configs(
                    lag=lag,
                    base_min_support=support,
                    strategy_mode=strategy_mode,
                ):
                    method_id = self.config_id(config)
                    if method_id in seen:
                        continue
                    seen.add(method_id)
                    signals = self.optimizer.select_candidates(draws, config, top_k=top_k)
                    signal_values = tuple(signal.value for signal in signals)
                    matched = tuple(sorted(set(signal_values) & set(target)))
                    signal_score = sum(signal.score for signal in signals)
                    methods.append(
                        LearnedMethod(
                            method_type="single",
                            label=config.detail_label,
                            configs=(config,),
                            top_k=top_k,
                            fit_signal_values=signal_values,
                            fit_target_values=target,
                            fit_matched_values=matched,
                            fit_score=len(matched) * 1000 + signal_score,
                            saved_at=datetime.now().isoformat(timespec="seconds"),
                        )
                    )
        methods.sort(key=lambda item: (item.fit_match_count, item.fit_score), reverse=True)
        return methods

    def evaluate_rescue_methods(
        self,
        draws: Sequence[Draw],
        target: tuple[int, ...],
        *,
        top_k: int,
        max_lag: int,
    ) -> list[LearnedMethod]:
        """Evaluate broader non-pattern strategies against the known target."""
        labels = self.rescue_labels(max_lag=max_lag)
        methods: list[LearnedMethod] = []
        seen: set[str] = set()
        for label in labels:
            if label in seen:
                continue
            seen.add(label)
            scores = self.rescue_scores(draws, label)
            signal_values = self.values_from_scores(scores, top_k=top_k)
            matched = tuple(sorted(set(signal_values) & set(target)))
            fit_signal_score = sum(scores.get(value, 0.0) for value in signal_values)
            methods.append(
                LearnedMethod(
                    method_type="rescue",
                    label=label,
                    configs=tuple(),
                    top_k=top_k,
                    fit_signal_values=signal_values,
                    fit_target_values=target,
                    fit_matched_values=matched,
                    fit_score=len(matched) * 1500 + fit_signal_score,
                    saved_at=datetime.now().isoformat(timespec="seconds"),
                )
            )
        methods.sort(key=lambda item: (item.fit_match_count, item.fit_score), reverse=True)
        return methods

    def rescue_labels(self, *, max_lag: int) -> list[str]:
        windows = (20, 40, 80, 160, 0)
        labels: list[str] = []
        for window in windows:
            label_window = "all" if window == 0 else str(window)
            labels.append(f"Rescue|hot_recent|window={label_window}")
            labels.append(f"Rescue|cold_gap|window={label_window}")
            labels.append(f"Rescue|hybrid_hot_gap|window={label_window}")
        labels.extend(
            [
                "Rescue|same_weekday|window=all",
                "Rescue|same_weekday|window=120",
                "Rescue|recent_overlap|lags=1,2,3,5,8,13",
                "Rescue|neighbor_shift|distance=1",
                "Rescue|neighbor_shift|distance=2",
            ]
        )
        for lag in range(1, max_lag + 1):
            labels.append(f"Rescue|transition_loose|lag={lag}")
            labels.append(f"Rescue|pair_follow|lag={lag}")
        return labels

    def evaluate_ensemble_methods(
        self,
        draws: Sequence[Draw],
        target: tuple[int, ...],
        base_methods: Sequence[LearnedMethod],
        *,
        top_k: int,
    ) -> list[LearnedMethod]:
        methods: list[LearnedMethod] = []
        configs = [method.configs[0] for method in base_methods if method.configs]
        combo_sets = list(combinations(configs[:12], 2)) + list(combinations(configs[:9], 3))
        seen: set[str] = set()
        for combo in combo_sets:
            label = " + ".join(self.short_config_label(config) for config in combo)
            method_id = "ensemble|" + "||".join(self.config_id(config) for config in combo)
            if method_id in seen:
                continue
            seen.add(method_id)
            signal_values = self.ensemble_signal_values(draws, combo, top_k=top_k)
            matched = tuple(sorted(set(signal_values) & set(target)))
            methods.append(
                LearnedMethod(
                    method_type="ensemble",
                    label=label,
                    configs=tuple(combo),
                    top_k=top_k,
                    fit_signal_values=signal_values,
                    fit_target_values=target,
                    fit_matched_values=matched,
                    fit_score=len(matched) * 1200 + len(combo) * 10,
                    saved_at=datetime.now().isoformat(timespec="seconds"),
                )
            )
        methods.sort(key=lambda item: (item.fit_match_count, item.fit_score), reverse=True)
        return methods

    def rescue_scores(self, draws: Sequence[Draw], label: str) -> dict[int, float]:
        parts = self.parse_rescue_label(label)
        kind = parts.get("kind", "")
        scores: dict[int, float] = defaultdict(float)
        if not draws:
            return scores

        if kind == "hot_recent":
            for value, count in self.frequency_counts(draws, parts).items():
                scores[value] += float(count)
        elif kind == "cold_gap":
            for value, gap in self.gap_counts(draws).items():
                scores[value] += float(gap)
        elif kind == "hybrid_hot_gap":
            freq = self.frequency_counts(draws, parts)
            gaps = self.gap_counts(draws)
            recent = self.frequency_counts(draws, {"window": "20"})
            for value in range(NUMBER_MIN, NUMBER_MAX + 1):
                scores[value] += freq.get(value, 0) * 2.0
                scores[value] += gaps.get(value, 0) * 0.35
                scores[value] += recent.get(value, 0) * 0.6
        elif kind == "same_weekday":
            target_weekday = next_auto_draw_date(draws).weekday()
            subset = [draw for draw in self.windowed_draws(draws, parts) if draw.weekday_index == target_weekday]
            if not subset:
                subset = list(draws)
            for value, count in self.count_values(subset).items():
                scores[value] += float(count)
        elif kind == "recent_overlap":
            lags = [int(item) for item in parts.get("lags", "1,2,3").split(",") if item]
            total = len(draws)
            for lag in lags:
                if lag <= 0 or lag > total:
                    continue
                weight = 1.0 / max(1, lag)
                for value in draws[-lag].numbers:
                    scores[value] += 10.0 * weight
        elif kind == "neighbor_shift":
            distance = int(parts.get("distance", "1"))
            freq = self.frequency_counts(draws, {"window": "80"})
            for value in draws[-1].numbers:
                for candidate in (value - distance, value + distance):
                    if NUMBER_MIN <= candidate <= NUMBER_MAX:
                        scores[candidate] += 10.0 + freq.get(candidate, 0)
        elif kind == "transition_loose":
            lag = int(parts.get("lag", "1"))
            anchor = set(draws[-1].numbers)
            for index in range(0, len(draws) - lag):
                overlap = len(anchor & set(draws[index].numbers))
                if overlap <= 0:
                    continue
                for value in draws[index + lag].numbers:
                    scores[value] += float(overlap)
        elif kind == "pair_follow":
            lag = int(parts.get("lag", "1"))
            anchor = set(draws[-1].numbers)
            for index in range(0, len(draws) - lag):
                overlap = len(anchor & set(draws[index].numbers))
                if overlap < 2:
                    continue
                for value in draws[index + lag].numbers:
                    scores[value] += float(overlap * overlap)

        if not scores:
            for value, count in self.count_values(draws).items():
                scores[value] = float(count)
        return dict(scores)

    def ensemble_signal_values(
        self,
        draws: Sequence[Draw],
        configs: Sequence[StrategyConfig],
        *,
        top_k: int = 7,
    ) -> tuple[int, ...]:
        scores: dict[int, float] = defaultdict(float)
        for config in configs:
            signals = self.optimizer.select_candidates(draws, config, top_k=max(top_k * 2, 14))
            for rank, signal in enumerate(signals, 1):
                scores[signal.value] += (top_k * 2 - rank + 1) + signal.score * 0.001
        ranked = sorted(scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
        return tuple(value for value, _score in ranked[:top_k])

    def signal_values_from_method(
        self,
        draws: Sequence[Draw],
        method: LearnedMethod,
        *,
        top_k: int | None = None,
    ) -> tuple[int, ...]:
        actual_top_k = top_k or method.top_k
        if method.method_type == "rescue":
            return self.values_from_scores(
                self.rescue_scores(draws, method.label),
                top_k=actual_top_k,
            )
        if not method.configs:
            return ()
        if method.method_type == "ensemble" or len(method.configs) > 1:
            return self.ensemble_signal_values(draws, method.configs, top_k=actual_top_k)
        signals = self.optimizer.select_candidates(draws, method.configs[0], top_k=actual_top_k)
        return tuple(signal.value for signal in signals)

    def combined_signal_values(
        self,
        draws: Sequence[Draw],
        methods: Sequence[LearnedMethod],
        *,
        top_k: int = 7,
    ) -> tuple[int, ...]:
        scores: dict[int, float] = defaultdict(float)
        for method_index, method in enumerate(methods):
            weight = max(1.0, method.fit_match_count) * (1.0 / (method_index + 1))
            signals = self.signal_values_from_method(draws, method, top_k=top_k)
            for rank, value in enumerate(signals, 1):
                scores[value] += weight * (top_k - rank + 1)
        ranked = sorted(scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
        return tuple(value for value, _score in ranked[:top_k])

    @staticmethod
    def parse_rescue_label(label: str) -> dict[str, str]:
        chunks = label.split("|")
        result: dict[str, str] = {"kind": chunks[1] if len(chunks) > 1 else ""}
        for chunk in chunks[2:]:
            if "=" not in chunk:
                continue
            key, value = chunk.split("=", 1)
            result[key] = value
        return result

    @staticmethod
    def windowed_draws(draws: Sequence[Draw], parts: dict[str, str]) -> list[Draw]:
        window_text = parts.get("window", "all")
        if window_text == "all":
            return list(draws)
        window = max(1, int(window_text))
        return list(draws[-window:])

    def frequency_counts(self, draws: Sequence[Draw], parts: dict[str, str]) -> Counter[int]:
        return self.count_values(self.windowed_draws(draws, parts))

    @staticmethod
    def count_values(draws: Sequence[Draw]) -> Counter[int]:
        counter: Counter[int] = Counter()
        for draw in draws:
            counter.update(draw.numbers)
        return counter

    @staticmethod
    def gap_counts(draws: Sequence[Draw]) -> dict[int, int]:
        gaps: dict[int, int] = {}
        for value in range(NUMBER_MIN, NUMBER_MAX + 1):
            gap = len(draws) + 1
            for distance, draw in enumerate(reversed(draws), 1):
                if value in draw.numbers:
                    gap = distance
                    break
            gaps[value] = gap
        return gaps

    @staticmethod
    def values_from_scores(scores: dict[int, float], *, top_k: int) -> tuple[int, ...]:
        ranked = sorted(scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
        return tuple(value for value, _score in ranked[:top_k])

    @staticmethod
    def config_id(config: StrategyConfig) -> str:
        offsets = ",".join(str(value) for value in config.lag_offsets)
        return (
            f"{config.name}|lag={config.lag}|support={config.min_support}|"
            f"structure={int(config.use_structure)}|repeat={int(config.use_repeat_overlap)}|"
            f"offsets={offsets}"
        )

    @staticmethod
    def short_config_label(config: StrategyConfig) -> str:
        return f"N+{config.lag}/S{config.min_support}/{config.name}"


def parse_target_numbers(raw_text: str) -> tuple[int, ...]:
    """Parse one six-number row from free text."""
    cleaned = re.sub(r"[,;|/\\-]+", " ", raw_text.strip())
    tokens = [token for token in cleaned.split() if token]
    if len(tokens) != 6:
        raise ValueError("Dãy số phải có đúng 6 số.")
    try:
        values = tuple(sorted(int(token) for token in tokens))
    except ValueError as exc:
        raise ValueError("Dãy số chỉ được chứa số nguyên.") from exc
    if any(value < 1 or value > 45 for value in values):
        raise ValueError("Mỗi số phải nằm trong khoảng 01 đến 45.")
    if len(set(values)) != 6:
        raise ValueError("6 số trong một kỳ không được trùng nhau.")
    return values


def next_auto_draw_date(draws: Sequence[Draw]) -> date:
    """Return the next date used when the user only enters a target row."""
    if not draws:
        return date.today()
    return max(draw.draw_date for draw in draws) + timedelta(days=1)


def build_target_draw(draw_date: date, values: Sequence[int]) -> Draw:
    """Build a Draw object from a learned target row."""
    sorted_values = tuple(sorted(int(value) for value in values))
    odd_count = sum(value % 2 for value in sorted_values)
    low_count = sum(value <= 22 for value in sorted_values)
    weekday_index = draw_date.weekday()
    return Draw(
        draw_date=draw_date,
        weekday_index=weekday_index,
        weekday_name=WEEKDAY_NAMES[weekday_index],
        n1=sorted_values[0],
        n2=sorted_values[1],
        n3=sorted_values[2],
        n4=sorted_values[3],
        n5=sorted_values[4],
        n6=sorted_values[5],
        total_sum=sum(sorted_values),
        odd_count=odd_count,
        even_count=6 - odd_count,
        low_count=low_count,
        high_count=6 - low_count,
        source_file="target_learning",
        source_row=None,
    )


def learned_method_signal_values(
    draws: Sequence[Draw],
    *,
    store: LearnedMethodStore | None = None,
    engine: TargetLearningEngine | None = None,
    top_k: int = 7,
) -> tuple[tuple[LearnedMethod, ...], tuple[int, ...]]:
    """Return combined signals from saved learned methods, if any exist."""
    methods = (store or LearnedMethodStore()).load()
    if not methods:
        return (), ()
    current_engine = engine or TargetLearningEngine()
    return methods, current_engine.combined_signal_values(draws, methods, top_k=top_k)
