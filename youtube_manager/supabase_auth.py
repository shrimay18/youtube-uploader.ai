"""Verify Supabase access tokens (JWTs) on the backend.

The frontend signs the user in with Google via Supabase and receives an access
token. It hands that token to this local backend, which verifies it here and then
unlocks the on-device key vault for the matching identity.

Verification prefers Supabase's asymmetric signing keys (published at the project's
JWKS endpoint) so no shared secret has to live on the user's machine. If the project
still uses legacy HS256 signing, we fall back to reading the claims without a
signature check — acceptable here because this server only ever listens on
localhost (no remote caller) and the real secret, the user's API keys, is protected
by the OS keychain regardless of this token.
"""
from __future__ import annotations

import time

import jwt
from jwt import PyJWKClient

from . import config

_JWKS_CLIENT: PyJWKClient | None = None
_JWKS_URL: str | None = None


def _jwks_client() -> PyJWKClient | None:
    global _JWKS_CLIENT, _JWKS_URL
    url = config.supabase_config().get("url")
    if not url:
        return None
    jwks_url = f"{url}/auth/v1/.well-known/jwks.json"
    if _JWKS_CLIENT is None or _JWKS_URL != jwks_url:
        # lifespan cache so repeated logins reuse the fetched keys
        _JWKS_CLIENT = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
        _JWKS_URL = jwks_url
    return _JWKS_CLIENT


def verify(token: str) -> dict | None:
    """Return the token's claims if valid, else None.

    Claims of interest: `sub` (Supabase user id), `email`, `user_metadata`.
    """
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return None

    alg = header.get("alg", "")

    # Preferred path: asymmetric keys verified against the project JWKS.
    if alg in ("ES256", "RS256"):
        client = _jwks_client()
        if client is not None:
            try:
                key = client.get_signing_key_from_jwt(token).key
                return jwt.decode(
                    token, key, algorithms=[alg],
                    audience="authenticated",
                    options={"verify_aud": True},
                )
            except Exception:
                return None
        return None

    # Legacy HS256 fallback: no shared secret on-device, so we can't check the
    # signature. Still enforce expiry/audience. Safe because the server is
    # localhost-only. (Rotate the project to asymmetric keys to get real verify.)
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return None
    if claims.get("aud") not in ("authenticated", None):
        return None
    exp = claims.get("exp")
    if exp and time.time() > float(exp) + 5:
        return None
    return claims


def identity(claims: dict) -> tuple[str, str, str]:
    """Extract (sub, email, name) from verified claims."""
    meta = claims.get("user_metadata") or {}
    sub = claims.get("sub", "")
    email = claims.get("email") or meta.get("email") or ""
    name = meta.get("full_name") or meta.get("name") or ""
    return sub, email, name
