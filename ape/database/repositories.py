"""Repository abstractions for database access."""

from __future__ import annotations

from datetime import date
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ape.database.base import Base
from ape.database.models import Draw, Prediction, Rule

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Small generic repository for common ORM operations."""

    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def get(self, entity_id: int) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def list_all(self, limit: int | None = None, offset: int = 0) -> list[ModelT]:
        statement = select(self.model).offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.scalars(statement).all())

    def count(self) -> int:
        statement = select(func.count()).select_from(self.model)
        return int(self.session.scalar(statement) or 0)

    def delete(self, entity: ModelT) -> None:
        self.session.delete(entity)
        self.session.flush()


class DrawRepository(BaseRepository[Draw]):
    """Queries and persistence rules for historical draws."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Draw)

    def get_by_date(self, draw_date: date) -> Draw | None:
        statement = select(Draw).where(Draw.draw_date == draw_date)
        return self.session.scalar(statement)

    def latest(self) -> Draw | None:
        statement = select(Draw).order_by(Draw.draw_date.desc()).limit(1)
        return self.session.scalar(statement)

    def list_chronological(self) -> list[Draw]:
        statement = select(Draw).order_by(Draw.draw_date.asc())
        return list(self.session.scalars(statement).all())

    def upsert(self, draw: Draw) -> tuple[Draw, bool]:
        """Insert a new draw or replace the mutable fields of an existing date.

        Returns:
            A tuple of (stored_draw, created).
        """
        existing = self.get_by_date(draw.draw_date)
        if existing is None:
            return self.add(draw), True

        for field_name in (
            "weekday_index",
            "weekday_name",
            "n1",
            "n2",
            "n3",
            "n4",
            "n5",
            "n6",
            "total_sum",
            "odd_count",
            "even_count",
            "low_count",
            "high_count",
            "source_file",
            "source_row",
        ):
            setattr(existing, field_name, getattr(draw, field_name))

        self.session.flush()
        return existing, False


class PredictionRepository(BaseRepository[Prediction]):
    """Queries for saved prediction records."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Prediction)

    def pending(self) -> list[Prediction]:
        statement = (
            select(Prediction)
            .where(Prediction.status == "pending")
            .order_by(Prediction.target_date.asc())
        )
        return list(self.session.scalars(statement).all())


class RuleRepository(BaseRepository[Rule]):
    """Queries for discovered rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Rule)

    def active(self, minimum_quality: float = 0.0) -> list[Rule]:
        statement = (
            select(Rule)
            .where(Rule.is_active.is_(True), Rule.quality_score >= minimum_quality)
            .order_by(Rule.quality_score.desc())
        )
        return list(self.session.scalars(statement).all())
