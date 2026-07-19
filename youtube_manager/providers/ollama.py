"""Ollama provider — fully local, free. Requires `ollama serve` running."""
from __future__ import annotations

import json

import requests

from .base import LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, cfg: dict):
        self.model = cfg.get("model", "llama3.1:8b")
        self.host = cfg.get("host", "http://localhost:11434").rstrip("/")

    def complete(self, system: str, user: str) -> str:
        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.7},
                },
                timeout=180,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.host}. Is `ollama serve` running "
                f"and `ollama pull {self.model}` done?"
            ) from exc
        data = resp.json()
        return data.get("message", {}).get("content", "")
