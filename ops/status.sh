#!/data/data/com.termux/files/usr/bin/bash

echo "===== PROCESS ====="
pgrep -af "RiskRadarAI.*main.py" || echo "Calisan surec yok"

echo
echo "===== SON LOG ====="
tail -n 20 /data/data/com.termux/files/home/RiskRadarAI/run.log 2>/dev/null || echo "run.log okunamadi"
