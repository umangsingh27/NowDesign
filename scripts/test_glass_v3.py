"""
Test script for Glass v3 — PlaywrightGlassRenderer.

Generates two test composites (dark + light mode) and saves them.
Uses a rich synthetic background (colourful gradient + geometric shapes)
so the refraction displacement is clearly visible.

Run: python scripts/test_glass_v3.py
"""

import sys
import io
import time
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()


def make_rich_background(theme: str) -> Image.Image:
    """
    Creates a visually rich 1080×1080 background with high-contrast
    edges near where the glass card will sit — makes refraction visible.
    Uses geometric shapes so the edge-bending is obvious.
    """
    img = Image.new("RGB", (1080, 1080))
    draw = ImageDraw.Draw(img)

    if theme == "dark":
        bg_array = np.zeros((1080, 1080, 3), dtype=np.uint8)
        for y in range(1080):
            t = y / 1080
            r = int(4 + t * 12)
            g = int(12 + t * 20)
            b = int(28 + t * 35)
            bg_array[y, :] = [r, g, b]
        img = Image.fromarray(bg_array)
        draw = ImageDraw.Draw(img)

        for i in range(8):
            y_pos = 200 + i * 100
            draw.line([(50, y_pos), (1030, y_pos)],
                      fill=(21, 121, 190), width=2)

        for i in range(5):
            x0 = 100 + i * 200
            draw.line([(x0, 100), (x0 + 300, 900)],
                      fill=(40, 160, 220), width=1)

        draw.ellipse([360, 250, 720, 550],
                     outline=(255, 180, 60), width=3)
        draw.ellipse([400, 290, 680, 510],
                     outline=(255, 140, 30), width=2)

        draw.rectangle([480, 0, 520, 1080], fill=(35, 100, 160))
        draw.rectangle([530, 0, 545, 1080], fill=(21, 60, 100))

    else:  # light
        bg_array = np.full((1080, 1080, 3), 240, dtype=np.uint8)
        for y in range(1080):
            t = y / 1080
            v = int(235 + t * 15)
            bg_array[y, :] = [v, v, v]
        img = Image.fromarray(bg_array)
        draw = ImageDraw.Draw(img)

        for i in range(6):
            y_pos = 250 + i * 100
            draw.line([(50, y_pos), (1030, y_pos)],
                      fill=(180, 180, 185), width=2)

        draw.ellipse([360, 250, 720, 550],
                     outline=(160, 160, 165), width=2)

        draw.rectangle([480, 0, 520, 1080], fill=(21, 121, 190))
        draw.rectangle([530, 0, 542, 1080], fill=(68, 148, 203))

    return img


def make_card_spec(theme: str) -> dict:
    return {
        "position": {"x": 108, "y": 300},
        "width": 864,
        "height": 480,
        "corner_radius": 24,
        "glass": {
            "fill": "rgba(0,0,0,0.62)" if theme == "dark" else "rgba(255,255,255,0.78)",
            "blur_radius": 16,
            "refraction_scale": 22,
        },
    }


def run_test():
    from backend.core.compositor.glass_renderer import PlaywrightGlassRenderer

    renderer = PlaywrightGlassRenderer()
    output_dir = Path("backend/storage_data/generated_posts")
    output_dir.mkdir(parents=True, exist_ok=True)

    for theme in ("dark", "light"):
        print(f"\n-- Glass v3 test: {theme} mode --")
        bg = make_rich_background(theme)
        card = make_card_spec(theme)

        t0 = time.monotonic()
        result = renderer.render(bg, card, theme)
        elapsed = time.monotonic() - t0

        out_path = output_dir / f"glass_v3_{theme}.png"
        result.convert("RGB").save(out_path, format="PNG")

        size_kb = out_path.stat().st_size // 1024
        print(f"  Saved: {out_path}")
        print(f"  Size:  {size_kb} KB")
        print(f"  Time:  {elapsed:.1f}s")
        print(f"  Mode:  {result.mode}  Size: {result.size}")

    print()
    print("=" * 60)
    print("VISUAL REVIEW -- open these files:")
    print("  Dark:  backend/storage_data/generated_posts/glass_v3_dark.png")
    print("  Light: backend/storage_data/generated_posts/glass_v3_light.png")
    print()
    print("Checklist vs Figma reference posts:")
    print("  [ ] Background stripes/circles visibly BEND at card edges")
    print("  [ ] Rainbow prismatic fringing (chromatic aberration) at corners")
    print("  [ ] Card center: background clearly visible + blurred through glass")
    print("  [ ] Card surface: gradient sheen (brighter top, darker bottom)")
    print("  [ ] Bright specular glow at top-centre of card")
    print("  [ ] Dark mode: deep glass, moody, industrial feel")
    print("  [ ] Light mode: clean glass, airy, sophisticated feel")
    print("  [ ] Overall: looks like real curved glass, NOT painted frosted box")
    print("=" * 60)


if __name__ == "__main__":
    run_test()
