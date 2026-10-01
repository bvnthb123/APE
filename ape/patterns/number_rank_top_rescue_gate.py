"""Top-hit rescue wrapper for the number ranking rescue lab.

This module keeps the missing-number rescue behavior from number_rank_rescue_gate
and adds three extra repair paths:

* Top rescue: when all target numbers have independent ways but the public Top-N
  ranking misses the target row, learn extra methods for the failed row.
* Edge rescue: when boundary values such as 01/02/44/45 disappear from the
  survivor chain, inject explicit low/high edge methods and let the walkback
  gate decide whether they survive.
* Band rescue: when a mid-range value such as 35 disappears from the survivor
  chain, inject local-range and zone-range methods around that missing value.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Sequence

from ape.database.models import Draw
from ape.patterns.target_learning import LearnedMethod
from ape.patterns.number_rank_rescue_gate import (
    NumberRankingRescueTrainer,
    RANKING_MODES,
    RescueAttemptConfig,
    RescueModeResult,
)


class NumberRankingTopRescueTrainer(NumberRankingRescueTrainer):
    """Ranking rescue trainer with Top-hit, boundary-number and band rescue paths."""

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

        best_eval = None
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
            if repair_used >= repair_rounds:
                break

            rescue_values = self.rescue_values_for_failure(evaluation)
            if not rescue_values:
                break

            rescue_methods = self.learn_rescue_methods(
                evaluation.fail_history,
                evaluation.fail_target_values,
                rescue_values,
                attempt=attempt,
                way_top=way_top,
            )
            before = len(method_pool)
            method_pool = self.dedupe_methods([*method_pool, *rescue_methods])
            for method in rescue_methods:
                if method.method_type == "edge_rescue":
                    boost = 25.0
                elif method.method_type == "band_rescue":
                    boost = 22.0
                else:
                    boost = 10.0
                method_scores.setdefault(self.method_key(method), float(max(1, method.fit_match_count)) + boost)
            if len(method_pool) <= before:
                break

        assert best_eval is not None
        return best_eval.result, best_eval.survivors, best_eval.method_scores

    def learn_rescue_methods(
        self,
        history: Sequence[Draw],
        target_values: tuple[int, ...],
        missing_values: tuple[int, ...],
        *,
        attempt: RescueAttemptConfig,
        way_top: int,
    ) -> list[LearnedMethod]:
        """Learn normal rescue methods, then add boundary and band-specific methods."""
        methods = list(
            super().learn_rescue_methods(
                history,
                target_values,
                missing_values,
                attempt=attempt,
                way_top=way_top,
            )
        )
        edge_methods = self.edge_rescue_methods(
            history,
            target_values,
            missing_values,
            top_k=way_top,
        )
        band_methods = self.band_rescue_methods(
            history,
            target_values,
            missing_values,
            top_k=way_top,
        )
        return self.dedupe_methods([*methods, *edge_methods, *band_methods])

    def edge_rescue_methods(
        self,
        draws: Sequence[Draw],
        target_values: tuple[int, ...],
        rescue_values: tuple[int, ...],
        *,
        top_k: int,
    ) -> list[LearnedMethod]:
        methods: list[LearnedMethod] = []
        rescue_set = set(rescue_values)
        now = datetime.now().isoformat(timespec="seconds")
        labels: list[str] = []
        if rescue_set & {1, 2, 3, 4, 5}:
            labels.extend([
                "EdgeRescue|low|width=3",
                "EdgeRescue|low|width=5",
                "EdgeRescue|low|width=7",
            ])
        if rescue_set & {41, 42, 43, 44, 45}:
            labels.extend([
                "EdgeRescue|high|width=3",
                "EdgeRescue|high|width=5",
                "EdgeRescue|high|width=7",
            ])
        for label in labels:
            signal_values = self.edge_rescue_values(draws, label, top_k=top_k)
            matched = tuple(sorted(set(signal_values) & set(target_values)))
            if not (set(signal_values) & rescue_set):
                continue
            methods.append(
                LearnedMethod(
                    method_type="edge_rescue",
                    label=label,
                    configs=tuple(),
                    top_k=top_k,
                    fit_signal_values=signal_values,
                    fit_target_values=target_values,
                    fit_matched_values=matched,
                    fit_score=len(matched) * 2500 + len(set(signal_values) & rescue_set) * 3000,
                    saved_at=now,
                )
            )
        return methods

    def band_rescue_methods(
        self,
        draws: Sequence[Draw],
        target_values: tuple[int, ...],
        rescue_values: tuple[int, ...],
        *,
        top_k: int,
    ) -> list[LearnedMethod]:
        """Create local and zone-band methods for non-edge missing values."""
        methods: list[LearnedMethod] = []
        rescue_set = set(rescue_values)
        now = datetime.now().isoformat(timespec="seconds")
        labels: list[str] = []
        for value in sorted(rescue_set):
            if 1 <= value <= 45:
                labels.extend(
                    [
                        f"BandRescue|around|center={value}|radius=3",
                        f"BandRescue|around|center={value}|radius=5",
                        f"BandRescue|around|center={value}|radius=8",
                    ]
                )
                if value <= 15:
                    labels.append("BandRescue|zone|start=1|end=15")
                elif value <= 30:
                    labels.append("BandRescue|zone|start=16|end=30")
                else:
                    labels.append("BandRescue|zone|start=31|end=45")
        for label in dict.fromkeys(labels):
            signal_values = self.band_rescue_values(draws, label, top_k=top_k)
            matched = tuple(sorted(set(signal_values) & set(target_values)))
            if not (set(signal_values) & rescue_set):
                continue
            methods.append(
                LearnedMethod(
                    method_type="band_rescue",
                    label=label,
                    configs=tuple(),
                    top_k=top_k,
                    fit_signal_values=signal_values,
                    fit_target_values=target_values,
                    fit_matched_values=matched,
                    fit_score=len(matched) * 2400 + len(set(signal_values) & rescue_set) * 2800,
                    saved_at=now,
                )
            )
        return methods

    def signal_values_from_method(
        self,
        draws: Sequence[Draw],
        method: LearnedMethod,
        *,
        top_k: int,
    ) -> tuple[int, ...]:
        if method.method_type == "edge_rescue":
            return self.edge_rescue_values(draws, method.label, top_k=top_k)
        if method.method_type == "band_rescue":
            return self.band_rescue_values(draws, method.label, top_k=top_k)
        return self.engine.signal_values_from_method(draws, method, top_k=top_k)

    def edge_rescue_values(self, draws: Sequence[Draw], label: str, *, top_k: int) -> tuple[int, ...]:
        parts = self.parse_pipe_label(label)
        side = parts.get("side", parts.get("kind", "low"))
        width = int(parts.get("width", "5"))
        if side == "high":
            primary = list(range(45, max(0, 45 - width), -1))
        else:
            primary = list(range(1, min(45, width) + 1))

        freq = self.recent_frequency(draws, window=80)
        fill = sorted(
            (value for value in range(1, 46) if value not in set(primary)),
            key=lambda value: (freq[value], value),
            reverse=True,
        )
        result = [*primary, *fill]
        return tuple(result[:top_k])

    def band_rescue_values(self, draws: Sequence[Draw], label: str, *, top_k: int) -> tuple[int, ...]:
        parts = self.parse_pipe_label(label)
        kind = parts.get("kind", "around")
        if kind == "zone":
            start = int(parts.get("start", "1"))
            end = int(parts.get("end", "45"))
            band = list(range(max(1, start), min(45, end) + 1))
            center = (start + end) / 2
        else:
            center_value = int(parts.get("center", "23"))
            radius = int(parts.get("radius", "5"))
            start = max(1, center_value - radius)
            end = min(45, center_value + radius)
            band = list(range(start, end + 1))
            center = float(center_value)

        freq = self.recent_frequency(draws, window=120)
        gaps = self.gap_counts(draws)
        scored: list[tuple[float, int]] = []
        for value in band:
            distance_score = max(0.0, 10.0 - abs(value - center))
            score = distance_score * 3.0 + freq[value] * 1.4 + gaps.get(value, 0) * 0.08
            scored.append((score, value))
        primary = [value for _score, value in sorted(scored, key=lambda item: (item[0], item[1]), reverse=True)]
        fill = sorted(
            (value for value in range(1, 46) if value not in set(primary)),
            key=lambda value: (freq[value], gaps.get(value, 0), value),
            reverse=True,
        )
        return tuple([*primary, *fill][:top_k])

    @staticmethod
    def parse_pipe_label(label: str) -> dict[str, str]:
        chunks = label.split("|")
        result: dict[str, str] = {"kind": chunks[1] if len(chunks) > 1 else ""}
        # Preserve the old EdgeRescue side format: EdgeRescue|low|width=5.
        if label.startswith("EdgeRescue|") and len(chunks) > 1:
            result["side"] = chunks[1]
        for chunk in chunks[2:]:
            if "=" not in chunk:
                continue
            key, value = chunk.split("=", 1)
            result[key] = value
        return result

    @staticmethod
    def recent_frequency(draws: Sequence[Draw], *, window: int) -> Counter[int]:
        freq: Counter[int] = Counter()
        for draw in list(draws)[-window:]:
            for value in draw.numbers:
                freq[int(value)] += 1
        return freq

    @staticmethod
    def gap_counts(draws: Sequence[Draw]) -> dict[int, int]:
        gaps = {value: len(draws) for value in range(1, 46)}
        for offset, draw in enumerate(reversed(draws), 1):
            for value in draw.numbers:
                gaps[int(value)] = min(gaps[int(value)], offset)
        return gaps

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
            values = self.signal_values_from_method(draws, method, top_k=way_top)
            if value in set(values):
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
            values = self.signal_values_from_method(draws, method, top_k=way_top)
            base_score = method_scores.get(self.method_key(method), float(max(1, method.fit_match_count)))
            if method.method_type in {"edge_rescue", "band_rescue"}:
                base_score *= 1.35
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
            values = self.signal_values_from_method(draws, method, top_k=way_top)
            hits = target_set & set(values)
            if not hits:
                method_scores[key] = method_scores.get(key, 1.0) * 0.95
                continue
            best_rank = min(values.index(value) + 1 for value in hits)
            rank_bonus = (way_top - best_rank + 1) / way_top
            rescue_bonus = 1.5 if method.method_type in {"edge_rescue", "band_rescue"} else 0.0
            method_scores[key] = method_scores.get(key, 1.0) + recency_bonus + rank_bonus + len(hits) * 0.25 + rescue_bonus

    @staticmethod
    def rescue_values_for_failure(evaluation) -> tuple[int, ...]:
        """Return values to repair for either missing-way or Top-hit failure."""
        if evaluation.fail_missing_values:
            return evaluation.fail_missing_values
        if not evaluation.result.steps:
            return tuple()
        failed_step = evaluation.result.steps[-1]
        matched = set(failed_step.matched_values)
        # Top rescue: all values had ways, but some/all correct values were outside Top-N.
        return tuple(value for value in failed_step.target_values if value not in matched)
