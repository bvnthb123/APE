"""Descriptive event-sequence analysis."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from statistics import mean, median, pstdev
from typing import Any, Sequence

from ape.analytics.audit import audit_draws
from ape.analytics.report import AnalysisReport, EventMetric
from ape.core.exceptions import APEError
from ape.core.settings import SETTINGS
from ape.database.models import Draw


class AnalysisError(APEError):
    """Raised when a descriptive report cannot be generated."""


class EventSequenceAnalyzer:
    """Generate reproducible descriptive metrics from historical rows."""

    def __init__(
        self,
        min_value: int = SETTINGS.min_number,
        max_value: int = SETTINGS.max_number,
        values_per_row: int = SETTINGS.numbers_per_draw,
        recent_window: int = 30,
    ) -> None:
        if min_value >= max_value:
            raise ValueError("min_value must be smaller than max_value")
        if values_per_row <= 0:
            raise ValueError("values_per_row must be positive")
        if recent_window <= 0:
            raise ValueError("recent_window must be positive")

        self.min_value = min_value
        self.max_value = max_value
        self.values_per_row = values_per_row
        self.recent_window = recent_window

    def analyze(self, draws: Sequence[Draw], limit: int = 10) -> AnalysisReport:
        if limit <= 0:
            raise AnalysisError("limit phải lớn hơn 0.")
        if not draws:
            raise AnalysisError(
                "Database chưa có dữ liệu. Hãy import file Excel trước."
            )

        rows = sorted(draws, key=lambda draw: draw.draw_date)
        row_count = len(rows)
        recent_size = min(self.recent_window, row_count)

        counts: Counter[int] = Counter()
        recent_counts: Counter[int] = Counter()
        positions: dict[int, list[int]] = defaultdict(list)
        pair_counts: Counter[tuple[int, int]] = Counter()
        triple_counts: Counter[tuple[int, int, int]] = Counter()
        odd_even: Counter[str] = Counter()
        low_high: Counter[str] = Counter()
        repeats: Counter[str] = Counter()
        consecutive: Counter[str] = Counter()
        total_buckets: Counter[str] = Counter()
        value_ranges: Counter[str] = Counter()
        weekday_counts: Counter[str] = Counter()
        year_counts: Counter[str] = Counter()
        month_counts: Counter[str] = Counter()
        totals: list[int] = []

        previous_values: set[int] | None = None
        for row_index, draw in enumerate(rows):
            values = tuple(sorted(draw.numbers))
            total = sum(values)
            totals.append(total)
            weekday_counts[draw.weekday_name] += 1
            year_counts[str(draw.draw_date.year)] += 1
            month_counts[draw.draw_date.strftime("%Y-%m")] += 1

            odd_count = sum(value % 2 for value in values)
            low_count = sum(value <= 22 for value in values)
            odd_even[f"{odd_count}-{self.values_per_row - odd_count}"] += 1
            low_high[f"{low_count}-{self.values_per_row - low_count}"] += 1

            adjacent_count = sum(
                right - left == 1
                for left, right in zip(values, values[1:])
            )
            consecutive[str(adjacent_count)] += 1

            if previous_values is not None:
                shared = len(set(values) & previous_values)
                repeats[str(shared)] += 1
            previous_values = set(values)

            bucket_start = (total // 20) * 20
            total_buckets[f"{bucket_start}-{bucket_start + 19}"] += 1

            for value in values:
                counts[value] += 1
                positions[value].append(row_index)
                value_ranges[self._range_label(value)] += 1

            pair_counts.update(combinations(values, 2))
            triple_counts.update(combinations(values, 3))

        for draw in rows[-recent_size:]:
            recent_counts.update(draw.numbers)

        metrics = [
            self._event_metric(
                value,
                rows,
                counts,
                recent_counts,
                positions,
                recent_size,
            )
            for value in range(self.min_value, self.max_value + 1)
        ]

        count_leaders = sorted(
            metrics,
            key=lambda item: (-item.count, item.latest_distance, item.event_id),
        )[:limit]
        count_laggards = sorted(
            metrics,
            key=lambda item: (item.count, -item.latest_distance, item.event_id),
        )[:limit]
        longest_distances = sorted(
            metrics,
            key=lambda item: (-item.latest_distance, item.count, item.event_id),
        )[:limit]

        date_gaps = [
            (right.draw_date - left.draw_date).days
            for left, right in zip(rows, rows[1:])
        ]

        dataset = {
            "total_rows": row_count,
            "total_value_slots": row_count * self.values_per_row,
            "first_date": rows[0].draw_date.isoformat(),
            "last_date": rows[-1].draw_date.isoformat(),
            "span_days": (rows[-1].draw_date - rows[0].draw_date).days,
            "recent_window": recent_size,
            "minimum_date_gap_days": min(date_gaps) if date_gaps else 0,
            "maximum_date_gap_days": max(date_gaps) if date_gaps else 0,
            "average_date_gap_days": round(mean(date_gaps), 4) if date_gaps else 0.0,
        }

        structure = {
            "total": {
                "minimum": min(totals),
                "maximum": max(totals),
                "average": round(mean(totals), 4),
                "median": round(float(median(totals)), 4),
                "standard_deviation": round(pstdev(totals), 4),
                "buckets": self._sorted_counter(total_buckets),
            },
            "odd_even_patterns": self._sorted_counter(odd_even),
            "low_high_patterns": self._sorted_counter(low_high),
            "shared_with_previous_row": self._sorted_counter(repeats),
            "adjacent_pair_count": self._sorted_counter(consecutive),
            "value_ranges": self._sorted_counter(value_ranges),
        }

        weekday_summary = {
            "row_counts": self._sorted_counter(weekday_counts),
            "value_counts": self._weekday_value_counts(rows),
        }
        time_summary = {
            "year_counts": self._sorted_counter(year_counts),
            "month_counts": dict(sorted(month_counts.items())),
        }

        return AnalysisReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            dataset=dataset,
            event_metrics=[item.to_dict() for item in metrics],
            count_leaders=[item.to_dict() for item in count_leaders],
            count_laggards=[item.to_dict() for item in count_laggards],
            longest_distances=[item.to_dict() for item in longest_distances],
            common_pairs=self._group_rows(pair_counts, row_count, limit),
            common_triples=self._group_rows(triple_counts, row_count, limit),
            structure=structure,
            weekday_summary=weekday_summary,
            time_summary=time_summary,
            audit=audit_draws(
                rows,
                self.min_value,
                self.max_value,
                self.values_per_row,
            ),
        )

    def _event_metric(
        self,
        value: int,
        rows: Sequence[Draw],
        counts: Counter[int],
        recent_counts: Counter[int],
        positions: dict[int, list[int]],
        recent_size: int,
    ) -> EventMetric:
        indexes = positions.get(value, [])
        row_count = len(rows)
        latest_distance = row_count - 1 - indexes[-1] if indexes else row_count
        internal_distances = [
            right - left - 1
            for left, right in zip(indexes, indexes[1:])
        ]
        edge_distances = [indexes[0], latest_distance] if indexes else [row_count]
        prior_distance = internal_distances[-1] if internal_distances else None
        mean_distance = (
            mean(internal_distances)
            if internal_distances
            else float(latest_distance)
        )
        rate = counts[value] / row_count
        recent_rate = recent_counts[value] / recent_size

        return EventMetric(
            event_id=value,
            count=counts[value],
            rate=round(rate, 6),
            latest_distance=latest_distance,
            prior_distance=prior_distance,
            mean_distance=round(mean_distance, 4),
            largest_distance=max(internal_distances + edge_distances),
            last_date=(rows[indexes[-1]].draw_date.isoformat() if indexes else None),
            recent_count=recent_counts[value],
            recent_rate=round(recent_rate, 6),
            change_rate=round(recent_rate - rate, 6),
        )

    def _weekday_value_counts(self, rows: Sequence[Draw]) -> dict[str, Any]:
        counters: dict[str, Counter[int]] = defaultdict(Counter)
        for draw in rows:
            counters[draw.weekday_name].update(draw.numbers)
        return {
            weekday: {
                f"{value:02d}": count
                for value, count in sorted(counter.items())
            }
            for weekday, counter in sorted(counters.items())
        }

    @staticmethod
    def _group_rows(
        counter: Counter[tuple[int, ...]],
        row_count: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        return [
            {
                "values": "-".join(f"{value:02d}" for value in values),
                "count": count,
                "rate": round(count / row_count, 6),
            }
            for values, count in sorted(
                counter.items(),
                key=lambda item: (-item[1], item[0]),
            )[:limit]
        ]

    @staticmethod
    def _sorted_counter(counter: Counter[str]) -> dict[str, int]:
        return dict(sorted(counter.items(), key=lambda item: item[0]))

    @staticmethod
    def _range_label(value: int) -> str:
        if value <= 9:
            return "01-09"
        if value <= 19:
            return "10-19"
        if value <= 29:
            return "20-29"
        if value <= 39:
            return "30-39"
        return "40-45"
