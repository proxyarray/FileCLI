from typer.testing import CliRunner

from filecli import cli as cli_module


def test_version_and_help() -> None:
    runner = CliRunner()
    version = runner.invoke(cli_module.cli, ["--version"])
    help_output = runner.invoke(cli_module.cli, ["--help"])
    assert version.exit_code == 0
    assert "FileCLI 0.2.0" in version.stdout
    assert help_output.exit_code == 0
    assert "MUSOS INDIA" in help_output.stdout


def test_startup_settings_error_is_user_friendly(monkeypatch) -> None:
    class BrokenApp:
        def __init__(self, path=None):
            raise ValueError("invalid test configuration")

    monkeypatch.setattr(cli_module, "FileCLI", BrokenApp)
    monkeypatch.setattr(cli_module, "configure_logging", lambda: None)
    result = CliRunner().invoke(cli_module.cli, [])
    assert result.exit_code == 2
    assert "FileCLI cannot start: invalid test configuration" in result.stderr
