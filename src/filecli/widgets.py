"""Reusable monochrome file-manager widgets."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static


EXTENSION_COLORS = {
    ".py": "#5dade2",
    ".js": "#f4d03f",
    ".html": "#e67e22",
    ".htm": "#e67e22",
    ".css": "#bb8fce",
    ".json": "#48c9b0",
    ".md": "#85c1e9",
    ".txt": "#cccccc",
    ".log": "#aaaaaa",
    ".png": "#e056fd",
    ".jpg": "#e056fd",
    ".jpeg": "#e056fd",
    ".svg": "#e056fd",
    ".gif": "#e056fd",
    ".webp": "#e056fd",
    ".mp4": "#ff5c5c",
    ".mkv": "#ff5c5c",
    ".mov": "#ff5c5c",
    ".mp3": "#58d68d",
    ".wav": "#58d68d",
    ".flac": "#58d68d",
    ".zip": "#e59866",
    ".tar": "#e59866",
    ".gz": "#e59866",
    ".7z": "#e59866",
    ".exe": "#ff5c5c",
    ".appimage": "#ff5c5c",
    ".deb": "#ff5c5c",
    ".pdf": "#5dade2",
    ".docx": "#5dade2",
    ".xlsx": "#5dade2",
    ".pptx": "#5dade2",
    ".toml": "#48c9b0",
    ".yaml": "#48c9b0",
    ".yml": "#48c9b0",
    ".ini": "#48c9b0",
    ".conf": "#48c9b0",
}


def extension_color(path: Path) -> str:
    """Return the filename color for a file; selection styling is applied by the table."""
    return "#aaaaaa" if path.is_dir() and not path.is_symlink() else EXTENSION_COLORS.get(path.suffix.lower(), "#aaaaaa")


def file_name_cell(path: Path, *, selected: bool = False, cursor: bool = False) -> Text:
    """Create a filename cell with directory, extension, and selection precedence."""
    is_directory = path.is_dir() and not path.is_symlink()
    prefix = "[DIR] " if is_directory else "      "
    if cursor:
        style = None
    elif selected:
        style = "white on #444444"
    elif is_directory:
        style = "bold white"
    else:
        style = extension_color(path)
    return Text(prefix + path.name, style=style)


class DirectoryPanel(Vertical):
    """A bordered path heading and fixed-column directory table."""

    def __init__(self, label: str, path: Path):
        super().__init__(id=f"pane-{label.lower()}", classes="directory-panel")
        self.title = label
        self.path = path
        self.selected: set[Path] = set()
        self.visible_paths: list[Path] = []
        self.compact_columns = False
        self.refresh_generation = 0
        self.loading = False

    def compose(self) -> ComposeResult:
        yield Static(id=f"{self.id}-path", classes="pane-path")
        yield DataTable(id=f"{self.id}-table", cursor_type="row", zebra_stripes=False)


class BrandHeader(Static):
    """Compact FILECLI by MUSOS INDIA identity."""

    def __init__(self):
        super().__init__(id="brand")


class StatusBar(Static):
    """Current location, local time, and disk free-space status."""

    def __init__(self):
        super().__init__(id="status")


class FileInformationPanel(Static):
    """Selection metadata displayed below the directory panes."""

    def __init__(self):
        super().__init__("No item selected", id="info")


class FunctionToolbar(Static):
    """Responsive always-visible function-key legend."""

    FULL = "F1 Help  F2 Rename  F3 View  F4 Edit  F5 Copy  F6 Move  F7 Mkdir  F8 Delete  F9 Open  F10 Exit"
    COMPACT = "F1 Help F2 Ren F3 View F4 Edit F5 Copy F6 Move F7 Mkdir F8 Del F9 Open F10 Exit"
    MINI = "F1Help F2Ren F3View F4Edit F5Copy F6Move F7Mk F8Del F9Open F10Exit"

    def __init__(self):
        super().__init__(self.FULL, id="shortcuts")

    def resize_to(self, width: int) -> None:
        if width >= len(self.FULL):
            self.update(self.FULL)
        elif width >= len(self.COMPACT):
            self.update(self.COMPACT)
        else:
            self.update(self.MINI)
