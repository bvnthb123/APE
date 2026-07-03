"""Serializable reports for randomness diagnostics."""

from dataclasses import asdict, dataclass
import json
from typing import Any


@dataclass(slots=True)
class RandomnessReport:
    total_draws: int
    total_slots: int
    expected_frequency: float
    chi_square_statistic: float
    chi_square_p_value: float
    normalized_entropy: float
    maximum_absolute_z_score: float
    average_consecutive_overlap: float
    overlap_distribution: dict[str, int]
    simulations: int
    seed: int
    frequency_extremeness_p_value: float
    overlap_extremeness_p_value: float
    simulation_summary: dict[str, float]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
