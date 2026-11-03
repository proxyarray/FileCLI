from pathlib import Path
import stat
import zipfile

import pytest

from filecli.archives import create_archive, extract_archive
from filecli.fileops import OperationError
from filecli.search import search_files


def test_search_filename_extension_content_and_recursive(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "Hello.TXT").write_text("needle text")
    (tmp_path / "other.py").write_text("needle")
    assert len(search_files(tmp_path, "hello", extension=".txt")) == 1
    assert len(search_files(tmp_path, "", contains_text="needle")) == 2
    assert len(search_files(tmp_path, "hello", recursive=False)) == 0


def test_archive_create_and_extract(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("archive data")
    archive = create_archive([source], tmp_path / "files.zip")
    output = tmp_path / "out"
    extract_archive(archive, output)
    assert (output / "source.txt").read_text() == "archive data"


def test_archive_path_traversal_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("../escaped.txt", "bad")
    with pytest.raises(OperationError):
        extract_archive(archive, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()


def test_archive_conflict_is_not_overwritten(tmp_path: Path) -> None:
    archive = tmp_path / "files.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("existing.txt", "archive")
        stream.writestr("later.txt", "archive")
    output = tmp_path / "out"
    output.mkdir()
    (output / "existing.txt").write_text("keep")
    with pytest.raises(OperationError, match="overwrite"):
        extract_archive(archive, output)
    assert (output / "existing.txt").read_text() == "keep"
    assert not (output / "later.txt").exists()


def test_zip_symbolic_link_entry_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("link")
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr(info, "/etc/passwd")
    with pytest.raises(OperationError, match="symbolic link"):
        extract_archive(archive, tmp_path / "out")


def test_tar_archive_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("tar data")
    archive = create_archive([source], tmp_path / "files.tar.gz", format="tar.gz")
    output = tmp_path / "out"
    extract_archive(archive, output)
    assert (output / "source.txt").read_text() == "tar data"
