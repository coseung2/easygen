"""Shared drawing kit for the local-python video templates.

Promoted from lab/junyoung-intro (2026-09-28). Everything here is template-agnostic: canvas,
easing, outlined text, pills, stickers, zoom, sparkles, rings, loupe, flood wipes, and the
raw-frame encoder. Templates import this and supply their own scenes and copy.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

HERE = Path(__file__).resolve().parent
FONT_DIR = HERE / 'fonts'

# default palette ('neon'): green, violet, ink, paper, yellow
PALETTES = {
    'neon': {'a': (0, 222, 90), 'b': (145, 98, 255), 'ink': (14, 14, 16), 'paper': (250, 250, 246),
             'hi': (255, 222, 60)},
    'warm': {'a': (198, 91, 67), 'b': (255, 164, 76), 'ink': (46, 36, 32), 'paper': (255, 248, 242),
             'hi': (255, 214, 102)},
    'pastel': {'a': (120, 200, 255), 'b': (255, 140, 190), 'ink': (30, 32, 48), 'paper': (252, 250, 255),
               'hi': (255, 230, 110)},
}


def find_font(names: list[str]) -> str:
    """First existing font among bundled, per-user, and system font folders."""
    dirs = [FONT_DIR, Path.home() / 'AppData/Local/Microsoft/Windows/Fonts', Path('C:/Windows/Fonts')]
    for name in names:
        for d in dirs:
            p = d / name
            if p.exists():
                return str(p)
    raise FileNotFoundError('font not found: ' + ', '.join(names))


class Kit:
    """Canvas size, palette, fonts and drawing helpers bound together."""

    def __init__(self, width=1080, height=1920, fps=30, palette='neon'):
        self.W, self.H, self.FPS = width, height, fps
        p = PALETTES.get(palette, PALETTES['neon'])
        self.A, self.B, self.INK, self.PAPER, self.HI = p['a'], p['b'], p['ink'], p['paper'], p['hi']
        self.SAFE = round(120 * width / 1080)
        self.HEAD = find_font(['BlackHanSans-Regular.ttf'])
        self.GM = find_font(['GmarketSansTTFBold.ttf', 'malgunbd.ttf'])
        self.PB = find_font(['Pretendard-Black.ttf', 'malgunbd.ttf'])
        self.PSB = find_font(['Pretendard-SemiBold.ttf', 'malgun.ttf'])
        self._fonts = {}
        self._text = {}
        self._disk = {}

    # ---------- basics ----------
    def F(self, path, size):
        key = (path, size)
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(path, size)
        return self._fonts[key]

    def canvas(self, color):
        return Image.new('RGB', (self.W, self.H), color)

    # ---------- text ----------
    def _disk_struct(self, r):
        if r not in self._disk:
            y, x = np.ogrid[-r:r + 1, -r:r + 1]
            self._disk[r] = x * x + y * y <= r * r
        return self._disk[r]

    def text_layer(self, s, font, fill, stroke=0, stroke_fill=None):
        """RGBA text; outline = disk dilation of the glyph mask (no notches at Hangul joins)."""
        stroke_fill = stroke_fill or self.INK
        key = (s, font.path, font.size, fill, stroke, stroke_fill)
        if key in self._text:
            return self._text[key]
        probe = ImageDraw.Draw(Image.new('L', (1, 1)))
        b = probe.textbbox((0, 0), s, font=font, anchor='lt')
        pad = 20 + stroke
        tw, th = b[2] - b[0] + pad * 2, b[3] - b[1] + pad * 2
        mask = Image.new('L', (tw, th), 0)
        ImageDraw.Draw(mask).text((pad - b[0], pad - b[1]), s, font=font, fill=255)
        layer = Image.new('RGBA', (tw, th), stroke_fill + (0,))
        if stroke:
            grown = ndimage.binary_dilation(np.asarray(mask) > 96, structure=self._disk_struct(stroke))
            layer.putalpha(Image.fromarray((grown * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)))
        glyph = Image.new('RGBA', (tw, th), fill + (0,))
        glyph.putalpha(mask)
        layer.alpha_composite(glyph)
        self._text[key] = (layer, pad)
        return layer, pad

    def text(self, img, xy, s, font, fill, anchor='mm', scale=1.0, rotate=0.0, alpha=1.0, stroke=0,
             stroke_fill=None):
        if alpha <= 0.01 or scale <= 0.02 or not s:
            return
        layer, pad = self.text_layer(s, font, fill, stroke, stroke_fill)
        tw, th = layer.size
        if scale != 1:
            layer = layer.resize((max(1, int(tw * scale)), max(1, int(th * scale))), Image.BILINEAR)
        if rotate:
            layer = layer.rotate(rotate, resample=Image.BICUBIC, expand=True)
        if alpha < 1:
            layer = layer.copy()
            layer.putalpha(layer.getchannel('A').point(lambda v: int(v * alpha)))
        x, y = xy
        if anchor == 'mm':
            x, y = x - layer.width / 2, y - layer.height / 2
        elif anchor == 'lm':
            x, y = x - pad * scale, y - layer.height / 2
        elif anchor == 'rm':
            x, y = x - layer.width + pad * scale, y - layer.height / 2
        img.paste(layer, (int(x), int(y)), layer)

    def fit_font(self, path, size, s, max_width):
        """Largest font size ≤ size whose rendered width fits max_width."""
        while size > 20:
            f = self.F(path, size)
            b = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), s, font=f, anchor='lt')
            if b[2] - b[0] <= max_width:
                return f
            size -= 6
        return self.F(path, size)

    def pill(self, img, cx, cy, s, font, fg, bg, pad=(40, 22), alpha=1.0, scale=1.0):
        if alpha <= 0.01 or scale <= 0.02:
            return
        b = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), s, font=font, anchor='lt')
        w, h = (b[2] - b[0] + pad[0] * 2) * scale, (b[3] - b[1] + pad[1] * 2) * scale
        layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), h / 2,
                                                fill=bg + (int(255 * alpha),))
        img.paste(layer, (0, 0), layer)
        self.text(img, (cx, cy), s, font, fg, scale=scale, alpha=alpha)

    # ---------- images ----------
    @staticmethod
    def fit(im, box):
        s = min(box[0] / im.width, box[1] / im.height)
        return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)

    def cover(self, im):
        s = max(self.W / im.width, self.H / im.height)
        im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
        x, y = (im.width - self.W) // 2, (im.height - self.H) // 2
        return im.crop((x, y, x + self.W, y + self.H))

    @staticmethod
    def paste(img, rgba, cx, cy, scale=1.0, rot=0.0):
        if scale <= 0.02:
            return
        im = rgba if scale == 1 else rgba.resize(
            (max(1, int(rgba.width * scale)), max(1, int(rgba.height * scale))), Image.BILINEAR)
        if rot:
            im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
        img.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)

    def zoom_at(self, img, z, fx, fy):
        if z <= 1.0001:
            return img
        w, h = self.W / z, self.H / z
        x0 = min(max(0, fx - fx / z), self.W - w)
        y0 = min(max(0, fy - fy / z), self.H - h)
        return img.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((self.W, self.H), Image.BILINEAR)

    def punch(self, img, z=1.05):
        return self.zoom_at(img, z, self.W / 2, self.H / 2)

    @staticmethod
    def sparkle(d, x, y, r, color):
        if r <= 0.5:
            return
        k = r * 0.28
        d.polygon([(x, y - r), (x + k, y - k), (x + r, y), (x + k, y + k), (x, y + r),
                   (x - k, y + k), (x - r, y), (x - k, y - k)], fill=color)

    @staticmethod
    def ring(img, x, y, r, color, width=10, alpha=1.0):
        if r <= 1:
            return
        layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse((x - r, y - r, x + r, y + r), outline=color + (int(255 * alpha),), width=width)
        img.paste(layer, (0, 0), layer)

    def loupe(self, img, src, px, py, cx, cy, r, zoom, s):
        """Circular magnifier of src around (px, py) drawn at (cx, cy), with a leader line."""
        if s <= 0.02:
            return
        src_r = r / zoom
        crop = src.crop((int(px - src_r), int(py - src_r), int(px + src_r), int(py + src_r)))
        rr = max(4, int(r * s))
        crop = crop.resize((rr * 2, rr * 2), Image.LANCZOS)
        d = ImageDraw.Draw(img)
        d.line((px, py, cx, cy), fill=self.INK, width=7)
        mask = Image.new('L', crop.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, rr * 2 - 1, rr * 2 - 1), fill=255)
        d.ellipse((cx - rr - 16, cy - rr - 16, cx + rr + 16, cy + rr + 16), fill=self.PAPER, outline=self.INK, width=6)
        img.paste(crop, (int(cx - rr), int(cy - rr)), mask)
        d.line((cx - 30, cy, cx + 30, cy), fill=self.HI, width=5)
        d.line((cx, cy - 30, cx, cy + 30), fill=self.HI, width=5)

    @staticmethod
    def flood(img, cx, cy, r, color):
        if r > 0:
            ImageDraw.Draw(img).ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)


# ---------- easing ----------
def clamp(v):
    return max(0.0, min(1.0, v))


def prog(t, a, b):
    return clamp((t - a) / (b - a))


def out_back(t, s=1.9):
    t = clamp(t) - 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


def out_cubic(t):
    return 1 - (1 - clamp(t)) ** 3


def io_(t):
    t = clamp(t)
    return 3 * t * t - 2 * t ** 3


def lerp(a, b, k):
    return a + (b - a) * k


def inv_smoothstep(k):
    """Progress p in [0,1] where io_(p) == k."""
    return 0.5 - math.sin(math.asin(1 - 2 * k) / 3)


def inv_out_cubic(k):
    return 1 - (1 - k) ** (1 / 3)


# ---------- media ----------
def grab_frame(src, t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', str(src), '-frames:v', '1',
                          '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, check=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(raw)).convert('RGB')


def decode_clip(src, start, dur, W, H, fps):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(start), '-t', str(dur), '-i', str(src),
                          '-vf', f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    n = W * H * 3
    return [Image.frombytes('RGB', (W, H), raw[i:i + n]) for i in range(0, len(raw) - n + 1, n)]


def load_image(path):
    from PIL import ImageOps
    return ImageOps.exif_transpose(Image.open(path)).convert('RGB')


def is_video(path):
    return Path(path).suffix.lower() in {'.mp4', '.mov', '.m4v', '.webm', '.mkv'}


# ---------- encoding ----------
AUDIO_TAIL = 'alimiter=limit=0.5:level=disabled,volume=3.5dB,alimiter=limit=0.7:level=disabled'


def encode(frames_fn, total, W, H, fps, audio_inputs, filter_complex, out, dur, on_progress=None):
    """Pipe rendered frames into FFmpeg with the given audio graph. audio_inputs are extra -i paths."""
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps),
           '-i', '-']
    for a in audio_inputs:
        cmd += ['-i', str(a)]
    cmd += ['-filter_complex', filter_complex, '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-pix_fmt',
            'yuv420p', '-crf', '18', '-preset', 'medium', '-c:a', 'aac', '-b:a', '192k', '-t', str(dur), str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(total):
        proc.stdin.write(frames_fn(n).tobytes())
        if on_progress and n % 30 == 0:
            on_progress(n / total)
    proc.stdin.close()
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f'ffmpeg exited with {code}')
    return out
