#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/moonlight-voice"
cd "$APP_DIR"

# Ensure data directory for audio uploads exists.
mkdir -p /data/moonlight-voice

echo "[moonlight-voice] Launching service from ${APP_DIR}"
echo "[moonlight-voice] Data directory: /data/moonlight-voice (contents: $(ls -A /data/moonlight-voice 2>/dev/null || true))"
echo "[moonlight-voice] Executable: python3 -m moonlight_voice"

exec python3 -m moonlight_voice
