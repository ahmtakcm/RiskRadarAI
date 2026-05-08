def build_reply_keyboard() -> dict:
    return {
        "keyboard": [
            ["✅ Sağlık", "🧾 Audit"],
            ["📚 Profiller", "📡 Kaynaklar"],
            ["👁 Watch", "🔎 Tara"],
            ["📋 Menü"],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
        "is_persistent": True,
    }
