"""Text-hook overlay for Shorts thumbnails (Pillow).

Draws a bold, high-contrast phrase on the selected frame. The phrase text
comes from the LLM (Metadata.thumbnail_text).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    # Try common bold Windows fonts, fall back to Pillow default.
    for name in ("arialbd.ttf", "ariblk.ttf", "seguisb.ttf", "impact.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def add_text_overlay(
    image_path: Path,
    text: str,
    out_path: Path,
    position: str = "bottom",
) -> Path:
    """Return a new image with `text` overlaid. If text is empty, just copies."""
    img = Image.open(image_path).convert("RGB")
    W, H = img.size

    if not text.strip():
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, quality=92)
        return out_path

    draw = ImageDraw.Draw(img)
    font_size = max(36, int(W * 0.11))
    font = _load_font(font_size)
    margin = int(W * 0.06)
    lines = _wrap(draw, text.upper(), font, W - 2 * margin)

    line_h = font.getbbox("Ag")[3] + int(font_size * 0.25)
    block_h = line_h * len(lines)
    if position == "top":
        y = margin
    elif position == "center":
        y = (H - block_h) // 2
    else:
        y = H - block_h - margin

    stroke = max(2, font_size // 12)
    for line in lines:
        line_w = draw.textlength(line, font=font)
        x = (W - line_w) // 2
        # White fill, black stroke — reads on any background.
        draw.text(
            (x, y), line, font=font, fill=(255, 255, 255),
            stroke_width=stroke, stroke_fill=(0, 0, 0),
        )
        y += line_h

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)
    return out_path
