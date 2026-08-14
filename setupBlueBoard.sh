#!/usr/bin/env bash
set -euo pipefail
scope="venv"; user_install="false"; skip_system="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope) scope="${2:?--scope requires venv or global}"; shift 2;;
    --user) user_install="true"; shift;;
    --skip-system) skip_system="true"; shift;;
    *) printf 'Usage: %s [--scope venv|global] [--user] [--skip-system]\n' "$0" >&2; exit 2;;
  esac
done
[[ "$scope" == "venv" || "$scope" == "global" ]] || { printf 'Scope must be venv or global.\n' >&2; exit 2; }
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_dir="$repo_root/python/.venv"

if [[ "$skip_system" != "true" ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    printf 'Installing Linux system prerequisites (bluez, Python venv/build support)...\n'
    privilege=(sudo)
    [[ "${EUID:-$(id -u)}" -eq 0 ]] && privilege=()
    apt_runner=("${privilege[@]}" apt-get)
    "${apt_runner[@]}" update
    "${apt_runner[@]}" install -y bluez python3-venv python3-dev python3-pip kmod
    command -v modprobe >/dev/null 2>&1 && "${privilege[@]}" modprobe uinput || printf 'Warning: could not load uinput; configure /dev/uinput permissions manually.\n' >&2
  else
    printf 'apt-get was not found; skipping system package installation.\n' >&2
    printf 'Install BlueZ, Python venv/dev support, and uinput prerequisites using your distribution package manager.\n' >&2
  fi
fi

if [[ "$scope" == "venv" ]]; then
  python3 -m venv "$venv_dir"
  "$venv_dir/bin/python" -m pip install --editable "$repo_root[linux]"
  printf 'Setup complete. Run ./scanBlueBoard.sh or ./runBlueBoard.sh\n'
else
  install_args=(python3 -m pip install "$repo_root[linux]")
  [[ "$user_install" == "true" ]] && install_args+=(--user)
  "${install_args[@]}"
  printf 'Global installation complete. Verify with: blueboard --version\n'
fi
