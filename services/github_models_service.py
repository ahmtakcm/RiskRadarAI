import json
import re
import time
from pathlib import Path
from typing import Any

import requests

from config.paths import RULES_DIR
from config.settings import settings
from core.logger import get_logger

logger = get_logger("github_models_service")

PROMPTS_PATH = RULES_DIR / "github_models_prompts.json"
SCHEMAS_PATH = RULES_DIR / "gemini_schema.json"
API_URL = "https://models.github.ai/inference/chat/completions"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("GitHub Models json yüklenemedi (%s): %s", path.name, exc)
        return {}


def _extract_json_block(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    raw = str(text).strip()
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


class GitHubModelsService:
    def __init__(self):
        self.enabled = (
            getattr(settings, "github_models_enabled", False)
            and bool(getattr(settings, "github_models_token", ""))
        )
        self.cooldown_until = 0.0
        self._cooldown_logged_until = 0.0
        if self.enabled:
            logger.info("GitHub Models aktif")

    def is_enabled(self) -> bool:
        return self.enabled

    def _is_in_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    def _enter_cooldown(self, seconds: int, prompt_name: str, reason: str) -> None:
        until = time.time() + max(60, int(seconds))
        self.cooldown_until = max(self.cooldown_until, until)
        if self._cooldown_logged_until < self.cooldown_until:
            remaining = int(self.cooldown_until - time.time())
            logger.warning('GitHub Models cooldown aktif (%s): %s | %s sn', prompt_name, reason, remaining)
            self._cooldown_logged_until = self.cooldown_until

    def _response_text(self, data: dict[str, Any]) -> str:
        message = ((data.get("choices") or [{}])[0].get("message") or {})
        content = message.get("content", "")
        if isinstance(content, list):
            texts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    txt = part.get("text") or part.get("content") or ""
                    if txt:
                        texts.append(str(txt))
                elif isinstance(part, str):
                    texts.append(part)
            return "\n".join(texts).strip()
        return str(content or "").strip()

    def _generate_json(self, prompt_name: str, user_text: str, *, max_tokens: int = 500) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        prompt_def = PROMPTS.get(prompt_name, {})
        if not prompt_def:
            logger.warning("GitHub Models prompt tanımı yok: %s", prompt_name)
            return None

        system_text = str(prompt_def.get("system", "")).strip()
        schema_def = SCHEMAS.get(prompt_name, {})
        schema_keys = ", ".join(schema_def.keys()) if schema_def else "JSON"
        final_user = (
            user_text
            + "\n\nYALNIZCA GEÇERLİ JSON DÖNDÜR. Açıklama yazma. Markdown kullanma."
            + f" JSON anahtarları: {schema_keys}"
        )

        payload = {
            "model": getattr(settings, "github_models_model", "openai/gpt-4.1"),
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": final_user},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {settings.github_models_token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

        if self._is_in_cooldown():
            remaining = int(self.cooldown_until - time.time())
            if remaining > 0 and self._cooldown_logged_until < self.cooldown_until:
                logger.warning('GitHub Models beklemede (%s): cooldown %s sn', prompt_name, remaining)
                self._cooldown_logged_until = self.cooldown_until
            return None

        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=getattr(settings, "github_models_timeout", 30),
            )
            if response.status_code == 429:
                retry_after = 0
                try:
                    retry_after = int(float(response.headers.get('Retry-After', '0') or '0'))
                except Exception:
                    retry_after = 0
                self._enter_cooldown(max(retry_after, getattr(settings, 'github_models_cooldown_seconds', 900)), prompt_name, '429 Too Many Requests')
                return None
            response.raise_for_status()
            data = response.json()
            text = self._response_text(data)
            parsed = _extract_json_block(text)
            if parsed is None:
                raise ValueError("GitHub Models geçerli JSON döndürmedi")
            return parsed
        except requests.HTTPError as exc:
            logger.warning("GitHub Models hatası (%s): %s", prompt_name, exc)
            return None
        except Exception as exc:
            logger.warning("GitHub Models hatası (%s): %s", prompt_name, exc)
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
        return self._generate_json("classify_signal", user_text, max_tokens=550)

    def match_events(self, a_title: str, a_text: str, b_title: str, b_text: str) -> dict[str, Any] | None:
        tmpl = PROMPTS.get("match_events", {}).get("user_template", "")
        if not tmpl:
            return None
        user_text = tmpl.format(a_title=a_title, a_text=a_text[:7000], b_title=b_title, b_text=b_text[:7000])
        return self._generate_json("match_events", user_text, max_tokens=250)

    def summarize_market_impact(self, title: str, text: str) -> dict[str, Any] | None:
        tmpl = PROMPTS.get("summarize_market_impact", {}).get("user_template", "")
        if not tmpl:
            return None
        user_text = tmpl.format(title=title, text=text[:9000])
        return self._generate_json("summarize_market_impact", user_text, max_tokens=400)

    def translate_official_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        tmpl = PROMPTS.get("translate_official_item", {}).get("user_template", "")
        if not tmpl:
            return None
        article_text = str(item.get("article_text", "") or item.get("description", "") or "")[:12000]
        user_text = tmpl.format(
            source_name=item.get("source_name", ""),
            title=item.get("title", ""),
            text=article_text,
            link=item.get("link", ""),
        )
        return self._generate_json("translate_official_item", user_text, max_tokens=1400)

    def build_digest_paragraph(self, items: list[dict[str, Any]]) -> dict[str, Any] | None:
        tmpl = PROMPTS.get("digest_paragraph", {}).get("user_template", "")
        if not tmpl:
            return None
        parts: list[str] = []
        for idx, item in enumerate(items[:12], start=1):
            parts.append(f"[{idx}] {item.get('translated_text', '')}")
        user_text = tmpl.format(items="\n".join(parts))
        return self._generate_json("digest_paragraph", user_text, max_tokens=350)


github_models_service = GitHubModelsService()
