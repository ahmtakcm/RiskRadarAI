#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${RISKRADARAI_SERVICE:-riskradarai.service}"
PROJECT_DIR="${RISKRADARAI_DIR:-/home/ahmtakcm/RiskRadarAI}"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
LOG_FILE="$PROJECT_DIR/run.log"

cd "$PROJECT_DIR"

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$SERVICE_NAME" >/dev/null 2>&1; then
  sudo -n systemctl restart "$SERVICE_NAME"
  systemctl --no-pager --full status "$SERVICE_NAME" | head -30
  exit 0
fi

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python bulunamadi: $PYTHON_BIN"
  exit 1
fi

pkill -f "$PROJECT_DIR/venv/bin/python.*main.py" 2>/dev/null || true
sleep 2
nohup "$PYTHON_BIN" -u main.py >> "$LOG_FILE" 2>&1 &
sleep 3
pgrep -af "$PROJECT_DIR.*main.py" || echo "RiskRadarAI sureci bulunamadi"
tail -n 20 "$LOG_FILE" 2>/dev/null || true
