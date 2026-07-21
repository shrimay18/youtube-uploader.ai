"""Claude (Anthropic) provider — highest quality. Supports multiple keys."""
from __future__ import annotations

from .base import KeyedProvider, QuotaExceeded


class ClaudeProvider(KeyedProvider):
    name = "anthropic"

    def __init__(self, cfg: dict, keys: list | None = None):
        super().__init__(cfg, keys)
        self.model = self.cfg.get("model", "claude-sonnet-5")

    def _call(self, key: str, system: str, user: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        try:
            msg = client.messages.create(
                model=self.model, max_tokens=2048, temperature=0.7,
                system=system, messages=[{"role": "user", "content": user}],
            )
        except Exception as e:
            s = str(e)
            if "429" in s or "rate_limit" in s or "overloaded" in s.lower():
                raise QuotaExceeded(f"Anthropic rate/quota limit: {s[:120]}") from e
            raise
        return "".join(block.text for block in msg.content if block.type == "text")
