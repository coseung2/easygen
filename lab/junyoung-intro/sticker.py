"""Sticker cutout: segment, clean the alpha, add a bold white die-cut stroke and soft shadow.

Usage: python sticker.py <model> <out.jpg> <index>...   (index = media_index.json position)
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from rembg import new_session, remove
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from lab_paths import font_path, lab_path

WORK = lab_path('2026-09-28-junyoung-intro')


def clean_alpha(alpha, thresh=0.5):
    """Binarize (kills haze), keep the largest blob, fill holes, then feather 1px."""
    a = np.asarray(alpha, np.float32) / 255.0
    m = a > thresh
    lab, n = ndimage.label(m)
    if n > 1:
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        m = lab == (1 + int(np.argmax(sizes)))
    m = ndimage.binary_fill_holes(m)
    m = ndimage.binary_opening(m, iterations=2)
    out = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    return out


def make_sticker(rgb, alpha, stroke=None, shadow=True):
    """Return RGBA sticker: white die-cut outline around the subject, plus drop shadow."""
    w, h = rgb.size
    stroke = stroke or max(8, int(min(w, h) * 0.028))
    pad = stroke * 3
    canvas = (w + pad * 2, h + pad * 2)
    a = Image.new('L', canvas, 0)
    a.paste(alpha, (pad, pad))
    m = np.asarray(a) > 127
    grown = ndimage.binary_dilation(m, structure=ndimage.generate_binary_structure(2, 1), iterations=stroke)
    outline = Image.fromarray((grown * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))
    out = Image.new('RGBA', canvas, (0, 0, 0, 0))
    if shadow:
        sh = outline.filter(ImageFilter.GaussianBlur(stroke * 1.2)).point(lambda v: int(v * 0.45))
        shadow_layer = Image.new('RGBA', canvas, (0, 0, 0, 0))
        shadow_layer.putalpha(sh)
        out.alpha_composite(shadow_layer, (int(stroke * 0.5), int(stroke * 0.9)))
    white = Image.new('RGBA', canvas, (255, 255, 255, 0))
    white.putalpha(outline)
    out.alpha_composite(white)
    subj = Image.new('RGBA', canvas, (0, 0, 0, 0))
    subj.paste(rgb.convert('RGBA'), (pad, pad))
    subj.putalpha(a)
    out.alpha_composite(subj)
    return out.crop(out.getbbox())


def load(i):
    index = json.load(open(WORK / 'data' / 'media_index.json', encoding='utf-8'))
    im = ImageOps.exif_transpose(Image.open(WORK / 'sources' / index[i]['file'])).convert('RGB')
    im.thumbnail((1400, 1400))
    return im


if __name__ == '__main__':
    model, out_path, picks = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3:]]
    session = new_session(model)
    cell = 360
    font = ImageFont.truetype(str(font_path('malgun.ttf', 'Malgun.ttf')), 20)
    sheet = Image.new('RGB', (cell * len(picks), cell), (150, 104, 255))
    for k, i in enumerate(picks):
        im = load(i)
        alpha = remove(im, session=session, only_mask=True)
        st = make_sticker(im, clean_alpha(alpha))
        st.thumbnail((cell - 20, cell - 20))
        sheet.paste(st, (k * cell + (cell - st.width) // 2, (cell - st.height) // 2), st)
        ImageDraw.Draw(sheet).text((k * cell + 8, 6), f'#{i}', font=font, fill='white')
        print('done', i, flush=True)
    sheet.save(out_path, quality=90)
