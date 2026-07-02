"""
Application settings.
"""
from dataclasses import dataclass
from pathlib import Path

from ape.core.constants import (
    MIN_NUMBER,
    MAX_NUMBER,
    NUMBERS_PER_DRAW,
    DEFAULT_TOP_N,
    DEFAULT_BACKTEST_START,
)

@dataclass(frozen=True)
class AppSettings:
    root_dir: Path
    data_dir: Path
    logs_dir: Path
    reports_dir: Path
    database_file: Path
    default_excel_file: Path
    min_number: int = MIN_NUMBER
    max_number: int = MAX_NUMBER
    numbers_per_draw: int = NUMBERS_PER_DRAW
    top_n: int = DEFAULT_TOP_N
    backtest_start: int = DEFAULT_BACKTEST_START
    log_level: str = "INFO"

def build_settings() -> AppSettings:
    root_dir = Path(__file__).resolve().parents[2]
    data_dir = root_dir / "data"
    logs_dir = root_dir / "logs"
    reports_dir = root_dir / "reports"
    for directory in [data_dir, logs_dir, reports_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    return AppSettings(
        root_dir=root_dir,
        data_dir=data_dir,
        logs_dir=logs_dir,
        reports_dir=reports_dir,
        database_file=data_dir / "ape.db",
        default_excel_file=data_dir / "history.xlsx",
    )

SETTINGS = build_settings()
