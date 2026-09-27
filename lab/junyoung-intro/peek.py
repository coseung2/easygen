"""Show selected thumbnails large with index labels."""
import sys
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont

WORK = Path('F:/modal-gui/lab/2026-09-28-junyoung-intro')
ix = json.load(open(WORK / 'data' / 'media_index.json', encoding='utf-8'))
picks = [int(a) for a in sys.argv[2:]]
font = ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf', 22)
cols, cw, ch = 6, 330, 360
sheet = Image.new('RGB', (cols * cw, ((len(picks) + cols - 1) // cols) * ch), (20, 20, 20))
d = ImageDraw.Draw(sheet)
for k, i in enumerate(picks):
    t = WORK / 'thumbs' / (Path(ix[i]['file']).stem + '.jpg')
    im = Image.open(t)
    im.thumbnail((cw - 10, ch - 40))
    x, y = (k % cols) * cw, (k // cols) * ch
    sheet.paste(im, (x + 5, y + 5))
    d.text((x + 8, y + ch - 32), f"#{i} {ix[i]['date'][5:]} {ix[i]['type'][0]}{ix[i].get('duration') or ''}",
           font=font, fill=(200, 246, 64))
sheet.save(sys.argv[1], quality=88)
