#!/usr/bin/env sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
data_home=${XDG_DATA_HOME:-"$HOME/.local/share"}
venv="$data_home/filecli/venv"
entry="$HOME/.local/bin/filecli"

python3 -m venv "$venv"
"$venv/bin/python" -m pip install "$project_dir"
mkdir -p "$HOME/.local/bin"
if [ -e "$entry" ] || [ -L "$entry" ]; then
    if [ "$(readlink "$entry")" != "$venv/bin/filecli" ]; then
        printf 'Refusing to overwrite existing %s\n' "$entry" >&2
        exit 1
    fi
else
    ln -s "$venv/bin/filecli" "$entry"
fi

printf '\nFileCLI installed. Run: filecli\n'
printf 'If needed, add %s to PATH.\n' "$HOME/.local/bin"
