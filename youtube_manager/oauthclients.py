"""OAuth client resolution (P2).

Two kinds of client, each pinning uploads to a different project's quota:
  - `app`  : the shared app client (env GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) —
             the shared ~6/day pool.
  - `user` : a client the user created in their own Google Cloud project — their own
             quota. Stored per-user; the secret is encrypted at rest (KeyCrypto).

Store holds ciphertext only (opaque); the caller supplies KeyCrypto to enc/dec.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OAuthClient:
    client_id: str
    client_secret: str
    kind: str            # 'app' | 'user'


def app_client() -> OAuthClient | None:
    """The shared app client from the backend env (never shipped to the frontend)."""
    cid = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
    sec = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
    return OAuthClient(cid, sec, "app") if cid and sec else None


class UserClientStore(ABC):
    @abstractmethod
    def get(self, user_id: str) -> dict | None:
        """Return {'client_id', 'client_secret_ciphertext'} or None."""

    @abstractmethod
    def put(self, user_id: str, client_id: str, client_secret_ciphertext: str) -> None: ...

    @abstractmethod
    def delete(self, user_id: str) -> None: ...


class InMemoryUserClientStore(UserClientStore):
    def __init__(self):
        self._d: dict[str, dict] = {}

    def get(self, user_id):
        r = self._d.get(user_id)
        return dict(r) if r else None

    def put(self, user_id, client_id, client_secret_ciphertext):
        self._d[user_id] = {"client_id": client_id,
                            "client_secret_ciphertext": client_secret_ciphertext}

    def delete(self, user_id):
        self._d.pop(user_id, None)


def user_client(store: UserClientStore, crypto, user_id: str) -> OAuthClient | None:
    """Decrypt and return the user's own OAuth client, or None if they haven't added one."""
    row = store.get(user_id)
    if not row:
        return None
    try:
        secret = crypto.dec(row["client_secret_ciphertext"])
    except Exception:
        return None
    return OAuthClient(row["client_id"], secret, "user")


def save_user_client(store: UserClientStore, crypto, user_id: str,
                     client_id: str, client_secret: str) -> None:
    store.put(user_id, client_id.strip(), crypto.enc(client_secret.strip()))
