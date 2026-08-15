"""Persistence for per-user encrypted keys — behind an interface (DIP).

KeyService depends on the KeyStore abstraction, not on Supabase, so it's unit-
tested with InMemoryKeyStore and runs in prod with SupabaseKeyStore. Rows hold
already-encrypted ciphertext; the store never sees plaintext.

Row shape (opaque to the store):
  {provider, ext_id, label, model, base_url, key_ciphertext, position}
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class KeyStore(ABC):
    @abstractmethod
    def load(self, user_id: str) -> dict:
        """Return {"keys": [row, ...], "order": [token, ...]} for a user."""

    @abstractmethod
    def replace(self, user_id: str, keys: list[dict], order: list) -> None:
        """Atomically replace all of a user's key rows + preference order."""


class InMemoryKeyStore(KeyStore):
    """For tests / local dev. Deep-copies in and out so callers can't mutate it."""

    def __init__(self):
        self._data: dict[str, dict] = {}

    def load(self, user_id: str) -> dict:
        d = self._data.get(user_id, {"keys": [], "order": []})
        return {"keys": [dict(r) for r in d["keys"]], "order": list(d["order"])}

    def replace(self, user_id: str, keys: list[dict], order: list) -> None:
        self._data[user_id] = {"keys": [dict(r) for r in keys], "order": list(order)}


class SupabaseKeyStore(KeyStore):
    """Prod store: Supabase REST with the service_role key (bypasses RLS).

    `user_keys` rows and `user_prefs.engine_order` — the public anon key can never
    read these (no RLS policy grants it). Requires the 0003 migration.
    """

    def __init__(self, url: str, service_key: str, timeout: int = 20):
        self.base = url.rstrip("/") + "/rest/v1"
        self.key = service_key
        self.timeout = timeout

    def _headers(self, extra: dict | None = None) -> dict:
        h = {"apikey": self.key, "Authorization": f"Bearer {self.key}",
             "Content-Type": "application/json"}
        if extra:
            h.update(extra)
        return h

    def load(self, user_id: str) -> dict:
        import requests
        r = requests.get(
            f"{self.base}/user_keys",
            headers=self._headers(),
            params={"user_id": f"eq.{user_id}", "order": "position.asc",
                    "select": "provider,ext_id,label,model,base_url,key_ciphertext,position"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        keys = r.json()
        p = requests.get(
            f"{self.base}/user_prefs",
            headers=self._headers(),
            params={"user_id": f"eq.{user_id}", "select": "engine_order"},
            timeout=self.timeout,
        )
        p.raise_for_status()
        rows = p.json()
        order = (rows[0].get("engine_order") if rows else None) or []
        return {"keys": keys, "order": order}

    def replace(self, user_id: str, keys: list[dict], order: list) -> None:
        import requests
        # 1) wipe existing key rows for this user
        requests.delete(
            f"{self.base}/user_keys",
            headers=self._headers(), params={"user_id": f"eq.{user_id}"},
            timeout=self.timeout,
        ).raise_for_status()
        # 2) insert new rows
        if keys:
            payload = [{**row, "user_id": user_id} for row in keys]
            requests.post(
                f"{self.base}/user_keys",
                headers=self._headers({"Prefer": "return=minimal"}),
                json=payload, timeout=self.timeout,
            ).raise_for_status()
        # 3) upsert the preference order
        requests.post(
            f"{self.base}/user_prefs",
            headers=self._headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            json={"user_id": user_id, "engine_order": order}, timeout=self.timeout,
        ).raise_for_status()
