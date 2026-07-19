"""Ingest — resolve a video source to a local file path.

Long-form: Google Drive share link -> download via gdown.
Shorts:    local file path -> used in place.
Optional thumbnail: local path OR http link (downloaded).
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass
class Source:
    video_path: Path
    kind: str = ""            # "long" | "short" — decided by duration after ingest
    thumbnail_path: Path | None = None
    origin: str = ""          # original link/path, for the draft record


_DRIVE_ID_RE = re.compile(r"(?:/d/|id=|/file/d/)([A-Za-z0-9_-]{20,})")


def _drive_id(link: str) -> str | None:
    m = _DRIVE_ID_RE.search(link)
    return m.group(1) if m else None


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def ingest(
    source: str,
    downloads_dir: Path,
    thumbnail: str | None = None,
) -> Source:
    """Resolve `source` (Drive link or local path) into a local video file.

    Format (short vs long) is NOT decided here — it's determined from the
    downloaded file's duration by the caller.
    """
    downloads_dir.mkdir(parents=True, exist_ok=True)

    if _is_url(source):
        drive_id = _drive_id(source)
        if not drive_id:
            raise ValueError(
                f"URL is not a recognizable Google Drive file link: {source}\n"
                "Use a 'share' link like https://drive.google.com/file/d/<ID>/view "
                "with access set to 'Anyone with the link'."
            )
        out = downloads_dir / f"{drive_id}.mp4"
        if not out.exists():
            import gdown

            gdown.download(id=drive_id, output=str(out), quiet=False)
        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError(
                "Drive download failed. Confirm the file is shared as "
                "'Anyone with the link'."
            )
        video_path = out
    else:
        p = Path(source).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"Local video not found: {p}")
        video_path = p

    thumb_path = _resolve_thumbnail(thumbnail, downloads_dir) if thumbnail else None

    return Source(
        video_path=video_path,
        thumbnail_path=thumb_path,
        origin=source,
    )


def _resolve_thumbnail(thumbnail: str, downloads_dir: Path) -> Path:
    if _is_url(thumbnail):
        drive_id = _drive_id(thumbnail)
        out = downloads_dir / "thumb_provided.jpg"
        if drive_id:
            import gdown

            gdown.download(id=drive_id, output=str(out), quiet=True)
        else:
            r = requests.get(thumbnail, timeout=60)
            r.raise_for_status()
            out.write_bytes(r.content)
        return out
    p = Path(thumbnail).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Thumbnail not found: {p}")
    dest = downloads_dir / f"thumb_provided{p.suffix}"
    shutil.copy(p, dest)
    return dest
