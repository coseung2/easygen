"""V5 soundtrack: local synthesis that follows the picture's timing map (DESIGN.md §4).

Energy: rule (tick->hit) / rotor (slow mechanical steps) / crib (stepped, dissonance on contradictions)
/ Bombe (accelerating ticks) / STOP (hard silence) / decode (plucks) / route (warm expansion) / callback.
"""
from pathlib import Path
import json, wave
import numpy as np

R = Path(__file__).resolve().parent
SR = 48000
DUR = 60.0
N = int(DUR * SR)
buf = np.zeros((N, 2), np.float32)
rng = np.random.default_rng(29092026)


def add(t, z, gain=1.0, pan=0.0):
    a = int(t * SR)
    b = min(a + len(z), N)
    if a < 0 or b <= a:
        return
    z = z[: b - a] * gain
    buf[a:b, 0] += z * np.sqrt((1 - pan) / 2)
    buf[a:b, 1] += z * np.sqrt((1 + pan) / 2)


def tt(d):
    return np.arange(int(d * SR)) / SR


def kick(d=.35):
    t = tt(d)
    return np.sin(2 * np.pi * (44 * t + 3.2 * (1 - np.exp(-t * 30)))) * np.exp(-t * 11)


def click(d=.03, hz=1800):
    t = tt(d)
    return (rng.normal(0, 1, len(t)) * .55 + np.sin(2 * np.pi * hz * t) * .35) * np.exp(-t * 140)


def tone(hz, d, att=.005, dec=5.0, bright=.2):
    t = tt(d)
    return (np.sin(2 * np.pi * hz * t) + bright * np.sin(2 * np.pi * hz * 2.003 * t)) * np.minimum(t / att, 1) * np.exp(-t * dec)


def pad(hz, d, att=.6):
    t = tt(d)
    env = np.minimum(t / att, 1) * np.minimum((d - t) / .5, 1).clip(0, 1)
    z = sum(np.sin(2 * np.pi * hz * m * t + p) / (i + 1) for i, (m, p) in enumerate([(1, 0), (1.004, 1), (2, 2), (3.01, .5)]))
    return z * env


def swell(d, up=True):
    t = tt(d)
    z = np.convolve(rng.normal(0, 1, len(t)), np.ones(24) / 24, mode='same')
    e = (t / d) ** 2 if up else (1 - t / d) ** 2
    return z * e


def buzz(d=.5):
    t = tt(d)
    return (np.sign(np.sin(2 * np.pi * 110 * t)) * .3 + np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 466.2 * t)) * np.exp(-t * 4) * .5


# ---- S1 rule 0–5
t, dt = .7, .06
while t < 2.62:
    add(t, click(.025, 2400), .22, float(np.sin(t * 9)) * .4)
    t += dt; dt *= 1.14
add(2.85, kick(.6), .55)
add(2.85, tone(880, .9, dec=3), .12)
add(2.85, tone(1318.5, .9, dec=3.5), .06, .3)
add(3.4, tone(55, 1.6, att=.03, dec=1.5), .22)
add(4.7, swell(1.3), .10, -.2)
# ---- S2 rotor 5–11: drone + a mechanical click per step
add(5.8, pad(55, 5.2, att=1.0), .07)
t = 6.4
for k in range(26):
    d = .10 + .10 * abs(k - 12.5) / 12.5
    add(t + d * .6, click(.02, 1300), .18, float(np.sin(k)) * .3)
    t += d
add(7.6, tone(220, 1.2, dec=2.5), .05)
add(10.4, swell(1.4), .16)
# ---- S3 crib 11.5–20: pulse, slides, contradiction buzz, pass chord
add(12.0, kick(.5), .35)
for i in range(8):
    add(12.0 + i * .05, click(.02, 2000), .10)
for t0 in (12.7, 14.9, 16.05):
    add(t0, swell(.45), .09, .3)
add(13.7, buzz(.7), .20)
add(15.4, buzz(.55), .22)
for hz in (293.66, 369.99, 440.0):
    add(16.45, tone(hz, 1.6, dec=1.8), .06)
for b in np.arange(12.0, 19.5, .5):
    add(b, kick(.25), .12)
# ---- S4 Bombe 19.4–32.8: accelerating ticks, rising drone
t, gap = 20.6, .25
while t < 32.8:
    u = (t - 20.6) / 12.2
    add(t, click(.018, 1500 + 900 * u), .10 + .08 * u, float(np.sin(t * 7)) * .5)
    t += max(.045, gap * (1 - u) ** 1.3)
seg = tt(32.8 - 19.6)
f = 55 * (1 + seg / (32.8 - 19.6)) ** 1.0
drone = np.sin(2 * np.pi * np.cumsum(f) / SR) + .3 * np.sin(2 * np.pi * 2 * np.cumsum(f) / SR)
add(19.6, drone * np.minimum(seg / 1.5, 1) * .09)
for b in np.arange(20.5, 32.7, .5):
    add(b, kick(.28), .20)
# elimination blips follow the picture (last two exact)
for te in (31.4, 32.1):
    add(te, tone(660, .2, dec=12), .08)
# ---- STOP 32.8: hard cut, one click, silence
stop = int(32.8 * SR)
buf[stop:int(35.8 * SR)] = 0
add(32.8, click(.04, 900), .45)
add(32.8, tone(880, 1.2, dec=2.2), .08)
# ---- S6 decode 35.9–41
add(35.9, tone(440, 1.0, dec=3), .08)
for i in range(6):
    add(37.0 + i * .22 + .08, tone([587.33, 659.25, 698.46, 783.99, 880, 987.77][i], .5, dec=6), .07, (i - 2.5) / 4)
for k in range(10):
    add(38.9 + (k + 1) * .045, click(.015, 2600), .07)
add(36.0, pad(73.42, 5.0, att=1.5), .05)
# ---- S7 chart/route 41–53.5: expansion, lift at the route change
add(41.3, kick(.6), .35)
add(41.3, pad(73.42, 4.2, att=.8), .08)   # D
add(45.2, swell(.8, up=True), .10)
add(45.9, pad(87.31, 4.6, att=.4), .09)   # F — the route turns
add(50.6, pad(98.0, 3.2, att=.4), .08)    # G
for b in np.arange(41.3, 53.2, .5):
    add(b, kick(.3), .16 if b < 45.9 else .22)
mel = [587.33, 698.46, 880, 783.99, 698.46, 659.25, 587.33, 523.25]
for i, b in enumerate(np.arange(46.0, 53.0, .5)):
    add(b, tone(mel[i % len(mel)], .7, dec=3.5), .045, float(np.sin(i)) * .4)
add(50.8, tone(146.83, 2.0, dec=1.2), .10)
# ---- S8 callback 53–60
add(53.4, swell(1.2, up=False), .06)
add(55.2, kick(.6), .45)
add(55.2, tone(880, 1.2, dec=2.5), .10)
add(55.2, tone(1318.5, 1.2, dec=3), .05, .3)
add(55.6, pad(55, 4.3, att=.6), .08)
for hz in (293.66, 349.23, 440.0):
    add(57.4, tone(hz, 2.6, dec=.9), .05)

delay = int(.17 * SR)
buf[delay:] += buf[:-delay].copy() * .12
buf[stop:stop + int(.05 * SR)] *= 1.0
buf[int(32.84 * SR):int(35.8 * SR)] *= np.linspace(1, 0, int(35.8 * SR) - int(32.84 * SR))[:, None] ** 8  # keep only the stop click tail
buf *= .82 / max(float(np.abs(buf).max()), .82)
buf[-SR:] *= np.linspace(1, 0, SR)[:, None]
with wave.open(str(R / 'soundtrack.wav'), 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((buf * 32767).astype('<i2').tobytes())
(R / 'soundtrack.json').write_text(json.dumps({
    'type': 'original local synthesis, cues aligned to DESIGN.md timing map', 'seconds': DUR,
    'seed': 29092026, 'external_samples': False, 'speech': False,
    'stop_silence': [32.84, 35.8]}, indent=2), encoding='utf-8')
print('soundtrack.wav written')
