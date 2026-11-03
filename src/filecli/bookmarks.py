"""Bookmark and recent-path list helpers."""

from pathlib import Path

from .settings import Settings, save_settings


def toggle_bookmark(settings: Settings, path: Path) -> bool:
    value = str(Path(path).expanduser().resolve())
    if value in settings.bookmarks:
        settings.bookmarks.remove(value)
        bookmarked = False
    else:
        settings.bookmarks.insert(0, value)
        bookmarked = True
    save_settings(settings)
    return bookmarked


def record_recent(settings: Settings, path: Path, *, is_file: bool = False, limit: int = 20) -> None:
    field = settings.recent_files if is_file else settings.recent_directories
    value = str(Path(path).expanduser().resolve())
    if value in field:
        field.remove(value)
    field.insert(0, value)
    del field[limit:]
    save_settings(settings)

