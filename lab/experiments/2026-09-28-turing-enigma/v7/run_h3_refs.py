"""Approved 2026-09-29: 7 H3 ref2v calls (max 2 retries). Sequential so the warm container is reused."""
from pathlib import Path
import json, subprocess, sys

R = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
(R / 'h3' / 'inputs').mkdir(parents=True, exist_ok=True)
KEEP = ('Preserve the exact photographic reference: composition, objects, lighting, desaturated 1940s film look and grain. '
        'Do not add, remove, or reshape objects. No text, letters, numbers, logos, subtitles or UI. No faces. One continuous shot, no cuts. ')
SHOTS = [
    ('r1-keys', 21701, 'Animate: the index finger presses the rounded key down firmly and holds; at the moment it bottoms out, the single frosted lamp above flares brighter warm amber, then settles to a steady glow. Camera locked macro, a tiny focus breathing only.'),
    ('r2-rotors', 21702, 'Animate: the center rotor wheel clicks forward one notch at a time, three distinct mechanical steps with a brief pause between them, the neighbouring rotors stay still, light glints move across the brass ridges. Camera locked.'),
    ('r3-radio', 21703, 'Animate: the operator keeps writing, the pencil moves steadily across the notepad, the receiver dial glow flickers faintly, a slight head tilt as he listens. Very slow push-in toward the notepad.'),
    ('r4-hut', 21704, 'Animate: slow steady push-in down toward the single lamp-lit sheet in the center, the hands hold the pencil still then begin to write, the lamp light stays constant, dust drifts through the lamp beam.'),
    ('r5-bombe', 21705, 'Animate: every circular drum in the grid rotates at its own steady speed, some clockwise and some counter-clockwise, the whole machine vibrating slightly, hazy light constant. Camera locked straight-on, perfectly symmetrical.'),
    ('r6-convoy', 21706, 'Animate: the convoy of ships sails steadily forward from lower left toward upper right, wakes lengthen behind them, whitecaps roll, cloud shadows drift slowly across the sea. Camera locked top-down, very slow drift in the ships direction.'),
    ('r7-wake', 21707, 'Animate: the ship moves steadily up the frame, its straight bright wake extends and stays straight behind it, gentle swell moves across the dark water, low sun glints. Camera locked top-down.'),
]
only = set(sys.argv[1:])
for sid, seed, motion in SHOTS:
    if only and sid not in only:
        continue
    src = R / 'refs' / f'{sid}.png'
    inp = R / 'h3' / 'inputs' / f'{sid}.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-vf', 'scale=768:1344:flags=lanczos', str(inp)], check=True)
    cmd = [sys.executable, str(REPO / 'tools' / 'run_h3_job.py'), '--kind', 'ref2v', '--input', str(inp), '--prompt', KEEP + motion,
           '--seconds', '5', '--width', '768', '--height', '1344', '--seed', str(seed), '--job-id', f'enigma7-{sid}',
           '--out-root', str(R / 'h3' / 'clips'), '--out-name', f'{sid}.mp4', '--manifest', str(R / 'h3' / 'manifest.jsonl')]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(REPO))
    status = 'ok' if p.returncode == 0 else 'fail'
    print(json.dumps({'shot': sid, 'status': status, 'tail': (p.stdout + p.stderr)[-400:]}, ensure_ascii=False), flush=True)
