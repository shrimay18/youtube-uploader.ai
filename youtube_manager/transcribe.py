"""Transcribe — extract audio with ffmpeg, then faster-whisper w/ timestamps.

Returns full text plus segment timestamps used to auto-build chapters.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Segment:
    start: float          # seconds
    end: float
    text: str


@dataclass
class Transcript:
    text: str
    segments: list[Segment] = field(default_factory=list)
    language: str = ""
    duration: float = 0.0


def _tool_bin(name: str) -> str:
    """Locate ffmpeg/ffprobe, with a fallback for when winget's PATH hasn't refreshed."""
    exe = shutil.which(name)
    if exe:
        return exe
    import glob
    import os

    exe_name = f"{name}.exe"
    candidates = [
        os.path.expandvars(rf"%LOCALAPPDATA%\Microsoft\WinGet\Links\{exe_name}"),
        *glob.glob(
            os.path.expandvars(
                rf"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\{exe_name}"
            ),
            recursive=True,
        ),
        rf"C:\ffmpeg\bin\{exe_name}",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    raise RuntimeError(
        f"{name} not found on PATH. Install ffmpeg (winget install Gyan.FFmpeg) "
        "and reopen the terminal."
    )


def _ffmpeg_bin() -> str:
    return _tool_bin("ffmpeg")


def _add_cuda_dll_dirs() -> None:
    """Make the pip-installed CUDA libs (cuBLAS/cuDNN) loadable on Windows."""
    import os
    try:
        import nvidia
    except ImportError:
        return
    # `nvidia` is a namespace package -> use __path__ (its __file__ is None).
    for base in list(getattr(nvidia, "__path__", [])):
        for sub in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
            d = os.path.join(base, sub, "bin")
            if os.path.isdir(d):
                try:
                    os.add_dll_directory(d)
                except (OSError, AttributeError):
                    pass
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def _resolve_device(device: str, compute_type: str | None) -> tuple[str, str]:
    """Resolve device='auto' to cuda when a working GPU is present, else cpu."""
    if device in ("auto", "", None):
        device = "cpu"
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                device = "cuda"
        except Exception:
            pass
    if compute_type in ("auto", "", None):
        compute_type = "float16" if device == "cuda" else "int8"
    return device, compute_type


def _make_model(model_size, device, compute_type, cpu_threads):
    """Build a WhisperModel, falling back CUDA -> CPU if the GPU can't load."""
    from faster_whisper import WhisperModel

    if device == "cuda":
        _add_cuda_dll_dirs()
        try:
            return WhisperModel(model_size, device="cuda", compute_type=compute_type), "cuda"
        except Exception as e:
            print(f"      (GPU unavailable: {str(e)[:80]}; using CPU)")
    return (
        WhisperModel(model_size, device="cpu", compute_type="int8",
                     cpu_threads=cpu_threads if cpu_threads and cpu_threads > 0 else 0),
        "cpu",
    )


def probe_duration(video_path: Path) -> float:
    """Return the video's duration in seconds (fast; via ffprobe, no transcription)."""
    try:
        out = subprocess.run(
            [
                _tool_bin("ffprobe"), "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
            ],
            check=True, capture_output=True, text=True,
        )
        return float(out.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def extract_audio(video_path: Path, max_seconds: float | None = None) -> Path:
    """16kHz mono wav — what Whisper wants. Optionally only the first max_seconds."""
    tmp = Path(tempfile.gettempdir()) / f"youtube_manager_{video_path.stem}.wav"
    cmd = [_ffmpeg_bin(), "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000"]
    if max_seconds and max_seconds > 0:
        cmd += ["-t", str(int(max_seconds))]      # only decode the first slice — huge win
    cmd += ["-f", "wav", str(tmp)]
    subprocess.run(cmd, check=True, capture_output=True)
    return tmp


def transcribe(
    video_path: Path,
    model_size: str = "small",
    compute_type: str = "int8",
    device: str = "cpu",
    vad_filter: bool = False,
    task: str = "transcribe",
    language: str | None = None,
    beam_size: int = 1,
    cpu_threads: int = 0,
    max_minutes: float = 0,
) -> Transcript:
    # Optionally cap very long videos (0 = full).
    max_seconds = max_minutes * 60 if max_minutes and max_minutes > 0 else None
    audio = extract_audio(video_path, max_seconds=max_seconds)

    device, compute_type = _resolve_device(device, compute_type)
    model, device = _make_model(model_size, device, compute_type, cpu_threads)
    # vad_filter=True mangles Hinglish/code-switched audio (it mis-detects Hindi and
    # emits gibberish) -> keep it OFF by default. beam_size=1 is ~1.5x faster than 5
    # with negligible quality loss for metadata. language=None auto-detects.
    seg_iter, info = model.transcribe(
        str(audio), task=task, language=language, vad_filter=vad_filter, beam_size=beam_size
    )

    segments: list[Segment] = []
    parts: list[str] = []
    for s in seg_iter:
        segments.append(Segment(start=s.start, end=s.end, text=s.text.strip()))
        parts.append(s.text.strip())

    try:
        audio.unlink(missing_ok=True)
    except OSError:
        pass

    return Transcript(
        text=" ".join(parts).strip(),
        segments=segments,
        language=getattr(info, "language", ""),
        duration=getattr(info, "duration", 0.0),
    )


def _fmt_ts(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def naive_chapters(transcript: Transcript, hint_minutes: float = 3.0) -> list[dict]:
    """Evenly-spaced timestamp+context HINTS for the LLM (not the final chapters).

    We provide anchors roughly every `hint_minutes` across the whole video (each
    snapped to a nearby segment for real context). The LLM decides how many actual
    chapters there are by grouping these into distinct topics/questions — so the
    chapter count follows the content naturally rather than any fixed cap.
    """
    segs = transcript.segments
    if not segs:
        return []
    duration = transcript.duration or segs[-1].end
    n = max(3, int(duration / (hint_minutes * 60)) + 1)

    hints: list[dict] = []
    seen: set[str] = set()
    for i in range(n):
        target = 0.0 if i == 0 else duration * i / n
        seg = min(segs, key=lambda s: abs(s.start - target))
        t = 0.0 if i == 0 else seg.start
        ts = _fmt_ts(t)
        if ts not in seen:
            seen.add(ts)
            hints.append({"time": ts, "seconds": t, "text": seg.text})
    return hints
