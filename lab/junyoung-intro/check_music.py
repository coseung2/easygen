"""Loudness per half-second and a waveform + spectrogram image, to verify groove, drop-out and ta-da."""
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from lab_paths import font_path

path, out = sys.argv[1], sys.argv[2]
with wave.open(path) as w:
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if w.getnchannels() == 2:
        x = x.reshape(-1, 2).mean(axis=1)
step = sr // 2
rms = [20 * np.log10(np.sqrt(np.mean(x[i:i + step] ** 2)) + 1e-6) for i in range(0, len(x), step)]
print(' '.join(f'{i * 0.5:.1f}:{v:.0f}' for i, v in enumerate(rms)))
print('peak', round(float(np.abs(x).max()), 3), 'len', round(len(x) / sr, 2))

Wd, Hd = 1800, 520
img = Image.new('RGB', (Wd, Hd), (18, 18, 20))
d = ImageDraw.Draw(img)
font = ImageFont.truetype(str(font_path('consola.ttf', 'CascadiaMono.ttf')), 16)
cols = np.array_split(x, Wd)
for i, c in enumerate(cols):
    a = float(np.abs(c).max()) if len(c) else 0
    d.line((i, 130 - a * 120, i, 130 + a * 120), fill=(200, 246, 64))
n = 2048
hop = max(1, (len(x) - n) // Wd)
spec = np.zeros((Hd - 280, Wd))
win = np.hanning(n)
for i in range(Wd):
    seg = x[i * hop:i * hop + n]
    if len(seg) < n:
        break
    mag = np.abs(np.fft.rfft(seg * win))[:600]
    col = 20 * np.log10(mag + 1e-6)
    spec[:, i] = np.interp(np.linspace(0, 599, Hd - 280), np.arange(600), col)[::-1]
spec = np.clip((spec + 20) / 70, 0, 1)
img.paste(Image.fromarray((spec * 255).astype(np.uint8)).convert('RGB'), (0, 280))
dur = len(x) / sr
for s in range(0, int(dur) + 1):
    xx = s / dur * Wd
    d.line((xx, 0, xx, 270), fill=(80, 80, 90))
    d.text((xx + 2, 250), str(s), font=font, fill='white')
img.save(out)
