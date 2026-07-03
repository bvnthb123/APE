"""Tests for the M2 database layer."""

from datetime import date

from ape.database.database import DatabaseManager
from ape.database.models import Draw
from ape.database.repositories import DrawRepository

EXPECTED_TABLES = {
    "draws",
    "features",
    "predictions",
    "engine_scores",
    "rules",
    "experiments",
    "run_records",
}


def build_sample_draw() -> Draw:
    numbers = [1, 8, 17, 25, 36, 45]
    odd_count = sum(number % 2 for number in numbers)
    low_count = sum(number <= 22 for number in numbers)
    return Draw(
        draw_date=date(2026, 7, 1),
        weekday_index=2,
        weekday_name="Thứ Tư",
        n1=numbers[0],
        n2=numbers[1],
        n3=numbers[2],
        n4=numbers[3],
        n5=numbers[4],
        n6=numbers[5],
        total_sum=sum(numbers),
        odd_count=odd_count,
        even_count=6 - odd_count,
        low_count=low_count,
        high_count=6 - low_count,
        source_file="test.xlsx",
        source_row=2,
    )


def test_database_initialization_creates_all_tables(tmp_path):
    manager = DatabaseManager(tmp_path / "test.db")
    manager.initialize()

    assert manager.health_check() is True
    assert EXPECTED_TABLES.issubset(set(manager.table_names()))

    manager.dispose()


def test_draw_repository_adds_and_reads_draw(tmp_path):
    manager = DatabaseManager(tmp_path / "test.db")
    manager.initialize()

    with manager.session() as session:
        repository = DrawRepository(session)
        stored = repository.add(build_sample_draw())
        assert stored.id is not None
        assert stored.numbers == [1, 8, 17, 25, 36, 45]

    with manager.session() as session:
        repository = DrawRepository(session)
        stored = repository.get_by_date(date(2026, 7, 1))
        assert stored is not None
        assert stored.total_sum == 132
        assert repository.count() == 1

    manager.dispose()
