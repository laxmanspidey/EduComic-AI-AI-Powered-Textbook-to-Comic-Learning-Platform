"""
Comic Panel Composer — True Comic Book Layout
==================================================

DESIGN PHILOSOPHY:
  Matches traditional educational comic book design (like the reference inertia comic).
  - The illustration covers the entire 1024x1024 panel.
  - Text elements are rendered as comic book overlays (Title boxes, Speech bubbles, Caption boxes)
  - No massive solid colored backgrounds blocking the art.
  - Text size is large and readable (24-30px).

LAYOUT (1024×1024):
  ┌─────────────────────────────────────────────────────────┐
  │ ┌──────────────────────────┐                            │
  │ │ THE MYSTERY OF THE BUS   │                            │
  │ └──────────────────────────┘                            │
  │                                   ╭──────────────────╮  │
  │                                   │ Why do I fall    │  │
  │                                   │ backward?        │  │
  │                                   ╰────────v─────────╯  │
  │                                                         │
  │               (Full Image Background)                   │
  │                                                         │
  │                                                         │
  │ ┌─────────────────────────────────────────────────────┐ │
  │ │ Our body tries to stay in its original state of     │ │
  │ │ rest. That's INERTIA!                               │ │
  │ └─────────────────────────────────────────────────────┘ │
  └─────────────────────────────────────────────────────────┘
"""
import io
import textwrap
from PIL import Image, ImageDraw, ImageFont

# ──────────────────────────────────────────────────────────────────────────────
# Layout constants
# ──────────────────────────────────────────────────────────────────────────────
CANVAS_W = 1024
CANVAS_H = 1024

# Colors
C = {
    'title_bg':     (255, 215, 0, 255),    # Comic Yellow
    'title_fg':     (0, 0, 0, 255),        # Black
    'title_bdr':    (0, 0, 0, 255),
    'bubble_bg':    (255, 255, 255, 245),  # White (slightly transparent)
    'bubble_fg':    (15, 15, 15, 255),
    'bubble_bdr':   (0, 0, 0, 255),
    'caption_bg':   (255, 255, 255, 245),  # White
    'caption_fg':   (15, 15, 15, 255),
    'caption_bdr':  (0, 0, 0, 255),
    'formula_bg':   (255, 240, 200, 245),  # Light yellow/cream
    'formula_fg':   (0, 0, 0, 255),
    'shadow':       (0, 0, 0, 80),
}


# ──────────────────────────────────────────────────────────────────────────────
# Font helpers (cached)
# ──────────────────────────────────────────────────────────────────────────────
_FONT_CACHE: dict = {}

def _font(size: int, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold, italic)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    
    # Prefer Comic Sans if available, fallback to Arial/Calibri
    if bold and italic:
        paths = [r"C:\Windows\Fonts\comicbd.ttf", r"C:\Windows\Fonts\arialbi.ttf"]
    elif bold:
        paths = [r"C:\Windows\Fonts\comicbd.ttf", r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\calibrib.ttf"]
    elif italic:
        paths = [r"C:\Windows\Fonts\comic.ttf", r"C:\Windows\Fonts\ariali.ttf"]
    else:
        paths = [r"C:\Windows\Fonts\comic.ttf", r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\calibri.ttf"]
        
    for p in paths:
        try:
            f = ImageFont.truetype(p, size)
            _FONT_CACHE[key] = f
            return f
        except (IOError, OSError):
            continue
            
    try:
        f = ImageFont.load_default(size=size)
    except Exception:
        f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f

def _tw(draw: ImageDraw.Draw, text: str, font) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]

def _th(draw: ImageDraw.Draw, text: str, font) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]

# ──────────────────────────────────────────────────────────────────────────────
# Drawing helpers
# ──────────────────────────────────────────────────────────────────────────────
def _draw_rect_with_shadow(img: Image.Image, x: int, y: int, w: int, h: int, fill, outline, width=3):
    d = ImageDraw.Draw(img)
    # Shadow
    d.rectangle([x+6, y+6, x+w+6, y+h+6], fill=C['shadow'])
    # Box
    d.rectangle([x, y, x+w, y+h], fill=fill, outline=outline, width=width)

def _draw_rounded_rect_with_shadow(img: Image.Image, x: int, y: int, w: int, h: int, r: int, fill, outline, width=3):
    ov = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    # Shadow
    d.rounded_rectangle([x+6, y+6, x+w+6, y+h+6], radius=r, fill=C['shadow'])
    # Box
    d.rounded_rectangle([x, y, x+w, y+h], radius=r, fill=fill, outline=outline, width=width)
    img.alpha_composite(ov)

# ──────────────────────────────────────────────────────────────────────────────
# 1. TITLE BOX (Top Left)
# ──────────────────────────────────────────────────────────────────────────────
def _draw_title(canvas: Image.Image, title: str) -> int:
    if not title:
        return 0
    draw = ImageDraw.Draw(canvas)
    
    fs = 32
    f = _font(fs, bold=True)
    title = title.upper()
    
    tw = _tw(draw, title, f)
    th = _th(draw, title, f)
    
    # If title is too long, shrink font
    while tw > CANVAS_W - 80 and fs > 18:
        fs -= 2
        f = _font(fs, bold=True)
        tw = _tw(draw, title, f)
        th = _th(draw, title, f)
        
    pad_x, pad_y = 20, 15
    bw = tw + pad_x * 2
    bh = th + pad_y * 2
    bx, by = 20, 20
    
    _draw_rect_with_shadow(canvas, bx, by, bw, bh, C['title_bg'], C['title_bdr'], width=4)
    
    draw.text((bx + pad_x, by + pad_y - 2), title, font=f, fill=C['title_fg'])
    return by + bh

# ──────────────────────────────────────────────────────────────────────────────
# 2. SPEECH BUBBLE
# ──────────────────────────────────────────────────────────────────────────────
def _draw_speech_bubble(canvas: Image.Image, text: str, title_bottom: int):
    if not text:
        return
        
    # Remove simple dialogue prefixes like "Teacher:" or "Student:"
    if ":" in text:
        parts = text.split(":", 1)
        if len(parts[0]) < 15:
            text = parts[1].strip()
            
    draw = ImageDraw.Draw(canvas)
    fs = 26
    font = _font(fs, bold=True)
    
    avg_cw = max(8, int(fs * 0.55))
    max_chars = max(15, (CANVAS_W // 2) // avg_cw)
    lines = textwrap.wrap(text, width=max_chars)[:6]
    if not lines:
        return
        
    lh = fs + 8
    pad_x, pad_y = 25, 20
    
    bw = max(200, max(_tw(draw, l, font) for l in lines) + pad_x * 2)
    bh = len(lines) * lh + pad_y * 2
    
    # Position: top right, or below title if space is tight
    bx = CANVAS_W - bw - 40
    by = 40
    
    # If it overlaps the title vertically and horizontally, push it down
    if by < title_bottom + 10:
        by = max(40, title_bottom + 20)
        
    _draw_rounded_rect_with_shadow(canvas, bx, by, bw, bh, 25, C['bubble_bg'], C['bubble_bdr'], width=3)
    
    # Bubble tail (pointing down-left roughly)
    ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(ov)
    tx, ty = bx + 40, by + bh
    td.polygon([(tx, ty), (tx + 25, ty), (tx - 10, ty + 30)], fill=C['bubble_bg'])
    td.line([(tx, ty), (tx - 10, ty + 30), (tx + 25, ty)], fill=C['bubble_bdr'], width=3)
    canvas.alpha_composite(ov)
    
    draw = ImageDraw.Draw(canvas)
    for i, line in enumerate(lines):
        draw.text((bx + pad_x, by + pad_y + i * lh), line, font=font, fill=C['bubble_fg'])

# ──────────────────────────────────────────────────────────────────────────────
# 3. FORMULA BOX (Mid-bottom, above caption)
# ──────────────────────────────────────────────────────────────────────────────
def _draw_formula(canvas: Image.Image, formula: str, caption_h: int) -> int:
    if not formula:
        return 0
        
    draw = ImageDraw.Draw(canvas)
    fs = 42
    f = _font(fs, bold=True)
    
    tw = _tw(draw, formula, f)
    th = _th(draw, formula, f)
    
    pad_x, pad_y = 30, 20
    bw = tw + pad_x * 2
    bh = th + pad_y * 2
    bx = (CANVAS_W - bw) // 2
    by = CANVAS_H - caption_h - bh - 40
    
    _draw_rounded_rect_with_shadow(canvas, bx, by, bw, bh, 15, C['formula_bg'], C['caption_bdr'], width=4)
    draw.text((bx + pad_x, by + pad_y - 4), formula, font=f, fill=C['formula_fg'])
    
    return bh + 40

# ──────────────────────────────────────────────────────────────────────────────
# 4. CAPTION BOX (Bottom)
# ──────────────────────────────────────────────────────────────────────────────
def _draw_caption(canvas: Image.Image, caption: str, key_points: list) -> int:
    """
    Render caption at the bottom. If key_points are available, they take precedence 
    to ensure the high-quality LLM educational facts are displayed.
    """
    if key_points:
        # Join the key points with bullet points for a clean educational comic caption
        caption = "\n".join(f"• {kp}" for kp in key_points if kp)
        
    if not caption:
        return 0
        
    draw = ImageDraw.Draw(canvas)
    fs = 24  # slightly smaller to fit bullet points
    font = _font(fs)
    
    avg_cw = max(8, int(fs * 0.55))
    max_chars = max(40, (CANVAS_W - 100) // avg_cw)
    
    # Wrap each line (bullet point) individually
    lines = []
    for line in caption.split('\n'):
        wrapped = textwrap.wrap(line, width=max_chars)
        if wrapped:
            lines.extend(wrapped)
        else:
            lines.append("")
    lines = lines[:6] # max 6 lines to not overflow
    
    lh = fs + 8
    pad_x, pad_y = 30, 25
    
    bw = CANVAS_W - 40
    bh = len(lines) * lh + pad_y * 2
    bx = 20
    by = CANVAS_H - bh - 20
    
    _draw_rect_with_shadow(canvas, bx, by, bw, bh, C['caption_bg'], C['caption_bdr'], width=4)
    
    for i, line in enumerate(lines):
        draw.text((bx + pad_x, by + pad_y + i * lh), line, font=font, fill=C['caption_fg'])
        
    return bh + 40

# ──────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────
def add_panel_overlay(image_bytes: bytes, panel: dict) -> bytes:
    """
    Compose a traditional comic book panel layout.
    """
    bg = Image.open(io.BytesIO(image_bytes)).convert('RGBA')
    
    # Ensure background is exactly 1024x1024
    if bg.size != (CANVAS_W, CANVAS_H):
        bg = bg.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
        
    canvas = Image.new('RGBA', (CANVAS_W, CANVAS_H), (0,0,0,255))
    canvas.paste(bg, (0, 0))

    title      = panel.get('title', '').strip()
    formula    = panel.get('formula', '').strip()
    caption    = panel.get('caption', '').strip()
    dialogue   = panel.get('dialogue', '').strip()
    key_points = panel.get('key_points', [])
    
    # 1. Caption Box at bottom
    caption_h = _draw_caption(canvas, caption, key_points)
    
    # 2. Formula Box (above caption)
    _draw_formula(canvas, formula, caption_h)
    
    # 3. Title Box at top-left
    title_bottom = _draw_title(canvas, title)
    
    # 4. Speech bubble
    _draw_speech_bubble(canvas, dialogue, title_bottom)
    
    # Add a thick comic panel border around the whole image
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, CANVAS_W-1, CANVAS_H-1], outline=(0,0,0,255), width=6)

    out = io.BytesIO()
    canvas.convert('RGB').save(out, format='PNG', optimize=True)
    return out.getvalue()
