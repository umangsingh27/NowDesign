"""
Image compositor for NowPurchase AI Design Studio.

Takes a validated LayoutPlan and a background PIL Image.
Produces a 1080×1080 PNG as bytes.

The compositor is deterministic: same LayoutPlan + same background = same output.
It makes zero creative decisions — the Planner already made all of them.
All colour values are pre-resolved in the LayoutPlan.
"""

import io
import json
import re
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.core.compositor.glass_renderer import GlassEffectRenderer
from backend.core.models import LayoutPlan


_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class ImageCompositor:
    """
    Receives a LayoutPlan + background image, returns 1080×1080 PNG bytes.
    Inject a GlassEffectRenderer to swap the glass implementation.
    """

    def __init__(self, glass_renderer: GlassEffectRenderer):
        self.glass_renderer = glass_renderer
        self._font_cache: dict[str, ImageFont.FreeTypeFont] = {}

    # ── Public API ────────────────────────────────────────────────────────

    def composite(self, layout_plan: LayoutPlan, background: Image.Image) -> bytes:
        """Main entry point. Returns PNG bytes."""
        # 1. Prepare background
        canvas = self._prepare_background(background)

        # 2. Global overlay (slight darkening for dark, slight brightening for light)
        if layout_plan.theme == "dark":
            canvas = self._apply_global_overlay(canvas, (0, 0, 0), 0.15)
        else:
            canvas = self._apply_global_overlay(canvas, (255, 255, 255), 0.08)

        # Resolve glass_card position for relative element placement.
        # glass_card.position is dict[str, int] in the model.
        gc_pos = layout_plan.glass_card.position
        gc_x_raw = gc_pos.get("x", 108) if isinstance(gc_pos, dict) else 108
        gc_x = gc_x_raw if isinstance(gc_x_raw, int) else 108
        gc_y = gc_pos.get("y", 0) if isinstance(gc_pos, dict) else 0

        # 3. Render glass card
        card_spec = layout_plan.glass_card.model_dump()
        card_spec["position"] = {"x": gc_x, "y": gc_y}
        canvas = self.glass_renderer.render(canvas, card_spec, layout_plan.theme)

        # 4. Render elements in input order (stable sort preserves planner z-order).
        for element in layout_plan.elements:
            el_dict = element.model_dump() if hasattr(element, "model_dump") else element
            el_type = el_dict.get("type", "")

            if el_type == "text":
                canvas = self._render_text(canvas, el_dict, gc_x, gc_y)
            elif el_type in ("line", "horizontal_line"):
                canvas = self._render_line(canvas, el_dict, gc_x, gc_y)

        # 5. Render divider if present
        if layout_plan.divider:
            div_dict = (
                layout_plan.divider.model_dump()
                if hasattr(layout_plan.divider, "model_dump")
                else layout_plan.divider
            )
            canvas = self._render_line(canvas, div_dict, gc_x, gc_y)

        # 6. Render logo pill
        canvas = self._render_logo_pill(canvas, layout_plan.logo_pill.model_dump(), layout_plan.theme)

        # 7. Render bottom tag
        if layout_plan.bottom_tag:
            bt = layout_plan.bottom_tag.model_dump()
            canvas = self._render_text(canvas, bt, gc_x, gc_y)

        # 8. Export
        return self._export_png(canvas, layout_plan.theme)

    # ── Background ────────────────────────────────────────────────────────

    def _prepare_background(self, img: Image.Image) -> Image.Image:
        """Centre-crop and resize to exactly 1080×1080, convert to RGBA."""
        target = 1080
        w, h = img.size
        scale = max(target / w, target / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - target) // 2
        top = (new_h - target) // 2
        cropped = resized.crop((left, top, left + target, top + target))
        return cropped.convert("RGBA")

    def _apply_global_overlay(
        self,
        canvas: Image.Image,
        color: tuple,
        opacity: float
    ) -> Image.Image:
        """Subtle global tint to improve glass card readability."""
        overlay = Image.new("RGBA", canvas.size, (*color, int(opacity * 255)))
        return Image.alpha_composite(canvas, overlay)

    # ── Text ──────────────────────────────────────────────────────────────

    def _render_text(
        self,
        canvas: Image.Image,
        element: dict,
        gc_x: int = 0,
        gc_y: int = 0
    ) -> Image.Image:
        """Render a text element onto the canvas."""
        content = element.get("content", "")
        if not content:
            return canvas

        font_path = element.get("font") or ""
        font_size = element.get("size") or 24
        font = self._load_font(font_path, font_size)

        # Resolve position
        pos = element.get("position", {})
        rel_to = pos.get("relative_to")
        raw_x = pos.get("x", 0)
        raw_y = pos.get("y", 0)

        if rel_to == "glass_card":
            base_x, base_y = gc_x, gc_y
            card_padding = 0
        else:
            base_x, base_y = 0, 0

        # Handle centered x
        if raw_x == "center":
            abs_x = None  # Will center after measuring
        else:
            abs_x = base_x + int(raw_x)
        abs_y = base_y + int(raw_y)

        # Text transform
        text = content
        transform = element.get("text_transform", "")
        if transform == "uppercase":
            text = text.upper()

        # Wrap text (Optional fields may be None — coerce to defaults)
        max_width = element.get("max_width") or 900
        max_lines = element.get("max_lines")
        lines = self._wrap_text(text, font, max_width)
        if max_lines:
            lines = lines[:max_lines]

        # Parse colour
        color = self._parse_color(element.get("color") or "#FFFFFF")

        # Draw lines
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        line_height = int(font_size * (element.get("line_height") or 1.25))
        curr_y = abs_y

        for line in lines:
            if abs_x is None:
                # Centre horizontally
                bbox = draw.textbbox((0, 0), line, font=font)
                line_w = bbox[2] - bbox[0]
                draw_x = (canvas.width - line_w) // 2
            else:
                draw_x = abs_x
            draw.text((draw_x, curr_y), line, font=font, fill=color)
            curr_y += line_height

        return Image.alpha_composite(canvas, layer)

    def _load_font(self, font_path: str, size: int) -> ImageFont.FreeTypeFont:
        """Load font from cache or disk. Falls back to default if not found."""
        cache_key = f"{font_path}_{size}"
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        abs_path = _PROJECT_ROOT / "backend" / font_path
        if abs_path.exists():
            try:
                font = ImageFont.truetype(str(abs_path), size)
                self._font_cache[cache_key] = font
                return font
            except Exception:
                pass

        # Fallback: scale the default font size
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:
            font = ImageFont.load_default()
        self._font_cache[cache_key] = font
        return font

    def _wrap_text(self, text: str, font, max_width: int) -> list[str]:
        """Word-wrap text to fit within max_width pixels."""
        dummy = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy)
        words = text.split()
        lines, current = [], []
        for word in words:
            test = " ".join(current + [word])
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width or not current:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines or [text]

    # ── Lines ─────────────────────────────────────────────────────────────

    def _render_line(
        self,
        canvas: Image.Image,
        element: dict,
        gc_x: int = 0,
        gc_y: int = 0
    ) -> Image.Image:
        """Render a horizontal divider line."""
        pos = element.get("position", {})
        rel_to = pos.get("relative_to")
        base_x = gc_x if rel_to == "glass_card" else 0
        base_y = gc_y if rel_to == "glass_card" else 0

        x = base_x + int(pos.get("x") or 0)
        y = base_y + int(pos.get("y") or 0)
        width = element.get("width") or 864
        thickness = element.get("thickness") or 1
        color = self._parse_color(element.get("color") or "rgba(21,121,190,0.50)")

        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        draw.line([(x, y), (x + width, y)], fill=color, width=thickness)
        return Image.alpha_composite(canvas, layer)

    # ── Logo pill ─────────────────────────────────────────────────────────

    def _render_logo_pill(
        self,
        canvas: Image.Image,
        pill_spec: dict,
        theme: str
    ) -> Image.Image:
        """Render the glass pill with logo inside. Hug-content sizing."""
        logo_spec = pill_spec.get("logo", {})
        logo_asset = logo_spec.get("asset", "")
        max_logo_w = logo_spec.get("max_width", 180)

        # Load logo
        logo_img = None
        if logo_asset:
            abs_logo = _PROJECT_ROOT / "backend" / logo_asset
            if abs_logo.exists():
                try:
                    logo_img = Image.open(str(abs_logo)).convert("RGBA")
                except Exception:
                    pass

        if logo_img:
            scale = min(max_logo_w / logo_img.width, 1.0)
            logo_w = int(logo_img.width * scale)
            logo_h = int(logo_img.height * scale)
            logo_img = logo_img.resize((logo_w, logo_h), Image.LANCZOS)
        else:
            # Fallback: text placeholder
            logo_w, logo_h = max_logo_w, 32

        # Pill dimensions
        padding = pill_spec.get("padding", {})
        h_pad = padding.get("horizontal", 24)
        v_pad = padding.get("vertical", 12)
        pill_w = max(logo_w + h_pad * 2, pill_spec.get("min_width", 160))
        pill_h = pill_spec.get("height", 56)
        corner_r = pill_spec.get("corner_radius", 100)

        # Centre pill horizontally
        pill_x = (canvas.width - pill_w) // 2
        pill_y = pill_spec.get("position", {}).get("y", 72)

        # Glass fill
        glass = pill_spec.get("glass", {})
        fill_str = glass.get("fill", "rgba(0,0,0,0.60)")
        fill_rgba = self._parse_color(fill_str)
        border_str = glass.get("border", "rgba(255,255,255,0.20)")
        border_rgba = self._parse_color(border_str)

        # Draw pill
        pill_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(pill_layer)
        draw.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=corner_r,
            fill=fill_rgba,
            outline=border_rgba,
            width=1
        )
        canvas = Image.alpha_composite(canvas, pill_layer)

        # Place logo inside pill (centred)
        logo_x = pill_x + (pill_w - logo_w) // 2
        logo_y = pill_y + (pill_h - logo_h) // 2

        if logo_img:
            canvas.alpha_composite(logo_img, dest=(logo_x, logo_y))
        else:
            # Draw text fallback
            fallback_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            draw_f = ImageDraw.Draw(fallback_layer)
            fb_font = self._load_font("assets/fonts/Urbanist-Bold.ttf", 20)
            draw_f.text(
                (logo_x, logo_y),
                "NowPurchase",
                font=fb_font,
                fill=(255, 255, 255, 220)
            )
            canvas = Image.alpha_composite(canvas, fallback_layer)

        return canvas

    # ── Export ────────────────────────────────────────────────────────────

    def _export_png(self, canvas: Image.Image, theme: str) -> bytes:
        """Flatten RGBA to RGB and encode as PNG bytes."""
        bg_color = (2, 12, 19) if theme == "dark" else (242, 242, 242)
        rgb = Image.new("RGB", canvas.size, bg_color)
        rgb.paste(canvas, mask=canvas.split()[3])
        buf = io.BytesIO()
        rgb.save(buf, format="PNG", optimize=False)
        return buf.getvalue()

    # ── Utilities ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_color(color_str: str) -> tuple:
        """
        Parse any CSS color string to an RGBA tuple (0–255 each).
        Handles: #RRGGBB, #RGB, rgba(r,g,b,a), rgb(r,g,b)
        """
        s = color_str.strip()
        if s.startswith("#"):
            s = s.lstrip("#")
            if len(s) == 3:
                s = "".join(c * 2 for c in s)
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            return (r, g, b, 255)
        rgba_match = re.match(
            r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)",
            s
        )
        if rgba_match:
            r, g, b = int(rgba_match[1]), int(rgba_match[2]), int(rgba_match[3])
            a = int(float(rgba_match[4]) * 255) if rgba_match[4] else 255
            return (r, g, b, a)
        # Fallback: white
        return (255, 255, 255, 255)
