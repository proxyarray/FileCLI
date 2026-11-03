"""Directory search and deterministic sorting."""

from __future__ import annotations

from pathlib import Path


def search_files(root: Path, query: str = "", *, extension: str | None = None,
                 file_type: str | None = None, contains_text: str | None = None,
                 recursive: bool = True, case_sensitive: bool = False) -> list[Path]:
    root = Path(root)
    candidates = root.rglob("*") if recursive else root.iterdir()
    needle = query if case_sensitive else query.casefold()
    results: list[Path] = []
    for path in candidates:
        try:
            if path.is_symlink():
                continue
            name = path.name if case_sensitive else path.name.casefold()
            if needle not in name:
                continue
            if extension and path.suffix.casefold() != extension.casefold():
                continue
            if file_type == "directory" and not path.is_dir():
                continue
            if file_type == "file" and not path.is_file():
                continue
            if contains_text is not None:
                if not path.is_file():
                    continue
                with path.open("r", encoding="utf-8", errors="replace") as stream:
                    content = stream.read(1024 * 1024)
                haystack = content if case_sensitive else content.casefold()
                sought = contains_text if case_sensitive else contains_text.casefold()
                if sought not in haystack:
                    continue
            results.append(path)
        except (OSError, PermissionError):
            continue
    return sorted(results, key=lambda item: str(item).casefold())

