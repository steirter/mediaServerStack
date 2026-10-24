#!/usr/bin/env bash
set -euo pipefail

if ((EUID != 0)); then
  printf 'Run this installer with sudo: sudo %s\n' "$0" >&2
  exit 1
fi

if [[ -z ${SUDO_USER:-} || $SUDO_USER == root ]]; then
  printf 'Run this with sudo from the Linux user that should run the service.\n' >&2
  exit 1
fi

if ! getent passwd "$SUDO_USER" >/dev/null; then
  printf 'Could not find the invoking user: %s\n' "$SUDO_USER" >&2
  exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
service_instance=$(systemd-escape --template=trickplaycheck-web@.service "$SUDO_USER")

install -d -o root -g root -m 0755 /usr/local/lib/trickplaycheck
install -o root -g root -m 0644 \
  "$script_dir/trickplaycheck-web.py" \
  /usr/local/lib/trickplaycheck/trickplaycheck-web.py
install -o root -g root -m 0644 \
  "$script_dir/check-trickplay-progress.sh" \
  /usr/local/lib/trickplaycheck/check-trickplay-progress.sh
install -o root -g root -m 0644 \
  "$script_dir/trickplaycheck-web@.service" \
  /etc/systemd/system/trickplaycheck-web@.service

systemctl daemon-reload
systemctl enable --now "$service_instance"

printf 'Installed and started %s\n' "$service_instance"
printf 'Open http://SERVER_IP:8765 from a device on your local network.\n'
systemctl --no-pager status "$service_instance"
