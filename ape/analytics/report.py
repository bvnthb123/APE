"""Report models for event analysis."""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class EventMetric:
    event_id: int
    count: int
    rate: float
