import time
from config.settings import settings
from core.logger import get_logger
# Gemini geçici devre dışı: dosyada cooldown typo hataları var.
# from services.gemini_service import gemini_service
from services.groq_service import groq_service
from services.github_models_service import github_models_service

logger = get_logger("ai_router")

AI_MAX_CALLS_PER_WINDOW = 3
AI_WINDOW_SECONDS = 300
_ai_window_start = 0
_ai_window_calls = 0


class AIRouter:
    def __init__(self):
        self.providers = {
            "github": github_models_service,
            "github_models": github_models_service,
            "github-models": github_models_service,
            "groq": groq_service,
            # "gemini": gemini_service,
        }

    def _provider_order(self):
        seen = []
        for name in [settings.ai_provider_primary, settings.ai_provider_secondary, "github", "groq"]:
            n = (name or "").strip().lower()
            if n and n not in seen:
                seen.append(n)
        return seen

    def _call(self, method_name: str, *args, **kwargs):
        global _ai_window_start, _ai_window_calls

        now = time.time()
        if now - _ai_window_start > AI_WINDOW_SECONDS:
            _ai_window_start = now
            _ai_window_calls = 0

        if _ai_window_calls >= AI_MAX_CALLS_PER_WINDOW:
            logger.info("AI çağrı limiti nedeniyle atlandı: %s", method_name)
            return None

        _ai_window_calls += 1

        for provider_name in self._provider_order():
            provider = self.providers.get(provider_name)
            if provider is None or not provider.is_enabled():
                continue
            try:
                fn = getattr(provider, method_name)
                result = fn(*args, **kwargs)
                if result:
                    if settings.gemini_log_enabled:
                        logger.info("AI sağlayıcı başarılı: %s -> %s", provider_name, method_name)
                    return result
            except Exception as exc:
                logger.warning("AI sağlayıcı hatası (%s -> %s): %s", provider_name, method_name, exc)
        return None

    def classify_signal(self, item: dict):
        return self._call("classify_signal", item)

    def match_events(self, a_title: str, a_text: str, b_title: str, b_text: str):
        return self._call("match_events", a_title, a_text, b_title, b_text)

    def summarize_market_impact(self, title: str, text: str):
        return self._call("summarize_market_impact", title, text)

    def translate_official_item(self, item: dict):
        return self._call("translate_official_item", item)

    def build_digest_paragraph(self, items: list[dict]):
        return self._call("build_digest_paragraph", items)

    def is_enabled(self) -> bool:
        return any(p.is_enabled() for p in self.providers.values())


ai_router = AIRouter()
