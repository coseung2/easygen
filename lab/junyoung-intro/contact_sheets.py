"""Build labeled contact sheets of every source, in capture order, for selection review.

Videos show their middle frame and duration. Also writes data/media_index.json with
per-file date, caption title, duration, resolution, and orientation.
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.stdout.reconfigure(encoding='utf-8')
WORK = Path('F:/modal-gui/lab/2026-09-28-junyoung-intro')
SRC = WORK / 'sources'
THUMB = WORK / 'thumbs'
THUMB.mkdir(exist_ok=True)
font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 15)

rows = json.load(open(WORK / 'data' / 'moments.json', encoding='utf-8'))
index = []
for r in rows:
    title = (r['caption'] or '').split('\n')[0][:18]
    for a in r['assets'] or []:
        if a['kind'] != 'source':
            continue
        match = sorted(SRC.glob(f"{r['id'][:8]}_{a['pos'] or 0:02d}.*"))
        if not match:
            continue
        f = match[0]
        item = {'file': f.name, 'moment': r['id'], 'date': r['captured_kst'][:10], 'title': title,
                'type': a['type'].split('/')[0], 'w': a['w'], 'h': a['h'], 'hearts': r['hearts']}
        thumb = THUMB / (f.stem + '.jpg')
        if item['type'] == 'video':
            probe = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                                               'format=duration:stream=width,height:stream_side_data=rotation',
                                               '-select_streams', 'v:0', '-of', 'json', str(f)],
                                              capture_output=True, text=True).stdout)
            dur = float(probe['format'].get('duration', 0))
            item['duration'] = round(dur, 1)
            if not thumb.exists():
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(dur / 2), '-i', str(f), '-frames:v', '1',
                                '-vf', 'scale=320:320:force_original_aspect_ratio=decrease', str(thumb)])
        elif not thumb.exists():
            try:
                im = ImageOps.exif_transpose(Image.open(f)).convert('RGB')
                im.thumbnail((320, 320))
                im.save(thumb, quality=85)
            except Exception as e:  # HEIC etc.
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(f), '-vf',
                                'scale=320:320:force_original_aspect_ratio=decrease', str(thumb)])
        index.append(item)

json.dump(index, open(WORK / 'data' / 'media_index.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

cols, cw, ch, per = 8, 240, 290, 48
for s in range(0, len(index), per):
    chunk = index[s:s + per]
    sheet = Image.new('RGB', (cols * cw, ((len(chunk) + cols - 1) // cols) * ch), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    for i, it in enumerate(chunk):
        x, y = (i % cols) * cw, (i // cols) * ch
        t = THUMB / (Path(it['file']).stem + '.jpg')
        if t.exists():
            im = Image.open(t)
            im.thumbnail((cw - 8, ch - 50))
            sheet.paste(im, (x + 4 + (cw - 8 - im.width) // 2, y + 4))
        tag = f"#{s + i} {it['date'][5:]} " + (f"▶{it['duration']}s" if it['type'] == 'video' else 'img')
        d.text((x + 6, y + ch - 44), tag, font=font, fill=(200, 246, 64) if it['type'] == 'video' else 'white')
        d.text((x + 6, y + ch - 24), it['title'], font=font, fill=(170, 170, 170))
    sheet.save(WORK / f'_sheet_{s // per:02d}.jpg', quality=85)
print('media', len(index), 'videos', sum(1 for i in index if i['type'] == 'video'),
      'video seconds', round(sum(i.get('duration', 0) for i in index), 1))
