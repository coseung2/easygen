"""심준영 등장인물 소개 — fast, funny freeze-frame character intro. 9:16 · 30fps · 20s.

Each cast chapter: the real clip plays for two beats with a push-in, then on the downbeat it
'찰칵' freezes (flash + shutter), the frame drops to a brand-color duotone, the BRIA die-cut
sticker pops out with overshoot, and a variety-show name card slams in. Music is the bouncy
120 BPM bed, so every freeze lands on a beat. Copy is grounded in 어서와 captions.
"""
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).parent))
import render_launch as rl  # noqa: E402  shared drawing helpers, palette, fonts
from render_launch import (F, GM, HEAD, PB, PSB, GREEN, VIOLET, INK, PAPER, YELLOW,  # noqa: E402
                           W, H, FPS, prog, out_back, out_cubic, io_, lerp, canvas, draw_text, pill,
                           paste, zoom_at, sparkle, load_sticker)

WORK = rl.WORK
OUT = WORK / 'junyoung-freeze-v2.mp4'
MUSIC = WORK / 'music_freeze_chiptune_150.wav'
ix = rl.ix

# (media index, freeze second, role, gag line, color) — roles grounded in captions / visible frames
CAST = [
    (145, 15.0, '매서운 눈빛 담당', '"…뭘 봐?"', GREEN),          # 09-06 '주위를 째려보는 준영이'
    (168, 23.4, '하품 대마왕', '하아암~ 오늘도 피곤', VIOLET),     # visible yawn
    (91, 12.4, '분유 먹방러', '원샷 후 바로 취함', YELLOW),        # 08-30 '분유먹고 취한 준영씨'
    (169, 13.4, '표정 부자', '오늘의 표정: 새침', GREEN),         # visible expression
    (176, 10.8, '공부하는 준영쓰', '초점책 정독 중', VIOLET),      # 09-18 '공부하는 준영쓰'
]
BEAT = 0.4                    # 150 BPM chiptune
INTRO, CH, PLAY, OUTRO = 4 * BEAT, 8 * BEAT, 3 * BEAT, 8 * BEAT   # 1.6 / 3.2 / 1.2 / 3.2 s
DUR = INTRO + len(CAST) * CH + OUTRO
TILTS = [-5, 4, -4, 5, -3]


def decode(idx, start, dur):
    src = WORK / 'sources' / ix[idx]['file']
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(start), '-t', str(dur), '-i', str(src),
                          '-vf', f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    n = W * H * 3
    return [Image.frombytes('RGB', (W, H), raw[i:i + n]) for i in range(0, len(raw) - n + 1, n)]


def duotone(img, color):
    g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=2)
    return ImageOps.colorize(g, black=INK, white=color).convert('RGB')


PREP = []
for idx, t, *_ , col in CAST:
    frames = decode(idx, t - PLAY, PLAY + 0.1)[:int(PLAY * FPS)]
    still = Image.open(WORK / 'frames' / f'ff_{idx}.png').convert('RGB')
    still = ImageOps.fit(still, (W, H))
    PREP.append({'frames': frames, 'frozen': duotone(still, col), 'sticker': load_sticker(f'ff_{idx}', (900, 1000))})
    print('prepared', idx, flush=True)


def intro(lt):
    img = canvas(YELLOW)
    pill(img, W / 2, 560, 'CAST', F(GM, 60), PAPER, INK, scale=out_back(prog(lt, 0, 0.3), 2.4))
    for k, (s, y, c) in enumerate([('등장인물', 820, INK), ('소개', 1080, VIOLET)]):
        p = prog(lt, 0.12 + k * 0.1, 0.45 + k * 0.1)
        draw_text(img, (W / 2, y + 1100 * (1 - out_back(p, 1.4))), s, F(HEAD, 280), c)
    draw_text(img, (W / 2, 1330), '우리 집 신입 · 심준영 편', F(PB, 60), INK, alpha=out_cubic(prog(lt, 0.6, 0.9)))
    r = lerp(0, 2300, io_(prog(lt, INTRO - 0.35, INTRO)))
    if r > 0:
        ImageDraw.Draw(img).ellipse((W / 2 - r, 560 - r, W / 2 + r, 560 + r), fill=INK)
    return img


def chapter(i, lt):
    p = PREP[i]
    _, _, role, gag, col = CAST[i]
    pill_bg = INK if col == YELLOW else col
    pill_fg = PAPER if pill_bg in (VIOLET, INK) else INK
    if lt < PLAY:
        f = p['frames'][min(len(p['frames']) - 1, int(lt * FPS))]
        img = zoom_at(f, 1 + 0.07 * io_(lt / PLAY), W / 2, H * 0.42)
        pill(img, W - rl.SAFE - 110, rl.SAFE + 40, f'CAST 0{i + 1}', F(GM, 38), PAPER, INK,
             alpha=out_cubic(prog(lt, 0, 0.2)))
        return img
    k = lt - PLAY
    img = zoom_at(p['frozen'], lerp(1.12, 1.04, out_cubic(prog(k, 0, 0.35))), W / 2, H * 0.42).copy()
    d = ImageDraw.Draw(img)
    # speed lines behind the sticker for the first half beat
    if k < 0.5:
        a = 1 - k / 0.5
        for n in range(22):
            ang = n / 22 * 6.283
            r0, r1 = 560, 1500
            c = tuple(int(lerp(ch, 255, 0.35)) for ch in col)
            d.line((W / 2 + np.cos(ang) * r0, 820 + np.sin(ang) * r0 * 1.2,
                    W / 2 + np.cos(ang) * r1, 820 + np.sin(ang) * r1 * 1.2), fill=c, width=int(10 * a) + 1)
    s = out_back(prog(k, 0.03, 0.3), 2.4)
    paste(img, p['sticker'], W / 2, 820, scale=s, rot=lerp(-14, TILTS[i], out_cubic(prog(k, 0.03, 0.4))))
    for n, (sx, sy) in enumerate([(-360, -420), (380, -330), (-330, 380)]):
        tw = abs(np.sin(lt * 8 + n * 2))
        sparkle(d, W / 2 + sx, 820 + sy, 42 * tw * out_cubic(prog(k, 0.2, 0.4)), YELLOW if col != YELLOW else PAPER)
    # name card: label slides from the left, role slams in, gag line types after
    slide = (1 - out_cubic(prog(k, 0.22, 0.45))) * -1000
    pill(img, rl.SAFE + 170 + slide, 1440, '심준영 (0세)', F(PB, 48), pill_fg, pill_bg)
    draw_text(img, (W / 2, 1600), role, F(HEAD, 128), YELLOW if col != YELLOW else PAPER, stroke=12,
              stroke_fill=INK, scale=out_back(prog(k, 0.32, 0.52), 1.7))
    n_chars = int(len(gag) * prog(k, 0.55, 1.0))
    draw_text(img, (W / 2, 1780), gag[:n_chars] if n_chars else ' ', F(PB, 64), PAPER, stroke=6, stroke_fill=INK)
    pill(img, W - rl.SAFE - 110, rl.SAFE + 40, f'CAST 0{i + 1}', F(GM, 38), PAPER, INK)
    flash = [0.95, 0.6, 0.25][int(k * FPS)] if k * FPS < 3 else 0
    if flash:
        img = Image.blend(img, canvas(PAPER), flash)
    return img


def outro(lt):
    img = canvas(INK)
    for n, p in enumerate(PREP):
        a = out_back(prog(lt, 0.05 + n * 0.08, 0.35 + n * 0.08), 2.2)
        st = p['sticker']
        paste(img, st, [210, 540, 870, 330, 750][n], [470, 400, 470, 900, 900][n], scale=0.36 * a, rot=TILTS[n] * 2)
    draw_text(img, (W / 2, 1330 + 900 * (1 - out_back(prog(lt, 0.4, 0.75), 1.4))), '심준영', F(HEAD, 250), GREEN)
    draw_text(img, (W / 2, 1530), '1인 5역 소화 중', F(HEAD, 110), PAPER, alpha=out_cubic(prog(lt, 0.8, 1.1)))
    pill(img, W / 2, 1700, '우리 집 막내 · 2026.08.20 데뷔', F(PB, 44), INK, YELLOW, alpha=out_cubic(prog(lt, 1.0, 1.3)))
    r = lerp(0, 2300, io_(prog(lt, OUTRO - 0.4, OUTRO)))
    if r > 0:
        ImageDraw.Draw(img).ellipse((W / 2 - r, 560 - r, W / 2 + r, 560 + r), fill=YELLOW)
    return img


def render(t):
    if t < INTRO:
        return intro(t)
    if t < INTRO + len(CAST) * CH:
        i = int((t - INTRO) / CH)
        lt = t - INTRO - i * CH
        img = chapter(i, lt)
        if lt < 2 / FPS:
            img = zoom_at(img, 1.05, W / 2, H / 2)
        return img
    return outro(t - INTRO - len(CAST) * CH)


def sfx(path):
    sr = 48000
    tr = np.zeros(int((DUR + 1) * sr), np.float32)
    rng = np.random.default_rng(9)

    def put(t, sig):
        s = int(t * sr)
        tr[s:s + len(sig)] += sig[:max(0, len(tr) - s)].astype(np.float32)

    def shutter(t):
        for off, dec, g in ((0, 34, 0.5), (0.05, 24, 0.32)):
            n = int(0.07 * sr)
            noise = rng.standard_normal(n)
            put(t + off, (noise - np.convolve(noise, np.ones(5) / 5, 'same')) * np.exp(-np.arange(n) / sr * dec) * g)

    def pop(t, f0, f1, length=0.12, g=0.28):
        n = int(length * sr)
        tt = np.arange(n) / sr
        put(t, np.sin(2 * np.pi * np.cumsum(np.linspace(f0, f1, n)) / sr) * np.exp(-tt * 22) * g)

    def whoosh(t, length=0.28, g=0.12):
        n = int(length * sr)
        noise = np.convolve(rng.standard_normal(n), np.ones(8) / 8, 'same')
        put(t, noise * np.sin(np.pi * np.arange(n) / n) ** 2 * g)

    for i in range(len(CAST)):
        t0 = INTRO + i * CH + PLAY
        shutter(t0)
        pop(t0 + 0.09, 420, 1500, 0.14, 0.26)     # sticker 'boing'
        whoosh(t0 + 0.2)                           # name card slide
        pop(t0 + 0.33, 1300, 500, 0.1, 0.2)        # role slam
        for c in range(len(CAST[i][3])):           # typewriter ticks
            pop(t0 + 0.55 + c * 0.45 / max(1, len(CAST[i][3])), 2400, 2200, 0.02, 0.05)
    for n in range(5):
        pop(DUR - OUTRO + 0.05 + n * 0.08, 600 + n * 120, 1400 + n * 120, 0.1, 0.18)
    pcm = (np.clip(tr, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def main():
    import music_chiptune
    end = INTRO + len(CAST) * CH
    freezes = [INTRO + i * CH + PLAY for i in range(len(CAST))]
    music_chiptune.build(MUSIC, DUR, beat=BEAT, intro=INTRO, freezes=freezes, end=end, coin=end + 1.8)
    fx = WORK / 'sfx_freeze.wav'
    sfx(fx)
    af = (f'[1:a]atrim=0:{DUR},asetpts=N/SR/TB,afade=t=out:st={DUR - 0.5}:d=0.5[m];'
          f'[m][2:a]amix=inputs=2:normalize=0:duration=first,'
          f'lowpass=f=11000,alimiter=limit=0.5:level=disabled,volume=2dB,'
          f'alimiter=limit=0.6:level=disabled[a]')
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-i', str(MUSIC), '-i', str(fx), '-filter_complex', af, '-map', '0:v', '-map', '[a]',
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium', '-c:a', 'aac', '-b:a', '192k',
           '-t', str(DUR), str(OUT)]
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
        f0 = [INTRO + i * CH + PLAY for i in range(len(CAST))]
        ts = [0.8, INTRO + 0.6, f0[0] + 0.05, f0[0] + 0.4, f0[0] + 1.6, f0[1] + 1.6, f0[2] + 1.6, f0[3] + 1.6,
              f0[4] + 1.6, DUR - OUTRO + 0.6, DUR - OUTRO + 1.6, DUR - 0.1]
        sheet = Image.new('RGB', (6 * 300, 2 * 533))
        for k, t in enumerate(ts):
            sheet.paste(render(t).resize((300, 533)), ((k % 6) * 300, (k // 6) * 533))
        sheet.save(WORK / '_freeze_stills.jpg', quality=88)
        print('stills ok')
    else:
        main()
