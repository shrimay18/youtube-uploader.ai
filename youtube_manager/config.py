"""Config loading + shared paths.

Central place that resolves the repo root, loads settings.yaml and
channel_profile.yaml, and exposes the folders the pipeline writes to.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

# Repo root = parent of this package.
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


def _load_dotenv() -> None:
    """Load ROOT/.env into os.environ so secrets stay in a gitignored file.

    Values in .env take precedence, making the file the single source of truth
    you manage. Tiny parser (KEY=VALUE, # comments, optional quotes) — no dep.
    """
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.split(" #", 1)[0].strip().strip('"').strip("'")
        if key:
            os.environ[key] = val


_load_dotenv()  # run once at import so every entry point gets the keys


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing config file: {path}. Copy the template in config/ and fill it in."
        )
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=1)
def settings() -> dict:
    return _load_yaml(CONFIG_DIR / "settings.yaml")


def supabase_config() -> dict:
    """Public Supabase config (url + anon/publishable key). Env overrides YAML."""
    sb = settings().get("supabase", {}) or {}
    return {
        "url": (os.environ.get("SUPABASE_URL") or sb.get("url") or "").rstrip("/"),
        "anon_key": os.environ.get("SUPABASE_ANON_KEY") or sb.get("anon_key") or "",
    }


def admin_config() -> dict:
    """Admin-only config. The service key (full DB read) must come from the
    environment (.env) and only exists on the creator's machine — never shipped.

    Returns {service_key, admin_emails}. When service_key is empty the admin
    dashboard stays completely dormant.
    """
    sb = settings().get("supabase", {}) or {}
    # Admin emails are PII, so they live in .env (TM_ADMIN_EMAILS, comma-separated)
    # and are kept out of the committed YAML. Fall back to YAML for backward compat.
    env_emails = os.environ.get("TM_ADMIN_EMAILS", "")
    emails = [e for e in env_emails.split(",")] if env_emails.strip() else (sb.get("admin_emails") or [])
    if isinstance(emails, str):
        emails = [emails]
    return {
        "service_key": os.environ.get("SUPABASE_SERVICE_KEY", "").strip(),
        "admin_emails": [str(e).strip().lower() for e in emails if e],
    }


def is_admin(email: str | None) -> bool:
    cfg = admin_config()
    return bool(cfg["service_key"]) and (email or "").strip().lower() in cfg["admin_emails"]


# ---- Channels ----------------------------------------------------------

def channels() -> dict:
    """Map of channel_key -> {label, handle, profile} from settings.yaml."""
    return settings().get("channels", {}) or {}


def default_channel() -> str:
    """The channel key used when --channel is omitted."""
    ch = channels()
    dc = settings().get("default_channel")
    if dc and dc in ch:
        return dc
    if ch:
        return next(iter(ch))            # first configured channel
    return "default"                     # single-channel fallback (no channels block)


def resolve_channel(name: str | None) -> str:
    """Normalize a user-supplied channel name/key to a configured channel key."""
    ch = channels()
    if not name:
        return default_channel()
    if name in ch:
        return name
    # Allow matching by label or handle (case-insensitive).
    low = name.strip().lower().lstrip("@")
    for key, cfg in ch.items():
        label = str(cfg.get("label", "")).strip().lower()
        handle = str(cfg.get("handle", "")).strip().lower().lstrip("@")
        if low in (key.lower(), label, handle):
            return key
    raise ValueError(
        f"Unknown channel '{name}'. Configured channels: {', '.join(ch) or '(none)'}. "
        "Add it under `channels:` in config/settings.yaml."
    )


def channel_label(channel_key: str) -> str:
    cfg = channels().get(channel_key, {})
    return cfg.get("label") or channel_key


def _profile_path(channel_key: str | None) -> Path:
    """Resolve which profile file a channel uses; fall back to the shared one."""
    if channel_key:
        cfg = channels().get(channel_key, {})
        fname = cfg.get("profile")
        if fname:
            return CONFIG_DIR / fname
    return CONFIG_DIR / "channel_profile.yaml"


def channel_profile(channel_key: str | None = None) -> dict:
    """Load the profile for a channel (or the default shared profile)."""
    return _load_yaml(_profile_path(channel_key))


def load_profile_override(path_or_name: str) -> dict:
    """Load an arbitrary profile file for a one-off draft (--profile).

    Accepts a bare filename (resolved under config/) or a full/relative path.
    Lets you run a single video against a different niche without touching the
    channel's saved profile — ideal for niche switches / A-B tests.
    """
    p = Path(path_or_name).expanduser()
    if not p.is_absolute() and not p.exists():
        p = CONFIG_DIR / path_or_name          # allow "channel_profile.new.yaml"
    return _load_yaml(p)


def check_profile(p: dict) -> list[str]:
    """Return the list of required fields still empty/'???' in a profile dict."""
    required = ["niche", "audience", "tone", "default_cta"]
    return [k for k in required if not p.get(k) or str(p.get(k)).strip() in ("", "???")]


def profile_is_filled(channel_key: str | None = None) -> tuple[bool, list[str]]:
    """Return (ok, missing_fields). '???' or empty required fields count as missing."""
    missing = check_profile(channel_profile(channel_key))
    return (len(missing) == 0, missing)


@dataclass(frozen=True)
class Paths:
    root: Path
    drafts: Path
    downloads: Path


def paths() -> Paths:
    s = settings().get("paths", {})
    drafts = ROOT / s.get("drafts", "drafts")
    downloads = ROOT / s.get("downloads", "downloads")
    drafts.mkdir(parents=True, exist_ok=True)
    downloads.mkdir(parents=True, exist_ok=True)
    return Paths(root=ROOT, drafts=drafts, downloads=downloads)


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def youtube_api_keys() -> list[str]:
    """App-level YouTube Data API keys for READ/SEO research, rotated on quota.

    Reads YOUTUBE_API_KEY (may be comma-separated) plus YOUTUBE_API_KEY_2..7.
    NOTE: these are for search/videos.list only — uploads use OAuth and their
    quota is charged to the OAuth client's project, not to these keys.
    """
    raw: list[str] = []
    raw += (os.environ.get("YOUTUBE_API_KEY", "") or "").split(",")
    for i in range(2, 8):
        raw.append(os.environ.get(f"YOUTUBE_API_KEY_{i}", "") or "")
    out: list[str] = []
    for k in (s.strip() for s in raw):
        if k and k not in out:
            out.append(k)
    return out
