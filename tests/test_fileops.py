from pathlib import Path
import threading

import pytest

from filecli.fileops import (
    ConflictError, OperationError, copy_path, create_directory, create_file,
    directory_size, list_directory, move_path, remove_path, rename, set_permissions,
    Progress, trash_path,
)


def test_create_rename_copy_move_and_delete(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    create_directory(source)
    create_directory(destination)
    file = create_file(source / "one.txt")
    file.write_text("data")
    renamed = rename(file, "two.txt")
    assert renamed.name == "two.txt"
    copied = copy_path(renamed, destination / "two.txt")
    assert copied.read_text() == "data"
    moved = move_path(copied, destination / "moved.txt")
    assert moved.exists()
    remove_path(moved, permanent=True)
    assert not moved.exists()


def test_conflict_never_overwrites_implicitly(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.write_text("new")
    target.write_text("old")
    with pytest.raises(ConflictError):
        copy_path(source, target)
    assert target.read_text() == "old"


def test_symlink_not_followed_for_copy_or_delete(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "valuable").write_text("kept")
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    copied = copy_path(link, tmp_path / "copied-link")
    assert copied.is_symlink()
    remove_path(link, permanent=True)
    assert (target / "valuable").exists()


def test_hidden_files_and_sort(tmp_path: Path) -> None:
    (tmp_path / ".hidden").touch()
    (tmp_path / "b").touch()
    (tmp_path / "a").mkdir()
    assert [item.name for item in list_directory(tmp_path)] == ["a", "b"]
    assert {item.name for item in list_directory(tmp_path, show_hidden=True)} == {".hidden", "a", "b"}


def test_protected_delete_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    with pytest.raises(OperationError):
        remove_path(home, permanent=True)


def test_cancelled_overwrite_preserves_original(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.write_bytes(b"replacement")
    target.write_bytes(b"original")
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(OperationError, match="cancelled"):
        copy_path(source, target, overwrite=True, progress=Progress(cancel_event=cancel))
    assert target.read_bytes() == b"original"
    assert sorted(item.name for item in tmp_path.iterdir()) == ["source", "target"]


def test_confirmed_overwrite_replaces_atomically(tmp_path: Path) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    source.write_text("new")
    target.write_text("old")
    copy_path(source, target, overwrite=True)
    assert target.read_text() == "new"
    assert source.read_text() == "new"


def test_copy_directory_into_itself_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(OperationError, match="itself"):
        copy_path(source, source / "nested")


def test_directory_copy_preserves_symlink_without_following(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "valuable").write_text("kept")
    source = tmp_path / "source"
    source.mkdir()
    (source / "link").symlink_to(target, target_is_directory=True)
    copied = copy_path(source, tmp_path / "copy")
    assert (copied / "link").is_symlink()
    assert copied.joinpath("link").readlink() == target
    assert (target / "valuable").read_text() == "kept"


def test_trash_uses_xdg_directory_and_directory_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    target = tmp_path / "target.txt"
    target.write_bytes(b"12345")
    assert directory_size(target) == 5
    trashed = trash_path(target)
    assert not target.exists()
    assert trashed.read_bytes() == b"12345"
    assert (tmp_path / "data" / "Trash" / "info" / f"{trashed.name}.trashinfo").exists()


def test_permission_editing(tmp_path: Path) -> None:
    target = tmp_path / "mode.txt"
    target.touch()
    set_permissions(target, 0o640)
    assert target.stat().st_mode & 0o777 == 0o640
