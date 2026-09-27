"""심준영 신제품 출시 — product-launch spoof, 9:16 · 30fps · ~22s. Uses cached BRIA stickers.

Grammar borrowed from NEPDA / SaaS launch refs: quiz hook, product reveal, spec callouts,
causal transitions (a scene element floods into the next background), burst cuts on the
beat, and an end card that wipes back to the opening color. Copy is grounded in 어서와
captions (steps/brief.md); '오똑한 콧날' was added by the parent.
"""
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from PIL import ImageFont
from scipy import ndimage

WORK = Path('F:/modal-gui/lab/2026-09-28-junyoung-intro')
ST = WORK / 'stickers'
FR = WORK / 'frames'
W, H, FPS = 1080, 1920, 30
MUSIC = WORK / 'music_bouncy_120.wav'
OUT = WORK / 'junyoung-launch-v5.mp4'
SAFE = 120                    # inner margin shared with the name card and growth bar
ix = json.load(open(WORK / 'data' / 'media_index.json', encoding='utf-8'))
FART_SRC = WORK / 'sources' / ix[167]['file']

GREEN = (0, 222, 90)
VIOLET = (145, 98, 255)
INK = (14, 14, 16)
PAPER = (250, 250, 246)
YELLOW = (255, 222, 60)

FONTS = Path('C:/Users/coseung2/AppData/Local/Microsoft/Windows/Fonts')
HEAD = 'C:/Users/coseung2/Desktop/Projects/modal-gui/output/promo/fonts/BlackHanSans-Regular.ttf'
GM = str(FONTS / 'GmarketSansTTFBold.ttf')
PB = str(FONTS / 'Pretendard-Black.ttf')
PSB = str(FONTS / 'Pretendard-SemiBold.ttf')
_fc = {}


def F(p, s):
    if (p, s) not in _fc:
        _fc[(p, s)] = ImageFont.truetype(p, s)
    return _fc[(p, s)]


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


def canvas(c):
    return Image.new('RGB', (W, H), c)


_disk = {}


def _disk_struct(r):
    if r not in _disk:
        y, x = np.ogrid[-r:r + 1, -r:r + 1]
        _disk[r] = x * x + y * y <= r * r
    return _disk[r]


_text_cache = {}


def text_layer(s, font, fill, stroke=0, stroke_fill=INK):
    """RGBA text with a solid outline built by dilating the glyph mask with a disk.

    PIL's own stroke leaves notches where Hangul strokes meet at sharp joins; a disk dilation
    of the filled glyphs gives an even, gap-free outline. Cached because titles repeat per frame.
    """
    key = (s, font.path, font.size, fill, stroke, stroke_fill)
    if key in _text_cache:
        return _text_cache[key]
    probe = ImageDraw.Draw(Image.new('L', (1, 1)))
    b = probe.textbbox((0, 0), s, font=font, anchor='lt')
    pad = 20 + stroke
    tw, th = b[2] - b[0] + pad * 2, b[3] - b[1] + pad * 2
    mask = Image.new('L', (tw, th), 0)
    ImageDraw.Draw(mask).text((pad - b[0], pad - b[1]), s, font=font, fill=255)
    layer = Image.new('RGBA', (tw, th), stroke_fill + (0,))
    if stroke:
        m = np.asarray(mask) > 96
        grown = ndimage.binary_dilation(m, structure=_disk_struct(stroke))
        outline = Image.fromarray((grown * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
        layer.putalpha(outline)
    glyph = Image.new('RGBA', (tw, th), fill + (0,))
    glyph.putalpha(mask)
    layer.alpha_composite(glyph)
    _text_cache[key] = (layer, pad)
    return layer, pad


def draw_text(img, xy, s, font, fill, anchor='mm', scale=1.0, rotate=0.0, alpha=1.0, stroke=0, stroke_fill=INK):
    if alpha <= 0.01 or scale <= 0.02:
        return
    layer, pad = text_layer(s, font, fill, stroke, stroke_fill)
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
        x, y = x - pad * scale, y - layer.height / 2      # glyph left edge sits on x
    elif anchor == 'rm':      # right edge of the glyphs sits on x (layer carries 20 px padding)
        x, y = x - layer.width + pad * scale, y - layer.height / 2
    img.paste(layer, (int(x), int(y)), layer)


def pill(img, cx, cy, s, font, fg, bg, pad=(40, 22), alpha=1.0, scale=1.0):
    if alpha <= 0.01 or scale <= 0.02:
        return
    probe = ImageDraw.Draw(Image.new('L', (1, 1)))
    b = probe.textbbox((0, 0), s, font=font, anchor='lt')
    w, h = (b[2] - b[0] + pad[0] * 2) * scale, (b[3] - b[1] + pad[1] * 2) * scale
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    d.rounded_rectangle((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), h / 2, fill=bg + (a,))
    img.paste(layer, (0, 0), layer)
    draw_text(img, (cx, cy), s, font, fg, scale=scale, alpha=alpha)


def load_sticker(i, box):
    """i is a media index (stickers/<i>.png) or a sticker file stem such as 'ff_145'."""
    im = Image.open(ST / f'{i}.png')
    s = min(box[0] / im.width, box[1] / im.height)
    return im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)


def paste(img, rgba, cx, cy, scale=1.0, rot=0.0):
    if scale <= 0.02:
        return
    im = rgba if scale == 1 else rgba.resize((max(1, int(rgba.width * scale)), max(1, int(rgba.height * scale))),
                                            Image.BILINEAR)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    img.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def cover(im):
    s = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def zoom_at(img, z, fx, fy):
    """Zoom by z keeping source point (fx, fy) fixed on screen."""
    if z <= 1.0001:
        return img
    w, h = W / z, H / z
    x0 = min(max(0, fx - fx / z), W - w)
    y0 = min(max(0, fy - fy / z), H - h)
    return img.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((W, H), Image.BILINEAR)


def sparkle(d, x, y, r, color):
    k = r * 0.28
    d.polygon([(x, y - r), (x + k, y - k), (x + r, y), (x + k, y + k), (x, y + r),
               (x - k, y + k), (x - r, y), (x - k, y - k)], fill=color)


def ring(img, x, y, r, color, width=10, alpha=1.0):
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((x - r, y - r, x + r, y + r), outline=color + (int(255 * alpha),), width=width)
    img.paste(layer, (0, 0), layer)


HERO = load_sticker(1, (900, 980))
NOSE = load_sticker(175, (1250, 1350))
GROW = load_sticker(158, (700, 820))
EYES = cover(Image.open(FR / 'eyes.png').convert('RGB'))
ANGEL = load_sticker(159, (820, 900))
BURST = [(79, '호기심 천국', '0o0 표정 장착'), (183, '꿀잠 모드', '어디서든 즉시'), (99, '발바닥 자랑', '말랑 보증'),
         (147, '귀여움 대방출', '신생아실 1위'), (184, '잠에 취함', '분유 먹으면 즉시'), (118, '병원도 씩씩', '울고 먹고 쌌다')]
BURST_ST = [load_sticker(i, (820, 900)) for i, _, _ in BURST]


# ---------------- scenes ----------------

def hook(lt):
    img = canvas(GREEN)
    pill(img, W / 2, 470, 'NEW', F(GM, 64), PAPER, INK, scale=out_back(prog(lt, 0, 0.3), 2.4))
    for k, (s, y) in enumerate([('신제품', 800), ('출시', 1060)]):
        p = prog(lt, 0.12 + k * 0.1, 0.45 + k * 0.1)
        draw_text(img, (W / 2, y + 1100 * (1 - out_back(p, 1.4))), s, F(HEAD, 300), INK)
    a = out_cubic(prog(lt, 0.6, 0.9))
    draw_text(img, (W / 2, 1320), '2026 F/W 한정판 · 단 1개', F(PB, 60), INK, alpha=a)
    # the NEW badge floods into the next scene's violet
    r = lerp(0, 2300, io_(prog(lt, 1.55, 2.0)))
    if r > 0:
        ImageDraw.Draw(img).ellipse((W / 2 - r, 470 - r, W / 2 + r, 470 + r), fill=VIOLET)
    return img


SPARKS = [(a, 0.55 + 0.45 * ((a * 7) % 1)) for a in np.linspace(0, math.tau, 12, endpoint=False)]


def reveal(lt):
    img = canvas(VIOLET)
    d = ImageDraw.Draw(img)
    p = prog(lt, 0.4, 1.0)
    for a, spd in SPARKS:
        dist = 200 + 520 * spd * out_cubic(p)
        if 0 < p < 1:
            sparkle(d, W / 2 + math.cos(a) * dist, 780 + math.sin(a) * dist, 46 * (1 - p * 0.6), YELLOW)
    y = lerp(-700, 780, out_back(prog(lt, 0.0, 0.45), 1.6))
    paste(img, HERO, W / 2, y, rot=lerp(-10, -3, out_cubic(prog(lt, 0, 0.5))))
    k = out_cubic(prog(lt, 0.5, 0.85))
    top = lerp(H + 50, 1360, k)
    d.rounded_rectangle((70, top, W - 70, top + 460), 44, fill=PAPER)
    draw_text(img, (120, top + 90), '심준영', F(HEAD, 120), INK, anchor='lm')
    draw_text(img, (W - 240, top + 95), 'JUNYOUNG', F(GM, 40), VIOLET)
    for n, line in enumerate(['출시일  2026. 08. 20', '숙성 기간  38주', '구성  볼살 · 발바닥 · 방구']):
        draw_text(img, (124, top + 210 + n * 72), line, F(PSB, 44), INK, anchor='lm')
    return img


EYE_PTS = [(355, 725), (740, 810)]


def eyes(lt):
    z = lerp(1.0, 1.55, io_(prog(lt, 0.0, 0.7)))
    img = zoom_at(EYES, z, 548, 770).copy()
    tone = Image.new('RGB', (W, H), INK)
    img = Image.blend(img, tone, 0.12)
    d = ImageDraw.Draw(img)
    for n, (ex, ey) in enumerate(EYE_PTS):
        sx = (ex - (548 - 548 / z)) * z if z > 1 else ex
        sy = (ey - (770 - 770 / z)) * z if z > 1 else ey
        k = out_back(prog(lt, 0.7 + n * 0.12, 1.0 + n * 0.12), 2.2)
        ring(img, sx, sy, 150 * k, GREEN, width=14)
        for s in range(3):
            tw = abs(math.sin(lt * 9 + s * 2.1 + n))
            sparkle(d, sx + [-150, 160, 30][s], sy + [-150, -110, -190][s], 40 * tw * k, YELLOW)
    draw_text(img, (W / 2, 1450), '초롱초롱', F(HEAD, 210), PAPER, stroke=10, stroke_fill=INK,
              scale=out_back(prog(lt, 1.0, 1.3), 2.2))
    draw_text(img, (W / 2, 1650), '눈망울', F(HEAD, 210), GREEN, stroke=10, stroke_fill=INK,
              scale=out_back(prog(lt, 1.12, 1.42), 2.2))
    pill(img, W / 2, 1830, 'SPEC 01 · 고해상도 눈빛 탑재', F(PB, 40), INK, GREEN, alpha=out_cubic(prog(lt, 1.4, 1.7)))
    # a green eye ring grows into the next scene's green
    r = lerp(0, 2300, io_(prog(lt, 2.45, 2.8)))
    if r > 0:
        ImageDraw.Draw(img).ellipse((W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r), fill=GREEN)
    return img


NOSE_PT = (634, 787)          # nose tip: local max of the face-profile edge (find_nose.py), inset 3px
MAG = (250, 400, 175)         # magnifier centre x, y and radius


def magnifier(img, src, px, py, cx, cy, r, zoom, s):
    """Circular loupe showing a zoomed crop around (px, py), linked by a leader line."""
    if s <= 0.02:
        return
    src_r = r / zoom
    crop = src.crop((int(px - src_r), int(py - src_r), int(px + src_r), int(py + src_r)))
    rr = max(4, int(r * s))
    crop = crop.resize((rr * 2, rr * 2), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    d.line((px, py, cx, cy), fill=INK, width=7)
    mask = Image.new('L', crop.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, rr * 2 - 1, rr * 2 - 1), fill=255)
    d.ellipse((cx - rr - 16, cy - rr - 16, cx + rr + 16, cy + rr + 16), fill=PAPER, outline=INK, width=6)
    img.paste(crop, (int(cx - rr), int(cy - rr)), mask)
    # crosshair inside the loupe, centred on the nose tip
    d.line((cx - 30, cy, cx + 30, cy), fill=YELLOW, width=5)
    d.line((cx, cy - 30, cx, cy + 30), fill=YELLOW, width=5)


def nose(lt):
    img = canvas(GREEN)
    d = ImageDraw.Draw(img)
    cx, cy = 686, 982            # puts the nose tip near (430, 740)
    s = out_back(prog(lt, 0.0, 0.4), 1.8)
    paste(img, NOSE, cx, cy, scale=s)
    nx, ny = NOSE_PT
    k = out_back(prog(lt, 0.45, 0.8), 2.0)
    if k > 0.02:
        clean = img.copy()
        ring(img, nx, ny, 58 * k, YELLOW, width=9)
        magnifier(img, clean, nx, ny, MAG[0], MAG[1], MAG[2], 2.6, k)
        n = lerp(0, 100, out_cubic(prog(lt, 0.7, 1.3)))
        pill(img, MAG[0], MAG[1] + MAG[2] + 70, f'오똑 지수 {n:.0f}%', F(GM, 46), INK, YELLOW)
    draw_text(img, (W / 2, 1480), '오똑한', F(HEAD, 200), INK, scale=out_back(prog(lt, 1.0, 1.3), 2.2))
    draw_text(img, (W / 2, 1690), '콧날', F(HEAD, 200), PAPER, stroke=10, scale=out_back(prog(lt, 1.12, 1.42), 2.2))
    pill(img, W / 2, 1860, 'SPEC 02 · 각도 측정 완료', F(PB, 40), PAPER, INK, alpha=out_cubic(prog(lt, 1.4, 1.7)))
    # an ink bar sweeps up and becomes the next background
    sweep = io_(prog(lt, 2.45, 2.8))
    if sweep > 0:
        top = lerp(H, -10, sweep)
        if top < H:
            d.rectangle((0, top, W, H), fill=INK)
    return img


BBUNG = 1.0                   # local second of the fart hit, on a downbeat (real audio aligned to this)
LAUNCH = (BBUNG, BBUNG + 0.95)
L_START, L_END = (W / 2, 860), (880, 230)
FART_GREEN = (186, 232, 120)


def launch_pos(k):
    e = clamp(k) ** 1.6       # accelerate away
    x = lerp(L_START[0], L_END[0], e)
    y = lerp(L_START[1], L_END[1], e) - 160 * math.sin(math.pi * e)
    return x, y, e


def fart(lt):
    img = canvas(INK)
    d = ImageDraw.Draw(img)
    if lt < BBUNG:
        tremble = 7 * math.sin(lt * 70) * prog(lt, 0.45, BBUNG)
        paste(img, ANGEL, L_START[0] + tremble, L_START[1], scale=out_back(prog(lt, 0, 0.3), 1.8))
        draw_text(img, (W / 2, 1520), '천사 같은 얼굴로…', F(HEAD, 120), PAPER, stroke=8,
                  alpha=out_cubic(prog(lt, 0.1, 0.35)))
    else:
        k = prog(lt, *LAUNCH)
        # blast puff at the launch point, expanding and fading
        pk = prog(lt, BBUNG, BBUNG + 0.7)
        if pk < 1:
            col = tuple(int(lerp(c, i, pk)) for c, i in zip(FART_GREEN, INK))
            for n in range(7):
                a = 1.9 + n * 0.42
                dist = 60 + 300 * out_cubic(pk)
                r = (70 + n % 3 * 28) * (0.7 + out_cubic(pk))
                x, y = L_START[0] + math.cos(a) * dist, L_START[1] + 120 + math.sin(a) * dist * 0.6
                d.ellipse((x - r, y - r, x + r, y + r), fill=col)
        # jet trail: clouds left behind along the flight path
        for j in range(1, 11):
            tj = k - j * 0.07
            if tj <= 0:
                break
            x, y, e = launch_pos(tj)
            age = j / 10
            r = (30 + 70 * (1 - e)) * (0.7 + age)
            col = tuple(int(lerp(c, i, age * 0.8)) for c, i in zip(FART_GREEN, INK))
            d.ellipse((x - r, y - r, x + r, y + r), fill=col)
        if k < 1:
            x, y, e = launch_pos(k)
            paste(img, ANGEL, x, y, scale=max(0.0, 1 - e) ** 1.2, rot=-760 * e)
        tw = prog(lt, LAUNCH[1] - 0.05, LAUNCH[1] + 0.35)
        if 0 < tw < 1:
            sparkle(d, L_END[0], L_END[1], 85 * math.sin(math.pi * tw), YELLOW)
            sparkle(d, L_END[0] + 55, L_END[1] - 45, 34 * math.sin(math.pi * tw), PAPER)
        draw_text(img, (300, 600), '뿡!', F(HEAD, 300), YELLOW, stroke=16,
                  scale=out_back(prog(lt, BBUNG, BBUNG + 0.22), 3.0), rotate=10 + 4 * math.sin(lt * 20),
                  alpha=1 - prog(lt, BBUNG + 1.2, BBUNG + 1.5))
        draw_text(img, (W / 2, 1500), '방구 추진력', F(HEAD, 190), PAPER, stroke=10,
                  scale=out_back(prog(lt, BBUNG + 0.55, BBUNG + 0.85), 2.2))
        pill(img, W / 2, 1720, 'SPEC 03 · 점점 커지는 사운드', F(PB, 40), INK, YELLOW,
             alpha=out_cubic(prog(lt, BBUNG + 0.85, BBUNG + 1.15)))
    # screen shake right after the hit
    if BBUNG <= lt < BBUNG + 0.4:
        amp = 24 * (1 - (lt - BBUNG) / 0.4)
        shaken = canvas(INK)
        shaken.paste(img, (int(amp * math.sin(lt * 95)), int(amp * 0.6 * math.cos(lt * 80))))
        img = shaken
    flash = [0.9, 0.5, 0.2][int((lt - BBUNG) * FPS)] if 0 <= (lt - BBUNG) * FPS < 3 else 0
    if flash:
        img = Image.blend(img, canvas(PAPER), flash)
    # yellow cloud floods into the next scene
    r = lerp(0, 2300, io_(prog(lt, 2.65, 3.0)))
    if r > 0:
        ImageDraw.Draw(img).ellipse((W / 2 - r, 1180 - r, W / 2 + r, 1180 + r), fill=YELLOW)
    return img


def grow(lt):
    img = canvas(YELLOW)
    d = ImageDraw.Draw(img)
    k = io_(prog(lt, 0.4, 1.9))
    sc = lerp(0.72, 1.0, out_back(prog(lt, 0.4, 2.0), 1.2))
    paste(img, GROW, W / 2, 760, scale=sc * out_back(prog(lt, 0, 0.35), 1.8))
    x0, x1, y = 120, W - 120, 1390
    d.rounded_rectangle((x0, y - 34, x1, y + 34), 34, fill=PAPER, outline=INK, width=6)
    if k > 0:
        d.rounded_rectangle((x0 + 8, y - 26, lerp(x0 + 60, x1 - 8, k), y + 26), 26, fill=GREEN)
    draw_text(img, (W / 2, 1230), f'{lerp(3.55, 4.40, k):.2f}kg', F(GM, 120), INK)
    draw_text(img, (x0, y + 90), '08.29  3.55kg', F(PSB, 38), INK, anchor='lm')
    draw_text(img, (x1 - 260, y + 90), '09.15  4.4kg', F(PSB, 38), INK, anchor='lm')
    draw_text(img, (W / 2, 1640), '쑥쑥 성장', F(HEAD, 200), INK, scale=out_back(prog(lt, 2.0, 2.3), 2.2))
    pill(img, W / 2, 1830, 'SPEC 04 · 17일 만에 +0.85kg', F(PB, 40), PAPER, INK, alpha=out_cubic(prog(lt, 2.2, 2.5)))
    return img


BURST_BG = [VIOLET, GREEN, INK, YELLOW, VIOLET, GREEN]
BEAT = 0.5


def burst(lt):
    i = min(len(BURST) - 1, int(lt / BEAT))
    local = lt - i * BEAT
    bg = BURST_BG[i]
    fg = PAPER if bg in (VIOLET, INK) else INK
    img = canvas(bg)
    paste(img, BURST_ST[i], W / 2, 860, scale=out_back(prog(local, 0, 0.18), 2.6), rot=[-5, 4, -3, 5, -4, 3][i])
    _, title, sub = BURST[i]
    draw_text(img, (W / 2, 1480), title, F(HEAD, 150), fg, scale=out_back(prog(local, 0.04, 0.2), 2.4))
    draw_text(img, (W / 2, 1640), sub, F(PB, 56), fg, alpha=out_cubic(prog(local, 0.1, 0.25)))
    draw_text(img, (W - SAFE, SAFE + 40), f'0{i + 1} / 06', F(GM, 40), fg, anchor='rm')
    return img


def endcard(lt):
    img = canvas(INK)
    draw_text(img, (W / 2, 640), '지금 우리 집에서', F(PB, 76), PAPER, alpha=out_cubic(prog(lt, 0, 0.3)))
    draw_text(img, (W / 2, 860 + 1100 * (1 - out_back(prog(lt, 0.05, 0.4), 1.4))), '심준영', F(HEAD, 280), GREEN)
    a = out_cubic(prog(lt, 0.45, 0.8))
    draw_text(img, (W / 2, 1080), '절찬 육아 중', F(HEAD, 120), PAPER, alpha=a)
    pill(img, W / 2, 1300, '한정판 1개 · 평생 소장 · 반품 불가', F(PB, 44), INK, GREEN, alpha=out_cubic(prog(lt, 0.7, 1.0)))
    draw_text(img, (W / 2, 1440), '출시 2026.08.20 · 신생아 졸업 09.19', F(PSB, 38), (170, 170, 170),
              alpha=out_cubic(prog(lt, 0.9, 1.2)))
    # green flood back to the hook color for a clean loop
    r = lerp(0, 2300, io_(prog(lt, 2.6, 3.0)))
    if r > 0:
        ImageDraw.Draw(img).ellipse((W / 2 - r, 860 - r, W / 2 + r, 860 + r), fill=GREEN)
    return img


# every cut sits on the 120 BPM beat grid (0.5 s)
SCENES = [(0.0, 2.0, hook), (2.0, 4.5, reveal), (4.5, 7.5, eyes), (7.5, 10.0, nose), (10.0, 13.0, fart),
          (13.0, 16.0, grow), (16.0, 19.0, burst), (19.0, 22.0, endcard)]
DUR = SCENES[-1][1]
GROW_T0 = 13.0
NOSE_T0 = 7.5
FART_HIT = 10.0 + BBUNG       # = 11.0 s: the music cuts out and the real fart lands on the downbeat


def render(t):
    for a, b, fn in SCENES:
        if a <= t < b:
            img = fn(t - a)
            if a > 0 and (t - a) < 2 / FPS:   # 2-frame punch-in on every cut
                img = zoom_at(img, 1.05, W / 2, H / 2)
            return img
    return SCENES[-1][2](t - SCENES[-1][0])


def sfx(path):
    sr = 48000
    tr = np.zeros(int((DUR + 1) * sr), np.float32)

    def pop(t, f0=900, f1=300, length=0.09, gain=0.35):
        n = int(length * sr)
        tt = np.arange(n) / sr
        f = np.linspace(f0, f1, n)
        tone = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-tt * 40) * gain
        s = int(t * sr)
        tr[s:s + n] += tone.astype(np.float32)

    for a, _, _ in SCENES[1:]:
        if a != 10.0:   # the fart scene starts on the tiptoe section; keep it quiet
            pop(a, 1200, 400, gain=0.22)
    for k in range(6):
        pop(16.0 + k * BEAT, 700 + k * 90, 350, gain=0.22)
    pop(2.0 + 0.45, 500, 1400, 0.14, 0.25)  # hero land 'boing'

    # fart body: a short low 'ppuung' under the real fart so it reads clearly on phone speakers
    n = int(0.42 * sr)
    tt = np.arange(n) / sr
    f0 = 118 * (1 - 0.35 * tt / 0.42) * (1 + 0.06 * np.sin(2 * np.pi * 23 * tt))
    ph = 2 * np.pi * np.cumsum(f0) / sr
    buzz = np.sign(np.sin(ph)) * 0.5 + np.sin(ph) * 0.5 + 0.25 * np.sin(2 * ph)
    buzz = np.convolve(buzz, np.ones(10) / 10, mode='same')
    env = np.minimum(tt / 0.012, 1) * np.exp(-tt * 4.5)
    s = int(FART_HIT * sr)
    tr[s:s + n] += (buzz * env * 0.32).astype(np.float32)

    # fart launch: rising whoosh, then a twinkle when the baby vanishes
    hit = FART_HIT + 0.3          # let the fart ring alone before the whoosh
    n = int(0.65 * sr)
    tt = np.arange(n) / sr
    noise = np.random.default_rng(5).standard_normal(n)
    noise = np.convolve(noise, np.ones(6) / 6, mode='same')
    sweep = np.sin(2 * np.pi * np.cumsum(np.linspace(260, 1700, n)) / sr)
    env = np.sin(np.pi * tt / 0.65) ** 2
    s = int(hit * sr)
    tr[s:s + n] += ((noise * 0.35 + sweep * 0.65) * env * 0.12).astype(np.float32)
    t2 = FART_HIT + 0.95
    m = int(0.5 * sr)
    tt = np.arange(m) / sr
    ting = (np.sin(2 * np.pi * 2600 * tt) + 0.6 * np.sin(2 * np.pi * 3900 * tt)) * np.exp(-tt * 9) * 0.18
    s = int(t2 * sr)
    tr[s:s + m] += ting.astype(np.float32)

    # growth bar: one blip per 0.05 kg the counter shows, climbing a C-major scale in step with
    # the bar's easing, a soft riser underneath, and a level-up chime when the bar is full
    def blip(t, midi, length=0.11, gain=0.16):
        n = int(length * sr)
        tt = np.arange(n) / sr
        f = 440 * 2 ** ((midi - 69) / 12)
        tone = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)
        env = np.minimum(tt / 0.003, 1) * np.exp(-tt * 28)
        s = int(t * sr)
        tr[s:s + n] += (tone * env * gain).astype(np.float32)

    g0, g1 = GROW_T0 + 0.4, GROW_T0 + 1.9          # matches k = io_(prog(lt, 0.4, 1.9)) in grow()
    steps = round((4.40 - 3.55) / 0.05)             # 17 counter steps
    scale = [67, 69, 71, 72, 74, 76, 77, 79, 81, 83, 84, 86, 88, 89, 91, 93, 95]
    for j in range(1, steps + 1):
        k = j / steps
        p = 0.5 - math.sin(math.asin(1 - 2 * k) / 3)  # inverse of the smoothstep easing
        blip(g0 + (g1 - g0) * p, scale[j - 1], gain=0.12 + 0.06 * k)
    n = int((g1 - g0) * sr)
    ramp = np.array([io_(x) for x in np.linspace(0, 1, n)])
    riser = np.sin(2 * np.pi * np.cumsum(260 + 900 * ramp) / sr) * ramp * 0.05
    s = int(g0 * sr)
    tr[s:s + n] += riser.astype(np.float32)
    for off, m in ((0.0, 84), (0.07, 88), (0.14, 91), (0.21, 96)):
        blip(g1 + off, m, length=0.5, gain=0.2)

    # nose meter: one short tick per 10 % the '오똑 지수' shows, rising with the counter's
    # out-cubic easing (fast, then settling), then a two-note 'ding-dong' at 100 %
    n0, n1 = NOSE_T0 + 0.7, NOSE_T0 + 1.3          # matches out_cubic(prog(lt, 0.7, 1.3)) in nose()
    ticks = [72, 74, 76, 77, 79, 81, 83, 84, 86, 88]
    for j in range(1, 11):
        p = 1 - (1 - j / 10) ** (1 / 3)             # inverse of out_cubic
        blip(n0 + (n1 - n0) * p, ticks[j - 1], length=0.07, gain=0.11 + 0.05 * j / 10)
    blip(n1 + 0.02, 91, length=0.35, gain=0.2)
    blip(n1 + 0.14, 96, length=0.6, gain=0.22)
    pcm = (np.clip(tr, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def main():
    import music_bouncy
    music_bouncy.build(MUSIC, DUR, groove_start=2.0, tapestop=(FART_HIT - 0.5, FART_HIT), resume=FART_HIT + 1.0,
                       burst=(16.0, 19.0), tada=19.0, tag=20.0)
    fx = WORK / 'sfx_launch.wav'
    sfx(fx)
    # real fart: onset at 10.92 s in the clip; trim the room noise before it, cut hiss, lift the low end
    fart_delay = int(FART_HIT * 1000)
    af = (f'[1:a]atrim=0:{DUR},asetpts=N/SR/TB,afade=t=out:st={DUR - 0.6}:d=0.6[m];'
          f'[2:a]atrim=start=10.9:end=11.75,asetpts=N/SR/TB,highpass=f=60,lowpass=f=4200,'
          f'equalizer=f=150:t=q:w=1.2:g=7,equalizer=f=3500:t=q:w=1.5:g=-6,'
          f'agate=threshold=0.02:ratio=3:attack=2:release=80,volume=17dB,'
          f'afade=t=in:d=0.01,afade=t=out:st=0.55:d=0.3,adelay={fart_delay}:all=1[f];'
          f'[m][f][3:a]amix=inputs=3:normalize=0:duration=first,'
          f'alimiter=limit=0.5:level=disabled,volume=3.5dB,'
          f'alimiter=limit=0.7:level=disabled[a]')
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-i', str(MUSIC), '-i', str(FART_SRC), '-i', str(fx), '-filter_complex', af,
           '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium',
           '-c:a', 'aac', '-b:a', '192k', '-t', str(DUR), str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = int(DUR * FPS)
    for n in range(total):
        proc.stdin.write(render(n / FPS).tobytes())
        if n % 90 == 0:
            print(f'{n}/{total}', flush=True)
    proc.stdin.close()
    proc.wait()
    fx.unlink(missing_ok=True)
    print('done', OUT, DUR)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'stills':
        ts = [3.9, 6.6, 8.3, 9.3, 10.9, 11.15, 11.35, 11.55, 11.8, 12.2, 16.1, 20.5]
        sheet = Image.new('RGB', (6 * 300, 2 * 533))
        for k, t in enumerate(ts):
            sheet.paste(render(t).resize((300, 533)), ((k % 6) * 300, (k // 6) * 533))
        sheet.save(WORK / '_launch_stills.jpg', quality=88)
        print('stills ok')
    else:
        main()
