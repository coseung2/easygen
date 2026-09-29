"""빠른 비트 BGM, 128 BPM, 보컬 없음. 로컬 합성(1단계), 영상 타임라인과 같은 박자 격자.

훅 8박: 글자마다 스탭 + 킥. 이후 4-on-the-floor 킥, 2·4박 클랩, 16분 하이햇, 오프비트 베이스,
플럭 코드(C–G–Am–F), 리드 훅. 장소마다 확대 직전 휘익(노이즈 스윕), 실사 진입에 임팩트.
엔딩 전 라이저 → 마지막 히트 → 여운.

python music_fast.py -> music/bgm-02.wav
"""
import wave
from pathlib import Path

import numpy as np

from timeline import B, DUR, END_START, HOOK_END, INTRO_END, N_STOPS, STOP_LEN, stop_times

SR = 48000
HERE = Path(__file__).parent
rng = np.random.default_rng(128)

CHORDS = [(48, [60, 64, 67]), (43, [55, 59, 62]), (45, [57, 60, 64]), (41, [53, 57, 60])]
HOOK = [72, None, 72, 74, None, 76, None, 79, 76, None, 74, None, 72, None, 69, None]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n, a=0.002, d=8.0):
    t = np.arange(n) / SR
    return np.minimum(t / a, 1) * np.exp(-t * d)


def add(tr, t, sig, g=1.0):
    s = int(round(t * SR))
    if s < 0 or s >= len(tr):
        return
    n = min(len(sig), len(tr) - s)
    tr[s:s + n] += sig[:n] * g


def kick(n=int(0.35 * SR)):
    t = np.arange(n) / SR
    f = 50 + 110 * np.exp(-t * 35)
    ph = 2 * np.pi * np.cumsum(f) / SR
    click = 0.3 * np.exp(-t * 200) * rng.uniform(-1, 1, n) * np.minimum(t / 0.001, 1)
    return np.sin(ph) * np.exp(-t * 9) + click


def clap(n=int(0.25 * SR)):
    x = rng.uniform(-1, 1, n)
    x = np.convolve(x, [1, -0.6], mode="same")
    t = np.arange(n) / SR
    e = np.exp(-t * 22) + 0.5 * np.exp(-np.maximum(t - 0.012, 0) * 22) * (t > 0.012)
    return x * e * np.minimum(t / 0.002, 1)


def hat(open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    x = rng.uniform(-1, 1, n)
    x = x - np.convolve(x, np.ones(4) / 4, mode="same")
    return x * env(n, 0.001, 12 if open_ else 60)


def saw(m, length, d=6.0, detune=0.006):
    n = int(length * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k in (-detune, 0, detune):
        out += 2 * ((hz(m) * (1 + k) * t) % 1.0) - 1
    out /= 3
    out = np.convolve(out, np.ones(6) / 6, mode="same")
    return out * env(n, 0.003, d)


def bass(m, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    x = np.sign(np.sin(2 * np.pi * hz(m) * t)) * 0.6 + np.sin(2 * np.pi * hz(m) * t)
    x = np.convolve(x, np.ones(24) / 24, mode="same")
    return x * env(n, 0.004, 7)


def lead(m, length):
    n = int(length * SR)
    t = np.arange(n) / SR
    ph = (hz(m) * t) % 1.0
    x = np.where(ph < 0.25, 1.0, -1.0) * 0.6 + np.sin(2 * np.pi * hz(m) * t) * 0.5
    x = np.convolve(x, np.ones(5) / 5, mode="same")
    return x * env(n, 0.004, 5)


def whoosh(length=0.45, up=True):
    n = int(length * SR)
    x = rng.uniform(-1, 1, n)
    t = np.linspace(0, 1, n)
    out = np.zeros(n)
    k0 = 2
    for i in range(0, n, 512):
        p = t[i] if up else 1 - t[i]
        k = int(k0 + (1 - p) * 40)
        seg = x[i:i + 512]
        out[i:i + 512] = seg - np.convolve(seg, np.ones(k) / k, mode="same")
    return out * np.sin(np.pi * t) ** 1.5


def impact():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(40 + 80 * np.exp(-t * 18)) / SR) * np.exp(-t * 4)
    crash = rng.uniform(-1, 1, n)
    crash = (crash - np.convolve(crash, np.ones(3) / 3, mode="same")) * np.exp(-t * 5) * np.minimum(t / 0.003, 1)
    return boom * 0.9 + crash * 0.35


def stab(m_list, length=0.22):
    return sum(saw(m, length, d=14) for m in m_list) / len(m_list)


def snap():
    """사진이 '착' 붙는 소리: 짧고 밝은 노이즈."""
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    x = rng.uniform(-1, 1, n)
    x = x - np.convolve(x, np.ones(8) / 8, mode="same")
    return x * np.exp(-t * 45) * np.minimum(t / 0.0015, 1)


def main():
    n = int(DUR * SR) + SR
    drums, music, fx = np.zeros(n), np.zeros(n), np.zeros(n)

    # 훅 (v4): 0박 임팩트 → 1박 "철?" → 2박 "땡!" 큰 히트 → 2.5–6.5박 몽타주 그루브(컷마다 틱)
    # → 6.5–8박 스네어 롤 + 라이저 → 8박에 본 그루브 드롭
    add(fx, 0, impact(), 0.6)
    add(drums, 0, kick(), 1.0)
    add(music, 0, stab([m + 12 for m in CHORDS[2][1]]), 0.45)
    add(drums, B, kick(), 0.9)
    add(music, B, stab([m + 12 for m in CHORDS[2][1]]), 0.4)
    add(fx, 2 * B, impact(), 0.95)
    add(drums, 2 * B, kick(), 1.0)
    add(drums, 2 * B, clap(), 0.8)
    add(music, 2 * B, stab([m + 12 for m in CHORDS[0][1]]), 0.6)
    # v5: 3박 노랑 와이프 → 4–9박 사진 한 장 = 한 박(킥 + 착) → 10박 GO 히트 → 10.5–12박 롤·라이저
    add(fx, 3 * B, whoosh(0.4 * B), 0.4)
    for bb in range(4, 10):
        t = bb * B
        add(drums, t, kick(), 0.9)
        add(fx, t, snap(), 0.7)
        if bb % 2 == 1:
            add(drums, t, clap(), 0.45)
        for s in range(4):
            add(drums, t + s * B / 4, hat(open_=(s == 2)), 0.14 if s == 2 else 0.1)
        add(music, t + B / 2, bass(CHORDS[(bb - 4) % 4][0] - 12, B / 2), 0.45)
        add(music, t, stab([m + 12 for m in CHORDS[(bb - 4) % 4][1]], 0.18), 0.25)
    add(fx, 10 * B, impact(), 0.8)
    add(drums, 10 * B, kick(), 1.0)
    add(music, 10 * B, stab([m + 12 for m in CHORDS[0][1]]), 0.55)
    n_roll = 12
    for j in range(n_roll):
        add(drums, 10.5 * B + j * (1.5 * B / n_roll), clap(), 0.18 + 0.03 * j)
    add(fx, 10.5 * B, whoosh(1.5 * B), 0.6)

    # 본 그루브: 인트로부터 엔딩 히트 직전까지
    groove_end = END_START + 2 * B
    beat = 0
    t = HOOK_END
    while t < groove_end - 1e-6:
        bar = int(beat // 4)
        root, ch = CHORDS[bar % 4]
        add(drums, t, kick(), 1.0)
        if beat % 2 == 1:
            add(drums, t, clap(), 0.55)
        for s in range(4):
            add(drums, t + s * B / 4, hat(open_=(s == 2)), 0.18 if s == 2 else 0.12)
        add(music, t + B / 2, bass(root - 12, B / 2), 0.5)
        if beat % 2 == 0:
            add(music, t, sum(saw(m, B * 0.9, d=7) for m in ch) / 3, 0.22)
        else:
            add(music, t + B / 2, sum(saw(m + 12, B * 0.4, d=12) for m in ch) / 3, 0.14)
        for h in range(2):
            m = HOOK[(beat * 2 + h) % 16]
            if m is not None and bar % 2 == 1:
                add(music, t + h * B / 2, lead(m, B / 2), 0.16)
        beat += 1
        t += B

    # 장소마다: 확대 직전 휘익, 실사 진입 임팩트, 복귀 휘익(작게)
    for k in range(N_STOPS):
        st = stop_times(k)
        add(fx, st["zoom"] - 0.28, whoosh(0.42), 0.55)
        add(fx, st["live"], impact(), 0.5)
        add(fx, st["back"] - 0.05, whoosh(0.3, up=False), 0.3)

    # 엔딩: 라이저 → 히트 → 코드 여운
    add(fx, END_START, whoosh(2 * B), 0.6)
    hit = END_START + 2 * B
    add(fx, hit, impact(), 0.8)
    add(drums, hit, kick(), 1.0)
    tail = sum(saw(m, 2.4, d=1.6) for m in [48, 60, 64, 67, 72]) / 5
    add(music, hit, tail, 0.5)

    mix = drums * 0.8 + music * 0.9 + fx * 0.7
    mix = np.tanh(mix * 1.4) / np.tanh(1.4)
    mix = np.convolve(mix, np.ones(3) / 3, mode="same")  # 샘플 단위 급변 완화 (AAC 오버슈트 방지)
    mix = mix[: int(DUR * SR)]
    fade = int(0.6 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.7   # 약 −3dB, AAC 인코딩 오버슈트 여유
    st = np.stack([mix, np.roll(mix, 12)], axis=1)
    pcm = (st * 32767).astype(np.int16)
    out = HERE / "music" / "bgm-02.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(out, round(len(mix) / SR, 2), "s")


if __name__ == "__main__":
    main()
