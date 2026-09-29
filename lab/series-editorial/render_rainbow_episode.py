"""08 무지개 — 편집 인포그래픽 6컷 30초 (코드 렌더, 로컬).

계약: series/08-rainbow/master-prompt-v2.md (SHOT 1-6) +
      motion-board.md. 생성 영상 미사용, 유료 호출 0.
텍스트는 마스터 프롬프트의 고정 문구를 그대로 쓴다.
중앙 정렬은 문장부호(?!.)를 제외한 글자 폭을 기준으로 한다.

usage:
  python render_rainbow_episode.py stills    씬별 스틸 6장
  python render_rainbow_episode.py render    씬별 무음 mp4 6개 (redo/scenes/)
  python render_rainbow_episode.py assemble  sfx + 음악 + 최종 mp4 + 컨택트
"""
from __future__ import annotations

import cmath
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'pipelines' / '_shared'))
sys.path.insert(0, str(REPO))
from tools.lab_paths import series_path
from motionkit import AUDIO_TAIL, Kit, find_font, io_, lerp, out_back, out_cubic, prog  # noqa: E402
from sfx import Track  # noqa: E402

W, H, FPS, S = 1920, 1080, 24, 2
CUT_T, CUTS = 5.0, 6
N_CUT = int(CUT_T * FPS)

ROOT = series_path('08-rainbow', 'redo')
SCENES = ROOT / 'scenes'

INK = (16, 16, 16)
PAPER = (240, 235, 221)
GOLD = (183, 152, 84)
CHARCOAL = (52, 52, 50)
SPECTRUM = [
    (219, 41, 36), (247, 115, 31), (245, 194, 46), (79, 176, 87),
    (48, 140, 207), (71, 79, 179), (140, 79, 173),
]

K = Kit(width=W * S, height=H * S, fps=FPS, palette='neon')
K.INK, K.PAPER = INK, PAPER
SUR_PATH = find_font(['Cafe24Ssurround.ttf'])


def arc_pts(cx, cy, r, a0, a1, step):
    span = a1 - a0
    n = max(1, int(abs(span) / step))
    return [(cx + r * math.cos(math.radians(a0 + span * i / n)),
             cy - r * math.sin(math.radians(a0 + span * i / n))) for i in range(n + 1)]


def stamp(ov, pts, color, width, alpha=255):
    d = ImageDraw.Draw(ov, 'RGBA')
    r = width / 2.0
    for x, y in pts:
        d.ellipse((x - r, y - r, x + r, y + r), fill=color + (alpha,))


def band_arc(ov, cx, cy, r, a0, a1, color, width, alpha=255):
    step = max(0.12, min(0.8, math.degrees((width * 0.7) / max(1.0, r))))
    stamp(ov, arc_pts(cx, cy, r, a0, a1, step), color, width, alpha)


def dashed_arc(ov, cx, cy, r, a0, a1, dash=16.0, gap=12.0, color=PAPER, width=5, alpha=110):
    sign = 1.0 if a1 >= a0 else -1.0
    total = math.radians(abs(a1 - a0)) * r
    a = 0.0
    while a < total:
        b = min(a + dash * S, total)
        s0 = a0 + sign * math.degrees(a / r)
        s1 = a0 + sign * math.degrees(b / r)
        stamp(ov, arc_pts(cx, cy, r, s0, s1, 0.5), color, width, alpha)
        a += (dash + gap) * S


def seg(ov, x0, y0, x1, y1, color, width, alpha=255):
    ImageDraw.Draw(ov, 'RGBA').line((x0, y0, x1, y1), fill=color + (alpha,), width=int(round(width)))


def dash_line(ov, x0, y0, x1, y1, color, width, dash=16, gap=12, frac=1.0, alpha=255):
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 1 or frac <= 0:
        return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    a = 0.0
    cut = L * min(1.0, frac)
    while a < cut:
        b = min(a + dash * S, cut)
        seg(ov, x0 + ux * a, y0 + uy * a, x0 + ux * b, y0 + uy * b, color, width, alpha)
        a += (dash + gap) * S


def arrow_head(ov, x, y, ux, uy, size, color, alpha=255):
    n = (-uy, ux)
    p1 = (x, y)
    p2 = (x - size * ux + size * 0.52 * n[0], y - size * uy + size * 0.52 * n[1])
    p3 = (x - size * ux - size * 0.52 * n[0], y - size * uy - size * 0.52 * n[1])
    ImageDraw.Draw(ov, 'RGBA').polygon([p1, p2, p3], fill=color + (alpha,))


def ray(ov, p0, p1, color, width, frac=1.0, head=0, alpha=255):
    if frac <= 0:
        return
    x0, y0 = p0
    x1, y1 = p1
    fx, fy = x0 + (x1 - x0) * frac, y0 + (y1 - y0) * frac
    seg(ov, x0, y0, fx, fy, color, width, alpha)
    L = math.hypot(x1 - x0, y1 - y0)
    if head and L > 1 and frac > 0.92:
        arrow_head(ov, fx, fy, (x1 - x0) / L, (y1 - y0) / L, head * S, color, alpha)


def circle_line_hit(cx, cy, r, ox, oy, dx, dy):
    dx, dy = dx / math.hypot(dx, dy), dy / math.hypot(dx, dy)
    fx, fy = ox - cx, oy - cy
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r
    disc = b * b - 4 * c
    if disc < 0:
        return (ox + dx * 100, oy + dy * 100)
    t = (-b + math.sqrt(disc)) / 2
    return (ox + dx * t, oy + dy * t)


def rot(dx, dy, deg):
    z = complex(dx, dy) * cmath.exp(complex(0, math.radians(deg)))
    return (z.real, z.imag)


def _phi_range(cy, r):
    s = min(1.0, max(-1.0, (cy - H) / r))
    a = math.degrees(math.asin(s))
    return a, 180.0 - a


def _core_width(s, font):
    core = s.rstrip('?!.')
    if not core:
        core = s
    return font.getlength(core)


def text_wipe(img, cx, cy, s, font, fill, frac=1.0, scale=1.0, edge=30, alpha=1.0, gradient=False):
    if frac <= 0.004 or scale <= 0.02 or alpha <= 0.02 or not s:
        return
    layer, pad = K.text_layer(s, font, fill)
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))),
                             Image.BILINEAR)
    w, h = layer.size
    x0 = int(w * min(1.0, max(0.0, frac)))
    ramp = np.clip((x0 - np.arange(w)) / float(edge) + 1.0, 0.0, 1.0)
    al = np.asarray(layer.getchannel('A'), np.float32) * ramp[None, :] * alpha
    out = layer
    if gradient:
        pos = np.linspace(0, 1, len(SPECTRUM))
        xs = np.clip((np.arange(w) - pad) / max(1.0, _core_width(s, font)), 0, 1)
        cols = np.stack([np.interp(xs, pos, [c[k] for c in SPECTRUM]) for k in range(3)], -1)
        grad = np.repeat(cols[None, :, :], h, 0).astype(np.uint8)
        out = Image.fromarray(grad, 'RGB').convert('RGBA')
        out.putalpha(layer.getchannel('A'))
    out = out.copy()
    out.putalpha(Image.fromarray(al.astype(np.uint8)))
    lx = cx - _core_width(s, font) / 2.0 - pad
    img.paste(out, (int(lx), int(cy - h / 2)), out)


def pill(img, cx, cy, s, font, fg, bg, scale=1.0, alpha=1.0, border=None):
    if scale <= 0.02 or alpha <= 0.02:
        return
    b = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), s, font=font, anchor='lt')
    pw, ph = b[2] - b[0] + 72 * S, b[3] - b[1] + 40 * S
    layer = Image.new('RGBA', (int(pw), int(ph)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer, 'RGBA')
    d.rounded_rectangle((0, 0, pw - 1, ph - 1), ph / 2, fill=bg + (int(235 * alpha),),
                        outline=(border or fg) + (int(255 * alpha),), width=3 * S)
    K.text(layer, (pw / 2, ph / 2), s, font, fg, anchor='mm', alpha=alpha)
    if scale != 1.0:
        layer = layer.resize((max(1, int(pw * scale)), max(1, int(ph * scale))), Image.BILINEAR)
    img.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)


def make_chrome(bg, fg):
    img = Image.new('RGBA', (W * S, H * S), bg + (255,))
    d = ImageDraw.Draw(img, 'RGBA')
    la = fg + (110,)
    d.line((84 * S, 84 * S, 1836 * S, 84 * S), fill=la, width=2 * S)
    d.line((84 * S, 996 * S, 1836 * S, 996 * S), fill=la, width=2 * S)
    for x, y in ((84, 84), (1836, 84), (84, 996), (1836, 996)):
        d.ellipse((x * S - 5 * S, y * S - 5 * S, x * S + 5 * S, y * S + 5 * S), fill=GOLD + (235,))
    for x in (84, 1836):
        d.line((x * S, 84 * S, x * S, 108 * S), fill=la, width=2 * S)
        d.line((x * S, 972 * S, x * S, 996 * S), fill=la, width=2 * S)
    return img


def make_fiber():
    rng = np.random.default_rng(7)
    coarse = rng.standard_normal((H, W)).astype(np.float32)
    fine = rng.standard_normal((H, W)).astype(np.float32)
    return ndimage.gaussian_filter(coarse, 2.4, mode='reflect') * 2.5, fine


def make_vignette():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
    return (1.0 - 0.075 * np.clip(r, 0, 1.35) ** 2.1)[..., None]


FIBER_C, FIBER_F = make_fiber()
VIG = make_vignette()
CHROME_INK = make_chrome(INK, PAPER)
CHROME_PAPER = make_chrome(PAPER, INK)


def scene_zoom(scene, t):
    if scene == 0:
        return 1.0 + 0.012 * io_(prog(t, 0, CUT_T)), 960 * S, 540 * S
    if scene == 1:
        return 1.0 + 0.025 * io_(prog(t, 1.6, 3.0)), 960 * S, 540 * S
    if scene == 3:
        return 1.02, 960 * S, (540 + (io_(t / CUT_T) - 0.5) * 22) * S
    return 1.0, 960 * S, 540 * S


def cloud_bumps(ov, y_base, rng, color_specs):
    for color, alpha, r0, r1, count in color_specs:
        xs = np.linspace(90, W - 90, count)
        for i, x in enumerate(xs):
            r = rng.uniform(r0, r1) * S
            y = y_base * S + (i % 2) * 26 * S
            ImageDraw.Draw(ov, 'RGBA').pieslice((x * S - r, y - r, x * S + r, y + r), 180, 360,
                                                fill=color + (alpha,))


def scene1(t, ov, img):
    cx, cy, r0 = 960, 1420, 920
    for i, col in enumerate(SPECTRUM):
        r = r0 + 33 - i * 11
        lo, hi = _phi_range(cy, r)
        start = 0.12 + i * 0.05
        p = out_cubic(prog(t, start, start + 1.35))
        if p <= 0:
            continue
        band_arc(ov, cx * S, cy * S, r * S, hi, hi + (lo - hi) * p, col, 16)
    lo, hi = _phi_range(cy, r0 - 52)
    p = out_cubic(prog(t, 0.30, 1.80))
    band_arc(ov, cx * S, cy * S, (r0 - 52) * S, hi, hi + (lo - hi) * p, PAPER, 4, 70)
    lo, hi = _phi_range(cy, r0 + 44)
    p = out_cubic(prog(t, 0.45, 2.05))
    _dash_arc_prog(ov, cx * S, cy * S, (r0 + 44) * S, hi, lo, p, PAPER, 4, 105)
    f1, f2 = K.F(SUR_PATH, 96 * S), K.F(SUR_PATH, 130 * S)
    text_wipe(img, 960 * S, 612 * S, '무지개는', f1, PAPER,
              out_cubic(prog(t, 0.80, 1.30)), lerp(1.06, 1.0, out_cubic(prog(t, 0.80, 1.30))))
    text_wipe(img, 960 * S, 748 * S, '반원일까?', f2, GOLD,
              out_cubic(prog(t, 1.10, 1.75)), lerp(1.15, 1.0, out_back(prog(t, 1.25, 1.95))),
              gradient=True)


def _dash_arc_prog(ov, cx, cy, r, a_from, a_to, frac, color, width, alpha):
    span = a_to - a_from
    total = abs(span)
    cut = total * min(1.0, max(0.0, frac))
    s = 0.0
    while s < total:
        if s >= cut:
            break
        d0, d1 = s, min(s + 3.2, total, cut)
        if d1 > d0:
            band_arc(ov, cx, cy, r, a_from + span * d0 / total, a_from + span * d1 / total,
                     color, width, alpha)
        s += 5.8


def scene2(t, ov, img):
    sd = ImageDraw.Draw(ov, 'RGBA')
    scx, scy, sr = 450, 320, 54
    sd.ellipse(((scx - sr) * S, (scy - sr) * S, (scx + sr) * S, (scy + sr) * S), fill=GOLD + (235,))
    sd.ellipse(((scx - 78) * S, (scy - 78) * S, (scx + 78) * S, (scy + 78) * S),
               outline=GOLD + (120,), width=2 * S)
    for a in (-25, 15, 55):
        x1 = (scx + math.cos(math.radians(a)) * 92) * S
        y1 = (scy - math.sin(math.radians(a)) * 92) * S
        x2 = (scx + math.cos(math.radians(a)) * 122) * S
        y2 = (scy - math.sin(math.radians(a)) * 122) * S
        seg(ov, x1, y1, x2, y2, GOLD, 3 * S, 90)
    dcx, dcy, dr = 1210, 520, 150
    sd.ellipse(((dcx - dr) * S, (dcy - dr) * S, (dcx + dr) * S, (dcy + dr) * S),
               fill=(255, 255, 255, 70), outline=INK + (255,), width=4 * S)
    sd.ellipse(((dcx - 105) * S, (dcy - 105) * S, (dcx + 105) * S, (dcy + 105) * S),
               outline=INK + (80,), width=2 * S)
    sd.ellipse(((dcx - 5) * S, (dcy - 5) * S, (dcx + 5) * S, (dcy + 5) * S), fill=INK + (200,))
    for ang, t0 in ((150, 0.5), (180, 0.9), (210, 1.3)):
        px = (dcx + math.cos(math.radians(ang)) * dr) * S
        py = (dcy - math.sin(math.radians(ang)) * dr) * S
        sx = (528 + 0.28 * (py / S - scy)) * S
        ray(ov, (sx, py), (px, py), INK, 3.5 * S, out_cubic(prog(t, t0, t0 + 0.45)), head=16)
    entry = ((dcx - dr) * S, dcy * S)
    back = ((dcx + math.cos(math.radians(-10)) * dr * 0.97) * S,
            (dcy - math.sin(math.radians(-10)) * dr * 0.97) * S)
    ray(ov, entry, back, INK, 3.5 * S, out_cubic(prog(t, 1.6, 2.2)))
    for i, col in enumerate(SPECTRUM):
        t0 = 2.35 + i * 0.11
        p = out_cubic(prog(t, t0, t0 + 0.40))
        if p <= 0:
            continue
        a = 6.0 + i * 4.0
        ex = back[0] + math.cos(math.radians(a)) * 330 * S
        ey = back[1] + math.sin(math.radians(a)) * 330 * S
        ray(ov, back, (ex, ey), col, 3.5 * S, p, head=14)
    f_chip = K.F(SUR_PATH, 46 * S)
    p_slide = out_cubic(prog(t, 3.35, 3.95))
    if t < 3.35:
        pill(img, 470 * S, 470 * S, '햇빛', f_chip, INK, PAPER, 1.0, io_(prog(t, 0.65, 1.05)))
        pill(img, 1210 * S, 770 * S, '물방울', f_chip, INK, PAPER, 1.0, io_(prog(t, 1.05, 1.45)))
    else:
        c1x, c1y = lerp(470, 818, p_slide), lerp(470, 905, p_slide)
        c2x, c2y = lerp(1210, 1102, p_slide), lerp(770, 905, p_slide)
        pill(img, c1x * S, c1y * S, '햇빛', f_chip, INK, PAPER)
        pill(img, c2x * S, c2y * S, '물방울', f_chip, INK, PAPER)
        pp = out_back(prog(t, 3.75, 4.05))
        text_wipe(img, 960 * S, 905 * S, '+', K.F(SUR_PATH, 60 * S), INK,
                  prog(t, 3.75, 4.05) * 4, lerp(1.2, 1.0, pp))


def scene3(t, ov, img):
    horizon = 800
    for i, y in enumerate((852, 902, 952)):
        xs = 160 + (i % 2) * 60
        while xs < 1760:
            seg(ov, xs * S, y * S, (xs + 60) * S, y * S, PAPER, 2 * S, 40)
            xs += 150
    sd = ImageDraw.Draw(ov, 'RGBA')
    sx, sy, sr = 1620, 260, 26
    sd.ellipse(((sx - sr) * S, (sy - sr) * S, (sx + sr) * S, (sy + sr) * S), fill=GOLD + (235,))
    sd.ellipse(((sx - 40) * S, (sy - 40) * S, (sx + 40) * S, (sy + 40) * S),
               outline=GOLD + (110,), width=2 * S)
    for a in (200, 220, 240):
        seg(ov, (sx + math.cos(math.radians(a)) * 46) * S, (sy - math.sin(math.radians(a)) * 46) * S,
            (sx + math.cos(math.radians(a)) * 66) * S, (sy - math.sin(math.radians(a)) * 66) * S,
            GOLD, 3 * S, 90)
    dash_line(ov, sx * S, sy * S, 1050 * S, 700 * S, GOLD, 2 * S, dash=18, gap=14,
              frac=out_cubic(prog(t, 0.4, 1.2)), alpha=70)
    for dx, dy, rr in ((700, 420, 5), (760, 520, 7), (1210, 480, 5), (1120, 640, 8), (860, 620, 5)):
        sd.ellipse(((dx - rr) * S, (dy - rr) * S, (dx + rr) * S, (dy + rr) * S), fill=PAPER + (80,))
    ccx, ccy, cr = 960, 620, 310
    for i, col in enumerate(SPECTRUM):
        r = cr + 16.75 - i * 5.0
        start = 0.12 + i * 0.05
        p = out_cubic(prog(t, start, start + 1.15))
        if p <= 0:
            continue
        band_arc(ov, ccx * S, ccy * S, r * S, 158.3, 158.3 - 136.6 * p, col, 7)
    p_low = out_cubic(prog(t, 1.5, 2.4))
    if p_low > 0:
        _dash_arc_prog(ov, ccx * S, ccy * S, 345 * S, 211.4, 328.6, p_low, PAPER, 4, 110)
    p_mask = io_(prog(t, 2.8, 3.4))
    if p_mask > 0:
        edge = lerp(H, horizon, p_mask)
        ImageDraw.Draw(ov, 'RGBA').rectangle((0, edge * S, W * S, H * S), fill=INK + (255,))
    seg(ov, 120 * S, horizon * S, 1800 * S, horizon * S, PAPER, 3 * S, 140)
    sd.ellipse(((960 - 15) * S, (748 - 15) * S, (960 + 15) * S, (748 + 15) * S), fill=PAPER + (255,))
    sd.polygon([(940 * S, 800 * S), (980 * S, 800 * S), (972 * S, 766 * S), (948 * S, 766 * S)],
               fill=PAPER + (255,))
    p_txt = out_cubic(prog(t, 3.5, 4.0))
    if p_txt > 0:
        out_a = 1.0 - io_(prog(t, 4.5, 4.9))
        dy = io_(prog(t, 4.5, 4.9)) * 26
        text_wipe(img, 960 * S, (258 + dy) * S, '땅이 아래쪽을 가려요', K.F(SUR_PATH, 74 * S),
                  PAPER, p_txt, 1.0, alpha=out_a)


def scene4(t, ov, img, rng):
    cloud_bumps(ov, 880, rng, [(CHARCOAL, 210, 90, 150, 5), (PAPER, 40, 70, 120, 6)])
    cloud_bumps(ov, 940, rng, [(PAPER, 90, 55, 90, 7)])
    ccx, ccy, cr = 960, 560, 280
    p_close = io_(prog(t, 0.8, 2.8))
    if p_close > 0:
        for i, col in enumerate(SPECTRUM):
            r = (cr + 23.5 - i * 7) * S
            band_arc(ov, ccx * S, ccy * S, r, 210, 210 - 120 * p_close, col, 10)
            band_arc(ov, ccx * S, ccy * S, r, 330, 330 + 120 * p_close, col, 10)
    p_bot = io_(prog(t, 1.5, 2.9))
    if p_bot > 0:
        for i, col in enumerate(SPECTRUM):
            r = (cr + 23.5 - i * 7) * S
            band_arc(ov, ccx * S, ccy * S, r, 210, 210 + 120 * p_bot, col, 10)
    p_dash = io_(prog(t, 1.2, 2.9))
    if p_dash > 0:
        dashed_arc(ov, ccx * S, ccy * S, 330 * S, 210, 210 - 120 * p_dash, dash=16, gap=12,
                   color=PAPER, width=4, alpha=90)
        dashed_arc(ov, ccx * S, ccy * S, 330 * S, 330, 330 + 120 * p_dash, dash=16, gap=12,
                   color=PAPER, width=4, alpha=90)
        dashed_arc(ov, ccx * S, ccy * S, 330 * S, 210, 210 + 120 * p_dash, dash=16, gap=12,
                   color=PAPER, width=4, alpha=90)
    if t > 2.0:
        a_arrow = io_(prog(t, 2.0, 2.6))
        for base in (45, 200):
            band_arc(ov, ccx * S, ccy * S, 352 * S, base, base - 24 * a_arrow, GOLD, 5, 170)
            ang = math.radians(base - 24 * a_arrow)
            arrow_head(ov, (ccx + 352 * math.cos(ang)) * S, (ccy - 352 * math.sin(ang)) * S,
                       math.sin(ang), math.cos(ang), 16 * S, GOLD, 190)
    sd = ImageDraw.Draw(ov, 'RGBA')
    p_dot = io_(prog(t, 2.8, 3.05))
    if p_dot > 0:
        rr = lerp(16, 6, p_dot)
        sd.ellipse(((ccx - rr) * S, (ccy - rr) * S, (ccx + rr) * S, (ccy + rr) * S),
                   fill=GOLD + (int(255 * p_dot),))
    else:
        sd.ellipse(((ccx - 5) * S, (ccy - 5) * S, (ccx + 5) * S, (ccy + 5) * S), fill=PAPER + (200,))
    for a in (0, 90, 180, 270):
        seg(ov, (ccx + math.cos(math.radians(a)) * 12) * S, (ccy - math.sin(math.radians(a)) * 12) * S,
            (ccx + math.cos(math.radians(a)) * 22) * S, (ccy - math.sin(math.radians(a)) * 22) * S,
            PAPER, 2 * S, 120)
    txt = '높은 곳에선 원이 보여요'
    f4 = K.F(SUR_PATH, 44 * S)
    slots = [0.55 if ch == ' ' else 1.0 for ch in txt]
    total_slots = sum(slots)
    acc, idx = 0.0, 0
    for ch, wt in zip(txt, slots):
        center_slot = acc + wt / 2
        acc += wt
        if ch == ' ':
            continue
        ang = 150.0 + (30.0 - 150.0) * center_slot / total_slots
        px = ccx + 395 * math.cos(math.radians(ang))
        py = ccy - 395 * math.sin(math.radians(ang))
        t0 = 3.3 + idx * 0.085
        p = out_back(prog(t, t0, t0 + 0.30))
        text_wipe(img, px * S, py * S, ch, f4, PAPER, prog(t, t0, t0 + 0.30) * 1000,
                  lerp(0.6, 1.0, p))
        idx += 1


def scene5(t, ov, img):
    O = (440, 560)
    u = (0.93, 0.37)
    Sp = (O[0] - 230 * u[0], O[1] - 230 * u[1])
    A5 = (O[0] + 430 * u[0], O[1] + 430 * u[1])
    R5 = 280
    sd = ImageDraw.Draw(ov, 'RGBA')
    p_s = out_back(prog(t, 0.5, 0.85))
    if p_s > 0:
        r = 14 * p_s
        sd.ellipse((Sp[0] * S - r * S, Sp[1] * S - r * S, Sp[0] * S + r * S, Sp[1] * S + r * S),
                   fill=GOLD + (235,))
        sd.ellipse(((Sp[0] - 26) * S, (Sp[1] - 26) * S, (Sp[0] + 26) * S, (Sp[1] + 26) * S),
                   outline=GOLD + (120,), width=2 * S)
    p_o = out_back(prog(t, 1.0, 1.35))
    if p_o > 0:
        r = 9 * p_o
        sd.ellipse((O[0] * S - r * S, O[1] * S - r * S, O[0] * S + r * S, O[1] * S + r * S),
                   fill=INK + (255,))
        sd.ellipse(((O[0] - 16) * S, (O[1] - 16) * S, (O[0] + 16) * S, (O[1] + 16) * S),
                   outline=INK + (140,), width=2 * S)
    dash_line(ov, Sp[0] * S, Sp[1] * S, (A5[0] + 60 * u[0]) * S, (A5[1] + 60 * u[1]) * S,
              GOLD, 2.5 * S, dash=18, gap=14, frac=out_cubic(prog(t, 1.3, 1.9)), alpha=110)
    p_cone = out_cubic(prog(t, 1.7, 2.35))
    for da in (-20, 20):
        d = rot(u[0], u[1], da)
        ray(ov, (O[0] * S, O[1] * S), ((O[0] + d[0] * 520) * S, (O[1] + d[1] * 520) * S),
            INK, 2.5 * S, p_cone, head=15)
    p_circ = out_cubic(prog(t, 2.1, 3.1))
    if p_circ > 0:
        dashed_arc(ov, A5[0] * S, A5[1] * S, R5 * S, 0, 360 * p_circ, dash=16, gap=12,
                   color=INK, width=4, alpha=120)
    for da, t0 in ((-20, 2.6), (0, 2.75), (20, 2.9)):
        p = out_back(prog(t, t0, t0 + 0.35))
        if p <= 0:
            continue
        d = rot(u[0], u[1], da)
        P = circle_line_hit(A5[0] * S, A5[1] * S, R5 * S, O[0] * S, O[1] * S, d[0], d[1])
        ray(ov, (O[0] * S, O[1] * S), P, INK, 3 * S, min(1.0, p))
        r = 26 * p
        sd.ellipse((P[0] - r * S, P[1] - r * S, P[0] + r * S, P[1] + r * S),
                   fill=(255, 255, 255, 60), outline=INK + (150,), width=2 * S)
        for k in range(3):
            band_arc(ov, P[0], P[1], (34 + 5 * k) * S, 210, 270, SPECTRUM[2 * k], 6, int(200 * p))
    if p_circ > 0.9:
        sd.ellipse((A5[0] * S - 9 * S, A5[1] * S - 9 * S, A5[0] * S + 9 * S, A5[1] * S + 9 * S),
                   fill=GOLD + (235,))
    f5 = K.F(SUR_PATH, 72 * S)
    text_wipe(img, 960 * S, 232 * S, '무지개는 보는 사람을', f5, INK, out_cubic(prog(t, 3.5, 4.0)), 1.0)
    text_wipe(img, 960 * S, 322 * S, '중심으로 생겨요', f5, INK, out_cubic(prog(t, 3.8, 4.3)), 1.0)


def scene6(t, ov, img):
    k = io_(prog(t, 0.45, 1.7))
    cy = lerp(1420, 560, k)
    r0 = lerp(920, 320, k)
    p_ext = out_cubic(prog(t, 0.55, 1.8))
    for i, col in enumerate(SPECTRUM):
        r = (r0 + 23.5 - i * 7) * S
        lo, hi = _phi_range(cy, r / S)
        band_arc(ov, 960 * S, cy * S, r, hi, lo, col, 10)
        if p_ext > 0:
            band_arc(ov, 960 * S, cy * S, r, hi, lerp(hi, 270, p_ext), col, 10)
            band_arc(ov, 960 * S, cy * S, r, lerp(lo, -90, p_ext), lo, col, 10)
    sd = ImageDraw.Draw(ov, 'RGBA')
    p_dot = out_back(prog(t, 1.9, 2.15))
    if p_dot > 0:
        r = 9 * p_dot
        sd.ellipse((960 * S - r * S, 560 * S - r * S, 960 * S + r * S, 560 * S + r * S),
                   fill=GOLD + (235,))
    for base in (45, 135):
        ang = math.radians(base)
        px = (960 + 372 * math.cos(ang)) * S
        py = (560 - 372 * math.sin(ang)) * S
        sd.ellipse((px - 6 * S, py - 6 * S, px + 6 * S, py + 6 * S), fill=GOLD + (200,))
    p_con = io_(prog(t, 2.2, 2.8))
    if p_con > 0:
        for r, al in ((360, 70), (410, 50)):
            band_arc(ov, 960 * S, 560 * S, r * S, 0, 360 * p_con, PAPER, 4, al)
    p_sw = io_(prog(t, 2.3, 3.3))
    if p_sw > 0:
        a0 = 200 + 320 * p_sw
        band_arc(ov, 960 * S, 560 * S, 352 * S, a0 - 26, a0, (222, 190, 120), 14, 60)
        band_arc(ov, 960 * S, 560 * S, 352 * S, a0 - 16, a0, (238, 210, 150), 7, 220)
    text_wipe(img, 960 * S, 460 * S, '무지개는 원!', K.F(SUR_PATH, 96 * S), GOLD,
              out_cubic(prog(t, 1.95, 2.5)), lerp(1.14, 1.0, out_back(prog(t, 2.1, 2.7))),
              gradient=True)
    text_wipe(img, 960 * S, 700 * S, '땅에서는 일부만 보일 뿐', K.F(SUR_PATH, 44 * S), PAPER,
              out_cubic(prog(t, 2.5, 3.0)), 1.0)


def render_frame(n):
    scene = min(CUTS - 1, n // N_CUT)
    t = (n % N_CUT) / FPS
    img = (CHROME_PAPER if scene in (1, 4) else CHROME_INK).copy()
    ov = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))
    rng = np.random.default_rng(5000 + scene * 3)
    if scene == 0:
        scene1(t, ov, img)
    elif scene == 1:
        scene2(t, ov, img)
    elif scene == 2:
        scene3(t, ov, img)
    elif scene == 3:
        scene4(t, ov, img, rng)
    elif scene == 4:
        scene5(t, ov, img)
    else:
        scene6(t, ov, img)
    img.alpha_composite(ov)
    frame = img.convert('RGB').resize((W, H), Image.LANCZOS)
    z, fx, fy = scene_zoom(scene, t)
    if z > 1.0005:
        cw, ch = W / z, H / z
        x0 = min(max(0, fx / S - cw / 2), W - cw)
        y0 = min(max(0, fy / S - ch / 2), H - ch)
        frame = frame.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.BILINEAR)
    arr = np.asarray(frame, np.float32)
    dyn = np.random.default_rng(9000 + n).standard_normal((H, W, 1)).astype(np.float32)
    arr = arr * (1.0 + FIBER_C[..., None] * 0.010) + FIBER_C[..., None] * 2.2 + FIBER_F[..., None] * 1.1 + dyn * 2.1
    arr *= VIG
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def encode_video_only(frames_fn, total, out, on_progress=None):
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf',
           '18', '-preset', 'medium', str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(total):
        proc.stdin.write(frames_fn(n).tobytes())
        if on_progress and n % 60 == 0:
            on_progress(n / total)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError('ffmpeg failed: ' + str(out))
    return out


def build_episode_sfx(path):
    tr = Track(CUT_T * CUTS + 0.5, seed=21)
    for c in range(1, CUTS):
        tr.shutter(c * CUT_T, gain=0.45)
    tr.pop(0.03, f0=150, f1=62, length=0.34, gain=0.16)
    tr.whoosh(0.15, length=1.50, gain=0.09, f0=150, f1=1500, tone=0.32)
    tr.blip(1.26, 76, length=0.20, gain=0.10)
    tr.blip(1.70, 84, length=0.34, gain=0.125)
    tr.ting(1.74, gain=0.05)
    b = CUT_T
    for t0 in (0.5, 0.9, 1.3):
        tr.pop(b + t0, 1400, 700, 0.05, gain=0.05)
    tr.chime(b + 2.35, notes=(84, 87, 91), step=0.05, gain=0.11)
    for i in range(3):
        tr.blip(b + 2.5 + i * 0.16, 81 + i * 2, length=0.16, gain=0.05)
    tr.pop(b + 0.7, 900, 500, 0.07, gain=0.06)
    tr.pop(b + 1.1, 900, 500, 0.07, gain=0.06)
    tr.whoosh(b + 3.35, length=0.5, gain=0.05, f0=300, f1=900, tone=0.4)
    tr.blip(b + 3.85, 84, length=0.3, gain=0.12)
    tr.ting(b + 3.9, gain=0.05)
    b = 2 * CUT_T
    tr.whoosh(b + 0.4, length=0.8, gain=0.05, f0=200, f1=900, tone=0.4)
    tr.counter(b + 1.5, b + 2.4, 8, lambda k: k, [67, 69, 71, 72, 74, 76, 77, 79],
               length=0.09, base=0.03, rise=0.02)
    tr.pop(b + 2.85, 90, 46, 0.5, gain=0.2)
    tr.whoosh(b + 2.9, length=0.4, gain=0.07, f0=500, f1=120, tone=0.2)
    tr.pop(b + 3.5, 1100, 600, 0.06, gain=0.07)
    tr.whoosh(b + 4.5, length=0.35, gain=0.045, f0=700, f1=200, tone=0.3)
    b = 3 * CUT_T
    tr.counter(b + 0.9, b + 2.7, 9, io_, [64, 66, 68, 69, 71, 72, 74, 76, 79],
               length=0.10, base=0.035, rise=0.03)
    tr.chime(b + 2.85, notes=(84, 88, 91, 96), step=0.05, gain=0.13)
    tr.pop(b + 2.95, 500, 240, 0.12, gain=0.09)
    tr.ting(b + 3.4, gain=0.04)
    b = 4 * CUT_T
    tr.pop(b + 0.6, 1200, 620, 0.06, gain=0.06)
    tr.pop(b + 1.1, 1100, 560, 0.06, gain=0.06)
    tr.riser(b + 1.7, b + 2.35, out_cubic, gain=0.045)
    tr.counter(b + 2.15, b + 3.05, 7, io_, [64, 67, 69, 71, 74, 76, 78],
               length=0.09, base=0.03, rise=0.025)
    for t0 in (2.6, 2.75, 2.9):
        tr.ting(b + t0, gain=0.045)
    tr.pop(b + 3.5, 1200, 700, 0.06, gain=0.07)
    b = 5 * CUT_T
    tr.riser(b + 0.5, b + 1.75, out_cubic, gain=0.06)
    tr.chime(b + 1.85, notes=(79, 84, 88, 91), step=0.05, gain=0.15)
    tr.pop(b + 1.95, 800, 400, 0.10, gain=0.10)
    tr.whoosh(b + 2.35, length=0.85, gain=0.06, f0=400, f1=1800, tone=0.5)
    tr.ting(b + 3.05, gain=0.05)
    tr.chime(28.7, notes=(72, 76, 79, 84), step=0.08, gain=0.11)
    return tr.save(path)


def cmd_stills():
    ROOT.mkdir(parents=True, exist_ok=True)
    for scene, t in ((0, 2.6), (1, 4.6), (2, 4.0), (3, 4.6), (4, 4.6), (5, 4.0)):
        dest = ROOT / f'still_s{scene + 1}.jpg'
        render_frame(scene * N_CUT + int(t * FPS)).save(dest, quality=90)
        print('still:', dest)


def cmd_render():
    SCENES.mkdir(parents=True, exist_ok=True)
    for scene in range(CUTS):
        out = SCENES / f's{scene + 1}.mp4'
        encode_video_only(lambda n, s=scene: render_frame(s * N_CUT + n), N_CUT, out,
                          on_progress=lambda p, s=scene: print(f'  s{s + 1} {p * 100:5.1f}%', flush=True))
        print('scene:', out)


def cmd_assemble():
    sfx = ROOT / '08_rainbow_sfx.wav'
    build_episode_sfx(sfx)
    lst = ROOT / 'scenes.txt'
    lines = ["file '" + str(SCENES / f's{i}.mp4').replace('\\', '/') + "'" for i in range(1, CUTS + 1)]
    lst.write_text('\n'.join(lines), encoding='utf-8')
    final = ROOT / '08_rainbow_code_v1.mp4'
    music = series_path('music-beds', 'es-bed-02.flac')
    filt = '[1:a]volume=1.0[sfx];[2:a]atrim=0:30,afade=t=in:st=0:d=1.5,afade=t=out:st=28.2:d=1.8,volume=0.45[mus];[sfx][mus]amix=inputs=2:duration=longest:normalize=0,volume=5.5dB,' + AUDIO_TAIL + '[a]'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst),
                    '-i', str(sfx), '-i', music, '-filter_complex', filt, '-map', '0:v',
                    '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', '30',
                    str(final)], check=True)
    print('final:', final)
    contact = ROOT / '08_rainbow_code_v1_contact.jpg'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(final), '-vf',
                    'fps=1,scale=320:-1,tile=6x5', '-frames:v', '1', '-q:v', '4', str(contact)],
                   check=True)
    for i, t in enumerate((2.6, 7.6, 14.0, 19.6, 24.6, 29.4)):
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t), '-i', str(final),
                        '-frames:v', '1', '-q:v', '3', str(ROOT / f'final_s{i + 1}.jpg')], check=True)
    print('contact:', contact)
    subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration,size',
                    '-show_entries', 'stream=codec_name,width,height,r_frame_rate', '-of',
                    'default=noprint_wrappers=1', str(final)])


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'stills'
    if cmd == 'stills':
        cmd_stills()
    elif cmd == 'render':
        cmd_render()
    elif cmd == 'assemble':
        cmd_assemble()
    else:
        raise SystemExit('unknown: ' + cmd)
