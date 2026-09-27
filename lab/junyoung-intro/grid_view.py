"""Large view of one sticker/frame with a labelled 100px source-coordinate grid."""
import sys
from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]
im = Image.open(src).convert('RGBA')
bg = Image.new('RGBA', im.size, (150, 104, 255, 255))
bg.alpha_composite(im)
d = ImageDraw.Draw(bg)
font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 22)
for x in range(0, im.width, 100):
    d.line((x, 0, x, im.height), fill=(255, 255, 0, 255), width=1)
    d.text((x + 3, 3), str(x), font=font, fill=(255, 0, 0, 255))
for y in range(0, im.height, 100):
    d.line((0, y, im.width, y), fill=(255, 255, 0, 255), width=1)
    d.text((3, y + 3), str(y), font=font, fill=(255, 0, 0, 255))
bg.convert('RGB').save(out, quality=85)
