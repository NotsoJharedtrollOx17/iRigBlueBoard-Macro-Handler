#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
printf 'Checking for uncommitted changes before updating...\n'
if [[ -n "$(git -C "$repo_root" status --porcelain)" ]]; then
  printf 'Update stopped: commit or stash local changes before running this script.\n' >&2
  exit 1
fi

printf 'Updating the local main branch from origin/main...\n'
git -C "$repo_root" fetch origin main
if git -C "$repo_root" show-ref --verify --quiet refs/heads/main; then
  git -C "$repo_root" switch main
else
  git -C "$repo_root" switch --track -c main origin/main
fi
git -C "$repo_root" pull --ff-only origin main
printf 'Refreshing the selected installation...\n'
exec "$repo_root/setupBlueBoard.sh" "$@"
