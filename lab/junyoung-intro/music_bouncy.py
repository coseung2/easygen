"""Bouncy comedic 120 BPM bed, synthesized locally and locked to the launch video's cut grid.

Oom-pah groove: kick + tuba-ish bass on beats 1/3, clap + ukulele strum on 2/4, offbeat hats,
and a marimba hook over C–Am–F–G. Gags: snare roll + slide whistle into the reveal, a record
scratch and silence before the fart hit, a crash when the groove drops back in, and a ta-da.
"""
import wave

import numpy as np

SR = 48000
_rng = np.random.default_rng(11)
_cache = {}

CHORDS = [(48, [60, 64, 67, 72]), (45, [57, 60, 64, 69]), (41, [57, 60, 65, 69]), (43, [55, 59, 62, 67])]
MELODY = {0: 76, 1: 79, 2: 81, 3: 79, 4: 76, 6: 72,
          8: 72, 9: 74, 10: 76, 12: 74, 13: 72, 14: 69,
          16: 77, 17: 76, 18: 74, 19: 72, 20: 74, 22: 77,
          24: 79, 25: 81, 26: 79, 27: 77, 28: 74, 30: 79, 31: 83}


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def add(track, t, sig, gain=1.0):
    s = int(round(t * SR))
    if s < 0 or s >= len(track):
        return
    n = min(len(sig), len(track) - s)
    track[s:s + n] += sig[:n] * gain


def smooth(x, k):
    return np.convolve(x, np.ones(k) / k, mode='same')


def kick():
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 10)


def clap():
    n = int(0.2 * SR)
    noise = _rng.standard_normal(n)
    band = smooth(noise, 3) - smooth(noise, 28)
    t = np.arange(n) / SR
    env = np.zeros(n)
    for off, rate in ((0, 60), (0.011, 60), (0.022, 22)):
        env += (t >= off) * np.exp(-np.maximum(t - off, 0) * rate)
    return band * env * 1.4


def hat(length=0.05):
    n = int(length * SR)
    noise = _rng.standard_normal(n)
    return (noise - smooth(noise, 6)) * np.exp(-np.arange(n) / SR * 70)


def crash():
    n = int(1.4 * SR)
    noise = _rng.standard_normal(n)
    return (noise - smooth(noise, 4)) * np.exp(-np.arange(n) / SR * 3.2) * 0.8


def bass(m, length=0.42):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(m)
    tone = np.sin(2 * np.pi * f * t) + 0.45 * np.sin(4 * np.pi * f * t) + 0.18 * np.sin(6 * np.pi * f * t)
    return tone * np.minimum(t / 0.006, 1) * np.exp(-t * 6.5)


def marimba(m, length=0.38):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(m)
    tone = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 30)
    return tone * np.minimum(t / 0.002, 1) * np.exp(-t * 9)


def pluck(m, length=0.6, decay=0.994):
    """Karplus–Strong string, ukulele-like."""
    key = (m, length, decay)
    if key in _cache:
        return _cache[key]
    n = int(length * SR)
    p = max(2, int(round(SR / hz(m))))
    buf = list(np.random.default_rng(m).uniform(-1, 1, p))
    out = np.empty(n)
    for i in range(n):
        j = i % p
        v = buf[j]
        out[i] = v
        buf[j] = decay * 0.5 * (v + buf[(j + 1) % p])
    out *= np.minimum(np.arange(n) / SR / 0.003, 1)
    _cache[key] = out
    return out


def strum(track, t, notes, gain, length=0.6, decay=0.994):
    for k, m in enumerate(notes):
        add(track, t + k * 0.012, pluck(m, length, decay), gain / len(notes) * 1.6)


def slide_whistle(t0, t1):
    n = int((t1 - t0) * SR)
    t = np.arange(n) / SR
    k = t / (t1 - t0)
    f = 600 * 3 ** k * (1 + 0.02 * np.sin(2 * np.pi * 7 * t))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.3 + 0.7 * k)


def scratch():
    n = int(0.24 * SR)
    t = np.arange(n) / SR
    noise = _rng.standard_normal(n)
    band = smooth(noise, 2) - smooth(noise, 12)
    sweep = np.sin(2 * np.pi * np.cumsum(np.linspace(1300, 160, n)) / SR)
    env = np.sin(np.pi * t / 0.24) ** 0.5
    return (band * 0.7 + sweep * 0.6) * env


def tape_stop(track, t0, t1):
    """Slow the music to a halt between t0 and t1 (pitch and speed fall together, 'uuung~')."""
    i0, n = int(t0 * SR), int((t1 - t0) * SR)
    L = t1 - t0
    tau = np.arange(n) / SR
    pos = tau - tau ** 2 / (2 * L)            # speed ramps 1 -> 0
    src = i0 + pos * SR
    warped = np.interp(src, np.arange(len(track)), track)
    fade = np.ones(n)
    k = int(0.04 * SR)
    fade[-k:] = np.linspace(1, 0, k)
    track[i0:i0 + n] = warped * fade


def build(path, dur, groove_start=2.0, tapestop=(10.5, 11.0), resume=12.0, burst=(16.0, 19.0), tada=21.0,
          tag=None):
    track = np.zeros(int((dur + 2) * SR))

    # intro: ding, snare roll and slide whistle up into the reveal
    add(track, 0.0, marimba(84, 0.8), 0.35)
    add(track, 0.0, marimba(88, 0.8), 0.25)
    t = 0.5
    while t < groove_start - 1e-6:
        add(track, t, clap(), 0.08 + 0.25 * (t - 0.5))
        t += 0.25 if t < 1.0 else (0.125 if t < 1.5 else 0.0625)
    add(track, 1.35, slide_whistle(1.35, groove_start), 0.22)
    add(track, groove_start, crash(), 0.35)

    # groove on an 8th-note grid
    s = 0
    while True:
        t = groove_start + s * 0.25
        if t >= tada - 1e-6:
            break
        pos, bar, e = s % 8, (s // 8) % 4, s % 32
        root, chord = CHORDS[bar]
        in_burst = burst[0] <= t < burst[1]
        if tapestop is None or not (tapestop[1] <= t < resume):
            if pos in (0, 4):
                add(track, t, kick(), 0.85)
                add(track, t, bass(root if pos == 0 else root + 7), 0.5)
            if pos in (2, 6):
                add(track, t, clap(), 0.32)
                strum(track, t, chord, 0.4)
            if pos == 7:
                strum(track, t, chord, 0.22)
            if s % 2 == 1:
                add(track, t, hat(), 0.10)
            if e in MELODY:
                add(track, t, marimba(MELODY[e] + (12 if in_burst else 0)), 0.30)
            if in_burst:
                add(track, t + 0.125, hat(0.03), 0.08)
        s += 1

    # fart gag: the groove winds down like a tape stopping, the fart owns the silent bar,
    # then the groove drops back in on the downbeat with a crash
    if tapestop is not None:
        tape_stop(track, *tapestop)
        track[int(tapestop[1] * SR):int(resume * SR)] = 0
        add(track, resume, crash(), 0.3)
    add(track, burst[0], crash(), 0.25)

    # ta-da
    for k, m in enumerate([72, 76, 79]):
        add(track, tada - 0.375 + k * 0.125, marimba(m), 0.30)
    add(track, tada, kick(), 1.0)
    add(track, tada, crash(), 0.4)
    add(track, tada, bass(36, 1.0), 0.6)
    strum(track, tada, [60, 64, 67, 72, 76], 0.7, length=1.4, decay=0.997)
    add(track, tada, marimba(84, 1.2), 0.35)

    # 'shave and a haircut… two bits' tag to close on a laugh
    if tag is not None:
        for off, m in ((0, 72), (0.25, 67), (0.375, 67), (0.5, 69), (0.75, 67), (1.25, 71), (1.5, 72)):
            strum(track, tag + off, [m, m + 7], 0.5, length=0.35)
            add(track, tag + off, marimba(m + 12, 0.3), 0.22)
        add(track, tag + 1.25, kick(), 0.7)
        add(track, tag + 1.5, kick(), 0.9)
        add(track, tag + 1.5, clap(), 0.35)

    track = track[:int(dur * SR)]
    active = track[int(groove_start * SR):int(tada * SR)]
    track *= 0.16 / np.sqrt(np.mean(active ** 2))
    track = np.tanh(track) * 0.97
    pcm = (track * 32767).astype(np.int16)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path
