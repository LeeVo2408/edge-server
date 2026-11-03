#!/usr/bin/env bash
# FPV demo: prepare the edge server VM to relay a webcam stream to the
# Vision Pro over Tailscale (WebRTC/WHEP via MediaMTX).
#
# Run on the VM, from the edge-server repo root:
#   bash setup-edge-demo.sh
#
# What it does:
#   1. Installs Tailscale if missing and joins the tailnet as "stev-edgeserver".
#   2. Writes the MediaMTX WebRTC settings into infrastructure/.env so MediaMTX
#      advertises the Tailscale IP (otherwise the headset gets a LAN IP it
#      cannot reach and the panel stays black).
#   3. Restarts the container and checks the ports the demo needs.
set -euo pipefail

ENV_FILE="infrastructure/.env"
TS_NAME="stev-edgeserver"

if [[ ! -f docker-compose.yml ]]; then
  echo "Run this from the edge-server repo root (where docker-compose.yml is)." >&2
  exit 1
fi

# --- 1. Tailscale ---------------------------------------------------------
if ! command -v tailscale >/dev/null 2>&1; then
  echo "==> Installing Tailscale"
  curl -fsSL https://tailscale.com/install.sh | sh
fi

if ! tailscale ip -4 >/dev/null 2>&1; then
  echo "==> Joining the tailnet (open the login link it prints)"
  sudo tailscale up --hostname="$TS_NAME"
fi

TS_IP="$(tailscale ip -4 | head -n1)"
echo "==> Tailscale IP: $TS_IP  (MagicDNS name: $TS_NAME)"

# --- 2. MediaMTX WebRTC settings -----------------------------------------
[[ -f "$ENV_FILE" ]] || cp infrastructure/.env.example "$ENV_FILE"

set_env() {  # set_env KEY VALUE : replace the line if present, else append
  if grep -q "^$1=" "$ENV_FILE"; then
    sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE"
  fi
}

grep -q "FPV demo: MediaMTX WebRTC" "$ENV_FILE" || \
  printf '\n# --- FPV demo: MediaMTX WebRTC over Tailscale ---\n' >> "$ENV_FILE"
set_env MTX_WEBRTCADDITIONALHOSTS "$TS_IP"
set_env MTX_WEBRTCLOCALTCPADDRESS ":8189"
echo "==> Wrote MTX_WEBRTC* settings to $ENV_FILE"

# --- 3. Restart and check -------------------------------------------------
if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi
echo "==> Restarting the edge server ($DC)"
$DC up -d --force-recreate

sleep 5
echo "==> Listening ports (need 8554 RTSP in, 8889 WHEP, 8189 WebRTC media):"
for p in 8554 8889 8189; do
  if sudo ss -lntu | grep -q ":$p "; then echo "   OK   :$p"; else echo "   MISSING :$p"; fi
done

cat <<EOF

Edge server ready.
  Webcam laptop pushes to:  rtsp://$TS_NAME:8554/live   (or rtsp://$TS_IP:8554/live)
  Vision Pro plays from:    http://$TS_NAME:8889/live/whep
  Quick check from a laptop: open http://$TS_IP:8889/live in a browser once the
  webcam is streaming (MediaMTX's built-in WebRTC viewer page).
EOF
