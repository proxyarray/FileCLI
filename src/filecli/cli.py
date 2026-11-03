"""Command-line entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .app import FileCLI
from .logging_config import configure_logging
from .settings import Settings, save_settings

cli = typer.Typer(add_completion=False, help="A dual-pane terminal file manager by MUSOS INDIA")


@cli.callback(invoke_without_command=True)
def main(
    path: Optional[Path] = typer.Argument(None, help="Directory to open"),
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
) -> None:
    if version:
        typer.echo(f"FileCLI {__version__}")
        raise typer.Exit()
    if path is not None and not path.expanduser().is_dir():
        raise typer.BadParameter(f"Not a directory: {path}")
    configure_logging()
    try:
        app = FileCLI(path.expanduser() if path else None)
    except (OSError, TypeError, ValueError) as exc:
        typer.echo(f"FileCLI cannot start: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    app.run()


@cli.command()
def init_config() -> None:
    """Create the default settings file."""
    path = save_settings(Settings())
    typer.echo(f"Created {path}")


def entrypoint() -> None:
    cli()


if __name__ == "__main__":
    entrypoint()
