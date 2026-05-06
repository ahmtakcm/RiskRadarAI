# RiskRadarAI Engineering Rules

Bu dokuman RiskRadarAI icin teknik karar sozlesmesidir. Genel yazilim prensiplerini bu projenin gercek risklerine cevirir: kaynaklar kirilir, relay kullanimi gerekebilir, alarm kalitesi guven ister ve runtime durum GitHub'a karismamalidir.

## Altin Kurallar

### 1. Alarm guveni hizdan once gelir
RiskRadarAI erken sinyal uretir, ama kesinlik iddiasi tasiyan mesajlar daha yuksek kanit ister. Sosyal, OSINT ve relay kaynaklari hiz katmanidir; resmi kaynak veya guvenilir ikinci sinyal yoksa mesaj dili bunu acikca yansitmalidir.

### 2. Kaynak erisimi kirilgan kabul edilir
403, Cloudflare, DNS, timeout ve RSS bozulmasi normal operasyon senaryosudur. Bir kaynak bozuldugunda bot cokmemeli; kaynak sagligi kaydedilmeli, cooldown uygulanmali ve mumkunse yedek/relay kaynak devreye girmelidir.

### 3. Relay kaynaklar seffaf etiketlenir
Dogru kaynak ama dolayli kanal kullanan her feed `source_class`, `source_family`, `access_risk`, `notes` ve gerekiyorsa `account` alanlariyla aciklanmalidir. Relay hicbir zaman sessizce resmi kaynak gibi gosterilmemelidir.

### 4. Konfigurasyon veri, kod karar noktasi olsun
Yeni feed, profil, kural ve routing tercihleri mumkun oldugunca `rules/` ve `profiles/` altinda tutulmalidir. Kod sadece tekrarlanan davranisi tasimalidir; tekil kaynak bilgisi kodun icine gomulmemelidir.

### 5. Runtime state GitHub'a girmez
`.env`, `venv/`, `logs/`, `storage/`, runtime backup'lari ve `user_inputs/` icindeki anlik durum commit disinda kalmalidir. GitHub'a sadece tekrar kurulabilir kod, kural ve dokumantasyon gitmelidir.

### 6. Her parser dar ve test edilebilir olur
Ozel parser sadece hedef sayfa ailesinin yapisini bilmeli, genel link parser'in yerine gecmemelidir. Parser degisikliginde en az bir hedefli smoke test calistirilir ve beklenen item sayisi/ornek baslik kontrol edilir.

### 7. Hata yutulmaz, degrade edilir
Beklenen dis dunya hatalari loglanir ve kaynak bazinda izlenir. Beklenmeyen kod hatalari gizlenmez; servis crash ediyorsa sebep bulunur. Operasyonel hata ile yazilim hatasi loglarda ayirt edilebilir olmalidir.

### 8. Guvenlik varsayilan ayardir
API key, Telegram token, chat ID ve hesap bilgileri sadece `.env` veya guvenli runtime ortaminda tutulur. Loglar credential basmaz. Yeni entegrasyonlarda minimum yetki ve token rotasyonu dusunulur.

### 9. Systemd tek gercek calisma yolu kabul edilir
Ubuntu sunucuda servis yonetimi `riskradarai.service` uzerinden yapilir. `ops/start.sh`, `ops/stop.sh`, `ops/status.sh` systemd ile uyumlu kalir; eski Termux/nohup yollarina geri donulmez.

### 10. Test piramidi pragmatik tutulur
Her degisiklik icin en az ilgili smoke test calisir. Paylasilan fetcher/parser/filter davranisi degisirse unit test veya fixture testi eklenir. Uzak kaynaklara bagimli testler kisa, hedefli ve hata nedeni okunur olmalidir.

### 11. AI ciktisi denetlenmis katmandir
AI saglayicilari haber secimini destekler; tek basina dogruluk otoritesi degildir. AI hatasi, kota dolumu veya provider kesintisi botu durdurmamalidir. Kural tabanli fallback davranisi korunur.

### 12. Git akisi kucuk ve geri alinabilir olur
Her commit tek bir amaca hizmet etmelidir. Runtime dosyalari stage edilmez. Degisiklikten sonra `git status -sb`, hedefli test ve servis durumu kontrol edilir. Push edilen commit mesaji neyin neden degistigini kisaca anlatmalidir.

## Degisiklik Kabul Kontrol Listesi

- Degisiklik runtime state dosyalarini commit'e almiyor.
- Ilgili kaynak/parser/fetcher icin hedefli test calisti.
- JSON dosyalari `python -m json.tool` ile dogrulandi.
- Python dosyalari `python -m compileall` ile kontrol edildi.
- Servis gerekiyorsa restart edildi ve `ops/status.sh` temiz dondu.
- Relay veya dolayli kaynak kullanildiysa `notes` ve `source_class` alanlari guncellendi.
- Yeni credential gerekiyorsa `.env.example` guncellendi, gercek secret commit edilmedi.

## Oncelikli Teknik Borclar

1. `gh auth login` tamamlanmali; boylece PR, issue ve CI kontrolleri sunucudan da yonetilebilir.
2. Kirilgan dis kaynaklar icin per-source health raporu ureten kisa bir script eklenmeli.
3. Kritik parserlar icin fixture tabanli testler eklenmeli: Truth Social archive, UKMTO relay, CENTCOM, Iran MFA.
4. `rules/` JSON semasi basit bir validator ile korunmali.
5. Telegram alarm dili icin relay/resmi/sosyal ayrimini gosteren regression testleri yazilmali.
6. GitHub Actions icinde JSON validation, compileall ve temel smoke test otomatik calismali.
