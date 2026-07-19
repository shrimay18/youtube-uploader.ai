"""Connected YouTube accounts — add as many as you like, publish to several at once.

Each account holds its OAuth token plus a per-account "voice" profile (niche / tone
that shapes generation). The whole store is encrypted at rest with the logged-in
user's vault key, so tokens never sit in plaintext and never leave the device.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config, vault, youtube

STORE = config.CONFIG_DIR / "youtube_accounts.enc"

# Fields safe to expose to the frontend (everything except the token).
_PUBLIC = ("id", "title", "handle", "thumbnail")


def _read() -> list[dict]:
    if not STORE.exists():
        return []
    try:
        return json.loads(vault.decrypt_str(STORE.read_text(encoding="utf-8")))
    except PermissionError:
        raise
    except Exception:
        return []


def _write(accounts: list[dict]) -> None:
    STORE.write_text(vault.encrypt_str(json.dumps(accounts)), encoding="utf-8")


def _default_profile() -> dict:
    """Seed a new account's voice from the default channel profile so it works immediately."""
    try:
        return dict(config.channel_profile(config.default_channel()))
    except Exception:
        return {"niche": "", "audience": "", "tone": "", "default_cta": ""}


def _public(a: dict) -> dict:
    out = {k: a.get(k, "") for k in _PUBLIC}
    prof = a.get("profile", {}) or {}
    out["profile"] = prof
    out["profile_ok"] = not config.check_profile(prof)
    return out


def list_public() -> list[dict]:
    """Connected accounts without tokens — for the UI."""
    return [_public(a) for a in _read()]


def connect() -> dict:
    """Run OAuth, identify the channel, store it (encrypted). Returns the public account."""
    token_json = youtube.oauth_connect()
    service, _ = youtube.service_from_token(token_json)
    info = youtube.channel_details(service)
    if not info.get("id"):
        raise ValueError("That Google account has no YouTube channel. Pick an account with a channel.")

    accounts = _read()
    existing = next((a for a in accounts if a.get("id") == info["id"]), None)
    if existing:
        existing.update({**info, "token": token_json})  # re-auth / refresh
        account = existing
    else:
        account = {**info, "token": token_json, "profile": _default_profile()}
        accounts.append(account)
    _write(accounts)
    return _public(account)


def remove(account_id: str) -> None:
    _write([a for a in _read() if a.get("id") != account_id])


def token_for(account_id: str) -> str | None:
    a = next((a for a in _read() if a.get("id") == account_id), None)
    return a.get("token") if a else None


def get(account_id: str) -> dict | None:
    return next((a for a in _read() if a.get("id") == account_id), None)


def profile_for(account_id: str) -> dict | None:
    a = get(account_id)
    return a.get("profile") if a else None


def set_profile(account_id: str, profile: dict) -> bool:
    accounts = _read()
    a = next((a for a in accounts if a.get("id") == account_id), None)
    if not a:
        return False
    a["profile"] = {**(a.get("profile") or {}), **profile}
    _write(accounts)
    return True


def label_for(account_id: str) -> str:
    a = get(account_id)
    return (a.get("title") if a else "") or "YouTube"
