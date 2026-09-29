"""발광다이오두 쇼츠 (9:16, 30fps). Lab 일회성 렌더. lab venv(PIL, numpy, scipy)로 실행.

python render.py            -> final.mp4
python render.py stills 1 3 -> review/still_*.jpg
"""
import math
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

from motionkit import AUDIO_TAIL, Kit, encode, io_, lerp, out_back, out_cubic, prog  # noqa: E402
from sfx import Track  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(os.environ.get("MODAL_GUI_DATA_ROOT", ROOT / "data")) / "lab" / "2026-09-28-balgwang-diodu"
sys.path.insert(0, str(ROOT / "pipelines" / "_shared"))
K = Kit(palette='neon')
W, H, FPS = K.W, K.H, K.FPS
T = 26.5
OUTRO_T, FADE_T = 23.2, 25.0   # slow push-in hold, then fade to black
N = int(T * FPS)
GREEN, HI, INK, PAPER, VIO = K.A, K.HI, K.INK, K.PAPER, K.B


# ---------- assets ----------
def load_sticker(name, height, max_w=980):
    im = Image.open(WORK / 'stickers' / f'{name}.png').convert('RGBA')
    s = min(height / im.height, max_w / im.width)
    return im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)


ST_P4 = load_sticker('p4', 860)
ST_P0 = load_sticker('p0', 640, 560)
ST_P2 = load_sticker('p2', 640, 560)
ST_FZ = load_sticker('freeze', 1000, 1000)


def glow_of(st, color, blur=70):
    pad = blur * 3
    base = Image.new('L', (st.width + pad * 2, st.height + pad * 2), 0)
    base.paste(st.getchannel('A'), (pad, pad))
    a = base.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: min(255, int(v * 1.4)))
    g = Image.new('RGBA', base.size, color + (0,))
    g.putalpha(a)
    return g


def crown(w=300):
    """LED crown that caps the flat head cut of the freeze sticker."""
    h = int(w * 0.62)
    im = Image.new('RGBA', (w + 24, h + 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    o = 12
    pts = [(o, o + h), (o, o + h * 0.3), (o + w * 0.25, o + h * 0.62), (o + w * 0.5, o),
           (o + w * 0.75, o + h * 0.62), (o + w, o + h * 0.3), (o + w, o + h)]
    d.polygon(pts, fill=HI + (255,), outline=INK + (255,), width=10)
    for x, y in ((o, o + h * 0.3), (o + w * 0.5, o), (o + w, o + h * 0.3)):
        d.ellipse((x - 20, y - 20, x + 20, y + 20), fill=GREEN + (255,), outline=INK + (255,), width=6)
    for k in range(5):
        x = o + w * (0.14 + 0.18 * k)
        d.ellipse((x - 11, o + h * 0.78 - 11, x + 11, o + h * 0.78 + 11), fill=PAPER + (255,))
    return im


GLOW_FZ = glow_of(ST_FZ, HI)


def sticker_fz(img, cx, cy, sc):
    K.paste(img, ST_FZ, cx, cy, sc)


# tantrum montage: (sticker, cx, cy, rot, label, max_h, max_w)
MONT = [('tt_322', 290, 720, -8, '버럭', 560, 560), ('tt_395', 790, 760, 7, '억울', 460, 600),
        ('tt_17', 270, 1260, 6, '항의', 540, 480), ('tt_441', 800, 1280, -6, '씩씩', 540, 520),
        ('tt_30', 560, 1010, -3, '또 항의', 560, 520), ('tt_434', 540, 1180, 2, '끝까지 항의', 700, 640)]
MONT_ST = [(load_sticker(n, mh, mw), cx, cy, r, lab) for n, cx, cy, r, lab, mh, mw in MONT
           if (WORK / 'stickers' / f'{n}.png').exists()]
# Nations League 2026 vs Wales (SPOTIME upload 2026-09-25): miss, then the arm goes up
UW, UH = 900, 400
_n2 = UW * UH * 3
_raw2 = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '76.9', '-t', '2.4', '-i', str(WORK / 'sources/yt_LQIcAaNSxuM.mp4'),
                        '-vf', f'crop=iw:ih*0.74:0:ih*0.06,scale={UW}:{UH},fps={FPS}', '-f', 'rawvideo',
                        '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
UNL = [Image.frombytes('RGB', (UW, UH), _raw2[i:i + _n2]) for i in range(0, len(_raw2) - _n2 + 1, _n2)]

# LED dot-matrix background
BG = Image.new('RGB', (W, H), INK)
_d = ImageDraw.Draw(BG)
for y in range(12, H, 28):
    for x in range(12, W, 28):
        _d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(24, 44, 30))

# match clip card (Ronaldo-only edit of Dinamo Zagreb 0-1 Real Madrid, 2011-09-14)
CW, CH = 1000, 562
CLIP_T0, FREEZE_T = 5.4, 10.9
_n = CW * CH * 3


def _decode(start, dur):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(start), '-t', str(dur), '-i',
                          str(WORK / 'sources/yt_Y_pnx65jAOA.mp4'), '-vf', f'scale={CW}:{CH},fps={FPS}', '-f',
                          'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    return [Image.frombytes('RGB', (CW, CH), raw[i:i + _n]) for i in range(0, len(raw) - _n + 1, _n)]


# wide play (3.5–7.0 s) then the close-up (0–2.0 s) that ends on the freeze frame: whole head in frame
_close = 2.0
CLIP = _decode(3.5, FREEZE_T - CLIP_T0 - _close) + _decode(0.0, _close)
FREEZE = Image.open(WORK / 'frames/freeze.png').convert('RGB').resize((CW, CH), Image.LANCZOS)

# sunburst rays
RAYS = Image.new('RGBA', (2300, 2300), (0, 0, 0, 0))
_d = ImageDraw.Draw(RAYS)
for k in range(18):
    c = 1150
    pts = [(c, c)] + [(c + 1300 * math.cos(math.radians(a)), c + 1300 * math.sin(math.radians(a)))
                      for a in (k * 20, k * 20 + 9)]
    _d.polygon(pts, fill=HI + (70,) if k % 2 else GREEN + (55,))
RAYS = RAYS.filter(ImageFilter.GaussianBlur(6))


def F_HEAD(s): return K.F(K.HEAD, s)
def F_PB(s): return K.F(K.PB, s)
def F_GM(s): return K.F(K.GM, s)
def F_PSB(s): return K.F(K.PSB, s)


def card(img, pic, cx, cy, scale=1.0, dark=0.0):
    if scale <= 0.02:
        return
    fr = Image.new('RGB', (CW + 24, CH + 24), PAPER)
    fr.paste(pic, (12, 12))
    if dark:
        fr = ImageEnhance.Brightness(fr).enhance(1 - dark)
    K.paste(img, fr.convert('RGBA'), cx, cy, scale)


# ---------- scenes ----------
def s1(img, t):
    k = out_back(prog(t, 0.3, 0.8))
    if k > 0:
        K.paste(img, ST_P4, W / 2, 1300 + (1 - k) * 300, 0.4 + 0.6 * k)
    K.pill(img, W / 2, 340, 'TOP SECRET', F_GM(48), INK, HI, scale=out_back(prog(t, 0.0, 0.35)))
    K.text(img, (W / 2, 520), '우리형의 비밀', F_HEAD(150), PAPER, scale=out_back(prog(t, 0.1, 0.5)), stroke=10)
    K.text(img, (W / 2, 670), '사실 별명이 하나 더 있다?', F_PB(62), GREEN, alpha=prog(t, 0.5, 0.8), stroke=6)
    for i, (x, y, t0) in enumerate(((190, 1000, 1.0), (890, 1080, 1.3), (230, 1500, 1.6))):
        K.text(img, (x, y), '?', F_HEAD(190), HI, scale=out_back(prog(t, t0, t0 + 0.3)),
               rotate=math.sin((t - t0) * 9 + i) * 10, stroke=8)


def s2(img, t):
    K.text(img, (W / 2, 330), '알려진 별명들', F_HEAD(96), PAPER, scale=out_back(prog(t, 0.0, 0.3)), stroke=8)
    ka, kb = out_cubic(prog(t, 0.1, 0.5)), out_cubic(prog(t, 0.3, 0.7))
    K.paste(img, ST_P0, lerp(-400, 320, ka), 1220, 1.0, rot=-6)
    K.paste(img, ST_P2, lerp(W + 400, 770, kb), 1300, 1.0, rot=6)
    for s, y, t0, col in (('우리형', 520, 0.3, GREEN), ('날강두', 650, 0.9, VIO), ('CR7', 780, 1.5, GREEN)):
        K.pill(img, W / 2, y, s, F_HEAD(72), INK if col == GREEN else PAPER, col,
               scale=out_back(prog(t, t0, t0 + 0.25)))
    k = out_back(prog(t, 2.1, 2.4))
    if k > 0:
        K.pill(img, W / 2, 1720, '근데 진짜는 따로 있다', F_PB(58), INK, HI, scale=k)


BOOS = [(170, 560, -12, 6.6), (910, 590, 10, 7.0), (150, 1340, 8, 7.4), (930, 1370, -9, 7.8),
        (520, 1450, 4, 8.2), (330, 540, 6, 8.6), (760, 1470, -5, 9.0)]


def s3(img, t):
    """Absolute t in [CLIP_T0, FREEZE_T)."""
    K.text(img, (W / 2, 300), '2011.09.14', F_GM(76), HI, alpha=prog(t, CLIP_T0, CLIP_T0 + 0.3), stroke=6)
    K.text(img, (W / 2, 400), '디나모 자그레브 원정', F_PB(62), PAPER,
           alpha=prog(t, CLIP_T0 + 0.1, CLIP_T0 + 0.4), stroke=6)
    pic = CLIP[min(len(CLIP) - 1, int((t - CLIP_T0) * FPS))]
    card(img, pic, W / 2, 960, out_back(prog(t, CLIP_T0, CLIP_T0 + 0.35)))
    for x, y, rot, t0 in BOOS:
        if t >= t0:
            K.text(img, (x, y + math.sin((t - t0) * 7) * 8), '우~', F_HEAD(96), VIO,
                   scale=out_back(prog(t, t0, t0 + 0.2)), rotate=rot, stroke=8, stroke_fill=PAPER)
    if t >= CLIP_T0 + 1.0:
        K.pill(img, W / 2, 1640, '경기 내내 야유 세례', F_PB(58), PAPER, VIO,
               scale=out_back(prog(t, CLIP_T0 + 1.0, CLIP_T0 + 1.3)))


BUBBLE = ['내가 부자고, 잘생기고,', '훌륭한 선수라서', '다들 질투하는 거야']


def s4(img, t):
    """Freeze → sticker pops out of the frame → quote bubble."""
    lt = t - FREEZE_T
    kc = prog(lt, 0.3, 0.7)
    card(img, FREEZE, W / 2, 960, 1.0 + 0.08 * kc, dark=0.75 * kc)
    if lt < 0.9:
        K.text(img, (W / 2, 1720), '찰칵', F_HEAD(110), HI, scale=out_back(prog(lt, 0.0, 0.2)),
               alpha=1 - prog(lt, 0.6, 0.9), stroke=8)
    k = out_back(prog(lt, 0.3, 0.75))
    if k > 0:
        K.paste(img, ST_FZ, W / 2, lerp(960, 1230, k), lerp(0.55, 1.0, k))
    kb = out_back(prog(lt, 0.8, 1.1))
    if kb > 0:
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dd = ImageDraw.Draw(layer)
        bw, bh, cx, cy = 900 * kb, 330 * kb, W / 2, 400
        dd.polygon([(cx + 40 * kb, cy + bh / 2 - 8), (cx + 150 * kb, cy + bh / 2 - 8),
                    (cx + 70 * kb, cy + bh / 2 + 100 * kb)], fill=PAPER + (255,), outline=INK + (255,), width=8)
        dd.rounded_rectangle((cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2), 60 * kb, fill=PAPER + (255,),
                             outline=INK + (255,), width=8)
        dd.rectangle((cx + 48 * kb, cy + bh / 2 - 12, cx + 142 * kb, cy + bh / 2 - 2), fill=PAPER + (255,))
        img.paste(layer, (0, 0), layer)
        for j, line in enumerate(BUBBLE):
            a = prog(lt, 1.1 + j * 0.45, 1.3 + j * 0.45)
            K.text(img, (W / 2, 310 + j * 92), line, F_PB(62), INK if j < 2 else (200, 30, 60), alpha=a,
                   scale=0.9 + 0.1 * out_back(a))
    K.text(img, (W / 2, 1830), '2011년 9월 경기 후 실제 발언 (BBC·가디언 보도)', F_PSB(34), PAPER,
           alpha=0.75 * prog(lt, 1.2, 1.6))


GLOW_T, END_T = 14.6, 19.2   # GLOW_T now starts the tantrum montage
SLAM = END_T + 1.2
MONT_STEP, UNL_T = 0.42, 17.4


def rays(img, t, alpha):
    if alpha <= 0.01:
        return
    r = RAYS.rotate(t * 25, resample=Image.BILINEAR)
    if alpha < 1:
        r.putalpha(r.getchannel('A').point(lambda v: int(v * alpha)))
    img.paste(r, (int(W / 2 - 1150), int(1230 - 1150)), r)


def glow(img, y, sc, strength):
    g = GLOW_FZ.copy()
    g.putalpha(g.getchannel('A').point(lambda v: int(v * strength)))
    K.paste(img, g, W / 2, y, sc)


def s5(img, t):
    """'근데 평소 모습은' → tantrum stickers slap in one by one → this week's Nations League clip."""
    lt = t - GLOW_T
    K.text(img, (W / 2, 270), '근데 평소 모습은', F_HEAD(104), PAPER, scale=out_back(prog(lt, 0.0, 0.3)), stroke=9)
    dim = prog(t, UNL_T, UNL_T + 0.25)
    for i, (st, cx, cy, rot, lab) in enumerate(MONT_ST):
        t0 = GLOW_T + 0.35 + i * MONT_STEP
        k = out_back(prog(t, t0, t0 + 0.16), 2.6)
        if k <= 0:
            continue
        K.paste(img, st, cx, cy, lerp(1.5, 1.0, k) if k < 1 else 1.0, rot=rot)
        K.pill(img, cx, cy + st.height / 2 - 10, lab, F_HEAD(54), INK, HI if i % 2 == 0 else GREEN,
               pad=(28, 14), scale=out_back(prog(t, t0 + 0.08, t0 + 0.22)))
    if dim > 0:
        veil = Image.new('RGBA', (W, H), INK + (int(170 * dim),))
        img.paste(veil, (0, 0), veil)
        ku = out_back(prog(t, UNL_T, UNL_T + 0.3))
        i = min(len(UNL) - 1, max(0, int((t - UNL_T) * FPS)))
        fr = Image.new('RGB', (UW + 20, UH + 20), PAPER)
        fr.paste(UNL[i], (10, 10))
        K.paste(img, fr.convert('RGBA'), W / 2, 1000, ku, rot=-2)
        K.pill(img, W / 2, 720, '그리고 이번 주 네이션스리그', F_PB(54), INK, HI, scale=ku)
        K.text(img, (W / 2, 1300), '슛 빗나가자 또 버럭', F_HEAD(88), PAPER, alpha=prog(t, UNL_T + 0.5, UNL_T + 0.8),
               stroke=8)


WORD, TAIL_OLD, TAIL_NEW = '발광다이오', '드', '두'
F_WORD = K.fit_font(K.HEAD, 170, WORD + TAIL_OLD, W - 2 * K.SAFE + 60)


def word_width(s):
    b = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), s, font=F_WORD, anchor='lt')
    return b[2] - b[0]


WW, TW = word_width(WORD), word_width(TAIL_OLD)


def s6(img, t):
    lt = t - END_T
    km = io_(prog(lt, 0.0, 0.5))
    rays(img, t, 0.5 * km)
    y, sc = lerp(1230, 1380, km), lerp(1.0, 0.82, km)
    glow(img, y, sc, 0.85 * km)
    sticker_fz(img, W / 2, y + (1 - out_back(prog(lt, 0.0, 0.4))) * 700, sc)
    x0, cy = W / 2 - (WW + TW) / 2, 560
    on = t < SLAM or t > SLAM + 0.9 or int((t - SLAM) / 0.12) % 2 == 0
    col = GREEN if on else tuple(int(c * 0.4) for c in GREEN)
    a_word = prog(lt, 0.2, 0.5)
    K.text(img, (x0, cy), WORD, F_WORD, col, anchor='lm', alpha=a_word, stroke=9)
    kf = prog(t, SLAM - 0.35, SLAM)
    if t < SLAM - 0.35:
        K.text(img, (x0 + WW, cy), TAIL_OLD, F_WORD, col, anchor='lm', alpha=a_word, stroke=9)
    elif kf < 1:
        K.text(img, (x0 + WW + TW / 2 + 420 * kf, cy - 500 * kf + 1100 * kf * kf), TAIL_OLD, F_WORD, GREEN,
               rotate=-260 * kf, alpha=1 - kf, stroke=9)
    if t >= SLAM:
        ks = prog(t, SLAM, SLAM + 0.18)
        K.text(img, (x0 + WW + TW / 2, cy), TAIL_NEW, F_WORD, HI, scale=lerp(3.2, 1.0, out_cubic(ks)),
               alpha=min(1, ks * 3), stroke=9)
    K.text(img, (W / 2, 250), '그래서 붙은 별명', F_PB(64), PAPER, alpha=prog(lt, 0.1, 0.4), stroke=6)
    kj = out_back(prog(t, SLAM + 0.7, SLAM + 0.95), 2.4)
    if kj > 0:
        K.pill(img, W / 2, cy - 170, '지랄', F_HEAD(88), PAPER, (215, 40, 60), pad=(34, 12), scale=kj)
    K.text(img, (W / 2, 760), '빛나서 발광이 아니었다', F_PB(60), PAPER, alpha=prog(t, SLAM + 1.1, SLAM + 1.4), stroke=6)
    a = 0.7 * prog(t, SLAM + 0.5, SLAM + 0.9)
    K.text(img, (W / 2, 1790), '사진 Jan S0L0 · Wikimedia Commons (CC BY-SA 2.0)', F_PSB(28), PAPER, alpha=a)
    K.text(img, (W / 2, 1830), '경기 영상 YouTube · SPOTIME · 발언 BBC/The Guardian 2011.09.15', F_PSB(28), PAPER, alpha=a)
    K.text(img, (W / 2, 1870), '별명 유래 나무위키 · 재미로 보는 밈 영상', F_PSB(28), PAPER, alpha=a)


def frame(n):
    t = n / FPS
    img = BG.copy()
    if t < 2.6:
        s1(img, t)
    elif t < CLIP_T0:
        s2(img, t - 2.6)
    elif t < FREEZE_T:
        s3(img, t)
    elif t < GLOW_T:
        s4(img, t)
    elif t < END_T:
        s5(img, t)
    else:
        s6(img, t)
    if FREEZE_T <= t < FREEZE_T + 0.2:
        img = Image.blend(img, Image.new('RGB', (W, H), (255, 255, 255)), 0.85 * (1 - (t - FREEZE_T) / 0.2))
    if SLAM <= t < SLAM + 0.3:
        amp = 26 * (1 - (t - SLAM) / 0.3)
        img = ImageChops.offset(img, int(amp * math.sin(n * 2.1)), int(amp * math.cos(n * 1.7)))
    for tc in (2.6, CLIP_T0, GLOW_T, END_T):
        if tc <= t < tc + 0.12:
            img = K.punch(img, 1.06 - 0.5 * (t - tc))
    # natural ending: gentle push-in toward the word + sticker, then fade to black with the music
    if t >= OUTRO_T:
        img = K.zoom_at(img, 1.0 + 0.07 * io_(prog(t, OUTRO_T, T)), W / 2, 900)
    if t >= FADE_T:
        img = Image.blend(img, Image.new('RGB', (W, H), (0, 0, 0)), io_(prog(t, FADE_T, T - 0.15)))
    return img


# ---------- audio ----------
def build_sfx():
    tr = Track(T)
    tr.pop(0.05)
    tr.pop(0.15, 700, 250)
    tr.pop(0.35, 500, 200, gain=0.35)
    for t0 in (1.0, 1.3, 1.6):
        tr.pop(t0, 1300, 600, gain=0.25)
    for t0 in (2.6, CLIP_T0, GLOW_T, END_T):
        tr.whoosh(t0 - 0.12)
    for t0 in (2.9, 3.5, 4.1, 4.7):
        tr.pop(t0, 1000, 400, gain=0.3)
    for _, _, _, t0 in BOOS:
        tr.pop(t0, 300, 180, 0.12, gain=0.25)
    tr.shutter(FREEZE_T, 1.3)
    tr.pop(FREEZE_T + 0.35, 600, 200, gain=0.4)
    for j in range(3):
        tr.typewriter(FREEZE_T + 1.1 + j * 0.45, FREEZE_T + 1.35 + j * 0.45, 6)
    tr.riser(GLOW_T, END_T, io_, gain=0.05)
    for i in range(len(MONT_ST)):
        t0 = GLOW_T + 0.35 + i * MONT_STEP
        tr.pop(t0, 220, 70, 0.14, gain=0.7, decay=18)
        tr.shutter(t0, 0.5)
    tr.whoosh(UNL_T - 0.1)
    tr.pop(UNL_T + 0.05, 900, 300, gain=0.4)
    tr.whoosh(SLAM - 0.35, 0.35, 0.14, 1800, 300, tone=0.3)
    tr.pop(SLAM, 180, 60, 0.3, gain=0.8, decay=10)
    tr.ting(SLAM + 0.02, 0.25)
    for k in range(6):
        tr.blip(SLAM + 0.12 * k, 84 + (k % 2) * 7, gain=0.1)
    tr.pop(SLAM + 0.7, 1200, 300, 0.12, gain=0.6)
    tr.chime(OUTRO_T + 0.1, notes=(84, 88, 91, 96, 100), step=0.12, gain=0.12)
    return tr.save(WORK / 'sfx.wav')


MUSIC_OFF = 4.3  # the generated track is near-silent for its first ~4 s

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'stills':
        for t in [float(x) for x in sys.argv[2:]]:
            frame(int(t * FPS)).save(WORK / 'review' / f'still_{t:05.2f}.jpg', quality=88)
        sys.exit(0)
    sfx = build_sfx()
    fc = (f'[1:a]atrim={MUSIC_OFF}:{MUSIC_OFF + T},asetpts=PTS-STARTPTS,volume=0.55,'
          f'afade=t=out:st={OUTRO_T + 0.3}:d={T - OUTRO_T - 0.3}:curve=qsin[m];'
          f'[2:a]aformat=channel_layouts=stereo,aresample=48000[s];'
          f'[m][s]amix=inputs=2:normalize=0,{AUDIO_TAIL}[a]')
    out = WORK / 'final_v2.mp4'
    encode(frame, N, W, H, FPS, [WORK / 'music/audio.flac', sfx], fc, out, T,
           on_progress=lambda p: print(f'{p:.0%}', flush=True))
    print('done', out)
