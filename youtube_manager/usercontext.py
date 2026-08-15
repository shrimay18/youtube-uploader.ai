"""Per-request user context — replaces the global vault._STATE.

Built fresh from the authenticated user's decrypted keys on each request and
passed explicitly to the services that need it (no module globals, no
os.environ key-stuffing). This is the DIP/statelessness fix for multi-tenancy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

BUILTINS = ("gemini", "openai", "anthropic", "groq")
DEFAULT_ORDER = ["anthropic", "gemini", "openai", "groq"]


@dataclass
class UserContext:
    id: str
    email: str = ""
    llm: dict = field(default_factory=dict)      # {provider: [key, ...]}
    order: list = field(default_factory=list)    # preference tokens (builtins + custom ids)
    custom: list = field(default_factory=list)   # [{id, name, base, model, key}]

    def keys_for(self, provider: str) -> list:
        return list(self.llm.get("anthropic" if provider == "claude" else provider) or [])

    def engine_order(self) -> list:
        return list(self.order or DEFAULT_ORDER)

    def custom_providers(self) -> list:
        return [c for c in (self.custom or []) if c.get("key")]

    def has_llm(self) -> bool:
        return any(self.llm.get(p) for p in BUILTINS) or bool(self.custom_providers())
