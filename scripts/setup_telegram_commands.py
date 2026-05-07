import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".env"))

token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
if not token:
    raise SystemExit("BOT_TOKEN bulunamadı")

commands = [
    {"command": "kaynak_test_url", "description": "URL test et"},
    {"command": "kaynak_test", "description": "Kaynak test et"},
    {"command": "kaynak_sil", "description": "Kaynak sil"},
    {"command": "kaynak_ekle", "description": "Yeni kaynak ekle"},
    {"command": "kaynak_liste", "description": "Kaynakları listele"},
    {"command": "kaynak", "description": "Kaynak komutları"},
    {"command": "profil_liste", "description": "Profil listesini göster"},
    {"command": "profil_durum", "description": "Aktif profilleri göster"},
    {"command": "profil_tum", "description": "Tüm kaynaklar"},
    {"command": "profil_resmi", "description": "Kritik resmi açıklamalar"},
    {"command": "profil_haber", "description": "Global haber akışı"},
    {"command": "profil_ekonomi", "description": "Ekonomi/merkez bankası"},
    {"command": "profil_osint", "description": "OSINT ve lider kaynakları"},
    {"command": "profil_saglik", "description": "Sağlık kaynakları"},
    {"command": "profiles", "description": "Profil listesini göster"},
    {"command": "profile_status", "description": "Profil durumunu göster"},
    {"command": "profile_on", "description": "Profil aç: profile_on <id>"},
    {"command": "profile_off", "description": "Profil kapat: profile_off <id>"},
    {"command": "profile_policy", "description": "Profil policy: profile_policy <id>"},
    {"command": "profile_sources", "description": "Profil kaynakları: profile_sources <id>"},
    {"command": "alarm_on", "description": "Alarm aç: alarm_on <id>"},
    {"command": "alarm_off", "description": "Alarm kapat: alarm_off <id>"},
    {"command": "digest_on", "description": "Digest aç: digest_on <id>"},
    {"command": "digest_off", "description": "Digest kapat: digest_off <id>"},
    {"command": "alarm_esik", "description": "Alarm eşiği: alarm_esik <id> <sayı>"},
    {"command": "ara", "description": "Manuel arama: ara <profil?> <sorgu>"},
    {"command": "tara", "description": "Manuel tarama: tara <profil?> <24s|24h|sorgu>"},
    {"command": "watch_liste", "description": "Manuel takip listesi"},
    {"command": "watch_ekle", "description": "Manuel takip ekle"},
    {"command": "watch_sil", "description": "Manuel takip sil"},
    {"command": "feed_kontrol", "description": "Feed log/hata kontrolü"},
    {"command": "profil", "description": "Yardım"},
    {"command": "audit", "description": "Bildirim audit"},
    {"command": "health", "description": "Sağlık durumu"},
    {"command": "source_health", "description": "Kaynak sağlık raporu"},
]

r = requests.post(
    f"https://api.telegram.org/bot{token}/setMyCommands",
    json={"commands": commands},
    timeout=20,
)
print("STATUS:", r.status_code)
print("BODY:", r.text)
