#!/data/data/com.termux/files/usr/bin/bash

pkill -f "/data/data/com.termux/files/home/RiskRadarAI/venv/bin/python main.py" 2>/dev/null
sleep 2
pgrep -af "RiskRadarAI.*main.py" || echo "RiskRadarAI durdu"
