"""Review gate — write the editable draft.yaml.

draft.yaml is the source of truth. The single review UI is the editable
`youtube_manager review` server (reviewserver.py); there is no separate static preview.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dateutil import tz

from .generate import Metadata


def _default_publish_at(timezone: str) -> str:
    """Suggest tomorrow 18:00 in the target tz as an RFC3339 string placeholder."""
    zone = tz.gettz(timezone)
    dt = (datetime.now(zone) + timedelta(days=1)).replace(
        hour=18, minute=0, second=0, microsecond=0
    )
    return dt.isoformat()


def write_draft(
    slug: str,
    meta: Metadata,
    video_path: Path,
    kind: str,
    drafts_dir: Path,
    settings: dict,
    thumbnail_path: Path | None = None,
    origin: str = "",
    channel_key: str = "default",
    channel_label: str = "",
    audio_language: str = "",
) -> Path:
    timezone = settings.get("timezone", "Asia/Kolkata")
    draft = {
        "_meta": {
            "slug": slug,
            "kind": kind,
            "channel": channel_key,          # which channel this uploads to
            "channel_label": channel_label,
            "video_path": str(video_path),
            "origin": origin,
            "generated_at": datetime.now(tz.gettz(timezone)).isoformat(),
            "engine": settings.get("engine"),
        },
        # How the title was derived (informational; not used at publish).
        "_title_flow": {
            "raw_title": meta.raw_title,
            "reference_title": meta.title_critique,
            "score": meta.title_score,
            "ranking_titles": meta.ranking_titles,
        },
        # ---- EDIT BELOW BEFORE PUBLISHING ----
        "title": meta.title_variants[0] if meta.title_variants else "",
        # Each option carries its local SEO score (0-100), shown in the review UI.
        "title_options": meta.title_options,
        "title_variants": meta.title_variants,
        "description": meta.description,
        "tags": meta.tags,
        "hashtags": meta.hashtags,
        "category_id": meta.category_id,
        "category": meta.category,
        "chapters": meta.chapters,
        "pinned_comment": meta.pinned_comment,
        "thumbnail": str(thumbnail_path) if thumbnail_path else "",
        "thumbnail_text": meta.thumbnail_text,
        # Language: metadata is English; audio language auto-detected by Whisper.
        "language": settings.get("defaults", {}).get("language", "en"),
        "audio_language": audio_language or settings.get("defaults", {}).get("audio_language", ""),
        # Scheduling — leave "now" to publish immediately, or an RFC3339 IST time.
        "privacy": settings.get("defaults", {}).get("privacy", "private"),
        "publish_at": _default_publish_at(timezone),
        "made_for_kids": settings.get("defaults", {}).get("made_for_kids", False),
    }

    drafts_dir.mkdir(parents=True, exist_ok=True)
    draft_path = drafts_dir / f"{slug}.yaml"
    with draft_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(draft, fh, sort_keys=False, allow_unicode=True, width=100)

    # No static preview HTML — the single UI is the editable `youtube_manager review` server.
    return draft_path
