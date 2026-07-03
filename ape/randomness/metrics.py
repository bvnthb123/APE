"""Mathematical helpers for randomness diagnostics."""

from collections import Counter
from math import log
from typing import Sequence

import numpy as np

from ape.database.models import Draw


def frequency_counts(
    draws: Sequence[Draw],
    min_number: int,
    max_number: int,
) -> np.ndarray:
    counter = Counter(number for draw in draws for number in draw.numbers)
    return np.array(
        [counter[number] for number in range(min_number, max_number + 1)],
        dtype=float,
    )


def normalized_entropy(counts: np.ndarray) -> float:
    probabilities = counts / counts.sum()
    entropy = -sum(
        probability * log(probability)
        for probability in probabilities
        if probability > 0
    )
    return float(entropy / log(len(counts)))


def maximum_z_score(
    counts: np.ndarray,
    draw_count: int,
    numbers_per_draw: int,
    population_size: int,
) -> float:
    probability = numbers_per_draw / population_size
    expected = draw_count * probability
    standard_deviation = (
        draw_count * probability * (1 - probability)
    ) ** 0.5
    return float(np.max(np.abs((counts - expected) / standard_deviation)))


def overlap_metrics(
    draws: Sequence[Draw],
) -> tuple[float, Counter[int]]:
    overlaps = [
        len(set(left.numbers) & set(right.numbers))
        for left, right in zip(draws, draws[1:])
    ]
    if not overlaps:
        return 0.0, Counter()
    return float(np.mean(overlaps)), Counter(overlaps)


def simulate_rows(
    rng: np.random.Generator,
    draw_count: int,
    population_size: int,
    numbers_per_draw: int,
) -> np.ndarray:
    random_scores = rng.random((draw_count, population_size))
    return np.argpartition(
        random_scores,
        numbers_per_draw - 1,
        axis=1,
    )[:, :numbers_per_draw]


def mean_overlap_array(sample: np.ndarray) -> float:
    if len(sample) < 2:
        return 0.0
    overlaps = [
        len(set(left.tolist()) & set(right.tolist()))
        for left, right in zip(sample, sample[1:])
    ]
    return float(np.mean(overlaps))
