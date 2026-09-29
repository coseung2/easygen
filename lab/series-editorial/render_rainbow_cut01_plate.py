"""08 무지개 훅 컷 — 하이브리드 테스트: 리치 플레이트 + 코드 타이포/모션.

베이스: boards/v2/scene-ref-01-full.png (GPT 생성 편집 인포그래픽 플레이트, 텍스트 없음)
타이포: Cafe24Ssurround, 문장부호 제외 광학 정렬, 무지개 그라데이션 (에피소드와 동일 로직)

usage:
  python render_rainbow_cut01_plate.py stills   배치 두 안 스틸
  python render_rainbow_cut01_plate.py render <bl|center>   5초 컷 렌더
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO / 'pipelines' / '_shared'))
sys.path.insert(0, str(REPO))
from tools.lab_paths import series_path
import render_rainbow_episode as ep  # noqa: E402
from sfx import Track  # noqa: E402

PLATE = series_path('08-rainbow', 'boards', 'v2', 'scene-ref-01-full.png')
OUT = series_path('08-rainbow', 'redo', 'cut01')
W, H, FPS = 1920, 1080, 24
T = 5.0


def load_plate():
    return Image.open(PLATE).convert('RGB').resize((W, H), Image.LANCZOS)


def title_layout(name):
    if name == 'bl':
        return (600, 792, 84), (600, 892, 112)
    return (960, 592, 84), (960, 692, 112)


def add_scrim(frame):
    from PIL import ImageFilter
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).ellipse((340, 405, 1580, 860), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(90))
    dark = Image.new('RGB', (W, H), (8, 8, 8))
    frame.paste(dark, (0, 0), mask.point(lambda v: int(v * 0.46)))
    return frame


def base_frame(plate, t):
    z = 1.0 + 0.030 * ep.io_(ep.prog(t, 0, T))
    cw, ch = W / z, H / z
    x0 = min(max(0, 960 - cw / 2), W - cw)
    y0 = min(max(0, 540 - ch / 2), H - ch)
    return plate.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.BILINEAR)


def render_frame(n, layout='center', grain=True):
    t = (n % int(T * FPS)) / FPS
    plate = load_plate()
    frame = base_frame(plate, t)
    if layout == 'center_scrim':
        frame = add_scrim(frame)
        layout = 'center'
    (c1x, c1y, s1), (c2x, c2y, s2) = title_layout(layout)
    ep.text_wipe(frame, c1x, c1y, '무지개는', ep.K.F(ep.SUR_PATH, s1), ep.PAPER,
                 ep.out_cubic(ep.prog(t, 0.80, 1.30)),
                 ep.lerp(1.06, 1.0, ep.out_cubic(ep.prog(t, 0.80, 1.30))))
    ep.text_wipe(frame, c2x, c2y, '반원일까?', ep.K.F(ep.SUR_PATH, s2), ep.GOLD,
                 ep.out_cubic(ep.prog(t, 1.10, 1.75)),
                 ep.lerp(1.15, 1.0, ep.out_back(ep.prog(t, 1.25, 1.95))), gradient=True)
    if not grain:
        return frame
    arr = np.asarray(frame, np.float32)
    dyn = np.random.default_rng(9000 + n).standard_normal((H, W, 1)).astype(np.float32)
    arr = arr + ep.FIBER_C[..., None] * 0.9 + dyn * 1.3
    arr *= ep.VIG
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def build_sfx(path):
    tr = Track(T + 0.5, seed=11)
    tr.pop(0.03, f0=150, f1=62, length=0.34, gain=0.16)
    tr.whoosh(0.15, length=1.50, gain=0.09, f0=150, f1=1500, tone=0.32)
    tr.blip(1.26, 76, length=0.20, gain=0.10)
    tr.blip(1.70, 84, length=0.34, gain=0.125)
    tr.ting(1.74, gain=0.05)
    return tr.save(path)


def cmd_stills():
    for layout in ('bl', 'center', 'center_scrim'):
        img = render_frame(int(2.6 * FPS), layout)
        dest = OUT / f'plate_test_{layout}.jpg'
        img.save(dest, quality=90)
        print('still:', dest)


def cmd_render(layout):
    OUT.mkdir(parents=True, exist_ok=True)
    wav = build_sfx(OUT / 'cut01_plate_sfx.wav')
    final = OUT / f'cut01_hook_plate_{layout}_v1.mp4'
    N = int(T * FPS)
    ep.encode_video_only(lambda n: render_frame(n, layout), N, final,
                         on_progress=lambda p: print(f'  render {p * 100:5.1f}%', flush=True))
    print('video:', final)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'stills'
    if cmd == 'stills':
        cmd_stills()
    elif cmd == 'render':
        cmd_render(sys.argv[2] if len(sys.argv) > 2 else 'center')
    else:
        raise SystemExit('unknown: ' + cmd)
