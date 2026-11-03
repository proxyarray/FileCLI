# Troubleshooting

## Installation and launch

Use Python 3.11 or newer. Run `./install.sh`; it creates a dedicated virtual environment and a `~/.local/bin/filecli` link. If `filecli` is not found afterward, add `~/.local/bin` to `PATH`. For manual installation, create a virtual environment and install the project inside it; this also works with Linux distributions that mark system Python as externally managed.

If `python3 -m venv` is unavailable on Linux Mint, install the matching `python3-venv` package using the system package manager and retry.

## Display

The layout adapts to terminal width and height, but an 80 x 24 or larger terminal is recommended. If selection colors are hard to see, verify that the terminal supports ANSI colors and choose another configured theme.

## Access and filesystems

Permission errors are displayed as operation errors. FileCLI does not elevate privileges. Read-only mounts, remote filesystem failures, and inaccessible directories cannot be overridden by the application.

## Configuration

The normal Linux Mint configuration path is `~/.config/filecli/settings.json`. The program reports malformed JSON and invalid timezone values instead of silently resetting configuration. Back up the file before manually editing or replacing it.

## Trash

Trash uses the user's XDG data directory, normally `~/.local/share/Trash`. If moving to Trash fails (for example, because a mounted filesystem cannot be moved across devices), the error is surfaced and the source is not intentionally permanently removed.
