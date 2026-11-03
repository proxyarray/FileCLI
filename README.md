# FileCLI

FileCLI by MUSOS INDIA is a keyboard-driven, dual-pane terminal file manager for Linux. The interface uses a black background, white active-panel border and selection, restrained extension colors, aligned file columns, and a persistent function-key toolbar. Files are previewed as data; FileCLI never executes a file on preview.

## Requirements and installation

- Python 3.11 or newer
- Linux terminal with a practical minimum size of 80 x 24
- Python virtual-environment support (`python3-venv` on Debian-based systems)

Install from a checkout:

```sh
./install.sh
```

The installer uses a dedicated virtual environment and adds a `~/.local/bin/filecli` link without replacing an unrelated existing file. Launch with `filecli`, open a folder with `filecli ~/Documents`, or inspect options with `filecli --help` and `filecli --version`.

For development:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pytest
```

## Keyboard controls

| Key | Action |
|---|---|
| Up / Down | Move selection |
| Left / Backspace | Parent directory |
| Right / Enter | Open directory or preview file |
| Tab | Switch panes |
| Space / Ctrl+A | Select item / select all |
| F1 | Help |
| F2 / F3 / F4 | Rename / preview / edit text file |
| F5 / F6 | Copy / move selected items to the other pane |
| F7 / F8 | Create directory / delete with confirmation |
| F9 / F10 | Open selected item / exit |
| `/` / `G` | Recursive filename search / go to path |
| `H` / `R` / `N` | Toggle hidden files / refresh / create file |
| `B` / `D` / `S` | Toggle bookmark / storage information / cycle sorting |
| `C` / `X` / `T` / `Z` / `U` | Compare / swap panes / edit settings / create ZIP / extract archive |
| Esc | Back/close a dialog, go to parent, or cancel an active file operation |

## Safety and file operations

Delete asks for confirmation and moves items to the XDG Trash by default. Change `use_trash` to `false` in settings to use permanent deletion (the UI still confirms). The filesystem layer rejects deleting the filesystem root, home directory, and key system directories. Copy/move conflicts are never overwritten without an explicit confirmation. Recursive directory copies preserve symbolic links instead of following them. Archive extraction rejects path traversal, links, device entries, and existing destinations. File edit writes a temporary sibling before replacement.

Copy, move, large-file scans, previews, and search use bounded chunks or background workers where appropriate. Search skips symbolic links and unreadable entries. File operations never invoke a shell.

## Configuration

Settings are stored at `~/.config/filecli/settings.json` (or the platformdirs equivalent). `filecli init-config` writes a default file. For a documented example and options, see [docs/configuration.md](docs/configuration.md) and [config.example.json](config.example.json). Defaults: black-and-white Classic Monochrome theme, white-on-black selection, hidden files off, `Asia/Kolkata`, `DD-MM-YYYY`, 24-hour time, and Trash enabled.

Available configurable themes: Classic Monochrome (the black-and-white default), Amber Terminal, Monochrome, Green Terminal, and Light Terminal. Press `T` to edit the JSON settings in the application; `Ctrl+Enter` validates and saves, while `Esc` cancels. The default interface uses tasteful extension colors for filenames, overridden by the white-on-black active selection. Unknown keys are ignored and invalid timezone/theme/sort values produce an explicit configuration error.

At terminal widths below 88 columns, FileCLI switches to one visible pane; `TAB` changes which directory is shown. Between 88 and 111 columns, it keeps both panes with compact information fields. Resizing reflows the panels and toolbar.

## Current feature scope

The package provides dual-pane browsing, safe basic file operations, recursive filename/extension search, sorting, text/image/PDF/metadata previews, disk and largest-file information, ZIP/TAR archive listing/creation/extraction, bookmarks/recent directories, SHA-256 and file comparison helpers, batch rename, permission helpers, and persistent settings/date formatting. The TUI exposes core navigation, copy/move/delete, text editing, previews, basic search, ZIP create/extract, disk information, and JSON settings editing. The helper APIs for batch rename, permission changes, SHA-256, and binary comparison are not yet surfaced in the TUI; neither are keyboard remapping, a navigable virtual archive filesystem, in-place image/PDF rendering, or content-search filters.

## Troubleshooting

- **`filecli: command not found`:** ensure the Python user scripts directory is on `PATH`, or run `python3 -m filecli`.
- **No color / unreadable colors:** use a true-color terminal and check the terminal's background setting; the interface uses standard Textual/Rich styling.
- **Permission denied:** FileCLI reports the underlying filesystem error. It does not request or invoke `sudo`; check directory ownership and mount permissions.
- **Timezone unavailable:** install the system `tzdata` package, or set `timezone` to an installed IANA timezone.
- **Terminal too small:** increase the terminal dimensions before launching.
- **Configuration won't load:** inspect the JSON at the path above; remove malformed JSON or run `filecli init-config` only after preserving any desired settings.
