#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$script_dir/.." && pwd)

if (($# > 1)); then
  printf 'Usage: %s [username]\n' "${0##*/}" >&2
  exit 2
fi

username=${1:-}
if [[ -z $username ]]; then
  read -r -p 'Linux username for the /home/<username> data paths: ' username
fi

if [[ ! $username =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  printf 'Invalid Linux username: %s\n' "$username" >&2
  exit 2
fi

host_home=/home/$username
if [[ ! -d $host_home ]]; then
  printf 'Home directory does not exist: %s\n' "$host_home" >&2
  exit 1
fi

printf 'Starting the stack with HOME=%s\n' "$host_home"
HOME=$host_home docker compose -f "$repo_dir/docker-compose.yml" config >/dev/null
HOME=$host_home docker compose -f "$repo_dir/docker-compose.yml" up -d "$@"