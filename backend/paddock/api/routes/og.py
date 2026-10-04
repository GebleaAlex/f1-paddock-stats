"""Social preview images (Open Graph): a 1200x630 PNG card per page, drawn with Pillow.

Pages pass their own title, a short line of context and up to four stats in the query string, so the card always
matches the page and no headless browser is needed. Inputs are length-limited and only drawn as text.
"""

from __future__ import annotations

import io
import os
import re
import textwrap
import unicodedata
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Query, Response
from PIL import Image, ImageDraw, ImageFont

router = APIRouter(tags=["meta"])

W, H = 1200, 630
BG = (13, 13, 13)
SURFACE = (26, 26, 25)
INK = (255, 255, 255)
INK2 = (195, 194, 183)
MUTED = (145, 143, 136)
ACCENT = (57, 135, 229)
HEX = re.compile(r"^[0-9a-fA-F]{6}$")


# A real font is needed for accents (Pérez, Räikkönen) and dashes. The Docker image installs DejaVu; on Windows and
# macOS the system fonts are used. PADDOCK_OG_FONT and PADDOCK_OG_FONT_BOLD override the choice.
_FONTS = {
    "regular": [
        os.environ.get("PADDOCK_OG_FONT", ""),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
    "bold": [
        os.environ.get("PADDOCK_OG_FONT_BOLD", ""),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
}


@lru_cache(maxsize=2)
def _font_path(weight: str) -> str | None:
    return next((p for p in _FONTS[weight] if p and Path(p).is_file()), None)


@lru_cache(maxsize=64)
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _font_path("bold" if bold else "regular")
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)


def _safe(text: str) -> str:
    """Without a system font, Pillow's built-in font has no accents or typographic dashes: strip them."""
    if _font_path("regular"):
        return text
    text = text.replace("–", "-").replace("—", "-").replace("…", "...").replace("·", "-")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int, max_lines: int) -> list[str]:
    """Wrap text to fit `width` pixels, at most `max_lines` lines (the last one ellipsised)."""
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = word
        if len(lines) == max_lines:
            break
    if line and len(lines) < max_lines:
        lines.append(line)
    if len(lines) == max_lines and " ".join(lines) != " ".join(words):
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


def _logo(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    draw.rounded_rectangle([x, y, x + size, y + size], radius=int(size * 0.28), fill=ACCENT)
    s = size / 28
    stroke = max(3, int(2.6 * s))
    # The "P" mark from the site's favicon: stem, bowl and a short foot.
    draw.line(
        [(x + 8 * s, y + 21 * s), (x + 8 * s, y + 7 * s), (x + 14.5 * s, y + 7 * s)],
        fill=INK,
        width=stroke,
        joint="curve",
    )
    draw.arc([x + 10 * s, y + 7 * s, x + 19 * s, y + 16 * s], start=-90, end=90, fill=INK, width=stroke)
    draw.line([(x + 14.5 * s, y + 16 * s), (x + 8 * s, y + 16 * s)], fill=INK, width=stroke)
    draw.line([(x + 15 * s, y + 21 * s), (x + 20 * s, y + 21 * s)], fill=INK, width=stroke)


@lru_cache(maxsize=512)
def render(title: str, eyebrow: str, sub: str, stats: tuple[tuple[str, str], ...], color: str | None) -> bytes:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    stripe = tuple(int(color[i : i + 2], 16) for i in (0, 2, 4)) if color else ACCENT
    draw.rectangle([0, 0, 12, H], fill=stripe)

    _logo(draw, 72, 60, 52)
    draw.text((140, 68), "Paddock Stats", font=_font(30, bold=True), fill=INK)
    note = _safe("Unofficial · free and open source")
    draw.text((W - 72 - draw.textlength(note, font=_font(22)), 76), note, font=_font(22), fill=MUTED)

    y = 170
    if eyebrow:
        draw.text((72, y), _safe(eyebrow.upper()), font=_font(24), fill=MUTED)
        y += 44
    title_font = _font(68 if len(title) < 28 else 58, bold=True)
    for line in _wrap(draw, _safe(title), title_font, W - 144, 2):
        draw.text((72, y), line, font=title_font, fill=INK)
        y += title_font.size + 14
    if sub:
        y += 14
        sub_font = _font(30)
        for line in _wrap(draw, _safe(sub), sub_font, W - 144, 2):
            draw.text((72, y), line, font=sub_font, fill=INK2)
            y += 42

    if stats:
        gap = 18
        n = len(stats)
        box_w = (W - 144 - gap * (n - 1)) // n
        top = H - 72 - 120
        for i, (label, value) in enumerate(stats):
            x = 72 + i * (box_w + gap)
            draw.rounded_rectangle([x, top, x + box_w, top + 120], radius=18, fill=SURFACE)
            label, value = _safe(label), _safe(value)
            draw.text((x + 24, top + 20), label, font=_font(22), fill=MUTED)
            size = 44
            while size > 24 and draw.textlength(value, font=_font(size, bold=True)) > box_w - 48:
                size -= 2
            draw.text((x + 24, top + 54), value, font=_font(size, bold=True), fill=INK)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


@router.get("/og.png", response_class=Response)
def og_image(
    title: str = Query("Formula 1 statistics, 1950 to today", max_length=90),
    eyebrow: str = Query("", max_length=60),
    sub: str = Query("", max_length=160),
    stats: str = Query("", max_length=200, description="Up to four 'Label:Value' pairs separated by |"),
    color: str = Query("", max_length=6, description="Hex colour of the side stripe, without #"),
):
    pairs = []
    for part in stats.split("|")[:4]:
        if ":" in part:
            label, value = part.split(":", 1)
            pairs.append(
                (
                    textwrap.shorten(label.strip(), 22, placeholder="…"),
                    textwrap.shorten(value.strip(), 18, placeholder="…"),
                )
            )
    png = render(title.strip(), eyebrow.strip(), sub.strip(), tuple(pairs), color if HEX.match(color or "") else None)
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})
