"""Seed a template's cutout cache with the approved lab stickers (same source, model, and size),
so a regression render uses exactly the stickers that were approved instead of re-cutting.

Usage: python seed_cutout_cache.py <cache dir> [launch|freeze]
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'pipelines' / '_shared'))
sys.path.insert(0, str(REPO / 'tools'))
from lab_paths import lab_path
import cutout  # noqa: E402

LAB = lab_path('2026-09-28-junyoung-intro')
cache = Path(sys.argv[1])
which = sys.argv[2] if len(sys.argv) > 2 else 'launch'
cache.mkdir(parents=True, exist_ok=True)
ix = json.load(open(LAB / 'data' / 'media_index.json', encoding='utf-8'))
seeded = 0


def seed(src, lab_sticker):
    global seeded
    if not lab_sticker.exists():
        return
    out = cache / f"{cutout.cache_key(src, 'bria-rmbg')}.png"
    shutil.copyfile(lab_sticker, out)
    out.with_suffix('.json').write_text(json.dumps({'model': 'bria-rmbg', 'license': 'CC BY-NC 4.0',
                                                    'coverage': None, 'seeded_from': str(lab_sticker)}),
                                        encoding='utf-8')
    seeded += 1


if which == 'launch':
    for i in [1, 79, 99, 118, 147, 158, 159, 175, 183, 184]:
        seed(LAB / 'sources' / ix[i]['file'], LAB / 'stickers' / f'{i}.png')
else:
    # freeze stills are written by the template as freeze_<sha1(src|at)>.png; reproduce that name,
    # copy the lab freeze frame to it, then key the sticker on that still
    for i, at in [(145, 15.0), (168, 23.4), (91, 12.4), (169, 13.4), (176, 10.8)]:
        src = LAB / 'sources' / ix[i]['file']
        key = hashlib.sha1(f'{src.as_posix()}|{at}'.encode()).hexdigest()[:12]
        still = cache / f'freeze_{key}.png'
        shutil.copyfile(LAB / 'frames' / f'ff_{i}.png', still)
        seed(still, LAB / 'stickers' / f'ff_{i}.png')
print('seeded', seeded)
