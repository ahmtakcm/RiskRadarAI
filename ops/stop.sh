#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${RISKRADARAI_SERVICE:-riskradarai.service}"
PROJECT_DIR="${RISKRADARAI_DIR:-/home/ahmtakcm/RiskRadarAI}"

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$SERVICE_NAME" >/dev/null 2>&1; then
  sudo -n systemctl stop "$SERVICE_NAME"
  systemctl --no-pager --full status "$SERVICE_NAME" | head -25 || true
  exit 0
fi

pkill -f "$PROJECT_DIR/venv/bin/python.*main.py" 2>/dev/null || true
sleep 2
pgrep -af "$PROJECT_DIR.*main.py" || echo "RiskRadarAI durdu"
