"""
Background image generator for NowPurchase AI Design Studio.

Two classes:
  BackgroundGenerator       — generates backgrounds via Gemini Imagen 4 API
  BackgroundLibrarySelector — picks from pre-approved backgrounds on disk

Strategy (applied by BackgroundGenerator.generate):
  1. If library contains images AND force_generate=False -> pick randomly (saves API cost)
  2. If library is empty OR force_generate=True -> call Gemini Imagen API
  3. Validate luminance of result — retry up to 3 times if it fails threshold
  4. Return PIL Image (1080x1080, RGB)

Theme determines:
  - Which prompt template is used (dark industrial vs light minimal)
  - Which library folder is checked (dark/ vs light/)
  - Which luminance threshold to apply (<= 0.40 for dark, >= 0.72 for light)
"""

import asyncio
import io
import json
import os
import random
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
from dotenv import load_dotenv

load_dotenv()


def _load_brand_config() -> dict:
    """Load brand_config.json once and cache it on the function object."""
    if not hasattr(_load_brand_config, "_cache"):
        # Walk up from this file to find brand_config.json at project root
        candidate = Path(__file__).resolve()
        for _ in range(6):
            candidate = candidate.parent
            config_path = candidate / "brand_config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    _load_brand_config._cache = json.load(f)
                break
        else:
            raise FileNotFoundError(
                "brand_config.json not found in any ancestor directory of imagen.py"
            )
    return _load_brand_config._cache


class BackgroundLibrarySelector:
    """
    Manages the pre-approved background image libraries.
    Checks assets/backgrounds/dark/ or assets/backgrounds/light/
    depending on the theme passed via library_path.
    """

    VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    @staticmethod
    def _resolve_library_path(library_path: str) -> Path:
        """Resolve library_path (relative to backend/) to an absolute path."""
        candidate = Path(__file__).resolve()
        for _ in range(6):
            candidate = candidate.parent
            if (candidate / "brand_config.json").exists():
                return candidate / "backend" / library_path
        # Fallback: assume we're one level below project root
        return Path(__file__).resolve().parent.parent.parent / "backend" / library_path

    @classmethod
    def count(cls, library_path: str) -> int:
        """Return the number of valid image files in the library folder."""
        folder = cls._resolve_library_path(library_path)
        if not folder.exists():
            return 0
        return sum(
            1 for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in cls.VALID_EXTENSIONS
        )

    @classmethod
    def pick(cls, library_path: str) -> Optional[Image.Image]:
        """
        Randomly select one image from the library and return it as a PIL Image.
        Returns None if the library is empty or does not exist.
        """
        folder = cls._resolve_library_path(library_path)
        if not folder.exists():
            return None
        candidates = [
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in cls.VALID_EXTENSIONS
        ]
        if not candidates:
            return None
        chosen = random.choice(candidates)
        return Image.open(str(chosen)).convert("RGB")


class BackgroundGenerator:
    """
    Generates 1080x1080 background images for social post composition.

    Uses Gemini Imagen 4 API (google-genai SDK).
    Reads ALL prompt templates and luminance thresholds from brand_config.json.
    Never hardcodes prompts or thresholds — always reads from config.
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-init the Gemini client — raises if API key is not set."""
        if self._client is None:
            from google import genai
            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key or api_key == "AIzaSy-your-key-here":
                raise EnvironmentError(
                    "GEMINI_API_KEY not set. Add your real key to .env before generating backgrounds."
                )
            self._client = genai.Client(api_key=api_key)
        return self._client

    def _build_prompt(self, base_prompt: str, mood_modifier: str, theme: str) -> tuple[str, str]:
        """
        Construct the final Imagen prompt + negative from brand_config values.

        Reads prompt_base and negative verbatim from brand_config.themes[theme].background.
        Never called with hardcoded strings — all template text lives in brand_config.

        Returns: (positive_prompt, negative_prompt)
        """
        config = _load_brand_config()
        bg_config = config["themes"][theme]["background"]

        prompt_base: str = bg_config["prompt_base"]
        negative: str = bg_config["negative"]

        # Combine: caller's brief content + mood + brand_config's detailed base
        parts = [p for p in [base_prompt, mood_modifier, prompt_base] if p]
        positive = ", ".join(parts)

        return positive, negative

    def validate_luminance(self, image: Image.Image, theme: str) -> dict:
        """
        Compute average luminance of the full image and the centre 70% zone.

        Dark mode:  passes if center_luminance <= DARK_BG_CENTER_MAX_LUMINANCE (default 0.40)
        Light mode: passes if center_luminance >= LIGHT_BG_CENTER_MIN_LUMINANCE (default 0.72)

        Thresholds read from env vars (set in .env from brand_config values).

        Returns:
          passed:           bool
          full_luminance:   float (BT.601 average over whole image)
          center_luminance: float (BT.601 average over centre 70% zone)
          threshold:        float (the value being compared against)
          theme:            str
        """
        arr = np.array(image.convert("RGB")).astype(np.float32) / 255.0
        # BT.601 perceptual luminance coefficients
        lum = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]

        h, w = lum.shape
        # Centre 70% zone: crop 15% from each edge
        y_margin = int(h * 0.15)
        x_margin = int(w * 0.15)
        centre_zone = lum[y_margin: h - y_margin, x_margin: w - x_margin]

        full_lum = float(np.mean(lum))
        centre_lum = float(np.mean(centre_zone))

        if theme == "dark":
            # Read from brand_config centre_luminance_max, overridable by env var
            config_threshold = _load_brand_config()["themes"]["dark"]["background"]["center_luminance_max"]
            threshold = float(os.getenv("DARK_BG_CENTER_MAX_LUMINANCE", str(config_threshold)))
            passed = centre_lum <= threshold
        else:
            config_threshold = _load_brand_config()["themes"]["light"]["background"]["center_luminance_min"]
            threshold = float(os.getenv("LIGHT_BG_CENTER_MIN_LUMINANCE", str(config_threshold)))
            passed = centre_lum >= threshold

        return {
            "passed": passed,
            "full_luminance": round(full_lum, 4),
            "center_luminance": round(centre_lum, 4),
            "threshold": threshold,
            "theme": theme
        }

    async def generate(
        self,
        prompt: str,
        mood_modifier: str,
        theme: str,
        library_path: str,
        force_generate: bool = False
    ) -> Image.Image:
        """
        Main entry point. Returns a 1080x1080 PIL Image (RGB).

        Steps:
          1. Check pre-approved library (unless force_generate=True)
          2. Call Gemini Imagen API
          3. Validate luminance — retry up to 3 times with exponential backoff
        """
        # Step 1: Library-first strategy
        if not force_generate:
            lib_count = BackgroundLibrarySelector.count(library_path)
            if lib_count > 0:
                image = BackgroundLibrarySelector.pick(library_path)
                if image is not None:
                    return self._resize_to_square(image, 1080)

        # Step 2 + 3: Generate via API with luminance-gated retry
        positive_prompt, negative_prompt = self._build_prompt(prompt, mood_modifier, theme)
        model = os.getenv("IMAGEN_MODEL", "imagen-4.0-fast-generate-001")

        max_attempts = 3
        last_error = "Unknown error"

        for attempt in range(max_attempts):
            try:
                image = await self._call_imagen_api(
                    model=model,
                    prompt=positive_prompt,
                    negative_prompt=negative_prompt
                )
                image = self._resize_to_square(image, 1080)

                validation = self.validate_luminance(image, theme)
                if validation["passed"]:
                    return image

                last_error = (
                    f"Luminance check failed (attempt {attempt + 1}/{max_attempts}): "
                    f"centre={validation['center_luminance']:.3f}, "
                    f"threshold={'<=' if theme == 'dark' else '>='}{validation['threshold']}"
                )

            except Exception as exc:
                last_error = f"API error on attempt {attempt + 1}: {exc}"

            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)  # 1s then 2s backoff

        raise RuntimeError(
            f"Background generation failed after {max_attempts} attempts. Last: {last_error}"
        )

    async def _call_imagen_api(
        self,
        model: str,
        prompt: str,
        negative_prompt: str
    ) -> Image.Image:
        """
        Call Gemini Imagen API. Returns PIL Image.
        Runs the synchronous SDK call in a thread-pool executor to stay async-safe.
        """
        from google.genai import types

        client = self._get_client()

        def _sync_call() -> bytes:
            config_kwargs: dict = {
                "number_of_images": 1,
                "aspect_ratio": "1:1",
                "output_mime_type": "image/png",
            }
            if negative_prompt:
                config_kwargs["negative_prompt"] = negative_prompt

            response = client.models.generate_images(
                model=model,
                prompt=prompt,
                config=types.GenerateImagesConfig(**config_kwargs)
            )
            return response.generated_images[0].image.image_bytes

        loop = asyncio.get_event_loop()
        image_bytes: bytes = await loop.run_in_executor(None, _sync_call)
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")

    @staticmethod
    def _resize_to_square(image: Image.Image, size: int) -> Image.Image:
        """
        Centre-crop and resize any input image to size x size pixels.
        Preserves aspect ratio by scaling the shorter dimension to fill size,
        then cropping the longer dimension symmetrically.
        """
        w, h = image.size
        scale = max(size / w, size / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = image.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - size) // 2
        top = (new_h - size) // 2
        return resized.crop((left, top, left + size, top + size))
