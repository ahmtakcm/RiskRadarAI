import json
import re
from pathlib import Path
from typing import Any

import requests

from config.paths import RULES_DIR
from config.settings import settings
from core.logger import get_logger

logger = get_logger("groq_service")
PROMPTS_PATH = RULES_DIR / "groq_prompts.json"
SCHEMAS_PATH = RULES_DIR / "gemini_schema.json"
API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Groq json yüklenemedi (%s): %s", path.name, exc)
        return {}


def _extract_json_block(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    raw = text.strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass
    brace = re.search(r"(\{.*\})", raw, re.DOTALL)
    if brace:
        try:
            return json.loads(brace.group(1))
        except Exception:
            pass
    return None


PROMPTS = _load_json(PROMPTS_PATH)
SCHEMAS = _load_json(SCHEMAS_PATH)


class GroqService:
    def __init__(self):
        self.enabled = getattr(settings, "groq_enabled", False) and bool(getattr(settings, "groq_api_key", ""))
        if self.enabled:
            logger.info("Groq aktif")

    def is_enabled(self) -> bool:
        return self.enabled

    def _generate_json(self, prompt_name: str, user_text: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        prompt_def = PROMPTS.get(prompt_name, {})
        if not prompt_def:
            return None
        schema_def = SCHEMAS.get(prompt_name, {})
        system_text = str(prompt_def.get("system", "")).strip()
        schema_keys = ", ".join(schema_def.keys()) if schema_def else "JSON"
        final_user = (
            user_text
            + "\n\nYALNIZCA GEÇERLİ JSON DÖNDÜR. Açıklama yazma. Markdown kullanma."
            + f" JSON anahtarları: {schema_keys}"
        )
        payload = {
            "model": getattr(settings, "groq_model", "llama-3.3-70b-versatile"),
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": final_user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=getattr(settings, "groq_timeout", 20))
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"].strip()
            parsed = _extract_json_block(text)
            if parsed is None:
                raise ValueError("Groq geçerli JSON döndürmedi")
            return parsed
        except Exception as exc:
            logger.warning("Groq hatası (%s): %s", prompt_name, exc)
            return None

    def classify_signal(self, item: dict[str, Any]) -> dict[str, Any] | None:
        tmpl = PROMPTS.get("classify_signal", {}).get("user_template", "")
        if not tmpl:
            return None
        article_text = str(item.get("article_text", "") or "")[:9000]
        user_text = tmpl.format(
            source_kind=item.get("source_kind", ""),
            source_name=item.get("source_name", ""),
            title=item.get("title", ""),
            description=item.get("description", ""),
            article_text=article_text,
            link=item.get("link", ""),
        )
        return self._generate_json("classify_signal", user_text)

    def match_events(self, a_title: str, a_text: str, b_title: str, b_text: str) -> dict[str, Any] | None:
        tmpl = PROMPTS.get("match_events", {}).get("user_template", "")
        if not tmpl:
            return None
        user_text = tmpl.format(a_title=a_title, a_text=a_text[:7000], b_title=b_title, b_text=b_text[:7000])
        return self._generate_json("match_events", user_text)

    def summarize_market_impact(self, title: str, text: str) -> dict[str, Any] | None:
        tmpl = PROMPTS.get("summarize_market_impact", {}).get("user_template", "")
        if not tmpl:
            return None
        user_text = tmpl.format(title=title, text=text[:9000])
        return self._generate_json("summarize_market_impact", user_text)

    def translate_official_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        tmpl = PROMPTS.get("translate_official_item", {}).get("user_template", "")
        if not tmpl:
            return None
        article_text = str(item.get("article_text", "") or item.get("description", "") or "")[:9000]
        user_text = tmpl.format(
            source_name=item.get("source_name", ""),
            title=item.get("title", ""),
            text=article_text,
            link=item.get("link", ""),
        )
        return self._generate_json("translate_official_item", user_text)

    def build_digest_paragraph(self, items: list[dict[str, Any]]) -> dict[str, Any] | None:
        tmpl = PROMPTS.get("digest_paragraph", {}).get("user_template", "")
        if not tmpl:
            return None
        parts: list[str] = []
        for idx, item in enumerate(items[:12], start=1):
            parts.append(f"[{idx}] {item.get('translated_text', '')}")
        user_text = tmpl.format(items='\n'.join(parts))
        return self._generate_json("digest_paragraph", user_text)


groq_service = GroqService()
