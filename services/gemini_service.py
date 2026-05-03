import json
import re
import time
from pathlib import Path
from typing import Any

import requests

from config.paths import RULES_DIR
from config.settings import settings
from core.logger import get_logger

logger = get_logger('gemini_service')

PROMPTS_PATH = RULES_DIR / 'gemini_prompts.json'
SCHEMA_PATH = RULES_DIR / 'gemini_schema.json'
API_URL_TEMPLATE = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'

try:
    from google import genai
except Exception:
    genai = None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        logger.warning('Gemini json yüklenemedi (%s): %s', path.name, exc)
        return {}


PROMPTS = _load_json(PROMPTS_PATH)
SCHEMAS = _load_json(SCHEMA_PATH)


class GeminiService:
    def __init__(self):
        self.enabled = settings.gemini_enabled and bool(settings.gemini_api_key)
        self.client = None
        self.using_sdk = False
        self.last_error_code: int | None = None
        self.last_error_kind: str | None = None
        self.last_error_message: str = ''
        self.cooldown_until: float = 0.0
        self.cooldown_reason: str = ''
        self.last_cooldown_log_ts: float = 0.0
        if self.enabled and settings.gemini_sdk_preferred and genai is not None:
            try:
                self.client = genai.Client(api_key=settings.gemini_api_key)
                self.using_sdk = True
                logger.info('Gemini SDK aktif')
            except Exception as exc:
                logger.warning('Gemini SDK başlatılamadı, REST fallback kullanılacak: %s', exc)
        elif self.enabled:
            logger.info('Gemini REST aktif')

    def is_enabled(self) -> bool:
        return self.enabled

    def _clear_last_error(self):
        self.last_error_code = None
        self.last_error_kind = None
        self.last_error_message = ''

    def _mark_error(self, exc: Exception | str, status_code: int | None = None):
        text = str(exc or '').strip()
        low = text.lower()
        self.last_error_code = status_code
        self.last_error_message = text[:240]
        if status_code == 429 or '429' in low or 'resourceexhausted' in low or 'quota' in low:
            self.last_error_kind = 'quota'
        else:
            self.last_error_kind = 'error'

    def _now_ts(self) -> float:
        return time.time()

    def _extract_retry_delay_seconds(self, text: str) -> int | None:
        low = str(text or '').lower()
        m = re.search(r'retry in\s*([0-9]+(?:\.[0-9]+)?)s', low)
        if m:
            try:
                return max(1, int(float(m.group(1))))
            except Exception:
                return None
        m = re.search(r"'retrydelay':\s*'([0-9]+)s'", low)
        if m:
            try:
                return max(1, int(m.group(1)))
            except Exception:
                return None
        return None

    def _start_cooldown_from_error(self, text: str, status_code: int | None = None):
        low = str(text or '').lower()
        if not (status_code == 429 or '429' in low or 'resourceexhausted' in low or 'quota' in low):
            return

        retry_sec = self._extract_retry_delay_seconds(text) or 0

        is_daily = (
            'perday' in low
            or 'free_tier_requests' in low
            or 'generaterequestsperday' in low
            or 'quotaid' in low and 'perday' in low
        )

        if is_daily:
            cooldown_sec = max(1800, retry_sec + 30)   # en az 30 dk
            reason = 'daily_quota'
        else:
            cooldown_sec = max(45, min(300, retry_sec + 5))  # 45 sn - 5 dk
            reason = 'quota'

        until = self._now_ts() + cooldown_sec
        if until > self.cooldown_until:
            self.cooldown_until = until
            self.cooldown_reason = reason
            logger.warning('Gemini cooldown aktif: %s | %s sn', reason, int(cooldown_sec))

    def _is_cooldown_active(self) -> bool:
        return self.cooldown_until > self._now_ts()

    def _log_cooldown_skip(self):
        now = self._now_ts()
        if now - self.last_cooldown_log_ts < 60:
            return
        remain = max(0, int(self.cooldown_until - now))
        logger.info('Gemini cooldown nedeniyle AI katmanı atlandı: %s | kalan=%s sn', self.cooldown_reason or 'quota', remain)
        self.last_cooldown_log_ts = now

    def _build_contents(self, user_text: str) -> list[dict[str, Any]]:
        return [{'role': 'user', 'parts': [{'text': user_text}]}]

    def _build_generation_config(self, schema_def: dict[str, Any]) -> dict[str, Any]:
        config: dict[str, Any] = {'temperature': 0.2, 'response_mime_type': 'application/json'}
        if schema_def:
            config['response_schema'] = {'type': 'OBJECT', 'properties': {k: {'type': 'STRING'} for k in schema_def.keys()}}
        return config

    def _extract_text_from_sdk(self, response: Any) -> str | None:
        if response is None:
            return None
        text = getattr(response, 'text', None)
        if text:
            return str(text).strip() or None
        try:
            candidates = getattr(response, 'candidates', None) or []
            if candidates:
                parts = getattr(candidates[0].content, 'parts', [])
                texts = [getattr(p, 'text', '') for p in parts if getattr(p, 'text', '')]
                joined = '\n'.join(texts).strip()
                return joined or None
        except Exception:
            return None
        return None

    def _post_rest(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        if self._is_cooldown_active():
            self._log_cooldown_skip()
            return None
        url = API_URL_TEMPLATE.format(model=settings.gemini_model)
        headers = {'x-goog-api-key': settings.gemini_api_key, 'Content-Type': 'application/json'}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=settings.gemini_timeout)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            status = getattr(exc.response, 'status_code', None)
            self._mark_error(exc, status)
            self._start_cooldown_from_error(str(exc), status)
            logger.warning('Gemini REST hatası: %s', exc)
            return None
        except Exception as exc:
            self._mark_error(exc)
            self._start_cooldown_from_error(str(exc), None)
            logger.warning('Gemini REST hatası: %s', exc)
            return None

    def _extract_text_from_rest(self, response_json: dict[str, Any] | None) -> str | None:
        if not response_json:
            return None
        try:
            candidates = response_json.get('candidates') or []
            if not candidates:
                return None
            parts = candidates[0].get('content', {}).get('parts', [])
            texts = [p.get('text', '') for p in parts if p.get('text')]
            joined = '\n'.join(texts).strip()
            return joined or None
        except Exception as exc:
            logger.warning('Gemini response parse hatası: %s', exc)
            return None

    def _generate_json(self, prompt_name: str, user_text: str) -> dict[str, Any] | None:
        self._clear_last_error()
        if self._is_cooldown_active():
            self._log_cooldown_skip()
            return None
        prompt_def = PROMPTS.get(prompt_name, {})
        schema_def = SCHEMAS.get(prompt_name, {})
        if not prompt_def:
            return None
        system_text = prompt_def.get('system', '').strip()
        text = None
        if self.using_sdk and self.client is not None:
            try:
                response = self.client.models.generate_content(
                    model=settings.gemini_model,
                    contents=self._build_contents(user_text),
                    config={'system_instruction': system_text, **self._build_generation_config(schema_def)},
                )
                text = self._extract_text_from_sdk(response)
                if text:
                    self._clear_last_error()
                    self.cooldown_until = 0.0
                    self.cooldown_reason = ''
                if settings.gemini_log_enabled:
                    logger.info('Gemini SDK isteği başarılı: %s', prompt_name)
            except Exception as exc:
                self._mark_error(exc)
                self._start_cooldown_from_error(str(exc), None)
                if self.last_error_kind == 'quota':
                    logger.warning('Gemini SDK quota hatası, cooldown başlatıldı: %s', exc)
                    return None
                logger.warning('Gemini SDK hatası, REST fallback denenecek: %s', exc)
        if not text:
            payload = {
                'systemInstruction': {'parts': [{'text': system_text}]},
                'contents': self._build_contents(user_text),
                'generationConfig': {'temperature': 0.2, 'responseMimeType': 'application/json'},
            }
            if schema_def:
                payload['generationConfig']['responseSchema'] = {'type': 'OBJECT', 'properties': {k: {'type': 'STRING'} for k in schema_def.keys()}}
            raw = self._post_rest(payload)
            text = self._extract_text_from_rest(raw)
            if text:
                self._clear_last_error()
                self.cooldown_until = 0.0
                self.cooldown_reason = ''
                if settings.gemini_log_enabled:
                    logger.info('Gemini REST isteği başarılı: %s', prompt_name)
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            logger.warning('Gemini JSON decode başarısız, ham metin döndü')
            return {'raw_text': text}

    def classify_signal(self, item: dict[str, Any]) -> dict[str, Any] | None:
        tmpl = PROMPTS.get('classify_signal', {}).get('user_template', '')
        if not tmpl:
            return None
        article_text = str(item.get('article_text', '') or '')[:7000]
        user_text = tmpl.format(
            source_kind=item.get('source_kind', ''),
            source_name=item.get('source_name', ''),
            title=item.get('title', ''),
            description=item.get('description', ''),
            article_text=article_text,
            link=item.get('link', ''),
        )
        return self._generate_json('classify_signal', user_text)

    def match_events(self, a_title: str, a_text: str, b_title: str, b_text: str) -> dict[str, Any] | None:
        tmpl = PROMPTS.get('match_events', {}).get('user_template', '')
        if not tmpl:
            return None
        user_text = tmpl.format(a_title=a_title, a_text=a_text[:6000], b_title=b_title, b_text=b_text[:6000])
        return self._generate_json('match_events', user_text)

    def summarize_market_impact(self, title: str, text: str) -> dict[str, Any] | None:
        tmpl = PROMPTS.get('summarize_market_impact', {}).get('user_template', '')
        if not tmpl:
            return None
        user_text = tmpl.format(title=title, text=text[:7000])
        return self._generate_json('summarize_market_impact', user_text)


gemini_service = GeminiService()
