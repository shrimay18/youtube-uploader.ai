"""Claude provider — highest quality, paid. Key from env ANTHROPIC_API_KEY."""
from __future__ import annotations

import os

from .base import LLMProvider


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, cfg: dict):
        self.model = cfg.get("model", "claude-sonnet-5")
        self._client = None

    def client(self):
        if self._client is not None:
            return self._client
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Get a key at https://console.anthropic.com/."
            )
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def complete(self, system: str, user: str) -> str:
        client = self.client()
        msg = client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=0.7,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Concatenate text blocks.
        return "".join(block.text for block in msg.content if block.type == "text")
