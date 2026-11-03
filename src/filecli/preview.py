"""Non-executing file preview and metadata helpers."""

from __future__ import annotations

import hashlib
import mimetypes
import stat
from pathlib import Path

from .settings import Settings, format_timestamp

TEXT_EXTENSIONS = {".txt", ".md", ".py", ".html", ".htm", ".css", ".js", ".json", ".xml", ".csv", ".log"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".tif", ".tiff"}


def file_metadata(path: Path, settings: Settings | None = None) -> dict[str, str | int]:
    path = Path(path)
    info = path.lstat()
    return {
        "name": path.name,
        "extension": path.suffix or "(none)",
        "size": info.st_size,
        "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "modified": format_timestamp(info.st_mtime, settings or Settings()),
        "permissions": stat.filemode(info.st_mode),
        "symlink_target": str(path.readlink()) if path.is_symlink() else "",
    }


def preview_file(path: Path, *, max_bytes: int = 65536) -> str:
    path = Path(path)
    suffix = path.suffix.casefold()
    if suffix in TEXT_EXTENSIONS:
        try:
            with path.open("rb") as stream:
                return stream.read(max_bytes).decode("utf-8", errors="replace")
        except OSError as exc:
            return f"Unable to read file: {exc}"
    if suffix in IMAGE_EXTENSIONS:
        return f"Image file: {path.name}\nMIME: {mimetypes.guess_type(path.name)[0] or 'image/unknown'}\nSize: {path.stat().st_size:,} bytes"
    if suffix == ".pdf":
        try:
            with path.open("rb") as stream:
                content = stream.read(max_bytes)
            pages = content.count(b"/Type /Page")
            return f"PDF document: {path.name}\nPages detected in preview: {pages or 'unknown'}\nSize: {path.stat().st_size:,} bytes"
        except OSError as exc:
            return f"Unable to inspect PDF: {exc}"
    metadata = file_metadata(path)
    return "\n".join(f"{key.replace('_', ' ').title()}: {value}" for key, value in metadata.items() if value != "")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def compare_files(first: Path, second: Path) -> bool:
    first, second = Path(first), Path(second)
    if first.stat().st_size != second.stat().st_size:
        return False
    with first.open("rb") as left, second.open("rb") as right:
        while True:
            a, b = left.read(1024 * 1024), right.read(1024 * 1024)
            if a != b:
                return False
            if not a:
                return True
