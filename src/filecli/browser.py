"""Directory listing and sorting."""

from pathlib import Path


def list_directory(path: Path, show_hidden: bool = False, sort_by: str = "name",
                   descending: bool = False) -> list[Path]:
    path = Path(path)
    entries = [item for item in path.iterdir() if show_hidden or not item.name.startswith(".")]
    key_map = {
        "name": lambda item: item.name.casefold(),
        "size": lambda item: item.stat(follow_symlinks=False).st_size,
        "type": lambda item: "" if item.is_dir() else item.suffix.casefold(),
        "created": lambda item: item.stat(follow_symlinks=False).st_ctime,
        "modified": lambda item: item.stat(follow_symlinks=False).st_mtime,
    }
    if sort_by not in key_map:
        raise ValueError(f"Unsupported sort field: {sort_by}")
    directories = [item for item in entries if item.is_dir() and not item.is_symlink()]
    files = [item for item in entries if item not in directories]
    return (
        sorted(directories, key=key_map[sort_by], reverse=descending)
        + sorted(files, key=key_map[sort_by], reverse=descending)
    )
