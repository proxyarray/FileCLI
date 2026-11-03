"""ZIP and TAR archive inspection, creation, and safe extraction."""

from __future__ import annotations

import tarfile
import os
import stat
import tempfile
import zipfile
from pathlib import Path

from .fileops import OperationError


def archive_members(path: Path) -> list[str]:
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    if tarfile.is_tarfile(path):
        with tarfile.open(path, "r:*") as archive:
            return archive.getnames()
    raise OperationError(f"Unsupported or invalid archive: {path.name}")


def _safe_destination(root: Path, member: str) -> Path:
    root = root.resolve()
    destination = (root / member).resolve(strict=False)
    if destination != root and root not in destination.parents:
        raise OperationError(f"Archive contains an unsafe path: {member}")
    return destination


def extract_archive(path: Path, destination: Path) -> list[Path]:
    path, destination = Path(path), Path(destination)
    if destination.is_symlink():
        raise OperationError(f"Refusing to extract through a symbolic-link destination: {destination}")
    created_destination = not destination.exists()
    destination.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    directories: list[Path] = []
    created_directories: list[Path] = []
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                names: set[str] = set()
                for member in members:
                    name = member.filename.rstrip("/")
                    if name in names:
                        raise OperationError(f"Archive contains duplicate path: {name}")
                    names.add(name)
                    mode = (member.external_attr >> 16) & 0o170000
                    if mode == stat.S_IFLNK:
                        raise OperationError(f"Refusing symbolic link in archive: {name}")
                    _validate_member(destination, name)
                with tempfile.TemporaryDirectory(prefix=".filecli-extract-", dir=destination) as stage_name:
                    stage = Path(stage_name)
                    archive.extractall(stage)
                    files, directories = _commit_staged(stage, destination, created_directories)
        elif tarfile.is_tarfile(path):
            with tarfile.open(path, "r:*") as archive:
                members = archive.getmembers()
                names: set[str] = set()
                for member in members:
                    name = member.name.rstrip("/")
                    if name in names:
                        raise OperationError(f"Archive contains duplicate path: {name}")
                    names.add(name)
                    if member.issym() or member.islnk() or member.isdev():
                        raise OperationError(f"Refusing unsafe archive entry: {member.name}")
                    _validate_member(destination, name)
                with tempfile.TemporaryDirectory(prefix=".filecli-extract-", dir=destination) as stage_name:
                    stage = Path(stage_name)
                    try:
                        archive.extractall(stage, members=members, filter="data")
                    except TypeError:
                        archive.extractall(stage, members=members)
                    files, directories = _commit_staged(stage, destination, created_directories)
        else:
            raise OperationError(f"Unsupported or invalid archive: {path.name}")
        return files + directories
    except Exception:
        for item in reversed(files):
            item.unlink(missing_ok=True)
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        if created_destination:
            try:
                destination.rmdir()
            except OSError:
                pass
        raise


def _validate_member(destination: Path, name: str) -> None:
    if not name or name in {".", "./"}:
        return
    target = _safe_destination(destination, name)
    if target.exists() or target.is_symlink():
        raise OperationError(f"Extraction would overwrite: {target}")
    for parent in target.parents:
        if parent == destination:
            break
        if parent.exists() and not parent.is_dir():
            raise OperationError(f"Extraction path is not a directory: {parent}")


def _commit_staged(stage: Path, destination: Path, created_directories: list[Path]) -> tuple[list[Path], list[Path]]:
    files: list[Path] = []
    directories: list[Path] = []
    try:
        for source in sorted(stage.rglob("*"), key=lambda item: (len(item.parts), not item.is_dir())):
            relative = source.relative_to(stage)
            target = destination / relative
            if source.is_dir():
                if target.exists():
                    if not target.is_dir() or target.is_symlink():
                        raise OperationError(f"Extraction would overwrite: {target}")
                    continue
                target.mkdir()
                created_directories.append(target)
                directories.append(target)
            else:
                missing: list[Path] = []
                parent = target.parent
                while parent != destination and not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for parent in reversed(missing):
                    parent.mkdir()
                    created_directories.append(parent)
                if target.exists() or target.is_symlink():
                    raise OperationError(f"Extraction would overwrite: {target}")
                os.replace(source, target)
                files.append(target)
        return files, directories
    except Exception:
        for item in reversed(files):
            item.unlink(missing_ok=True)
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise


def create_archive(source_paths: list[Path], output: Path, *, format: str = "zip") -> Path:
    output = Path(output)
    if output.exists():
        raise OperationError(f"Archive already exists: {output}")
    try:
        if format == "zip":
            with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                for source in source_paths:
                    source = Path(source)
                    if source.is_dir():
                        for item in source.rglob("*"):
                            archive.write(item, item.relative_to(source.parent))
                    else:
                        archive.write(source, source.name)
        elif format in {"tar", "tar.gz", "tgz"}:
            mode = "w:gz" if format in {"tar.gz", "tgz"} else "w"
            with tarfile.open(output, mode) as archive:
                for source in source_paths:
                    source = Path(source)
                    archive.add(source, arcname=source.name, recursive=True)
        else:
            raise ValueError("Archive format must be zip, tar, or tar.gz")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output
