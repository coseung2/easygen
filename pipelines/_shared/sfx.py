"""Synthesized sound effects shared by the local-python templates (all offline, no samples)."""
from __future__ import annotations

import wave

import numpy as np

SR = 48000


class Track:
    def __init__(self, seconds, seed=9):
        self.buf = np.zeros(int((seconds + 1) * SR), np.float32)
        self.rng = np.random.default_rng(seed)

    def put(self, t, sig, gain=1.0):
        s = int(round(t * SR))
        if s < 0 or s >= len(self.buf):
            return
        n = min(len(sig), len(self.buf) - s)
        self.buf[s:s + n] += (sig[:n] * gain).astype(np.float32)

    # ---------- primitives ----------
    def pop(self, t, f0=900, f1=300, length=0.09, gain=0.3, decay=40):
        n = int(length * SR)
        tt = np.arange(n) / SR
        self.put(t, np.sin(2 * np.pi * np.cumsum(np.linspace(f0, f1, n)) / SR) * np.exp(-tt * decay), gain)

    def blip(self, t, midi, length=0.11, gain=0.16):
        n = int(length * SR)
        tt = np.arange(n) / SR
        f = 440 * 2 ** ((midi - 69) / 12)
        tone = np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)
        self.put(t, tone * np.minimum(tt / 0.003, 1) * np.exp(-tt * 28), gain)

    def shutter(self, t, gain=1.0):
        for off, dec, g in ((0, 34, 0.5), (0.05, 24, 0.32)):
            n = int(0.07 * SR)
            noise = self.rng.standard_normal(n)
            click = (noise - np.convolve(noise, np.ones(5) / 5, 'same')) * np.exp(-np.arange(n) / SR * dec)
            self.put(t + off, click, g * gain)

    def whoosh(self, t, length=0.28, gain=0.12, f0=260, f1=1700, tone=0.0):
        n = int(length * SR)
        noise = np.convolve(self.rng.standard_normal(n), np.ones(8) / 8, 'same')
        sweep = np.sin(2 * np.pi * np.cumsum(np.linspace(f0, f1, n)) / SR)
        env = np.sin(np.pi * np.arange(n) / n) ** 2
        self.put(t, (noise * (1 - tone) + sweep * tone) * env, gain)

    def ting(self, t, gain=0.18):
        n = int(0.5 * SR)
        tt = np.arange(n) / SR
        self.put(t, (np.sin(2 * np.pi * 2600 * tt) + 0.6 * np.sin(2 * np.pi * 3900 * tt)) * np.exp(-tt * 9), gain)

    def fart_body(self, t, gain=0.32):
        """Short low 'ppuung' laid under a real fart so it reads on phone speakers."""
        n = int(0.42 * SR)
        tt = np.arange(n) / SR
        f0 = 118 * (1 - 0.35 * tt / 0.42) * (1 + 0.06 * np.sin(2 * np.pi * 23 * tt))
        ph = 2 * np.pi * np.cumsum(f0) / SR
        buzz = np.sign(np.sin(ph)) * 0.5 + np.sin(ph) * 0.5 + 0.25 * np.sin(2 * ph)
        buzz = np.convolve(buzz, np.ones(10) / 10, mode='same')
        self.put(t, buzz * np.minimum(tt / 0.012, 1) * np.exp(-tt * 4.5), gain)

    def counter(self, t0, t1, steps, inverse_ease, notes, length=0.11, base=0.12, rise=0.06):
        """One blip per counter step, timed by the inverse of the counter's easing."""
        for j in range(1, steps + 1):
            k = j / steps
            self.blip(t0 + (t1 - t0) * inverse_ease(k), notes[min(j - 1, len(notes) - 1)], length,
                      base + rise * k)

    def riser(self, t0, t1, ease, gain=0.05):
        n = int((t1 - t0) * SR)
        ramp = np.array([ease(x) for x in np.linspace(0, 1, n)])
        self.put(t0, np.sin(2 * np.pi * np.cumsum(260 + 900 * ramp) / SR) * ramp, gain)

    def chime(self, t, notes=(84, 88, 91, 96), step=0.07, gain=0.2):
        for k, m in enumerate(notes):
            self.blip(t + k * step, m, length=0.5, gain=gain)

    def typewriter(self, t0, t1, count, gain=0.05):
        for c in range(count):
            self.pop(t0 + c * (t1 - t0) / max(1, count), 2400, 2200, 0.02, gain)

    def save(self, path):
        pcm = (np.clip(self.buf, -1, 1) * 32767).astype(np.int16)
        with wave.open(str(path), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        return path
