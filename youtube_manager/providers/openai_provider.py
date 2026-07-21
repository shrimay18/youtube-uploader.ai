"""OpenAI (GPT) provider — Chat Completions API. Supports multiple keys."""
from __future__ import annotations

import requests

from .base import KeyedProvider, QuotaExceeded


class OpenAIProvider(KeyedProvider):
    name = "openai"

    def __init__(self, cfg: dict, keys: list | None = None):
        super().__init__(cfg, keys)
        self.model = self.cfg.get("model", "gpt-4o-mini")
        self.base = self.cfg.get("host", "https://api.openai.com/v1").rstrip("/")

    def _call(self, key: str, system: str, user: str) -> str:
        try:
            r = requests.post(
                f"{self.base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "response_format": {"type": "json_object"},
                },
                timeout=120,
            )
        except requests.RequestException as e:
            raise RuntimeError(f"OpenAI request failed: {e}") from e

        if r.status_code == 429:
            raise QuotaExceeded("OpenAI rate/quota limit hit.")
        if r.status_code in (401, 403):
            raise RuntimeError(f"OpenAI auth error {r.status_code} (bad key).")
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI error {r.status_code}: {r.text[:200]}")
        return r.json()["choices"][0]["message"]["content"] or ""
