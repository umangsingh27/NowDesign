"""
Creator Skills — six skills used exclusively by the Creator Agent.

1. GenerateBackground          — pick from library or call Gemini Imagen 4
2. ValidateBackgroundLuminance — verify luminance in centre zone meets theme target
3. RenderGlassEffect           — delegate to configured GlassEffectRenderer
4. RenderTextElement           — draw a single text element onto the canvas
5. PlaceLogo                   — render the glass logo pill with the logo inside
6. CompositeFinal              — flatten + save the final 1080x1080 PNG
"""

import base64
import glob
import io
import json
import os
import random
import re
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.core.skills.base import Skill


# ── Session-scoped canvas registry ──────────────────────────────────────────
# The Creator skills hand off intermediate canvas bytes via this in-memory
# store keyed by session_id. The base64 payloads never go through the LLM —
# the LLM only needs to know each skill succeeded and (optionally) hand the
# session_id forward. This keeps the agent's context under the 200k-token cap.

_canvas_store: dict[str, str] = {}


def _read_canvas(session_id: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    if session_id in _canvas_store:
        return _canvas_store[session_id]
    raise RuntimeError(
        f"No canvas in store for session {session_id} and none provided. "
        "Did generate_background run first?"
    )


def _write_canvas(session_id: str, b64: str) -> None:
    _canvas_store[session_id] = b64


def _normalize_to_b64(raw_or_b64: bytes) -> str:
    """
    Imagen's google-genai SDK returns image_bytes as ASCII bytes that ALREADY
    contain a base64-encoded PNG. Older docs (and library files we read from
    disk) hand us actual raw PNG bytes. Detect which one we have and return a
    plain base64 string either way.

    A real PNG starts with the 8-byte magic 89 50 4E 47 0D 0A 1A 0A.
    Base64-encoded PNG always starts with the ASCII letters "iVBORw0K".
    """
    if raw_or_b64.startswith(b"\x89PNG\r\n\x1a\n"):
        return base64.b64encode(raw_or_b64).decode("ascii")
    # JPEG signature
    if raw_or_b64[:3] == b"\xff\xd8\xff":
        return base64.b64encode(raw_or_b64).decode("ascii")
    # Otherwise assume it's already base64-encoded ASCII
    return raw_or_b64.decode("ascii")


def _project_root() -> Path:
    candidate = Path(__file__).resolve()
    for _ in range(6):
        candidate = candidate.parent
        if (candidate / "brand_config.json").exists():
            return candidate
    return Path(__file__).resolve().parent.parent.parent.parent


def _decode_b64_image(b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64)))


def _encode_image_b64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _parse_color(s: str) -> tuple:
    s = s.strip()
    if s.startswith("#"):
        s = s.lstrip("#")
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
    m = re.match(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)", s
    )
    if m:
        r, g, b = int(m[1]), int(m[2]), int(m[3])
        a = int(float(m[4]) * 255) if m[4] else 255
        return (r, g, b, a)
    return (255, 255, 255, 255)


# ── 1. GenerateBackground ────────────────────────────────────────────────────

class GenerateBackground(Skill):
    """Pick from library, or generate a new background via Gemini Imagen 4."""

    @property
    def name(self) -> str:
        return "generate_background"

    @property
    def description(self) -> str:
        return (
            "Generate or select a background image for the post. "
            "If force_generate is false and the library_path contains .png/.jpg "
            "files, picks one at random. Otherwise calls Gemini Imagen 4."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "mood_modifier": {"type": "string"},
                "theme": {"type": "string", "enum": ["dark", "light"]},
                "library_path": {"type": "string"},
                "force_generate": {"type": "boolean", "default": False},
            },
            "required": ["prompt", "mood_modifier", "theme", "library_path"],
        }

    def _execute(
        self,
        prompt: str,
        mood_modifier: str,
        theme: str,
        library_path: str,
        force_generate: bool = False,
    ) -> dict:
        root = _project_root()
        # Library path is relative to backend/
        abs_lib = root / "backend" / library_path

        if not force_generate and abs_lib.exists():
            files = (
                glob.glob(str(abs_lib / "*.png"))
                + glob.glob(str(abs_lib / "*.jpg"))
                + glob.glob(str(abs_lib / "*.jpeg"))
            )
            if files:
                picked = random.choice(files)
                with open(picked, "rb") as f:
                    img_bytes = f.read()
                b64 = _normalize_to_b64(img_bytes)
                _write_canvas(self._current_session_id, b64)
                return {
                    "stored": True,
                    "byte_count": len(img_bytes),
                    "source": "library",
                    "library_file": os.path.basename(picked),
                }

        # Build the full prompt. Imagen-4 no longer supports negative_prompt,
        # so avoidance terms are folded into the main prompt as "avoid ...".
        if theme == "dark":
            full_prompt = (
                f"{prompt}, {mood_modifier}, dark industrial environment, "
                "shallow depth of field with strongly blurred background elements, "
                "abstract industrial forms with 3D CGI render quality, subtle dark "
                "gradient centre zone, very dark overall atmosphere, ambient minimal "
                "industrial lighting, 8K resolution. "
                "Avoid: bright colors, high contrast, text, logos, faces, watermarks, "
                "cartoon, oversaturated, daylight exterior, harsh lighting, "
                "sharp foreground objects."
            )
        else:
            full_prompt = (
                f"{prompt}, {mood_modifier}, minimal abstract industrial environment, "
                "soft diffused light, clean airy atmosphere, light tones, "
                "out-of-focus depth of field, abstract 3D CGI industrial forms, "
                "bright open atmosphere. "
                "Avoid: dark backgrounds, heavy shadows, moody, night scene, "
                "dramatic lighting, text, logos, faces, cartoon."
            )

        # Call Gemini with retry
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
        model = os.getenv("IMAGEN_MODEL", "imagen-4.0-fast-generate-001")

        last_err: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = client.models.generate_images(
                    model=model,
                    prompt=full_prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="1:1",
                        safety_filter_level="block_low_and_above",
                    ),
                )
                image_bytes = response.generated_images[0].image.image_bytes
                # Imagen returns image_bytes as ASCII bytes containing the
                # already-base64-encoded PNG (starts with b"iVBORw0K..."). If we
                # re-encoded it we'd get garbage. Detect and normalize.
                b64 = _normalize_to_b64(image_bytes)
                _write_canvas(self._current_session_id, b64)
                return {
                    "stored": True,
                    "byte_count": len(image_bytes),
                    "source": "generated",
                    "library_file": None,
                }
            except Exception as exc:
                last_err = exc
                time.sleep(2.0 * (attempt + 1))

        # Final fallback: synthetic gradient background. Keeps the pipeline alive
        # so the Compositor can still produce something reviewable when Imagen is
        # unavailable; the error is recorded in the skill log.
        fallback = self._synthetic_background(theme)
        buf = io.BytesIO()
        fallback.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        _write_canvas(self._current_session_id, b64)
        return {
            "stored": True,
            "byte_count": len(buf.getvalue()),
            "source": "synthetic_fallback",
            "library_file": None,
            "imagen_error": str(last_err)[:300] if last_err else "unknown",
        }

    @staticmethod
    def _synthetic_background(theme: str) -> Image.Image:
        """Synthetic gradient — used only when both library and Imagen fail."""
        arr = np.zeros((1080, 1080, 3), dtype=np.float32)
        ys = np.linspace(0, 1, 1080)[:, np.newaxis]
        if theme == "dark":
            arr[:, :, 0] = 0.016 + ys * 0.04
            arr[:, :, 1] = 0.06 + ys * 0.08
            arr[:, :, 2] = 0.10 + ys * 0.10
        else:
            arr[:, :] = 0.94
            arr[:, :, 2] -= ys * 0.05
        return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "RGB")


# ── 2. ValidateBackgroundLuminance ───────────────────────────────────────────

class ValidateBackgroundLuminance(Skill):
    """Confirm a background's centre-zone luminance meets the theme threshold."""

    @property
    def name(self) -> str:
        return "validate_background_luminance"

    @property
    def description(self) -> str:
        return (
            "Validate that a background image's centre-zone luminance is within "
            "the threshold for the specified theme. Returns pass/fail with metrics."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "image_bytes_b64": {
                    "type": "string",
                    "description": "Optional. Omit to validate the session's current canvas.",
                },
                "theme": {"type": "string", "enum": ["dark", "light"]},
            },
            "required": ["theme"],
        }

    def _execute(self, theme: str, image_bytes_b64: str | None = None) -> dict:
        b64 = _read_canvas(self._current_session_id, image_bytes_b64)
        img = _decode_b64_image(b64).convert("RGB")
        arr = np.asarray(img, dtype=np.float32) / 255.0
        # Standard luminance: 0.299R + 0.587G + 0.114B
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

        h, w = lum.shape
        cy1, cy2 = int(h * 0.15), int(h * 0.85)
        cx1, cx2 = int(w * 0.15), int(w * 0.85)
        center = lum[cy1:cy2, cx1:cx2]

        full_luminance = float(np.mean(lum))
        center_luminance = float(np.mean(center))

        dark_max = float(os.getenv("DARK_BG_CENTER_MAX_LUMINANCE", "0.40"))
        light_min = float(os.getenv("LIGHT_BG_CENTER_MIN_LUMINANCE", "0.72"))

        if theme == "dark":
            threshold = dark_max
            passed = center_luminance <= dark_max
        else:
            threshold = light_min
            passed = center_luminance >= light_min

        return {
            "passed": passed,
            "full_luminance": round(full_luminance, 3),
            "center_luminance": round(center_luminance, 3),
            "threshold": threshold,
            "theme": theme,
        }


# ── 3. RenderGlassEffect ─────────────────────────────────────────────────────

class RenderGlassEffect(Skill):
    """Delegate to the configured GlassEffectRenderer (pillow or playwright)."""

    @property
    def name(self) -> str:
        return "render_glass_effect"

    @property
    def description(self) -> str:
        return (
            "Render the glass card effect onto the background image. "
            "Delegates to the GlassEffectRenderer configured in system_config.json."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "background_bytes_b64": {
                    "type": "string",
                    "description": "Optional. Omit to use the session's current canvas.",
                },
                "card_spec": {"type": "object"},
                "theme": {"type": "string", "enum": ["dark", "light"]},
            },
            "required": ["card_spec", "theme"],
        }

    def _execute(
        self,
        card_spec: dict,
        theme: str,
        background_bytes_b64: str | None = None,
    ) -> dict:
        cfg_path = _project_root() / "system_config.json"
        with open(cfg_path) as f:
            config = json.load(f)
        renderer_name = config.get("glass_renderer", "pillow")

        if renderer_name == "playwright":
            from backend.core.compositor.glass_renderer import PlaywrightGlassRenderer
            renderer = PlaywrightGlassRenderer()
        else:
            from backend.core.compositor.glass_renderer import PillowGlassRenderer
            renderer = PillowGlassRenderer()

        b64 = _read_canvas(self._current_session_id, background_bytes_b64)
        bg = _decode_b64_image(b64).convert("RGB")
        result = renderer.render(bg, card_spec, theme)
        result_b64 = _encode_image_b64(result, "PNG")
        _write_canvas(self._current_session_id, result_b64)
        return {
            "stored": True,
            "renderer_used": renderer_name,
            "theme": theme,
        }


# ── 4. RenderTextElement ─────────────────────────────────────────────────────

class RenderTextElement(Skill):
    """Render a single text element onto the canvas using Pillow."""

    def __init__(self, db_logger, agent_name: str):
        super().__init__(db_logger, agent_name)
        self.font_cache: dict[str, ImageFont.FreeTypeFont] = {}

    @property
    def name(self) -> str:
        return "render_text_element"

    @property
    def description(self) -> str:
        return (
            "Render a single text element onto a canvas at the specified position "
            "with exact font, size, and color from the element_spec. "
            "Include card_bounds in element_spec for relative_to glass_card positioning."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "canvas_bytes_b64": {
                    "type": "string",
                    "description": "Optional. Omit to use the session's current canvas.",
                },
                "element_spec": {"type": "object"},
            },
            "required": ["element_spec"],
        }

    def _load_font(self, font_path: str, size: int) -> ImageFont.FreeTypeFont:
        key = f"{font_path}_{size}"
        if key in self.font_cache:
            return self.font_cache[key]
        abs_path = _project_root() / "backend" / font_path
        if abs_path.exists():
            try:
                f = ImageFont.truetype(str(abs_path), size)
                self.font_cache[key] = f
                return f
            except Exception:
                pass
        try:
            f = ImageFont.load_default(size=size)
        except TypeError:
            f = ImageFont.load_default()
        self.font_cache[key] = f
        return f

    def _wrap(self, text: str, font, max_width: int) -> list[str]:
        dummy = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy)
        words = text.split()
        lines, cur = [], []
        for w in words:
            test = " ".join(cur + [w])
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width or not cur:
                cur.append(w)
            else:
                lines.append(" ".join(cur))
                cur = [w]
        if cur:
            lines.append(" ".join(cur))
        return lines or [text]

    def _execute(self, element_spec: dict, canvas_bytes_b64: str | None = None) -> dict:
        b64 = _read_canvas(self._current_session_id, canvas_bytes_b64)
        canvas = _decode_b64_image(b64).convert("RGBA")
        content = element_spec.get("content") or ""
        if not content:
            _write_canvas(self._current_session_id, _encode_image_b64(canvas, "PNG"))
            return {"stored": True, "skipped": "empty content"}

        font_path = element_spec.get("font") or ""
        font_size = element_spec.get("size") or 24
        font = self._load_font(font_path, font_size)

        # Text transform
        text = content
        if element_spec.get("text_transform") == "uppercase":
            text = text.upper()

        # Position
        pos = element_spec.get("position", {})
        rel = pos.get("relative_to")
        raw_x = pos.get("x", 0)
        raw_y = pos.get("y", 0)
        card = element_spec.get("card_bounds") or {}

        if rel == "glass_card":
            base_x, base_y = int(card.get("x", 0)), int(card.get("y", 0))
        else:
            base_x, base_y = 0, 0

        abs_x: Optional[int]
        if raw_x == "center":
            abs_x = None
        else:
            abs_x = base_x + int(raw_x)
        abs_y = base_y + int(raw_y)

        max_width = element_spec.get("max_width") or 900
        max_lines = element_spec.get("max_lines")
        lines = self._wrap(text, font, max_width)
        if max_lines:
            lines = lines[:max_lines]

        color = _parse_color(element_spec.get("color") or "#FFFFFF")
        letter_spacing = element_spec.get("letter_spacing") or 0

        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        line_height = int(font_size * (element_spec.get("line_height") or 1.25))
        cy = abs_y

        for line in lines:
            if abs_x is None:
                bb = draw.textbbox((0, 0), line, font=font)
                dx = (canvas.width - (bb[2] - bb[0])) // 2
            else:
                dx = abs_x

            if letter_spacing and letter_spacing != 0:
                cursor = dx
                for ch in line:
                    draw.text((cursor, cy), ch, font=font, fill=color)
                    bb = draw.textbbox((0, 0), ch, font=font)
                    cursor += (bb[2] - bb[0]) + int(letter_spacing)
            else:
                draw.text((dx, cy), line, font=font, fill=color)
            cy += line_height

        result = Image.alpha_composite(canvas, layer)
        result_b64 = _encode_image_b64(result, "PNG")
        _write_canvas(self._current_session_id, result_b64)
        return {"stored": True, "element_id": element_spec.get("id", "")}


# ── 5. PlaceLogo ─────────────────────────────────────────────────────────────

class PlaceLogo(Skill):
    """Render the glass logo pill with the brand logo centered inside it."""

    @property
    def name(self) -> str:
        return "place_logo"

    @property
    def description(self) -> str:
        return (
            "Render the glass logo pill at the top-center of the canvas with the "
            "brand logo inside it. Handles all three logo types identically — the "
            "Planner has already resolved the correct asset path."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "canvas_bytes_b64": {
                    "type": "string",
                    "description": "Optional. Omit to use the session's current canvas.",
                },
                "pill_spec": {"type": "object"},
            },
            "required": ["pill_spec"],
        }

    def _execute(self, pill_spec: dict, canvas_bytes_b64: str | None = None) -> dict:
        b64 = _read_canvas(self._current_session_id, canvas_bytes_b64)
        canvas = _decode_b64_image(b64).convert("RGBA")
        logo_spec = pill_spec.get("logo", {})
        logo_asset = logo_spec.get("asset", "")
        max_logo_w = logo_spec.get("max_width", 180)

        logo_img: Optional[Image.Image] = None
        if logo_asset:
            abs_logo = _project_root() / "backend" / logo_asset
            if abs_logo.exists():
                try:
                    logo_img = Image.open(str(abs_logo)).convert("RGBA")
                except Exception:
                    logo_img = None

        if logo_img is not None:
            scale = min(max_logo_w / logo_img.width, 1.0)
            logo_w = int(logo_img.width * scale)
            logo_h = int(logo_img.height * scale)
            logo_img = logo_img.resize((logo_w, logo_h), Image.LANCZOS)
        else:
            logo_w, logo_h = max_logo_w, 32

        padding = pill_spec.get("padding", {})
        h_pad = padding.get("horizontal", 24)
        pill_w = max(logo_w + h_pad * 2, pill_spec.get("min_width", 160))
        pill_h = pill_spec.get("height", 56)
        corner_r = pill_spec.get("corner_radius", 100)

        pill_x = (canvas.width - pill_w) // 2
        pill_y = pill_spec.get("position", {}).get("y", 72)

        glass = pill_spec.get("glass", {})
        fill = _parse_color(glass.get("fill", "rgba(0,0,0,0.60)"))
        border = _parse_color(glass.get("border", "rgba(255,255,255,0.20)"))

        pill_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(pill_layer)
        draw.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=corner_r,
            fill=fill,
            outline=border,
            width=1,
        )
        canvas = Image.alpha_composite(canvas, pill_layer)

        logo_x = pill_x + (pill_w - logo_w) // 2
        logo_y = pill_y + (pill_h - logo_h) // 2

        if logo_img is not None:
            canvas.alpha_composite(logo_img, dest=(logo_x, logo_y))
        else:
            fb_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            fb_draw = ImageDraw.Draw(fb_layer)
            try:
                fp = _project_root() / "backend" / "assets/fonts/Urbanist-Bold.ttf"
                fb_font = (
                    ImageFont.truetype(str(fp), 20)
                    if fp.exists()
                    else ImageFont.load_default()
                )
            except Exception:
                fb_font = ImageFont.load_default()
            fb_draw.text(
                (logo_x, logo_y),
                "NowPurchase",
                font=fb_font,
                fill=(255, 255, 255, 220),
            )
            canvas = Image.alpha_composite(canvas, fb_layer)

        result_b64 = _encode_image_b64(canvas, "PNG")
        _write_canvas(self._current_session_id, result_b64)
        return {"stored": True, "pill_w": pill_w, "pill_h": pill_h}


# ── 6. CompositeFinal ────────────────────────────────────────────────────────

class CompositeFinal(Skill):
    """Flatten the RGBA canvas to RGB PNG and save to the generated_posts dir."""

    @property
    def name(self) -> str:
        return "composite_final"

    @property
    def description(self) -> str:
        return (
            "Flatten the canvas to RGB and save the final 1080x1080 PNG to disk. "
            "Returns the saved file path and metadata."
        )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "canvas_bytes_b64": {
                    "type": "string",
                    "description": "Optional. Omit to use the session's current canvas.",
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional. Defaults to the current session.",
                },
                "attempt_number": {"type": "integer", "default": 1},
            },
            "required": [],
        }

    def _execute(
        self,
        canvas_bytes_b64: str | None = None,
        session_id: str | None = None,
        attempt_number: int = 1,
    ) -> dict:
        sid = session_id or self._current_session_id
        b64 = _read_canvas(sid, canvas_bytes_b64)
        canvas = _decode_b64_image(b64).convert("RGBA")
        rgb = Image.new("RGB", canvas.size, (255, 255, 255))
        rgb.paste(canvas, mask=canvas.split()[3])

        images_path = os.getenv(
            "IMAGES_PATH", str(_project_root() / "backend" / "storage_data" / "generated_posts")
        )
        out_dir = Path(images_path)
        out_dir.mkdir(parents=True, exist_ok=True)

        attempt_path = out_dir / f"{sid}_attempt{attempt_number}.png"
        latest_path = out_dir / f"{sid}_latest.png"
        rgb.save(str(attempt_path), format="PNG", optimize=False)
        rgb.save(str(latest_path), format="PNG", optimize=False)

        size_kb = attempt_path.stat().st_size // 1024
        return {
            "image_path": str(attempt_path),
            "latest_path": str(latest_path),
            "file_size_kb": size_kb,
            "dimensions": [1080, 1080],
        }
