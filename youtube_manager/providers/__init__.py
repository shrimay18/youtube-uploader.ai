"""LLM providers behind one interface. Pick via settings.yaml `engine` (+ `fallback`)."""
from __future__ import annotations

import os

from .base import LLMProvider, QuotaExceeded


def _build(name: str, settings: dict) -> LLMProvider:
    name = name.lower()
    if name == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(settings.get("gemini", {}))
    if name == "groq":
        from .groq import GroqProvider
        return GroqProvider(settings.get("groq", {}))
    if name == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider(settings.get("ollama", {}))
    if name == "claude":
        from .claude import ClaudeProvider
        return ClaudeProvider(settings.get("claude", {}))
    raise ValueError(f"Unknown engine '{name}'. Use gemini | groq | ollama | claude.")


def _available(name: str) -> bool:
    """Skip cloud providers whose key is missing so we don't waste a failed call."""
    name = name.lower()
    if name == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY"))
    if name == "groq":
        return bool(os.environ.get("GROQ_API_KEY"))
    if name == "claude":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    return True  # ollama is local — try it regardless


def get_provider(settings: dict) -> LLMProvider:
    """Return the primary engine, or a FallbackProvider chain if `fallback` is set."""
    primary = (settings.get("engine") or "gemini").lower()
    chain_names = [primary] + [
        n.lower() for n in (settings.get("fallback") or []) if n.lower() != primary
    ]
    chain = [(n, _build(n, settings)) for n in chain_names if _available(n)]

    if not chain:
        # No key for the primary and no fallbacks available — build primary anyway so
        # the user gets its explicit "key not set" error.
        return _build(primary, settings)
    if len(chain) == 1:
        return chain[0][1]
    return FallbackProvider(chain)


class FallbackProvider(LLMProvider):
    """Try providers in order; on quota/failure, move to the next.

    Once a provider hits its quota, it's skipped for the rest of the run (daily
    limits persist), so we don't waste a doomed call on every request.
    """

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
                print(f"      [engine] {name} quota exhausted -> trying next")
                self._exhausted.add(name)
                errors.append(f"{name}: {e}")
            except Exception as e:  # network / 5xx / ollama down -> try next
                print(f"      [engine] {name} failed ({type(e).__name__}) -> trying next")
                errors.append(f"{name}: {e}")
        raise QuotaExceeded("All engines failed -> " + " | ".join(errors))

    def complete(self, system: str, user: str) -> str:
        return self._run("complete", system, user)

    def complete_json(self, system: str, user: str) -> dict:
        return self._run("complete_json", system, user)
