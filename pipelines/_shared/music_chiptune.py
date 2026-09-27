"""8-bit game-style bed (chiptune), 150 BPM, synthesized locally.

Pulse-wave lead hook, 12.5 % pulse arpeggios, triangle bass, noise drums. A count-in of rising
blips, a power-up stinger on every freeze, and a victory fanfare at the end.
"""
import wave

import numpy as np

SR = 48000
_rng = np.random.default_rng(21)

# I–V–vi–IV in C, one chord per bar (bar = 4 beats)
CHORDS = [(48, [60, 64, 67]), (43, [55, 59, 62]), (45, [57, 60, 64]), (41, [53, 57, 60])]
# lead hook on an 8th-note grid over 4 bars (32 steps); None = rest
HOOK = [72, None, 76, 79, None, 76, 74, 72,
        71, None, 74, 79, None, 74, 71, 67,
        69, None, 72, 76, None, 72, 71, 69,
        65, 67, 69, 72, None, 74, 76, None]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def add(track, t, sig, gain=1.0):
    s = int(round(t * SR))
    if s < 0 or s >= len(track):
        return
    n = min(len(sig), len(track) - s)
    track[s:s + n] += sig[:n] * gain


def pulse(m, length, duty=0.5, decay=6.0, vib=0.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    f = hz(m) * (1 + vib * np.sin(2 * np.pi * 6 * t) * np.minimum(t / 0.15, 1))
    ph = np.cumsum(f) / SR % 1.0
    wave_ = np.where(ph < duty, 1.0, -1.0)
    wave_ = np.convolve(wave_, np.ones(3) / 3, mode='same')     # tame aliasing a little
    env = np.minimum(t / 0.003, 1) * np.exp(-t * decay)
    return wave_ * env


def triangle(m, length, decay=3.0):
    n = int(length * SR)
    t = np.arange(n) / SR
    ph = hz(m) * t % 1.0
    tri = 4 * np.abs(ph - 0.5) - 1
    return tri * np.minimum(t / 0.004, 1) * np.exp(-t * decay)


def noise_hit(length, decay, lp=1):
    n = int(length * SR)
    x = _rng.choice([-1.0, 1.0], n)                             # NES-style 1-bit noise
    if lp > 1:
        x = np.convolve(x, np.ones(lp) / lp, mode='same')
    return x * np.exp(-np.arange(n) / SR * decay)


def kick():
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    f = 50 + 180 * np.exp(-t * 40)
    ph = np.cumsum(f) / SR % 1.0
    return (4 * np.abs(ph - 0.5) - 1) * np.exp(-t * 14)


def build(path, dur, beat=0.4, intro=1.6, freezes=(), end=None, stinger_gain=0.3, coin=None):
    track = np.zeros(int((dur + 2) * SR))
    e8 = beat / 2
    e16 = beat / 4

    # count-in: three blips on the beats before the downbeat, then a rising 'bwoop'
    for k in range(3):
        add(track, intro - beat * (4 - k), pulse(72, 0.08, 0.5, 30), 0.22)
    n = int(beat * SR)
    t = np.arange(n) / SR
    sweep = np.where((np.cumsum(np.linspace(hz(60), hz(84), n)) / SR % 1.0) < 0.5, 1.0, -1.0)
    add(track, intro - beat, sweep * (t / beat) * 0.8, 0.2)

    end = end if end is not None else dur
    s = 0
    while True:
        tt = intro + s * e16
        if tt >= end - 1e-6:
            break
        bar = int(s // 16) % 4
        root, chord = CHORDS[bar]
        p16 = s % 16
        # drums
        if p16 in (0, 8):
            add(track, tt, kick(), 0.9)
        if p16 in (4, 12):
            add(track, tt, noise_hit(0.14, 18, lp=2), 0.32)
        if p16 % 2 == 0:
            add(track, tt, noise_hit(0.03, 90), 0.07)
        # triangle bass on 8ths, root/octave
        if p16 % 2 == 0:
            add(track, tt, triangle(root + (12 if (p16 // 2) % 2 else 0), e8 * 0.95, 4), 0.5)
        # arpeggio: 12.5 % pulse, 16ths through chord tones
        add(track, tt, pulse(chord[p16 % 3] + 12, e16 * 0.9, 0.125, 14), 0.07)
        # lead hook on 8ths
        if s % 2 == 0:
            step = int(s // 2) % 32
            m = HOOK[step]
            if m is not None:
                add(track, tt, pulse(m, e8 * 1.6, 0.5, 5, vib=0.004), 0.16)
        s += 1

    # power-up stinger on every freeze (quick rising arpeggio)
    for ft in freezes:
        for k, m in enumerate([72, 76, 79, 84, 88]):
            add(track, ft + k * 0.035, pulse(m, 0.09, 0.25, 22), stinger_gain * (0.6 + 0.1 * k))

    # victory fanfare
    if end < dur:
        for k, m in enumerate([72, 76, 79]):
            add(track, end + k * e16, pulse(m, e16 * 0.95, 0.5, 8), 0.2)
        add(track, end + 3 * e16, pulse(84, 1.4, 0.5, 2.2, vib=0.008), 0.22)
        add(track, end + 3 * e16, pulse(76, 1.4, 0.25, 2.2), 0.12)
        add(track, end + 3 * e16, triangle(48, 1.4, 2.0), 0.55)
        add(track, end + 3 * e16, kick(), 1.0)
        add(track, end + 3 * e16, noise_hit(0.6, 5, lp=3), 0.2)

    # classic 'coin' pickup to close the outro gap and lead back into the loop
    if coin is not None:
        add(track, coin, pulse(83, 0.07, 0.5, 10), 0.24)
        add(track, coin + 0.07, pulse(88, 0.5, 0.5, 5), 0.24)
        for k in range(3):   # soft count-in echo so the loop re-enters on the beat
            add(track, dur - beat * (3 - k), pulse(72, 0.08, 0.5, 30), 0.14)

    track = track[:int(dur * SR)]
    body = track[int(intro * SR):int(end * SR)]
    track *= 0.17 / np.sqrt(np.mean(body ** 2))
    track = np.tanh(track) * 0.97
    pcm = (track * 32767).astype(np.int16)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path
