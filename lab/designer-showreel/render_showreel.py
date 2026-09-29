"""Code-only designer showreel for Modal GUI.

Creates deterministic PNG frames with Pillow, then encodes them with FFmpeg.
No external footage, generated assets, AE project, or paid API is used.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


W, H, FPS, SECONDS = 1280, 720, 30, 18
BG = (8, 12, 24)
INK = (239, 237, 229)
MUTED = (132, 145, 166)
CYAN = (76, 224, 224)
CORAL = (255, 111, 94)
VIOLET = (154, 126, 255)
GRID = (23, 34, 56)
FONT = r"C:\Windows\Fonts\segoeuib.ttf"
MONO = r"C:\Windows\Fonts\consolab.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path if Path(path).exists() else r"C:\Windows\Fonts\arialbd.ttf", size)


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def fade(t: float, start: float, end: float) -> float:
    return ease((t - start) / max(0.001, end - start))


def text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, size: int, fill=INK, anchor="la") -> None:
    draw.text(xy, value, font=font(FONT, size), fill=fill, anchor=anchor)


def grid(draw: ImageDraw.ImageDraw, t: float) -> None:
    drift = int((t * 18) % 48)
    for x in range(-48 + drift, W + 48, 48):
        draw.line((x, 0, x, H), fill=GRID, width=1)
    for y in range(-48 + drift // 2, H + 48, 48):
        draw.line((0, y, W, y), fill=GRID, width=1)


def background(t: float) -> Image.Image:
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    glow = int(16 + 10 * math.sin(t * 0.7))
    draw.ellipse((W - 420, -200, W + 160, 360), fill=(glow, 28, 54))
    draw.ellipse((-240, H - 220, 300, H + 260), fill=(8, 24, 42))
    grid(draw, t)
    return image


def corner_label(draw: ImageDraw.ImageDraw, t: float, label: str) -> None:
    draw.text((48, 42), f"00{int(t * 10) % 100:02d}  /  CODEX", font=font(MONO, 14), fill=MUTED)
    draw.line((48, 68, 178, 68), fill=CORAL, width=3)
    draw.text((W - 48, 42), label, font=font(MONO, 14), fill=MUTED, anchor="ra")


def draw_cursor(draw: ImageDraw.ImageDraw, x: float, y: float, color=CORAL) -> None:
    draw.line((x, y, x + 22, y + 36), fill=color, width=3)
    draw.line((x + 22, y + 36, x + 9, y + 33), fill=color, width=3)
    draw.line((x + 9, y + 33, x, y), fill=color, width=3)


def scene(image: Image.Image, t: float) -> None:
    draw = ImageDraw.Draw(image)
    if t < 3:
        p = fade(t, 0, 1.0)
        corner_label(draw, t, "SYSTEM 01")
        text(draw, (W / 2, 270 - 25 * (1 - p)), "I DESIGN", 92, anchor="mm")
        text(draw, (W / 2, 368 - 25 * (1 - p)), "IN SYSTEMS", 92, fill=CYAN, anchor="mm")
        draw.rectangle((260, 420, 1020, 424), fill=(40, 57, 84))
        draw.rectangle((260, 420, 260 + 760 * p, 424), fill=CORAL)
        draw_cursor(draw, 260 + 760 * p, 420)
    elif t < 7:
        q = t - 3
        corner_label(draw, t, "SYSTEM 02")
        text(draw, (72, 130), "I TURN INTENT", 66, anchor="lm")
        text(draw, (72, 198), "INTO MOTION", 66, fill=CORAL, anchor="lm")
        p = ease(min(1, q / 2.2))
        for i in range(9):
            x = 150 + i * 112
            y = 420 + math.sin(i * 1.3 + q * 4) * 60 * p
            r = 12 + 5 * math.sin(q * 5 + i)
            color = [CYAN, CORAL, VIOLET][i % 3]
            draw.ellipse((x-r, y-r, x+r, y+r), fill=color)
            if i:
                prev = 150 + (i - 1) * 112
                prev_y = 420 + math.sin((i - 1) * 1.3 + q * 4) * 60 * p
                draw.line((prev, prev_y, x, y), fill=(54, 79, 112), width=3)
        for i in range(5):
            xx = 100 + i * 260 + (q * 90) % 80
            draw.line((xx, 570, xx + 140, 570), fill=(64, 85, 119), width=2)
    elif t < 12:
        q = t - 7
        corner_label(draw, t, "SYSTEM 03")
        text(draw, (W / 2, 104), "I MAKE COMPLEXITY", 58, anchor="ma")
        text(draw, (W / 2, 166), "FEEL SIMPLE", 72, fill=CYAN, anchor="ma")
        nodes = [(220, 360), (430, 280), (430, 470), (650, 360), (850, 250), (850, 470), (1060, 360)]
        connections = [(0,1),(0,2),(1,3),(2,3),(3,4),(3,5),(4,6),(5,6)]
        for a, b in connections:
            x1, y1 = nodes[a]; x2, y2 = nodes[b]
            pulse = (math.sin(q * 4 - a * 0.7) + 1) / 2
            draw.line((x1, y1, x2, y2), fill=(38 + int(42 * pulse), 66 + int(80 * pulse), 92 + int(100 * pulse)), width=3)
        for i, (x, y) in enumerate(nodes):
            r = 28 + (7 if int(q * 5) % 7 == i else 0)
            color = CORAL if i in (0, 6) else (CYAN if i == 3 else VIOLET)
            draw.rounded_rectangle((x-r, y-r, x+r, y+r), radius=10, outline=color, width=3)
            draw.ellipse((x-5, y-5, x+5, y+5), fill=color)
        draw_cursor(draw, 1060 + 18 * math.sin(q * 2), 360 + 18 * math.cos(q * 2), CYAN)
    elif t < 16:
        q = t - 12
        corner_label(draw, t, "SYSTEM 04")
        text(draw, (64, 126), "I BUILD WITH", 70, anchor="lm")
        text(draw, (64, 204), "CONSTRAINTS", 70, fill=CORAL, anchor="lm")
        draw.rounded_rectangle((64, 310, 1216, 592), radius=18, outline=(55, 75, 105), width=2)
        for i in range(48):
            x = 100 + i * 22
            h = 20 + 85 * (0.5 + 0.5 * math.sin(i * 1.8 + q * 5))
            color = CYAN if i % 4 else CORAL
            draw.line((x, 448 - h / 2, x, 448 + h / 2), fill=color, width=5)
        for i in range(5):
            x = 120 + i * 240 + q * 30
            draw.rectangle((x, 520, x + 80, 548), outline=VIOLET, width=2)
        text(draw, (64, 650), "TYPE / RHYTHM / LIMITS", 15, fill=MUTED)
    else:
        q = t - 16
        corner_label(draw, t, "SIGNATURE")
        p = fade(q, 0, 0.8)
        text(draw, (W / 2, 270), "CODEX", 124, fill=INK, anchor="mm")
        text(draw, (W / 2, 390), "CREATIVE SYSTEMS", 38, fill=CYAN, anchor="mm")
        draw.line((340, 458, 940, 458), fill=CORAL, width=4)
        text(draw, (W / 2, 520), "idea  →  structure  →  motion", 22, fill=MUTED, anchor="mm")
        draw.arc((W/2-220, 190, W/2+220, 630), start=200, end=200 + 280 * p, fill=VIOLET, width=3)


def render(output_dir: Path, final: Path) -> None:
    frames = output_dir / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for index in range(FPS * SECONDS):
        t = index / FPS
        image = background(t)
        scene(image, t)
        image.save(frames / f"frame-{index:05d}.png", optimize=True)
    final.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
        "-i", str(frames / "frame-%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(final),
    ], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    final = args.output_dir / "final.mp4"
    render(args.output_dir, final)
    (args.output_dir / "production.json").write_text(json.dumps({
        "request": "코드만 써서 Codex를 디자이너로 소개하는 쇼릴",
        "format": {"aspect": "16:9", "seconds": SECONDS, "fps": FPS, "resolution": [W, H]},
        "shots": [
            {"t": "0-3", "stage": 1, "tool": "local-python+local-ffmpeg", "cost": 0},
            {"t": "3-7", "stage": 1, "tool": "local-python+local-ffmpeg", "cost": 0},
            {"t": "7-12", "stage": 1, "tool": "local-python+local-ffmpeg", "cost": 0},
            {"t": "12-16", "stage": 1, "tool": "local-python+local-ffmpeg", "cost": 0},
            {"t": "16-18", "stage": 1, "tool": "local-python+local-ffmpeg", "cost": 0},
        ],
        "fonts": ["Segoe UI", "Consolas"], "music": "none",
        "paid": {"calls": 0, "actual": 0, "estimated": 0}, "output": str(final),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "verdict.md").write_text("# Verdict\n\n초안 렌더 완료. 사용자 평가 대기.\n", encoding="utf-8")
    print(final)


if __name__ == "__main__":
    main()
