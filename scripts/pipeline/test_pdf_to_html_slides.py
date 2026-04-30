import sys
from pathlib import Path
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz

from pdf_to_html_slides import (
    COPYRIGHT_OVERLAY_COLOR,
    NOTEBOOKLM_LOGO_BBOX,
    _median_color,
    mask_notebooklm_logo,
    overlay_copyright_notice,
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

    def test_logo_region_uses_exact_boundary_color(self):
        # Edge-row tile uses the *actual* adjacent pixel value, not a median
        # estimate, so a uniform background is reproduced byte-exact (no ±5 slop).
        bg = (37, 91, 158)
        logo = (250, 250, 250)
        W, H = 400, 240
        pix = _solid_pixmap(W, H, bg)
        fx0, fy0, fx1, fy1 = NOTEBOOKLM_LOGO_BBOX
        lx0 = int(W * fx0); ly0 = int(H * fy0)
        lx1 = int(W * fx1); ly1 = int(H * fy1)
        pix.set_rect(fitz.IRect(lx0, ly0, lx1, ly1), logo)

        mask_notebooklm_logo(pix)

        for y in (ly0, (ly0 + ly1) // 2, ly1 - 1):
            for x in (lx0, (lx0 + lx1) // 2, lx1 - 1):
                self.assertEqual(pix.pixel(x, y), bg)

    def test_logo_region_resists_anti_alias_bleed_above_bbox(self):
        # Regression for BCE-1701 follow-up: when the row directly above the
        # bbox contains stray dark pixels (anti-aliased logo bottom-edge bleed),
        # a single-row sample would tile those pixels into vertical streaks. The
        # per-column median over a multi-row strip must reject them as outliers.
        bg = (245, 245, 240)
        bleed = (40, 40, 40)  # dark anti-alias pixel imitating logo edge
        logo = (255, 255, 255)
        W, H = 800, 480
        pix = _solid_pixmap(W, H, bg)
        fx0, fy0, fx1, fy1 = NOTEBOOKLM_LOGO_BBOX
        lx0 = int(W * fx0); ly0 = int(H * fy0)
        lx1 = int(W * fx1); ly1 = int(H * fy1)
        # Put bleed pixels on the SINGLE row directly above the bbox at scattered
        # columns (mimicking dotted bottom edge of "NotebookLM" letters). Other
        # rows in the source strip remain bg.
        for x in range(lx0, lx1, 4):
            pix.set_rect(fitz.IRect(x, ly0 - 1, x + 1, ly0), bleed)
        pix.set_rect(fitz.IRect(lx0, ly0, lx1, ly1), logo)

        mask_notebooklm_logo(pix)

        # Inside the bbox should be uniformly bg — the median across the 3-row
        # source strip discards the bleed row as an outlier.
        for y in (ly0, (ly0 + ly1) // 2, ly1 - 1):
            for x in (lx0, lx0 + 7, (lx0 + lx1) // 2, lx1 - 1):
                self.assertEqual(pix.pixel(x, y), bg)

    def test_logo_region_does_not_duplicate_pattern_above(self):
        # A horizontal rule sitting two rows above the bbox must NOT be duplicated
        # inside the bbox (would happen with a multi-row strip copy). Edge-row
        # tile only replicates the row directly above, so the rule stays put.
        bg = (245, 245, 245)
        rule = (20, 20, 200)
        logo = (255, 255, 255)
        W, H = 400, 240
        pix = _solid_pixmap(W, H, bg)
        fx0, fy0, fx1, fy1 = NOTEBOOKLM_LOGO_BBOX
        lx0 = int(W * fx0); ly0 = int(H * fy0)
        lx1 = int(W * fx1); ly1 = int(H * fy1)
        # Rule two rows above the bbox; the row directly adjacent stays bg.
        pix.set_rect(fitz.IRect(0, ly0 - 2, W, ly0 - 1), rule)
        pix.set_rect(fitz.IRect(lx0, ly0, lx1, ly1), logo)

        mask_notebooklm_logo(pix)

        # Inside the bbox should be uniformly bg (no rule duplication).
        for y in (ly0, ly0 + (ly1 - ly0) // 2, ly1 - 1):
            self.assertEqual(pix.pixel((lx0 + lx1) // 2, y), bg)
        # The original rule above the bbox is untouched.
        self.assertEqual(pix.pixel((lx0 + lx1) // 2, ly0 - 2), rule)


class OverlayCopyrightNoticeTests(TestCase):
    def test_overlay_writes_dark_text_inside_bbox(self):
        # Render copyright text on a clean light-bg pixmap and verify pixels in
        # the bbox interior shifted toward the text color (we don't pin exact
        # glyph positions because they depend on font availability).
        bg = (245, 245, 240)
        W, H = 1280, 720
        pix = _solid_pixmap(W, H, bg)

        overlay_copyright_notice(pix)

        fx0, fy0, fx1, fy1 = NOTEBOOKLM_LOGO_BBOX
        lx0 = int(W * fx0); ly0 = int(H * fy0)
        lx1 = int(W * fx1); ly1 = int(H * fy1)
        # Sample the entire bbox; at least one pixel must be appreciably darker
        # than bg (= a glyph stroke landed there).
        any_glyph_pixel = False
        for y in range(ly0, ly1):
            for x in range(lx0, lx1):
                px = pix.pixel(x, y)
                if px != bg:
                    any_glyph_pixel = True
                    break
            if any_glyph_pixel:
                break
        self.assertTrue(any_glyph_pixel, "overlay should leave at least one non-bg pixel in bbox")

    def test_overlay_does_not_touch_outside_bbox(self):
        bg = (245, 245, 240)
        W, H = 1280, 720
        pix = _solid_pixmap(W, H, bg)

        overlay_copyright_notice(pix)

        fx0, fy0, fx1, fy1 = NOTEBOOKLM_LOGO_BBOX
        lx0 = int(W * fx0); ly0 = int(H * fy0)
        # Sample a few points well outside the bbox.
        for x, y in [(10, 10), (W // 2, H // 2), (lx0 - 10, ly0 - 10), (10, H - 5)]:
            self.assertEqual(pix.pixel(x, y), bg)

    def test_overlay_rejects_alpha_pixmap(self):
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), True)
        with self.assertRaises(ValueError):
            overlay_copyright_notice(pix)
