"""Persistent "fixed" boilerplate — the description block and pinned comment the
creator wants added to every upload.

Set once, applied always. Stored ENCRYPTED at rest with the logged-in user's vault
key (same envelope as connected YouTube accounts), so it survives across sessions,
browsers and devices and never sits in plaintext — the user is never asked to
retype it per video.
"""
from __future__ import annotations

import json

from . import config, vault

STORE = config.CONFIG_DIR / "fixed_content.enc"

_POSITIONS = ("top", "bottom", "auto")
_MODES = ("ai", "fixed", "integrate")

DEFAULT = {"desc_text": "", "desc_position": "auto", "comment_text": "", "comment_mode": "ai"}


def get() -> dict:
    """Stored fixed content, or empty defaults. Raises PermissionError if locked."""
    if not STORE.exists():
        return dict(DEFAULT)
    try:
        data = json.loads(vault.decrypt_str(STORE.read_text(encoding="utf-8")))
        return _clean(data or {})
    except PermissionError:
        raise
    except Exception:
        return dict(DEFAULT)


def save(data: dict) -> dict:
    """Persist (encrypted) and return the cleaned value."""
    clean = _clean(data or {})
    STORE.write_text(vault.encrypt_str(json.dumps(clean)), encoding="utf-8")
    return clean


def purge() -> None:
    """Delete the stored fixed content (used by account reset). No auth needed."""
    STORE.unlink(missing_ok=True)


def _clean(data: dict) -> dict:
    pos = str(data.get("desc_position") or "auto")
    mode = str(data.get("comment_mode") or "ai")
    return {
        "desc_text": str(data.get("desc_text") or ""),
        "desc_position": pos if pos in _POSITIONS else "auto",
        "comment_text": str(data.get("comment_text") or ""),
        "comment_mode": mode if mode in _MODES else "ai",
    }
