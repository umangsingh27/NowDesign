"""Session 6 full compositor end-to-end test (5d)."""
import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
import io
import copy
from pathlib import Path
import numpy as np
from PIL import Image
from backend.core.compositor.compositor import ImageCompositor
from backend.core.compositor.glass_renderer import PillowGlassRenderer
from backend.core.models import LayoutPlan


comp = ImageCompositor(glass_renderer=PillowGlassRenderer())

# Create a synthetic dark background (navy gradient with warm glow)
h, w = 1080, 1080
arr = np.zeros((h, w, 3), dtype=np.float32)
arr[:, :] = [0.016, 0.094, 0.149]  # #041826 base

# Warm glow at bottom-centre (simulates foundry furnace heat)
y_coords = np.linspace(0, 1, h)[:, np.newaxis]
x_norm = np.linspace(-1, 1, w)[np.newaxis, :]
glow = np.maximum(0, (1 - y_coords * 1.8)) * np.maximum(0, 1 - np.abs(x_norm) * 2.5)
arr[:, :, 0] += glow * 0.25
arr[:, :, 1] += glow * 0.05
# Blue highlight top-left
blue_glow = (
    np.maximum(0, 0.3 - y_coords * 0.6)
    * np.maximum(0, 0.4 - np.maximum(0, x_norm) * 0.8)
)
arr[:, :, 2] += blue_glow * 0.3

bg = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), 'RGB')

plan_dict = {
    'template': 'stat_forward',
    'session_id': 'sess_compositor_test',
    'theme': 'dark',
    'logo_type': 'nowpurchase',
    'canvas': {'width': 1080, 'height': 1080},
    'background': {
        'prompt': 'dark industrial foundry',
        'mood_modifier': 'blue steel cool tones',
        'luminance_target': 0.35,
        'library_path': 'assets/backgrounds/dark/',
    },
    'logo_pill': {
        'position': {'x': 'center', 'y': 72},
        'sizing': 'hug_content',
        'padding': {'horizontal': 24, 'vertical': 12},
        'min_width': 160, 'max_width': 320,
        'height': 56, 'corner_radius': 100,
        'glass': {'fill': 'rgba(0,0,0,0.60)', 'border': 'rgba(255,255,255,0.20)'},
        'logo': {
            'asset': 'assets/logos/nowpurchase_white.png',
            'max_width': 180,
            'vertical_align': 'center',
        },
    },
    'glass_card': {
        'position': {'x': 108, 'y': 300},
        'width': 864, 'height': 520, 'corner_radius': 24,
        'glass': {
            'fill': 'rgba(0,0,0,0.62)',
            'border_top': 'rgba(255,255,255,0.28)',
            'border_rest': 'rgba(255,255,255,0.08)',
            'blur_radius': 16,
            'inner_highlight': 'rgba(255,255,255,0.18)',
            'drop_shadow': '0 8px 32px rgba(0,0,0,0.45)',
        },
        'padding': {'top': 48, 'right': 48, 'bottom': 48, 'left': 48},
    },
    'elements': [
        {
            'id': 'stat', 'type': 'text', 'content': '23%',
            'font': 'assets/fonts/Urbanist-ExtraBold.ttf', 'size': 96,
            'color': '#FFFFFF',
            'position': {'x': 48, 'y': 40, 'relative_to': 'glass_card'},
            'alignment': 'left', 'max_width': 768,
            'letter_spacing': -2, 'z_order': 1,
        },
        {
            'id': 'stat_label', 'type': 'text', 'content': 'REDUCTION IN SCRAP RATE',
            'font': 'assets/fonts/Oxanium-Medium.ttf', 'size': 20,
            'color': 'rgba(255,255,255,0.60)',
            'position': {'x': 48, 'y': 170, 'relative_to': 'glass_card'},
            'alignment': 'left', 'max_width': 500, 'z_order': 2,
        },
        {
            'id': 'headline', 'type': 'text',
            'content': "MetalCloud's AI charge mix optimizer. Live in 250+ foundries.",
            'font': 'assets/fonts/Urbanist-Bold.ttf', 'size': 50,
            'color': '#FFFFFF',
            'position': {'x': 48, 'y': 220, 'relative_to': 'glass_card'},
            'alignment': 'left', 'max_width': 768, 'max_lines': 2,
            'line_height': 1.25, 'z_order': 3,
        },
        {
            'id': 'body', 'type': 'text',
            'content': 'Real-time AI recommendations for every heat. Reducing costs and eliminating guesswork.',
            'font': 'assets/fonts/Oxanium-Regular.ttf', 'size': 22,
            'color': 'rgba(255,255,255,0.70)',
            'position': {'x': 48, 'y': 385, 'relative_to': 'glass_card'},
            'alignment': 'left', 'max_width': 768, 'max_lines': 2,
            'line_height': 1.5, 'z_order': 4,
        },
    ],
    'divider': {
        'type': 'horizontal_line',
        'position': {'x': 48, 'y': 360, 'relative_to': 'glass_card'},
        'width': 768, 'color': 'rgba(21,121,190,0.50)', 'thickness': 1,
    },
    'bottom_tag': {
        'type': 'text', 'content': 'MetalCloud by NowPurchase',
        'font': 'assets/fonts/Oxanium-Regular.ttf', 'size': 16,
        'color': 'rgba(255,255,255,0.40)',
        'position': {'x': 'center', 'y': 1040},
    },
}

plan = LayoutPlan.from_dict(plan_dict)
print(f'LayoutPlan validated: theme={plan.theme}, logo_type={plan.logo_type}')

png_bytes = comp.composite(plan, bg)
assert len(png_bytes) > 10_000, f'Output too small: {len(png_bytes)} bytes'

out_dir = Path('backend/storage_data/generated_posts')
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / 'test_composite_dark.png'
with open(out_path, 'wb') as f:
    f.write(png_bytes)

print(f'Dark composite saved: {out_path} ({len(png_bytes):,} bytes)')

check = Image.open(io.BytesIO(png_bytes))
assert check.size == (1080, 1080), f'Expected 1080x1080, got {check.size}'
assert check.mode == 'RGB', f'Expected RGB, got {check.mode}'
print(f'Output verified: {check.size}, mode={check.mode}')

# Light mode composite
bg_light_arr = np.zeros((1080, 1080, 3), dtype=np.float32)
bg_light_arr[:, :] = [0.95, 0.95, 0.94]
y_l = np.linspace(0, 1, 1080)[:, np.newaxis]
bg_light_arr[:, :, 0] -= y_l * 0.05
bg_light_arr[:, :, 1] -= y_l * 0.04
bg_light = Image.fromarray((np.clip(bg_light_arr, 0, 1) * 255).astype(np.uint8), 'RGB')

light_plan_dict = copy.deepcopy(plan_dict)
light_plan_dict['theme'] = 'light'
light_plan_dict['glass_card']['glass']['fill'] = 'rgba(255,255,255,0.78)'
light_plan_dict['glass_card']['glass']['border_top'] = 'rgba(0,0,0,0.12)'
light_plan_dict['glass_card']['glass']['border_rest'] = 'rgba(0,0,0,0.05)'
light_plan_dict['glass_card']['glass']['inner_highlight'] = 'rgba(255,255,255,0.90)'
light_plan_dict['logo_pill']['glass']['fill'] = 'rgba(255,255,255,0.75)'
light_plan_dict['logo_pill']['glass']['border'] = 'rgba(0,0,0,0.10)'
light_plan_dict['logo_pill']['logo']['asset'] = 'assets/logos/nowpurchase_dark.png'
for el in light_plan_dict['elements']:
    if el['color'] == '#FFFFFF':
        el['color'] = '#0D0D0D'
    elif '255,255,255,0.60' in el['color']:
        el['color'] = 'rgba(0,0,0,0.55)'
    elif '255,255,255,0.70' in el['color']:
        el['color'] = 'rgba(0,0,0,0.65)'
light_plan_dict['bottom_tag']['color'] = 'rgba(0,0,0,0.40)'

light_plan = LayoutPlan.from_dict(light_plan_dict)
light_png = comp.composite(light_plan, bg_light)
light_path = out_dir / 'test_composite_light.png'
with open(light_path, 'wb') as f:
    f.write(light_png)
print(f'Light composite saved: {light_path} ({len(light_png):,} bytes)')

print()
print('Full compositor end-to-end: ALL PASSED')
print()
print('=' * 60)
print('VISUAL REVIEW REQUIRED')
print('=' * 60)
print('Open these files and compare to Figma originals:')
print(f'  Dark:  {out_path.resolve()}')
print(f'  Light: {light_path.resolve()}')
print()
print('Calibration checklist:')
print('  [ ] Glass card opacity -- too light or too dark?')
print('  [ ] Glass card blur -- visible frosted effect?')
print('  [ ] Top border highlight -- visible bright line at card top?')
print('  [ ] Logo pill -- correct position and size?')
print('  [ ] Text hierarchy -- stat > headline > body, clear reading order?')
print('  [ ] Blue divider line -- visible at 50% opacity?')
print('  [ ] Bottom tag -- legible at 40% opacity?')
print('  [ ] Dark/light modes feel distinctly different?')
print('=' * 60)
