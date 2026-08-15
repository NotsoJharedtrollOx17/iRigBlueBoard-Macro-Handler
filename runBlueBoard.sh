#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_exe="$repo_root/python/.venv/bin/python"
config_file="$repo_root/python/config/blueboard.json"
if [[ ! -x "$python_exe" ]]; then
  printf 'Python environment not found. Run ./setupBlueBoard.sh first.\n' >&2
  exit 1
fi
execute_actions="false"
for argument in "$@"; do
  [[ "$argument" == "--execute-actions" ]] && execute_actions="true"
done
if [[ "$execute_actions" == "true" ]]; then
  current_user="$(id -un)"
  if [[ ! -c /dev/uinput ]]; then
    printf 'Keyboard actions require /dev/uinput. Run ./setupBlueBoard.sh --skip-system first.\n' >&2
    exit 1
  fi
  if ! id -nG | tr ' ' '\n' | grep -qx input; then
    printf 'Keyboard actions require the current user to belong to the input group. Run: sudo usermod -aG input "%s"; then log out and in.\n' "$current_user" >&2
    exit 1
  fi
fi
exec "$python_exe" -m blueboard_macro_handler run --config "$config_file" "$@"
