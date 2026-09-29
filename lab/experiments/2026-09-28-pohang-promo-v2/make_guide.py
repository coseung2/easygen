"""지도 생성용 가이드 이미지: 실제 해안선(OSM)과 6곳 위치를 9:16 캔버스에 그린다 (1단계, 무료).

결과: map/guide.png, map/pins_guide.json (가이드 좌표계의 핀 픽셀 위치)
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
OUT = HERE / "map"
W, H = 1024, 1824
# 북 이가리 ~ 남 구룡포 전체가 세로로 들어가는 범위
LAT0, LAT1 = 35.95, 36.21
LON0, LON1 = 129.30, 129.62
PLACES = {  # 확인된 좌표 (steps/brief.md)
    "igari": (36.1832, 129.3786),
    "gonryunsan": (36.1347, 129.3916),
    "spacewalk": (36.0651, 129.3904),
    "yeongildae": (36.0566, 129.3785),
    "homigot": (36.0768, 129.5672),
    "guryongpo": (35.9872, 129.5556),
}


def proj(lat, lon):
    kx = math.cos(math.radians((LAT0 + LAT1) / 2))
    sx = W / ((LON1 - LON0) * kx)
    sy = H / (LAT1 - LAT0)
    s = min(sx, sy)
    cx, cy = (LON0 + LON1) / 2, (LAT0 + LAT1) / 2
    return W / 2 + (lon - cx) * kx * s, H / 2 - (lat - cy) * s


def main():
    OUT.mkdir(exist_ok=True)
    coast = json.loads((HERE / "data" / "coastline.json").read_text(encoding="utf-8"))
    # 해안선을 벽으로 그린 뒤, 동쪽 가장자리(바다)에서 채워 들어간 곳만 바다로 본다.
    LAND, SEA, WALL = (200, 220, 170), (120, 170, 210), (40, 40, 40)
    im = Image.new("RGB", (W, H), LAND)
    d = ImageDraw.Draw(im)
    for line in coast["lines"]:
        pts = [proj(a, b) for a, b in line]
        if len(pts) > 1:
            d.line(pts, fill=WALL, width=6)
    # 해안선 양 끝을 캔버스 위·아래 가장자리까지 세로 벽으로 막아 바다 채움이 육지로 새지 않게 한다
    allpts = [proj(a, b) for l in coast["lines"] for a, b in l]
    top = min(allpts, key=lambda p: p[1])
    bot = max(allpts, key=lambda p: p[1])
    d.line([top, (top[0], -5)], fill=WALL, width=6)
    d.line([bot, (bot[0], H + 5)], fill=WALL, width=6)
    for y in range(0, H, 40):  # 동쪽 가장자리의 여러 점에서 채움 (섬·만으로 끊긴 바다 포함)
        if im.getpixel((W - 2, y)) == LAND:
            ImageDraw.floodfill(im, (W - 2, y), SEA)
    for line in coast["lines"]:
        pts = [proj(a, b) for a, b in line]
        if len(pts) > 1:
            d.line(pts, fill=(40, 40, 40), width=6)
    pins = {}
    for k, (a, b) in PLACES.items():
        x, y = proj(a, b)
        pins[k] = [round(x), round(y)]
        d.ellipse([x - 22, y - 22, x + 22, y + 22], fill=(230, 60, 40), outline=(255, 255, 255), width=5)
    im.save(OUT / "guide.png")
    (OUT / "pins_guide.json").write_text(json.dumps(pins, indent=1), encoding="utf-8")
    print(pins)


if __name__ == "__main__":
    main()
