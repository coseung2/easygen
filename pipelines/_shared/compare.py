"""Regression check: compare a template render with an approved reference video.

Reports per-second mean absolute pixel difference (0–255 scale), the worst frames, format, and
audio loudness/peak for both. Writes a side-by-side sheet of the worst frames.

Usage: python compare.py <reference.mp4> <candidate.mp4> <report.json>
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 270, 480


def frames(path, fps=10):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vf', f'fps={fps},scale={W}:{H}',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    n = W * H * 3
    return [np.frombuffer(raw[i:i + n], np.uint8).reshape(H, W, 3) for i in range(0, len(raw) - n + 1, n)]


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=width,height,r_frame_rate',
                          '-of', 'json', str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def loudness(path):
    err = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(path), '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    i = re.findall(r'I:\s+(-?[\d.]+) LUFS', err)
    p = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', err)
    return {'lufs': float(i[-1]) if i else None, 'true_peak': float(p[-1]) if p else None}


def main(ref, cand, report):
    a, b = frames(ref), frames(cand)
    n = min(len(a), len(b))
    diff = [float(np.abs(a[i].astype(int) - b[i].astype(int)).mean()) for i in range(n)]
    per_second = [round(float(np.mean(diff[s:s + 10])), 2) for s in range(0, n, 10)]
    worst = sorted(range(n), key=lambda i: -diff[i])[:6]
    sheet = Image.new('RGB', (W * 2, H * len(worst)))
    for row, i in enumerate(sorted(worst)):
        sheet.paste(Image.fromarray(a[i]), (0, row * H))
        sheet.paste(Image.fromarray(b[i]), (W, row * H))
    sheet_path = Path(report).with_suffix('.worst.jpg')
    sheet.save(sheet_path, quality=85)
    result = {
        'frames_compared': n, 'frame_count': [len(a), len(b)],
        'mean_abs_diff': round(float(np.mean(diff)), 2), 'max_abs_diff': round(max(diff), 2),
        'per_second': per_second,
        'worst_frames_s': [round(i / 10, 1) for i in sorted(worst)],
        'probe': {'reference': probe(ref), 'candidate': probe(cand)},
        'audio': {'reference': loudness(ref), 'candidate': loudness(cand)},
        'worst_sheet': str(sheet_path),
    }
    Path(report).write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('mean_abs_diff', 'max_abs_diff', 'per_second', 'worst_frames_s', 'audio')}))


if __name__ == '__main__':
    main(*sys.argv[1:4])
