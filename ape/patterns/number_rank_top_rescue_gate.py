"""Top-hit rescue wrapper for the number ranking rescue lab.

This module keeps the missing-number rescue behavior from number_rank_rescue_gate
and adds one extra repair path: when all target numbers have independent ways
but the public Top-N ranking misses the target row, learn extra methods for the
failed row and prioritize target values that were outside Top-N.
"""

from __future__ import annotations

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
    """Ranking rescue trainer with an additional Top-hit rescue path."""

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
                # Stronger boost than missing-number rescue because the failure is ranking-related:
                # these methods already have independent support, but were not represented in Top-N.
                method_scores.setdefault(self.method_key(method), float(max(1, method.fit_match_count)) + 10.0)
            if len(method_pool) <= before:
                break

        assert best_eval is not None
        return best_eval.result, best_eval.survivors, best_eval.method_scores

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
