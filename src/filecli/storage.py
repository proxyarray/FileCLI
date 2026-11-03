"""Mounted filesystem and large-file information using Linux system interfaces."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import NamedTuple


class DiskInfo(NamedTuple):
    device: str
    filesystem: str
    mountpoint: str
    total: int
    used: int
    free: int


def mounted_disks() -> list[DiskInfo]:
    mounts: dict[str, tuple[str, str]] = {}
    try:
        with Path("/proc/self/mounts").open(encoding="utf-8") as stream:
            for line in stream:
                parts = line.split()
                if len(parts) >= 3:
                    device, mountpoint, filesystem = parts[:3]
                    mounts[mountpoint.replace("\\040", " ")] = (device, filesystem)
    except OSError:
        mounts[str(Path.home())] = ("unknown", "unknown")
    result: list[DiskInfo] = []
    for mountpoint, (device, filesystem) in mounts.items():
        try:
            usage = shutil.disk_usage(mountpoint)
            if usage.total:
                result.append(DiskInfo(device, filesystem, mountpoint, usage.total, usage.used, usage.free))
        except OSError:
            continue
    return result


def largest_files(root: Path, limit: int = 20) -> list[tuple[Path, int]]:
    found: list[tuple[Path, int]] = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            try:
                if not path.is_symlink():
                    found.append((path, path.stat().st_size))
            except OSError:
                continue
    return sorted(found, key=lambda item: item[1], reverse=True)[:limit]

