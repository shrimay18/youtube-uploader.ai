"""YouTube OAuth 2.0 — hosted web flow (P2).

Replaces the local loopback flow (`run_local_server`, which only works on a device)
with a stateless redirect-based code exchange suitable for a server:

  1. build_auth_url(...)      -> send the user to Google's consent screen
  2. Google redirects back to your /oauth/callback with ?code=...&state=...
  3. exchange_code(...)       -> access_token + refresh_token (store the refresh token)
  4. refresh_access_token(...) -> a fresh access token at upload time

Plain OAuth2 endpoints via `requests`, so it's easy to mock/test and carries no
device-only assumptions. The refresh/exchange use the SAME client that authorized
the channel (this is what pins a channel's uploads to the right quota project).
"""
from __future__ import annotations

from urllib.parse import urlencode

import requests

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def build_auth_url(client_id: str, redirect_uri: str, state: str,
                   scopes: list[str] | None = None) -> str:
    """Consent URL. access_type=offline + prompt=consent => we always get a refresh token."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes or SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URI}?{urlencode(params)}"


def exchange_code(client_id: str, client_secret: str, redirect_uri: str,
                  code: str, timeout: int = 20) -> dict:
    """Swap the callback `code` for tokens. Returns access_token / refresh_token / expires_in."""
    r = requests.post(TOKEN_URI, data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str,
                         timeout: int = 20) -> dict:
    """Get a fresh access token from a stored refresh token, using the authorizing client."""
    r = requests.post(TOKEN_URI, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()
