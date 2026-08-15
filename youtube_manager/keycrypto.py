"""Server-side encryption for stored user secrets (P1, hosted SaaS).

Every API key / OAuth secret is Fernet-encrypted at rest with a single backend
master key (env TM_MASTER_KEY). The ciphertext is opaque without the master key,
so even a Supabase leak exposes nothing usable. Injected into KeyService (DIP),
so tests can swap in a throwaway key.
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet


class KeyCrypto:
    def __init__(self, master_key: str | bytes):
        self._f = Fernet(master_key.encode() if isinstance(master_key, str) else master_key)

    def enc(self, plaintext: str) -> str:
        return self._f.encrypt(plaintext.encode()).decode()

    def dec(self, ciphertext: str) -> str:
        return self._f.decrypt(ciphertext.encode()).decode()

    @staticmethod
    def generate_master_key() -> str:
        """Make a fresh master key — run once, put the value in TM_MASTER_KEY."""
        return Fernet.generate_key().decode()

    @classmethod
    def from_env(cls) -> "KeyCrypto":
        mk = os.environ.get("TM_MASTER_KEY")
        if not mk:
            raise RuntimeError(
                "TM_MASTER_KEY is not set. Generate one with "
                "KeyCrypto.generate_master_key() and set it on the backend host."
            )
        return cls(mk)
