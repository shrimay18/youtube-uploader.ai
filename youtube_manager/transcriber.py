"""Transcription behind one interface (P3).

Local Whisper is great on a device but expensive/slow on a server, so the hosted
backend swaps in a transcription API. All implementations return the SAME
`transcribe.Transcript` (text + segments + language + duration), so the pipeline is
unchanged — only the source moves. Injected/selected via get_transcriber(), DIP.

`transcribe(audio_path)` takes an already-extracted audio file (the pipeline extracts
once with ffmpeg, then hands it here) — keeps this module ffmpeg-free and testable.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

import requests

from .transcribe import Segment, Transcript


class Transcriber(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> Transcript: ...


class DeepgramTranscriber(Transcriber):
    URL = "https://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str, model: str = "nova-2", timeout: int = 600):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def transcribe(self, audio_path: str) -> Transcript:
        with open(audio_path, "rb") as fh:
            audio = fh.read()
        r = requests.post(
            self.URL,
            headers={"Authorization": f"Token {self.api_key}"},
            params={"model": self.model, "detect_language": "true",
                    "punctuate": "true", "smart_format": "true"},
            data=audio, timeout=self.timeout,
        )
        r.raise_for_status()
        return _parse_deepgram(r.json())


class OpenAITranscriber(Transcriber):
    URL = "https://api.openai.com/v1/audio/transcriptions"

    def __init__(self, api_key: str, model: str = "whisper-1", timeout: int = 600):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def transcribe(self, audio_path: str) -> Transcript:
        with open(audio_path, "rb") as fh:
            r = requests.post(
                self.URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (os.path.basename(audio_path), fh)},
                data={"model": self.model, "response_format": "verbose_json"},
                timeout=self.timeout,
            )
        r.raise_for_status()
        return _parse_openai(r.json())


class LocalWhisperTranscriber(Transcriber):
    """Thin adapter over the existing local faster-whisper path (dev / desktop)."""

    def __init__(self, settings: dict | None = None):
        self.w = (settings or {}).get("whisper", {})

    def transcribe(self, audio_path: str) -> Transcript:
        from pathlib import Path

        from . import transcribe as _t
        return _t.transcribe(
            Path(audio_path),
            model_size=self.w.get("model", "small"),
            compute_type=self.w.get("compute_type", "auto"),
            device=self.w.get("device", "auto"),
            task=self.w.get("task", "transcribe"),
            beam_size=self.w.get("beam_size", 1),
        )


def get_transcriber(settings: dict | None = None) -> Transcriber:
    """Pick the transcriber: env TM_TRANSCRIBER (deepgram|openai|local) or settings, default local."""
    settings = settings or {}
    provider = (os.environ.get("TM_TRANSCRIBER")
                or (settings.get("transcriber", {}) or {}).get("provider") or "local").lower()
    if provider == "deepgram":
        return DeepgramTranscriber(os.environ.get("DEEPGRAM_API_KEY", ""))
    if provider == "openai":
        return OpenAITranscriber(os.environ.get("OPENAI_API_KEY", ""))
    return LocalWhisperTranscriber(settings)


# ---- response parsers (pure; unit-tested) --------------------------------

def _parse_deepgram(payload: dict) -> Transcript:
    try:
        ch = payload["results"]["channels"][0]
        alt = ch["alternatives"][0]
    except (KeyError, IndexError):
        return Transcript(text="")
    text = alt.get("transcript", "")
    language = ch.get("detected_language") or payload.get("metadata", {}).get("detected_language", "")
    duration = float(payload.get("metadata", {}).get("duration", 0.0) or 0.0)
    # coarse segments: group words into ~20-word chunks (feeds naive chapters)
    words = alt.get("words", []) or []
    segments: list[Segment] = []
    chunk = 20
    for i in range(0, len(words), chunk):
        grp = words[i:i + chunk]
        segments.append(Segment(
            start=float(grp[0].get("start", 0.0)),
            end=float(grp[-1].get("end", 0.0)),
            text=" ".join(w.get("punctuated_word") or w.get("word", "") for w in grp).strip(),
        ))
    return Transcript(text=text, segments=segments, language=language or "", duration=duration)


def _parse_openai(payload: dict) -> Transcript:
    segments = [
        Segment(start=float(s.get("start", 0.0)), end=float(s.get("end", 0.0)),
                text=(s.get("text") or "").strip())
        for s in (payload.get("segments") or [])
    ]
    return Transcript(
        text=(payload.get("text") or "").strip(),
        segments=segments,
        language=payload.get("language", "") or "",
        duration=float(payload.get("duration", 0.0) or 0.0),
    )
