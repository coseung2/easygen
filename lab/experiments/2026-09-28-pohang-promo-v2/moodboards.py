"""포항 홍보 4방향 무드보드 (1단계 로컬). python moodboards.py -> moodboard/*.png"""
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
OUT = HERE / "moodboard"
FD = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts"
BOLD = FD / "GmarketSansTTFBold.ttf"
MED = FD / "Pretendard-SemiBold.ttf"
REG = FD / "Pretendard-Regular.ttf"
LATIN = FD / "Montserrat-Black.otf"
SERIF = Path(r"C:\Windows\Fonts\NotoSerifKR-VF.ttf")

BW, BH = 1600, 1500
TW, TH = 330, 587  # 9:16 썸네일
_f = {}


def F(p, n):
    if (p, n) not in _f:
        _f[(p, n)] = ImageFont.truetype(str(p), n)
    return _f[(p, n)]


def ctext(d, xy, s, f, fill, anchor="mm"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def wrap(d, x, y, s, f, fill, width, gap=10):
    line = ""
    for w in s.split(" "):
        t = (line + " " + w).strip()
        if d.textlength(t, font=f) > width and line:
            d.text((x, y), line, font=f, fill=fill)
            y += f.size + gap
            line = w
        else:
            line = t
    if line:
        d.text((x, y), line, font=f, fill=fill)
        y += f.size + gap
    return y


def grad(w, h, c1, c2):
    im = Image.new("RGB", (1, h))
    im.putdata([tuple(int(a + (b - a) * i / (h - 1)) for a, b in zip(c1, c2)) for i in range(h)])
    return im.resize((w, h))


def photo_slot(w, h, c1, c2, label):
    """실사가 들어갈 자리. 색만 무드로 보여준다."""
    im = grad(w, h, c1, c2)
    d = ImageDraw.Draw(im)
    d.rectangle([12, 12, w - 12, h - 12], outline=(255, 255, 255), width=2)
    ctext(d, (w / 2, h - 60), label, F(MED, 20), (255, 255, 255))
    ctext(d, (w / 2, h - 32), "실사 자리", F(REG, 16), (255, 255, 255))
    return im


# ------------------------------------------------------------------ 지도
COAST = json.loads((HERE / "data" / "coastline.json").read_text(encoding="utf-8"))
LAT0, LAT1, LON0, LON1 = 35.93, 36.12, 129.33, 129.60
PLACES = [  # (이름, lat, lon, 확인됨, 라벨 오프셋)
    ("영일대", 36.0565608, 129.3784651, True, (-14, 14, "ra")),
    ("스페이스워크", 36.0651092, 129.3904401, True, (12, -24, "la")),
    ("호미곶", 36.077, 129.567, False, (-12, -24, "ra")),
    ("구룡포", 35.99, 129.555, False, (-14, -10, "ra")),
]


def proj(lat, lon, w, h, pad=20):
    sx = (w - 2 * pad) / (LON1 - LON0)
    sy = sx / math.cos(math.radians(36))
    cy = (LAT0 + LAT1) / 2
    return pad + (lon - LON0) * sx, h / 2 - (lat - cy) * sy


def map_frame(w, h, route_p=1.0, focus=None, card=None):
    im = Image.new("RGB", (w, h), (243, 238, 227))
    d = ImageDraw.Draw(im)
    for line in COAST["lines"]:
        pts = [proj(a, b, w, h) for a, b in line]
        if len(pts) > 1:
            d.line(pts, fill=(47, 111, 163), width=3)
    pins = [proj(p[1], p[2], w, h) for p in PLACES]
    order = [0, 1, 2, 3]
    route = [pins[i] for i in order]
    n = max(1, int(route_p * (len(route) - 1) * 20))
    seg_pts = []
    for i in range(len(route) - 1):
        (x0, y0), (x1, y1) = route[i], route[i + 1]
        for k in range(20):
            t = k / 20
            mx, my = (x0 + x1) / 2, min(y0, y1) - 40
            seg_pts.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1,
                            (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1))
    seg_pts = seg_pts[:n]
    for i in range(0, len(seg_pts) - 1, 2):
        d.line([seg_pts[i], seg_pts[i + 1]], fill=(255, 122, 61), width=4)
    for (name, _, _, ok, (ox, oy, anc)), (x, y) in zip(PLACES, pins):
        r = 10 if name == focus else 7
        if ok:
            d.ellipse([x - r, y - r, x + r, y + r], fill=(30, 42, 54))
        else:
            d.ellipse([x - r, y - r, x + r, y + r], outline=(30, 42, 54), width=3)
        d.text((x + ox, y + oy), name, font=F(MED, 18), fill=(30, 42, 54), anchor=anc)
    if card:
        cx, cy, scale = card
        cw, ch = 170 * scale, 120 * scale
        d.rounded_rectangle([cx - cw / 2 + 6, cy - ch / 2 + 8, cx + cw / 2 + 6, cy + ch / 2 + 8],
                            radius=16, fill=(200, 190, 175))
        slot = photo_slot(int(cw), int(ch), (255, 170, 110), (40, 70, 120), "")
        m = Image.new("L", slot.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, slot.width, slot.height], radius=16, fill=255)
        im.paste(slot, (int(cx - cw / 2), int(cy - ch / 2)), m)
    return im


def frames_map():
    w, h = TW, TH
    f1 = map_frame(w, h, route_p=0.35)
    d = ImageDraw.Draw(f1)
    ctext(d, (w / 2, 70), "포항 한 바퀴", F(BOLD, 36), (30, 42, 54))
    x, y = proj(36.0651092, 129.3904401, w, h)
    f2 = map_frame(w, h, route_p=0.4, focus="스페이스워크", card=(x + 60, y - 110, 1.0))
    ImageDraw.Draw(f2).text((20, h - 70), "02 스페이스워크", font=F(BOLD, 26), fill=(30, 42, 54))
    f3 = Image.new("RGB", (w, h), (243, 238, 227))
    slot = photo_slot(w - 40, int((w - 40) * 1.25), (255, 170, 110), (40, 70, 120), "")
    f3.paste(slot, (20, 110))
    d3 = ImageDraw.Draw(f3)
    ctext(d3, (w / 2, 60), "카드가 화면을 채움", F(MED, 20), (30, 42, 54))
    f4 = photo_slot(w, h, (255, 170, 110), (30, 50, 90), "스페이스워크 실사")
    ImageDraw.Draw(f4).text((24, 40), "02", font=F(LATIN, 40), fill=(255, 255, 255))
    return [(f1, "지도 위 경로가 그려짐"), (f2, "핀 도착 → 미리보기 카드"),
            (f3, "카드 확대"), (f4, "실사로 전환")]


# ------------------------------------------------------------------ 출시 패러디
def frames_launch():
    w, h = TW, TH
    k, o, wht = (12, 12, 14), (255, 106, 0), (245, 245, 245)
    f1 = Image.new("RGB", (w, h), k)
    d = ImageDraw.Draw(f1)
    ctext(d, (w / 2, h / 2 - 30), "NEW", F(LATIN, 90), o)
    ctext(d, (w / 2, h / 2 + 50), "coming soon", F(REG, 22), (150, 150, 150))
    f2 = Image.new("RGB", (w, h), wht)
    d = ImageDraw.Draw(f2)
    ctext(d, (w / 2, 150), "포항", F(BOLD, 96), k)
    ctext(d, (w / 2, 230), "PRO MAX", F(LATIN, 34), o)
    d.ellipse([w / 2 - 90, 300, w / 2 + 90, 480], fill=(255, 176, 102))
    ctext(d, (w / 2, 530), "일출 탑재", F(MED, 24), k)
    f3 = Image.new("RGB", (w, h), wht)
    d = ImageDraw.Draw(f3)
    for i, (a, b) in enumerate([("일출", "호미곶"), ("야경", "영일대"), ("트랙", "스페이스워크")]):
        y = 120 + i * 150
        d.rounded_rectangle([30, y, w - 30, y + 120], radius=20, fill=(255, 255, 255),
                            outline=(220, 220, 220), width=2)
        d.text((56, y + 24), a, font=F(BOLD, 34), fill=k)
        d.text((56, y + 72), b, font=F(REG, 20), fill=(120, 120, 120))
        d.ellipse([w - 100, y + 35, w - 50, y + 85], fill=o)
    ctext(d, (w / 2, 80), "SPEC", F(LATIN, 28), o)
    f4 = Image.new("RGB", (w, h), k)
    d = ImageDraw.Draw(f4)
    ctext(d, (w / 2, h / 2 - 40), "지금 출시", F(BOLD, 60), wht)
    d.rounded_rectangle([w / 2 - 110, h / 2 + 30, w / 2 + 110, h / 2 + 90], radius=30, fill=o)
    ctext(d, (w / 2, h / 2 + 60), "포항 가기", F(BOLD, 26), wht)
    return [(f1, "블랙 티저"), (f2, "제품 공개"), (f3, "스펙 카드"), (f4, "출시 + 버튼")]


# ------------------------------------------------------------------ 오해 풀기
def frames_myth():
    w, h = TW, TH
    g = (150, 150, 150)
    f1 = Image.new("RGB", (w, h), (235, 235, 235))
    d = ImageDraw.Draw(f1)
    ctext(d, (w / 2, h / 2 - 40), "포항 하면", F(BOLD, 50), (40, 40, 40))
    ctext(d, (w / 2, h / 2 + 40), "철?", F(BOLD, 90), (40, 40, 40))
    f2 = Image.new("RGB", (w, h), (200, 200, 200))
    d = ImageDraw.Draw(f2)
    for i in range(5):
        d.rectangle([40 + i * 55, 280 - i * 25, 80 + i * 55, 470], fill=g)
    ctext(d, (w / 2, 120), "…만 있는 줄", F(MED, 30), (70, 70, 70))
    d.line([30, 90, w - 30, 500], fill=(255, 60, 60), width=10)
    f3 = photo_slot(w, h, (120, 200, 240), (0, 90, 160), "바다 실사")
    d = ImageDraw.Draw(f3)
    ctext(d, (w / 2, 110), "바다도", F(BOLD, 70), (255, 255, 255))
    ctext(d, (w / 2, 190), "있어요", F(BOLD, 70), (255, 230, 60))
    f4 = Image.new("RGB", (w, h), (255, 230, 60))
    d = ImageDraw.Draw(f4)
    ctext(d, (w / 2, h / 2 - 50), "생각보다", F(BOLD, 52), (20, 20, 20))
    ctext(d, (w / 2, h / 2 + 30), "포항", F(BOLD, 96), (0, 90, 160))
    return [(f1, "질문 훅"), (f2, "예상 이미지 → 빨간 줄"), (f3, "반전: 선명한 실사"),
            (f4, "반전 2–3회 뒤 엔딩")]


# ------------------------------------------------------------------ 동그라미 여행
def frames_circle():
    w, h = TW, TH
    sun = (255, 170, 80)

    def base(c1, c2, label, cy, r, fill, ring=False):
        im = grad(w, h, c1, c2)
        d = ImageDraw.Draw(im)
        if ring:
            d.ellipse([w / 2 - r, cy - r, w / 2 + r, cy + r], outline=fill, width=18)
        else:
            d.ellipse([w / 2 - r, cy - r, w / 2 + r, cy + r], fill=fill)
        ctext(d, (w / 2, h - 70), label, F(SERIF, 28), (255, 255, 255))
        return im

    f1 = base((40, 50, 100), (255, 150, 100), "해 · 호미곶", 260, 90, sun)
    f2 = base((10, 20, 45), (30, 55, 95), "등불 · 영일대", 260, 90, (255, 214, 130))
    f3 = base((60, 150, 200), (20, 80, 140), "물결 · 바다", 260, 90, (240, 250, 255), ring=True)
    f4 = base((250, 236, 214), (230, 200, 160), "그릇 · 음식", 260, 90, (255, 255, 255))
    d = ImageDraw.Draw(f4)
    d.ellipse([w / 2 - 60, 200, w / 2 + 60, 320], fill=(230, 90, 70))
    ctext(d, (w / 2, h - 70), "그릇 · 음식", F(SERIF, 28), (90, 60, 40))
    return [(f1, "원 = 해"), (f2, "같은 자리 매치 컷 → 등불"), (f3, "→ 물결"),
            (f4, "→ 그릇, 끝에 다시 해")]


# ------------------------------------------------------------------ 보드
BOARDS = [
    {
        "file": "0-map-journey.png", "title": "지도 여행", "tag": "사용자 제안",
        "promise": "포항 해안선을 따라 장소를 옮겨 다니며, 미리보기 카드가 열리고 실사로 들어간다.",
        "structure": "이동 + 발견",
        "frames": frames_map,
        "palette": [((243, 238, 227), "종이"), ((47, 111, 163), "바다선"), ((255, 122, 61), "경로"),
                    ((30, 42, 54), "잉크")],
        "type": [(BOLD, "지명 Gmarket Sans"), (MED, "설명 Pretendard")],
        "motion": "경로 선 그리기 → 핀 도착 → 카드 튀어나옴 → 카드가 화면을 채우며 실사로 확대. 같은 흐름을 장소마다 반복하고 마지막에 전체 경로를 다시 보여준다.",
        "music": "새로 생성: 가볍게 걷는 템포(100–110 BPM), 장소 도착마다 포인트음",
        "media": "지도·핀·카드·글자 1단계(코드). 실사 4단계(H3) 또는 촬영본",
        "refs": "a3HPd9wsROU-wonka-vox-paper 지도·경로, SgmuplXU2iY-langease 카드 선택→확대",
    },
    {
        "file": "1-launch-parody.png", "title": "포항 출시 패러디", "tag": "추천 · 승인된 패러디 구조 응용",
        "promise": "포항을 신제품처럼 공개하고, 관광지를 기능 스펙으로 소개한다.",
        "structure": "축적 + 변환",
        "frames": frames_launch,
        "palette": [((12, 12, 14), "블랙"), ((245, 245, 245), "화이트"), ((255, 106, 0), "오렌지"),
                    ((255, 176, 102), "일출")],
        "type": [(LATIN, "PRO MAX Montserrat"), (BOLD, "헤드 Gmarket Sans")],
        "motion": "블랙 티저 → 제품 회전 공개 → 스펙 카드가 차례로 쌓임 → 출시 버튼. 앞 요소가 다음 장면이 되는 전환(승인됨).",
        "music": "새로 생성: 리드미컬한 120 BPM, 스펙마다 효과음 (승인된 방향)",
        "media": "그래픽 1단계. 스펙 카드 속 장소는 실사 컷 또는 그래픽",
        "refs": "junyoung-launch-v5 (승인), SgmuplXU2iY-langease, nepda-neop",
    },
    {
        "file": "2-myth-flip.png", "title": "포항 오해 풀기", "tag": "추천",
        "promise": "흔한 첫인상을 보여주고, 예상 밖의 풍경으로 뒤집는다.",
        "structure": "충돌 + 해소",
        "frames": frames_myth,
        "palette": [((200, 200, 200), "예상(회색)"), ((0, 90, 160), "바다"), ((255, 230, 60), "반전"),
                    ((20, 20, 20), "글자")],
        "type": [(BOLD, "질문 Gmarket Sans"), (MED, "보조 Pretendard")],
        "motion": "회색 예상 이미지 → 빨간 줄 → 채도 폭발 실사. 반전 2–3회, 뒤로 갈수록 컷이 빨라진다.",
        "music": "새로 생성: 멈칫하는 정지 → 반전 순간 드롭",
        "media": "질문·예상 그래픽 1단계, 반전 실사 4단계 또는 촬영본",
        "refs": "nepda-neop 퀴즈 훅·컷 밀도",
    },
    {
        "file": "3-circle-journey.png", "title": "동그라미 여행", "tag": "추천",
        "promise": "같은 자리의 동그라미가 해, 등불, 물결, 그릇으로 바뀌며 포항을 잇는다.",
        "structure": "반복 · 변주",
        "frames": frames_circle,
        "palette": [((255, 170, 80), "해"), ((255, 214, 130), "등불"), ((20, 80, 140), "바다"),
                    ((250, 236, 214), "모래")],
        "type": [(SERIF, "Noto Serif KR"), (MED, "보조 Pretendard")],
        "motion": "원의 위치·크기를 고정한 매치 컷. 장면마다 원만 다른 사물로 바뀌고 끝에서 다시 해가 된다.",
        "music": "새로 생성: 잔잔한 루프, 매치 컷마다 같은 음",
        "media": "원·글자 1단계, 장면은 실사 4단계 또는 그래픽",
        "refs": "qaYO4A8Zf5E-seven-sunbeam 모티프 회수, transition-grammar 같은 형태",
    },
]


def board(b):
    im = Image.new("RGB", (BW, BH), (250, 249, 246))
    d = ImageDraw.Draw(im)
    d.text((60, 50), b["title"], font=F(BOLD, 56), fill=(20, 20, 20))
    d.text((60, 125), b["tag"], font=F(MED, 22), fill=(255, 106, 0))
    d.text((60, 165), b["promise"], font=F(MED, 26), fill=(50, 50, 50))
    d.text((60, 205), "구조 · " + b["structure"], font=F(REG, 22), fill=(110, 110, 110))
    x = 60
    for i, (fr, cap) in enumerate(b["frames"]()):
        im.paste(fr, (x, 260))
        d.rectangle([x, 260, x + TW, 260 + TH], outline=(210, 210, 210), width=1)
        d.text((x, 260 + TH + 14), f"{i + 1}  {cap}", font=F(MED, 20), fill=(60, 60, 60))
        if i < 3:
            ctext(d, (x + TW + 22, 260 + TH / 2), "→", F(MED, 30), (160, 160, 160))
        x += TW + 44
    y = 260 + TH + 70
    d.text((60, y), "팔레트", font=F(BOLD, 24), fill=(20, 20, 20))
    for i, (c, name) in enumerate(b["palette"]):
        px = 60 + i * 130
        d.rounded_rectangle([px, y + 40, px + 110, y + 130], radius=14, fill=c,
                            outline=(220, 220, 220))
        d.text((px, y + 140), name, font=F(REG, 18), fill=(80, 80, 80))
        d.text((px, y + 164), "#%02X%02X%02X" % c, font=F(REG, 16), fill=(140, 140, 140))
    tx = 640
    d.text((tx, y), "글자", font=F(BOLD, 24), fill=(20, 20, 20))
    for i, (fp, label) in enumerate(b["type"]):
        sample = "POHANG PRO MAX" if fp == LATIN else "포항 POHANG"
        d.text((tx, y + 40 + i * 70), sample, font=F(fp, 40), fill=(20, 20, 20))
        d.text((tx + 440, y + 55 + i * 70), label, font=F(REG, 18), fill=(120, 120, 120))
    y2 = y + 210
    yy = y2
    for k, label in (("motion", "움직임"), ("music", "음악"), ("media", "매체"), ("refs", "근거")):
        d.text((60, yy), label, font=F(BOLD, 22), fill=(20, 20, 20))
        yy = wrap(d, 170, yy, b[k], F(REG, 21), (60, 60, 60), BW - 240, gap=8) + 10
    d.text((60, BH - 40), "무드보드 · 실사 칸은 색감만 표시 · 호미곶·구룡포 핀은 위치 확인 전(빈 원)",
           font=F(REG, 16), fill=(150, 150, 150))
    return im


def main():
    OUT.mkdir(exist_ok=True)
    thumbs = []
    for b in BOARDS:
        im = board(b)
        im.save(OUT / b["file"])
        thumbs.append(im.resize((800, 750)))
    sheet = Image.new("RGB", (1600, 1500), (255, 255, 255))
    for i, t in enumerate(thumbs):
        sheet.paste(t, ((i % 2) * 800, (i // 2) * 750))
    sheet.save(OUT / "all.jpg", quality=90)


if __name__ == "__main__":
    main()
