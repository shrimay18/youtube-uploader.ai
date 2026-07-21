"""Local encrypted key vault + single-user auth.

Everything stays on THIS device. Keys are encrypted at rest with a key derived from
the user's password (scrypt) or a random key in the OS keychain (Google accounts).
On login we decrypt them into the process environment / in-memory state so the
pipeline can use them. No server, no cloud — the creator never sees anything.

Keys model (v2): the user can store MULTIPLE keys per LLM provider (rotated on
quota), an optional single YouTube Data API key, and an ordered engine PREFERENCE.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets

from . import config

ACCOUNT = config.CONFIG_DIR / "account.json"

# LLM providers the user can add keys for, + the env var that holds their PRIMARY key.
PROVIDERS = ("gemini", "openai", "anthropic", "groq")
ENV_MAP = {
    "gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY", "groq": "GROQ_API_KEY",
}
# Default preference order (best first). Only providers with a key are actually used.
DEFAULT_ORDER = ["anthropic", "gemini", "openai", "groq"]

KEYRING_SERVICE = "youtube_manager.ai"

# In-memory session (single-user, local).
_STATE: dict = {"authed": False, "fkey": None, "llm": {}, "youtube": "", "order": list(DEFAULT_ORDER), "custom": []}


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


# ---- storage helpers ---------------------------------------------------------

def _empty_llm() -> dict:
    return {p: [] for p in PROVIDERS}


def _seed_from_env() -> tuple[dict, str]:
    """Pick up any keys already in the environment/.env (dev convenience)."""
    llm = _empty_llm()
    for p in PROVIDERS:
        v = (os.environ.get(ENV_MAP[p]) or "").strip()
        if v:
            llm[p] = [v]
    return llm, (os.environ.get("YOUTUBE_API_KEY") or "").strip()


def _write(salt: bytes, fkey: bytes, llm: dict, youtube: str, order: list,
           custom: list | None = None, method: str = "password", email: str = "") -> None:
    f = _fernet(fkey)
    enc_llm = {p: [f.encrypt(k.encode()).decode() for k in (llm.get(p) or []) if k] for p in PROVIDERS}
    enc_custom = [
        {"id": c.get("id") or ("x" + secrets.token_hex(3)), "name": c.get("name", "Custom"),
         "base": c.get("base", ""), "model": c.get("model", ""),
         "key": f.encrypt(c["key"].encode()).decode()}
        for c in (custom or []) if c.get("key")
    ]
    ACCOUNT.write_text(json.dumps({
        "v": 2, "method": method, "email": email,
        "salt": base64.b64encode(salt).decode(),
        "verifier": f.encrypt(b"youtube_manager.ai").decode(),
        "llm": enc_llm,
        "youtube": f.encrypt(youtube.encode()).decode() if youtube else "",
        "order": list(order) or list(DEFAULT_ORDER),   # may include custom provider ids
        "custom": enc_custom,
    }), encoding="utf-8")


def _decrypt_all(fkey: bytes, data: dict) -> tuple[dict, str, list, list]:
    """Decrypt the stored config; migrates the old single-key `keys` format."""
    f = _fernet(fkey)

    def dec(v):
        try:
            return f.decrypt(v.encode()).decode()
        except Exception:
            return ""

    if "llm" not in data and "keys" in data:  # migrate legacy v1
        legacy = {k: dec(v) for k, v in (data.get("keys") or {}).items()}
        llm = _empty_llm()
        for p, ev in ENV_MAP.items():
            if legacy.get(ev):
                llm[p] = [legacy[ev]]
        return llm, legacy.get("YOUTUBE_API_KEY", ""), list(DEFAULT_ORDER), []

    llm = _empty_llm()
    for p in PROVIDERS:
        llm[p] = [dec(k) for k in (data.get("llm", {}).get(p) or []) if dec(k)]
    youtube = dec(data["youtube"]) if data.get("youtube") else ""
    order = list(data.get("order") or []) or list(DEFAULT_ORDER)
    custom = []
    for i, c in enumerate(data.get("custom") or []):
        k = dec(c.get("key", ""))
        if k:
            custom.append({"id": c.get("id") or ("x%d" % i), "name": c.get("name", "Custom"),
                           "base": c.get("base", ""), "model": c.get("model", ""), "key": k})
    return llm, youtube, order, custom


def _load_and_activate(fkey: bytes, data: dict) -> None:
    """Decrypt stored config and activate, filling empty providers from .env (dev)."""
    llm, youtube, order, custom = _decrypt_all(fkey, data)
    for p in PROVIDERS:
        if not llm.get(p):
            v = (os.environ.get(ENV_MAP[p]) or "").strip()
            if v:
                llm[p] = [v]
    _activate(fkey, llm, youtube, order, custom)


def _activate(fkey: bytes, llm: dict, youtube: str, order: list, custom: list | None = None) -> None:
    _STATE.update(authed=True, fkey=fkey, llm=llm, youtube=youtube, order=order, custom=custom or [])
    for p in PROVIDERS:
        ev, ks = ENV_MAP[p], (llm.get(p) or [])
        if ks:
            os.environ[ev] = ks[0]
        else:
            os.environ.pop(ev, None)
    # NOTE: YOUTUBE_API_KEY is OUR app-level key (from the deployment env / .env),
    # not a per-user key — the vault never sets or clears it.


# ---- account lifecycle -------------------------------------------------------

def setup(secret: str, keys: dict | None = None, method: str = "password", email: str = "") -> None:
    """Create the account (first run) and log in. `secret` is a password or Google sub."""
    if method == "password" and (not secret or len(secret) < 6):
        raise ValueError("Password must be at least 6 characters.")
    salt = secrets.token_bytes(16)
    fkey = _derive(secret, salt)
    llm, youtube = _seed_from_env()
    for p, ev in ENV_MAP.items():  # accept legacy {GEMINI_API_KEY: ...} on setup
        v = ((keys or {}).get(ev) or "").strip()
        if v and v not in llm[p]:
            llm[p].append(v)
    _write(salt, fkey, llm, youtube, list(DEFAULT_ORDER), method=method, email=email)
    _activate(fkey, llm, youtube, list(DEFAULT_ORDER))


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
    """Create a Google-signed account whose vault key lives in the OS keychain."""
    fkey = base64.urlsafe_b64encode(secrets.token_bytes(32))
    _store_fkey(email, fkey)
    salt = secrets.token_bytes(16)  # unused for google auth; keeps the file format uniform
    llm, youtube = _seed_from_env()
    for p, ev in ENV_MAP.items():
        v = ((keys or {}).get(ev) or "").strip()
        if v and v not in llm[p]:
            llm[p].append(v)
    _write(salt, fkey, llm, youtube, list(DEFAULT_ORDER), method="google", email=email)
    _activate(fkey, llm, youtube, list(DEFAULT_ORDER))


def google_unlock(email: str) -> bool:
    if not ACCOUNT.exists():
        return False
    fkey = _load_fkey(email)
    if not fkey:
        return False
    data = json.loads(ACCOUNT.read_text(encoding="utf-8"))
    try:
        _fernet(fkey).decrypt(data["verifier"].encode())
    except Exception:
        return False
    _load_and_activate(fkey, data)
    return True


def supabase_login(email: str, keys: dict | None = None) -> bool:
    same = (account_exists() and account_method() == "google"
            and account_email().strip().lower() == (email or "").strip().lower())
    if same and google_unlock(email):
        return True
    google_setup(email, keys)
    return True


def login(password: str) -> bool:
    if not ACCOUNT.exists():
        return False
    data = json.loads(ACCOUNT.read_text(encoding="utf-8"))
    salt = base64.b64decode(data["salt"])
    fkey = _derive(password, salt)
    from cryptography.fernet import InvalidToken
    try:
        _fernet(fkey).decrypt(data["verifier"].encode())
    except (InvalidToken, Exception):
        return False
    _load_and_activate(fkey, data)
    return True


def logout() -> None:
    for ev in ENV_MAP.values():   # leave YOUTUBE_API_KEY — it's the app's, not the user's
        os.environ.pop(ev, None)
    _STATE.update({"authed": False, "fkey": None, "llm": {}, "youtube": "", "order": list(DEFAULT_ORDER)})


def reset() -> None:
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


# ---- key management (settings / onboarding) ----------------------------------

def save_config(order: list | None = None, youtube=None, llm_ops: dict | None = None,
                custom: dict | None = None) -> None:
    """Update keys/order (requires an active session).

    `llm_ops` = {provider: {"keep": [indexes to keep], "add": [raw new keys]}}.
    `custom` = {"keep": [indexes], "add": [{name, base, model, key}]} for OpenAI-compatible extras.
    `youtube`: None = keep, "" = clear, otherwise set. `order`: new preference or None to keep.
    """
    if not _STATE["authed"] or not _STATE["fkey"]:
        raise PermissionError("Not logged in.")
    llm_ops = llm_ops or {}
    new_llm = _empty_llm()
    for p in PROVIDERS:
        existing = _STATE["llm"].get(p) or []
        ops = llm_ops.get(p) or {}
        kept = [existing[i] for i in ops.get("keep", []) if isinstance(i, int) and 0 <= i < len(existing)]
        added = [k.strip() for k in ops.get("add", []) if k and k.strip()]
        seen, merged = set(), []
        for k in kept + added:
            if k not in seen:
                seen.add(k); merged.append(k)
        new_llm[p] = merged

    if custom is None:
        new_custom = list(_STATE["custom"] or [])
    else:
        existing_c = _STATE["custom"] or []
        new_custom = [existing_c[i] for i in custom.get("keep", []) if isinstance(i, int) and 0 <= i < len(existing_c)]
        for e in custom.get("add", []):
            if (e.get("key") or "").strip():
                new_custom.append({
                    "id": (e.get("id") or ("x" + secrets.token_hex(3))),
                    "name": (e.get("name") or "Custom").strip(), "base": (e.get("base") or "").strip(),
                    "model": (e.get("model") or "").strip(), "key": e["key"].strip(),
                })

    yt = _STATE["youtube"] if youtube is None else (youtube or "").strip()
    # order may include custom provider ids; keep valid tokens, ensure the 4 built-ins exist
    valid_custom = {c["id"] for c in new_custom}
    new_order = [t for t in list(order or _STATE["order"]) if t in PROVIDERS or t in valid_custom]
    for p in PROVIDERS:
        if p not in new_order:
            new_order.append(p)
    for cid in valid_custom:
        if cid not in new_order:
            new_order.append(cid)

    data = json.loads(ACCOUNT.read_text(encoding="utf-8"))
    salt = base64.b64decode(data["salt"])
    _write(salt, _STATE["fkey"], new_llm, yt, new_order, custom=new_custom,
           method=data.get("method", "password"), email=data.get("email", ""))
    _activate(_STATE["fkey"], new_llm, yt, new_order, new_custom)


def _mask(v: str) -> str:
    """Show the first few + last few characters so a key is recognizable (never raw)."""
    if not v:
        return ""
    if len(v) > 12:
        return v[:6] + "…" + v[-4:]
    if len(v) > 4:
        return v[:4] + "…"
    return v


def masked_config() -> dict:
    """Masked view for the settings/onboarding UI — never returns raw keys."""
    return {
        "llm": {p: [_mask(k) for k in (_STATE["llm"].get(p) or [])] for p in PROVIDERS},
        "youtube": _mask(_STATE["youtube"]),
        "order": _STATE["order"] or list(DEFAULT_ORDER),
        "providers": list(PROVIDERS),
        "custom": [{"id": c.get("id"), "name": c.get("name", "Custom"), "base": c.get("base", ""),
                    "model": c.get("model", ""), "key": _mask(c.get("key", ""))} for c in (_STATE["custom"] or [])],
        "has_llm": any(_STATE["llm"].get(p) for p in PROVIDERS) or bool(_STATE["custom"]),
    }


def custom_providers() -> list:
    """Custom OpenAI-compatible providers (name/base/model/key). Active session only."""
    return list(_STATE["custom"] or [])


def llm_keys(provider: str) -> list:
    """All keys for a provider (for rotation). Active session only."""
    return list(_STATE["llm"].get(provider) or [])


def engine_order() -> list:
    return list(_STATE["order"] or DEFAULT_ORDER)


def has_llm_key() -> bool:
    return any(_STATE["llm"].get(p) for p in PROVIDERS) or bool(_STATE["custom"])


# ---- generic blob encryption (used by connected YouTube accounts) ------------

def encrypt_str(plaintext: str) -> str:
    if not _STATE["authed"] or not _STATE["fkey"]:
        raise PermissionError("Not logged in.")
    return _fernet(_STATE["fkey"]).encrypt(plaintext.encode()).decode()


def decrypt_str(ciphertext: str) -> str:
    if not _STATE["authed"] or not _STATE["fkey"]:
        raise PermissionError("Not logged in.")
    return _fernet(_STATE["fkey"]).decrypt(ciphertext.encode()).decode()
