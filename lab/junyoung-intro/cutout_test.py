"""Cutout quality test on candidate stills with two rembg models; writes a comparison sheet."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from rembg import new_session, remove

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from lab_paths import font_path, lab_path

WORK = lab_path('2026-09-28-junyoung-intro')
index = json.load(open(WORK / 'data' / 'media_index.json', encoding='utf-8'))
picks = [int(a) for a in sys.argv[1:]]
models = ['isnet-general-use', 'u2net_human_seg']
sessions = {m: new_session(m) for m in models}
font = ImageFont.truetype(str(font_path('malgun.ttf', 'Malgun.ttf')), 18)
cell = 300
sheet = Image.new('RGB', ((len(models) + 1) * cell, len(picks) * cell), (60, 60, 60))
for row, i in enumerate(picks):
    it = index[i]
    im = ImageOps.exif_transpose(Image.open(WORK / 'sources' / it['file'])).convert('RGB')
    im.thumbnail((900, 900))
    small = im.copy()
    small.thumbnail((cell, cell))
    sheet.paste(small, (0, row * cell))
    ImageDraw.Draw(sheet).text((6, row * cell + 6), f'#{i}', font=font, fill='yellow')
    for col, m in enumerate(models, 1):
        cut = remove(im, session=sessions[m])
        bg = Image.new('RGBA', cut.size, (200, 246, 64, 255))
        bg.alpha_composite(cut)
        bg.thumbnail((cell, cell))
        sheet.paste(bg.convert('RGB'), (col * cell, row * cell))
    print('done', i, flush=True)
ImageDraw.Draw(sheet).text((cell + 6, 6), models[0], font=font, fill='black')
ImageDraw.Draw(sheet).text((2 * cell + 6, 6), models[1], font=font, fill='black')
sheet.save(WORK / '_cutout_test.jpg', quality=88)
