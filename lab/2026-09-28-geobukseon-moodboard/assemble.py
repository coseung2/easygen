"""거북선·한산도 1592 20초 조립 — H3 클립 4편 + 키네틱 타이포 + (뒤에) 음악.

사용:
  python lab/2026-09-28-geobukseon-moodboard/assemble.py video
  python lab/2026-09-28-geobukseon-moodboard/assemble.py audio --music <flac> [--offset 32.5]
"""

from __future__ import annotations

import argparse
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.lab_paths import font_path, lab_path

ROOT = lab_path("2026-09-28-geobukseon-moodboard")
CLIPS = ROOT / "h3" / "clips"
WORK = ROOT / "assembled"
OUT = ROOT / "out"

W, H, FPS = 1080, 1920, 24
FRAMES = 120  # 5.0초 × 4

FONT_TITLE = font_path("BMJUA_ttf.ttf")
FONT_SUB = font_path("Pretendard-Bold.ttf", "Pretendard-Bold.otf")

PAPER = (247, 241, 228, 255)
INK = (20, 16, 12, 255)
ACCENT = (198, 66, 38, 255)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def fit_font(path: Path, text: str, max_w: int, start: int, step: int = 2, floor: int = 24) -> ImageFont.FreeTypeFont:
    size = start
    while size > floor:
        font = ImageFont.truetype(str(path), size)
        if font.getlength(text) <= max_w:
            return font
        size -= step
    return ImageFont.truetype(str(path), floor)


def text_img(segments: list[tuple[str, tuple[int, int, int, int], Path, int]], max_w: int,
             stroke: int = 7) -> Image.Image:
    """segments: (text, fill, font_path, start_size) — 합쳐서 한 장의 RGBA로."""
    total = 0
    rendered: list[tuple[Image.Image, tuple[int, int, int, int]]] = []
    for text, fill, path, start in segments:
        font = fit_font(path, text, max_w, start)
        img = Image.new("RGBA", (int(font.getlength(text)) + stroke * 4, int(font.size * 1.5) + stroke * 4), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((stroke * 2, stroke * 2), text, font=font, fill=fill,
                                 stroke_width=stroke, stroke_fill=INK)
        rendered.append((img, fill))
        total += img.width
    out = Image.new("RGBA", (total, max(i.height for i, _ in rendered)), (0, 0, 0, 0))
    x = 0
    for img, _ in rendered:
        out.alpha_composite(img, (x, (out.height - img.height) // 2))
        x += img.width
    return out


def place_shadow(canvas: Image.Image, img: Image.Image, xy: tuple[int, int],
                 shadow_alpha: int = 120, blur: int = 10, dy: int = 8) -> None:
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, shadow_alpha), (0, 0), img.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(shadow, (xy[0], xy[1] + dy))
    canvas.alpha_composite(img, xy)


def alpha_mul(img: Image.Image, k: float) -> Image.Image:
    if k >= 1:
        return img
    out = img.copy()
    a = out.split()[3].point(lambda v: int(v * max(0.0, k)))
    out.putalpha(a)
    return out


def wipe_mask(size: tuple[int, int], edge_x: float, feather: float = 110) -> Image.Image:
    w, h = size
    xs = np.arange(w, dtype=np.float32)
    a = np.clip((edge_x - xs) / feather, 0.0, 1.0) * 255.0
    arr = np.tile(a.astype(np.uint8), (h, 1))
    return Image.fromarray(arr, "L")


def centered_xy(img: Image.Image, cx: int, cy: int) -> tuple[int, int]:
    return cx - img.width // 2, cy - img.height // 2


# ---------------- clip overlays ----------------

def overlay_clip1(i: int) -> Image.Image:
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    t = i / FPS
    main = text_img([("1592", ACCENT, FONT_TITLE, 120), (" · 한산도 앞바다", PAPER, FONT_TITLE, 96)], 960)
    sub = text_img([("이순신의 함대, 진형을 펼치다", PAPER, FONT_SUB, 56)], 900, stroke=6)

    # 0-0.55s: 붓이 쓸며 드러남
    p = min(1.0, t / 0.55)
    eased = 1 - (1 - p) ** 3
    mx, my = centered_xy(main, W // 2, 350)
    mask = wipe_mask(main.size, eased * (main.width + 140))
    revealed = main.copy()
    revealed.putalpha(Image.composite(main.split()[3], Image.new("L", main.size, 0), mask))
    ink_band = None
    if p < 1:
        band_x = int(eased * (main.width + 140)) - 70
        band = Image.new("RGBA", (150, main.height + 90), (0, 0, 0, 0))
        ImageDraw.Draw(band).ellipse((0, 0, band.width - 1, band.height - 1), fill=(30, 24, 18, 110))
        ink_band = band.filter(ImageFilter.GaussianBlur(26))
    out1 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if ink_band is not None:
        out1.alpha_composite(ink_band, (mx + band_x - 40, my - 45))
    place_shadow(out1, revealed, (mx, my))

    # 1.4s: 보조 문구
    if t >= 1.4:
        k = min(1.0, (t - 1.4) / 0.35)
        risen = alpha_mul(sub, k)
        sx, sy = centered_xy(sub, W // 2, 500 + int((1 - k) * 26))
        place_shadow(out1, risen, (sx, sy), shadow_alpha=110, blur=8, dy=6)

    # 4.4s부터 아웃
    if t > 4.4:
        k = max(0.0, 1 - (t - 4.4) / 0.6)
        base = out1.copy()
        out1 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out1.paste(alpha_mul(base, k), (0, 0))
    return out1


def overlay_clip3(i: int) -> Image.Image:
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    t = i / FPS
    chars = "학익진"
    font = fit_font(FONT_TITLE, chars, 880, 240)
    char_imgs = []
    for ch in chars:
        bbox = font.getbbox(ch, stroke_width=8)
        img = Image.new("RGBA", (bbox[2] - bbox[0] + 24, bbox[3] - bbox[1] + 24), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((12 - bbox[0], 12 - bbox[1]), ch, font=font, fill=PAPER, stroke_width=8, stroke_fill=INK)
        char_imgs.append(img)
    gap = 26
    total_w = sum(c.width for c in char_imgs) + gap * (len(char_imgs) - 1)
    x0 = W // 2 - total_w // 2
    title_cy = 360

    for idx, img in enumerate(char_imgs):
        t0 = 0.5 + 0.5 * idx
        k = (t - t0) / 0.14
        if k <= 0:
            x0 += img.width + gap
            continue
        k = min(1.0, k)
        scale = 1.3 - 0.3 * (1 - (1 - k) ** 3)
        scaled = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        scaled = alpha_mul(scaled, k)
        cx = x0 + img.width // 2
        if k < 1:  # 먹 번짐 플래시
            r = int(200 + 90 * k)
            flash = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0))
            ImageDraw.Draw(flash).ellipse((0, 0, r * 2 - 1, r * 2 - 1), fill=(20, 16, 12, int(70 * (1 - k))))
            frame.alpha_composite(flash.filter(ImageFilter.GaussianBlur(30)), (cx - r, title_cy - r))
        place_shadow(frame, scaled, centered_xy(scaled, cx, title_cy))
        x0 += img.width + gap

    # 밑줄 붓선 1.9–2.3s
    if t >= 1.9:
        p = min(1.0, (t - 1.9) / 0.4)
        ul = Image.new("RGBA", (940, 40), (0, 0, 0, 0))
        d = ImageDraw.Draw(ul)
        length = int(900 * p)
        d.line((20, 20, 20 + length, 20), fill=ACCENT, width=12)
        frame.alpha_composite(ul.filter(ImageFilter.GaussianBlur(1.2)), (W // 2 - 470, 500))

    # 보조 문구 2.4s
    if t >= 2.4:
        k = min(1.0, (t - 2.4) / 0.4)
        sub = text_img([("학의 날개처럼 펼쳐진 진형", PAPER, FONT_SUB, 58)], 900, stroke=6)
        sub = alpha_mul(sub, k)
        place_shadow(frame, sub, centered_xy(sub, W // 2, 590 + int((1 - k) * 24)), shadow_alpha=110, blur=8, dy=6)

    if t > 4.6:
        k = max(0.0, 1 - (t - 4.6) / 0.4)
        base = frame.copy()
        frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        frame.paste(alpha_mul(base, k), (0, 0))
    return frame


def overlay_clip4(i: int) -> Image.Image:
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    t = i / FPS
    main = text_img([("한산도 대첩", PAPER, FONT_TITLE, 180)], 940)
    sub = text_img([("바다를 지켜낸 조선 수군", PAPER, FONT_SUB, 58)], 900, stroke=6)

    if t >= 1.0:
        k = min(1.0, (t - 1.0) / 0.7)
        e = 1 - (1 - k) ** 3
        img = alpha_mul(main, e)
        xy = centered_xy(img, W // 2, 400 + int((1 - e) * 34))
        place_shadow(frame, img, xy)

    if t >= 2.2:
        k = min(1.0, (t - 2.2) / 0.5)
        img = alpha_mul(sub, k)
        xy = centered_xy(img, W // 2, 560 + int((1 - k) * 24))
        place_shadow(frame, img, xy, shadow_alpha=110, blur=8, dy=6)
    return frame


OVERLAYS = {
    "clip-01": overlay_clip1,
    "clip-03": overlay_clip3,
    "clip-04": overlay_clip4,
}

SILENT = ["clip-01", "clip-02", "clip-03", "clip-04"]


def build_video() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    segments = []
    for name in SILENT:
        seg = WORK / f"seg-{name}.mp4"
        base = CLIPS / f"{name}-h3.mp4"
        if name in OVERLAYS:
            ov_dir = WORK / f"ov-{name}"
            ov_dir.mkdir(parents=True, exist_ok=True)
            renderer = OVERLAYS[name]
            for i in range(FRAMES):
                renderer(i).save(ov_dir / f"f{i:04d}.png")
            cmd = [
                "ffmpeg", "-v", "error", "-y",
                "-i", str(base), "-framerate", str(FPS), "-i", str(ov_dir / "f%04d.png"),
                "-filter_complex",
                "[0:v]scale=1098:1920,crop=1080:1920:9:0,fps=24,trim=end_frame=%d,setpts=PTS-STARTPTS[bg];"
                "[bg][1:v]overlay=0:0,format=yuv420p[v]" % FRAMES,
                "-map", "[v]", "-frames:v", str(FRAMES),
                "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-r", str(FPS),
                str(seg),
            ]
        else:
            cmd = [
                "ffmpeg", "-v", "error", "-y", "-i", str(base),
                "-filter_complex",
                "[0:v]scale=1098:1920,crop=1080:1920:9:0,fps=24,trim=end_frame=%d,setpts=PTS-STARTPTS,format=yuv420p[v]" % FRAMES,
                "-map", "[v]", "-frames:v", str(FRAMES),
                "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-r", str(FPS),
                str(seg),
            ]
        run(cmd)
        print("segment done:", seg.name)
        segments.append(seg)

    list_file = WORK / "concat.txt"
    list_file.write_text("".join(f"file '{s.as_posix()}'\n" for s in segments), encoding="utf-8")
    silent = OUT / "geobukseon-hansando_video-only.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(silent)])
    print("video-only:", silent)

    sheet = WORK / "contact.png"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-vf",
         "fps=1,scale=270:-1,tile=5x4", str(sheet)])
    print("contact:", sheet)


# ---------------- audio ----------------

def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as fh:
        rate = fh.getframerate()
        data = np.frombuffer(fh.readframes(fh.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        data = data.reshape(-1, fh.getnchannels()).mean(axis=1)
        return data, rate


def write_wav(path: Path, data: np.ndarray, rate: int) -> None:
    data = np.clip(data, -1.0, 1.0)
    pcm = (data * 32767.0).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes(stereo.tobytes())


def whoosh(rate: int, dur: float = 0.5) -> np.ndarray:
    n = int(rate * dur)
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n)
    # 간단한 이동평균 저역 + 진폭 엔벨로프
    k = 48
    kernel = np.ones(k) / k
    filt = np.convolve(noise, kernel, mode="same")
    env = np.exp(-np.linspace(0, 5.5, n)) * (1 - np.exp(-np.linspace(0, 40, n)))
    return filt * env * 0.35


def thud(rate: int, dur: float = 0.6) -> np.ndarray:
    n = int(rate * dur)
    tt = np.arange(n) / rate
    tone = np.sin(2 * math.pi * 86 * tt) * np.exp(-tt * 9)
    click = np.random.default_rng(11).standard_normal(n) * np.exp(-tt * 90) * 0.4
    return (tone * 0.8 + click) * 0.5


def add_at(buf: np.ndarray, sound: np.ndarray, at_sec: float, rate: int, gain: float = 1.0) -> None:
    start = int(at_sec * rate)
    end = min(len(buf), start + len(sound))
    if start >= len(buf):
        return
    buf[start:end] += sound[: end - start] * gain


def build_audio(music_path: Path, offset: float | None) -> None:
    total = FRAMES * 4 / FPS  # 20.0s
    music_rate = 48000
    tmp = WORK / "music-48k.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(music_path), "-ar", str(music_rate), "-ac", "1", str(tmp)])
    music, rate = read_wav(tmp)

    if offset is None:
        win = int(total * rate)
        hop = rate
        rms = np.array([np.sqrt(np.mean(music[i:i + hop] ** 2) + 1e-12) for i in range(0, len(music) - win, hop)])
        head = np.array([np.mean(rms[i:i + 5]) for i in range(0, len(rms) - 19)])
        tail = np.array([np.mean(rms[i + 15:i + 20]) for i in range(0, len(rms) - 19)])
        score = tail - 0.6 * head + 0.15 * (head + tail)
        best = int(np.argmax(score))
        offset = best
        print(f"auto offset: {offset}s (score {score[best]:.4f})")
    offset = max(0.0, min(offset, len(music) / rate - total - 0.05))

    start = int(offset * rate)
    bed = music[start:start + int(total * rate)].copy()
    fade_in = int(0.35 * rate)
    fade_out = int(1.4 * rate)
    bed[:fade_in] *= np.linspace(0, 1, fade_in)
    bed[-fade_out:] *= np.linspace(1, 0, fade_out)
    peak = np.max(np.abs(bed)) or 1.0
    bed = bed / peak * 0.82

    buf = bed.copy()
    add_at(buf, whoosh(rate), 0.10, rate, 0.55)
    add_at(buf, whoosh(rate), 10.12, rate, 0.55)
    add_at(buf, thud(rate), 15.90, rate, 0.7)
    add_at(buf, thud(rate, 0.9), 19.05, rate, 0.5)
    peak = np.max(np.abs(buf)) or 1.0
    buf = buf / peak * 0.95

    mix = WORK / "mix.wav"
    write_wav(mix, buf, rate)
    print("mix:", mix)

    final = OUT / "geobukseon-hansando_v1.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(OUT / "geobukseon-hansando_video-only.mp4"),
         "-i", str(mix), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)])
    print("final:", final)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["video", "audio"])
    parser.add_argument("--music", type=Path)
    parser.add_argument("--offset", type=float, default=None)
    args = parser.parse_args()
    if args.phase == "video":
        build_video()
    else:
        if not args.music:
            parser.error("--music 필요")
        build_audio(args.music, args.offset)


if __name__ == "__main__":
    main()
