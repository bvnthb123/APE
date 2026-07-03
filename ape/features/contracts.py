"""Contracts shared by Feature Factory v1."""

from dataclasses import asdict, dataclass
from typing import Any

DEFAULT_FEATURE_VERSION = "1.0"
DEFAULT_WINDOWS = (5, 10, 20, 50)


@dataclass(slots=True, frozen=True)
class FeatureValue:
    draw_id: int
    target_number: int
    feature_group: str
    feature_name: str
    feature_value: float
    feature_version: str

    def to_row(self) -> dict[str, object]:
        return {
            "draw_id": self.draw_id,
            "target_number": self.target_number,
            "feature_group": self.feature_group,
            "feature_name": self.feature_name,
            "feature_value": self.feature_value,
            "feature_version": self.feature_version,
        }


@dataclass(slots=True)
class FeatureBuildResult:
    version: str
    total_draws: int
    processed_draws: int
    skipped_draws: int
    feature_rows: int
    deleted_rows: int
    min_history: int
    windows: list[int]
    first_target_date: str | None
    last_target_date: str | None
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
