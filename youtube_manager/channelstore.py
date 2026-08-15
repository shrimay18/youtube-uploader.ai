"""Connected YouTube channels (P2) — server-side, per-user.

Replaces the local encrypted `youtube_accounts.enc` file. Each row is one
authorization of one channel by one client kind, so a channel can hold BOTH an
`app` connection (shared quota) and a `user` connection (own quota) — which is
exactly what the single-upload shared→BYO fallback needs.

Rows hold the refresh token as ciphertext (opaque to the store); the caller
supplies KeyCrypto. Key: (user_id, channel_id, client_kind).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ChannelStore(ABC):
    @abstractmethod
    def list_for(self, user_id: str) -> list[dict]:
        """All connection rows for a user."""

    @abstractmethod
    def upsert(self, row: dict) -> None:
        """Insert/replace one connection (row has user_id, channel_id, client_kind, …)."""

    @abstractmethod
    def delete(self, user_id: str, channel_id: str, client_kind: str | None = None) -> None:
        """Remove a channel's connection(s); client_kind=None removes both kinds."""


class InMemoryChannelStore(ChannelStore):
    def __init__(self):
        self._rows: list[dict] = []

    def _key(self, r):
        return (r["user_id"], r["channel_id"], r["client_kind"])

    def list_for(self, user_id):
        return [dict(r) for r in self._rows if r["user_id"] == user_id]

    def upsert(self, row):
        self._rows = [r for r in self._rows if self._key(r) != self._key(row)]
        self._rows.append(dict(row))

    def delete(self, user_id, channel_id, client_kind=None):
        self._rows = [r for r in self._rows if not (
            r["user_id"] == user_id and r["channel_id"] == channel_id
            and (client_kind is None or r["client_kind"] == client_kind))]


class SupabaseChannelStore(ChannelStore):
    """Prod store: Supabase REST with the service_role key. Requires the 0004 migration.
    Unique constraint on (user_id, channel_id, client_kind) powers the upsert."""

    _COLS = "user_id,channel_id,client_kind,title,handle,thumbnail,refresh_token_ciphertext"

    def __init__(self, url: str, service_key: str, timeout: int = 20):
        self.base = url.rstrip("/") + "/rest/v1"
        self.key = service_key
        self.timeout = timeout

    def _h(self, extra=None):
        h = {"apikey": self.key, "Authorization": f"Bearer {self.key}",
             "Content-Type": "application/json"}
        if extra:
            h.update(extra)
        return h

    def list_for(self, user_id):
        import requests
        r = requests.get(f"{self.base}/channel_connections", headers=self._h(),
                         params={"user_id": f"eq.{user_id}", "select": self._COLS},
                         timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def upsert(self, row):
        import requests
        requests.post(
            f"{self.base}/channel_connections",
            headers=self._h({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            json=row, timeout=self.timeout,
        ).raise_for_status()

    def delete(self, user_id, channel_id, client_kind=None):
        import requests
        params = {"user_id": f"eq.{user_id}", "channel_id": f"eq.{channel_id}"}
        if client_kind is not None:
            params["client_kind"] = f"eq.{client_kind}"
        requests.delete(f"{self.base}/channel_connections", headers=self._h(),
                        params=params, timeout=self.timeout).raise_for_status()
