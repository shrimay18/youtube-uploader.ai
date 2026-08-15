"""LLM providers behind one interface.

Engine selection now follows the signed-in user's PREFERENCE ORDER (from the vault),
falling back to settings.yaml `engine`/`fallback` for CLI/dev use. Each provider can
hold multiple keys and rotates through them on quota.
"""
from __future__ import annotations

import os

from .base import LLMProvider, QuotaExceeded

_ENV = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY", "claude": "ANTHROPIC_API_KEY", "groq": "GROQ_API_KEY"}


def _build(name: str, settings: dict, keys: list | None) -> LLMProvider:
    name = name.lower()
    if name == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(settings.get("gemini", {}), keys)
    if name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(settings.get("openai", {}), keys)
    if name in ("anthropic", "claude"):
        from .claude import ClaudeProvider
        return ClaudeProvider(settings.get("claude", settings.get("anthropic", {})), keys)
    if name == "groq":
        from .groq import GroqProvider
        return GroqProvider(settings.get("groq", {}), keys)
    if name == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider(settings.get("ollama", {}))
    raise ValueError(f"Unknown engine '{name}'.")


def _keys_for(name: str) -> list:
    """A provider's keys — from the vault if signed in, else the environment."""
    try:
        from .. import vault
        if vault.is_authed():
            ks = vault.llm_keys("anthropic" if name == "claude" else name)
            if ks:
                return ks
    except Exception:
        pass
    v = os.environ.get(_ENV.get(name, ""), "").strip()
    return [v] if v else []


def _build_chain(settings: dict, order: list, keys_for, custom_map: dict) -> LLMProvider:
    """Shared engine-chain builder. `keys_for(name)->list` and `custom_map` decouple
    the key SOURCE (global vault OR a per-request UserContext) from the wiring."""
    def _custom(c):
        from .openai_provider import OpenAIProvider
        p = OpenAIProvider({"host": c.get("base") or "https://api.openai.com/v1",
                            "model": c.get("model") or "gpt-4o-mini"}, [c["key"]])
        p.name = c.get("name") or "custom"
        return p

    norm = {"claude": "anthropic"}
    chain, seen_custom = [], set()
    for token in order:
        name = norm.get(token.lower(), token.lower())
        if name in ("gemini", "openai", "anthropic", "groq"):
            keys = keys_for(name)
            if keys:
                chain.append((name, _build(name, settings, keys)))
        elif name == "ollama":
            chain.append((name, _build("ollama", settings, None)))
        elif token in custom_map:
            seen_custom.add(token)
            chain.append((custom_map[token].get("name") or "custom", _custom(custom_map[token])))
    for cid, c in custom_map.items():   # safety: any custom not listed in order
        if cid not in seen_custom:
            chain.append((c.get("name") or "custom", _custom(c)))

    if not chain:
        first = order[0] if order else "gemini"
        return _build(first, settings, keys_for(first))  # surfaces its "no key" error
    if len(chain) == 1:
        return chain[0][1]
    return FallbackProvider(chain)


def get_provider(settings: dict) -> LLMProvider:
    """Build the engine chain from the signed-in user's vault (legacy/local path)."""
    order = None
    try:
        from .. import vault
        if vault.is_authed() and vault.has_llm_key():
            order = list(vault.engine_order())
    except Exception:
        pass
    if not order:
        primary = (settings.get("engine") or "gemini").lower()
        order = [primary] + [n.lower() for n in (settings.get("fallback") or []) if n.lower() != primary]

    custom_map = {}
    try:
        from .. import vault
        if vault.is_authed():
            custom_map = {c["id"]: c for c in vault.custom_providers() if c.get("key")}
    except Exception:
        pass
    return _build_chain(settings, order, _keys_for, custom_map)


def get_provider_for(ctx, settings: dict) -> LLMProvider:
    """Build the engine chain from a per-request UserContext (hosted/multi-tenant path)."""
    order = list(ctx.engine_order()) if ctx.has_llm() else []
    if not order:
        primary = (settings.get("engine") or "gemini").lower()
        order = [primary] + [n.lower() for n in (settings.get("fallback") or []) if n.lower() != primary]
    custom_map = {c["id"]: c for c in ctx.custom_providers()}
    return _build_chain(settings, order, ctx.keys_for, custom_map)


class FallbackProvider(LLMProvider):
    """Try providers in order; on quota/failure, move to the next (and remember it)."""

    name = "fallback"

    def __init__(self, chain: list[tuple[str, LLMProvider]]):
        self.chain = chain
        self._exhausted: set[str] = set()
        self._announced: set[str] = set()

    def _run(self, method: str, system: str, user: str):
        errors = []
        for name, provider in self.chain:
            if name in self._exhausted:
                continue
            try:
                result = getattr(provider, method)(system, user)
                if name not in self._announced and name != self.chain[0][0]:
                    print(f"      [engine] using fallback: {name}")
                    self._announced.add(name)
                return result
            except QuotaExceeded as e:
                print(f"      [engine] {name} exhausted -> trying next")
                self._exhausted.add(name)
                errors.append(f"{name}: {e}")
            except Exception as e:
                print(f"      [engine] {name} failed ({type(e).__name__}) -> trying next")
                errors.append(f"{name}: {e}")
        raise QuotaExceeded("All engines failed -> " + " | ".join(errors))

    def complete(self, system: str, user: str) -> str:
        return self._run("complete", system, user)

    def complete_json(self, system: str, user: str) -> dict:
        return self._run("complete_json", system, user)
