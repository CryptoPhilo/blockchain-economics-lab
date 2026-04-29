#!/usr/bin/env python3
"""
pdf_to_html_slides.py — Convert NotebookLM-generated slide PDFs into
a self-contained HTML viewer with fixed-size page-flip navigation.

Each PDF page is rendered at high DPI, base64-encoded, and embedded in a
single HTML file with keyboard/click/touch navigation.

Usage:
    python pdf_to_html_slides.py \
        --pdf /path/to/slides.pdf \
        --output /path/to/output.html \
        --title "Humanity Protocol" \
        --lang ko \
        --dpi 200
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import sys
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def compress_slide_pdf(
    input_path: str, output_path: str, jpeg_quality: int = 80,
) -> str:
    """Compress a slide PDF by converting embedded PNGs to JPEG.
    Typically reduces NotebookLM PDFs from ~6MB to ~800KB (87% reduction)."""
    if not HAS_PIL:
        raise ImportError("Pillow required for PDF compression: pip install Pillow")
    src = fitz.open(input_path)
    dst = fitz.open()
    for i in range(src.page_count):
        page = src[i]
        pix = page.get_pixmap(alpha=False)
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=jpeg_quality, optimize=True)
        new_page = dst.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, stream=buf.getvalue())
    dst.save(output_path, garbage=4, deflate=True)
    dst.close()
    src.close()
    orig_kb = os.path.getsize(input_path) / 1024
    comp_kb = os.path.getsize(output_path) / 1024
    print(f"  Compressed: {orig_kb:.0f} KB → {comp_kb:.0f} KB ({comp_kb/orig_kb*100:.0f}%)")
    return output_path


# NotebookLM exports place a logo (icon + "NotebookLM" text) at the bottom-right of every
# page. Coordinates measured from sample PDFs (16:9 layout); see BCE-1095.
NOTEBOOKLM_LOGO_BBOX = (0.90, 0.955, 1.00, 1.00)  # (x0, y0, x1, y1) as page fractions


def _median_color(pix: fitz.Pixmap, x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int]:
    """Return per-channel median RGB of pixels in [x0,x1)x[y0,y1) on an alpha=False pixmap."""
    x0 = max(0, x0); y0 = max(0, y0)
    x1 = min(pix.width, x1); y1 = min(pix.height, y1)
    rs, gs, bs = [], [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = pix.pixel(x, y)
            rs.append(r); gs.append(g); bs.append(b)
    if not rs:
        return (0, 0, 0)
    rs.sort(); gs.sort(); bs.sort()
    m = len(rs) // 2
    return (rs[m], gs[m], bs[m])


def mask_notebooklm_logo(
    pix: fitz.Pixmap, bbox: tuple[float, float, float, float] = NOTEBOOKLM_LOGO_BBOX,
) -> fitz.Pixmap:
    """Inpaint the NotebookLM logo by replicating the row directly above the bbox.

    For a logo pinned to the bottom-right corner, the row immediately above the logo
    samples the local background at exactly the boundary the eye expects to see
    extended. Tiling that row down through the bbox uses the *actual* local color
    (not a global median estimate) and avoids duplicating distant horizontal
    features that a multi-row copy would shift downward.

    Falls back to the previous median-color fill when no row above is available.
    Mutates and returns the pixmap. Requires alpha=False, 3-channel RGB.
    """
    if pix.alpha or pix.n != 3:
        raise ValueError("mask_notebooklm_logo requires an alpha=False RGB pixmap")
    W, H = pix.width, pix.height
    fx0, fy0, fx1, fy1 = bbox
    x0 = int(W * fx0); y0 = int(H * fy0)
    x1 = int(W * fx1); y1 = int(H * fy1)
    bw = x1 - x0; bh = y1 - y0
    if bw <= 0 or bh <= 0:
        return pix

    arr = np.frombuffer(pix.samples_mv, dtype=np.uint8).reshape(H, W, pix.n)

    if y0 >= 1:
        edge_row = arr[y0 - 1:y0, x0:x1]  # shape (1, bw, 3)
        arr[y0:y1, x0:x1] = edge_row  # broadcasts across bh rows
    else:
        left = _median_color(pix, x0 - bw, y0, x0, y1)
        pix.set_rect(fitz.IRect(x0, y0, x1, y1), left)
    return pix


def extract_pages_base64(
    pdf_path: str,
    dpi: int = 200,
    fmt: str = "jpeg",
    quality: int = 80,
    mask_logo: bool = True,
) -> list[tuple[str, str]]:
    """Render each PDF page to a base64-encoded image. Returns [(mime, b64), ...].
    When mask_logo is True (default), paints over the NotebookLM logo at the bottom-right of each page."""
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pages = []
    for i in range(doc.page_count):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat, alpha=False)
        if mask_logo:
            mask_notebooklm_logo(pix)
        if fmt == "jpeg":
            raw = pix.tobytes("jpeg", jpg_quality=quality)
            mime = "image/jpeg"
        else:
            raw = pix.tobytes("png")
            mime = "image/png"
        b64 = base64.b64encode(raw).decode('ascii')
        pages.append((mime, b64))
    doc.close()
    return pages


def build_viewer_html(
    pages_b64: list[str],
    title: str = "Slide Viewer",
    lang: str = "ko",
    aspect_ratio: tuple[int, int] = (16, 9),
) -> str:
    """Build a self-contained HTML slide viewer with page-flip navigation."""
    total = len(pages_b64)

    images_js = ",\n".join(
        f'    "data:{mime};base64,{b64}"' for mime, b64 in pages_b64
    )

    ar_w, ar_h = aspect_ratio
    aspect_pct = (ar_h / ar_w) * 100

    html = f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
  font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif;
  background: #1a1a2e;
  color: #e0e0e0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  user-select: none;
  -webkit-user-select: none;
}}

.viewer-container {{
  width: 90vw;
  max-width: 1280px;
  position: relative;
}}

.slide-wrapper {{
  position: relative;
  width: 100%;
  padding-bottom: {aspect_pct:.4f}%;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}}

.slide-wrapper img {{
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  object-fit: contain;
  background: #111;
}}

.nav-overlay {{
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  display: flex;
  z-index: 10;
}}

.nav-zone {{
  flex: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  opacity: 0;
  transition: opacity 0.2s;
}}
.nav-zone:hover {{ opacity: 1; }}
.nav-zone.left {{ justify-content: flex-start; padding-left: 16px; }}
.nav-zone.right {{ justify-content: flex-end; padding-right: 16px; }}

.nav-arrow {{
  width: 48px; height: 48px;
  background: rgba(0,0,0,0.5);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}}
.nav-arrow svg {{
  width: 24px; height: 24px;
  fill: none;
  stroke: #fff;
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}}

.controls {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 16px;
}}

.page-indicator {{
  font-size: 14px;
  font-weight: 700;
  color: #aaa;
  min-width: 80px;
  text-align: center;
}}

.dot-nav {{
  display: flex;
  gap: 6px;
  align-items: center;
}}
.dot {{
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #555;
  cursor: pointer;
  transition: all 0.2s;
}}
.dot.active {{
  background: #B8860B;
  width: 24px;
  border-radius: 4px;
}}

.title-bar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 4px;
}}
.title-bar h1 {{
  font-size: 18px;
  font-weight: 700;
  color: #ccc;
}}
.title-bar .badge {{
  background: #B8860B;
  color: #fff;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
}}

.fullscreen-btn {{
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  color: #ccc;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  transition: all 0.2s;
}}
.fullscreen-btn:hover {{
  background: rgba(255,255,255,0.2);
  color: #fff;
}}
</style>
</head>
<body>

<div class="viewer-container" id="viewer">
  <div class="title-bar">
    <h1>{title}</h1>
    <div style="display:flex;gap:8px;align-items:center;">
      <span class="badge">BCE Lab</span>
      <button class="fullscreen-btn" onclick="toggleFullscreen()">⛶ Fullscreen</button>
    </div>
  </div>

  <div class="slide-wrapper" id="slideWrapper">
    <img id="slideImg" src="" alt="Slide" draggable="false">
    <div class="nav-overlay">
      <div class="nav-zone left" onclick="prevSlide()">
        <div class="nav-arrow">
          <svg viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"/></svg>
        </div>
      </div>
      <div class="nav-zone right" onclick="nextSlide()">
        <div class="nav-arrow">
          <svg viewBox="0 0 24 24"><polyline points="9 6 15 12 9 18"/></svg>
        </div>
      </div>
    </div>
  </div>

  <div class="controls">
    <span class="page-indicator" id="pageIndicator">1 / {total}</span>
    <div class="dot-nav" id="dotNav"></div>
  </div>
</div>

<script>
const slides = [
{images_js}
];

let current = 0;
const total = slides.length;
const img = document.getElementById('slideImg');
const indicator = document.getElementById('pageIndicator');
const dotNav = document.getElementById('dotNav');

// Build dots
for (let i = 0; i < total; i++) {{
  const dot = document.createElement('div');
  dot.className = 'dot' + (i === 0 ? ' active' : '');
  dot.onclick = () => goTo(i);
  dotNav.appendChild(dot);
}}

function goTo(idx) {{
  current = Math.max(0, Math.min(total - 1, idx));
  img.src = slides[current];
  indicator.textContent = (current + 1) + ' / ' + total;
  document.querySelectorAll('.dot').forEach((d, i) => {{
    d.className = 'dot' + (i === current ? ' active' : '');
  }});
}}

function nextSlide() {{ goTo(current + 1); }}
function prevSlide() {{ goTo(current - 1); }}

// Keyboard navigation
document.addEventListener('keydown', (e) => {{
  if (e.key === 'ArrowRight' || e.key === ' ') {{ e.preventDefault(); nextSlide(); }}
  if (e.key === 'ArrowLeft') {{ e.preventDefault(); prevSlide(); }}
  if (e.key === 'Home') {{ e.preventDefault(); goTo(0); }}
  if (e.key === 'End') {{ e.preventDefault(); goTo(total - 1); }}
  if (e.key === 'f' || e.key === 'F') {{ toggleFullscreen(); }}
}});

// Touch swipe
let touchStartX = 0;
const wrapper = document.getElementById('slideWrapper');
wrapper.addEventListener('touchstart', (e) => {{ touchStartX = e.touches[0].clientX; }});
wrapper.addEventListener('touchend', (e) => {{
  const dx = e.changedTouches[0].clientX - touchStartX;
  if (Math.abs(dx) > 50) {{
    if (dx < 0) nextSlide();
    else prevSlide();
  }}
}});

function toggleFullscreen() {{
  const el = document.getElementById('viewer');
  if (!document.fullscreenElement) {{
    el.requestFullscreen?.() || el.webkitRequestFullscreenElement?.();
  }} else {{
    document.exitFullscreen?.() || document.webkitExitFullscreen?.();
  }}
}}

// Load first slide
goTo(0);
</script>
</body>
</html>'''
    return html


def convert_pdf_to_html_slides(
    pdf_path: str,
    output_path: str | None = None,
    title: str = "Slide Viewer",
    lang: str = "ko",
    dpi: int = 200,
    mask_logo: bool = True,
) -> str:
    """Main entry: convert a PDF to an HTML slide viewer."""
    if output_path is None:
        stem = Path(pdf_path).stem
        output_path = str(Path(pdf_path).parent / f"{stem}_slides.html")

    print(f"[1/2] Extracting pages from {pdf_path} at {dpi} DPI (JPEG)"
          f"{' with NotebookLM logo masking' if mask_logo else ''}...")
    pages = extract_pages_base64(pdf_path, dpi=dpi, fmt="jpeg", quality=80, mask_logo=mask_logo)
    print(f"  ✓ {len(pages)} pages extracted")

    print(f"[2/2] Building HTML viewer...")
    html = build_viewer_html(pages, title=title, lang=lang)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"  ✓ HTML viewer: {output_path} ({size_kb:,.1f} KB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF slides to HTML viewer with page-flip navigation"
    )
    parser.add_argument("--pdf", required=True, help="Input PDF path")
    parser.add_argument("--output", default=None, help="Output HTML path")
    parser.add_argument("--title", default="Slide Viewer", help="Viewer title")
    parser.add_argument("--lang", default="ko", help="Language code")
    parser.add_argument("--dpi", type=int, default=200, help="Render DPI (default: 200)")
    parser.add_argument(
        "--no-mask-logo", dest="mask_logo", action="store_false",
        help="Disable NotebookLM logo masking (use when input PDF is not from NotebookLM)",
    )
    parser.set_defaults(mask_logo=True)
    args = parser.parse_args()

    convert_pdf_to_html_slides(
        pdf_path=args.pdf,
        output_path=args.output,
        title=args.title,
        lang=args.lang,
        dpi=args.dpi,
        mask_logo=args.mask_logo,
    )


if __name__ == '__main__':
    main()
