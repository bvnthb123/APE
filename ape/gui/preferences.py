"""Persistent GUI preferences for the APE desktop app."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from ape.core.settings import SETTINGS


@dataclass(slots=True)
class GuiPreferences:
    """Small JSON-backed settings used by the desktop GUI."""

    window_width: int = 1240
    window_height: int = 790
    last_excel_dir: str = ""
    last_report_dir: str = ""

    @classmethod
    def load(cls, file_path: Path | None = None) -> "GuiPreferences":
        path = file_path or cls.default_path()
        if not path.exists():
            return cls()
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                window_width=int(data.get("window_width", 1240)),
                window_height=int(data.get("window_height", 790)),
                last_excel_dir=str(data.get("last_excel_dir", "")),
                last_report_dir=str(data.get("last_report_dir", "")),
            )
        except Exception:
            return cls()

    def save(self, file_path: Path | None = None) -> Path:
        path = file_path or self.default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def default_path() -> Path:
        return SETTINGS.data_dir / "gui_preferences.json"
