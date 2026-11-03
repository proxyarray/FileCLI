from pathlib import Path

import pytest

from filecli.preview import compare_files, preview_file, sha256_file
from filecli.settings import Settings, format_timestamp, load_settings, save_settings


def test_settings_persist_and_validate(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = Settings(show_hidden=True, timezone="Asia/Kolkata")
    save_settings(settings, path)
    loaded = load_settings(path)
    assert loaded.show_hidden
    assert loaded.timezone == "Asia/Kolkata"


def test_invalid_settings_are_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(timezone="Not/A_Zone")
    with pytest.raises(ValueError):
        Settings(theme="Not a theme")


def test_legacy_theme_is_migrated_to_monochrome() -> None:
    assert Settings(theme="Classic DOS Blue").theme == "Classic Monochrome"


def test_timestamp_uses_configured_timezone_and_format() -> None:
    value = format_timestamp(0, Settings())
    assert value.startswith("01-01-1970")
    assert value.endswith("IST")


def test_preview_hash_and_compare(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("safe preview")
    second.write_text("safe preview")
    assert preview_file(first) == "safe preview"
    assert compare_files(first, second)
    assert len(sha256_file(first)) == 64
