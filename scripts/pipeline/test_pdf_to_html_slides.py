import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz

from pdf_to_html_slides import (
    NOTEBOOKLM_LOGO_BBOX,
    _median_color,
    mask_notebooklm_logo,
)


def _solid_pixmap(w: int, h: int, color: tuple[int, int, int]) -> fitz.Pixmap:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, w, h), False)
    pix.set_rect(pix.irect, color)
    return pix


def _avg_pixel(pix: fitz.Pixmap, x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int]:
    rs = gs = bs = 0
    n = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = pix.pixel(x, y)
            rs += r; gs += g; bs += b; n += 1
    return (rs // n, gs // n, bs // n)


class MaskNotebookLMLogoTests(TestCase):
    def test_logo_region_replaced_with_background_color(self):
        # Dark navy slide with a bright logo patch in the bottom-right.
        bg = (30, 40, 55)
        logo = (245, 245, 245)
        W, H = 400, 240
        pix = _solid_pixmap(W, H, bg)
        fx0, fy0, fx1, fy1 = NOTEBOOKLM_LOGO_BBOX
        lx0 = int(W * fx0); ly0 = int(H * fy0)
        lx1 = int(W * fx1); ly1 = int(H * fy1)
        pix.set_rect(fitz.IRect(lx0, ly0, lx1, ly1), logo)
        # Sanity: pre-mask, logo region is bright.
        before = _avg_pixel(pix, lx0, ly0, lx1, ly1)
        self.assertGreater(before[0], 200)

        mask_notebooklm_logo(pix)

        after = _avg_pixel(pix, lx0, ly0, lx1, ly1)
        # After masking, logo region should match BG within tolerance.
        for ch_after, ch_bg in zip(after, bg):
            self.assertLessEqual(abs(ch_after - ch_bg), 5)

    def test_outside_logo_region_untouched(self):
        bg = (200, 50, 50)
        W, H = 400, 240
        pix = _solid_pixmap(W, H, bg)
        # Place a unique sentinel pixel block outside the logo bbox (top-left quadrant).
        sentinel = (10, 220, 10)
        pix.set_rect(fitz.IRect(20, 20, 60, 60), sentinel)

        mask_notebooklm_logo(pix)

        sample = _avg_pixel(pix, 20, 20, 60, 60)
        self.assertEqual(sample, sentinel)

    def test_rejects_alpha_pixmap(self):
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), True)
        with self.assertRaises(ValueError):
            mask_notebooklm_logo(pix)

    def test_median_color_matches_uniform_field(self):
        pix = _solid_pixmap(100, 100, (123, 45, 67))
        self.assertEqual(_median_color(pix, 0, 0, 100, 100), (123, 45, 67))
