"""Gemini provider — uses the current `google-genai` SDK. Supports multiple keys
(rotated on quota) via KeyedProvider.
"""
from __future__ import annotations

from .base import KeyedProvider, QuotaExceeded


class GeminiProvider(KeyedProvider):
    name = "gemini"

    def __init__(self, cfg: dict, keys: list | None = None):
        super().__init__(cfg, keys)
        self.model_name = self.cfg.get("model", "gemini-flash-latest")

    def _call(self, key: str, system: str, user: str) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=key)
        cfg_kwargs = dict(temperature=0.7, response_mime_type="application/json", max_output_tokens=8192)
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
                raise QuotaExceeded(f"Gemini quota hit for {self.model_name}.") from e
            raise
        text = resp.text or ""
        if not text:
            fr = ""
            try:
                fr = str(resp.candidates[0].finish_reason)
            except Exception:
                pass
            raise RuntimeError(f"Gemini returned no text (finish_reason={fr}).")
        return text
