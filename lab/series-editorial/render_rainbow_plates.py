"""08 무지개 2-6컷 — 하이브리드 렌더: AI 플레이트 + 코드 타이포/모션.

플레이트: redo/plates/s2..s6.png (GPT 이미지, 텍스트 없음, 타이포 자리 비움)
타이포: Cafe24Ssurround, 문장부호 제외 광학 정렬 (에피소드 로직 재사용)
1컷은 승인된 redo/cut01/cut01_hook_plate_center_scrim_v1.mp4 를 그대로 사용한다.

usage:
  python render_rainbow_plates.py stills    2-6컷 스틸
  python render_rainbow_plates.py render    2-6컷 무음 mp4 (redo/scenes_hybrid/)
  python render_rainbow_plates.py assemble  최종 30초 + 컨택트 + 검증
"""
from __future__ import annotations

import math
import subprocess
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

W, H, FPS, T = 1920, 1080, 24, 5.0
N_CUT = int(T * FPS)
ROOT = series_path('08-rainbow', 'redo')
PLATES = ROOT / 'plates'
OUT = ROOT / 'scenes_hybrid'
CUT01 = ROOT / 'cut01' / 'cut01_hook_plate_center_scrim_v1.mp4'

PUSH = {2: 0.030, 3: 0.015, 4: 0.020, 5: 0.015, 6: 0.020}


def load_plate(cut):
    return Image.open(PLATES / f's{cut}.png').convert('RGB').resize((W, H), Image.LANCZOS)


def base_frame(plate, t, cut):
    z = 1.0 + PUSH[cut] * ep.io_(ep.prog(t, 0, T))
    cw, ch = W / z, H / z
    x0 = min(max(0, 960 - cw / 2), W - cw)
    y0 = min(max(0, 540 - ch / 2), H - ch)
    return plate.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.BILINEAR)


def cut2(frame, t):
    f_chip = ep.K.F(ep.SUR_PATH, 46)
    p1 = ep.io_(ep.prog(t, 1.05, 1.60))
    p2 = ep.io_(ep.prog(t, 1.35, 1.90))
    c1x = ep.lerp(560, 818, p1)
    c2x = ep.lerp(1360, 1102, p2)
    ep.pill(frame, c1x, 905, '햇빛', f_chip, ep.INK, ep.PAPER, 1.0, min(1.0, p1 * 2))
    ep.pill(frame, c2x, 905, '물방울', f_chip, ep.INK, ep.PAPER, 1.0, min(1.0, p2 * 2))
    pp = ep.out_back(ep.prog(t, 2.0, 2.3))
    ep.text_wipe(frame, 960, 905, '+', ep.K.F(ep.SUR_PATH, 60), ep.PAPER,
                 ep.prog(t, 2.0, 2.35) * 4, ep.lerp(1.2, 1.0, pp))


def cut3(frame, t):
    dy = ep.io_(ep.prog(t, 4.4, 4.85)) * 26
    ep.text_wipe(frame, 960, 240 + dy, '땅이 아래쪽을 가려요', ep.K.F(ep.SUR_PATH, 74), ep.PAPER,
                 ep.out_cubic(ep.prog(t, 1.2, 1.75)), 1.0,
                 alpha=1.0 - ep.io_(ep.prog(t, 4.4, 4.85)))


def cut4(frame, t):
    ep.text_wipe(frame, 960, 225, '높은 곳에선 원이 보여요', ep.K.F(ep.SUR_PATH, 74), ep.PAPER,
                 ep.out_cubic(ep.prog(t, 1.4, 2.0)), 1.0)


def cut5(frame, t):
    f5 = ep.K.F(ep.SUR_PATH, 72)
    ep.text_wipe(frame, 960, 225, '무지개는 보는 사람을', f5, ep.PAPER,
                 ep.out_cubic(ep.prog(t, 1.3, 1.82)), 1.0)
    ep.text_wipe(frame, 960, 315, '중심으로 생겨요', f5, ep.PAPER,
                 ep.out_cubic(ep.prog(t, 1.6, 2.12)), 1.0)


def cut6(frame, t):
    ep.text_wipe(frame, 960, 450, '무지개는 원!', ep.K.F(ep.SUR_PATH, 96), ep.GOLD,
                 ep.out_cubic(ep.prog(t, 1.1, 1.7)),
                 ep.lerp(1.14, 1.0, ep.out_back(ep.prog(t, 1.25, 1.95))), gradient=True)
    ep.text_wipe(frame, 960, 690, '땅에서는 일부만 보일 뿐', ep.K.F(ep.SUR_PATH, 44), ep.PAPER,
                 ep.out_cubic(ep.prog(t, 1.8, 2.3)), 1.0)


def render_frame(n, cut):
    t = (n % N_CUT) / FPS
    frame = base_frame(load_plate(cut), t, cut)
    {'2': cut2, '3': cut3, '4': cut4, '5': cut5, '6': cut6}[str(cut)](frame, t)
    arr = np.asarray(frame, np.float32)
    dyn = np.random.default_rng(9000 + cut * 1000 + n).standard_normal((H, W, 1)).astype(np.float32)
    arr = arr + ep.FIBER_C[..., None] * 0.9 + dyn * 1.3
    arr *= ep.VIG
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def cmd_stills():
    ROOT.mkdir(parents=True, exist_ok=True)
    for cut, t in ((2, 2.6), (3, 1.9), (4, 2.2), (5, 2.4), (6, 2.8)):
        dest = ROOT / f'hybrid_still_s{cut}.jpg'
        render_frame(int(t * FPS), cut).save(dest, quality=90)
        print('still:', dest)


def cmd_render():
    OUT.mkdir(parents=True, exist_ok=True)
    for cut in range(2, 7):
        out = OUT / f's{cut}.mp4'
        ep.encode_video_only(lambda n, c=cut: render_frame(n, c), N_CUT, out,
                             on_progress=lambda p, c=cut: print(f'  s{c} {p * 100:5.1f}%', flush=True))
        print('scene:', out)


def build_hybrid_sfx(path):
    tr = Track(T * 6 + 0.5, seed=31)
    for c in range(1, 6):
        tr.shutter(c * T, gain=0.45)
    tr.pop(0.03, 150, 62, 0.34, gain=0.16)
    tr.whoosh(0.15, 1.50, 0.09, 150, 1500, 0.32)
    tr.blip(1.26, 76, 0.20, gain=0.10)
    tr.blip(1.70, 84, 0.34, gain=0.125)
    tr.ting(1.74, gain=0.05)
    b = T
    tr.whoosh(b + 0.2, 1.1, 0.06, 200, 900, 0.35)
    tr.pop(b + 1.05, 900, 520, 0.07, gain=0.07)
    tr.pop(b + 1.35, 900, 520, 0.07, gain=0.07)
    tr.blip(b + 2.0, 81, 0.25, gain=0.11)
    tr.ting(b + 2.05, gain=0.05)
    b = 2 * T
    tr.whoosh(b + 0.2, 0.9, 0.05, 220, 800, 0.4)
    tr.pop(b + 1.2, 950, 560, 0.07, gain=0.08)
    tr.whoosh(b + 4.4, 0.4, 0.05, 700, 220, 0.3)
    b = 3 * T
    tr.whoosh(b + 0.2, 1.0, 0.05, 240, 1100, 0.4)
    tr.chime(b + 1.4, (84, 88), step=0.06, gain=0.12)
    tr.ting(b + 1.45, gain=0.04)
    b = 4 * T
    tr.whoosh(b + 0.2, 0.9, 0.05, 220, 900, 0.4)
    tr.pop(b + 1.3, 1000, 600, 0.07, gain=0.08)
    tr.pop(b + 1.6, 1000, 600, 0.07, gain=0.08)
    b = 5 * T
    tr.riser(b + 0.4, b + 1.1, ep.out_cubic, gain=0.055)
    tr.blip(b + 1.15, 84, 0.35, gain=0.13)
    tr.ting(b + 1.2, gain=0.05)
    tr.pop(b + 1.8, 1100, 650, 0.07, gain=0.08)
    tr.chime(28.7, (72, 76, 79, 84), step=0.08, gain=0.11)
    return tr.save(path)


def cmd_assemble():
    if not CUT01.exists():
        raise SystemExit('cut01 hybrid render missing: ' + str(CUT01))
    sfx = ROOT / '08_rainbow_hybrid_sfx.wav'
    build_hybrid_sfx(sfx)
    lst = ROOT / 'scenes_hybrid.txt'
    parts = [CUT01] + [OUT / f's{i}.mp4' for i in range(2, 7)]
    lst.write_text('\n'.join("file '" + str(p).replace('\\', '/') + "'" for p in parts), encoding='utf-8')
    final = ROOT / '08_rainbow_hybrid_v1.mp4'
    music = series_path('music-beds', 'es-bed-02.flac')
    filt = ('[1:a]volume=1.0[sfx];[2:a]atrim=0:30,afade=t=in:st=0:d=1.5,afade=t=out:st=28.2:d=1.8,'
            'volume=0.45[mus];[sfx][mus]amix=inputs=2:duration=longest:normalize=0,volume=5.5dB,' + ep.AUDIO_TAIL + '[a]')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(lst),
                    '-i', str(sfx), '-i', music, '-filter_complex', filt, '-map', '0:v',
                    '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', '30',
                    str(final)], check=True)
    print('final:', final)
    contact = ROOT / '08_rainbow_hybrid_v1_contact.jpg'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(final), '-vf',
                    'fps=1,scale=320:-1,tile=6x5', '-frames:v', '1', '-q:v', '4', str(contact)],
                   check=True)
    for i, t in enumerate((2.6, 7.6, 12.0, 17.2, 22.4, 27.4)):
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t), '-i', str(final),
                        '-frames:v', '1', '-q:v', '3', str(ROOT / f'hybrid_final_s{i + 1}.jpg')],
                       check=True)
    print('contact:', contact)
    subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration,size',
                    '-show_entries', 'stream=codec_name,width,height,r_frame_rate', '-of',
                    'default=noprint_wrappers=1', str(final)])
    subprocess.run(['ffmpeg', '-i', str(final), '-af', 'volumedetect', '-f', 'null', '-'],
                   capture_output=True, text=True)


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
