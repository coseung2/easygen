"""Frames of one video at explicit seconds, labelled, to pick a sticker moment.

Usage: python peek_times.py <out.jpg> <media index> <t1> <t2> ...
"""
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WORK = Path('F:/modal-gui/lab/2026-09-28-junyoung-intro')
ix = json.load(open(WORK / 'data' / 'media_index.json', encoding='utf-8'))
out, idx, times = sys.argv[1], int(sys.argv[2]), [float(t) for t in sys.argv[3:]]
src = WORK / 'sources' / ix[idx]['file']
cw, ch = 300, 533
font = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 24)
sheet = Image.new('RGB', (cw * len(times), ch + 36), (20, 20, 20))
d = ImageDraw.Draw(sheet)
for k, t in enumerate(times):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', str(src), '-frames:v', '1',
                          '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, check=True).stdout
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    im.thumbnail((cw - 6, ch - 6))
    sheet.paste(im, (k * cw + 3, 3))
    d.text((k * cw + 8, ch + 4), f'#{idx} {t:.1f}s', font=font, fill=(200, 246, 64))
sheet.save(out, quality=88)
