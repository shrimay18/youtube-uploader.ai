"""Reusable draft pipeline — shared by the CLI and the web API.

build_draft() runs ingest -> duration/format -> transcribe -> research -> generate
-> (Shorts thumbnail) -> write draft.yaml, reporting progress via a `log` callback.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from . import config
from .providers.base import QuotaExceeded


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:40] or datetime.now().strftime("video-%Y%m%d-%H%M%S")


class DraftResult:
    def __init__(self, draft_path: Path, slug: str, kind: str, title: str, score: float):
        self.draft_path = draft_path
        self.slug = slug
        self.kind = kind
        self.title = title
        self.score = score


def build_draft(
    settings: dict,
    profile: dict,
    source: str,
    channel_key: str,
    channel_label: str,
    slug: str,
    thumbnail: str | None = None,
    force_kind: str | None = None,   # "short" | "long" | None (auto by duration)
    fixed_desc_text: str = "",
    fixed_desc_position: str = "auto",
    fixed_comment_text: str = "",
    fixed_comment_mode: str = "ai",
    log=print,
) -> DraftResult:
    """Run the full draft pipeline. Raises QuotaExceeded if the LLM quota is hit."""
    paths = config.paths()

    # 1. Ingest -----------------------------------------------------------
    from . import ingest as ingest_mod
    from . import transcribe as tr
    log("[1/5] Ingesting source (Drive link or local file)...")
    src = ingest_mod.ingest(source, paths.downloads, thumbnail=thumbnail)
    log(f"      video: {src.video_path.name}")

    # Decide format from duration unless forced.
    duration = tr.probe_duration(src.video_path)
    threshold = settings.get("defaults", {}).get("short_max_seconds", 120)
    if force_kind in ("short", "long"):
        kind = force_kind
    elif duration <= 0:
        kind = "long"
        log("      (couldn't read duration; defaulting to long-form)")
    else:
        kind = "short" if duration <= threshold else "long"
    if duration > 0:
        log(f"      duration: {int(duration // 60)}m{int(duration % 60):02d}s -> {kind.upper()}")
    src.kind = kind

    # 2. Transcribe -------------------------------------------------------
    w = settings.get("whisper", {})
    cap = w.get("max_minutes", 0)
    if cap and duration > cap * 60:
        log(f"[2/5] Transcribing first {cap} min of {int(duration // 60)} min (capped)...")
    elif duration > 15 * 60:
        log(f"[2/5] Transcribing the full {int(duration // 60)} min video... "
            "(long videos take a few minutes)")
    else:
        log("[2/5] Transcribing (faster-whisper)...")
    transcript = tr.transcribe(
        src.video_path,
        model_size=w.get("model", "small"),
        compute_type=w.get("compute_type", "int8"),
        device=w.get("device", "cpu"),
        vad_filter=w.get("vad_filter", False),
        task=w.get("task", "transcribe"),
        language=w.get("language"),
        beam_size=w.get("beam_size", 1),
        cpu_threads=w.get("cpu_threads", 0),
        max_minutes=cap,
    )
    log(f"      {len(transcript.segments)} segments, {round(transcript.duration)}s "
        f"({transcript.language or '??'})")

    # 3. Research ---------------------------------------------------------
    from . import research as rs
    log("[3/5] SEO research (autocomplete + trends)...")
    yt_key = config.env("YOUTUBE_API_KEY")
    research = rs.research(
        transcript.text, settings.get("research", {}), niche_hint=profile.get("niche", ""),
    )
    log(f"      {len(research.autocomplete)} autocomplete phrases, {len(research.rising)} trends")

    # 4. Generate ---------------------------------------------------------
    from . import generate as gen
    log(f"[4/5] Generating metadata via {settings.get('engine')} "
        "(ranking titles + real competitor tags -> scored SEO titles)...")
    meta = gen.generate(settings, profile, transcript, research, kind, yt_api_key=yt_key, log=log)
    log(f"      chosen title ({meta.title_score}/100): {meta.title_variants[0] if meta.title_variants else '-'}")

    # Apply the user's fixed description / pinned-comment boilerplate.
    meta.description = gen.apply_fixed_description(meta.description, fixed_desc_text, fixed_desc_position)
    meta.pinned_comment = gen.apply_fixed_comment(meta.pinned_comment, fixed_comment_text, fixed_comment_mode)
    if fixed_desc_text.strip():
        log(f"      applied fixed description ({fixed_desc_position})")
    if fixed_comment_text.strip():
        log(f"      applied fixed comment ({fixed_comment_mode})")

    # 4b. Shorts thumbnail ------------------------------------------------
    thumb_path = src.thumbnail_path
    if kind == "short" and thumb_path is None:
        try:
            from . import frameselect, thumbnail as thumb_mod
            log("      building Shorts thumbnail (best frame + text overlay)...")
            raw_frame = paths.downloads / f"{slug}_frame.jpg"
            frameselect.best_frame(src.video_path, raw_frame)
            thumb_path = thumb_mod.add_text_overlay(
                raw_frame, meta.thumbnail_text, paths.downloads / f"{slug}_thumb.jpg"
            )
        except Exception as e:
            log(f"      (thumbnail generation skipped: {e})")

    # 5. Write draft ------------------------------------------------------
    from . import review as rv
    log("[5/5] Writing draft...")
    draft_path = rv.write_draft(
        slug, meta, src.video_path, kind, paths.drafts, settings,
        thumbnail_path=thumb_path, origin=src.origin,
        channel_key=channel_key, channel_label=channel_label,
        audio_language=transcript.language,
    )
    log(f"Draft ready: {draft_path.name}")
    title = meta.title_variants[0] if meta.title_variants else ""
    return DraftResult(draft_path, slug, kind, title, meta.title_score)
