#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_exe="$repo_root/python/.venv/bin/python"
config_file="$repo_root/python/config/blueboard.json"
if [[ ! -x "$python_exe" ]]; then
  printf 'Python environment not found. Run ./setupBlueBoard.sh first.\n' >&2
  exit 1
fi
exec "$python_exe" -m blueboard_macro_handler scan --config "$config_file" "$@"
