"""심준영 freeze-frame character intro, 9:16 · 30fps · ~24s. Runs in the lab venv.

Each chapter: a real clip plays, snaps (flash + shutter), the background freezes to
desaturated dark, the baby pops out as a white die-cut sticker, and a name tag and a
caption-sourced trait slide in. Traits come only from 어서와 captions (steps/brief.md).
"""
import io
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from rembg import new_session, remove

sys.path.insert(0, str(Path(__file__).parent))
from sticker import clean_alpha, make_sticker  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from lab_paths import font_path, lab_path, series_path

WORK = lab_path('2026-09-28-junyoung-intro')
W, H, FPS = 1080, 1920, 30
MUSIC = series_path('music-beds', 'es-bed-02.flac')
OUT = WORK / 'junyoung-intro-v1.mp4'

# 어서와 design tokens
TERRA = (198, 91, 67)
APRICOT = (255, 227, 209)
COCOA = (46, 36, 32)
CREAM = (255, 248, 242)
WHITE = (255, 255, 255)

HEAD = str(font_path('BlackHanSans-Regular.ttf'))
GM = str(font_path('GmarketSansTTFBold.ttf'))
PB = str(font_path('Pretendard-Black.ttf'))
PSB = str(font_path('Pretendard-SemiBold.ttf'))
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


# (media index, freeze second, label, title, trait) — traits from captions only.
CHAPTERS = [
    (4, 16.2, '태명 심쿵이', '심준영', '2026. 08. 20 · 38주 · 탄생'),
    (47, 30.6, 'No.01', '잠꾸러기', '잘 먹고 잘 자요'),
    (83, 49.5, 'No.02', '분유 먹방러', '다 먹으면 취해요'),
    (171, 12.8, 'No.03', '눈빛 장인', '째려보고 · 땡글 · 똘망똘망'),
    (157, 3.3, 'No.04', '쑥쑥 성장 중', '3.55kg → 4.4kg'),
    (167, 9.8, 'No.05', '방구 트름 장인', '소리가 점점 커져요'),
]
TILTS = [-4, 3, -3, 4, -2, 3]
PLAY, HOLD = 1.1, 1.7
CH = PLAY + HOLD
INTRO = 1.6
PHOTO = 1.6
ENDCARD = 2.8
PHOTOS = [(182, '아빠와 아들'), (187, '할아버지 할머니와 30일 만의 상봉')]
T_PHOTOS = INTRO + len(CHAPTERS) * CH
T_END = T_PHOTOS + len(PHOTOS) * PHOTO
DUR = T_END + ENDCARD

ix = json.load(open(WORK / 'data' / 'media_index.json', encoding='utf-8'))


def first_frame_size(src, t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', str(src), '-frames:v', '1',
                          '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(raw)).size


def decode(src, start, dur):
    w, h = first_frame_size(src, start)
    if w / h < 0.75:
        args = ['-vf', f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}']
    else:
        args = ['-filter_complex',
                f'[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},'
                f'boxblur=40:2,eq=brightness=-0.08[bg];[b]scale={W}:-2[fg];'
                f'[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={FPS}']
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(start), '-t', str(dur), '-i', str(src), *args,
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    n = W * H * 3
    return [Image.frombytes('RGB', (W, H), raw[i:i + n]) for i in range(0, len(raw) - n + 1, n)]


def fit(im, bw, bh):
    """Scale up or down so the image fits inside bw x bh."""
    s = min(bw / im.width, bh / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def trim_bars(im, thresh=240):
    """Remove solid near-white letterbox bars baked into a photo."""
    a = np.asarray(im.convert('L'))
    rows = np.where(a.mean(axis=1) < thresh)[0]
    cols = np.where(a.mean(axis=0) < thresh)[0]
    if len(rows) and len(cols):
        im = im.crop((cols[0], rows[0], cols[-1] + 1, rows[-1] + 1))
    return im


def lift(im):
    """Brighten underexposed photos without clipping highlights."""
    mean = np.asarray(im.convert('L')).mean()
    if mean < 90:
        arr = np.asarray(im, np.float32) / 255.0
        gamma = math.log(0.42) / math.log(max(0.05, mean / 255.0))
        im = Image.fromarray((np.clip(arr ** gamma, 0, 1) * 255).astype(np.uint8))
    return im


SESSION = new_session('isnet-general-use')
PREP = []
for idx, freeze_t, *_ in CHAPTERS:
    src = WORK / 'sources' / ix[idx]['file']
    frames = decode(src, freeze_t - PLAY, PLAY + 0.2)[:int(PLAY * FPS)]
    still = frames[-1]
    alpha = clean_alpha(remove(still, session=SESSION, only_mask=True))
    sticker = fit(make_sticker(still, alpha, stroke=26), 840, 1060)
    gray = ImageOps.grayscale(still).convert('RGB')
    frozen = Image.blend(gray, Image.new('RGB', (W, H), COCOA), 0.5).filter(ImageFilter.GaussianBlur(4))
    PREP.append({'frames': frames, 'sticker': sticker, 'frozen': frozen})
    print('prepared', idx, flush=True)


def polaroid(idx):
    im = ImageOps.exif_transpose(Image.open(WORK / 'sources' / ix[idx]['file'])).convert('RGB')
    im = fit(lift(trim_bars(im)), 820, 900)
    b = 28
    card = Image.new('RGBA', (im.width + b * 2, im.height + b * 2), WHITE + (255,))
    card.paste(im, (b, b))
    return card


POLAROIDS = [polaroid(i) for i, _ in PHOTOS]


def zoom(img, z):
    if z <= 1.0001:
        return img
    w, h = int(W * z), int(H * z)
    big = img.resize((w, h), Image.BILINEAR)
    x, y = (w - W) // 2, (h - H) // 2
    return big.crop((x, y, x + W, y + H))


def text(img, xy, s, font, fill, anchor='mm', alpha=1.0):
    if alpha <= 0:
        return
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, s, font=font, fill=fill + (int(255 * alpha),), anchor=anchor)
    img.paste(layer, (0, 0), layer)


def pill(img, x, y, s, font, fg, bg, anchor='l', pad=(42, 22), alpha=1.0):
    """Draw a rounded tag; x is the left edge (anchor l) or centre (anchor m)."""
    if alpha <= 0:
        return
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    box = d.textbbox((0, 0), s, font=font, anchor='lt')
    tw, th = box[2] - box[0], box[3] - box[1]
    w, h = tw + pad[0] * 2, th + pad[1] * 2
    x0 = x if anchor == 'l' else x - w / 2
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    ld.rounded_rectangle((x0, y - h / 2, x0 + w, y + h / 2), h / 2, fill=bg + (a,))
    ld.text((x0 + pad[0] - box[0], y - th / 2 - box[1]), s, font=font, fill=fg + (a,))
    img.paste(layer, (0, 0), layer)


def paste_rgba(img, rgba, cx, cy, scale, rot):
    if scale <= 0.02:
        return
    im = rgba.resize((max(1, int(rgba.width * scale)), max(1, int(rgba.height * scale))), Image.BILINEAR)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    img.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


# ---------------- scenes ----------------

def intro(lt):
    img = Image.new('RGB', (W, H), CREAM)
    lines = [('우리 집에 온', F(PB, 84), COCOA, 700), ('심쿵이를', F(HEAD, 200), TERRA, 880),
             ('소개합니다', F(HEAD, 200), TERRA, 1100)]
    for k, (s, f, c, y) in enumerate(lines):
        a = prog(lt, 0.1 + k * 0.15, 0.4 + k * 0.15)
        text(img, (W / 2, y + 900 * (1 - out_back(a, 1.4))), s, f, c)
    r = lerp(0, 2300, io_(prog(lt, 1.25, 1.6)))
    if r > 0:
        ImageDraw.Draw(img).ellipse((W / 2 - r, 1100 - r, W / 2 + r, 1100 + r), fill=COCOA)
    return img


def chapter(i, lt):
    p = PREP[i]
    _, _, label, title, trait = CHAPTERS[i]
    if lt < PLAY:
        f = p['frames'][min(len(p['frames']) - 1, int(lt * FPS))]
        return zoom(f, 1 + 0.04 * lt / PLAY)
    k = lt - PLAY
    img = zoom(p['frozen'], 1.04 + 0.03 * k / HOLD).copy()
    s = out_back(prog(k, 0.03, 0.33), 2.2)
    rot = lerp(-12, TILTS[i], out_cubic(prog(k, 0.03, 0.4)))
    paste_rgba(img, p['sticker'], W / 2, 860, s, rot)
    slide = (1 - out_cubic(prog(k, 0.25, 0.55))) * -900
    pill(img, 80 + slide, 1470, label, F(GM, 40), COCOA, APRICOT)
    pill(img, 80 + slide * 1.2, 1590, title, F(HEAD, 96), WHITE, TERRA, pad=(48, 26))
    text(img, (96, 1730), trait, F(PSB, 50), WHITE, anchor='lm', alpha=out_cubic(prog(k, 0.45, 0.75)))
    text(img, (W - 70, 110), f'{i + 1:02d} / {len(CHAPTERS):02d}', F(GM, 38), APRICOT, anchor='rm')
    flash = [0.92, 0.55, 0.25][int(k * FPS)] if k * FPS < 3 else 0
    if flash:
        img = Image.blend(img, Image.new('RGB', (W, H), WHITE), flash)
    return img


def photo(i, lt):
    img = Image.new('RGB', (W, H), APRICOT)
    s = out_back(prog(lt, 0.0, 0.3), 2.0)
    rot = lerp(14, [-5, 4][i], out_cubic(prog(lt, 0, 0.4)))
    paste_rgba(img, POLAROIDS[i], W / 2, 830 + (1 - out_cubic(prog(lt, 0, 0.3))) * 200, s, rot)
    text(img, (W / 2, 1560), PHOTOS[i][1], F(PB, 66), COCOA, alpha=out_cubic(prog(lt, 0.3, 0.6)))
    return img


def endcard(lt):
    img = Image.new('RGB', (W, H), TERRA)
    text(img, (W / 2, 820 + 1000 * (1 - out_back(prog(lt, 0, 0.35), 1.4))), '심준영', F(HEAD, 250), WHITE)
    a = out_cubic(prog(lt, 0.4, 0.8))
    text(img, (W / 2, 1040), '2026.08.20 탄생 · 09.19 신생아 졸업', F(PSB, 44), APRICOT, alpha=a)
    text(img, (W / 2, 1180), '우리 집에 온 걸 환영해', F(PB, 72), WHITE, alpha=out_cubic(prog(lt, 0.7, 1.1)))
    return img


def render(t):
    if t < INTRO:
        return intro(t)
    if t < T_PHOTOS:
        i = int((t - INTRO) / CH)
        return chapter(i, t - INTRO - i * CH)
    if t < T_END:
        i = int((t - T_PHOTOS) / PHOTO)
        return photo(i, t - T_PHOTOS - i * PHOTO)
    return endcard(t - T_END)


def sfx_track(path):
    sr = 48000
    track = np.zeros(int(DUR * sr) + sr, np.float32)
    rng = np.random.default_rng(3)

    def burst(t, length, decay, gain):
        n = int(length * sr)
        env = np.exp(-np.linspace(0, 1, n) * decay)
        s = int(t * sr)
        track[s:s + n] += (rng.standard_normal(n) * env * gain).astype(np.float32)

    for i in range(len(CHAPTERS)):
        t = INTRO + i * CH + PLAY
        burst(t, 0.05, 30, 0.55)
        burst(t + 0.045, 0.08, 22, 0.35)
    for i in range(len(PHOTOS)):
        burst(T_PHOTOS + i * PHOTO, 0.05, 30, 0.3)
    pcm = (np.clip(track, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def main():
    sfx = WORK / 'sfx.wav'
    sfx_track(sfx)
    total = int(DUR * FPS)
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-i', str(MUSIC), '-i', str(sfx),
           '-filter_complex', AUDIO_FILTER,
           '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'medium',
           '-c:a', 'aac', '-b:a', '192k', '-t', str(DUR), str(OUT)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(total):
        proc.stdin.write(render(n / FPS).tobytes())
        if n % 90 == 0:
            print(f'{n}/{total}', flush=True)
    proc.stdin.close()
    proc.wait()
    print('done', OUT, round(DUR, 2), 's')


AUDIO_FILTER = (f'[1:a]atrim=0:{DUR},asetpts=N/SR/TB,loudnorm=I=-16:TP=-1.5:LRA=11,'
                f'afade=t=in:d=0.3,afade=t=out:st={DUR - 1.5}:d=1.5[m];'
                f'[m][2:a]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.9[a]')


def remux_audio():
    """Rebuild only the audio track of the rendered file (video stream copied)."""
    sfx = WORK / 'sfx.wav'
    sfx_track(sfx)
    tmp = OUT.with_name(OUT.stem + '.tmp.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(OUT), '-i', str(MUSIC), '-i', str(sfx),
                    '-filter_complex', AUDIO_FILTER, '-map', '0:v', '-map', '[a]', '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '192k', '-t', str(DUR), str(tmp)], check=True)
    tmp.replace(OUT)
    print('audio remuxed')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'audio':
        remux_audio()
    elif len(sys.argv) > 1 and sys.argv[1] == 'stills':
        times = [0.9, INTRO + 0.5]
        for i in range(len(CHAPTERS)):
            times.append(INTRO + i * CH + PLAY + 1.2)
        times += [T_PHOTOS + 1.0, T_PHOTOS + PHOTO + 1.0, T_END + 1.5]
        sheet = Image.new('RGB', (6 * 270, 2 * 480))
        for k, t in enumerate(times[:12]):
            sheet.paste(render(t).resize((270, 480)), ((k % 6) * 270, (k // 6) * 480))
        sheet.save(WORK / '_stills.jpg', quality=90)
        print('stills ok', round(DUR, 2))
    else:
        main()
