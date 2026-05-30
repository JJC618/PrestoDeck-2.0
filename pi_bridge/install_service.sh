#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE="/etc/systemd/system/presto-spotify-bridge.service"

sed "s#WorkingDirectory=/home/admin/PrestoDeck#WorkingDirectory=${PROJECT_DIR}#; s#ExecStart=/usr/bin/python3 /home/admin/PrestoDeck/pi_bridge/spotify_bridge.py#ExecStart=/usr/bin/python3 ${PROJECT_DIR}/pi_bridge/spotify_bridge.py#" \
  "${PROJECT_DIR}/pi_bridge/presto-spotify-bridge.service" | sudo tee "${SERVICE_FILE}" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable presto-spotify-bridge
sudo systemctl restart presto-spotify-bridge
sudo systemctl status presto-spotify-bridge --no-pager
