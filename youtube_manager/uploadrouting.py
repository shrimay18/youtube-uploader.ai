"""Upload routing — which OAuth client (and therefore whose quota) an upload uses.

Every channel connection is authorized by exactly one client and pins its uploads
to that client's project quota:
  - `app`  connection  -> the shared app client  -> the shared ~6/day pool
  - `user` connection  -> the user's own client  -> the user's own quota

Policy (per the product decision):
  - SINGLE upload : try the shared `app` client first; on quota-exhaustion, fall
                    back to the user's own `user` connection (if they've added one).
  - BULK  upload  : ONLY the user's own `user` connections — never the shared pool.

A "connection" here is an opaque dict; callers pass in a `do_upload(connection)`
callable. This module is pure/deterministic and fully unit-tested.
"""
from __future__ import annotations

from .providers.base import QuotaExceeded


class NoCredentials(Exception):
    """No usable connection for the requested mode (e.g. bulk with no BYO client)."""


def order_connections(connections: list[dict], mode: str) -> list[dict]:
    """Return the connections to try, in order, for `mode` ('single' | 'bulk')."""
    app = [c for c in connections if c.get("client_kind") == "app"]
    own = [c for c in connections if c.get("client_kind") == "user"]
    if mode == "bulk":
        return own                      # bulk never touches the shared pool
    return app + own                    # single: shared quota first, then the user's


def run_with_quota_fallback(connections: list[dict], mode: str, do_upload):
    """Try `do_upload(conn)` across the ordered connections, rotating to the next on
    QuotaExceeded. Returns the first success; raises NoCredentials if none apply, or
    QuotaExceeded if every applicable connection is out of quota."""
    chain = order_connections(connections, mode)
    if not chain:
        raise NoCredentials(
            "Bulk uploads need your own YouTube credentials — connect them to continue."
            if mode == "bulk" else
            "No YouTube channel is connected for this upload."
        )
    errors = []
    for conn in chain:
        try:
            return do_upload(conn)
        except QuotaExceeded as e:
            errors.append(f"{conn.get('client_kind')}: {e}")
            continue                    # this client's quota is spent — try the next
    raise QuotaExceeded(
        "Daily upload quota is exhausted. "
        + ("Add your own YouTube credentials to keep uploading." if mode == "single"
           else "Your own client's quota is used up for today.")
        + " (" + " | ".join(errors[-3:]) + ")"
    )
