"""Synthesize a beat-aligned SFX layer for the 21-enigma episode and mix it with the music."""

from __future__ import annotations

import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from lab_paths import series_path

EP = series_path("21-enigma-turing")
SR = 48000
DUR = 30.0
G0, STEP = 0.1, 0.5


def grid(k: int) -> float:
    return round(G0 + STEP * k, 3)


def tick(amp: float = 0.18) -> np.ndarray:
    n = int(0.02 * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(7).standard_normal(n) * np.exp(-t / 0.003)
    tone = np.sin(2 * math.pi * 1400 * t) * np.exp(-t / 0.004)
    return amp * (0.6 * noise + 0.8 * tone)


def thump(amp: float = 0.5) -> np.ndarray:
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * math.pi * 54 * t) * np.exp(-t / 0.13)
    click = np.random.default_rng(3).standard_normal(n) * np.exp(-t / 0.006) * 0.25
    return amp * (body + click)


def clunk(amp: float = 0.45) -> np.ndarray:
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    body = (
        0.6 * np.sin(2 * math.pi * 150 * t)
        + 0.3 * np.sin(2 * math.pi * 730 * t)
        + 0.2 * np.sin(2 * math.pi * 1500 * t)
    ) * np.exp(-t / 0.09)
    return amp * body


def chime(amp: float = 0.3) -> np.ndarray:
    n = int(2.6 * SR)
    t = np.arange(n) / SR
    body = (
        0.5 * np.sin(2 * math.pi * 880 * t)
        + 0.3 * np.sin(2 * math.pi * 1320 * t)
        + 0.2 * np.sin(2 * math.pi * 1760 * t)
    ) * np.exp(-t / 0.9)
    return amp * body


def place(buf: np.ndarray, sound: np.ndarray, at: float) -> None:
    i = int(at * SR)
    end = min(len(buf), i + len(sound))
    if end > i:
        buf[i:end] += sound[: end - i]


def main() -> None:
    buf = np.zeros(int(DUR * SR))
    for k in range(int(round((DUR - G0) / STEP))):
        amp = 0.18 if grid(k) < 25.1 else 0.10
        place(buf, tick(amp), grid(k))
    for boundary in (0.1, 5.1, 10.1, 15.1, 20.1, 25.1):
        place(buf, thump(), boundary)
    place(buf, clunk(), 22.6)
    place(buf, chime(), 28.6)
    peak = float(np.max(np.abs(buf)) or 1.0)
    if peak > 0.95:
        buf *= 0.95 / peak
    data = np.int16(np.clip(buf, -1.0, 1.0) * 32767)
    stereo = np.column_stack([data, data])
    sfx_path = EP / "music" / "sfx.wav"
    with wave.open(str(sfx_path), "wb") as fh:
        fh.setnchannels(2)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes(stereo.tobytes())

    mix_path = EP / "ae" / "music-mix-30s.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(EP / "ae" / "music-30s.wav"),
            "-i", str(sfx_path),
            "-filter_complex",
            "[0:a]volume=0.85[m];[1:a]volume=1.0[s];[m][s]amix=inputs=2:duration=first:normalize=0",
            "-ar", str(SR), "-ac", "2", str(mix_path),
        ],
        check=True,
    )
    print(f"sfx written: {sfx_path}")
    print(f"mix written: {mix_path}")


if __name__ == "__main__":
    main()
