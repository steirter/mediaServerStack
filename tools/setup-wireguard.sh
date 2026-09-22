#!/usr/bin/env bash
set -Eeuo pipefail

readonly VPN_INTERFACE="wg0"
readonly VPN_NETWORK="10.66.66.0/24"
readonly VPN_SERVER_ADDRESS="10.66.66.1/24"
readonly VPN_PORT="51820"
readonly LAN_NETWORK="192.168.0.0/24"
readonly LAN_INTERFACE="enp0s25"
readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_DIR="$(dirname -- "$SCRIPT_DIR")"
readonly OUTPUT_DIR="${WIREGUARD_OUTPUT_DIR:-$REPO_DIR/wireguard}"

endpoint="${WIREGUARD_ENDPOINT:-}"
clients=()
missing_tools=()

usage() {
    cat <<'EOF'
Usage: sudo ./tools/setup-wireguard.sh --endpoint HOST_OR_IP [--client NAME ...]

Creates a host WireGuard server and one client profile per --client argument.
The endpoint is the public IP address or DNS name clients use to reach home.
Existing /etc/wireguard/wg0.conf is never overwritten.
EOF
}

while (($#)); do
    case "$1" in
        --endpoint)
            [[ $# -ge 2 ]] || { echo "--endpoint needs a value" >&2; exit 2; }
            endpoint="$2"
            shift 2
            ;;
        --client)
            [[ $# -ge 2 ]] || { echo "--client needs a name" >&2; exit 2; }
            [[ "$2" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo "Invalid client name: $2" >&2; exit 2; }
            clients+=("$2")
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

[[ $EUID -eq 0 ]] || { echo "Run this script with sudo." >&2; exit 1; }
[[ -n "$endpoint" ]] || { echo "Provide --endpoint PUBLIC_IP_OR_DDNS_NAME." >&2; exit 2; }
((${#clients[@]} > 0)) || { echo "Provide at least one --client name." >&2; exit 2; }

if [[ -e "/etc/wireguard/${VPN_INTERFACE}.conf" ]]; then
    echo "Refusing to overwrite /etc/wireguard/${VPN_INTERFACE}.conf" >&2
    exit 1
fi

for command in wg wg-quick; do
    command -v "$command" >/dev/null || missing_tools+=("wireguard-tools")
done
command -v qrencode >/dev/null || missing_tools+=("qrencode")

if ((${#missing_tools[@]} > 0)); then
    if ! command -v apt-get >/dev/null; then
        echo "Install these packages before rerunning: ${missing_tools[*]}" >&2
        exit 1
    fi
    mapfile -t missing_tools < <(printf '%s\n' "${missing_tools[@]}" | sort -u)
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing_tools[@]}"
fi

install -d -m 700 /etc/wireguard "$OUTPUT_DIR"
umask 077

server_private_key="$(wg genkey)"
server_public_key="$(printf '%s' "$server_private_key" | wg pubkey)"
server_config="/etc/wireguard/${VPN_INTERFACE}.conf"
peer_blocks=()

for index in "${!clients[@]}"; do
    client_name="${clients[$index]}"
    client_address="10.66.66.$((index + 2))/32"
    client_private_key="$(wg genkey)"
    client_public_key="$(printf '%s' "$client_private_key" | wg pubkey)"

    cat >"$OUTPUT_DIR/${client_name}.conf" <<EOF
[Interface]
PrivateKey = ${client_private_key}
Address = ${client_address}
DNS = 192.168.0.1

[Peer]
PublicKey = ${server_public_key}
Endpoint = ${endpoint}:${VPN_PORT}
AllowedIPs = ${VPN_NETWORK}, ${LAN_NETWORK}
PersistentKeepalive = 25
EOF
    qrencode -o "$OUTPUT_DIR/${client_name}.png" <"$OUTPUT_DIR/${client_name}.conf"
    peer_blocks+=("$(cat <<EOF
[Peer]
PublicKey = ${client_public_key}
AllowedIPs = ${client_address}
EOF
)")
done

{
    printf '%s\n' '[Interface]' \
        "Address = ${VPN_SERVER_ADDRESS}" \
        "ListenPort = ${VPN_PORT}" \
        "PrivateKey = ${server_private_key}" \
        "PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -o ${LAN_INTERFACE} -j MASQUERADE" \
        "PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -s 10.66.66.0/24 -o ${LAN_INTERFACE} -j MASQUERADE"
    for peer in "${peer_blocks[@]}"; do
        printf '\n%s\n' "$peer"
    done
} >"$server_config"
chmod 600 "$server_config" "$OUTPUT_DIR"/*.conf "$OUTPUT_DIR"/*.png

printf 'net.ipv4.ip_forward = 1\n' >/etc/sysctl.d/99-wireguard-forward.conf
sysctl --load=/etc/sysctl.d/99-wireguard-forward.conf >/dev/null

if ufw status 2>/dev/null | grep -q '^Status: active'; then
    ufw allow "${VPN_PORT}/udp" comment 'WireGuard VPN'
    ufw route allow in on "$VPN_INTERFACE" to "$LAN_NETWORK" comment 'WireGuard to home LAN'
fi

systemctl enable --now "wg-quick@${VPN_INTERFACE}"

if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]]; then
    chown -R "$SUDO_USER":"$(id -gn "$SUDO_USER")" "$OUTPUT_DIR"
fi

echo "WireGuard is running on UDP ${VPN_PORT}."
echo "Client profiles and QR codes: ${OUTPUT_DIR}"