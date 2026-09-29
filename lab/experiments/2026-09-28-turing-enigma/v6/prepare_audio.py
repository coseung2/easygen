"""V6 soundtrack: local synthesis following the V6 timing map (72.5 s).

Hook (tick->hit, gap opens) / rotor steps + wiring plucks / crib (stepped, buzz on contradictions)
/ checklist demo (two slow tests) / Bombe (accelerating ticks) / STOP (silence) / human check
(two dull results, one bright) / route (warm lift) / callback.
"""
from pathlib import Path
import json, wave
import numpy as np

R = Path(__file__).resolve().parent
SR = 48000
DUR = 72.5
N = int(DUR * SR)
buf = np.zeros((N, 2), np.float32)
rng = np.random.default_rng(29092026)
OFF = 12.6  # map/callback cues = v5 times + OFF


def add(t, z, gain=1.0, pan=0.0):
    a = int(t * SR); b = min(a + len(z), N)
    if a < 0 or b <= a:
        return
    z = z[: b - a] * gain
    buf[a:b, 0] += z * np.sqrt((1 - pan) / 2); buf[a:b, 1] += z * np.sqrt((1 + pan) / 2)


def tt(d): return np.arange(int(d * SR)) / SR
def kick(d=.35): t = tt(d); return np.sin(2 * np.pi * (44 * t + 3.2 * (1 - np.exp(-t * 30)))) * np.exp(-t * 11)
def click(d=.03, hz=1800): t = tt(d); return (rng.normal(0, 1, len(t)) * .55 + np.sin(2 * np.pi * hz * t) * .35) * np.exp(-t * 140)
def tone(hz, d, att=.005, dec=5.0, bright=.2):
    t = tt(d); return (np.sin(2 * np.pi * hz * t) + bright * np.sin(2 * np.pi * hz * 2.003 * t)) * np.minimum(t / att, 1) * np.exp(-t * dec)
def pad(hz, d, att=.6):
    t = tt(d); env = np.minimum(t / att, 1) * np.minimum((d - t) / .5, 1).clip(0, 1)
    return sum(np.sin(2 * np.pi * hz * m * t + p) / (i + 1) for i, (m, p) in enumerate([(1, 0), (1.004, 1), (2, 2), (3.01, .5)])) * env
def swell(d, up=True):
    t = tt(d); z = np.convolve(rng.normal(0, 1, len(t)), np.ones(24) / 24, mode='same'); return z * ((t / d) ** 2 if up else (1 - t / d) ** 2)
def buzz(d=.5):
    t = tt(d); return (np.sign(np.sin(2 * np.pi * 110 * t)) * .3 + np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 466.2 * t)) * np.exp(-t * 4) * .5
def dull(d=.4):
    t = tt(d); return np.sin(2 * np.pi * 180 * t) * np.exp(-t * 9) * .8


# ---- S1 hook 0–5.6
t, dt = .7, .06
while t < 2.62:
    add(t, click(.025, 2400), .22, float(np.sin(t * 9)) * .4); t += dt; dt *= 1.14
add(2.85, kick(.6), .55); add(2.85, tone(880, .9, dec=3), .12); add(2.85, tone(1318.5, .9, dec=3.5), .06, .3)
add(3.15, swell(.4), .08); add(3.5, tone(55, 1.8, att=.03, dec=1.2), .24); add(3.5, tone(659.25, 1.2, dec=2.5), .05)
add(4.5, swell(.4, up=False), .06); add(5.1, swell(1.2), .10, -.2)
# ---- S2 rotor + wiring 5.9–16.3
add(6.1, pad(55, 8.6, att=1.0), .07)
t = 6.7
for k in range(26):
    d = .08 + .08 * abs(k - 12.5) / 12.5; add(t + d * .6, click(.02, 1300), .17, float(np.sin(k)) * .3); t += d
add(10.1, tone(880, 1.4, dec=2.2), .08)  # A->K
for i in range(12):
    add(11.0 + i * .1, tone([440, 523.25, 587.33, 659.25][i % 4], .5, dec=6), .035, (i - 6) / 8)
add(12.4, tone(220, 1.6, dec=2), .05)
add(14.4, tone(1318.5, .4, dec=6), .05)
add(14.7, swell(1.4), .16)
# ---- S3 crib 15.8–23.4
add(16.3, kick(.5), .35)
for i in range(8): add(16.3 + i * .05, click(.02, 2000), .10)
for t0 in (17.6, 19.8, 20.95): add(t0, swell(.45), .09, .3)
add(18.6, buzz(.7), .20); add(20.3, buzz(.55), .22)
for hz in (293.66, 369.99, 440.0): add(21.35, tone(hz, 1.6, dec=1.8), .06)
for b in np.arange(16.3, 23.5, .5): add(b, kick(.25), .12)
# ---- S4 checklist demo 23.4–29.4
for i in range(6): add(23.2 + i * .06, click(.02, 2200), .08)
add(24.3, swell(.6), .06)
add(25.9, click(.04, 1100), .25)      # setting 1
add(26.3, tone(660, .3, dec=8), .07)  # W->X holds
add(26.8, buzz(.45), .18)             # E->P fails
add(27.6, click(.04, 1100), .25)      # setting 2
add(27.9, buzz(.4), .18)              # W->X fails
add(28.3, tone(110, 1.2, dec=2), .12)
# ---- Bombe spin 29.4–41.6
t, gap = 29.4, .25
while t < 41.6:
    u = (t - 29.4) / 12.2
    add(t, click(.018, 1500 + 900 * u), .10 + .08 * u, float(np.sin(t * 7)) * .5); t += max(.045, gap * (1 - u) ** 1.3)
seg = tt(41.6 - 28.6); f = 55 * (1 + seg / (41.6 - 28.6))
add(28.6, (np.sin(2 * np.pi * np.cumsum(f) / SR) + .3 * np.sin(4 * np.pi * np.cumsum(f) / SR)) * np.minimum(seg / 1.5, 1) * .09)
for b in np.arange(29.5, 41.5, .5): add(b, kick(.28), .20)
# ---- STOP 41.6–44.4
stop = int(41.6 * SR); buf[stop:int(44.4 * SR)] = 0
add(41.6, click(.04, 900), .45); add(41.6, tone(880, 1.2, dec=2.2), .08)
# ---- S6 human check 44.6–53.9
add(44.5, pad(73.42, 9.0, att=1.5), .05)
for i, t0 in enumerate((46.0, 47.8, 49.6)):
    add(t0, tone(440, .6, dec=4), .06)
    if i < 2:
        for k in range(8): add(t0 + .4 + k * .1 + .06, click(.015, 1700), .06)
        add(t0 + 1.4, dull(), .16)
    else:
        for k in range(6): add(t0 + .4 + k * .2 + .08, tone([587.33, 659.25, 698.46, 783.99, 880, 987.77][k], .5, dec=6), .07, (k - 2.5) / 4)
add(51.8, swell(.5), .06); add(52.35, tone(1174.66, .9, dec=3), .08)  # dial -> O
for k in range(10): add(52.4 + (k + 1) * .04, click(.015, 2600), .07)
# ---- S7 chart/route (v5 cues + OFF)
add(41.3 + OFF, kick(.6), .35); add(41.3 + OFF, pad(73.42, 4.2, att=.8), .08)
add(45.2 + OFF, swell(.8), .10); add(45.9 + OFF, pad(87.31, 4.6, att=.4), .09); add(50.6 + OFF, pad(98.0, 3.2, att=.4), .08)
for b in np.arange(41.3 + OFF, 53.2 + OFF, .5): add(b, kick(.3), .16 if b < 45.9 + OFF else .22)
mel = [587.33, 698.46, 880, 783.99, 698.46, 659.25, 587.33, 523.25]
for i, b in enumerate(np.arange(46.0 + OFF, 53.0 + OFF, .5)): add(b, tone(mel[i % len(mel)], .7, dec=3.5), .045, float(np.sin(i)) * .4)
add(50.8 + OFF, tone(146.83, 2.0, dec=1.2), .10)
# ---- S8 callback
E0 = 53.0 + OFF; tb = E0 + 2.15
add(E0 + .4, swell(1.2, up=False), .06)
add(tb, kick(.6), .45); add(tb, tone(880, 1.2, dec=2.5), .10); add(tb, tone(1318.5, 1.2, dec=3), .05, .3)
add(tb + .35, swell(.4), .07); add(tb + .6, pad(55, 4.2, att=.6), .08)
for hz in (293.66, 349.23, 440.0): add(tb + .9, tone(hz, 3.0, dec=.8), .05)
add(tb + 3.3, swell(.4, up=False), .05)

delay = int(.17 * SR); buf[delay:] += buf[:-delay].copy() * .12
a, b = int(41.64 * SR), int(44.4 * SR); buf[a:b] *= np.linspace(1, 0, b - a)[:, None] ** 8
buf *= .82 / max(float(np.abs(buf).max()), .82); buf[-SR:] *= np.linspace(1, 0, SR)[:, None]
with wave.open(str(R / 'soundtrack.wav'), 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((buf * 32767).astype('<i2').tobytes())
(R / 'soundtrack.json').write_text(json.dumps({'type': 'original local synthesis aligned to V6 timing', 'seconds': DUR, 'seed': 29092026,
    'external_samples': False, 'speech': False, 'stop_silence': [41.64, 44.4]}, indent=2), encoding='utf-8')
print('soundtrack.wav written')
