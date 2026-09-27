"""Frames at fixed fractions of each selected video, one row per video."""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WORK = Path('F:/modal-gui/lab/2026-09-28-junyoung-intro')
ix = json.load(open(WORK / 'data' / 'media_index.json', encoding='utf-8'))
picks = [int(a) for a in sys.argv[2:]]
fr = [0.05, 0.2, 0.35, 0.5, 0.65, 0.8, 0.95]
cw, ch = 200, 260
font = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 18)
sheet = Image.new('RGB', (len(fr) * cw + 110, len(picks) * ch), (20, 20, 20))
d = ImageDraw.Draw(sheet)
for row, i in enumerate(picks):
    it = ix[i]
    src = WORK / 'sources' / it['file']
    dur = it['duration']
    d.text((6, row * ch + 10), f"#{i}\n{dur}s", font=font, fill=(200, 246, 64))
    for c, f in enumerate(fr):
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(dur * f), '-i', str(src), '-frames:v', '1',
                              '-vf', f'scale={cw - 6}:{ch - 6}:force_original_aspect_ratio=decrease', '-f', 'image2pipe',
                              '-vcodec', 'png', '-'], capture_output=True).stdout
        if raw:
            from io import BytesIO
            im = Image.open(BytesIO(raw))
            sheet.paste(im, (110 + c * cw, row * ch + 3))
        d.text((110 + c * cw + 4, row * ch + ch - 24), f'{dur * f:.1f}', font=font, fill='white')
sheet.save(sys.argv[1], quality=85)
