# Systemd Kurulumu

Bu servis dosyasi `/home/ahmtakcm/RiskRadarAI` altinda calisan RiskRadarAI botu icindir.

## Kurulum

```bash
cd ~/RiskRadarAI
mkdir -p logs
sudo cp ops/systemd/riskradarai.service /etc/systemd/system/riskradarai.service
sudo systemctl daemon-reload
sudo systemctl enable riskradarai
sudo systemctl start riskradarai
sudo systemctl status riskradarai --no-pager
```

## Loglar

```bash
journalctl -u riskradarai -f
 tail -f ~/RiskRadarAI/logs/systemd.log
 tail -f ~/RiskRadarAI/logs/systemd.err.log
```

## Guncelleme

```bash
sudo systemctl stop riskradarai
cd ~/RiskRadarAI
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl start riskradarai
sudo systemctl status riskradarai --no-pager
```

## Notlar

- `.env` dosyasindaki `CHAT_ID` grup ID olarak kalmalidir.
- `storage/`, `logs/`, `venv/` ve `.env` GitHub'a yuklenmez.
- Eski `nohup` sureci varsa systemd baslatmadan once durdurulmalidir.
