"""local-freeze-cast@1.0 — 프리즈 프레임 캐릭터 인트로 (패러디 톤), 9:16 · 30 fps.

Each cast entry is a short clip that plays for three beats, then freezes on the downbeat with a
flash + shutter, drops to a two-tone plate, and pops a white die-cut sticker with a variety-show
name card, role title and a typed gag line. Music: 8-bit chiptune at 150 BPM (0.4 s beats).
Length = 1.6 s intro + 3.2 s × cast (1–6) + 3.2 s outro.

Input: job JSON (job.schema.json). Output: MP4 + <output>.metadata.json. JSON-line events on stdout.
Promoted from lab/junyoung-intro render_freeze.py (junyoung-freeze-v2, approved 2026-09-28).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / '_shared'))
import cutout  # noqa: E402
import music_chiptune  # noqa: E402
from motionkit import (Kit, decode_clip, encode, grab_frame, io_, is_video, lerp, load_image,  # noqa: E402
                       out_back, out_cubic, prog)
from sfx import Track  # noqa: E402

PIPELINE = 'local-freeze-cast'
VERSION = '1.0'
BEAT = 0.4
INTRO, CH, PLAY, OUTRO = 4 * BEAT, 8 * BEAT, 3 * BEAT, 8 * BEAT
TILTS = [-5, 4, -4, 5, -3, 4]
# outro collage positions for up to six stickers
COLLAGE = [(210, 470), (540, 400), (870, 470), (330, 900), (750, 900), (540, 640)]
TAIL = 'lowpass=f=11000,alimiter=limit=0.5:level=disabled,volume=2dB,alimiter=limit=0.6:level=disabled'


def emit(event, **fields):
    sys.stdout.write(json.dumps({'type': event, 'pipeline': f'{PIPELINE}@{VERSION}', 'ts': round(time.time(), 3),
                                 **fields}, ensure_ascii=False) + '\n')
    sys.stdout.flush()


class FreezeCast:
    def __init__(self, job, cutout_python=None):
        self.job = job
        k = self.k = Kit(palette=job.get('palette', 'neon'))
        self.W, self.H, self.FPS = k.W, k.H, k.FPS
        self.cache = Path(job['output']).parent / '.cache'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.model = job.get('cutout_model', 'bria-rmbg')
        self.py = cutout_python
        self.cast = job['cast'][:6]
        if not self.cast:
            raise ValueError('cast is empty')
        self.DUR = INTRO + len(self.cast) * CH + OUTRO
        colors = [k.A, k.B, k.HI]
        self.prep = []
        for i, c in enumerate(self.cast):
            col = colors[i % 3]
            src = Path(c['media'])
            at = float(c.get('freeze_at', 0))
            if is_video(src):
                frames = decode_clip(src, max(0, at - PLAY), PLAY + 0.1, self.W, self.H, self.FPS)[:int(PLAY * self.FPS)]
                still = grab_frame(src, at)
            else:
                still = load_image(src)
                base = k.cover(still)
                frames = [k.zoom_at(base, 1 + 0.04 * n / (PLAY * self.FPS), self.W / 2, self.H * 0.42)
                          for n in range(int(PLAY * self.FPS))]
            key = hashlib.sha1(f'{src}|{at}'.encode()).hexdigest()[:12]
            still_path = self.cache / f'freeze_{key}.png'
            if not still_path.exists():
                still.save(still_path)
            st_path, info = cutout.cut(still_path, self.cache, self.model, python=self.py)
            self.prep.append({
                'frames': frames or [k.cover(still)],
                'frozen': self.duotone(ImageOps.fit(still, (self.W, self.H)), col),
                'sticker': Kit.fit(Image.open(st_path).convert('RGBA'), (900, 1000)),
                'color': col,
                'coverage': info.get('coverage'),
            })
            emit('log', message=f'prepared {i + 1}/{len(self.cast)}')

    def duotone(self, img, color):
        g = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=2)
        return ImageOps.colorize(g, black=self.k.INK, white=color).convert('RGB')

    def intro(self, lt):
        k, j = self.k, self.job
        img = k.canvas(k.HI)
        k.pill(img, self.W / 2, 560, j.get('badge', 'CAST'), k.F(k.GM, 60), k.PAPER, k.INK,
               scale=out_back(prog(lt, 0, 0.3), 2.4))
        for n, (line, y, c) in enumerate(zip(j.get('title', ['등장인물', '소개']), [820, 1080], [k.INK, k.B])):
            p = prog(lt, 0.12 + n * 0.1, 0.45 + n * 0.1)
            k.text(img, (self.W / 2, y + 1100 * (1 - out_back(p, 1.4))), line, k.fit_font(k.HEAD, 280, line, 960), c)
        k.text(img, (self.W / 2, 1330), j.get('subtitle', f"{j['name']} 편"), k.F(k.PB, 60), k.INK,
               alpha=out_cubic(prog(lt, 0.6, 0.9)))
        k.flood(img, self.W / 2, 560, lerp(0, 2300, io_(prog(lt, INTRO - 0.35, INTRO))), k.INK)
        return img

    def chapter(self, i, lt):
        k, p, c = self.k, self.prep[i], self.cast[i]
        col = p['color']
        pill_bg = k.INK if col == k.HI else col
        pill_fg = k.PAPER if pill_bg in (k.B, k.INK) else k.INK
        tag = f'CAST {i + 1:02d}'
        if lt < PLAY:
            f = p['frames'][min(len(p['frames']) - 1, int(lt * self.FPS))]
            img = k.zoom_at(f, 1 + 0.07 * io_(lt / PLAY), self.W / 2, self.H * 0.42)
            k.pill(img, self.W - k.SAFE - 110, k.SAFE + 40, tag, k.F(k.GM, 38), k.PAPER, k.INK,
                   alpha=out_cubic(prog(lt, 0, 0.2)))
            return img
        t = lt - PLAY
        img = k.zoom_at(p['frozen'], lerp(1.12, 1.04, out_cubic(prog(t, 0, 0.35))), self.W / 2, self.H * 0.42).copy()
        d = ImageDraw.Draw(img)
        if t < 0.5:
            a = 1 - t / 0.5
            line = tuple(int(lerp(ch, 255, 0.35)) for ch in col)
            for n in range(22):
                ang = n / 22 * 6.283
                d.line((self.W / 2 + np.cos(ang) * 560, 820 + np.sin(ang) * 672,
                        self.W / 2 + np.cos(ang) * 1500, 820 + np.sin(ang) * 1800), fill=line, width=int(10 * a) + 1)
        k.paste(img, p['sticker'], self.W / 2, 820, scale=out_back(prog(t, 0.03, 0.3), 2.4),
                rot=lerp(-14, TILTS[i % 6], out_cubic(prog(t, 0.03, 0.4))))
        for n, (sx, sy) in enumerate([(-360, -420), (380, -330), (-330, 380)]):
            tw = abs(np.sin(lt * 8 + n * 2))
            k.sparkle(d, self.W / 2 + sx, 820 + sy, 42 * tw * out_cubic(prog(t, 0.2, 0.4)),
                      k.HI if col != k.HI else k.PAPER)
        slide = (1 - out_cubic(prog(t, 0.22, 0.45))) * -1000
        label = c.get('label', f"{self.job['name']}")
        k.pill(img, k.SAFE + 170 + slide, 1440, label, k.F(k.PB, 48), pill_fg, pill_bg)
        role = c['role']
        k.text(img, (self.W / 2, 1600), role, k.fit_font(k.HEAD, 128, role, 900), k.HI if col != k.HI else k.PAPER,
               stroke=12, scale=out_back(prog(t, 0.32, 0.52), 1.7))
        gag = c.get('gag', '')
        n_chars = int(len(gag) * prog(t, 0.55, 1.0))
        k.text(img, (self.W / 2, 1780), gag[:n_chars], k.fit_font(k.PB, 64, gag, 940), k.PAPER, stroke=6)
        k.pill(img, self.W - k.SAFE - 110, k.SAFE + 40, tag, k.F(k.GM, 38), k.PAPER, k.INK)
        f = int(t * self.FPS)
        if f < 3:
            img = Image.blend(img, k.canvas(k.PAPER), [0.95, 0.6, 0.25][f])
        return img

    def outro(self, lt):
        k, j = self.k, self.job
        img = k.canvas(k.INK)
        n_cast = len(self.prep)
        if n_cast <= 3:   # one centered row; the 5-slot collage looks lopsided with few stickers
            gap = self.W / (n_cast + 1)
            slots = [(gap * (i + 1), 620) for i in range(n_cast)]
            size = 0.5 if n_cast > 1 else 0.62
        else:
            slots, size = COLLAGE, 0.36
        for n, p in enumerate(self.prep):
            a = out_back(prog(lt, 0.05 + n * 0.08, 0.35 + n * 0.08), 2.2)
            k.paste(img, p['sticker'], *slots[n], scale=size * a, rot=TILTS[n] * 2)
        k.text(img, (self.W / 2, 1330 + 900 * (1 - out_back(prog(lt, 0.4, 0.75), 1.4))), j['name'],
               k.fit_font(k.HEAD, 250, j['name'], 960), k.A)
        k.text(img, (self.W / 2, 1530), j.get('outro_title', f'1인 {len(self.cast)}역 소화 중'), k.F(k.HEAD, 110),
               k.PAPER, alpha=out_cubic(prog(lt, 0.8, 1.1)))
        if j.get('outro_tag'):
            k.pill(img, self.W / 2, 1700, j['outro_tag'], k.F(k.PB, 44), k.INK, k.HI,
                   alpha=out_cubic(prog(lt, 1.0, 1.3)))
        k.flood(img, self.W / 2, 560, lerp(0, 2300, io_(prog(lt, OUTRO - 0.4, OUTRO))), k.HI)
        return img

    def render(self, t):
        if t < INTRO:
            return self.intro(t)
        end = INTRO + len(self.cast) * CH
        if t < end:
            i = int((t - INTRO) / CH)
            lt = t - INTRO - i * CH
            img = self.chapter(i, lt)
            return self.k.punch(img) if lt < 2 / self.FPS else img
        return self.outro(t - end)

    def freezes(self):
        return [INTRO + i * CH + PLAY for i in range(len(self.cast))]

    def sfx(self, path):
        tr = Track(self.DUR, seed=9)
        for i, t0 in enumerate(self.freezes()):
            tr.shutter(t0)
            tr.pop(t0 + 0.09, 420, 1500, 0.14, 0.26, decay=22)
            tr.whoosh(t0 + 0.2)
            tr.pop(t0 + 0.33, 1300, 500, 0.1, 0.2, decay=22)
            tr.typewriter(t0 + 0.55, t0 + 1.0, len(self.cast[i].get('gag', '')))
        for n in range(len(self.cast)):
            tr.pop(self.DUR - OUTRO + 0.05 + n * 0.08, 600 + n * 120, 1400 + n * 120, 0.1, 0.18, decay=22)
        return tr.save(path)

    def run(self):
        out = Path(self.job['output'])
        out.parent.mkdir(parents=True, exist_ok=True)
        end = INTRO + len(self.cast) * CH
        music = music_chiptune.build(self.cache / 'music.wav', self.DUR, beat=BEAT, intro=INTRO,
                                     freezes=self.freezes(), end=end, coin=end + 1.8)
        fx = self.sfx(self.cache / 'sfx.wav')
        mix = (f'[1:a]atrim=0:{self.DUR},asetpts=N/SR/TB,afade=t=out:st={self.DUR - 0.5}:d=0.5[m];'
               f'[m][2:a]amix=inputs=2:normalize=0:duration=first,{TAIL}[a]')
        total = int(round(self.DUR * self.FPS))
        emit('render_started', seconds=self.DUR, frames=total)
        encode(lambda n: self.render(n / self.FPS), total, self.W, self.H, self.FPS, [music, fx], mix, out, self.DUR,
               on_progress=lambda p: emit('render_progress', percent=round(p * 100, 1)))
        meta = {'pipeline_id': PIPELINE, 'pipeline_version': VERSION, 'duration': self.DUR, 'fps': self.FPS,
                'size': [self.W, self.H], 'cutout_model': self.model, 'cutout_license': cutout.MODELS.get(self.model),
                'cast': len(self.cast), 'cutout_coverage': [p['coverage'] for p in self.prep]}
        out.with_suffix('.metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
        emit('render_completed', output=str(out), seconds=self.DUR)
        return out


def main(argv):
    """render.py <job.json> [--cutout-python <python>] [stills]"""
    args = list(argv)
    py = None
    if '--cutout-python' in args:
        i = args.index('--cutout-python')
        py = args[i + 1]
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return 2
    job = json.loads(Path(args[0]).read_text(encoding='utf-8'))
    if len(args) > 1 and args[1] == 'stills':
        fc = FreezeCast(job, cutout_python=py)
        ts = [0.8, INTRO + 0.6] + [f + 1.6 for f in fc.freezes()] + [fc.DUR - OUTRO + 1.6, fc.DUR - 0.1]
        sheet = Image.new('RGB', (6 * 300, 2 * 533))
        for i, t in enumerate(ts[:12]):
            sheet.paste(fc.render(t).resize((300, 533)), ((i % 6) * 300, (i // 6) * 533))
        out = Path(job['output']).with_suffix('.stills.jpg')
        sheet.save(out, quality=88)
        print(json.dumps({'stills': str(out)}))
        return 0
    try:
        FreezeCast(job, cutout_python=py).run()
    except Exception as error:
        emit('failed', message='캐릭터 인트로 렌더에 실패했습니다.', detail=str(error)[:400])
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
