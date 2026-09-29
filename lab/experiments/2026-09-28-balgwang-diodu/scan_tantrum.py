"""Scan tantrum compilations for close shots of one person with the whole head in frame.

usage: python scan_tantrum.py <video> [step]
Writes review/scan_<id>.json and review/scan_<id>_<page>.jpg sheets (every candidate, labelled with time).
Candidate: largest blob is tall (≥ 55 % of frame height), clear gap above the head, not hugging the sides,
and roughly one person (largest blob ≥ 70 % of all foreground).
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from rembg import new_session, remove
from scipy import ndimage

WORK = Path(__file__).resolve().parent
src = Path(sys.argv[1])
STEP = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
W, H = 384, 216
vid = src.stem.replace('yt_', '')

raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(src), '-vf', f'fps={1 / STEP},scale={W}:{H}',
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
    j = int(np.argmax(sizes))
    blob = lab == (1 + j)
    ys, xs = np.nonzero(blob)
    rows.append({'t': round(k * STEP, 2), 'gap': int(ys.min()), 'h': round((ys.max() - ys.min()) / H, 3),
                 'cx': round(float(xs.mean()) / W, 3), 'solo': round(float(sizes[j] / sizes.sum()), 3),
                 'area': round(float(blob.mean()), 3)})
json.dump(rows, open(WORK / f'review/scan_{vid}.json', 'w'))
good = [r for r in rows if r['gap'] >= 10 and r['h'] >= 0.55 and 0.2 < r['cx'] < 0.8 and r['solo'] >= 0.7
        and 0.05 < r['area'] < 0.6]
font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 18)
per = 48
for p in range(0, len(good), per):
    chunk = good[p:p + per]
    sheet = Image.new('RGB', (W * 8, H * 6), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for i, r in enumerate(chunk):
        x, y = (i % 8) * W, (i // 8) * H
        sheet.paste(frames[int(round(r['t'] / STEP))], (x, y))
        d.text((x + 5, y + 3), f"{r['t']}", font=font, fill=(255, 230, 0), stroke_width=2, stroke_fill=(0, 0, 0))
    sheet.save(WORK / f'review/scan_{vid}_{p // per}.jpg', quality=80)
print(vid, len(rows), 'scanned', len(good), 'candidates', (len(good) + per - 1) // per, 'sheets')
