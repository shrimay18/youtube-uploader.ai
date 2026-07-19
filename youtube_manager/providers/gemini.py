"""Gemini provider — free tier. Key from env GEMINI_API_KEY.

Uses the current `google-genai` SDK (the older `google-generativeai` is EOL).
"""
from __future__ import annotations

import os

from .base import LLMProvider


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, cfg: dict):
        self.model_name = cfg.get("model", "gemini-flash-latest")
        self._client = None  # lazy — avoids import/auth cost until first call

    def client(self):
        if self._client is not None:
            return self._client
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Get a free key at "
                "https://aistudio.google.com/apikey and set it "
                "(PowerShell: setx GEMINI_API_KEY \"your-key\", then reopen the shell)."
            )
        from google import genai

        self._client = genai.Client(api_key=api_key)
        return self._client

    def complete(self, system: str, user: str) -> str:
        from google.genai import types

        from .base import QuotaExceeded

        client = self.client()
        cfg_kwargs = dict(
            temperature=0.7,
            response_mime_type="application/json",
            max_output_tokens=8192,
        )
        # Newer flash models "think" by default, which eats the output-token budget
        # and truncates the JSON. Disable it for these structured tasks when supported.
        try:
            cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        except Exception:
            pass

        try:
            resp = client.models.generate_content(
                model=self.model_name,
                contents=f"{system}\n\n{user}",
                config=types.GenerateContentConfig(**cfg_kwargs),
            )
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                raise QuotaExceeded(
                    f"Gemini free-tier quota hit for {self.model_name}. "
                    "Wait for the daily reset (~1:30 PM IST), switch engine to Ollama "
                    "in settings.yaml, or use a paid key."
                ) from e
            raise
        text = resp.text or ""
        if not text:
            # Surface why (e.g. finish_reason=MAX_TOKENS / SAFETY) instead of silent "".
            fr = ""
            try:
                fr = str(resp.candidates[0].finish_reason)
            except Exception:
                pass
            raise RuntimeError(f"Gemini returned no text (finish_reason={fr}).")
        return text
