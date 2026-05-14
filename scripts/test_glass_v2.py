import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from PIL import Image
from pathlib import Path
from backend.core.compositor.compositor import ImageCompositor
from backend.core.compositor.glass_renderer import PillowGlassRenderer
from backend.core.models import LayoutPlan
import copy

comp = ImageCompositor(glass_renderer=PillowGlassRenderer())
out = Path("backend/storage_data/generated_posts")
out.mkdir(parents=True, exist_ok=True)

base_plan = {
    'template': 'stat_forward', 'session_id': 'sess_glass_v2_test',
    'theme': 'dark', 'logo_type': 'nowpurchase',
    'canvas': {'width': 1080, 'height': 1080},
    'background': {
        'prompt': 'dark industrial foundry', 'mood_modifier': 'blue steel',
        'luminance_target': 0.35, 'library_path': 'assets/backgrounds/dark/'
    },
    'logo_pill': {
        'position': {'x': 'center', 'y': 72}, 'sizing': 'hug_content',
        'padding': {'horizontal': 24, 'vertical': 12},
        'min_width': 160, 'max_width': 320, 'height': 56, 'corner_radius': 100,
        'glass': {'fill': 'rgba(0,0,0,0.60)', 'border': 'rgba(255,255,255,0.20)'},
        'logo': {'asset': 'assets/logos/nowpurchase_white.png', 'max_width': 180, 'vertical_align': 'center'}
    },
    'glass_card': {
        'position': {'x': 108, 'y': 300}, 'width': 864, 'height': 520, 'corner_radius': 24,
        'glass': {
            'fill': 'rgba(0,0,0,0.62)', 'blur_radius': 16,
            'border_top': 'rgba(255,255,255,0.28)', 'border_rest': 'rgba(255,255,255,0.08)',
            'inner_highlight': 'rgba(255,255,255,0.18)', 'drop_shadow': '0 8px 32px rgba(0,0,0,0.45)'
        },
        'padding': {'top': 48, 'right': 48, 'bottom': 48, 'left': 48}
    },
    'elements': [
        {'id': 'stat', 'type': 'text', 'content': '23%',
         'font': 'assets/fonts/Urbanist-ExtraBold.ttf', 'size': 96, 'color': '#FFFFFF',
         'position': {'x': 48, 'y': 40, 'relative_to': 'glass_card'},
         'alignment': 'left', 'max_width': 768, 'z_order': 1},
        {'id': 'label', 'type': 'text', 'content': 'REDUCTION IN SCRAP RATE',
         'font': 'assets/fonts/Oxanium-Medium.ttf', 'size': 20,
         'color': 'rgba(255,255,255,0.60)',
         'position': {'x': 48, 'y': 175, 'relative_to': 'glass_card'},
         'alignment': 'left', 'max_width': 500, 'z_order': 2},
        {'id': 'headline', 'type': 'text',
         'content': "MetalCloud's AI charge mix optimizer. Live in 250+ foundries.",
         'font': 'assets/fonts/Urbanist-Bold.ttf', 'size': 50, 'color': '#FFFFFF',
         'position': {'x': 48, 'y': 224, 'relative_to': 'glass_card'},
         'alignment': 'left', 'max_width': 768, 'max_lines': 2,
         'line_height': 1.25, 'z_order': 3},
        {'id': 'body', 'type': 'text',
         'content': 'Real-time AI recommendations for every heat.',
         'font': 'assets/fonts/Oxanium-Regular.ttf', 'size': 22,
         'color': 'rgba(255,255,255,0.70)',
         'position': {'x': 48, 'y': 390, 'relative_to': 'glass_card'},
         'alignment': 'left', 'max_width': 768, 'max_lines': 2, 'z_order': 4}
    ],
    'divider': {
        'type': 'horizontal_line',
        'position': {'x': 48, 'y': 365, 'relative_to': 'glass_card'},
        'width': 768, 'color': 'rgba(21,121,190,0.55)', 'thickness': 1
    },
    'bottom_tag': {
        'type': 'text', 'content': 'MetalCloud by NowPurchase',
        'font': 'assets/fonts/Oxanium-Regular.ttf', 'size': 16,
        'color': 'rgba(255,255,255,0.40)',
        'position': {'x': 'center', 'y': 1042}
    }
}

# ── DARK mode composite ───────────────────────────────────────────────────
dark_bg = Image.open(str(out / 'test_bg_dark.png'))
dark_plan = LayoutPlan.from_dict(base_plan)
dark_png = comp.composite(dark_plan, dark_bg)
dark_path = out / 'glass_v2_dark.png'
dark_path.write_bytes(dark_png)
print(f'Dark: {dark_path} ({len(dark_png):,} bytes)')

# ── LIGHT mode composite ──────────────────────────────────────────────────
light_plan_dict = copy.deepcopy(base_plan)
light_plan_dict['theme'] = 'light'
light_plan_dict['glass_card']['glass']['fill'] = 'rgba(255,255,255,0.78)'
light_plan_dict['glass_card']['glass']['border_top'] = 'rgba(0,0,0,0.12)'
light_plan_dict['glass_card']['glass']['border_rest'] = 'rgba(0,0,0,0.05)'
light_plan_dict['logo_pill']['glass']['fill'] = 'rgba(255,255,255,0.75)'
light_plan_dict['logo_pill']['glass']['border'] = 'rgba(0,0,0,0.10)'
light_plan_dict['logo_pill']['logo']['asset'] = 'assets/logos/nowpurchase_white.png'
for el in light_plan_dict['elements']:
    if el.get('color') == '#FFFFFF': el['color'] = '#0D0D0D'
    elif '255,255,255,0.60' in el.get('color',''): el['color'] = 'rgba(0,0,0,0.55)'
    elif '255,255,255,0.70' in el.get('color',''): el['color'] = 'rgba(0,0,0,0.65)'
light_plan_dict['bottom_tag']['color'] = 'rgba(0,0,0,0.40)'

light_bg = Image.open(str(out / 'test_bg_light.png'))
light_plan = LayoutPlan.from_dict(light_plan_dict)
light_png = comp.composite(light_plan, light_bg)
light_path = out / 'glass_v2_light.png'
light_path.write_bytes(light_png)
print(f'Light: {light_path} ({len(light_png):,} bytes)')

import io
from PIL import Image as PILImage
for label, data in [('dark', dark_png), ('light', light_png)]:
    img = PILImage.open(io.BytesIO(data))
    assert img.size == (1080, 1080) and img.mode == 'RGB'
    print(f'{label}: {img.size} {img.mode} OK')

print()
print('============================================================')
print('VISUAL CALIBRATION -- open these files:')
print('  Dark:  backend/storage_data/generated_posts/glass_v2_dark.png')
print('  Light: backend/storage_data/generated_posts/glass_v2_light.png')
print()
print('Checklist vs Figma reference posts (social_1.png through social_9.png):')
print('  [ ] Background visible and blurred through card')
print('  [ ] Card has gradient surface (lighter top, darker bottom)')
print('  [ ] Top edge has a clear bright highlight line')
print('  [ ] Surface specular glow visible in upper portion of card')
print('  [ ] Dark/light modes look clearly different')
print('  [ ] Text is legible with good hierarchy')
print('  [ ] Overall mood: premium glass, not painted box')
print('============================================================')
