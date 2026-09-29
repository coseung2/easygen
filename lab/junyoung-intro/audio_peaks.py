"""Find the loudest short events in candidate clips (fart/burp moments)."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from lab_paths import lab_path

WORK = lab_path('2026-09-28-junyoung-intro')
ix = json.load(open(WORK / 'data' / 'media_index.json', encoding='utf-8'))
sr = 16000
for i in [int(a) for a in sys.argv[1:]]:
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(WORK / 'sources' / ix[i]['file']), '-vn', '-ac', '1',
                          '-ar', str(sr), '-f', 's16le', '-'], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    if not len(a):
        print(i, 'no audio')
        continue
    win = sr // 20
    rms = np.sqrt(np.convolve(a ** 2, np.ones(win) / win, mode='same'))
    db = 20 * np.log10(rms + 1e-6)
    base = np.median(db)
    peaks = []
    order = np.argsort(db)[::-1]
    for p in order:
        t = p / sr
        if all(abs(t - q) > 0.8 for q, _ in peaks):
            peaks.append((t, db[p]))
        if len(peaks) == 5:
            break
    print(i, ix[i]['title'], f'dur {len(a) / sr:.1f}s median {base:.1f}dB',
          ' | '.join(f'{t:.2f}s {d:.1f}dB' for t, d in sorted(peaks)))
