"""Freeze-frame parody prep (lab venv): grab the exact freeze frame of each clip, cut it with
BRIA RMBG 2.0, and cache frames/ff_<idx>.png + stickers/ff_<idx>.png plus a review sheet."""
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rembg import new_session, remove

sys.path.insert(0, str(Path(__file__).parent))
from sticker import clean_alpha, make_sticker  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from lab_paths import font_path, lab_path

WORK = lab_path('2026-09-28-junyoung-intro')
ix = json.load(open(WORK / 'data' / 'media_index.json', encoding='utf-8'))

# (media index, freeze second)
CUTS = [(145, 15.0), (168, 23.4), (164, 10.8), (91, 12.4), (169, 13.4), (176, 10.8)]


def grab(idx, t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', str(WORK / 'sources' / ix[idx]['file']),
                          '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True,
                         check=True).stdout
    return Image.open(io.BytesIO(raw)).convert('RGB')


if __name__ == '__main__':
    # BRIA's 1 GB session runs out of memory across images, so each cut runs in its own process:
    #   python prep_freeze.py one <idx> <t>     -> one frame + sticker
    #   python prep_freeze.py                   -> spawn one process per cut, then build the sheet
    if len(sys.argv) > 1 and sys.argv[1] == 'one':
        idx, t = int(sys.argv[2]), float(sys.argv[3])
        session = new_session('bria-rmbg')
        fr, st = WORK / 'frames' / f'ff_{idx}.png', WORK / 'stickers' / f'ff_{idx}.png'
        im = grab(idx, t)
        im.save(fr)
        if not st.exists():
            small = im.copy()
            small.thumbnail((1400, 1400))
            mask = clean_alpha(remove(small, session=session, only_mask=True))
            make_sticker(small, mask, stroke=28).save(st)
        print('ok', idx, im.size, flush=True)
        sys.exit(0)
    for idx, t in CUTS:
        if not (WORK / 'stickers' / f'ff_{idx}.png').exists():
            subprocess.run([sys.executable, __file__, 'one', str(idx), str(t)], check=True)
    cell = 420
    font = ImageFont.truetype(str(font_path('malgunbd.ttf', 'malgun.ttf')), 26)
    sheet = Image.new('RGB', (cell * len(CUTS), cell * 2), (255, 216, 77))
    d = ImageDraw.Draw(sheet)
    for k, (idx, _) in enumerate(CUTS):
        for row, p in enumerate([WORK / 'frames' / f'ff_{idx}.png', WORK / 'stickers' / f'ff_{idx}.png']):
            im = Image.open(p).convert('RGBA')
            im.thumbnail((cell - 20, cell - 20))
            sheet.paste(im, (k * cell + (cell - im.width) // 2, row * cell + (cell - im.height) // 2), im)
        d.text((k * cell + 8, 4), f'#{idx}', font=font, fill=(40, 30, 20))
    sheet.save(WORK / '_ff_review.jpg', quality=85)
