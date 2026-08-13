#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_dir="$repo_root/python/.venv"
python3 -m venv "$venv_dir"
"$venv_dir/bin/python" -m pip install --editable "$repo_root[linux]"
printf 'Setup complete. Run ./scanBlueBoard.sh or ./runBlueBoard.sh\n'
