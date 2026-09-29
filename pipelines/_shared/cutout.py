"""Subject cutout → white die-cut sticker (RGBA PNG), cached by source hash.

Models (rembg names):
  bria-rmbg          BRIA RMBG 2.0 — best edges; CC BY-NC 4.0 (non-commercial use only)
  birefnet-general   BiRefNet — MIT; default when the job is marked commercial

BRIA's ~1 GB ONNX session runs out of memory across images on this host, so each image is cut in
a fresh child process (`python cutout.py one ...`). Run under the lab venv that has rembg,
numpy<2.3 and scipy.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

MODELS = {'bria-rmbg': 'CC BY-NC 4.0', 'birefnet-general': 'MIT', 'isnet-general-use': 'Apache-2.0'}


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
    return Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))


def make_sticker(rgb, alpha, stroke=None, shadow=True):
    """RGBA sticker: white die-cut outline around the subject plus a soft drop shadow."""
    w, h = rgb.size
    stroke = stroke or max(8, int(min(w, h) * 0.028))
    pad = stroke * 3
    size = (w + pad * 2, h + pad * 2)
    a = Image.new('L', size, 0)
    a.paste(alpha, (pad, pad))
    grown = ndimage.binary_dilation(np.asarray(a) > 127, structure=ndimage.generate_binary_structure(2, 1),
                                    iterations=stroke)
    outline = Image.fromarray((grown * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))
    out = Image.new('RGBA', size, (0, 0, 0, 0))
    if shadow:
        sh = outline.filter(ImageFilter.GaussianBlur(stroke * 1.2)).point(lambda v: int(v * 0.45))
        layer = Image.new('RGBA', size, (0, 0, 0, 0))
        layer.putalpha(sh)
        out.alpha_composite(layer, (int(stroke * 0.5), int(stroke * 0.9)))
    white = Image.new('RGBA', size, (255, 255, 255, 0))
    white.putalpha(outline)
    out.alpha_composite(white)
    subj = Image.new('RGBA', size, (0, 0, 0, 0))
    subj.paste(rgb.convert('RGBA'), (pad, pad))
    subj.putalpha(a)
    out.alpha_composite(subj)
    return out.crop(out.getbbox())


MAX_SIDE = 1500   # the approved lab stickers were cut at 1500 px; BRIA's mask changes with input size


def cache_key(image_path: Path, model: str, extra: str = '') -> str:
    h = hashlib.sha256()
    h.update(Path(image_path).read_bytes())
    h.update(f'|{model}|{MAX_SIDE}|{extra}|v2'.encode())
    return h.hexdigest()[:20]


def cut_one(image_path, out_path, model, max_side=MAX_SIDE, stroke=28):
    from rembg import new_session, remove
    from PIL import ImageOps
    im = ImageOps.exif_transpose(Image.open(image_path)).convert('RGB')
    im.thumbnail((max_side, max_side))
    mask = clean_alpha(remove(im, session=new_session(model), only_mask=True))
    make_sticker(im, mask, stroke=stroke).save(out_path)
    # mask coverage is a cheap sanity signal: near 0 or near 1 means the cut failed
    cov = float((np.asarray(mask) > 127).mean())
    return cov


def cut(image_path, cache_dir, model='bria-rmbg', python=None):
    """Cached sticker path for image_path. Spawns one child process per uncached image."""
    if model not in MODELS:
        raise ValueError(f'unknown cutout model {model}')
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f'{cache_key(image_path, model)}.png'
    meta = out.with_suffix('.json')
    if not out.exists():
        r = subprocess.run([python or sys.executable, __file__, 'one', str(image_path), str(out), model],
                           capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f'cutout failed for {image_path}: {r.stderr.strip()[-400:]}')
        meta.write_text(r.stdout.strip().splitlines()[-1], encoding='utf-8')
    info = json.loads(meta.read_text(encoding='utf-8')) if meta.exists() else {}
    return out, info


if __name__ == '__main__':
    if len(sys.argv) >= 5 and sys.argv[1] == 'one':
        cov = cut_one(sys.argv[2], sys.argv[3], sys.argv[4])
        print(json.dumps({'model': sys.argv[4], 'license': MODELS[sys.argv[4]], 'coverage': round(cov, 4)}))
    else:
        print(__doc__)
