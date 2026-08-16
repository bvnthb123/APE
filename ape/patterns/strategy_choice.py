"""Strategy choice lab and persistent saved calculation method.

This module lets APE generate multiple historical calculation methods, present
them for user review, and persist the selected method for later signal runs.
The output is historical signal research and does not guarantee future results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any, Sequence

from ape.core.settings import SETTINGS
from ape.database.models import Draw
from ape.patterns.audit import format_values
from ape.patterns.optimizer import StrategyConfig, StrategyOptimizer
from ape.patterns.recheck import StrategyRechecker


@dataclass(slots=True, frozen=True)
class SavedStrategy:
    """A user-approved calculation method saved for future signal runs."""

    label: str
    config: StrategyConfig
    top_k: int
    target_hits: int
    start_date: date
    saved_at: str

    @property
    def signal_label(self) -> str:
        return self.config.detail_label


@dataclass(slots=True, frozen=True)
class StrategyChoice:
    """One candidate calculation method shown to the user."""

    option_id: str
    config: StrategyConfig
    top_k: int
    target_hits: int
    tested_rows: int
    target_hit_rate: float
    one_plus_hit_rate: float
    zero_hit_rate: float
    average_hits: float
    max_hits: int
    signal_values: tuple[int, ...]
    distribution_label: str

    @property
    def signal_label(self) -> str:
        return format_values(self.signal_values)

    def to_row(self, rank: int) -> tuple[str, ...]:
        return (
            str(rank),
            self.config.detail_label,
            self.signal_label,
            f"{self.one_plus_hit_rate * 100:.2f}%",
            f"{self.average_hits:.3f}",
            f"{self.zero_hit_rate * 100:.2f}%",
            str(self.max_hits),
            str(self.tested_rows),
            self.distribution_label,
        )

    def to_saved_strategy(self) -> SavedStrategy:
        return SavedStrategy(
            label=self.config.detail_label,
            config=self.config,
            top_k=self.top_k,
            target_hits=self.target_hits,
            start_date=date(2026, 3, 1),
            saved_at=datetime.now().isoformat(timespec="seconds"),
        )


class SavedStrategyStore:
    """Persist and load the user-selected calculation method."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or SETTINGS.data_dir / "saved_strategy.json"

    def save(self, strategy: SavedStrategy) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "label": strategy.label,
            "top_k": strategy.top_k,
            "target_hits": strategy.target_hits,
            "start_date": strategy.start_date.isoformat(),
            "saved_at": strategy.saved_at,
            "config": self.config_to_dict(strategy.config),
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.path

    def load(self) -> SavedStrategy | None:
        if not self.path.exists():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return SavedStrategy(
            label=str(payload["label"]),
            config=self.config_from_dict(dict(payload["config"])),
            top_k=int(payload.get("top_k", 7)),
            target_hits=int(payload.get("target_hits", 1)),
            start_date=date.fromisoformat(str(payload.get("start_date", "2026-03-01"))),
            saved_at=str(payload.get("saved_at", "")),
        )

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


class StrategyChoiceEngine:
    """Generate candidate methods and calculate latest signals for each one."""

    def __init__(self, optimizer: StrategyOptimizer | None = None) -> None:
        self.optimizer = optimizer or StrategyOptimizer()
        self.rechecker = StrategyRechecker(self.optimizer)

    def generate_choices(
        self,
        draws: Sequence[Draw],
        *,
        start_date: date = date(2026, 3, 1),
        end_date: date | None = None,
        lag_from: int = 1,
        lag_to: int = 3,
        top_k: int = 7,
        base_min_support: int = 2,
        min_training_rows: int = 30,
        target_hits: int = 1,
        strategy_mode: str = "quick",
        limit: int = 12,
    ) -> list[StrategyChoice]:
        if not draws:
            return []
        actual_end_date = end_date or date.today()
        result = self.rechecker.recheck(
            draws,
            start_date=start_date,
            end_date=actual_end_date,
            lag_from=lag_from,
            lag_to=lag_to,
            top_k=top_k,
            base_min_support=base_min_support,
            min_training_rows=min_training_rows,
            target_hits=target_hits,
            strategy_mode=strategy_mode,
        )

        choices: list[StrategyChoice] = []
        for evaluation in result.evaluations[:limit]:
            signals = self.latest_signal_values(draws, evaluation.config, top_k=top_k)
            choices.append(
                StrategyChoice(
                    option_id=self.option_id(evaluation.config),
                    config=evaluation.config,
                    top_k=top_k,
                    target_hits=target_hits,
                    tested_rows=evaluation.tested_rows,
                    target_hit_rate=evaluation.target_hit_rate,
                    one_plus_hit_rate=evaluation.one_plus_hit_rate,
                    zero_hit_rate=evaluation.zero_hit_rate,
                    average_hits=evaluation.average_hits,
                    max_hits=evaluation.max_hits,
                    signal_values=signals,
                    distribution_label=evaluation.distribution_label,
                )
            )
        return choices

    def latest_signal_values(
        self,
        draws: Sequence[Draw],
        config: StrategyConfig,
        *,
        top_k: int,
    ) -> tuple[int, ...]:
        signals = self.optimizer.select_candidates(draws, config, top_k=top_k)
        return tuple(signal.value for signal in signals)

    @staticmethod
    def option_id(config: StrategyConfig) -> str:
        offsets = ",".join(str(value) for value in config.lag_offsets)
        return (
            f"{config.name}|lag={config.lag}|support={config.min_support}|"
            f"structure={int(config.use_structure)}|repeat={int(config.use_repeat_overlap)}|"
            f"offsets={offsets}"
        )


def saved_strategy_signal_values(
    draws: Sequence[Draw],
    *,
    store: SavedStrategyStore | None = None,
    optimizer: StrategyOptimizer | None = None,
) -> tuple[SavedStrategy | None, tuple[int, ...]]:
    """Return signals calculated from the saved method, if one exists."""
    strategy = (store or SavedStrategyStore()).load()
    if strategy is None:
        return None, ()
    current_optimizer = optimizer or StrategyOptimizer()
    signals = current_optimizer.select_candidates(draws, strategy.config, top_k=strategy.top_k)
    return strategy, tuple(signal.value for signal in signals)
