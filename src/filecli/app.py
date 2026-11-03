"""Textual dual-pane terminal interface."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import stat
import tempfile
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Label, Static, TextArea

from . import __version__
from .archives import archive_members, create_archive, extract_archive
from .bookmarks import record_recent, toggle_bookmark
from .browser import list_directory
from .errors import OperationError
from .fileops import (
    Progress, copy_path, create_directory, create_file, move_path, remove_path, rename,
)
from .preview import preview_file
from .search import search_files
from .settings import Settings, format_timestamp, load_settings, save_settings
from .shortcuts import HELP_TEXT
from .storage import largest_files, mounted_disks
from .themes import PALETTES
from .widgets import (
    BrandHeader,
    DirectoryPanel,
    FileInformationPanel,
    FunctionToolbar,
    StatusBar,
    file_name_cell,
)

LOGGER = logging.getLogger("filecli")


class PromptScreen(ModalScreen[str | None]):
    CSS = """
    PromptScreen { align: center middle; background: #000000 80%; }
    #prompt-box { width: 70%; height: auto; max-height: 80%; border: solid #ffffff; padding: 1 2; background: #000000; }
    #prompt-input { margin-top: 1; }
    """
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "submit", "OK"),
        Binding("ctrl+enter", "submit", "Save", priority=True),
    ]

    def __init__(self, title: str, initial: str = "", multiline: bool = False):
        super().__init__()
        self.prompt_title = title
        self.initial = initial
        self.multiline = multiline

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-box"):
            yield Label(self.prompt_title)
            if self.multiline:
                yield TextArea(self.initial, id="prompt-input")
            else:
                yield Input(value=self.initial, id="prompt-input")

    def on_mount(self) -> None:
        self.query_one("#prompt-input").focus()

    def action_submit(self) -> None:
        widget = self.query_one("#prompt-input")
        self.dismiss(widget.text if isinstance(widget, TextArea) else widget.value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    CSS = """
    ConfirmScreen { align: center middle; background: #000000 80%; }
    #confirm-box { width: 70%; height: auto; border: solid #ffffff; padding: 1 2; background: #000000; }
    """
    BINDINGS = [("escape", "no", "Cancel"), ("n", "no", "No"), ("y", "yes", "Yes")]

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(self.message)
            yield Label("Y: confirm     N / ESC: cancel")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class FileCLI(App[None]):
    TITLE = "FILECLI"
    BINDINGS = [
        Binding("up", "move_cursor(-1)", "Up", show=False),
        Binding("down", "move_cursor(1)", "Down", show=False),
        Binding("left", "left", "Left", show=False),
        Binding("right", "right", "Right", show=False),
        Binding("enter", "open_item", "Open", show=False),
        Binding("backspace", "parent", "Parent", show=False),
        Binding("tab", "switch_pane", "Pane", show=False, priority=True),
        Binding("space", "toggle_select", "Select", show=False),
        Binding("ctrl+a", "select_all", "Select all", show=False),
        Binding("f1", "help", "Help"),
        Binding("f2", "rename_item", "Rename"),
        Binding("f3", "preview_item", "View"),
        Binding("f4", "edit_item", "Edit"),
        Binding("f5", "copy_items", "Copy"),
        Binding("f6", "move_items", "Move"),
        Binding("f7", "new_directory", "Mkdir"),
        Binding("f8", "delete_items", "Delete"),
        Binding("f9", "open_item", "Open"),
        Binding("f10", "quit", "Exit"),
        Binding("/", "search", "Search", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("s", "sort_items", "Sort", show=False),
        Binding("h", "toggle_hidden", "Hidden", show=False),
        Binding("d", "storage", "Storage", show=False),
        Binding("b", "bookmark", "Bookmark", show=False),
        Binding("g", "goto_path", "Go to", show=False),
        Binding("c", "compare_directories", "Compare", show=False),
        Binding("x", "swap_panes", "Swap", show=False),
        Binding("n", "new_file", "New file", show=False),
        Binding("t", "settings", "Settings", show=False),
        Binding("z", "create_archive", "Archive", show=False),
        Binding("u", "extract_archive", "Extract", show=False),
        Binding("escape", "back", "Back", show=False),
    ]
    CSS = """
    Screen { width: 100%; height: 100%; background: #000000; color: #ffffff; }
    #brand { width: 100%; height: 1; padding: 0 1; color: #ffffff; text-style: bold; }
    #status { width: 100%; height: 1; padding: 0 1; color: #aaaaaa; border-bottom: solid #444444; }
    #panes { width: 100%; height: 1fr; min-height: 1; }
    DirectoryPanel {
        width: 1fr;
        height: 1fr;
        min-width: 0;
        min-height: 0;
        border: solid #555555;
        margin: 0;
    }
    DirectoryPanel.active { border: solid #ffffff; }
    DirectoryPanel.inactive { border: solid #555555; }
    .pane-path {
        height: 1;
        padding: 0 1;
        color: #ffffff;
        background: #111111;
        text-style: bold;
    }
    DataTable {
        height: 1fr;
        background: #000000;
        color: #ffffff;
        scrollbar-size-horizontal: 0;
        scrollbar-size-vertical: 1;
    }
    DataTable > .datatable--header {
        color: #ffffff;
        background: #202020;
        text-style: bold;
    }
    DataTable > .datatable--cursor {
        background: #444444;
        color: #ffffff;
    }
    DataTable:focus > .datatable--cursor {
        background: #ffffff;
        color: #000000;
        text-style: bold;
    }
    DataTable > .datatable--fixed-cursor {
        background: #444444;
        color: #ffffff;
    }
    #info { width: 100%; height: 2; padding: 0 1; color: #aaaaaa; border-top: solid #555555; }
    #message { width: 100%; height: 1; color: #ffffff; padding: 0 1; }
    #shortcuts {
        width: 100%;
        height: 1;
        padding: 0 1;
        color: #ffffff;
        background: #181818;
        text-style: bold;
    }
    .narrow DirectoryPanel.inactive { display: none; }
    .narrow DirectoryPanel { margin: 0; }
    .compact #info { height: 1; }
    """

    def __init__(self, start_path: Path | None = None):
        super().__init__()
        self.settings = load_settings()
        start = (start_path or Path(self.settings.start_directory)).expanduser()
        if not start.is_dir():
            start = Path.home()
        self.active_index = 0
        self.left = DirectoryPanel("Left", start)
        self.right = DirectoryPanel("Right", start)
        self.copy_buffer: list[Path] = []
        self.operation_cancel = threading.Event()
        self.operation_running = False
        self._last_layout_width = -1
        self.info_panel = FileInformationPanel()
        self._apply_theme()

    def _apply_theme(self) -> None:
        background, foreground, _, _, grey = PALETTES[self.settings.theme]
        self.styles.background = background
        self.styles.color = foreground
        self.stylesheet.add_source(
            f"Screen {{ background: {background}; color: {foreground}; }} "
            f"DirectoryPanel.active {{ border: solid {foreground}; }} "
            f"DirectoryPanel.inactive {{ border: solid {grey}; }}"
        )

    def compose(self) -> ComposeResult:
        yield BrandHeader()
        yield StatusBar()
        with Horizontal(id="panes"):
            yield self.left
            yield self.right
        yield self.info_panel
        yield Static(id="message")
        yield FunctionToolbar()

    async def on_mount(self) -> None:
        for pane in (self.left, self.right):
            table = self._table(pane)
            self._set_columns(pane)
            self.refresh_pane(pane)
        self._apply_responsive_layout()
        self._update_status()
        self.set_interval(60, self._update_status)
        self._focus_active()

    def _table(self, pane: DirectoryPanel) -> DataTable:
        return pane.table

    def _pane_path_label(self, pane: DirectoryPanel) -> Static:
        return pane.path_label

    @property
    def active(self) -> DirectoryPanel:
        return self.left if self.active_index == 0 else self.right

    @property
    def other(self) -> DirectoryPanel:
        return self.right if self.active_index == 0 else self.left

    def _focus_active(self) -> None:
        self._table(self.active).focus()

    def _set_columns(self, pane: DirectoryPanel) -> None:
        table = self._table(pane)
        table.clear(columns=True)
        pane.compact_columns = self.size.width < 112
        pane_width = self.size.width if "narrow" in self.classes else max(40, pane.size.width)
        if pane.compact_columns:
            table.add_column("Name", width=max(15, pane_width - 32), key="name")
            table.add_column("Size", width=8, key="size")
            table.add_column("Modified", width=16, key="modified")
        else:
            table.add_column("Name", width=max(12, pane_width - 42), key="name")
            table.add_column("Ext", width=6, key="extension")
            table.add_column("Size", width=9, key="size")
            table.add_column("Modified", width=18, key="modified")
        table.add_column("Type", width=5, key="type")

    def _apply_responsive_layout(self) -> None:
        narrow = self.size.width < 88
        compact = self.size.width < 112
        self.set_class(narrow, "narrow")
        self.set_class(compact, "compact")
        for index, pane in enumerate((self.left, self.right)):
            active = index == self.active_index
            pane.set_class(active, "active")
            pane.set_class(not active, "inactive")
            pane.display = not (narrow and not active)
        if self.is_mounted:
            if self._last_layout_width == self.size.width:
                return
            self._last_layout_width = self.size.width
            self.query_one("#shortcuts", FunctionToolbar).resize_to(self.size.width)
            for pane in (self.left, self.right):
                self._set_columns(pane)
                self.refresh_pane(pane)
            self._update_status()
            self._update_info()

    def on_resize(self, event) -> None:
        self._apply_responsive_layout()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self.screen_stack and self.screen is not self.screen_stack[0]:
            return False
        if isinstance(self.focused, (Input, TextArea)):
            return False
        return True

    def refresh_pane(self, pane: DirectoryPanel) -> None:
        table = self._table(pane)
        selected_path = pane.visible_paths[table.cursor_row] if (
            pane.visible_paths and table.cursor_row is not None and table.cursor_row < len(pane.visible_paths)
        ) else None
        pane.refresh_generation += 1
        pane.loading = True
        generation = pane.refresh_generation
        if self.is_mounted:
            self._pane_path_label(pane).update(f"{pane.title.upper()}  Loading directory…")
        if pane is self.left:
            self._refresh_left_worker(
                pane, generation, pane.path, selected_path, self.settings.show_hidden,
                self.settings.sort_by, self.settings.sort_descending,
            )
        else:
            self._refresh_right_worker(
                pane, generation, pane.path, selected_path, self.settings.show_hidden,
                self.settings.sort_by, self.settings.sort_descending,
            )

    @work(thread=True, group="refresh-left", exclusive=True)
    def _refresh_left_worker(
        self, pane: DirectoryPanel, generation: int, path: Path, selected_path: Path | None,
        show_hidden: bool, sort_by: str, descending: bool,
    ) -> None:
        self._load_pane_snapshot(
            pane, generation, path, selected_path, show_hidden, sort_by, descending,
        )

    @work(thread=True, group="refresh-right", exclusive=True)
    def _refresh_right_worker(
        self, pane: DirectoryPanel, generation: int, path: Path, selected_path: Path | None,
        show_hidden: bool, sort_by: str, descending: bool,
    ) -> None:
        self._load_pane_snapshot(
            pane, generation, path, selected_path, show_hidden, sort_by, descending,
        )

    def _load_pane_snapshot(
        self, pane: DirectoryPanel, generation: int, path: Path, selected_path: Path | None,
        show_hidden: bool, sort_by: str, descending: bool,
    ) -> None:
        try:
            entries = list_directory(path, show_hidden, sort_by, descending)
            rows: list[tuple[Path, bool, str, str, str, str]] = []
            for item in entries:
                try:
                    info = item.lstat()
                except OSError:
                    continue
                is_directory = item.is_dir() and not item.is_symlink()
                kind = "DIR" if is_directory else ("LINK" if item.is_symlink() else "FILE")
                extension = "DIR" if is_directory else ("LINK" if item.is_symlink() else (item.suffix[1:].upper() or "—"))
                size = "—" if is_directory else self._human_size(info.st_size)
                timestamp = format_timestamp(info.st_mtime, self.settings).split()
                modified_date = timestamp[0] if timestamp else ""
                modified_time = timestamp[1] if len(timestamp) > 1 else ""
                modified = f"{modified_date} {modified_time}"
                rows.append((item, is_directory, kind, extension, size, modified))
            self.call_from_thread(
                self._populate_pane, pane, generation, selected_path, rows, None,
            )
        except OSError as exc:
            self.call_from_thread(self._populate_pane, pane, generation, selected_path, [], str(exc))

    def _populate_pane(
        self, pane: DirectoryPanel, generation: int, selected_path: Path | None,
        rows: list[tuple[Path, bool, str, str, str, str]], error: str | None,
    ) -> None:
        if generation != pane.refresh_generation or not self.is_mounted:
            return
        if error:
            self.notify(f"Cannot read {pane.path}: {error}", severity="error", timeout=5)
        pane.loading = False
        current_selection = self._selected_path(pane)
        available = {row[0] for row in rows}
        if current_selection in available:
            selected_path = current_selection
        self._populate_pane_worker(pane, generation, selected_path, rows, error)

    @work(group="populate-left", exclusive=True)
    async def _populate_left_worker(
        self, pane: DirectoryPanel, generation: int, selected_path: Path | None,
        rows: list[tuple[Path, bool, str, str, str, str]], error: str | None,
    ) -> None:
        await self._populate_pane_rows(pane, generation, selected_path, rows)

    @work(group="populate-right", exclusive=True)
    async def _populate_right_worker(
        self, pane: DirectoryPanel, generation: int, selected_path: Path | None,
        rows: list[tuple[Path, bool, str, str, str, str]], error: str | None,
    ) -> None:
        await self._populate_pane_rows(pane, generation, selected_path, rows)

    def _populate_pane_worker(
        self, pane: DirectoryPanel, generation: int, selected_path: Path | None,
        rows: list[tuple[Path, bool, str, str, str, str]], error: str | None,
    ) -> None:
        if pane is self.left:
            self._populate_left_worker(pane, generation, selected_path, rows, error)
        else:
            self._populate_right_worker(pane, generation, selected_path, rows, error)

    async def _populate_pane_rows(
        self, pane: DirectoryPanel, generation: int, selected_path: Path | None,
        rows: list[tuple[Path, bool, str, str, str, str]],
    ) -> None:
        table = self._table(pane)
        table.clear()
        pane.visible_paths.clear()
        for index, (item, is_directory, kind, extension, size, modified) in enumerate(rows):
            if generation != pane.refresh_generation:
                return
            is_cursor = selected_path == item and pane is self.active
            is_selected = item in pane.selected and not is_cursor
            name = file_name_cell(item, selected=is_selected, cursor=is_cursor)
            cells = [name, size, modified, kind] if pane.compact_columns else [name, extension, size, modified, kind]
            if is_selected:
                cells = [Text(str(cell), style="white on #444444") for cell in cells]
            table.add_row(*cells, key=str(item))
            pane.visible_paths.append(item)
            if selected_path == item:
                table.move_cursor(row=index)
            if index % 250 == 249:
                await asyncio.sleep(0)
        width = max(12, pane.size.width - 5)
        path_text = str(pane.path)
        if len(path_text) > width:
            path_text = "…" + path_text[-(width - 1):]
        loading = "  [LOADING]" if pane.loading else ""
        self._pane_path_label(pane).update(f"{pane.title.upper()}  {path_text}{loading}")
        self._update_info()

    def _update_status(self) -> None:
        now = format_timestamp(datetime.now().timestamp(), self.settings)
        try:
            usage = shutil.disk_usage(self.active.path)
            disk = f"Free {self._human_size(usage.free)} / {self._human_size(usage.total)}"
        except OSError:
            disk = "Disk space unavailable"
        self.query_one("#brand", BrandHeader).update(
            Text.assemble(("FILECLI", "bold white"), ("  |  By MUSOS INDIA", "#aaaaaa"))
        )
        path = str(self.active.path)
        path_width = max(10, self.size.width - len(now) - len(disk) - 25)
        if len(path) > path_width:
            path = "…" + path[-(path_width - 1):]
        self.query_one("#status", StatusBar).update(
            Text.assemble((path, "white"), ("  |  ", "#555555"), (now, "#aaaaaa"),
                          ("  |  ", "#555555"), (disk, "#aaaaaa"))
        )

    @staticmethod
    def _human_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
            value /= 1024
        return f"{size}B"

    def _selected_path(self, pane: DirectoryPanel | None = None) -> Path | None:
        pane = pane or self.active
        table = self._table(pane)
        if table.row_count == 0:
            return None
        row = table.cursor_row
        if row is None or row >= len(pane.visible_paths):
            return None
        return pane.visible_paths[row]

    def _selected_paths(self, pane: DirectoryPanel | None = None) -> list[Path]:
        pane = pane or self.active
        selected = sorted(pane.selected)
        if selected:
            return selected
        current = self._selected_path(pane)
        return [current] if current else []

    def _update_info(self) -> None:
        path = self._selected_path()
        if path is None or not path.exists() and not path.is_symlink():
            self.info_panel.update("No item selected")
            return
        try:
            info = path.lstat()
            kind = "Directory" if path.is_dir() and not path.is_symlink() else ("Symbolic link" if path.is_symlink() else "File")
            size = self._human_size(info.st_size)
            details = f"{path.name}  |  {kind}  |  {size}  |  {format_timestamp(info.st_mtime, self.settings)}  |  {stat.filemode(info.st_mode)}"
            if path.is_symlink():
                details += f"  -> {path.readlink()}"
            self.info_panel.update(details)
        except OSError as exc:
            self.info_panel.update(f"Cannot inspect selection: {exc}")

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.has_focus:
            self.active_index = 0 if event.data_table.id == self.left.id + "-table" else 1
            self._apply_responsive_layout()
        self._update_info()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.active_index = 0 if event.data_table.id == self.left.id + "-table" else 1
        self.action_open_item()

    def action_move_cursor(self, delta: int) -> None:
        table = self._table(self.active)
        if table.row_count:
            table.move_cursor(row=max(0, min(table.row_count - 1, (table.cursor_row or 0) + delta)))

    def action_switch_pane(self) -> None:
        self.active_index = 1 - self.active_index
        self._apply_responsive_layout()
        self._focus_active()
        self._update_status()

    def action_left(self) -> None:
        self.action_parent()

    def action_right(self) -> None:
        path = self._selected_path()
        if path and path.is_dir() and not path.is_symlink():
            self._navigate(self.active, path)
        else:
            self.action_switch_pane()

    def action_open_item(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        if path.is_dir() and not path.is_symlink():
            self._navigate(self.active, path)
        elif path.suffix.lower() in {".zip", ".tar", ".gz", ".tgz"}:
            try:
                members = archive_members(path)
                self._show_text(f"Archive: {path.name}\n\n" + "\n".join(members[:500]))
            except Exception as exc:
                self._error(exc)
        else:
            self.action_preview_item()

    def action_create_archive(self) -> None:
        items = self._selected_paths()
        if items:
            self.push_screen(
                PromptScreen("ZIP archive filename:"),
                lambda value: self._create_archive_result(items, value),
            )

    def _create_archive_result(self, items: list[Path], value: str | None) -> None:
        if not value:
            return
        try:
            output = self._new_child_path(value)
            if output.suffix.lower() != ".zip":
                output = output.with_name(output.name + ".zip")
            self._create_archive_worker(items, output)
        except Exception as exc:
            self._error(exc)

    @work(thread=True)
    def _create_archive_worker(self, items: list[Path], output: Path) -> None:
        try:
            create_archive(items, output)
            self.call_from_thread(self._operation_done, f"Created {output.name}", None)
        except Exception as exc:
            self.call_from_thread(self._operation_done, "", str(exc))

    def action_extract_archive(self) -> None:
        path = self._selected_path()
        if not path or path.suffix.lower() not in {".zip", ".tar", ".gz", ".tgz"}:
            self.notify("Select a ZIP or TAR archive", severity="warning")
            return
        archive_name = path.name[:-7] if path.name.lower().endswith(".tar.gz") else path.stem
        destination = self.active.path / archive_name
        if destination.exists():
            self.push_screen(
                ConfirmScreen(f"Extract into existing directory {destination.name}? Existing files are not overwritten."),
                lambda confirmed: self._extract_archive_result(path, destination, confirmed),
            )
        else:
            self._extract_archive_result(path, destination, True)

    def _extract_archive_result(self, archive: Path, destination: Path, confirmed: bool) -> None:
        if confirmed:
            self._extract_archive_worker(archive, destination)

    @work(thread=True)
    def _extract_archive_worker(self, archive: Path, destination: Path) -> None:
        try:
            extracted = extract_archive(archive, destination)
            self.call_from_thread(self._operation_done, f"Extracted {len(extracted)} archive entries", None)
        except Exception as exc:
            self.call_from_thread(self._operation_done, "", str(exc))

    def _navigate(self, pane: DirectoryPanel, path: Path) -> None:
        try:
            resolved = path.expanduser().resolve(strict=True)
            if not resolved.is_dir():
                self.notify(f"Not a directory: {resolved}", severity="warning")
                return
            pane.path = resolved
            pane.selected.clear()
            self.refresh_pane(pane)
            self._update_status()
            self._focus_active()
            record_recent(self.settings, resolved)
        except OSError as exc:
            self._error(exc)

    def action_parent(self) -> None:
        if self.active.path.parent != self.active.path:
            self._navigate(self.active, self.active.path.parent)

    def action_toggle_select(self) -> None:
        path = self._selected_path()
        if path:
            if path in self.active.selected:
                self.active.selected.remove(path)
            else:
                self.active.selected.add(path)
            self.refresh_pane(self.active)

    def action_select_all(self) -> None:
        try:
            self.active.selected = {
                item for item in self.active.path.iterdir()
                if self.settings.show_hidden or not item.name.startswith(".")
            }
            self.refresh_pane(self.active)
        except OSError as exc:
            self._error(exc)

    def action_refresh(self) -> None:
        self.refresh_pane(self.active)

    def action_toggle_hidden(self) -> None:
        self.settings.show_hidden = not self.settings.show_hidden
        try:
            save_settings(self.settings)
        except OSError as exc:
            self._error(exc)
            self.settings.show_hidden = not self.settings.show_hidden
            return
        self.refresh_pane(self.active)
        self.notify(f"Hidden files {'shown' if self.settings.show_hidden else 'hidden'}")

    def action_goto_path(self) -> None:
        self.push_screen(PromptScreen("Go to directory path:"), self._goto_result)

    def _goto_result(self, value: str | None) -> None:
        if value:
            self._navigate(self.active, Path(value))

    def action_new_directory(self) -> None:
        self.push_screen(PromptScreen("New directory name:"), self._mkdir_result)

    def _mkdir_result(self, value: str | None) -> None:
        if value:
            try:
                create_directory(self._new_child_path(value))
                self.refresh_pane(self.active)
            except Exception as exc:
                self._error(exc)

    def action_new_file(self) -> None:
        self.push_screen(PromptScreen("New file name:"), self._new_file_result)

    def _new_file_result(self, value: str | None) -> None:
        if value:
            try:
                create_file(self._new_child_path(value))
                self.refresh_pane(self.active)
            except Exception as exc:
                self._error(exc)

    def _new_child_path(self, name: str) -> Path:
        if not name or Path(name).name != name or name in {".", ".."}:
            raise OperationError("Enter a filename without directory separators")
        return self.active.path / name

    def action_rename_item(self) -> None:
        path = self._selected_path()
        if path:
            self.push_screen(PromptScreen(f"Rename {path.name} to:", path.name), lambda value: self._rename_result(path, value))

    def _rename_result(self, path: Path, value: str | None) -> None:
        if value and value != path.name:
            try:
                rename(path, value)
                self.refresh_pane(self.active)
            except Exception as exc:
                self._error(exc)

    def action_copy_items(self) -> None:
        if self.active.loading:
            self.notify("Wait for the directory listing to finish", severity="warning")
            return
        items = self._selected_paths()
        if not items:
            return
        destination_dir = self.other.path
        if any((destination_dir / item.name).exists() or (destination_dir / item.name).is_symlink() for item in items):
            self.push_screen(ConfirmScreen("A destination exists. Replace conflicting item(s)?"), lambda ok: self._copy_result(items, destination_dir, ok))
        else:
            self._copy_result(items, destination_dir, False)

    @work(thread=True, group="file-operation", exclusive=True)
    def _copy_worker(self, items: list[Path], destination_dir: Path, overwrite: bool) -> None:
        try:
            self.operation_running = True
            total = sum(
                item.stat().st_size if item.is_file() and not item.is_symlink()
                else (self._directory_size(item) if item.is_dir() and not item.is_symlink() else 0)
                for item in items
            )
            progress = Progress(
                total_bytes=total,
                cancel_event=self.operation_cancel,
                on_update=lambda value: self.call_from_thread(
                    self._show_progress, value.completed_bytes, value.total_bytes
                ),
            )
            for item in items:
                progress.check_cancelled()
                copy_path(item, destination_dir / item.name, progress=progress, overwrite=overwrite)
            self.call_from_thread(self._operation_done, f"Copied {len(items)} item(s)", None)
        except Exception as exc:
            self.call_from_thread(self._operation_done, "", str(exc))

    @staticmethod
    def _directory_size(path: Path) -> int:
        total = 0
        for root, dirs, files in os.walk(path, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
            for name in files:
                file_path = Path(root) / name
                try:
                    total += file_path.lstat().st_size
                except OSError:
                    continue
        return total

    def _show_progress(self, completed: int, total: int) -> None:
        percent = f"{completed / total:.0%}" if total else "working"
        self.query_one("#message", Static).update(f"COPY: {percent}  {self._human_size(completed)} / {self._human_size(total)}")

    def _copy_result(self, items: list[Path], destination: Path, confirmed: bool) -> None:
        conflicts = any((destination / item.name).exists() or (destination / item.name).is_symlink() for item in items)
        if conflicts and not confirmed:
            return
        if self.operation_running:
            self.notify("Wait for the current file operation to finish", severity="warning")
            return
        self.operation_cancel.clear()
        self.operation_running = True
        self._copy_worker(items, destination, confirmed)

    def action_move_items(self) -> None:
        if self.active.loading:
            self.notify("Wait for the directory listing to finish", severity="warning")
            return
        items = self._selected_paths()
        if not items:
            return
        destination = self.other.path
        conflicts = any((destination / item.name).exists() or (destination / item.name).is_symlink() for item in items)
        if conflicts:
            self.push_screen(ConfirmScreen("A destination exists. Replace conflicting item(s)?"), lambda ok: self._move_result(items, destination, ok))
        else:
            self._move_result(items, destination, False)

    def _move_result(self, items: list[Path], destination: Path, confirmed: bool) -> None:
        conflicts = any((destination / item.name).exists() or (destination / item.name).is_symlink() for item in items)
        if conflicts and not confirmed:
            return
        if self.operation_running:
            self.notify("Wait for the current file operation to finish", severity="warning")
            return
        self.operation_cancel.clear()
        self.operation_running = True
        self._move_worker(items, destination, confirmed)

    def _show_move_progress(self, completed: int, total: int) -> None:
        percent = f"{completed / total:.0%}" if total else "working"
        self.query_one("#message", Static).update(f"MOVE: {percent}  {self._human_size(completed)} / {self._human_size(total)}")

    @work(thread=True, group="file-operation", exclusive=True)
    def _move_worker(self, items: list[Path], destination: Path, overwrite: bool) -> None:
        try:
            self.operation_running = True
            total = sum(
                item.stat().st_size if item.is_file() and not item.is_symlink()
                else (self._directory_size(item) if item.is_dir() and not item.is_symlink() else 0)
                for item in items
            )
            progress = Progress(
                total_bytes=total,
                cancel_event=self.operation_cancel,
                on_update=lambda value: self.call_from_thread(
                    self._show_move_progress, value.completed_bytes, value.total_bytes
                ),
            )
            for item in items:
                progress.check_cancelled()
                move_path(item, destination / item.name, overwrite=overwrite, progress=progress)
            self.call_from_thread(self._operation_done, f"Moved {len(items)} item(s)", None)
        except Exception as exc:
            self.call_from_thread(self._operation_done, "", str(exc))

    def _operation_done(self, message: str, error: str | None) -> None:
        self.operation_running = False
        if error:
            self._error(error)
        else:
            self.notify(message)
        self.refresh_pane(self.left)
        self.refresh_pane(self.right)

    def action_delete_items(self) -> None:
        items = self._selected_paths()
        if not items:
            return
        prompt = "Move to Trash" if self.settings.use_trash else "Permanently delete"
        self.push_screen(ConfirmScreen(f"{prompt} {len(items)} selected item(s)? This cannot be undone if permanently deleted."), lambda ok: self._delete_result(items, ok))

    def _delete_result(self, items: list[Path], confirmed: bool) -> None:
        if not confirmed:
            return
        try:
            for item in items:
                remove_path(item, permanent=not self.settings.use_trash)
            self.active.selected.clear()
            self.refresh_pane(self.active)
            self.notify(f"Deleted {len(items)} item(s)")
        except Exception as exc:
            self._error(exc)

    def action_preview_item(self) -> None:
        path = self._selected_path()
        if not path:
            return
        try:
            if path.is_file() and not path.is_symlink():
                record_recent(self.settings, path, is_file=True)
            self._show_text(preview_file(path, max_bytes=65536))
        except Exception as exc:
            self._error(exc)

    def action_edit_item(self) -> None:
        path = self._selected_path()
        if not path or not path.is_file() or path.is_symlink():
            self.notify("Select a regular text file to edit", severity="warning")
            return
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            self._error(f"Cannot open text file: {exc}")
            return
        self.push_screen(PromptScreen(f"Edit {path.name} (Ctrl+Enter saves):", text, multiline=True), lambda value: self._edit_result(path, value))

    def _edit_result(self, path: Path, value: str | None) -> None:
        if value is not None:
            temporary: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(value)
                shutil.copystat(path, temporary, follow_symlinks=False)
                temporary.replace(path)
                self.notify(f"Saved {path.name}")
                self.refresh_pane(self.active)
            except OSError as exc:
                self._error(exc)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

    def _show_text(self, text: str) -> None:
        self.push_screen(TextScreen(text))

    def action_search(self) -> None:
        self.push_screen(PromptScreen("Search filename (optionally use *.ext):"), self._search_result)

    def _search_result(self, query: str | None) -> None:
        if query is None:
            return
        extension = None
        if query.startswith("*."):
            extension, query = query[1:], ""
        self._search_worker(self.active.path, query, extension)

    @work(thread=True)
    def _search_worker(self, root: Path, query: str, extension: str | None) -> None:
        try:
            results = search_files(root, query, extension=extension, recursive=True)
            text = f"Search results ({len(results)}):\n\n" + "\n".join(str(path) for path in results[:500])
            self.call_from_thread(self._show_text, text)
        except Exception as exc:
            self.call_from_thread(self._error, exc)

    def action_sort_items(self) -> None:
        options = ("name", "size", "type", "created", "modified")
        current = options.index(self.settings.sort_by)
        self.settings.sort_by = options[(current + 1) % len(options)]
        if self.settings.sort_by == "name":
            self.settings.sort_descending = not self.settings.sort_descending
        try:
            save_settings(self.settings)
        except OSError as exc:
            self._error(exc)
            return
        self.refresh_pane(self.left)
        self.refresh_pane(self.right)
        self.notify(f"Sorted by {self.settings.sort_by} {'descending' if self.settings.sort_descending else 'ascending'}")

    def action_swap_panes(self) -> None:
        self.left.path, self.right.path = self.right.path, self.left.path
        self.left.selected, self.right.selected = self.right.selected, self.left.selected
        self.refresh_pane(self.left)
        self.refresh_pane(self.right)

    def action_compare_directories(self) -> None:
        try:
            left = {path.name for path in self.left.path.iterdir()}
            right = {path.name for path in self.right.path.iterdir()}
            only_left, only_right = sorted(left - right), sorted(right - left)
            self._show_text("Directory comparison\n\nOnly in left:\n" + "\n".join(only_left or ["(none)"]) +
                            "\n\nOnly in right:\n" + "\n".join(only_right or ["(none)"]))
        except OSError as exc:
            self._error(exc)

    def action_storage(self) -> None:
        self._storage_worker(self.active.path)

    @work(thread=True)
    def _storage_worker(self, current_path: Path) -> None:
        lines = ["Mounted filesystems\n"]
        for disk in mounted_disks():
            ratio = disk.used / disk.total if disk.total else 0
            width = 30
            filled = round(ratio * width)
            bar = "#" * filled + "-" * (width - filled)
            lines.append(f"{disk.mountpoint}\n  {disk.device}  [{disk.filesystem}]\n  [{bar}] {ratio:.0%} used\n  Total {self._human_size(disk.total)}  Used {self._human_size(disk.used)}  Free {self._human_size(disk.free)}\n")
        lines.append("Largest files in current directory:\n")
        try:
            lines.extend(f"{self._human_size(size):>8}  {path}" for path, size in largest_files(current_path, 10))
        except OSError as exc:
            lines.append(f"Cannot scan directory: {exc}")
        self.call_from_thread(self._show_text, "\n".join(lines))

    def action_bookmark(self) -> None:
        try:
            bookmarked = toggle_bookmark(self.settings, self.active.path)
            self.notify("Directory bookmarked" if bookmarked else "Bookmark removed")
        except OSError as exc:
            self._error(exc)

    def action_help(self) -> None:
        self._show_text(HELP_TEXT)

    def action_back(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()
        elif self.operation_running:
            self.operation_cancel.set()
            self.notify("Cancellation requested")
        else:
            self.action_parent()

    def action_settings(self) -> None:
        self.push_screen(SettingsEditorScreen(self.settings), self._settings_result)

    def _settings_result(self, value: Settings | None) -> None:
        if value is not None:
            try:
                save_settings(value)
            except OSError as exc:
                self._error(exc)
                return
            self.settings = value
            self._apply_theme()
            self.refresh_pane(self.left)
            self.refresh_pane(self.right)
            self._update_status()
            self.notify("Settings saved")

    def _error(self, error: Exception | str) -> None:
        message = str(error)
        LOGGER.error("%s", message, exc_info=isinstance(error, Exception))
        self.notify(message, severity="error", timeout=7)
        self.query_one("#message", Static).update(f"ERROR: {message}")

    def action_quit(self) -> None:
        self.exit()


class TextScreen(ModalScreen[None]):
    CSS = """
    TextScreen { align: center middle; background: #000000 80%; }
    #text-box { width: 95%; height: 95%; border: solid #ffffff; padding: 1; background: #000000; }
    #text-content { height: 1fr; overflow: auto; }
    """
    BINDINGS = [("escape", "close", "Close"), ("q", "close", "Close")]

    def __init__(self, content: str):
        super().__init__()
        self.content = content

    def compose(self) -> ComposeResult:
        with Vertical(id="text-box"):
            yield Static(self.content, id="text-content")
            yield Label("ESC / Q: close")

    def action_close(self) -> None:
        self.dismiss(None)


class SettingsEditorScreen(ModalScreen[Settings | None]):
    CSS = """
    SettingsEditorScreen { align: center middle; background: #000000 80%; }
    #settings-box { width: 95%; height: 95%; border: solid #ffffff; padding: 1; background: #000000; }
    #settings-content { height: 1fr; }
    """
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+enter", "save", "Save", priority=True),
    ]

    def __init__(self, settings: Settings):
        super().__init__()
        self.initial = json.dumps(asdict(settings), indent=2)

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-box"):
            yield Label("Settings JSON  |  Ctrl+Enter: validate and save  |  ESC: cancel")
            yield TextArea(self.initial, id="settings-content", language="json")

    def action_save(self) -> None:
        try:
            payload = json.loads(self.query_one("#settings-content", TextArea).text)
            value = Settings(**payload)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.notify(f"Invalid settings: {exc}", severity="error", timeout=6)
            return
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)
