"""Find frames where the main subject is large but its head does not touch the top edge.

Samples the Ronaldo-only edit every 0.5 s at 480 px, runs the fast u2netp mask, and scores:
  top_gap   : empty rows above the subject (0 = head cut off)
  height    : subject height / frame height (bigger = closer shot)
Writes review/head_scan.json and a sheet of the best candidates.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from rembg import new_session, remove
from scipy import ndimage

WORK = Path(__file__).resolve().parent
SRC = WORK / 'sources/yt_Y_pnx65jAOA.mp4'
W, H, STEP = 480, 270, 0.5

raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(SRC), '-vf', f'fps={1 / STEP},scale={W}:{H}',
                      '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
n = W * H * 3
frames = [Image.frombytes('RGB', (W, H), raw[i:i + n]) for i in range(0, len(raw) - n + 1, n)]
session = new_session('u2netp')
rows = []
for k, im in enumerate(frames):
    m = np.asarray(remove(im, session=session, only_mask=True)) > 128
    lab, cnt = ndimage.label(m)
    if cnt == 0:
        continue
    sizes = ndimage.sum(m, lab, range(1, cnt + 1))
    blob = lab == (1 + int(np.argmax(sizes)))
    ys, xs = np.nonzero(blob)
    rows.append({'t': round(k * STEP, 2), 'top_gap': int(ys.min()), 'height': round((ys.max() - ys.min()) / H, 3),
                 'area': round(float(blob.mean()), 3), 'cx': round(float(xs.mean()) / W, 3)})
json.dump(rows, open(WORK / 'review/head_scan.json', 'w'), indent=0)

# close shots with a clear gap above the head, not hugging the side edges
good = [r for r in rows if r['top_gap'] >= 6 and r['height'] >= 0.6 and 0.2 < r['cx'] < 0.8]
good.sort(key=lambda r: -r['height'])
picked = []
for r in good:
    if all(abs(r['t'] - p['t']) >= 2 for p in picked):
        picked.append(r)
    if len(picked) == 24:
        break
picked.sort(key=lambda r: r['t'])
font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 20)
sheet = Image.new('RGB', (W * 6, H * 4), (30, 30, 30))
d = ImageDraw.Draw(sheet)
for i, r in enumerate(picked):
    x, y = (i % 6) * W, (i // 6) * H
    sheet.paste(frames[int(round(r['t'] / STEP))], (x, y))
    d.text((x + 6, y + 4), f"{r['t']}s gap{r['top_gap']} h{r['height']}", font=font, fill=(255, 230, 0),
           stroke_width=2, stroke_fill=(0, 0, 0))
sheet.save(WORK / 'review/head_scan.jpg', quality=85)
print(len(rows), 'frames scanned,', len(good), 'good,', 'picked', [p['t'] for p in picked])
