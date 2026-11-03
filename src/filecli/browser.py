"""Directory listing and sorting."""

import stat
from pathlib import Path


def list_directory(path: Path, show_hidden: bool = False, sort_by: str = "name",
                   descending: bool = False) -> list[Path]:
    path = Path(path)
    entries = [item for item in path.iterdir() if show_hidden or not item.name.startswith(".")]
    if sort_by not in {"name", "size", "type", "created", "modified"}:
        raise ValueError(f"Unsupported sort field: {sort_by}")
    snapshots = []
    for item in entries:
        try:
            info = item.stat(follow_symlinks=False)
        except OSError:
            info = None
        is_directory = info is not None and stat.S_ISDIR(info.st_mode)
        snapshots.append((item, is_directory, info))

    def key(entry):
        item, _, info = entry
        if sort_by == "name":
            return item.name.casefold()
        if sort_by == "type":
            return item.suffix.casefold()
        if info is None:
            return -1
        if sort_by == "size":
            return info.st_size
        if sort_by == "created":
            return info.st_ctime
        return info.st_mtime

    directories = [entry for entry in snapshots if entry[1]]
    files = [entry for entry in snapshots if not entry[1]]
    return (
        [entry[0] for entry in sorted(directories, key=key, reverse=descending)]
        + [entry[0] for entry in sorted(files, key=key, reverse=descending)]
    )
