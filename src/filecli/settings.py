"""Persistent user settings and regional date/time formatting."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from platformdirs import user_config_path

from .themes import THEMES


@dataclass
class Settings:
    theme: str = "Classic Monochrome"
    show_hidden: bool = False
    start_directory: str = str(Path.home())
    sort_by: str = "name"
    sort_descending: bool = False
    preview_enabled: bool = True
    confirm_delete: bool = True
    timezone: str = "Asia/Kolkata"
    date_format: str = "%d-%m-%Y"
    clock_24h: bool = True
    relative_dates: bool = False
    calculate_directory_sizes: bool = False
    use_trash: bool = True
    bookmarks: list[str] | None = None
    recent_directories: list[str] | None = None
    recent_files: list[str] | None = None

    def __post_init__(self) -> None:
        if self.theme == "Classic DOS Blue":
            self.theme = "Classic Monochrome"
        self.bookmarks = self.bookmarks or []
        self.recent_directories = self.recent_directories or []
        self.recent_files = self.recent_files or []
        if self.theme not in THEMES:
            raise ValueError(f"Unknown theme: {self.theme}")
        if self.sort_by not in {"name", "size", "type", "created", "modified"}:
            raise ValueError(f"Unsupported sort field: {self.sort_by}")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {self.timezone}") from exc


def settings_path() -> Path:
    return Path(user_config_path("filecli", appauthor=False)) / "settings.json"


def load_settings(path: Path | None = None) -> Settings:
    config_path = path or settings_path()
    if not config_path.exists():
        return Settings()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read settings at {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Settings at {config_path} must contain a JSON object")
    allowed = {field.name for field in fields(Settings)}
    return Settings(**{key: value for key, value in data.items() if key in allowed})


def save_settings(settings: Settings, path: Path | None = None) -> Path:
    config_path = path or settings_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
    temporary.replace(config_path)
    return config_path


def format_timestamp(timestamp: float, settings: Settings) -> str:
    value = datetime.fromtimestamp(timestamp, tz=ZoneInfo(settings.timezone))
    clock = value.strftime("%H:%M" if settings.clock_24h else "%I:%M %p")
    suffix = " IST" if settings.timezone == "Asia/Kolkata" else f" {value.tzname() or settings.timezone}"
    return f"{value.strftime(settings.date_format)} {clock}{suffix}"
