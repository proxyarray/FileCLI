"""Safe filesystem operations used by both the UI and tests."""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from .browser import list_directory
from .errors import ConflictError, OperationError


@dataclass
class Progress:
    completed_bytes: int = 0
    total_bytes: int = 0
    current_path: str = ""
    cancelled: bool = False
    cancel_event: threading.Event | None = None
    on_update: Callable[[Progress], None] | None = None

    def check_cancelled(self) -> None:
        if self.cancelled or (self.cancel_event and self.cancel_event.is_set()):
            raise OperationError("Operation cancelled")


def create_file(path: Path) -> Path:
    path = Path(path)
    path.touch(exist_ok=False)
    return path


def create_directory(path: Path) -> Path:
    path = Path(path)
    path.mkdir(parents=False, exist_ok=False)
    return path


def rename(source: Path, new_name: str) -> Path:
    if not new_name or new_name in {".", ".."} or Path(new_name).name != new_name:
        raise OperationError("Enter a valid filename without a directory path")
    source = Path(source)
    destination = source.with_name(new_name)
    if destination.exists() or destination.is_symlink():
        raise ConflictError(f"Destination already exists: {destination.name}")
    return source.rename(destination)


def _tree_size(path: Path) -> int:
    if path.is_symlink() or not path.is_dir():
        return path.lstat().st_size
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
        total += sum((Path(root) / name).lstat().st_size for name in files)
    return total


def _copy_file(source: Path, destination: Path, progress: Progress) -> str:
    progress.check_cancelled()
    progress.current_path = str(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("xb") as writer:
        while chunk := reader.read(1024 * 1024):
            progress.check_cancelled()
            writer.write(chunk)
            progress.completed_bytes += len(chunk)
            if progress.on_update:
                progress.on_update(progress)
    shutil.copystat(source, destination, follow_symlinks=False)
    return str(destination)


def _copy_new(source: Path, destination: Path, progress: Progress) -> None:
    if source.is_dir() and not source.is_symlink():
        try:
            shutil.copytree(
                source, destination, symlinks=True,
                copy_function=lambda src, dst: _copy_file(Path(src), Path(dst), progress),
            )
            shutil.copystat(source, destination, follow_symlinks=False)
        except Exception:
            if destination.exists():
                remove_path(destination, permanent=True)
            raise
    elif source.is_symlink():
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(os.readlink(source), destination)
    else:
        progress.total_bytes = progress.total_bytes or source.stat().st_size
        try:
            _copy_file(source, destination, progress)
        except Exception:
            destination.unlink(missing_ok=True)
            raise


def copy_path(source: Path, destination: Path, *, progress: Progress | None = None,
              overwrite: bool = False) -> Path:
    source, destination = Path(source), Path(destination)
    progress = progress or Progress()
    if not source.exists() and not source.is_symlink():
        raise OperationError(f"Source does not exist: {source}")
    if source.resolve(strict=False) == destination.resolve(strict=False):
        raise OperationError("Source and destination are the same")
    if source.is_dir() and not source.is_symlink() and source.resolve() in destination.resolve(strict=False).parents:
        raise OperationError("Cannot copy a directory into itself")
    exists = destination.exists() or destination.is_symlink()
    if exists and not overwrite:
        raise ConflictError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if exists and _protected(destination):
        raise OperationError(f"Refusing to overwrite protected path: {destination}")
    staging = Path(tempfile.mkdtemp(prefix=".filecli-copy-", dir=destination.parent)) if exists else None
    staged_destination = staging / destination.name if staging else destination
    try:
        if source.is_file() and not source.is_symlink():
            progress.total_bytes = progress.total_bytes or source.stat().st_size
        _copy_new(source, staged_destination, progress)
        if exists:
            assert staging is not None
            backup = staging / ".filecli-original"
            os.replace(destination, backup)
            try:
                os.replace(staged_destination, destination)
            except Exception:
                os.replace(backup, destination)
                raise
            remove_path(backup, permanent=True)
        return destination
    finally:
        if staging and staging.exists():
            shutil.rmtree(staging)


def move_path(source: Path, destination: Path, *, progress: Progress | None = None,
              overwrite: bool = False) -> Path:
    source, destination = Path(source), Path(destination)
    if source.resolve(strict=False) == destination.resolve(strict=False):
        raise OperationError("Source and destination are the same")
    if source.is_dir() and not source.is_symlink() and source.resolve() in destination.resolve(strict=False).parents:
        raise OperationError("Cannot move a directory into itself")
    exists = destination.exists() or destination.is_symlink()
    if exists:
        if not overwrite:
            raise ConflictError(f"Destination already exists: {destination}")
        if _protected(destination):
            raise OperationError(f"Refusing to overwrite protected path: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup_dir = Path(tempfile.mkdtemp(prefix=".filecli-move-", dir=destination.parent)) if exists else None
    backup = backup_dir / "previous" if backup_dir else None
    if backup is not None:
        os.replace(destination, backup)
    try:
        progress = progress or Progress()
        if source.lstat().st_dev == destination.parent.stat().st_dev:
            os.replace(source, destination)
        else:
            copy_path(source, destination, progress=progress)
            remove_path(source, permanent=True)
    except Exception as exc:
        if destination.exists() or destination.is_symlink():
            remove_path(destination, permanent=True)
        if backup is not None and (backup.exists() or backup.is_symlink()):
            os.replace(backup, destination)
        if isinstance(exc, OperationError):
            raise
        raise OperationError(f"Cannot move {source}: {exc}") from exc
    else:
        if backup is not None:
            remove_path(backup, permanent=True)
    finally:
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)
    return destination


def _protected(path: Path) -> bool:
    resolved = path.resolve(strict=False)
    home = Path.home().resolve()
    protected = {
        Path("/"), Path("/etc"), Path("/usr"), Path("/var"), Path("/boot"),
        Path("/root"), Path("/mnt"), Path("/media"), Path("/opt"), Path("/srv"),
    }
    return resolved in protected or resolved in home.parents or resolved == home


def trash_path(path: Path) -> Path:
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        raise OperationError(f"Path does not exist: {path}")
    if _protected(path):
        raise OperationError(f"Refusing to delete protected directory: {path}")
    trash = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "Trash"
    files_dir, info_dir = trash / "files", trash / "info"
    files_dir.mkdir(parents=True, exist_ok=True)
    info_dir.mkdir(parents=True, exist_ok=True)
    name = path.name
    candidate = files_dir / name
    counter = 1
    while candidate.exists() or candidate.is_symlink():
        candidate = files_dir / f"{name}.{counter}"
        counter += 1
    info = info_dir / f"{candidate.name}.trashinfo"
    payload = "[Trash Info]\nPath=" + quote(str(path.absolute()), safe="/") + \
        "\nDeletionDate=" + datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S") + "\n"
    temporary = info.with_suffix(".tmp")
    temporary.write_text(payload, encoding="utf-8")
    try:
        shutil.move(str(path), str(candidate))
        temporary.replace(info)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return candidate


def remove_path(path: Path, *, permanent: bool = False) -> Path:
    path = Path(path)
    if not path.exists() and not path.is_symlink():
        raise OperationError(f"Path does not exist: {path}")
    if _protected(path):
        raise OperationError(f"Refusing to delete protected directory: {path}")
    if not permanent:
        return trash_path(path)
    if path.is_symlink() or not path.is_dir():
        path.unlink()
    else:
        shutil.rmtree(path)
    return path


def directory_size(path: Path) -> int:
    return _tree_size(Path(path))


def set_permissions(path: Path, mode: int) -> None:
    if mode < 0 or mode > 0o7777:
        raise ValueError("Permissions must be an octal mode between 0000 and 7777")
    Path(path).chmod(mode, follow_symlinks=False)


def batch_rename(paths: list[Path], pattern: str, replacement: str) -> list[Path]:
    planned = [(Path(path), Path(path).with_name(Path(path).name.replace(pattern, replacement))) for path in paths]
    destinations = [destination for _, destination in planned]
    if len(set(destinations)) != len(destinations):
        raise ConflictError("Batch rename would create duplicate filenames")
    for source, destination in planned:
        if destination != source and (destination.exists() or destination.is_symlink()):
            raise ConflictError(f"Destination already exists: {destination.name}")
    completed: list[tuple[Path, Path]] = []
    try:
        for source, destination in planned:
            if source != destination:
                source.rename(destination)
                completed.append((source, destination))
    except Exception:
        for source, destination in reversed(completed):
            destination.rename(source)
        raise
    return [destination for _, destination in planned]
