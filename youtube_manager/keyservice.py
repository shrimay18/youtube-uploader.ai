"""Per-user key management (P1) — the multi-tenant replacement for vault.py.

Mirrors the vault's public contract (masked_config / save_config / llm_keys /
custom_providers / engine_order) but keyed by user_id, backed by an injected
KeyStore + KeyCrypto. No global state, no os.environ. The API shapes match the
current /api/settings/keys endpoints so the frontend needs no changes.
"""
from __future__ import annotations

import secrets

from .usercontext import BUILTINS, DEFAULT_ORDER, UserContext

_newid = lambda: "x" + secrets.token_hex(3)


def _mask(v: str) -> str:
    if not v:
        return ""
    if len(v) > 12:
        return v[:6] + "…" + v[-4:]
    return (v[:4] + "…") if len(v) > 4 else v


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for k in items:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


class KeyService:
    def __init__(self, store, crypto):
        self.store = store
        self.crypto = crypto

    # ---- read -------------------------------------------------------------

    def _load_decrypted(self, user_id: str):
        raw = self.store.load(user_id)
        llm = {p: [] for p in BUILTINS}
        custom: list = []
        for row in sorted(raw["keys"], key=lambda r: r.get("position", 0)):
            prov = row.get("provider")
            try:
                key = self.crypto.dec(row["key_ciphertext"])
            except Exception:
                continue                              # unreadable row — skip, don't crash
            if prov in BUILTINS:
                llm[prov].append(key)
            elif prov == "custom":
                custom.append({
                    "id": row.get("ext_id") or _newid(),
                    "name": row.get("label") or "Custom",
                    "base": row.get("base_url") or "",
                    "model": row.get("model") or "",
                    "key": key,
                })
        order = list(raw.get("order") or []) or list(DEFAULT_ORDER)
        return llm, custom, order

    def build_context(self, user_id: str, email: str = "") -> UserContext:
        llm, custom, order = self._load_decrypted(user_id)
        return UserContext(id=user_id, email=email, llm=llm, order=order, custom=custom)

    def list_masked(self, user_id: str) -> dict:
        """Masked view for the settings UI — same shape as vault.masked_config()."""
        llm, custom, order = self._load_decrypted(user_id)
        return {
            "llm": {p: [_mask(k) for k in llm[p]] for p in BUILTINS},
            "youtube": "",                            # app-level; not per-user here
            "order": order,
            "providers": list(BUILTINS),
            "custom": [{"id": c["id"], "name": c["name"], "base": c["base"],
                        "model": c["model"], "key": _mask(c["key"])} for c in custom],
            "has_llm": any(llm[p] for p in BUILTINS) or bool(custom),
        }

    def has_llm(self, user_id: str) -> bool:
        llm, custom, _ = self._load_decrypted(user_id)
        return any(llm[p] for p in BUILTINS) or bool(custom)

    # ---- write ------------------------------------------------------------

    def save(self, user_id: str, order=None, llm_ops: dict | None = None,
             custom: dict | None = None) -> None:
        """Apply key edits. Same op contract as vault.save_config:

        llm_ops = {provider: {"keep": [kept indexes], "add": [new raw keys]}}
        custom  = {"keep": [indexes], "add": [{id?, name, base, model, key}]}
        order   = new preference tokens, or None to keep.
        """
        cur_llm, cur_custom, cur_order = self._load_decrypted(user_id)
        llm_ops = llm_ops or {}

        new_llm = {p: [] for p in BUILTINS}
        for p in BUILTINS:
            existing = cur_llm[p]
            ops = llm_ops.get(p) or {}
            kept = [existing[i] for i in ops.get("keep", []) if isinstance(i, int) and 0 <= i < len(existing)]
            added = [k.strip() for k in ops.get("add", []) if k and k.strip()]
            new_llm[p] = _dedupe(kept + added)

        if custom is None:
            new_custom = list(cur_custom)
        else:
            new_custom = [cur_custom[i] for i in custom.get("keep", []) if isinstance(i, int) and 0 <= i < len(cur_custom)]
            for e in custom.get("add", []):
                if (e.get("key") or "").strip():
                    new_custom.append({
                        "id": e.get("id") or _newid(),
                        "name": (e.get("name") or "Custom").strip(),
                        "base": (e.get("base") or "").strip(),
                        "model": (e.get("model") or "").strip(),
                        "key": e["key"].strip(),
                    })

        valid_custom = {c["id"] for c in new_custom}
        new_order = [t for t in list(order or cur_order) if t in BUILTINS or t in valid_custom]
        for p in BUILTINS:
            if p not in new_order:
                new_order.append(p)
        for cid in valid_custom:
            if cid not in new_order:
                new_order.append(cid)

        rows, pos = [], 0
        for p in BUILTINS:
            for k in new_llm[p]:
                rows.append({"provider": p, "ext_id": None, "label": None, "model": None,
                             "base_url": None, "key_ciphertext": self.crypto.enc(k), "position": pos})
                pos += 1
        for c in new_custom:
            rows.append({"provider": "custom", "ext_id": c["id"], "label": c["name"],
                         "model": c["model"], "base_url": c["base"],
                         "key_ciphertext": self.crypto.enc(c["key"]), "position": pos})
            pos += 1

        self.store.replace(user_id, rows, new_order)
