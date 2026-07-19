"""Admin analytics — reads across all users via the Supabase service key.

This module only works on a machine where SUPABASE_SERVICE_KEY is set (the
creator's). The service key bypasses Row Level Security, so it must never ship to
a user device — the caller (webapp) gates access to admin emails first.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

from . import config


def _headers(service_key: str) -> dict:
    return {"apikey": service_key, "Authorization": f"Bearer {service_key}"}


def _get(path: str, params: dict) -> list:
    sb = config.supabase_config()
    key = config.admin_config()["service_key"]
    url = f"{sb['url']}/rest/v1/{path}"
    r = requests.get(url, headers=_headers(key), params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _parse(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def stats() -> dict:
    """Aggregate signups + usage for the admin dashboard."""
    profiles = _get("profiles", {
        "select": "id,email,name,created_at,last_active",
        "order": "last_active.desc",
    })
    events = _get("usage_events", {
        "select": "user_id,type,created_at",
        "order": "created_at.desc",
        "limit": "10000",
    })

    now = datetime.now(timezone.utc)
    d7, d30 = now - timedelta(days=7), now - timedelta(days=30)

    by_type: dict[str, int] = defaultdict(int)
    events_7d = 0
    active_7d: set[str] = set()
    per_day: dict[str, int] = defaultdict(int)        # last 14 days, generate+publish
    per_user_gen: dict[str, int] = defaultdict(int)
    per_user_pub: dict[str, int] = defaultdict(int)

    for e in events:
        t = e.get("type", "")
        by_type[t] += 1
        ts = _parse(e.get("created_at", ""))
        if ts:
            if ts >= d7:
                events_7d += 1
                active_7d.add(e.get("user_id", ""))
            if ts >= now - timedelta(days=14) and t in ("generate", "publish"):
                per_day[ts.date().isoformat()] += 1
        if t == "generate":
            per_user_gen[e.get("user_id", "")] += 1
        elif t == "publish":
            per_user_pub[e.get("user_id", "")] += 1

    # Fill the 14-day series so the chart has no gaps.
    series = []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date().isoformat()
        series.append({"day": day, "count": per_day.get(day, 0)})

    signups_30d = sum(1 for p in profiles if (_parse(p.get("created_at", "")) or now) >= d30)

    users = []
    for p in profiles:
        uid = p.get("id", "")
        users.append({
            "email": p.get("email") or "—",
            "name": p.get("name") or "",
            "created_at": p.get("created_at"),
            "last_active": p.get("last_active"),
            "generations": per_user_gen.get(uid, 0),
            "publishes": per_user_pub.get(uid, 0),
        })

    return {
        "totals": {
            "users": len(profiles),
            "signups_30d": signups_30d,
            "active_7d": len([u for u in active_7d if u]),
            "generations": by_type.get("generate", 0),
            "publishes": by_type.get("publish", 0),
            "events_7d": events_7d,
        },
        "by_type": dict(by_type),
        "series_14d": series,
        "users": users,
    }
