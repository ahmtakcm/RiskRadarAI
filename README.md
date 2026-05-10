# RiskRadarAI
https://deepwiki.com/ahmtakcm/RiskRadarAI

Resmî + sosyal + OSINT kaynaklarından risk sinyali toplayan, **çift doğrulama** mantığıyla güven seviyesini etiketleyen modüler Telegram alarm botu.

## Neler yapar?
- Resmî (kurumsal) kaynaklar, RSS, HTML liste sayfaları ve sosyal “erken sinyal” kaynaklarını birlikte tarar
- Sosyal/OSINT sinyallerini “kesin alarm” yerine ayrı sınıfta işler; resmî sinyalle kesişirse **✅ çift doğrulandı** olarak yükseltir
- Takvim bazlı “yaklaşıyor / yayınlandı” alarmı üretebilir
- AI sağlayıcıları (GitHub Models / Groq / opsiyonel Gemini) ile sınıflandırma/özetleme/matching işlerini kademeli ve hata toleranslı yürütür

## Hızlı başlangıç (yerel)
Python 3.11+ önerilir.

```bash
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` içine en az şu iki alanı gir:
- `BOT_TOKEN`: Telegram bot token
- `CHAT_ID`: Mesaj gidecek grup/kanal/sohbet ID

Çalıştır:

```bash
python main.py
```

## Üretim (Ubuntu + systemd)
Kurulum adımları `ops/SYSTEMD.md` içinde.

## Konfigürasyon
- **Kurallar / kaynaklar**: `rules/`
- **Profiller**: `profiles/` (ör. `ACTIVE_PROFILE=...`)
- **Runtime state**: `storage/` ve `user_inputs/` (GitHub'a commit edilmez)

## Proje yapısı (kısa)
- `main.py`: uygulama girişi (single-instance kilidiyle)
- `workflows/`: tarama/işleme akışları
- `fetchers/`, `parsers/`, `filters/`: toplama → parse → filtreleme zinciri
- `services/`: Telegram/AI sağlayıcıları vb.
- `ops/`: systemd ve operasyon scriptleri

---

## Detaylar (mevcut notlar)

## Yeni eklenenler
- `rules/social_feeds.json`: sosyal kaynaklar ayrı dosyada tutulur.
- `rules/calendar_watch.json`: yaklaşan ve yayımlandı takvim alarmı.
- yeni profiller: `ekonomi_resmi`, `guvenlik_resmi`, `saglik_resmi`, `stratejik_karma`
- `listing_html` tipi ile RSS olmayan resmi / kurumsal sayfaları tarama
- PDF bağlantıları için temel tespit (`description: PDF rapor bağlantısı`)

## Kaynak türleri
- `news` / `rss`: standart haber akışı
- `official_html`: özel parser veya kurumsal HTML akışı
- `listing_html`: link listeleme mantığıyla kurumsal sayfa taraması
- `rss_social`: sosyal erken sinyal kaynağı

## Sosyal erken sinyal ne demek?
Sosyal hesaplar bazen resmi web sitesinden önce işaret verir. Bu yüzden ayrı tutulur. Çekirdek alarm motoru yine resmi kaynaklardan yürür; sosyal kaynaklar opsiyonel hız katmanıdır.

## Takvim alarmı
`calendar_watch.json` içinde her etkinlik için iki alarm türü üretilebilir:
- `yaklasiyor`
- `yayinlandi`

`yayinlandi` alarmı yayın sinyali metin aramasıyla çalışır; yüzde yüz kesinlik yerine pratik otomasyon amaçlıdır.


## Çift doğrulama mantığı

Bu sürümde sosyal kaynaklar ve resmî kaynaklar ayrı taranır.

- `rss_social` kaynakları erken sinyal üretir.
- `official_html`, `listing_html`, `rss` ve benzeri kurumsal kaynaklar resmî kanal gibi işlenir.
- Sosyal sinyal ile resmî sinyal ortak anahtar kelimelerde kesişirse mesaj `✅ ÇİFT DOĞRULANDI / SOSYAL + RESMÎ` etiketi alır.
- Sosyal sinyal önce gelirse `⚡ SOSYAL ERKEN SİNYAL / RESMÎ TEYİT BEKLENİYOR` şeklinde düşer ve beklemeye alınır.
- Daha sonra aynı konuda resmî kaynak gelirse `✅ RESMÎ TEYİT GELDİ` mesajı gönderilir.

### Yeni .env seçenekleri

```env
VERIFICATION_WINDOW_MINUTES=360
PENDING_SOCIAL_TTL_MINUTES=720
SEND_UNVERIFIED_SOCIAL_ALERTS=true
```


## Yeni işlem katmanı
- `rules/osint_feeds.json`: LiveUAMap, OSINT ve hızlı saha sinyalleri
- `rules/analysis_feeds.json`: Crisis Group, Security Council Report, PDF/rapor ve stratejik analiz akışı
- `filters/ai_agent.py`: kural tabanlı AI-agent benzeri sınıflandırıcı
- `services/assistant_output.py`: kişisel asistana gidecek temiz mesaj üretimi

Akış modeli:
1. Resmî kaynaklar
2. Sosyal kaynaklar
3. OSINT/hızlı saha kaynakları
4. Analiz/PDF/rapor kaynakları

Gayriresmî kaynaklar doğrudan kesin alarm sayılmaz; mümkünse resmî kaynakla eşleşirse **çift doğrulandı** olarak işaretlenir.


## Gemini

Bu sürüm önce `google-genai` SDK kullanmayı dener; SDK kullanılamazsa REST fallback ile devam eder.


## Social mirror failover

Sosyal RSS kaynakları için `rules/social_mirrors.json` kullanılır. Bir mirror 503/erişim hatası verirse sistem diğer aynaları dener. Art arda başarısızlıkta feed geçici cooldown'a alınır ve `storage/source_health.json` içinde izlenir.


## Freshness Gate

Bu sürümde sosyal/OSINT/resmî içerikler yaş sınırına göre elenir. Eski içerikler Telegram alarmına düşmez. Yaş sınırları `.env` üzerinden yönetilir.


## Hızlı güncelleme

Tam yedek + temiz kurulum en güvenli yöntemdir. Daha pratik güncellemeler için patch ZIP kullanıp sadece değişen dosyaları aynı klasöre açabilirsiniz. `.env` ve `storage/` korunur.


## Groq Entegrasyonu

Bu proje Groq OpenAI-uyumlu API ile çalışabilir. `.env` içine `GROQ_API_KEY`, `GROQ_ENABLED=true` ve `AI_PROVIDER_PRIMARY=groq` ekleyin. Gerekirse `AI_PROVIDER_SECONDARY=gemini` ile Gemini yedek sağlayıcı olarak kalır.


## Son kalite güncellemeleri
- Yorum/analiz/video sayfaları alarm akışından düşürülür.
- Haber sitesi içeriklerinde URL türü filtresi kullanılır.
- CENTCOM Press Releases kaynağı birincil resmî kaynaklara eklendi.
- Groq ana sağlayıcı, Gemini ikincil sağlayıcı olarak desteklenir.


## Resmî kaynak kırmızı alarm
- CENTCOM, Truth Social, Iran MFA, IRNA, liderlik ve cumhurbaşkanlığı gibi resmî kaynaklarda keyword eşleşirse alarm seviyesi sertleşir.

## Muhendislik Kurallari

Projenin teknik karar sozlesmesi [docs/ENGINEERING_RULES.md](docs/ENGINEERING_RULES.md) dosyasinda tutulur. Kisa ozet: alarm guveni hizdan once gelir, kaynaklar kirilgan kabul edilir, relay kaynaklar seffaf etiketlenir, runtime state GitHub'a girmez ve her degisiklik hedefli testle dogrulanir.
