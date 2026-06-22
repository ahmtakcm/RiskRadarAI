from filters.ai_agent import analyze_signal
from filters.ai_parse import normalize_gemini_result, choose_best_summary
from enrichers.text_hygiene import normalize_content_item
from enrichers.standard_pipeline import translate_official_item as standard_translate_official_item
from services.gemini_service import gemini_service
from services.groq_service import groq_service
from services.github_models_service import github_models_service
from config.settings import settings


class AIClient:
    def __init__(self):
        self.providers = {
            'github': github_models_service,
            'github_models': github_models_service,
            'github-models': github_models_service,
            'gemini': gemini_service,
            'groq': groq_service,
        }

    def _normalize_provider_name(self, name: str) -> str:
        return str(name or '').strip().lower().replace('-', '_')

    def _provider_order(self):
        seen = set()
        ordered = []
        fallback = ['github', 'gemini', 'groq']
        for raw_name in [settings.ai_provider_primary, settings.ai_provider_secondary, *fallback]:
            name = self._normalize_provider_name(raw_name)
            provider = self.providers.get(name)
            if not provider or name in seen:
                continue
            seen.add(name)
            ordered.append(provider)
        return ordered

    def is_enabled(self) -> bool:
        return any(provider.is_enabled() for provider in self._provider_order())

    def is_matching_enabled(self) -> bool:
        return settings.gemini_matching_enabled and self.is_enabled()

    def _classify_with_providers(self, item: dict):
        for provider in self._provider_order():
            try:
                if provider.is_enabled():
                    result = provider.classify_signal(item)
                    norm = normalize_gemini_result(result)
                    if norm:
                        return norm
            except Exception:
                continue
        return None

    def _match_with_providers(self, candidate_item: dict, official_item: dict):
        for provider in self._provider_order():
            try:
                if provider.is_enabled() and hasattr(provider, 'match_events'):
                    result = provider.match_events(
                        candidate_item.get('title', ''),
                        '\n'.join(filter(None, [candidate_item.get('title', ''), candidate_item.get('description', ''), candidate_item.get('article_text', '')])).strip(),
                        official_item.get('title', ''),
                        '\n'.join(filter(None, [official_item.get('title', ''), official_item.get('description', ''), official_item.get('article_text', '')])).strip(),
                    )
                    norm = normalize_gemini_result(result)
                    if norm:
                        return norm
            except Exception:
                continue
        return None

    def translate_official_item(self, item: dict) -> tuple[str, str]:
        # Use the unified translation pipeline to ensure consistent results
        try:
            return standard_translate_official_item(item)
        except Exception:
            # Fallback to previous lightweight behavior
            normalize_content_item(item)
            raw_text = str(item.get('article_text') or item.get('description') or '').strip()
            return str(item.get('title', '')).strip(), raw_text[:4000]

    def build_digest_paragraph(self, items: list[dict]) -> str | None:
        summary_providers = [*self._provider_order(), github_models_service]
        seen = set()
        ordered = []
        for provider in summary_providers:
            key = provider.__class__.__name__
            if key in seen:
                continue
            seen.add(key)
            ordered.append(provider)

        for provider in ordered:
            try:
                if provider.is_enabled() and hasattr(provider, 'build_digest_paragraph'):
                    result = provider.build_digest_paragraph(items)
                    if result:
                        paragraph = str(result.get('paragraph_tr', '') or '').strip()
                        if paragraph:
                            return paragraph
            except Exception as exc:
                try:
                    from core.logger import get_logger
                    get_logger('ai_client').warning('Digest provider hatası (%s): %s', provider.__class__.__name__, exc)
                except Exception:
                    pass
                continue
        return None

    def analyze_item(self, item: dict, verification_rules: dict | None = None, verified: bool = False) -> dict:
        normalize_content_item(item)
        base_result = analyze_signal(item, verification_rules or {})
        base_conf = base_result.get('confidence', 0)
        use_ai = (base_conf * 10 >= settings.gemini_min_score or bool(item.get('article_text')))
        if settings.gemini_only_for_unverified and verified:
            use_ai = False
        if use_ai:
            model_result = self._classify_with_providers(item)
            if model_result:
                base_result['gemini'] = model_result
                label = str(model_result.get('label', '')).strip().lower()
                if label in {'ignore', 'watch', 'early_signal', 'verified_alert'}:
                    base_result['category'] = label
                    base_result['header'] = {
                        'ignore': 'ÖNEMSİZ',
                        'watch': '🧭 İZLEME SİNYALİ',
                        'early_signal': '🚨 YÜKSEK ÖNCELİKLİ SİNYAL',
                        'verified_alert': '✅ DOĞRULANMIŞ KRİTİK ALARM',
                    }[label]
                    base_result['should_notify'] = label in {'watch', 'early_signal', 'verified_alert'}
                if model_result.get('market_impact'):
                    base_result['market_impact'] = model_result['market_impact']
                if model_result.get('security_impact'):
                    base_result['security_impact'] = model_result['security_impact']
                summary = choose_best_summary(item, model_result)
                if summary:
                    base_result['summary_tr'] = summary
                if 'severity' in model_result:
                    try:
                        sev = int(float(model_result['severity']))
                        base_result['confidence'] = max(base_result.get('confidence', 0), min(1.0, sev / 10))
                    except Exception:
                        pass
        if not base_result.get('summary_tr'):
            base_result['summary_tr'] = choose_best_summary(item, base_result.get('gemini') or {})
        if item.get('matched_profile'):
            base_result['should_notify'] = True
        return base_result

    def match_items(self, candidate_item: dict, official_item: dict) -> dict | None:
        if not self.is_matching_enabled():
            return None
        return self._match_with_providers(candidate_item, official_item)


ai_client = AIClient()
