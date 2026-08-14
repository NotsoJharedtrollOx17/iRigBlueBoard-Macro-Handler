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
system_prefix="/opt/blueboard-macro-handler"
system_venv="$system_prefix/venv"
system_launcher="/usr/local/bin/blueboard"
privilege=(sudo)
[[ "${EUID:-$(id -u)}" -eq 0 ]] && privilege=()

if [[ "$skip_system" != "true" ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    packages=(bluez python3-venv python3-dev kmod)
    [[ "$scope" == "global" && "$user_install" == "true" ]] && packages+=(pipx)
    printf 'Installing Linux system prerequisites...\n'
    apt_runner=("${privilege[@]}" apt-get)
    "${apt_runner[@]}" update
    "${apt_runner[@]}" install -y "${packages[@]}"
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
elif [[ "$user_install" == "true" ]]; then
  [[ "${EUID:-$(id -u)}" -ne 0 ]] || { printf 'Global --user scope is a per-user pipx installation. Run this script as your regular user, not root.\n' >&2; exit 1; }
  command -v pipx >/dev/null 2>&1 || { printf 'pipx is required for --scope global. Install pipx with your distribution package manager, then retry.\n' >&2; exit 1; }
  pipx install --editable --force "$repo_root[linux]"
  pipx ensurepath
  printf 'Per-user global CLI installation complete. Open a new terminal, then verify with: blueboard --version\n'
else
  if [[ -e "$system_launcher" ]] && ! grep -Fq "$system_venv/bin/python" "$system_launcher"; then
    printf 'Refusing to replace existing %s because it is not managed by this installer.\n' "$system_launcher" >&2
    exit 1
  fi
  printf 'Installing a system-wide BlueBoard CLI in %s...\n' "$system_prefix"
  "${privilege[@]}" install -d -m 0755 "$system_prefix"
  if [[ ! -x "$system_venv/bin/python" ]]; then
    "${privilege[@]}" python3 -m venv "$system_venv"
  fi
  "${privilege[@]}" "$system_venv/bin/python" -m pip install --upgrade --force-reinstall "$repo_root[linux]"
  launcher_tmp="$(mktemp)"
  trap 'rm -f "$launcher_tmp"' EXIT
  {
    printf '#!/usr/bin/env bash\n'
    printf 'exec %q -m blueboard_macro_handler "$@"\n' "$system_venv/bin/python"
  } > "$launcher_tmp"
  "${privilege[@]}" install -m 0755 "$launcher_tmp" "$system_launcher"
  printf 'System-wide installation complete. Verify with: blueboard --version\n'
fi
