from workflows.signal_engine import analyze_event
from clients.ai_client import ai_client


def build_post_release_analysis(event: dict, text: str) -> str:
    title = event.get("title") or "Makro açıklama"
    source = event.get("source_name") or "Kaynak"
    event_type = event.get("event_type") or event.get("category") or ""

    signal = analyze_event({
        "type": event_type,
        "title": title,
        "text": text or "",
    })

    impact = signal.get("impact") or {}

    ai_assessment = _ai_assessment(event, text, signal)

    lines = [
        "📣 MAKRO AÇIKLAMA ANALİZİ",
        "",
        f"Başlık: {title}",
        f"Kaynak: {source}",
        "",
        "AI Değerlendirme:",
        ai_assessment or _short_assessment(signal, text),
        "",
        "Makro Sinyal:",
        f"Yön: {_tr_bias(signal.get('bias'))}",
        f"Güven: {signal.get('confidence', 0)}",
    ]

    for asset, direction in impact.items():
        lines.append(f"{asset.upper()}: {_tr_direction(direction)}")

    return "\n".join(lines)


def _short_assessment(signal: dict, text: str) -> str:
    bias = signal.get("bias")

    if bias == "hawkish":
        return "Metin şahin algılanıyor. Sıkı para politikası, enflasyon baskısı veya faizlerin yüksek kalması vurgusu öne çıkıyor."
    if bias == "dovish":
        return "Metin güvercin algılanıyor. Gevşeme, büyüme kaygısı veya faiz indirimi beklentisini destekleyen unsurlar öne çıkıyor."
    if bias == "inflation_hot":
        return "Enflasyon baskısı güçlü algılanıyor. Bu durum dolar ve tahvil faizleri için destekleyici, riskli varlıklar için baskılayıcı olabilir."
    if bias == "inflation_cool":
        return "Enflasyon baskısı zayıflıyor algısı var. Bu durum risk iştahını destekleyebilir."
    if bias == "energy_supply_shock":
        return "Enerji arz riski algılanıyor. Petrol ve enflasyon beklentileri üzerinde yukarı baskı oluşabilir."

    return "Metin belirgin şahin veya güvercin sinyal üretmedi. Piyasa etkisi sınırlı ya da karışık olabilir."


def _tr_bias(value):
    return {
        "hawkish": "Şahin",
        "dovish": "Güvercin",
        "inflation_hot": "Sıcak enflasyon",
        "inflation_cool": "Soğuyan enflasyon",
        "energy_supply_shock": "Enerji arz şoku",
        "neutral": "Nötr",
    }.get(value or "neutral", value or "Nötr")


def _tr_direction(value):
    return {
        "bullish": "Pozitif",
        "bearish": "Negatif",
        "neutral": "Nötr",
    }.get(value, value)


def _ai_assessment(event: dict, text: str, signal: dict) -> str:
    try:
        item = {
            "title": event.get("title") or "Makro açıklama",
            "description": text[:2000],
            "article_text": text[:6000],
            "source_name": event.get("source_name") or "",
            "source": event.get("source_name") or "",
            "category": event.get("event_type") or event.get("category") or "macro_release",
        }

        result = ai_client.analyze_item(item, verification_rules={}, verified=True)

        summary = str(result.get("summary_tr") or "").strip()
        market_impact = result.get("market_impact") or {}

        parts = []
        if summary:
            parts.append(summary[:700])

        if market_impact:
            parts.append("Piyasa etkisi: " + str(market_impact)[:400])

        final = "\n".join(parts).strip()
        weak = {"piyasa etkisi: orta", "piyasa etkisi: yüksek", "piyasa etkisi: düşük"}
        if final and final.lower() not in weak and len(final) >= 80:
            return final

    except Exception:
        return ""

    return ""
