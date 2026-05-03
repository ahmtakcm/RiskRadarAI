#!/data/data/com.termux/files/usr/bin/bash

PROJECT_DIR="/data/data/com.termux/files/home/RiskRadarAI"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
LOG_FILE="$PROJECT_DIR/run.log"

cd "$PROJECT_DIR" || exit 1

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python bulunamadi: $PYTHON_BIN"
  exit 1
fi

pkill -f "/data/data/com.termux/files/home/RiskRadarAI/venv/bin/python main.py" 2>/dev/null
sleep 2

nohup "$PYTHON_BIN" main.py >> "$LOG_FILE" 2>&1 &
sleep 3

pgrep -af "RiskRadarAI.*main.py" || echo "RiskRadarAI sureci bulunamadi"
tail -n 15 "$LOG_FILE"
