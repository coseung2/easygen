"""QA: ffprobe + 1fps contact sheet + 10fps strips around every snap of the rendered file."""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
WORK = Path('F:/modal-gui/lab/2026-09-28-junyoung-intro')
SRC = WORK / 'junyoung-intro-v1.mp4'
print(subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                      'format=duration,size:stream=codec_type,width,height,r_frame_rate', '-of', 'compact', str(SRC)],
                     capture_output=True, text=True).stdout)
vol = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(SRC), '-af', 'volumedetect', '-f', 'null', '-'],
                     capture_output=True, text=True).stderr
print([l.split(']')[-1].strip() for l in vol.splitlines() if 'mean_volume' in l or 'max_volume' in l])
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(SRC), '-vf', 'fps=1,scale=180:320,tile=13x2',
                '-frames:v', '1', str(WORK / '_verify_1fps.jpg')], check=True)
INTRO, CH, PLAY = 1.6, 2.8, 1.1
snaps = [INTRO + i * CH + PLAY for i in range(6)]
w, h, per = 135, 240, 8
font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 18)
sheet = Image.new('RGB', (per * w + 90, len(snaps) * h), (20, 20, 20))
d = ImageDraw.Draw(sheet)
for row, s in enumerate(snaps):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(s - 0.2), '-t', '0.8', '-i', str(SRC),
                          '-vf', f'fps=10,scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True).stdout
    n = w * h * 3
    fr = [Image.frombytes('RGB', (w, h), raw[i:i + n]) for i in range(0, len(raw) - n + 1, n)][:per]
    d.text((6, row * h + h / 2), f'{s:.1f}s', font=font, fill='white')
    for c, f in enumerate(fr):
        sheet.paste(f, (90 + c * w, row * h))
sheet.save(WORK / '_verify_snaps.jpg', quality=88)
print('ok')
