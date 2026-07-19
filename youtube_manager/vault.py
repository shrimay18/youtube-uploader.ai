"""Local encrypted key vault + single-user auth.

Everything stays on THIS device. On first run the user sets a password and enters
their own API keys; the keys are encrypted at rest with a key derived from that
password (scrypt) and never leave the machine. On login we decrypt them into the
process environment so the pipeline can use them. There is no server, no cloud, and
the creator never sees anything.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path

from . import config

ACCOUNT = config.CONFIG_DIR / "account.json"
KEY_FIELDS = ("GEMINI_API_KEY", "GROQ_API_KEY", "YOUTUBE_API_KEY", "ANTHROPIC_API_KEY")

# Google accounts don't have a password to derive a key from, so their vault key
# is a random secret kept in the OS keychain (Windows Credential Manager / macOS
# Keychain / Secret Service). It never leaves the device and is never uploaded.
KEYRING_SERVICE = "youtube_manager.ai"

# In-memory session (single-user, local): holds the decrypted state after login.
_STATE: dict = {"authed": False, "fkey": None, "keys": {}}


def account_exists() -> bool:
    return ACCOUNT.exists()


def is_authed() -> bool:
    return bool(_STATE["authed"])


def _derive(password: str, salt: bytes) -> bytes:
    raw = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return base64.urlsafe_b64encode(raw)


def _fernet(fkey: bytes):
    from cryptography.fernet import Fernet
    return Fernet(fkey)


def account_method() -> str | None:
    if not ACCOUNT.exists():
        return None
    try:
        return json.loads(ACCOUNT.read_text(encoding="utf-8")).get("method", "password")
    except Exception:
        return "password"


def account_email() -> str:
    if not ACCOUNT.exists():
        return ""
    try:
        return json.loads(ACCOUNT.read_text(encoding="utf-8")).get("email", "")
    except Exception:
        return ""


def _write(salt: bytes, fkey: bytes, keys: dict, method: str = "password", email: str = "") -> None:
    f = _fernet(fkey)
    enc = {k: f.encrypt(v.encode()).decode() for k, v in keys.items() if v}
    ACCOUNT.write_text(json.dumps({
        "method": method, "email": email,
        "salt": base64.b64encode(salt).decode(),
        "verifier": f.encrypt(b"youtube_manager.ai").decode(),
        "keys": enc,
    }), encoding="utf-8")


def setup(secret: str, keys: dict, method: str = "password", email: str = "") -> None:
    """Create the account (first run) and log in. `secret` is a password or a Google sub."""
    if method == "password" and (not secret or len(secret) < 6):
        raise ValueError("Password must be at least 6 characters.")
    salt = secrets.token_bytes(16)
    fkey = _derive(secret, salt)
    # Use provided keys; fall back to any existing env/.env value (dev convenience).
    resolved = {}
    for k in KEY_FIELDS:
        v = (keys.get(k) or "").strip() or os.environ.get(k, "")
        if v:
            resolved[k] = v
    _write(salt, fkey, resolved, method=method, email=email)
    _activate(fkey, resolved)


def _keyring_user(email: str) -> str:
    return (email or "vault").strip().lower()


def _store_fkey(email: str, fkey: bytes) -> None:
    import keyring
    keyring.set_password(KEYRING_SERVICE, _keyring_user(email), fkey.decode())


def _load_fkey(email: str) -> bytes | None:
    import keyring
    try:
        v = keyring.get_password(KEYRING_SERVICE, _keyring_user(email))
    except Exception:
        return None
    return v.encode() if v else None


def google_setup(email: str, keys: dict | None = None) -> None:
    """Create (or re-key) a Google-signed account whose vault key lives in the OS keychain."""
    fkey = base64.urlsafe_b64encode(secrets.token_bytes(32))
    _store_fkey(email, fkey)
    salt = secrets.token_bytes(16)  # unused for google auth; keeps the file format uniform
    resolved = {}
    for k in KEY_FIELDS:
        v = (keys or {}).get(k)
        v = (v or "").strip() or os.environ.get(k, "")
        if v:
            resolved[k] = v
    _write(salt, fkey, resolved, method="google", email=email)
    _activate(fkey, resolved)


def google_unlock(email: str) -> bool:
    """Decrypt an existing Google vault using the keychain-held key. False if unavailable."""
    if not ACCOUNT.exists():
        return False
    fkey = _load_fkey(email)
    if not fkey:
        return False
    data = json.loads(ACCOUNT.read_text(encoding="utf-8"))
    f = _fernet(fkey)
    try:
        f.decrypt(data["verifier"].encode())
    except Exception:
        return False
    keys = {}
    for k, v in (data.get("keys") or {}).items():
        try:
            keys[k] = f.decrypt(v.encode()).decode()
        except Exception:
            pass
    _activate(fkey, keys)
    return True


def supabase_login(email: str, keys: dict | None = None) -> bool:
    """Unlock (or first-time create) the local vault after a verified Supabase sign-in.

    Keys never leave the device: an existing Google vault is decrypted with the
    keychain key; otherwise a fresh vault is created from the provided keys (or any
    detected env/.env values). Returns True once the vault is active.
    """
    same = (account_exists() and account_method() == "google"
            and account_email().strip().lower() == (email or "").strip().lower())
    if same and google_unlock(email):
        return True
    # First sign-in on this device, a switched account, or a missing keychain entry.
    google_setup(email, keys)
    return True


def login(password: str) -> bool:
    """Verify password, decrypt keys, load them into the environment."""
    if not ACCOUNT.exists():
        return False
    data = json.loads(ACCOUNT.read_text(encoding="utf-8"))
    salt = base64.b64decode(data["salt"])
    fkey = _derive(password, salt)
    from cryptography.fernet import InvalidToken
    f = _fernet(fkey)
    try:
        f.decrypt(data["verifier"].encode())
    except (InvalidToken, Exception):
        return False
    keys = {}
    for k, v in (data.get("keys") or {}).items():
        try:
            keys[k] = f.decrypt(v.encode()).decode()
        except Exception:
            pass
    _activate(fkey, keys)
    return True


def _activate(fkey: bytes, keys: dict) -> None:
    _STATE["authed"] = True
    _STATE["fkey"] = fkey
    _STATE["keys"] = keys
    for k, v in keys.items():
        if v:
            os.environ[k] = v


def logout() -> None:
    for k in KEY_FIELDS:
        os.environ.pop(k, None)
    _STATE.update({"authed": False, "fkey": None, "keys": {}})


def reset() -> None:
    """Delete the account so the user can set it up again (e.g. switch to Google)."""
    email = account_email()
    logout()
    if email:
        try:
            import keyring
            keyring.delete_password(KEYRING_SERVICE, _keyring_user(email))
        except Exception:
            pass
    try:
        ACCOUNT.unlink(missing_ok=True)
    except OSError:
        pass


def update_keys(new_keys: dict) -> None:
    """Update stored keys (requires an active session). Only non-empty values change."""
    if not _STATE["authed"] or not _STATE["fkey"]:
        raise PermissionError("Not logged in.")
    keys = dict(_STATE["keys"])
    for k, v in new_keys.items():
        if k in KEY_FIELDS and v is not None:
            v = v.strip()
            if v:
                keys[k] = v
            else:
                keys.pop(k, None)
    data = json.loads(ACCOUNT.read_text(encoding="utf-8"))
    salt = base64.b64decode(data["salt"])
    _write(salt, _STATE["fkey"], keys)
    # refresh env
    for k in KEY_FIELDS:
        os.environ.pop(k, None)
    _activate(_STATE["fkey"], keys)


def encrypt_str(plaintext: str) -> str:
    """Encrypt a string with the active session key (for local token storage)."""
    if not _STATE["authed"] or not _STATE["fkey"]:
        raise PermissionError("Not logged in.")
    return _fernet(_STATE["fkey"]).encrypt(plaintext.encode()).decode()


def decrypt_str(ciphertext: str) -> str:
    """Decrypt a string previously produced by encrypt_str."""
    if not _STATE["authed"] or not _STATE["fkey"]:
        raise PermissionError("Not logged in.")
    return _fernet(_STATE["fkey"]).decrypt(ciphertext.encode()).decode()


def masked_keys() -> dict:
    """Which keys are set (masked) — for the settings UI. Never returns raw values."""
    out = {}
    for k in KEY_FIELDS:
        v = _STATE["keys"].get(k, "")
        out[k] = (v[:4] + "…" + v[-4:]) if v and len(v) > 8 else ("set" if v else "")
    return out
