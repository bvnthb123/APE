"""Database-backed service for descriptive reports."""

from ape.analytics.analyzer import EventSequenceAnalyzer
from ape.analytics.report import AnalysisReport
from ape.database.database import DATABASE, DatabaseManager
from ape.database.repositories import DrawRepository


class AnalysisService:
    """Load historical rows from SQLite and generate a report."""

    def __init__(self, database: DatabaseManager | None = None) -> None:
        self.database = database or DATABASE

    def generate(self, limit: int = 10) -> AnalysisReport:
        self.database.initialize()
        with self.database.session() as session:
            draws = DrawRepository(session).list_chronological()
        return EventSequenceAnalyzer().analyze(draws, limit=limit)
