"""Cache BRIA RMBG 2.0 stickers and key frames for the launch video (runs once; lab venv).

Writes stickers/<idx>.png (RGBA, white die-cut + shadow), frames/<name>.png, and a
labelled review sheet with a 100px grid so feature callouts can be placed precisely.
"""
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from rembg import new_session, remove

sys.path.insert(0, str(Path(__file__).parent))
from sticker import clean_alpha, make_sticker  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from lab_paths import font_path, lab_path

WORK = lab_path('2026-09-28-junyoung-intro')
ST = WORK / 'stickers'
FR = WORK / 'frames'
ST.mkdir(exist_ok=True)
FR.mkdir(exist_ok=True)
ix = json.load(open(WORK / 'data' / 'media_index.json', encoding='utf-8'))
font = ImageFont.truetype(str(font_path('malgunbd.ttf', 'malgun.ttf')), 26)

PHOTOS = [int(a) for a in sys.argv[1:]] or [165, 175, 183, 144, 159, 118, 102, 1, 99, 147, 158, 184]
# (name, media index, second): full frames used as plates
FRAMES = [('eyes', 171, 10.8), ('eyes2', 171, 20.0), ('fart', 167, 10.0)]

session = new_session('bria-rmbg')


def grab(idx, t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', str(WORK / 'sources' / ix[idx]['file']),
                          '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True,
                         check=True).stdout
    return Image.open(io.BytesIO(raw)).convert('RGB')


for idx in PHOTOS:
    out = ST / f'{idx}.png'
    if out.exists():
        continue
    im = ImageOps.exif_transpose(Image.open(WORK / 'sources' / ix[idx]['file'])).convert('RGB')
    im.thumbnail((1500, 1500))
    mask = clean_alpha(remove(im, session=session, only_mask=True))
    make_sticker(im, mask, stroke=28).save(out)
    print('sticker', idx, flush=True)

for name, idx, t in FRAMES:
    out = FR / f'{name}.png'
    if not out.exists():
        grab(idx, t).save(out)
        print('frame', name, flush=True)

# review sheet: stickers on a grid, frames on a grid
items = [(f'#{i}', Image.open(ST / f'{i}.png')) for i in PHOTOS] + \
        [(n, Image.open(FR / f'{n}.png').convert('RGBA')) for n, _, _ in FRAMES]
cell = 520
cols = 5
sheet = Image.new('RGB', (cols * cell, ((len(items) + cols - 1) // cols) * cell), (150, 104, 255))
d = ImageDraw.Draw(sheet)
for k, (label, im) in enumerate(items):
    im = im.copy()
    scale = min((cell - 20) / im.width, (cell - 60) / im.height)
    im = im.resize((int(im.width * scale), int(im.height * scale)))
    x, y = (k % cols) * cell + 10, (k // cols) * cell + 50
    sheet.paste(im, (x, y), im)
    for g in range(0, 2000, 100):  # grid in source-pixel units
        gx, gy = x + g * scale, y + g * scale
        if g * scale < im.width:
            d.line((gx, y, gx, y + im.height), fill=(255, 255, 0), width=1)
        if g * scale < im.height:
            d.line((x, gy, x + im.width, gy), fill=(255, 255, 0), width=1)
    d.text((x, y - 42), f'{label}  {im.width / scale:.0f}x{im.height / scale:.0f}', font=font, fill='white')
sheet.save(WORK / '_launch_review.jpg', quality=88)
print('review ok')
