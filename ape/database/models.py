"""ORM models for the APE database layer."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ape.database.base import Base, TimestampMixin


class Draw(TimestampMixin, Base):
    """One historical six-number event."""

    __tablename__ = "draws"
    __table_args__ = (
        UniqueConstraint("draw_date", name="draw_date"),
        CheckConstraint("n1 >= 1 AND n6 <= 45", name="numbers_in_range"),
        CheckConstraint(
            "n1 < n2 AND n2 < n3 AND n3 < n4 AND n4 < n5 AND n5 < n6",
            name="numbers_sorted_unique",
        ),
        CheckConstraint("odd_count + even_count = 6", name="odd_even_total"),
        CheckConstraint("low_count + high_count = 6", name="low_high_total"),
        Index("ix_draws_draw_date", "draw_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draw_date: Mapped[date] = mapped_column(Date, nullable=False)
    weekday_index: Mapped[int] = mapped_column(Integer, nullable=False)
    weekday_name: Mapped[str] = mapped_column(String(20), nullable=False)

    n1: Mapped[int] = mapped_column(Integer, nullable=False)
    n2: Mapped[int] = mapped_column(Integer, nullable=False)
    n3: Mapped[int] = mapped_column(Integer, nullable=False)
    n4: Mapped[int] = mapped_column(Integer, nullable=False)
    n5: Mapped[int] = mapped_column(Integer, nullable=False)
    n6: Mapped[int] = mapped_column(Integer, nullable=False)

    total_sum: Mapped[int] = mapped_column(Integer, nullable=False)
    odd_count: Mapped[int] = mapped_column(Integer, nullable=False)
    even_count: Mapped[int] = mapped_column(Integer, nullable=False)
    low_count: Mapped[int] = mapped_column(Integer, nullable=False)
    high_count: Mapped[int] = mapped_column(Integer, nullable=False)

    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)

    features: Mapped[list[Feature]] = relationship(
        back_populates="draw",
        cascade="all, delete-orphan",
    )

    @property
    def numbers(self) -> list[int]:
        """Return the six values as a sorted list."""
        return [self.n1, self.n2, self.n3, self.n4, self.n5, self.n6]


class Feature(TimestampMixin, Base):
    """One generated feature value for a draw and optional target number."""

    __tablename__ = "features"
    __table_args__ = (
        UniqueConstraint(
            "draw_id",
            "target_number",
            "feature_name",
            "feature_version",
            name="draw_target_feature_version",
        ),
        Index("ix_features_lookup", "draw_id", "target_number", "feature_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draw_id: Mapped[int] = mapped_column(
        ForeignKey("draws.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    feature_group: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_name: Mapped[str] = mapped_column(String(120), nullable=False)
    feature_value: Mapped[float] = mapped_column(Float, nullable=False)
    feature_version: Mapped[str] = mapped_column(String(30), default="1.0", nullable=False)

    draw: Mapped[Draw] = relationship(back_populates="features")


class Prediction(TimestampMixin, Base):
    """A saved Top-N prediction for a future target date."""

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("run_id", "engine_name", name="run_engine"),
        Index("ix_predictions_target_date", "target_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    engine_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    predicted_numbers: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    score_map: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_numbers: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    hit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)


class EngineScore(TimestampMixin, Base):
    """Performance result of one engine for one evaluated target date."""

    __tablename__ = "engine_scores"
    __table_args__ = (
        UniqueConstraint("run_id", "engine_name", "target_date", name="run_engine_target"),
        Index("ix_engine_scores_engine", "engine_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    engine_name: Mapped[str] = mapped_column(String(80), nullable=False)
    predicted_numbers: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    actual_numbers: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_before: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    weight_after: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    evaluation_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Rule(TimestampMixin, Base):
    """A discovered rule with statistical quality metrics."""

    __tablename__ = "rules"
    __table_args__ = (Index("ix_rules_active_score", "is_active", "quality_score"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    antecedent: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    consequent: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    support_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    lift: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_success_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Experiment(TimestampMixin, Base):
    """A tracked research experiment and its measured result."""

    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="planned", nullable=False)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    baseline_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    improvement_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunRecord(TimestampMixin, Base):
    """Metadata for one application, import, backtest or prediction run."""

    __tablename__ = "run_records"
    __table_args__ = (Index("ix_run_records_type_status", "run_type", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    run_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="started", nullable=False)
    app_version: Mapped[str] = mapped_column(String(30), nullable=False)
    parameters: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
