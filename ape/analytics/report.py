"""Serializable report models for event-sequence analysis."""

from dataclasses import asdict, dataclass
import json
from typing import Any


@dataclass(slots=True, frozen=True)
class EventMetric:
    event_id: int
    count: int
    rate: float
    latest_distance: int
    prior_distance: int | None
    mean_distance: float
    largest_distance: int
    last_date: str | None
    recent_count: int
    recent_rate: float
    change_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnalysisReport:
    generated_at: str
    dataset: dict[str, Any]
    event_metrics: list[dict[str, Any]]
    count_leaders: list[dict[str, Any]]
    count_laggards: list[dict[str, Any]]
    longest_distances: list[dict[str, Any]]
    common_pairs: list[dict[str, Any]]
    common_triples: list[dict[str, Any]]
    structure: dict[str, Any]
    weekday_summary: dict[str, Any]
    time_summary: dict[str, Any]
    audit: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
