"""
Glass effect renderer — NowPurchase AI Design Studio.

PillowGlassRenderer v2: Correct multi-layer approach.

ROOT CAUSE of v1 failure:
  brand_config fill value rgba(0,0,0,0.62) is calibrated for CSS backdrop-filter,
  where blur and fill are DECOUPLED. In Pillow they are baked into one composite.
  On a dark background, 62% black fill = near-opaque card.

FIX — 6-stage glass construction:
  Stage 1: Extract region → heavy blur (radius 24) → this is the 'looking through glass' layer
  Stage 2: Edge distortion (barrel lens warp at rounded corners)
  Stage 3: Chromatic aberration (RGB channel split at edges only)
  Stage 4: Gradient surface fill (NOT solid — lighter at top, heavier at bottom)
           Effective opacity is fill_cfg * 0.45 (calibration for Pillow vs CSS)
  Stage 5: Surface specular (soft bright oval, top-centre of card)
  Stage 6: Rim lighting (bright top edge, Fresnel fade, then border stroke)

Visual target: background clearly visible and blurred through card,
premium gradient surface, bright polished top edge. Matches NowPurchase Figma posts.
"""

import os
import json
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


class GlassEffectRenderer(ABC):
    @abstractmethod
    def render(self, background: Image.Image, card_spec: dict, theme: str) -> Image.Image:
        pass


class PillowGlassRenderer(GlassEffectRenderer):

    # Pillow fill calibration: CSS fill opacity * FILL_SCALE = Pillow fill opacity
    # At 0.62 * 0.45 = 0.28 effective opacity — background clearly visible
    FILL_SCALE = 0.45
    BLUR_RADIUS = 24       # Stronger than v1's 16
    SPEC_OPACITY = 0.18    # Surface specular peak brightness
    RIM_OPACITY  = 0.55    # Bright top rim peak

    def render(self, background: Image.Image, card_spec: dict, theme: str) -> Image.Image:
        canvas = background.copy().convert("RGBA")

        pos = card_spec["position"]
        x   = pos["x"] if isinstance(pos.get("x"), int) else 108
        y   = int(pos["y"])
        w   = int(card_spec["width"])
        h   = int(card_spec["height"])
        r   = int(card_spec.get("corner_radius", 24))
        glass = card_spec.get("glass", {})

        fill_opacity_css = self._parse_fill_opacity(
            glass.get("fill", "rgba(0,0,0,0.62)" if theme == "dark"
                                else "rgba(255,255,255,0.78)")
        )
        # Pillow-calibrated opacity (much lower than CSS value)
        fill_opacity = fill_opacity_css * self.FILL_SCALE

        # ── STAGE 0: Drop shadow (behind card) ───────────────────────────
        canvas = self._render_shadow(canvas, x, y, w, h, r, theme)

        # ── STAGE 1: Blurred background — the 'looking through glass' layer
        region = background.crop((x, y, x + w, y + h)).convert("RGB")
        blurred = region.filter(ImageFilter.GaussianBlur(radius=self.BLUR_RADIUS))
        # Paste blurred region onto canvas in card area (no mask — raw rectangle)
        canvas.paste(blurred.convert("RGBA"), (x, y))

        # ── STAGE 2: Edge lens distortion (barrel warp at edges) ──────────
        distorted = self._barrel_distort(np.array(blurred), w, h)

        # ── STAGE 3: Chromatic aberration at edges ─────────────────────────
        distorted = self._chromatic_aberration(distorted, w, h)

        # Composite the distorted layer (only the blurred+distorted background)
        dist_img = Image.fromarray(distorted.astype(np.uint8), "RGB").convert("RGBA")
        dist_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        dist_layer.paste(dist_img, (x, y))
        # Apply rounded rect mask to distorted layer
        dist_mask = self._rounded_rect_mask(w, h, r)
        dist_arr = np.array(dist_layer)
        card_alpha = np.array(dist_mask)
        dist_arr[y:y+h, x:x+w, 3] = card_alpha
        dist_layer = Image.fromarray(dist_arr, "RGBA")
        canvas = Image.alpha_composite(canvas, dist_layer)

        # ── STAGE 4: Gradient surface fill ─────────────────────────────────
        canvas = self._render_gradient_fill(canvas, x, y, w, h, r,
                                            fill_opacity, theme)

        # ── STAGE 5: Surface specular highlight ─────────────────────────────
        canvas = self._render_surface_specular(canvas, x, y, w, h, theme)

        # ── STAGE 6: Rim lighting + border stroke ─────────────────────────
        canvas = self._render_rim_and_border(canvas, x, y, w, h, r, theme)

        return canvas

    # ── Stage helpers ──────────────────────────────────────────────────────

    def _render_shadow(self, canvas, x, y, w, h, r, theme):
        """Drop shadow under the card."""
        shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(shadow_layer)
        shadow_a = 120 if theme == "dark" else 40
        draw.rounded_rectangle(
            [x + 3, y + 10, x + w + 3, y + h + 10],
            radius=r, fill=(0, 0, 0, shadow_a)
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=14))
        return Image.alpha_composite(canvas, shadow_layer)

    def _barrel_distort(self, arr: np.ndarray, w: int, h: int) -> np.ndarray:
        """
        Barrel/lens distortion strongest at edges, zero at centre.
        Pixels near the card edge are warped outward, simulating glass refraction.
        Uses vectorised numpy coordinate mapping — no pixel loops.
        """
        arr_f = arr.astype(np.float32)

        # Normalised coords: -1..1 centred
        ys_n = np.linspace(-1, 1, h)[:, np.newaxis]  # (h,1)
        xs_n = np.linspace(-1, 1, w)[np.newaxis, :]  # (1,w)

        # Radial distance from centre
        r2 = xs_n**2 + ys_n**2

        # Edge proximity (1 at edge, 0 at centre) — smooth with SDF of rounded rect
        edge_x = np.abs(xs_n)
        edge_y = np.abs(ys_n)
        edge_prox = np.maximum(edge_x, edge_y)
        # Only distort within 15% of the edge
        edge_mask = np.clip((edge_prox - 0.70) / 0.30, 0, 1)

        # Barrel strength: push pixels outward from centre at edges
        strength = edge_mask * 5.0   # pixels of displacement

        dx = xs_n / (np.maximum(r2**0.5, 0.01)) * strength
        dy = ys_n / (np.maximum(r2**0.5, 0.01)) * strength

        # Convert to absolute source coords
        src_x = np.clip(
            (xs_n * 0.5 + 0.5) * (w - 1) + dx, 0, w - 1
        )
        src_y = np.clip(
            (ys_n * 0.5 + 0.5) * (h - 1) + dy, 0, h - 1
        )

        # Nearest-neighbour sample (fast, sufficient for glass blur context)
        src_xi = src_x.astype(int)
        src_yi = src_y.astype(int)
        result = arr_f[src_yi, src_xi]

        return result

    def _chromatic_aberration(self, arr: np.ndarray, w: int, h: int) -> np.ndarray:
        """
        Shift R channel slightly right and B channel slightly left at edges.
        Creates a subtle prismatic fringe — the optical signature of glass.
        Only affects the outer 12% of the card.
        """
        arr_out = arr.copy()

        # Edge proximity mask (1 = edge, 0 = centre)
        xs_n = np.linspace(0, 1, w)[np.newaxis, :]
        ys_n = np.linspace(0, 1, h)[:, np.newaxis]
        edge_x = 2 * np.abs(xs_n - 0.5)
        edge_y = 2 * np.abs(ys_n - 0.5)
        edge_prox = np.maximum(edge_x, edge_y)
        edge_mask = np.clip((edge_prox - 0.76) / 0.24, 0, 1)  # outer 12%

        if edge_mask.max() < 0.01:
            return arr_out

        # Shift R channel 2px right, B channel 2px left
        r_shifted = np.roll(arr[:, :, 0], 2, axis=1)
        b_shifted = np.roll(arr[:, :, 2], -2, axis=1)

        blend = edge_mask * 0.6  # 60% shift blend at maximum edge
        arr_out[:, :, 0] = arr[:, :, 0] * (1 - blend) + r_shifted * blend
        arr_out[:, :, 2] = arr[:, :, 2] * (1 - blend) + b_shifted * blend

        return arr_out

    def _render_gradient_fill(self, canvas, x, y, w, h, r, fill_opacity, theme):
        """
        Gradient fill: lighter at top (0.4 * opacity), heavier at bottom (1.0 * opacity).
        This is the defining visual of glass — it catches light unevenly.
        """
        fill_arr = np.zeros((h, w, 4), dtype=np.float32)
        y_vals = np.linspace(0, 1, h)[:, np.newaxis]
        # Top: 40% of fill_opacity, bottom: 100%
        gradient_a = (0.40 + y_vals * 0.60) * fill_opacity * 255

        if theme == "dark":
            fill_arr[:, :, :3] = 0          # Black fill
        else:
            fill_arr[:, :, :3] = 255        # White fill
        fill_arr[:, :, 3] = gradient_a

        fill_img = Image.fromarray(fill_arr.astype(np.uint8), "RGBA")

        # Apply rounded rect mask
        mask = self._rounded_rect_mask(w, h, r)
        fill_arr_uint = fill_arr.astype(np.uint8)
        fill_arr_uint[:, :, 3] = (
            fill_arr_uint[:, :, 3].astype(np.float32) * mask.astype(np.float32) / 255
        ).astype(np.uint8)
        fill_img = Image.fromarray(fill_arr_uint, "RGBA")

        fill_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        fill_layer.paste(fill_img, (x, y))
        return Image.alpha_composite(canvas, fill_layer)

    def _render_surface_specular(self, canvas, x, y, w, h, theme):
        """
        Soft oval specular highlight — simulates ambient light reflected off glass.
        Positioned in the upper-centre of the card.
        Brighter in dark mode (glass surface reflects more against dark background).
        """
        spec_w = int(w * 0.65)
        spec_h = int(h * 0.35)
        spec_x = x + (w - spec_w) // 2   # Centred horizontally
        spec_y = y + 4                    # Near top of card

        # Build radial gradient oval
        xs = np.linspace(-1, 1, spec_w)[np.newaxis, :]
        ys = np.linspace(-1, 1, spec_h)[:, np.newaxis]
        # Squash vertically for oval shape
        dist = np.sqrt(xs**2 + (ys * 1.6)**2)
        falloff = np.maximum(0, 1 - dist * 1.3) ** 2

        peak_opacity = self.SPEC_OPACITY if theme == "dark" else self.SPEC_OPACITY * 0.5
        spec_alpha = (falloff * peak_opacity * 255).astype(np.uint8)

        spec_arr = np.zeros((spec_h, spec_w, 4), dtype=np.uint8)
        spec_arr[:, :, :3] = 255  # White specular
        spec_arr[:, :, 3] = spec_alpha
        spec_img = Image.fromarray(spec_arr, "RGBA")

        spec_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        spec_layer.paste(spec_img, (spec_x, spec_y))
        return Image.alpha_composite(canvas, spec_layer)

    def _render_rim_and_border(self, canvas, x, y, w, h, r, theme):
        """
        Rim lighting: bright gradient from top edge fading down 12px.
        Border: bright 1px top edge, dim 1px full border.
        Inner highlight: 1px at y+1 inside card.
        """
        # Rim light (top edge glow, fades over 12 pixels downward)
        rim_h = 12
        rim_arr = np.zeros((rim_h, w, 4), dtype=np.float32)
        rim_fade = np.linspace(1, 0, rim_h)[:, np.newaxis]  # 1 at top, 0 at bottom
        rim_alpha = rim_fade * self.RIM_OPACITY * 255
        rim_arr[:, :, :3] = 255
        rim_arr[:, :, 3] = rim_alpha
        rim_img = Image.fromarray(rim_arr.astype(np.uint8), "RGBA")

        rim_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        rim_layer.paste(rim_img, (x, y))
        canvas = Image.alpha_composite(canvas, rim_layer)

        # Border strokes
        border_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(border_layer)

        if theme == "dark":
            top_stroke  = (255, 255, 255, 140)   # bright white
            full_stroke = (255, 255, 255, 35)    # dim white
            inner_stroke = (255, 255, 255, 60)
        else:
            top_stroke  = (255, 255, 255, 200)   # very bright (reflective on light)
            full_stroke = (0,   0,   0,   20)    # dim dark
            inner_stroke = (255, 255, 255, 180)

        # Full border (dim)
        draw.rounded_rectangle(
            [x, y, x + w - 1, y + h - 1],
            radius=r, outline=full_stroke, width=1
        )
        # Bright top edge
        draw.line([(x + r + 1, y), (x + w - r - 1, y)],
                  fill=top_stroke, width=1)
        # Inner highlight 1px below top edge
        draw.line([(x + r + 3, y + 1), (x + w - r - 3, y + 1)],
                  fill=inner_stroke, width=1)

        canvas = Image.alpha_composite(canvas, border_layer)
        return canvas

    def _rounded_rect_mask(self, w: int, h: int, r: int) -> np.ndarray:
        """Returns a (h, w) uint8 mask: 255 inside rounded rect, 0 outside."""
        mask_img = Image.new("L", (w, h), 0)
        draw = ImageDraw.Draw(mask_img)
        draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
        return np.array(mask_img)

    @staticmethod
    def _parse_fill_opacity(rgba_str: str) -> float:
        try:
            parts = rgba_str.strip().lstrip("rgba(").rstrip(")").split(",")
            return float(parts[3].strip())
        except Exception:
            return 0.62


class PlaywrightGlassRenderer(GlassEffectRenderer):
    """
    Option B: Playwright headless Chromium — TRUE liquid glass via CSS + SVG filters.

    Produces physically accurate refraction with:
    - Convex squircle bezel displacement map (Apple's preferred lens profile)
    - Snell's Law refraction (IOR 1.5)
    - 3-pass chromatic aberration (R/G/B channels at different scales)
    - backdrop-filter: url(#lg-filter) — real GPU compositing
    - Anti-aliased displacement edges

    Render time: ~3-5 seconds per image.
    Requires: playwright install chromium (one-time setup, ~300MB)
    Config:    system_config.json -> glass_renderer: "playwright"
    """

    def __init__(self):
        template_path = Path(__file__).parent / "glass_template.html"
        if not template_path.exists():
            raise FileNotFoundError(
                f"glass_template.html not found at {template_path}. "
                "This file is required for PlaywrightGlassRenderer."
            )
        self.template = template_path.read_text(encoding="utf-8")

    def render(
        self,
        background: Image.Image,
        card_spec: dict,
        theme: str,
        logo_pill_spec: dict = None,
        logo_image: Image.Image = None,
    ) -> Image.Image:
        """
        Renders background + glass card using real CSS liquid glass.
        Returns 1080×1080 PIL Image (RGBA) with glass card composited.
        Logo pill rendering is intentionally left to Pillow (compositor.py).
        """
        import base64
        import io
        from playwright.sync_api import sync_playwright

        # ── 1. Encode background as base64 JPEG ────────────────────────
        bg_rgb = background.convert("RGB").resize((1080, 1080), Image.LANCZOS)
        buf = io.BytesIO()
        bg_rgb.save(buf, format="JPEG", quality=92)
        bg_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        bg_data_uri = f"data:image/jpeg;base64,{bg_b64}"

        # ── 2. Extract card dimensions ─────────────────────────────────
        x = int(card_spec["position"]["x"])
        y = int(card_spec["position"]["y"])
        w = int(card_spec["width"])
        h = int(card_spec["height"])
        r = int(card_spec["corner_radius"])

        # ── 3. Compute physics parameters ─────────────────────────────
        scale_base = float(card_spec.get("glass", {}).get("refraction_scale", 22))
        scale_r = round(scale_base * 1.00, 1)
        scale_g = round(scale_base * 0.82, 1)
        scale_b = round(scale_base * 0.65, 1)
        bezel_width = min(40, r + 8)

        # ── 4. Theme-conditional visual parameters ─────────────────────
        if theme == "dark":
            glass_fill        = "rgba(0, 0, 0, 0.35)"
            glass_border_top  = "rgba(255, 255, 255, 0.28)"
            glass_border_rest = "rgba(255, 255, 255, 0.08)"
            inner_highlight   = "rgba(255, 255, 255, 0.18)"
            specular_color    = "rgba(255, 255, 255, 0.09)"
            drop_shadow       = "0 8px 32px rgba(0,0,0,0.45), 0 2px 8px rgba(0,0,0,0.30)"
        else:  # light
            glass_fill        = "rgba(255, 255, 255, 0.55)"
            glass_border_top  = "rgba(0, 0, 0, 0.12)"
            glass_border_rest = "rgba(0, 0, 0, 0.05)"
            inner_highlight   = "rgba(255, 255, 255, 0.90)"
            specular_color    = "rgba(255, 255, 255, 0.25)"
            drop_shadow       = "0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.08)"

        # ── 5. Pill placeholders (pill is rendered by Pillow, not here) ───
        pill_w = 200
        pill_h = 56
        pill_x = (1080 - pill_w) // 2
        pill_y = 72
        pill_fill   = "rgba(0,0,0,0)" if theme == "dark" else "rgba(255,255,255,0)"
        pill_border = "rgba(0,0,0,0)"
        empty_1px = (
            "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )

        # ── 6. Template substitution ───────────────────────────────────
        html = self.template
        substitutions = {
            "{{BG_DATA_URI}}":          bg_data_uri,
            "{{CARD_X}}":               str(x),
            "{{CARD_Y}}":               str(y),
            "{{CARD_W}}":               str(w),
            "{{CARD_H}}":               str(h),
            "{{CARD_RADIUS}}":          str(r),
            "{{BEZEL_WIDTH}}":          str(bezel_width),
            "{{REFRACTION_SCALE}}":     str(scale_base),
            "{{REFRACTION_SCALE_R}}":   str(scale_r),
            "{{REFRACTION_SCALE_G}}":   str(scale_g),
            "{{REFRACTION_SCALE_B}}":   str(scale_b),
            "{{GLASS_FILL}}":           glass_fill,
            "{{GLASS_BORDER_TOP}}":     glass_border_top,
            "{{GLASS_BORDER_REST}}":    glass_border_rest,
            "{{INNER_HIGHLIGHT}}":      inner_highlight,
            "{{SPECULAR_COLOR}}":       specular_color,
            "{{DROP_SHADOW}}":          drop_shadow,
            "{{PILL_X}}":               str(pill_x),
            "{{PILL_Y}}":               str(pill_y),
            "{{PILL_W}}":               str(pill_w),
            "{{PILL_H}}":               str(pill_h),
            "{{PILL_FILL}}":            pill_fill,
            "{{PILL_BORDER}}":          pill_border,
            "{{PILL_LOGO_DATA_URI}}":   empty_1px,
            "{{PILL_LOGO_W}}":          "1",
            "{{PILL_LOGO_H}}":          "1",
        }
        for token, value in substitutions.items():
            html = html.replace(token, value)

        # ── 7. Launch Playwright Chromium ──────────────────────────────
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--force-device-scale-factor=1",
                ],
            )
            page = browser.new_page(
                viewport={"width": 1080, "height": 1080},
                device_scale_factor=1,
            )
            page.set_content(html, wait_until="domcontentloaded")
            page.wait_for_function(
                "() => window.__GLASS_READY__ === true",
                timeout=8000,
            )
            page.wait_for_timeout(150)
            screenshot_bytes = page.screenshot(
                type="png",
                clip={"x": 0, "y": 0, "width": 1080, "height": 1080},
                omit_background=False,
            )
            browser.close()

        # ── 8. Convert to PIL Image ────────────────────────────────────
        result = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
        return result


def build_glass_renderer(config: dict | None = None) -> GlassEffectRenderer:
    if config is None:
        cfg_path = Path(__file__).parent.parent.parent.parent / "system_config.json"
        with open(cfg_path) as f:
            config = json.load(f)
    if config.get("glass_renderer") == "playwright":
        return PlaywrightGlassRenderer()
    return PillowGlassRenderer()


def _parse_fill_opacity(rgba_str: str) -> float:
    return PillowGlassRenderer._parse_fill_opacity(rgba_str)
