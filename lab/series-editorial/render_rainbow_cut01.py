"""08 무지개 훅 컷 01 — 편집 인포그래픽 재제작 테스트 (로컬 코드 렌더).

보드 계약 (series/08-rainbow/motion-board.md, 컷 01):
  먹색 바탕(#101010), 무지개 일곱 색 띠가 왼쪽에서 오른쪽으로 순차로 그려지고,
  반원 끝은 화면 아래로 잘린다. 얇은 기준선·등록 마크. 큰 제목
  "무지개는 반원일까?"가 마스크 와이프 + 간결한 스케일 펀치로 등장.

usage:
  python render_rainbow_cut01.py fonts    폰트 비교 시트
  python render_rainbow_cut01.py render   cut01_hook_v1.mp4 (5초, 1920x1080, 24fps)
  python render_rainbow_cut01.py stills   렌더 후 스틸/컨택트시트
"""
from __future__ import annotations

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
from motionkit import AUDIO_TAIL, Kit, encode, find_font, io_, lerp, out_back, out_cubic, prog  # noqa: E402
from sfx import Track  # noqa: E402

W, H, FPS = 1920, 1080, 24
S = 2                      # supersample: draw at 2x, downscale once
T = 5.0
N = int(T * FPS)
OUT = series_path('08-rainbow', 'redo', 'cut01')

INK = (16, 16, 16)         # #101010
PAPER = (240, 235, 221)    # #F0EBDD
GOLD = (183, 152, 84)      # #B79854
SPECTRUM = [
    (219, 41, 36), (247, 115, 31), (245, 194, 46), (79, 176, 87),
    (48, 140, 207), (71, 79, 179), (140, 79, 173),
]
BAND_W, BAND_GAP = 8, 3

K = Kit(width=W * S, height=H * S, fps=FPS, palette='neon')
K.INK, K.PAPER = INK, PAPER

FONTS = {
    'jua': 'BMJUA_ttf.ttf',
    'gmarket': 'GmarketSansTTFBold.ttf',
    'pretendard': 'Pretendard-ExtraBold.ttf',
    'surround': 'Cafe24Ssurround.ttf',
}
FONT_PATHS = {k: find_font([v]) for k, v in FONTS.items()}

# ---------- geometry (1x units) ----------
CX, CY, R = 960, 1420, 920        # 반원 중심은 화면 아래 → 양 끝이 아랫변에 잘림
STROKE = 10
R_IN = R - 52                     # 안쪽 얇은 기준원
R_DASH = R + 44                   # 바깥 점선 기준호


def phi_range(r):
    s = min(1.0, max(-1.0, (CY - H) / r))
    a = math.degrees(math.asin(s))
    return a, 180.0 - a


PHI_L, PHI_R = phi_range(R)
PHI_L_IN, PHI_R_IN = phi_range(R_IN)
PHI_L_DA, PHI_R_DA = phi_range(R_DASH)


def arc_pts(cx, cy, r, a0, a1, step=0.4):
    """도 단위 각도 a0→a1 (왼쪽=큰 각) 경로 위의 점 목록."""
    span = a1 - a0
    n = max(1, int(abs(span) / step))
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + span * i / n)
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
    return pts


def stamp(ov, pts, color, width, alpha=255):
    d = ImageDraw.Draw(ov, 'RGBA')
    r = width / 2.0
    for x, y in pts:
        d.ellipse((x - r, y - r, x + r, y + r), fill=color + (alpha,))


def dash_stamp(ov, cx, cy, r, a_from, a_to, frac, color, width, alpha, dash=3.4, gap=2.6):
    """frac(0..1)까지 점선을 순차 공개하며 찍는다."""
    span = a_to - a_from
    total = abs(span)
    cut = total * min(1.0, max(0.0, frac))
    s = 0.0
    while s < total:
        if s >= cut:
            break
        d0, d1 = s, min(s + dash, total, cut)
        if d1 > d0:
            seg_start = a_from + span * (d0 / total)
            seg_end = a_from + span * (d1 / total)
            stamp(ov, arc_pts(cx, cy, r, seg_start, seg_end, 0.4), color, width, alpha)
        s += dash + gap


def wipe_text(img, xy, s, font, fill, frac, scale=1.0, edge=30):
    """마스크 와이프 + 스케일을 적용한 텍스트 합성."""
    if frac <= 0.004 or scale <= 0.02:
        return
    layer, _pad = K.text_layer(s, font, fill)
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))),
                             Image.BILINEAR)
    w, h = layer.size
    x0 = int(w * min(1.0, max(0.0, frac)))
    a = np.clip((x0 - np.arange(w)) / float(edge) + 1.0, 0.0, 1.0)
    al = np.asarray(layer.getchannel('A'), np.float32) * a[None, :]
    layer.putalpha(Image.fromarray(al.astype(np.uint8)))
    img.paste(layer, (int(xy[0] - w / 2), int(xy[1] - h / 2)), layer)


def spectrum_text(img, xy, s, font, frac, scale=1.0, edge=30):
    """무지개 그라데이션 + 마스크 와이프 텍스트."""
    if frac <= 0.004 or scale <= 0.02:
        return
    layer, _pad = K.text_layer(s, font, PAPER)
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))),
                             Image.BILINEAR)
    w, h = layer.size
    pos = np.linspace(0, 1, len(SPECTRUM))
    xs = np.linspace(0, 1, w)
    cols = np.stack([np.interp(xs, pos, [c[k] for c in SPECTRUM]) for k in range(3)], -1)
    grad = np.repeat(cols[None, :, :], h, 0).astype(np.uint8)
    x0 = int(w * min(1.0, max(0.0, frac)))
    a = np.clip((x0 - np.arange(w)) / float(edge) + 1.0, 0.0, 1.0)
    al = np.asarray(layer.getchannel('A'), np.float32) * a[None, :]
    out = Image.fromarray(grad, 'RGB').convert('RGBA')
    out.putalpha(Image.fromarray(al.astype(np.uint8)))
    img.paste(out, (int(xy[0] - w / 2), int(xy[1] - h / 2)), out)


# ---------- chrome / texture ----------
def make_chrome():
    img = Image.new('RGBA', (W * S, H * S), INK + (255,))
    d = ImageDraw.Draw(img, 'RGBA')
    line_a = PAPER + (110,)
    d.line((84 * S, 84 * S, 1836 * S, 84 * S), fill=line_a, width=2 * S)
    d.line((84 * S, 996 * S, 1836 * S, 996 * S), fill=line_a, width=2 * S)
    for x, y in ((84, 84), (1836, 84), (84, 996), (1836, 996)):
        d.ellipse((x * S - 5 * S, y * S - 5 * S, x * S + 5 * S, y * S + 5 * S), fill=GOLD + (235,))
    for x in (84, 1836):  # 위 기준선 중앙 눈금
        d.line((x * S, 84 * S, x * S, 108 * S), fill=line_a, width=2 * S)
        d.line((x * S, 972 * S, x * S, 996 * S), fill=line_a, width=2 * S)
    return img


def make_fiber():
    rng = np.random.default_rng(7)
    coarse = rng.standard_normal((H, W)).astype(np.float32)
    fine = rng.standard_normal((H, W)).astype(np.float32)
    return ndimage.gaussian_filter(coarse, 2.4, mode='reflect') * 2.5, fine


def make_vignette():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    nx = (x - W / 2) / (W / 2)
    ny = (y - H / 2) / (H / 2)
    r = np.sqrt(nx * nx + ny * ny)
    return (1.0 - 0.075 * np.clip(r, 0, 1.35) ** 2.1)[..., None]


FIBER_C, FIBER_F = make_fiber()
VIG = make_vignette()
CHROME = make_chrome()


def render_frame(n):
    t = n / FPS
    img = CHROME.copy()
    ov = Image.new('RGBA', (W * S, H * S), (0, 0, 0, 0))

    # 무지개 일곱 색 띠 — 왼쪽에서 오른쪽으로, 빨강부터 순차로 그려진다
    for i, col in enumerate(SPECTRUM):
        r_i = R + 33 - i * (BAND_W + BAND_GAP)
        lo, hi = phi_range(r_i)
        start = 0.12 + i * 0.05
        p_i = out_cubic(prog(t, start, start + 1.35))
        if p_i <= 0.0:
            continue
        a_now = hi + (lo - hi) * p_i
        stamp(ov, arc_pts(CX * S, CY * S, r_i * S, hi, a_now), col, BAND_W * S)

    # 안쪽 얇은 기준원
    p_in = out_cubic(prog(t, 0.30, 1.80))
    a_in = PHI_R_IN + (PHI_L_IN - PHI_R_IN) * p_in
    stamp(ov, arc_pts(CX * S, CY * S, R_IN * S, PHI_R_IN, a_in), PAPER, int(2.0 * S), 70)

    # 바깥 점선 기준호 — 점선이 순차로 찍힌다
    p_da = out_cubic(prog(t, 0.45, 2.05))
    dash_stamp(ov, CX * S, CY * S, R_DASH * S, PHI_R_DA, PHI_L_DA, p_da, PAPER, int(2.0 * S), 105)

    img.alpha_composite(ov)

    # 제목: 2줄, 마스크 와이프 + 스케일 펀치
    f1 = K.F(FONT_PATHS[cur_font], 96 * S)
    f2 = K.F(FONT_PATHS[cur_font], 130 * S)
    p1 = out_cubic(prog(t, 0.80, 1.30))
    wipe_text(img, (960 * S, 612 * S), '무지개는', f1, PAPER, p1, lerp(1.06, 1.0, p1))
    p2w = out_cubic(prog(t, 1.10, 1.75))
    p2s = out_back(prog(t, 1.25, 1.95))
    spectrum_text(img, (960 * S, 748 * S), '반원일까?', f2, p2w, lerp(1.15, 1.0, p2s))

    # 다운스케일 → 슬로우 줌 → 그레인/비네트
    frame = img.convert('RGB').resize((W, H), Image.LANCZOS)
    z = 1.0 + 0.012 * io_(prog(t, 0, T))
    if z > 1.0005:
        cw, ch = W / z, H / z
        frame = frame.crop((int((W - cw) / 2), int((H - ch) / 2),
                            int((W + cw) / 2), int((H + ch) / 2))).resize((W, H), Image.BILINEAR)
    arr = np.asarray(frame, np.float32)
    dyn = np.random.default_rng(1000 + n).standard_normal((H, W, 1)).astype(np.float32)
    arr = arr * (1.0 + FIBER_C[..., None] * 0.010) + FIBER_C[..., None] * 2.2 + FIBER_F[..., None] * 1.1 \
        + dyn * 2.1
    arr *= VIG
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def build_sfx(path):
    tr = Track(T + 0.5, seed=11)
    tr.pop(0.03, f0=150, f1=62, length=0.34, gain=0.16)
    tr.whoosh(0.15, length=1.50, gain=0.09, f0=150, f1=1500, tone=0.32)
    tr.blip(1.26, 76, length=0.20, gain=0.10)
    tr.blip(1.70, 84, length=0.34, gain=0.125)
    tr.ting(1.74, gain=0.05)
    return tr.save(path)


def cmd_fonts():
    global cur_font
    rows = []
    for name, fname in FONTS.items():
        cur_font = name
        frame = render_frame(int(2.4 * FPS)).crop((430, 470, 1490, 890))
        strip = Image.new('RGB', (1060, 40), INK)
        ImageDraw.Draw(strip).text((12, 6), name + '  (' + fname + ')', font=K.F(FONT_PATHS[name], 26),
                                   fill=GOLD)
        row = Image.new('RGB', (1060, 460), INK)
        row.paste(strip, (0, 0))
        row.paste(frame, (0, 40))
        rows.append(row)
    sheet = Image.new('RGB', (1060, 460 * len(rows) + 16 * (len(rows) - 1)), INK)
    for i, row in enumerate(rows):
        sheet.paste(row, (0, i * (460 + 16)))
    dest = OUT / 'fonts_sheet.jpg'
    sheet.save(dest, quality=90)
    print('fonts sheet:', dest)


def cmd_render():
    global cur_font
    OUT.mkdir(parents=True, exist_ok=True)
    wav = build_sfx(OUT / 'cut01_sfx.wav')
    final = OUT / f'cut01_hook_{cur_font}_v{V}.mp4'
    out = encode(render_frame, N, W, H, FPS, [str(wav)], '[1:a]' + AUDIO_TAIL + '[a]', str(final), T,
                 on_progress=lambda p: print(f'  render {p*100:5.1f}%', flush=True))
    print('video:', out)
    return final


def cmd_stills(final=None):
    final = final or OUT / f'cut01_hook_{cur_font}_v{V}.mp4'
    contact = OUT / f'cut01_contact_{cur_font}_v{V}.jpg'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(final), '-vf',
                    'fps=2,scale=384:-1,tile=5x2', '-frames:v', '1', '-q:v', '4', str(contact)], check=True)
    for t, name in ((2.60, f'still_{cur_font}_v{V}_t2.6.jpg'),):
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t), '-i', str(final), '-frames:v', '1',
                        '-q:v', '3', str(OUT / name)], check=True)
    print('contact:', contact)


cur_font = 'surround'
V = 2

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'render'
    if cmd == 'fonts':
        OUT.mkdir(parents=True, exist_ok=True)
        cmd_fonts()
    elif cmd == 'render':
        cmd_render()
    elif cmd == 'stills':
        cmd_stills()
    else:
        raise SystemExit('unknown command: ' + cmd)
