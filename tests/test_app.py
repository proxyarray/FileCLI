import pytest
from pathlib import Path

from textual.coordinate import Coordinate

from filecli.app import FileCLI, PromptScreen, SettingsEditorScreen
from filecli.widgets import extension_color, file_name_cell


async def wait_for_rows(pilot, table, count: int) -> None:
    for _ in range(50):
        if table.row_count == count:
            return
        await pilot.pause(0.1)
    pytest.fail(f"Expected {count} rows, found {table.row_count}")


@pytest.mark.asyncio
async def test_tui_keyboard_navigation_and_resize(tmp_path: Path) -> None:
    (tmp_path / "alpha.txt").write_text("a")
    (tmp_path / "beta.txt").write_text("b")
    app = FileCLI(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        table = app.query_one("#pane-left-table")
        await wait_for_rows(pilot, table, 2)
        panes = app.query_one("#panes").region
        brand = app.query_one("#brand").region
        status = app.query_one("#status").region
        info = app.query_one("#info").region
        message = app.query_one("#message").region
        shortcuts = app.query_one("#shortcuts").region
        assert brand.bottom == status.y
        assert status.bottom == panes.y
        assert panes.bottom == info.y
        assert info.bottom == message.y
        assert message.bottom == shortcuts.y
        assert shortcuts.bottom == app.size.height
        assert app.query_one("#panes").region.width == app.size.width
        cursor_style = table.get_component_rich_style("datatable--cursor")
        assert "#ffffff" in str(cursor_style) and "#000000" in str(cursor_style)
        await pilot.press("down")
        assert table.cursor_row == 1
        await pilot.press("tab")
        assert app.active.title == "Right"
        assert "active" in app.right.classes
        await pilot.resize_terminal(80, 24)
        assert app.size.width == 80
        assert app.size.height == 24
        assert app.left.display is False
        assert app.right.display is True
        await pilot.press("tab")
        assert app.left.display is True
        assert app.right.display is False
        await pilot.resize_terminal(100, 30)
        assert app.left.display is True
        assert app.right.display is True
        assert len(app.query_one("#pane-left-table").columns) == 4
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, SettingsEditorScreen)
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_shortcut_keys_do_not_escape_text_prompt(tmp_path: Path) -> None:
    app = FileCLI(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("/")
        await pilot.pause()
        assert isinstance(app.screen, PromptScreen)
        await pilot.press("tab")
        assert app.active.title == "Left"
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "Screen"


@pytest.mark.asyncio
async def test_escape_navigates_to_parent_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.setattr("filecli.app.record_recent", lambda *args, **kwargs: None)
    app = FileCLI(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app._navigate(app.left, child)
        assert app.left.path == child
        await pilot.press("escape")
        await pilot.pause()
        assert app.left.path == tmp_path


@pytest.mark.asyncio
async def test_extension_colors_and_f9_open(tmp_path: Path) -> None:
    (tmp_path / "source.py").write_text("print('safe')")
    (tmp_path / "data.txt").write_text("text")
    (tmp_path / "folder").mkdir()
    assert extension_color(tmp_path / "source.py") == "#5dade2"
    assert extension_color(tmp_path / "folder") == "#aaaaaa"
    assert extension_color(Path("picture.jpg")) == "#e056fd"
    assert file_name_cell(tmp_path / "source.py", selected=True).style == "white on #444444"
    assert file_name_cell(tmp_path / "source.py", cursor=True).style is None
    app = FileCLI(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        table = app.query_one("#pane-left-table")
        await wait_for_rows(pilot, table, 3)
        assert table.get_cell_at(Coordinate(1, 0)).style is not None
        await pilot.press("down")
        await pilot.press("f9")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "TextScreen"


@pytest.mark.asyncio
async def test_large_directory_and_single_pane_toggle(tmp_path: Path) -> None:
    for index in range(250):
        (tmp_path / f"entry-{index:03}.txt").touch()
    app = FileCLI(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await wait_for_rows(pilot, app.left.table, 250)
        await wait_for_rows(pilot, app.right.table, 250)
        assert app.right.display is False


@pytest.mark.asyncio
async def test_copy_and_move_shortcuts_between_panels(tmp_path: Path) -> None:
    source, destination = tmp_path / "source", tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "copy.txt").write_text("copy")
    (source / "move.txt").write_text("move")
    app = FileCLI(source)
    app.right.path = destination
    async with app.run_test(size=(120, 30)) as pilot:
        await wait_for_rows(pilot, app.left.table, 2)
        app.left.loading = True
        await pilot.press("f5")
        await pilot.pause(0.1)
        assert not (destination / "copy.txt").exists()
        app.left.loading = False
        await pilot.press("f5")
        await pilot.pause(0.3)
        assert (destination / "copy.txt").read_text() == "copy"
        await pilot.press("down")
        await pilot.press("f6")
        await pilot.pause(0.3)
        assert (destination / "move.txt").read_text() == "move"
        assert not (source / "move.txt").exists()
