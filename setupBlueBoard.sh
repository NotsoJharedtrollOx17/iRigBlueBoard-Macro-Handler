#!/usr/bin/env bash
set -euo pipefail
scope="venv"; user_install="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope) scope="${2:?--scope requires venv or global}"; shift 2;;
    --user) user_install="true"; shift;;
    *) printf 'Usage: %s [--scope venv|global] [--user]\n' "$0" >&2; exit 2;;
  esac
done
[[ "$scope" == "venv" || "$scope" == "global" ]] || { printf 'Scope must be venv or global.\n' >&2; exit 2; }
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
venv_dir="$repo_root/python/.venv"
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
