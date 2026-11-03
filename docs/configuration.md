# User configuration

The settings file is JSON at the path returned by `platformdirs` for the `filecli` application. On Linux Mint this is normally `~/.config/filecli/settings.json`.

The complete supported settings structure is shown in [`../config.example.json`](../config.example.json). Omitted fields use defaults. The program validates theme, sort field, and IANA timezone values during load.

| Setting | Meaning |
|---|---|
| `theme` | One of the five themes listed in the README; `Classic DOS Blue` is migrated to `Classic Monochrome` |
| `show_hidden` | Include dotfiles in listings |
| `start_directory` | Initial path; defaults to the current user's home |
| `sort_by` / `sort_descending` | Name, size, type, created, or modified |
| `preview_enabled` | Preview files rather than attempting to launch them |
| `confirm_delete` | Keep the delete confirmation prompt |
| `timezone` | IANA timezone identifier; default `Asia/Kolkata` |
| `date_format` | Python `strftime` date format; default `%d-%m-%Y` |
| `clock_24h` | Use a 24-hour clock |
| `relative_dates` | Reserved preference for relative timestamp display |
| `calculate_directory_sizes` | Calculate directory totals when enabled by an interface workflow |
| `use_trash` | Move deletions to XDG Trash rather than unlinking permanently |
| `bookmarks` | List of bookmarked directory paths |
| `recent_directories` / `recent_files` | Recently visited paths |

File timestamps are converted at display time; the stored filesystem timestamps are not modified.
