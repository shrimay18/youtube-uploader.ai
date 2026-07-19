"""Groq provider — fast, free-tier cloud inference (OpenAI-compatible API).

Note: 'gsk_' keys are Groq (groq.com fast inference), NOT xAI's Grok.
Key from env GROQ_API_KEY.
"""
from __future__ import annotations

import os

import requests

from .base import LLMProvider, QuotaExceeded


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, cfg: dict):
        self.model = cfg.get("model", "llama-3.3-70b-versatile")
        self.base = cfg.get("host", "https://api.groq.com/openai/v1").rstrip("/")

    def complete(self, system: str, user: str) -> str:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Get a free key at https://console.groq.com/keys."
            )
        try:
            r = requests.post(
                f"{self.base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
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
            raise RuntimeError(f"Groq request failed: {e}") from e

        if r.status_code == 429:
            raise QuotaExceeded("Groq rate/quota limit hit.")
        if r.status_code >= 400:
            raise RuntimeError(f"Groq error {r.status_code}: {r.text[:200]}")
        return r.json()["choices"][0]["message"]["content"] or ""
