import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
import numpy as np
from PIL import Image
from pathlib import Path

def make_dark_bg(size=1080):
    arr = np.zeros((size, size, 3), dtype=np.float32)
    y = np.linspace(0, 1, size)[:, np.newaxis]
    x = np.linspace(0, 1, size)[np.newaxis, :]

    # Base: dark navy gradient
    arr[:, :, 0] = 0.008 + y * 0.012
    arr[:, :, 1] = 0.065 + y * 0.050
    arr[:, :, 2] = 0.110 + y * 0.080

    # Foundry glow — warm amber at bottom centre
    glow_y = np.maximum(0, 1 - (1 - y) * 2.5)
    glow_x = np.maximum(0, 1 - np.abs(x - 0.5) * 3.5)
    glow = glow_y * glow_x
    arr[:, :, 0] += glow * 0.55
    arr[:, :, 1] += glow * 0.18
    arr[:, :, 2] += glow * 0.02

    # Blue arc light — top left
    arc_x = np.maximum(0, 0.5 - np.abs(x - 0.15) * 2.5)
    arc_y = np.maximum(0, 0.5 - y * 1.5)
    arc = arc_x * arc_y
    arr[:, :, 0] += arc * 0.05
    arr[:, :, 1] += arc * 0.12
    arr[:, :, 2] += arc * 0.45

    rng = np.random.default_rng(42)
    for _ in range(18):
        sy = rng.integers(600, 900)
        sx = rng.integers(80, 1000)
        ssize = rng.integers(15, 55)
        intensity = rng.uniform(0.3, 0.85)
        yc = np.linspace(0, 1, ssize)[:, np.newaxis]
        xc = np.linspace(0, 1, ssize)[np.newaxis, :]
        spot = np.maximum(0, 1 - ((xc-0.5)**2 + (yc-0.5)**2)**0.5 * 2.8)
        ys1, ye1 = max(0, sy-ssize//2), min(size, sy+ssize//2)
        xs1, xe1 = max(0, sx-ssize//2), min(size, sx+ssize//2)
        actual_h, actual_w = ye1-ys1, xe1-xs1
        if actual_h > 0 and actual_w > 0:
            spot_crop = spot[:actual_h, :actual_w] * intensity
            arr[ys1:ye1, xs1:xe1, 0] += spot_crop * 0.9
            arr[ys1:ye1, xs1:xe1, 1] += spot_crop * 0.4

    # Diagonal light shafts (factory beams)
    for i in range(3):
        shaft_x = 0.2 + i * 0.3
        dist = np.abs(x - shaft_x - y * 0.15)
        shaft = np.maximum(0, 0.015 - dist) * 60
        arr[:, :, 0] += shaft * 0.4
        arr[:, :, 1] += shaft * 0.3
        arr[:, :, 2] += shaft * 0.15

    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), 'RGB')

def make_light_bg(size=1080):
    arr = np.ones((size, size, 3), dtype=np.float32) * 0.96
    y = np.linspace(0, 1, size)[:, np.newaxis]
    x = np.linspace(0, 1, size)[np.newaxis, :]

    arr[:, :, 0] -= y * 0.03
    arr[:, :, 1] -= y * 0.02

    sky = np.maximum(0, (0.5 - y) * 1.2)
    arr[:, :, 2] += sky * 0.04

    for i in range(4):
        sx = 0.1 + i * 0.25
        shape = np.maximum(0, 0.3 - (np.abs(x - sx) * 1.8 + np.abs(y - 0.6) * 2.0))
        arr[:, :, 0] -= shape * 0.06
        arr[:, :, 1] -= shape * 0.05
        arr[:, :, 2] -= shape * 0.04

    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), 'RGB')

if __name__ == "__main__":
    out = Path("backend/storage_data/generated_posts")
    out.mkdir(parents=True, exist_ok=True)
    dark = make_dark_bg()
    dark.save(str(out / "test_bg_dark.png"))
    print(f"Dark background saved: {out / 'test_bg_dark.png'}")
    light = make_light_bg()
    light.save(str(out / "test_bg_light.png"))
    print(f"Light background saved: {out / 'test_bg_light.png'}")
