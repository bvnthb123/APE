"""Independent six-channel ranking for the number-ranking rescue lab.

The old rescue flow measured per-value coverage but merged all surviving methods
into one pool. This trainer keeps six independent method channels through the
walkback chain. It is still a historical/target-fitting validation mechanism,
not an out-of-sample accuracy guarantee.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import permutations
from pathlib import Path
from typing import Sequence

from ape.database.models import Draw
from ape.patterns.audit import format_values
from ape.patterns.target_learning import LearnedMethod
from ape.patterns.number_rank_rescue_gate import (
    RescueAttemptConfig,
    RescueEvaluation,
    RescueModeResult,
    RescueStepResult,
)
from ape.patterns.number_rank_top_rescue_gate import NumberRankingTopRescueTrainer


class IndependentChannelRankingTrainer(NumberRankingTopRescueTrainer):
    """Carry six independent method channels from period to period."""

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
        first_target = self.draw_values(holdouts[0])
        channels = self.build_initial_channels(
            base_history, method_pool, first_target, way_top=way_top
        )
        channel_scores = [
            {
                self.method_key(method): method_scores.get(
                    self.method_key(method),
                    float(max(1, method.fit_match_count)),
                )
                for method in channel
            }
            for channel in channels
        ]

        steps: list[RescueStepResult] = []
        history = list(base_history)

        for index, target_draw in enumerate(holdouts, 1):
            target = self.draw_values(target_draw)
            method_count_before = len(
                self.dedupe_methods(
                    method for channel in channels for method in channel
                )
            )

            rankings = [
                self.rank_channel(
                    history,
                    channel,
                    channel_scores[channel_index],
                    ranking_mode=ranking_mode,
                    way_top=way_top,
                )
                for channel_index, channel in enumerate(channels)
            ]

            assigned_targets = self.assign_channels_to_targets(
                rankings, target, min_ways=min_ways
            )
            signal_values = self.round_robin_signal(rankings, top_k=top_k)
            matched = tuple(sorted(set(signal_values) & set(target)))

            next_channels: list[list[LearnedMethod]] = []
            per_value_counts: dict[int, int] = {}
            covered: list[int] = []

            for channel_index, target_value in enumerate(assigned_targets):
                channel = channels[channel_index]
                survivors = self.dedupe_methods(
                    method
                    for method in channel
                    if target_value
                    in set(
                        self.signal_values_from_method(
                            history, method, top_k=way_top
                        )
                    )
                )
                next_channels.append(survivors)
                count = len(survivors)
                per_value_counts[target_value] = count
                if count >= min_ways:
                    covered.append(target_value)

                self.update_channel_scores(
                    history,
                    channel,
                    channel_scores[channel_index],
                    target_value=target_value,
                    way_top=way_top,
                    step_index=index,
                )

            missing = tuple(
                value for value in target if value not in set(covered)
            )
            next_methods = self.dedupe_methods(
                method for channel in next_channels for method in channel
            )
            passed = (
                len(covered) == len(target)
                and len(next_methods) > 0
                and (
                    min_top_hits <= 0
                    or len(matched) >= min_top_hits
                )
            )

            # Feed the strongest local score back to the rescue restart.
            for channel_index, channel in enumerate(channels):
                for method in channel:
                    key = self.method_key(method)
                    local = channel_scores[channel_index].get(key, 1.0)
                    method_scores[key] = max(
                        method_scores.get(key, 0.0), local
                    )

            steps.append(
                RescueStepResult(
                    index=index,
                    draw_date=target_draw.draw_date,
                    target_values=target,
                    signal_values=signal_values,
                    matched_values=matched,
                    covered_values=tuple(sorted(covered)),
                    missing_values=missing,
                    passed=passed,
                    method_count_before=method_count_before,
                    method_count_after=len(next_methods),
                    per_value_way_counts=per_value_counts,
                    min_ways=min_ways,
                    min_top_hits=min_top_hits,
                )
            )

            if not passed:
                if missing:
                    reason = (
                        f"Ranking {ranking_mode} dừng ở kỳ {index:02d} "
                        f"({target_draw.draw_date.strftime('%d/%m/%Y')}). "
                        f"Thiếu cách độc lập: {format_values(missing)}. "
                        f"Đủ cách {len(covered)}/6, trùng Top "
                        f"{len(matched)}/6. Đã rescue "
                        f"{repair_used}/{repair_rounds} vòng."
                    )
                else:
                    reason = (
                        f"Ranking {ranking_mode} dừng ở kỳ {index:02d} "
                        f"({target_draw.draw_date.strftime('%d/%m/%Y')}). "
                        f"Đủ cách độc lập 6/6 nhưng Top {top_k} chỉ trùng "
                        f"{len(matched)}/6, thấp hơn ngưỡng {min_top_hits}. "
                        f"Đã rescue {repair_used}/{repair_rounds} vòng."
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

            channels = next_channels
            history.append(target_draw)

        final_rankings = [
            self.rank_channel(
                draws,
                channel,
                channel_scores[channel_index],
                ranking_mode=ranking_mode,
                way_top=way_top,
            )
            for channel_index, channel in enumerate(channels)
        ]
        final_signal = self.round_robin_signal(
            final_rankings, top_k=top_k
        )
        survivors = self.dedupe_methods(
            method for channel in channels for method in channel
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
            survivor_count=len(survivors),
            saved_path=save_path,
            fail_reason="",
        )
        return RescueEvaluation(
            result=result,
            survivors=survivors,
            method_scores=method_scores,
            fail_history=tuple(history),
            fail_target_values=tuple(),
            fail_missing_values=tuple(),
        )

    def build_initial_channels(
        self,
        history: Sequence[Draw],
        methods: Sequence[LearnedMethod],
        first_target: tuple[int, ...],
        *,
        way_top: int,
    ) -> list[list[LearnedMethod]]:
        return [
            self.methods_that_pull_value(
                methods, history, value, way_top=way_top
            )
            for value in first_target
        ]

    def rank_channel(
        self,
        draws: Sequence[Draw],
        methods: Sequence[LearnedMethod],
        scores: dict[tuple[object, ...], float],
        *,
        ranking_mode: str,
        way_top: int,
    ) -> list[tuple[int, float, int]]:
        value_scores: defaultdict[int, float] = defaultdict(float)
        value_counts: defaultdict[int, int] = defaultdict(int)

        for method_index, method in enumerate(methods):
            values = self.signal_values_from_method(
                draws, method, top_k=way_top
            )
            base = scores.get(
                self.method_key(method),
                float(max(1, method.fit_match_count)),
            )
            for rank, value in enumerate(values, 1):
                value_counts[value] += 1
                rank_weight = way_top - rank + 1
                if ranking_mode == "vote":
                    contribution = 1.0
                elif ranking_mode == "ranked_vote":
                    contribution = float(rank_weight)
                elif ranking_mode == "recent_score":
                    contribution = (base + method_index + 1) / rank
                elif ranking_mode == "coverage_balanced":
                    contribution = rank_weight / max(
                        1.0, value_counts[value] ** 0.35
                    )
                else:
                    contribution = base * rank_weight / max(1, way_top)
                value_scores[value] += contribution

        ranked = sorted(
            value_scores,
            key=lambda value: (
                value_scores[value],
                value_counts[value],
                value,
            ),
            reverse=True,
        )
        return [
            (value, value_scores[value], value_counts[value])
            for value in ranked
        ]

    def assign_channels_to_targets(
        self,
        channel_rankings: Sequence[
            Sequence[tuple[int, float, int]]
        ],
        target: tuple[int, ...],
        *,
        min_ways: int,
    ) -> tuple[int, ...]:
        if len(channel_rankings) != len(target):
            raise ValueError(
                "Independent channel count must equal target count."
            )

        score_maps = [
            {
                value: (score, count)
                for value, score, count in ranking
            }
            for ranking in channel_rankings
        ]

        best_assignment: tuple[int, ...] | None = None
        best_key: tuple[int, float] | None = None

        for permutation in permutations(target):
            covered = 0
            total_score = 0.0
            for channel_index, value in enumerate(permutation):
                score, count = score_maps[channel_index].get(
                    value, (0.0, 0)
                )
                if count >= min_ways:
                    covered += 1
                total_score += score

            key = (covered, total_score)
            if best_key is None or key > best_key:
                best_key = key
                best_assignment = tuple(permutation)

        assert best_assignment is not None
        return best_assignment

    def round_robin_signal(
        self,
        channel_rankings: Sequence[
            Sequence[tuple[int, float, int]]
        ],
        *,
        top_k: int,
    ) -> tuple[int, ...]:
        selected: list[int] = []
        seen: set[int] = set()
        depth = 0
        max_depth = max(
            (len(ranking) for ranking in channel_rankings),
            default=0,
        )

        while len(selected) < top_k and depth < max_depth:
            candidates: list[tuple[float, int, int]] = []
            for channel_index, ranking in enumerate(channel_rankings):
                if depth >= len(ranking):
                    continue
                value, score, _count = ranking[depth]
                candidates.append((score, channel_index, value))

            candidates.sort(
                key=lambda item: (item[0], -item[1], item[2]),
                reverse=True,
            )
            for _score, _channel_index, value in candidates:
                if value in seen:
                    continue
                selected.append(value)
                seen.add(value)
                if len(selected) >= top_k:
                    break
            depth += 1

        return tuple(selected)

    def update_channel_scores(
        self,
        draws: Sequence[Draw],
        methods: Sequence[LearnedMethod],
        scores: dict[tuple[object, ...], float],
        *,
        target_value: int,
        way_top: int,
        step_index: int,
    ) -> None:
        recency_bonus = 1.0 + step_index / 10.0
        for method in methods:
            key = self.method_key(method)
            values = self.signal_values_from_method(
                draws, method, top_k=way_top
            )
            if target_value not in values:
                scores[key] = scores.get(key, 1.0) * 0.95
                continue
            rank = values.index(target_value) + 1
            rank_bonus = (way_top - rank + 1) / way_top
            scores[key] = (
                scores.get(key, 1.0)
                + recency_bonus
                + rank_bonus
            )
