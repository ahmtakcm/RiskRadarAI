#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${RISKRADARAI_SERVICE:-riskradarai.service}"
PROJECT_DIR="${RISKRADARAI_DIR:-/home/ahmtakcm/RiskRadarAI}"

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$SERVICE_NAME" >/dev/null 2>&1; then
  echo "===== SYSTEMD ====="
  systemctl --no-pager --full status "$SERVICE_NAME" | head -35 || true
  echo
  echo "===== SON LOG ====="
  journalctl -u "$SERVICE_NAME" -n 30 --no-pager || true
  exit 0
fi

echo "===== PROCESS ====="
pgrep -af "$PROJECT_DIR.*main.py" || echo "Calisan surec yok"

echo
echo "===== SON LOG ====="
tail -n 30 "$PROJECT_DIR/run.log" 2>/dev/null || echo "run.log okunamadi"
