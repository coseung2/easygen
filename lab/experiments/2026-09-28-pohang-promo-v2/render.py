"""포항 지도 여행 숏폼 (9:16, 30초, 30fps) — 1단계 로컬 편집. 개인 테스트용.

훅(포항 하면 철?) → 삽화 지도 위 자동차 이동 → 핀 도착 · 미리보기 카드 → 확대 · 실사 → 지도로 복귀 × 6 → 엔딩.

python render.py              -> out/pohang-map-journey_v1.mp4
python render.py still 1 5.5  -> out/still_*.png
"""
import math
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from route import KINETIC, ROAD, STOPS
import timeline as TL

W, H, FPS, DUR = 1080, 1920, TL.FPS, TL.DUR
HERE = Path(__file__).parent
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = HERE / "out"
CLIPS = HERE / "clips"
SRC = Path(os.environ.get("MODAL_GUI_DATA_ROOT", ROOT / "data")) / "references" / "pohang-yt-test"
MUSIC = HERE / "music" / "bgm-02.wav"
FD = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts"
BOLD, MED = FD / "GmarketSansTTFBold.ttf", FD / "Pretendard-SemiBold.ttf"
LATIN = FD / "Montserrat-Black.otf"

ORANGE, NAVY, CREAM, WHITE = (255, 122, 61), (11, 42, 74), (255, 246, 230), (255, 255, 255)

# 원본별 사전 자르기 (x, y, w, h). 검은 띠·아래 자막 띠를 먼저 잘라낸 뒤 9:16으로 자른다.
PRE = {
    "R--qtc49Lco": (0, 62, 1920, 762),   # 곤륜산: 위아래 검은 띠 제거 (cropdetect)
    "RBhsrBwPheQ": (0, 0, 1920, 900),    # 호미곶: 아래 자막 띠(y 920–975) 제거
    "1m0WTsT_pLc": (0, 0, 1920, 900),    # 영일대 야경: 아래 설명 자막 띠 제거
}
# 9:16으로 자를 가로 중심 (사전 자르기 후 픽셀). 없으면 가운데.
CROP_X = {"RBhsrBwPheQ": 890, "1m0WTsT_pLc": 700}
CLIP_LEN = 3.4
# 실사 드론샷 카메라 무브. 여유 있게 크게(오버스캔) 뽑아 두고 그 안에서 밀고, 흐르고, 살짝 기울인다.
# (시작 확대, 끝 확대, 가로 이동 px, 세로 이동 px, 시작 회전°, 끝 회전°) — 출력 해상도 기준
OVERSCAN = 1.3
DRONE = {
    "VDPTjuLMO8A": (1.00, 1.18, 0, -60, 0.0, 2.5),     # 이가리: 부감에서 내려앉으며 천천히 회전
    "R--qtc49Lco": (1.12, 1.00, -90, 0, -1.5, 0.0),    # 곤륜산: 풀백하며 옆으로 흐름 (전망이 열림)
    "UAhCX7F6q_8": (1.00, 1.15, 70, -40, 1.0, -1.0),   # 스페이스워크: 트랙을 따라 올라가는 느낌
    "1m0WTsT_pLc": (1.00, 1.14, -70, 0, 0.0, 0.0),     # 영일대: 누각 쪽으로 옆 이동하며 밀기
    "RBhsrBwPheQ": (1.16, 1.02, 0, 50, 0.0, 0.0),      # 호미곶: 손과 해에서 풀백 (규모가 보임)
    "JqVi2vfNaWw": (1.00, 1.12, 60, 0, -1.0, 1.0),     # 구룡포: 골목을 따라 흐르는 트래킹
}

HOOK_END, INTRO_END = TL.HOOK_END, TL.INTRO_END
STOP_LEN = TL.STOP_LEN
DRIVE, POP, ZOOM, LIVE, BACK = TL.DRIVE, TL.POP, TL.ZOOM, TL.LIVE, TL.BACK
END_START = TL.END_START
BEAT = TL.B
ZOOM_IN = 1.7

_f = {}


def F(p, n):
    if (p, n) not in _f:
        _f[(p, n)] = ImageFont.truetype(str(p), n)
    return _f[(p, n)]


def clamp01(x):
    return max(0.0, min(1.0, x))


def seg(t, a, b):
    return clamp01((t - a) / (b - a))


def ease(p):
    return p * p * (3 - 2 * p)


def ease_out(p):
    return 1 - (1 - p) ** 3


def back(p, k=1.7):
    p -= 1
    return 1 + (k + 1) * p ** 3 + k * p ** 2


def lerp(a, b, p):
    return a + (b - a) * p


# ------------------------------------------------------------------ 소재 준비
def prepare_clips():
    CLIPS.mkdir(exist_ok=True)
    for *_, vid, start in STOPS:
        d = CLIPS / vid
        if d.exists() and len(list(d.glob("*.jpg"))) >= int(CLIP_LEN * FPS):
            continue
        d.mkdir(exist_ok=True)
        src = SRC / f"{vid}.mp4"
        pre = PRE.get(vid)
        pre_vf = f"crop={pre[2]}:{pre[3]}:{pre[0]}:{pre[1]}," if pre else ""
        cx = CROP_X.get(vid)
        x = f"{cx}-ih*9/32" if cx else "(iw-ih*9/16)/2"
        ow, oh = int(W * OVERSCAN) // 2 * 2, int(H * OVERSCAN) // 2 * 2
        vf = f"{pre_vf}crop=ih*9/16:ih:{x}:0,scale={ow}:{oh}:flags=lanczos,fps={FPS}"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-t", str(CLIP_LEN),
                        "-i", str(src), "-vf", vf, "-q:v", "3", str(d / "%03d.jpg")], check=True)


_clip_cache = {}


def _raw_frame(vid, t):
    n = len(list((CLIPS / vid).glob("*.jpg"))) if vid not in _clip_cache else _clip_cache[vid][0]
    i = max(1, min(n, int(t * FPS) + 1))
    if vid not in _clip_cache or _clip_cache[vid][1] != i:
        _clip_cache[vid] = (n, i, Image.open(CLIPS / vid / f"{i:03d}.jpg").convert("RGB"))
    return _clip_cache[vid][2]


def clip_frame(vid, t, dur=CLIP_LEN):
    """오버스캔 프레임에서 드론 무브를 적용해 W×H를 잘라낸다. 원래 영상의 움직임 위에 카메라가 한 겹 더 움직인다."""
    src = _raw_frame(vid, t)
    z0, z1, dx, dy, r0, r1 = DRONE.get(vid, (1.0, 1.08, 0, 0, 0.0, 0.0))
    p = ease(clamp01(t / dur))
    z, rot = lerp(z0, z1, p), lerp(r0, r1, p)
    # 흔들림 없이 부드러운 드론 느낌: 아주 작은 저주파 흔들림만 더한다
    wob_x = 4 * math.sin(t * 1.3 + len(vid))
    wob_y = 3 * math.sin(t * 0.9 + 2 * len(vid))
    sw, sh = src.size
    cx = sw / 2 + (p - 0.5) * dx * OVERSCAN + wob_x
    cy = sh / 2 + (p - 0.5) * dy * OVERSCAN + wob_y
    # 출력 1px = 오버스캔 이미지 1/z px. z=1이면 오버스캔 가운데 1/OVERSCAN 영역을 보여 주므로
    # 이동·회전할 여유가 사방에 남는다. 회전 각이 커지면 빈 모서리가 보이지 않게 z를 조금 올린다.
    ang = math.radians(rot)
    need = abs(math.cos(ang)) + abs(math.sin(ang)) * max(W / H, H / W) * 0.5
    z = max(z, need)
    k = 1 / z
    ca, sa = math.cos(ang) * k, math.sin(ang) * k
    # 출력 (X,Y) → 원본 (x,y): 중심 기준 회전·확대
    a, b = ca, -sa
    d_, e = sa, ca
    c = cx - a * W / 2 - b * H / 2
    f = cy - d_ * W / 2 - e * H / 2
    return src.transform((W, H), Image.AFFINE, (a, b, c, d_, e, f), Image.BICUBIC)


MAP = Image.open(HERE / "map" / "illustrated_v2.png").convert("RGB")
MW, MH = MAP.size
MAP2 = MAP.resize((MW * 2, MH * 2), Image.LANCZOS)
FIT = max(W / MW, H / MH)


# ------------------------------------------------------------------ 경로
def build_path():
    cum = [0.0]
    for a, b in zip(ROAD, ROAD[1:]):
        cum.append(cum[-1] + math.dist(a, b))
    return cum


CUM = build_path()


def at(s):
    s = max(0.0, min(CUM[-1], s))
    for i in range(len(ROAD) - 1):
        if CUM[i + 1] >= s:
            p = (s - CUM[i]) / max(1e-6, CUM[i + 1] - CUM[i])
            (x0, y0), (x1, y1) = ROAD[i], ROAD[i + 1]
            return x0 + (x1 - x0) * p, y0 + (y1 - y0) * p, math.atan2(y1 - y0, x1 - x0)
    x, y = ROAD[-1]
    return x, y, 0.0


def car_s(t):
    """시간 t에서 차의 경로 거리."""
    if t < INTRO_END:
        return 0.0
    k = min(len(STOPS) - 1, int((t - INTRO_END) // STOP_LEN))
    t0 = INTRO_END + k * STOP_LEN
    s_from = 0.0 if k == 0 else CUM[STOPS[k - 1][0]]
    s_to = CUM[STOPS[k][0]]
    if t >= END_START:
        return CUM[STOPS[-1][0]]
    return lerp(s_from, s_to, ease(seg(t, t0, t0 + DRIVE)))


# ------------------------------------------------------------------ 카메라
def camera(t):
    """(중심 x, 중심 y, 확대) 지도 픽셀 기준."""
    full = (MW / 2, MH / 2, 1.0)
    x, y, _ = at(car_s(t))
    near = (x, y, ZOOM_IN)
    if t < HOOK_END:
        return full
    if t < INTRO_END:
        p = ease(seg(t, HOOK_END + 0.2, INTRO_END))
        return tuple(lerp(a, b, p) for a, b in zip(full, near))
    if t >= END_START:
        p = ease(seg(t, END_START, END_START + 0.9))
        return tuple(lerp(a, b, p) for a, b in zip(near, full))
    return near


def clamp_cam(cx, cy, z):
    s = FIT * z
    hw, hh = W / 2 / s, H / 2 / s
    return min(max(cx, hw), MW - hw), min(max(cy, hh), MH - hh), s


def to_screen(p, cam):
    cx, cy, s = cam
    return W / 2 + (p[0] - cx) * s, H / 2 + (p[1] - cy) * s


def map_view(cam):
    cx, cy, s = cam
    # 출력 (X,Y) -> MAP2 좌표 ((X - W/2)/s + cx) * 2
    a = 2 / s
    return MAP2.transform((W, H), Image.AFFINE,
                          (a, 0, (cx - W / 2 / s) * 2, 0, a, (cy - H / 2 / s) * 2),
                          Image.BILINEAR)


# ------------------------------------------------------------------ 그리기 도구
def text(d, xy, s, font, fill, anchor="mm", stroke=0, sfill=(0, 0, 0)):
    d.text(xy, s, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=sfill)


def make_car():
    S = 4
    w, h = 44 * S, 76 * S
    im = Image.new("RGBA", (w + 20 * S, h + 20 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    o = 10 * S
    d.rounded_rectangle([o + 3 * S, o + 5 * S, o + w + 3 * S, o + h + 5 * S], 16 * S, fill=(0, 0, 0, 70))
    d.rounded_rectangle([o, o, o + w, o + h], 16 * S, fill=(232, 64, 52, 255), outline=(120, 20, 20, 255), width=2 * S)
    d.rounded_rectangle([o + 6 * S, o + 12 * S, o + w - 6 * S, o + 28 * S], 6 * S, fill=(190, 230, 250, 255))
    d.rounded_rectangle([o + 7 * S, o + 50 * S, o + w - 7 * S, o + 62 * S], 5 * S, fill=(170, 210, 235, 255))
    d.rounded_rectangle([o + 8 * S, o + 31 * S, o + w - 8 * S, o + 47 * S], 5 * S, fill=(255, 255, 255, 230))
    for yy in (o + 2 * S, o + h - 6 * S):
        d.ellipse([o + 4 * S, yy, o + 12 * S, yy + 4 * S], fill=(255, 240, 150, 255))
        d.ellipse([o + w - 12 * S, yy, o + w - 4 * S, yy + 4 * S], fill=(255, 240, 150, 255))
    im = im.resize((im.width // S, im.height // S), Image.LANCZOS)
    return im  # 위쪽이 차 앞


CAR = make_car()


def paste_car(img, xy, heading, scale, bounce=0.0):
    im = CAR.resize((int(CAR.width * scale), int(CAR.height * scale)), Image.LANCZOS)
    deg = -math.degrees(heading) - 90  # 차 앞(위쪽)을 진행 방향으로
    im = im.rotate(deg, resample=Image.BICUBIC, expand=True)
    x, y = xy
    img.paste(im, (int(x - im.width / 2), int(y - im.height / 2 - bounce)), im)


def rounded(im, r):
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], r, fill=255)
    return m


def draw_trail(d, cam, s_to):
    pts = []
    s = 0.0
    while s < s_to:
        x, y, _ = at(s)
        pts.append(to_screen((x, y), cam))
        s += 6
    for i in range(0, len(pts) - 1, 3):
        d.line([pts[i], pts[i + 1]], fill=ORANGE, width=7)


def draw_pin(d, xy, p, label=None):
    if p <= 0:
        return
    x, y = xy
    r = max(6.0, 20 * back(p))
    d.ellipse([x - r - 4, y - r * 2.1 - 4, x + r + 4, y - 4], fill=WHITE)
    d.polygon([(x - r * 0.6, y - r * 1.1), (x + r * 0.6, y - r * 1.1), (x, y + 2)], fill=WHITE)
    d.ellipse([x - r, y - r * 2.1, x + r, y - 8], fill=ORANGE)
    d.ellipse([x - r * 0.4, y - r * 1.5, x + r * 0.4, y - r * 0.7], fill=WHITE)


# ------------------------------------------------------------------ 훅
YELLOW, INK, RED = (255, 225, 40), (20, 20, 24), (235, 50, 50)


def word_img(s, size, fill, stroke=0, sfill=INK):
    f = F(BOLD, size)
    l, t_, r, b = f.getbbox(s, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + 20, b - t_ + 20), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10 - l, 10 - t_), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)
    return im


def slam(img, s, center, size, fill, p, rot=0.0, stroke=0, sfill=INK, shadow=True):
    """키네틱 타이포 한 단어: 크게 들어와서 튕기며 자리 잡는다. p=0..1"""
    if p <= 0:
        return
    sc = 2.2 - 1.2 * back(min(1.0, p), 2.4) if p < 1 else 1.0
    w = word_img(s, size, fill, stroke, sfill)
    w = w.resize((max(1, int(w.width * sc)), max(1, int(w.height * sc))), Image.BICUBIC)
    if rot:
        w = w.rotate(rot * (1 - 0.3 * min(1, p)), resample=Image.BICUBIC, expand=True)
    a = w.getchannel("A").point(lambda v: int(v * min(1.0, p * 3)))
    w.putalpha(a)
    x, y = center
    if shadow:
        sh = Image.new("RGBA", w.size, (0, 0, 0, 0))
        sh.putalpha(a.point(lambda v: int(v * 0.55)))
        img.paste(sh, (int(x - w.width / 2 + 14), int(y - w.height / 2 + 16)), sh)
    img.paste(w, (int(x - w.width / 2), int(y - w.height / 2)), w)


def beat_p(t, beat_index, length=0.9):
    """beat_index 박에 시작해 length 박 동안 0→1."""
    return seg(t, beat_index * BEAT, (beat_index + length) * BEAT)


HOOK_SHORT = ["이가리", "곤륜산", "스페이스워크", "영일대", "호미곶", "구룡포"]
CUT0 = 3                            # 질문 구간이 끝나는 박
# 콜라주: (중심 x, 중심 y, 회전°). 2열 × 3행, 한 박에 한 장씩 붙는다.
CARD_POS = [(292, 585, -4), (788, 575, 3), (300, 1105, 3), (782, 1095, -3), (290, 1625, -2), (792, 1615, 4)]
CARD_BEATS = [4, 5, 6, 7, 8, 9]
_card_cache = {}


def photo_card(i):
    """장소 사진 한 장을 폴라로이드 카드로 (정지 사진)."""
    if i in _card_cache:
        return _card_cache[i]
    fr = clip_frame(STOPS[i][4], 1.0)
    ph = fr.crop((0, 285, W, 285 + 1350)).resize((340, 425), Image.LANCZOS)
    bw, bot = 14, 64
    card = Image.new("RGBA", (340 + 2 * bw, 425 + bw + bot), (255, 255, 255, 255))
    card.paste(ph, (bw, bw))
    d = ImageDraw.Draw(card)
    ly = 425 + bw + bot / 2
    d.text((bw + 6, ly), f"{i + 1:02d}", font=F(LATIN, 30), fill=ORANGE, anchor="lm")
    d.text((card.width / 2 + 22, ly), HOOK_SHORT[i], font=F(BOLD, 34), fill=INK, anchor="mm")
    _card_cache[i] = card
    return card


def place_card(img, i, p):
    """카드가 살짝 크게 들어와 '착' 하고 자리 잡는다. p=0..1"""
    if p <= 0:
        return
    x, y, rot = CARD_POS[i]
    key = ("final", i)
    if p >= 1 and key in _card_cache:
        c, sh, off = _card_cache[key]
    else:
        card = photo_card(i)
        sc = 1.0 if p >= 1 else 1.4 - 0.4 * back(p, 1.3)
        c = card if sc == 1 else card.resize((int(card.width * sc), int(card.height * sc)), Image.BICUBIC)
        c = c.rotate(rot + (1 - min(p, 1.0)) * 10, resample=Image.BICUBIC, expand=True)
        a = c.getchannel("A")
        sh = Image.new("RGBA", c.size, (0, 0, 0, 0))
        sh.putalpha(a.point(lambda v: int(v * 0.35)))
        sh = sh.filter(ImageFilter.GaussianBlur(6))
        off = int(10 + 40 * (sc - 1))
        if p >= 1:
            _card_cache[key] = (c, sh, off)
        else:
            c.putalpha(a.point(lambda v: int(v * min(1.0, p * 4))))
    img.paste(sh, (int(x - sh.width / 2 + off), int(y - sh.height / 2 + off)), sh)
    img.paste(c, (int(x - c.width / 2), int(y - c.height / 2)), c)


def shade(img, top=520, bottom=760):
    """글자가 잘 읽히도록 위·아래를 어둡게."""
    g = Image.new("L", (1, H), 0)
    g.putdata([int(150 * max(0, 1 - y / top)) if y < top else
               int(170 * max(0, (y - (H - bottom)) / bottom)) if y > H - bottom else 0 for y in range(H)])
    g = g.resize((W, H))
    return Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, g)


def hook(t):
    """0–8박 훅 (v4). 첫 프레임부터 실사와 큰 질문이 보이게 한다.

    0–2박: 흑백 호미곶 + "포항 하면 / 철?" → 2박: "땡!"과 함께 색이 터짐
    2.5–6.5박: 6곳 몽타주(컷 0.31초), 번호 01→06 카운터
    6.5–8박: 노랑 화면 "포항 한 바퀴 GO!" → 지도로
    """
    b = t / BEAT
    cx = W / 2
    punch = 1 + 0.07 * math.exp(-(b - int(b)) * 6)

    if b < CUT0:
        base = clip_frame("RBhsrBwPheQ", 0.3 + t * 0.5)
        colour = ease_out(seg(t, 2 * BEAT, 2 * BEAT + 0.15))
        g = ImageOps.grayscale(base).convert("RGB")
        g = Image.blend(g, Image.new("RGB", (W, H), (30, 30, 30)), 0.35)
        img = shade(Image.blend(g, base, colour))
        # 첫 프레임에 이미 글자가 보이도록 p를 0.45에서 시작
        slam(img, "포항 하면", (cx, 470), int(150 * punch), WHITE, max(0.45, beat_p(t, 0, 0.6)),
             stroke=9, sfill=INK)
        slam(img, "철?", (cx, 820), int(430 * punch), (205, 205, 205), beat_p(t, 1, 0.55), rot=-6,
             stroke=12, sfill=INK)
        if b >= 2:
            d = ImageDraw.Draw(img)
            q = ease_out(seg(t, 2 * BEAT, 2 * BEAT + 0.12))
            d.line([(cx - 260, 960), (cx - 260 + 520 * q, 660)], fill=RED, width=34)
            slam(img, "땡!", (cx + 150, 1330), int(330 * punch), RED, beat_p(t, 2, 0.35), rot=-12,
                 stroke=14, sfill=WHITE)
        if 2 * BEAT <= t < 2 * BEAT + 2 / FPS:  # 땡 순간 흰 번쩍
            img = Image.blend(img, Image.new("RGB", (W, H), WHITE), 0.55)
        return img

    # 3–3.4박: 노란 화면이 아래에서 올라와 덮는다
    img = Image.new("RGB", (W, H), YELLOW)
    if b < 3.4:
        q = hook(2.99 * BEAT)
        h = int(H * ease(seg(t, 3 * BEAT, 3.4 * BEAT)))
        if h > 0:
            q.paste(img.crop((0, H - h, W, H)), (0, H - h))
        return q
    # 3.4박~: 제목, 4–9박: 사진이 한 박에 한 장씩 붙는다 (붙은 사진은 남는다)
    slam(img, "철만 있는 줄 알았지?", (cx, 230), 84, INK, beat_p(t, 3.4, 0.5), shadow=False)
    for i in range(6):
        place_card(img, i, beat_p(t, CARD_BEATS[i], 0.35))
    # 10박: 콜라주를 어둡게 두고 "포항 한 바퀴 GO!"
    if b >= 10:
        dim = 0.5 * ease_out(seg(t, 10 * BEAT, 10.3 * BEAT))
        img = Image.blend(img, Image.new("RGB", (W, H), (0, 0, 0)), dim)
        slam(img, "포항 한 바퀴", (cx, 820), int(150 * punch), WHITE, beat_p(t, 10, 0.4), stroke=9, sfill=INK)
        slam(img, "GO!", (cx, 1110), int(380 * punch), YELLOW, beat_p(t, 10.4, 0.4), rot=-4,
             stroke=14, sfill=INK)
    return img


# ------------------------------------------------------------------ 프레임
def card_rect(pin_xy):
    cw, ch = 300, 400
    x, y = pin_xy
    left = x < W / 2
    x0 = x + 60 if left else x - 60 - cw
    y0 = min(max(y - ch - 60, 140), H - ch - 300)
    return [x0, y0, x0 + cw, y0 + ch]


def render(t):
    if t < HOOK_END - BEAT / 2:
        return hook(t)
    cam = clamp_cam(*camera(t))
    img = map_view(cam)
    d = ImageDraw.Draw(img)
    s_now = car_s(t)
    draw_trail(d, cam, s_now)

    k = -1
    if INTRO_END <= t < END_START:
        k = int((t - INTRO_END) // STOP_LEN)
    # 지나온 핀과 현재 핀
    for i, (idx, pin, name, *_r) in enumerate(STOPS):
        if CUM[idx] <= s_now + 1 and (i < k or t >= END_START or
                                    (i == k and t >= INTRO_END + i * STOP_LEN + DRIVE)):
            t_arr = INTRO_END + i * STOP_LEN + DRIVE
            draw_pin(d, to_screen(pin, cam), seg(t, t_arr, t_arr + 0.25) if i == k else 1.0)

    x, y, hd = at(s_now)
    bounce = 0.0
    if k >= 0:
        t_arr = INTRO_END + k * STOP_LEN + DRIVE
        bounce = 14 * math.sin(math.pi * seg(t, t_arr, t_arr + 0.25))
    car_scale = FIT * cam[2] / FIT * 0.55 / (cam[2] / ZOOM_IN) if cam[2] else 1
    car_scale = 0.9 * cam[2] / ZOOM_IN + 0.25
    if t >= HOOK_END - BEAT / 2:
        drop = ease_out(seg(t, HOOK_END - BEAT / 2, HOOK_END + BEAT))
        paste_car(img, to_screen((x, y), cam), hd, car_scale, bounce + 200 * (1 - drop))

    # 훅 → 지도 원형 전환
    if t < HOOK_END:
        p = ease(seg(t, HOOK_END - BEAT / 2, HOOK_END))
        hk = hook(t)
        m = Image.new("L", (W, H), 255)
        r = p * 1200
        ImageDraw.Draw(m).ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r], fill=0)
        img = Image.composite(hk, img, m)
        return img

    if k >= 0:
        img = stop_overlay(img, t, k, cam)
    if t >= END_START:
        img = ending(img, t)
    return img


def stop_overlay(img, t, k, cam):
    idx, pin, name, copy, vid, _start = STOPS[k]
    t0 = INTRO_END + k * STOP_LEN
    t_pop, t_zoom, t_live = t0 + DRIVE, t0 + DRIVE + POP, t0 + DRIVE + POP + ZOOM
    t_back, t_end = t_live + LIVE, t0 + STOP_LEN
    if t < t_pop:
        return img
    pin_xy = to_screen(pin, cam)
    card = card_rect(pin_xy)
    full = [0, 0, W, H]
    ct = max(0.0, t - t_zoom)  # 영상 재생 시간
    frame = clip_frame(vid, ct)
    d = ImageDraw.Draw(img)
    if t < t_zoom:
        p = back(seg(t, t_pop, t_pop + 0.35))
        cx, cy = (card[0] + card[2]) / 2, (card[1] + card[3]) / 2
        w, h = (card[2] - card[0]) * p, (card[3] - card[1]) * p
        rect = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        rad, label = 28, True
    elif t < t_back:
        p = ease(seg(t, t_zoom, t_live))
        rect = [lerp(a, b, p) for a, b in zip(card, full)]
        rad, label = int(28 * (1 - p)), p < 0.3
    else:
        p = ease(seg(t, t_back, t_end))
        rect = [lerp(a, b, p) for a, b in zip(full, card)]
        rad, label = int(28 * p), False
    w, h = int(rect[2] - rect[0]), int(rect[3] - rect[1])
    if w < 4 or h < 4:
        return img
    # 테두리 (흰 카드)
    pad = int(10 * (1 - (0 if t < t_zoom else min(1, seg(t, t_zoom, t_live) + seg(t, t_back, t_end) * 0))))
    if t >= t_back:
        pad = int(10 * seg(t, t_back, t_end))
    if pad > 0:
        sh = Image.new("RGBA", (w + 2 * pad + 30, h + 2 * pad + 30), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([15, 25, 15 + w + 2 * pad, 25 + h + 2 * pad], rad + pad,
                                             fill=(0, 0, 0, 80))
        sh = sh.filter(ImageFilter.GaussianBlur(8))
        img.paste(sh, (int(rect[0] - pad - 15), int(rect[1] - pad - 15)), sh)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([rect[0] - pad, rect[1] - pad, rect[2] + pad, rect[3] + pad + (46 if label else 0)],
                            rad + pad, fill=WHITE)
    ph = frame.resize((w, h), Image.BILINEAR) if (w, h) != frame.size else frame
    img.paste(ph, (int(rect[0]), int(rect[1])), rounded(ph, max(rad, 0)))
    d = ImageDraw.Draw(img)
    if label and t < t_zoom + 0.15:
        text(d, ((rect[0] + rect[2]) / 2, rect[3] + 28), name, F(BOLD, 30 if len(name) < 8 else 24), NAVY)
    # 실사 위 키네틱 타이포: 박마다 한 덩어리씩 꽂힌다 (live 3박)
    if t_live - 0.05 <= t < t_back + 0.05:
        lb = (t - t_live) / BEAT
        w1, w2 = KINETIC[k]
        # 1박: 번호 + 장소명 띠
        q = back(seg(t, t_live, t_live + 0.5 * BEAT))
        bar_w = int((W - 120) * min(1, seg(t, t_live, t_live + 0.4 * BEAT) * 1.0))
        if bar_w > 0:
            d.rectangle([60, 150, 60 + bar_w, 262], fill=YELLOW)
        text(d, (80, 206 - 20 * (1 - q)), f"{k + 1:02d}", F(LATIN, 70), INK, anchor="lm")
        nf = F(BOLD, 64 if len(name) < 8 else 44)
        text(d, (210, 206 - 20 * (1 - q)), name, nf, INK, anchor="lm")
        # 2박: 첫 단어, 3박: 큰 강조 단어 (박마다 펀치)
        punch = 1 + 0.08 * math.exp(-(lb - int(max(lb, 0))) * 6)
        # 장소명 띠(0박) → 첫 단어(1.5박) → 강조 단어(3박) → 한 줄 문구(4박), 나머지 2박은 읽는 시간
        slam(img, w1, (W / 2 - 60, 1180), int(150 * punch), WHITE, seg(t, t_live + 1.5 * BEAT, t_live + 2.1 * BEAT),
             rot=-4, stroke=8, sfill=INK)
        slam(img, w2, (W / 2 + 30, 1420), int((220 if len(w2) <= 3 else 170) * punch), YELLOW,
             seg(t, t_live + 3 * BEAT, t_live + 3.6 * BEAT), rot=3, stroke=10, sfill=INK)
        d = ImageDraw.Draw(img)
        q2 = seg(t, t_live + 4 * BEAT, t_live + 4.6 * BEAT)
        if q2 > 0:
            text(d, (W / 2, H - 230), copy, F(MED, 50), WHITE, stroke=4, sfill=INK)
    return img


def ending(img, t):
    """엔딩: 라이저 2박 동안 지도 줌아웃 → 히트 박에 노랑 화면 + 큰 타이포."""
    hit = END_START + 2 * BEAT
    if t < hit:
        slam(img, "이번 주말은?", (W / 2, 520), 130, WHITE, seg(t, END_START + 0.5 * BEAT, END_START + 1.3 * BEAT),
             stroke=9, sfill=INK)
        return img
    lb = (t - hit) / BEAT
    punch = 1 + 0.08 * math.exp(-(lb - int(lb)) * 6)
    bg = Image.new("RGB", (W, H), YELLOW)
    mix = ease_out(seg(t, hit, hit + 0.12))
    img = Image.blend(img, bg, mix)
    slam(img, "이번 주말은", (W / 2, 620), int(110 * punch), INK, seg(t, hit, hit + 0.5 * BEAT), shadow=False)
    slam(img, "포항", (W / 2, 900), int(360 * punch), (32, 90, 200), seg(t, hit + 0.5 * BEAT, hit + 1.2 * BEAT),
         rot=-3, stroke=12, sfill=INK)
    slam(img, "한 바퀴 가자!", (W / 2, 1230), int(110 * punch), INK, seg(t, hit + 1.5 * BEAT, hit + 2.1 * BEAT),
         shadow=False)
    return img


def main():
    OUT.mkdir(exist_ok=True)
    prepare_clips()
    if len(sys.argv) > 1 and sys.argv[1] == "still":
        for v in sys.argv[2:]:
            render(float(v)).save(OUT / f"still_{float(v):05.2f}.png")
        return
    dst = OUT / "pohang-map-journey_v5.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(MUSIC), "-filter_complex",
           f"[1:a]atrim=0:{DUR},asetpts=N/SR/TB,alimiter=limit=0.7:level=false,apad[a]",
           "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-crf", "19", "-preset", "medium",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", str(DUR),
           "-movflags", "+faststart", str(dst)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total = int(DUR * FPS)
    for i in range(total):
        proc.stdin.write(render(i / FPS).tobytes())
        if i % 90 == 0:
            print(f"{i}/{total}", flush=True)
    proc.stdin.close()
    sys.exit(proc.wait())


if __name__ == "__main__":
    main()
