"""Side-by-side view of cached stickers on a colored background."""
import sys
from PIL import Image, ImageDraw, ImageFont

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from lab_paths import font_path, lab_path

ST = str(lab_path('2026-09-28-junyoung-intro', 'stickers'))
ids = sys.argv[2:]
cell = 420
font = ImageFont.truetype(str(font_path('malgunbd.ttf', 'malgun.ttf')), 28)
sheet = Image.new('RGB', (cell * len(ids), cell + 40), (255, 216, 77))
d = ImageDraw.Draw(sheet)
for k, i in enumerate(ids):
    im = Image.open(f'{ST}/{i}.png')
    im.thumbnail((cell - 20, cell - 20))
    sheet.paste(im, (k * cell + (cell - im.width) // 2, 40 + (cell - im.height) // 2), im)
    d.text((k * cell + 10, 4), f'#{i}', font=font, fill=(40, 30, 20))
sheet.save(sys.argv[1], quality=85)
