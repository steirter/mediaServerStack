#!/usr/bin/env bash
set -euo pipefail

if ((EUID != 0)); then
  printf 'Run this installer with sudo: sudo %s\n' "$0" >&2
  exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$script_dir/.." && pwd)
unit=docker-compose.service

if ! systemctl cat "$unit" >/dev/null 2>&1; then
  printf 'Systemd unit not found: %s\n' "$unit" >&2
  exit 1
fi

unit_working_dir=$(systemctl show --property=WorkingDirectory --value "$unit")
if [[ $unit_working_dir != "$repo_dir" ]]; then
  printf 'Unit working directory does not match this repository: %s\n' "$unit_working_dir" >&2
  exit 1
fi

drop_in_dir=/etc/systemd/system/docker-compose.service.d
install -d -m 0755 "$drop_in_dir"
printf '[Service]\nEnvironment=HOME=%s\n' "${repo_dir%/*}" >"$drop_in_dir/10-home.conf"
chmod 0644 "$drop_in_dir/10-home.conf"

systemctl daemon-reload
systemctl reset-failed "$unit"
systemctl start "$unit"
systemctl --no-pager --full status "$unit"
