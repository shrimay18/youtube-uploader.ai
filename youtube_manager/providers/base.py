"""Provider interface: one method that returns parsed JSON from a prompt."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod


class QuotaExceeded(Exception):
    """Raised when the LLM provider reports a rate/quota limit (e.g. HTTP 429).

    Propagated to the top so a draft aborts cleanly instead of writing garbage.
    """


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Return the raw model text for a system + user prompt."""
        raise NotImplementedError

    def complete_json(self, system: str, user: str) -> dict:
        """Call complete() and coerce the reply into a dict.

        Models sometimes wrap JSON in ```json fences or add prose; we extract
        the first balanced {...} block and parse it. On a parse failure we retry
        once with a stricter nudge, since real models occasionally misformat.
        """
        raw = self.complete(system, user)
        try:
            return extract_json(raw)
        except (ValueError, json.JSONDecodeError):
            retry = self.complete(
                system,
                user + "\n\nIMPORTANT: reply with ONLY one complete, valid JSON object. "
                "No prose, no markdown fences, no trailing commentary.",
            )
            return extract_json(retry)


def extract_json(text: str) -> dict:
    """Best-effort: pull the first JSON object out of a model reply."""
    text = text.strip()

    # Strip code fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    # Fast path.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: find the first balanced brace span.
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in model reply:\n{text[:500]}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                return json.loads(candidate)

    # Truncated reply (model hit the token limit mid-object): repair by closing
    # any open string/brackets so we salvage the complete fields instead of losing all.
    repaired = _repair_truncated_json(text[start:])
    if repaired is not None:
        return repaired
    raise ValueError(f"Unbalanced JSON in model reply:\n{text[:500]}")


def _repair_truncated_json(s: str):
    """Best-effort close of a truncated JSON object. Returns dict or None."""
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch in "{[":
                stack.append(ch)
            elif ch in "}]" and stack:
                stack.pop()

    repaired = s
    if in_str:
        repaired += '"'                       # close a dangling string
    repaired = repaired.rstrip()
    if repaired.endswith(","):
        repaired = repaired[:-1]              # drop a trailing comma
    for opener in reversed(stack):
        repaired += "}" if opener == "{" else "]"
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None
