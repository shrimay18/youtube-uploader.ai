"""Stateless per-request auth for the hosted API (P1).

Verifies the Supabase JWT the frontend sends, then builds a per-user context from
the user's stored keys. Replaces the single-user before_request guard + vault._STATE.

Wiring (P2/integration): in create_app()

    @app.before_request
    def _auth():
        if request.path in OPEN or not request.path.startswith("/api/"):
            return
        ctx = context_from_request(request, key_service)
        if not ctx:
            return jsonify({"error": "auth required"}), 401
        g.user = ctx

Not attached to the live app yet — the current local build keeps using vault so it
stays working until we deploy.
"""
from __future__ import annotations

from . import supabase_auth


def bearer_token(request) -> str | None:
    h = request.headers.get("Authorization", "")
    return h[7:].strip() if h.lower().startswith("bearer ") else None


def context_from_token(token: str | None, key_service):
    """Verify a Supabase access token and return a UserContext, or None."""
    if not token:
        return None
    claims = supabase_auth.verify(token)
    if not claims:
        return None
    sub, email, _name = supabase_auth.identity(claims)
    if not sub:
        return None
    return key_service.build_context(sub, email=email)


def context_from_request(request, key_service):
    return context_from_token(bearer_token(request), key_service)
