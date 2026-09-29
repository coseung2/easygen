"""local-launch-spoof@1.0 — 제품 런칭 패러디 (product-launch spoof), 9:16 · 30 fps · 22 s.

Input: one job JSON (see job.schema.json). Output: MP4 + metadata.json next to it.
Events: JSON lines on stdout (render_started / render_progress / render_completed / failed),
the same protocol tools/renderers use, so the app's pipeline-event handling applies.

Scene grid is fixed at 120 BPM (0.5 s beats): hook 2.0 · reveal 2.5 · spec_zoom 3.0 ·
spec_loupe 2.5 · gag_launch 3.0 · meter 3.0 · burst 3.0 (6 × 0.5) · endcard 3.0 = 22 s.
Promoted from lab/junyoung-intro render_launch.py (junyoung-launch-v5, approved 2026-09-28).
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / '_shared'))
import cutout  # noqa: E402
import music_bouncy  # noqa: E402
from motionkit import (Kit, clamp, decode_clip, encode, grab_frame, inv_out_cubic, inv_smoothstep, io_,  # noqa: E402
                       is_video, lerp, load_image, out_back, out_cubic, prog, AUDIO_TAIL)
from sfx import Track  # noqa: E402

PIPELINE = 'local-launch-spoof'
VERSION = '1.0'
BEAT = 0.5
SCENE_LEN = {'hook': 2.0, 'reveal': 2.5, 'spec_zoom': 3.0, 'spec_loupe': 2.5, 'gag_launch': 3.0,
             'meter': 3.0, 'burst': 3.0, 'endcard': 3.0}
ORDER = ['hook', 'reveal', 'spec_zoom', 'spec_loupe', 'gag_launch', 'meter', 'burst', 'endcard']


def emit(event, **fields):
    sys.stdout.write(json.dumps({'type': event, 'pipeline': f'{PIPELINE}@{VERSION}', 'ts': round(time.time(), 3),
                                 **fields}, ensure_ascii=False) + '\n')
    sys.stdout.flush()


class Launch:
    def __init__(self, job, cutout_python=None):
        self.job = job
        k = self.k = Kit(palette=job.get('palette', 'neon'))
        self.W, self.H, self.FPS = k.W, k.H, k.FPS
        self.work = Path(job['output']).parent
        self.cache = self.work / '.cache'
        self.model = job.get('cutout_model', 'bria-rmbg')
        self.py = cutout_python
        s = job['scenes']
        # scene start times on the beat grid
        self.t0 = {}
        t = 0.0
        for name in ORDER:
            self.t0[name] = t
            t += SCENE_LEN[name]
        self.DUR = t
        # --- load assets ---
        self.hero = self.sticker(s['reveal']['media'], (900, 980))
        z = s['spec_zoom']
        zsrc = z['media']
        self.zoom_plate = k.cover(grab_frame(zsrc, z.get('at', 0)) if is_video(zsrc) else load_image(zsrc))
        self.zoom_focus = z.get('focus', [self.W / 2, self.H * 0.4])
        self.zoom_marks = z.get('marks', [])
        lp = s['spec_loupe']
        self.loupe_st = self.sticker(lp['media'], (1250, 1350))
        self.loupe_center = lp.get('sticker_center', [686, 982])
        self.loupe_point = lp.get('point')           # [x, y] on screen once settled; None = auto
        if self.loupe_point is None:
            self.loupe_point = self.auto_profile_tip()
        g = s['gag_launch']
        self.gag_st = self.sticker(g['media'], (820, 900))
        self.gag_audio = g.get('sound_media')
        self.gag_sound_at = g.get('sound_at')
        m = s['meter']
        self.meter_st = self.sticker(m['media'], (700, 820))
        self.burst_items = [(self.sticker(item['media'], (820, 900)), item['title'], item.get('sub', ''))
                            for item in s['burst']['items'][:6]]

    # ---------- asset helpers ----------
    def sticker(self, media, box):
        src = Path(media)
        if is_video(src):
            still = self.cache / f'frame_{hashlib.sha1(str(src).encode()).hexdigest()[:10]}.png'
            self.cache.mkdir(parents=True, exist_ok=True)
            if not still.exists():
                grab_frame(src, 0).save(still)
            src = still
        path, info = cutout.cut(src, self.cache, self.model, python=self.py)
        self.cutout_info = info
        return Kit.fit(Image.open(path).convert('RGBA'), box)

    def auto_profile_tip(self):
        """Nose tip of a right-facing side profile: the first local peak of the face edge.

        Scans the settled sticker row by row, takes the rightmost skin pixel per row, and returns the
        first peak followed by a pull-back of at least 4 px (nose → philtrum). The overall rightmost
        point is usually the lips or a hand, which is why a global max is wrong here.
        """
        probe = self.k.canvas((0, 222, 90))
        Kit.paste(probe, self.loupe_st, *self.loupe_center)
        a = np.asarray(probe).astype(int)
        r, g, b = a[..., 0], a[..., 1], a[..., 2]
        green = (g > 180) & (r < 80) & (b < 140)
        white = (r > 235) & (g > 235) & (b > 235)
        skin = ~green & ~white & (r > 120) & (r > b + 15)
        cx, cy = self.loupe_center
        x0, x1 = int(cx - 150), int(cx + 80)
        edge = []
        for y in range(int(cy - 300), int(cy - 60)):
            xs = np.where(skin[y, x0:x1])[0]
            if len(xs):
                x = x0 + int(xs.max())
                if edge and x - edge[-1][0] > 40:      # jumped onto a hand/arm: profile ends
                    break
                edge.append((x, y))
        for i in range(len(edge)):
            x, y = edge[i]
            ahead = [e[0] for e in edge[i + 1:i + 30]]
            behind = [e[0] for e in edge[max(0, i - 30):i]]
            if ahead and behind and x >= max(behind) and x >= max(ahead) and x - min(ahead) >= 4:
                return [x - 3, y]
        if edge:
            x, y = max(edge)
            return [x - 3, y]
        return [int(cx - 50), int(cy - 200)]

    # ---------- scenes ----------
    def hook(self, lt):
        k, s = self.k, self.job['scenes']['hook']
        img = k.canvas(k.A)
        k.pill(img, self.W / 2, 470, s.get('badge', 'NEW'), k.F(k.GM, 64), k.PAPER, k.INK,
               scale=out_back(prog(lt, 0, 0.3), 2.4))
        for n, (line, y) in enumerate(zip(s.get('lines', ['신제품', '출시']), [800, 1060])):
            p = prog(lt, 0.12 + n * 0.1, 0.45 + n * 0.1)
            k.text(img, (self.W / 2, y + 1100 * (1 - out_back(p, 1.4))), line, k.fit_font(k.HEAD, 300, line, 960), k.INK)
        k.text(img, (self.W / 2, 1320), s.get('sub', ''), k.F(k.PB, 60), k.INK, alpha=out_cubic(prog(lt, 0.6, 0.9)))
        k.flood(img, self.W / 2, 470, lerp(0, 2300, io_(prog(lt, 1.55, 2.0))), k.B)
        return img

    SPARKS = [(a, 0.55 + 0.45 * ((a * 7) % 1)) for a in np.linspace(0, math.tau, 12, endpoint=False)]

    def reveal(self, lt):
        k, s = self.k, self.job['scenes']['reveal']
        img = k.canvas(k.B)
        d = ImageDraw.Draw(img)
        p = prog(lt, 0.4, 1.0)
        for a, spd in self.SPARKS:
            dist = 200 + 520 * spd * out_cubic(p)
            if 0 < p < 1:
                k.sparkle(d, self.W / 2 + math.cos(a) * dist, 780 + math.sin(a) * dist, 46 * (1 - p * 0.6), k.HI)
        k.paste(img, self.hero, self.W / 2, lerp(-700, 780, out_back(prog(lt, 0.0, 0.45), 1.6)),
                rot=lerp(-10, -3, out_cubic(prog(lt, 0, 0.5))))
        top = lerp(self.H + 50, 1360, out_cubic(prog(lt, 0.5, 0.85)))
        d.rounded_rectangle((70, top, self.W - 70, top + 460), 44, fill=k.PAPER)
        k.text(img, (120, top + 90), self.job['name'], k.fit_font(k.HEAD, 120, self.job['name'], 560), k.INK, anchor='lm')
        if s.get('latin'):
            k.text(img, (self.W - 120, top + 95), s['latin'], k.F(k.GM, 40), k.B, anchor='rm')
        for n, line in enumerate(s.get('specs', [])[:3]):
            k.text(img, (124, top + 210 + n * 72), line, k.F(k.PSB, 44), k.INK, anchor='lm')
        return img

    def spec_zoom(self, lt):
        k, s = self.k, self.job['scenes']['spec_zoom']
        fx, fy = self.zoom_focus
        z = lerp(1.0, 1.55, io_(prog(lt, 0.0, 0.7)))
        img = Image.blend(k.zoom_at(self.zoom_plate, z, fx, fy), k.canvas(k.INK), 0.12)
        d = ImageDraw.Draw(img)
        for n, (ex, ey) in enumerate(self.zoom_marks[:3]):
            sx = (ex - (fx - fx / z)) * z if z > 1 else ex
            sy = (ey - (fy - fy / z)) * z if z > 1 else ey
            kk = out_back(prog(lt, 0.7 + n * 0.12, 1.0 + n * 0.12), 2.2)
            k.ring(img, sx, sy, 150 * kk, k.A, width=14)
            for j in range(3):
                tw = abs(math.sin(lt * 9 + j * 2.1 + n))
                k.sparkle(d, sx + [-150, 160, 30][j], sy + [-150, -110, -190][j], 40 * tw * kk, k.HI)
        l1, l2 = (s.get('title', ['', '']) + ['', ''])[:2]
        k.text(img, (self.W / 2, 1450), l1, k.fit_font(k.HEAD, 210, l1, 960), k.PAPER, stroke=10,
               scale=out_back(prog(lt, 1.0, 1.3), 2.2))
        k.text(img, (self.W / 2, 1650), l2, k.fit_font(k.HEAD, 210, l2, 960), k.A, stroke=10,
               scale=out_back(prog(lt, 1.12, 1.42), 2.2))
        k.pill(img, self.W / 2, 1830, s.get('tag', ''), k.F(k.PB, 40), k.INK, k.A, alpha=out_cubic(prog(lt, 1.4, 1.7)))
        k.flood(img, self.W / 2, self.H / 2, lerp(0, 2300, io_(prog(lt, 2.45, 2.8))), k.A)
        return img

    def spec_loupe(self, lt):
        k, s = self.k, self.job['scenes']['spec_loupe']
        img = k.canvas(k.A)
        d = ImageDraw.Draw(img)
        k.paste(img, self.loupe_st, *self.loupe_center, scale=out_back(prog(lt, 0.0, 0.4), 1.8))
        nx, ny = self.loupe_point
        kk = out_back(prog(lt, 0.45, 0.8), 2.0)
        if kk > 0.02:
            clean = img.copy()
            k.ring(img, nx, ny, 58 * kk, k.HI, width=9)
            k.loupe(img, clean, nx, ny, 250, 400, 175, 2.6, kk)
            n = lerp(0, 100, out_cubic(prog(lt, 0.7, 1.3)))
            k.pill(img, 250, 645, f"{s.get('meter_label', '지수')} {n:.0f}%", k.F(k.GM, 46), k.INK, k.HI)
        l1, l2 = (s.get('title', ['', '']) + ['', ''])[:2]
        k.text(img, (self.W / 2, 1480), l1, k.fit_font(k.HEAD, 200, l1, 960), k.INK, scale=out_back(prog(lt, 1.0, 1.3), 2.2))
        k.text(img, (self.W / 2, 1690), l2, k.fit_font(k.HEAD, 200, l2, 960), k.PAPER, stroke=10,
               scale=out_back(prog(lt, 1.12, 1.42), 2.2))
        k.pill(img, self.W / 2, 1860, s.get('tag', ''), k.F(k.PB, 40), k.PAPER, k.INK, alpha=out_cubic(prog(lt, 1.4, 1.7)))
        sweep = io_(prog(lt, 2.45, 2.8))
        top = lerp(self.H, -10, sweep)
        if sweep > 0 and top < self.H:
            d.rectangle((0, top, self.W, self.H), fill=k.INK)
        return img

    HIT = 1.0
    L_START, L_END = (540, 860), (880, 230)
    CLOUD = (186, 232, 120)

    def _launch_pos(self, t):
        e = clamp(t) ** 1.6
        return (lerp(self.L_START[0], self.L_END[0], e),
                lerp(self.L_START[1], self.L_END[1], e) - 160 * math.sin(math.pi * e), e)

    def gag_launch(self, lt):
        k, s = self.k, self.job['scenes']['gag_launch']
        img = k.canvas(k.INK)
        d = ImageDraw.Draw(img)
        hit = self.HIT
        if lt < hit:
            tremble = 7 * math.sin(lt * 70) * prog(lt, 0.45, hit)
            k.paste(img, self.gag_st, self.L_START[0] + tremble, self.L_START[1], scale=out_back(prog(lt, 0, 0.3), 1.8))
            k.text(img, (self.W / 2, 1520), s.get('setup', ''), k.fit_font(k.HEAD, 120, s.get('setup', ''), 960),
                   k.PAPER, stroke=8, alpha=out_cubic(prog(lt, 0.1, 0.35)))
        else:
            kk = prog(lt, hit, hit + 0.95)
            pk = prog(lt, hit, hit + 0.7)
            if pk < 1:
                col = tuple(int(lerp(c, i, pk)) for c, i in zip(self.CLOUD, k.INK))
                for n in range(7):
                    a = 1.9 + n * 0.42
                    dist = 60 + 300 * out_cubic(pk)
                    r = (70 + n % 3 * 28) * (0.7 + out_cubic(pk))
                    x, y = self.L_START[0] + math.cos(a) * dist, self.L_START[1] + 120 + math.sin(a) * dist * 0.6
                    d.ellipse((x - r, y - r, x + r, y + r), fill=col)
            for j in range(1, 11):
                tj = kk - j * 0.07
                if tj <= 0:
                    break
                x, y, e = self._launch_pos(tj)
                age = j / 10
                r = (30 + 70 * (1 - e)) * (0.7 + age)
                d.ellipse((x - r, y - r, x + r, y + r),
                          fill=tuple(int(lerp(c, i, age * 0.8)) for c, i in zip(self.CLOUD, k.INK)))
            if kk < 1:
                x, y, e = self._launch_pos(kk)
                k.paste(img, self.gag_st, x, y, scale=max(0.0, 1 - e) ** 1.2, rot=-760 * e)
            tw = prog(lt, hit + 0.9, hit + 1.3)
            if 0 < tw < 1:
                k.sparkle(d, self.L_END[0], self.L_END[1], 85 * math.sin(math.pi * tw), k.HI)
                k.sparkle(d, self.L_END[0] + 55, self.L_END[1] - 45, 34 * math.sin(math.pi * tw), k.PAPER)
            k.text(img, (300, 600), s.get('hit', '뿡!'), k.F(k.HEAD, 300), k.HI, stroke=16,
                   scale=out_back(prog(lt, hit, hit + 0.22), 3.0), rotate=10 + 4 * math.sin(lt * 20),
                   alpha=1 - prog(lt, hit + 1.2, hit + 1.5))
            k.text(img, (self.W / 2, 1500), s.get('title', ''), k.fit_font(k.HEAD, 190, s.get('title', ''), 960),
                   k.PAPER, stroke=10, scale=out_back(prog(lt, hit + 0.55, hit + 0.85), 2.2))
            k.pill(img, self.W / 2, 1720, s.get('tag', ''), k.F(k.PB, 40), k.INK, k.HI,
                   alpha=out_cubic(prog(lt, hit + 0.85, hit + 1.15)))
        if hit <= lt < hit + 0.4:
            amp = 24 * (1 - (lt - hit) / 0.4)
            shaken = k.canvas(k.INK)
            shaken.paste(img, (int(amp * math.sin(lt * 95)), int(amp * 0.6 * math.cos(lt * 80))))
            img = shaken
        f = int((lt - hit) * self.FPS)
        if 0 <= f < 3:
            img = Image.blend(img, k.canvas(k.PAPER), [0.9, 0.5, 0.2][f])
        k.flood(img, self.W / 2, 1180, lerp(0, 2300, io_(prog(lt, 2.65, 3.0))), k.HI)
        return img

    def meter(self, lt):
        k, s = self.k, self.job['scenes']['meter']
        img = k.canvas(k.HI)
        d = ImageDraw.Draw(img)
        kk = io_(prog(lt, 0.4, 1.9))
        sc = lerp(0.72, 1.0, out_back(prog(lt, 0.4, 2.0), 1.2))
        k.paste(img, self.meter_st, self.W / 2, 760, scale=sc * out_back(prog(lt, 0, 0.35), 1.8))
        x0, x1, y = 120, self.W - 120, 1390
        d.rounded_rectangle((x0, y - 34, x1, y + 34), 34, fill=k.PAPER, outline=k.INK, width=6)
        if kk > 0:
            d.rounded_rectangle((x0 + 8, y - 26, lerp(x0 + 60, x1 - 8, kk), y + 26), 26, fill=k.A)
        v0, v1 = s['from'], s['to']
        dec = s.get('decimals', 2)
        k.text(img, (self.W / 2, 1230), f"{lerp(v0, v1, kk):.{dec}f}{s.get('unit', '')}", k.F(k.GM, 120), k.INK)
        k.text(img, (x0, y + 90), s.get('from_label', ''), k.F(k.PSB, 38), k.INK, anchor='lm')
        k.text(img, (x1, y + 90), s.get('to_label', ''), k.F(k.PSB, 38), k.INK, anchor='rm')
        k.text(img, (self.W / 2, 1640), s.get('title', ''), k.fit_font(k.HEAD, 200, s.get('title', ''), 960), k.INK,
               scale=out_back(prog(lt, 2.0, 2.3), 2.2))
        k.pill(img, self.W / 2, 1830, s.get('tag', ''), k.F(k.PB, 40), k.PAPER, k.INK, alpha=out_cubic(prog(lt, 2.2, 2.5)))
        return img

    def burst(self, lt):
        k = self.k
        n = len(self.burst_items)
        i = min(n - 1, int(lt / BEAT))
        local = lt - i * BEAT
        bg = [k.B, k.A, k.INK, k.HI, k.B, k.A][i % 6]
        fg = k.PAPER if bg in (k.B, k.INK) else k.INK
        img = k.canvas(bg)
        st, title, sub = self.burst_items[i]
        k.paste(img, st, self.W / 2, 860, scale=out_back(prog(local, 0, 0.18), 2.6), rot=[-5, 4, -3, 5, -4, 3][i % 6])
        k.text(img, (self.W / 2, 1480), title, k.fit_font(k.HEAD, 150, title, 960), fg,
               scale=out_back(prog(local, 0.04, 0.2), 2.4))
        k.text(img, (self.W / 2, 1640), sub, k.F(k.PB, 56), fg, alpha=out_cubic(prog(local, 0.1, 0.25)))
        k.text(img, (self.W - k.SAFE, k.SAFE + 40), f'{i + 1:02d} / {n:02d}', k.F(k.GM, 40), fg, anchor='rm')
        return img

    def endcard(self, lt):
        k, s = self.k, self.job['scenes']['endcard']
        img = k.canvas(k.INK)
        k.text(img, (self.W / 2, 640), s.get('kicker', ''), k.F(k.PB, 76), k.PAPER, alpha=out_cubic(prog(lt, 0, 0.3)))
        k.text(img, (self.W / 2, 860 + 1100 * (1 - out_back(prog(lt, 0.05, 0.4), 1.4))), self.job['name'],
               k.fit_font(k.HEAD, 280, self.job['name'], 960), k.A)
        k.text(img, (self.W / 2, 1080), s.get('title', ''), k.F(k.HEAD, 120), k.PAPER, alpha=out_cubic(prog(lt, 0.45, 0.8)))
        k.pill(img, self.W / 2, 1300, s.get('tag', ''), k.F(k.PB, 44), k.INK, k.A, alpha=out_cubic(prog(lt, 0.7, 1.0)))
        k.text(img, (self.W / 2, 1440), s.get('footnote', ''), k.F(k.PSB, 38), (170, 170, 170),
               alpha=out_cubic(prog(lt, 0.9, 1.2)))
        k.flood(img, self.W / 2, 860, lerp(0, 2300, io_(prog(lt, 2.6, 3.0))), k.A)
        return img

    # ---------- timeline ----------
    def render(self, t):
        for name in ORDER:
            a = self.t0[name]
            if a <= t < a + SCENE_LEN[name]:
                img = getattr(self, name)(t - a)
                if a > 0 and (t - a) < 2 / self.FPS:
                    img = self.k.punch(img)
                return img
        return self.endcard(SCENE_LEN['endcard'] - 1e-3)

    def sfx(self, path):
        tr = Track(self.DUR, seed=5)
        gag = self.t0['gag_launch']
        hit = gag + self.HIT
        for name in ORDER[1:]:
            if name != 'gag_launch':
                tr.pop(self.t0[name], 1200, 400, gain=0.22)
        for n in range(len(self.burst_items)):
            tr.pop(self.t0['burst'] + n * BEAT, 700 + n * 90, 350, gain=0.22)
        tr.pop(self.t0['reveal'] + 0.45, 500, 1400, 0.14, 0.25)
        tr.fart_body(hit)
        tr.whoosh(hit + 0.3, 0.65, 0.12, tone=0.65)
        tr.ting(hit + 0.95)
        m = self.job['scenes']['meter']
        g0, g1 = self.t0['meter'] + 0.4, self.t0['meter'] + 1.9
        dec = m.get('decimals', 2)
        step = m.get('tick', 10 ** -dec * 5)
        steps = max(1, min(24, round(abs(m['to'] - m['from']) / step)))
        tr.counter(g0, g1, steps, inv_smoothstep, [67, 69, 71, 72, 74, 76, 77, 79, 81, 83, 84, 86, 88, 89, 91, 93, 95])
        tr.riser(g0, g1, io_)
        tr.chime(g1)
        n0, n1 = self.t0['spec_loupe'] + 0.7, self.t0['spec_loupe'] + 1.3
        tr.counter(n0, n1, 10, inv_out_cubic, [72, 74, 76, 77, 79, 81, 83, 84, 86, 88], 0.07, 0.11, 0.05)
        tr.blip(n1 + 0.02, 91, 0.35, 0.2)
        tr.blip(n1 + 0.14, 96, 0.6, 0.22)
        return tr.save(path), hit

    def run(self):
        out = Path(self.job['output'])
        out.parent.mkdir(parents=True, exist_ok=True)
        music = self.cache / 'music.wav'
        self.cache.mkdir(parents=True, exist_ok=True)
        fx, hit = self.sfx(self.cache / 'sfx.wav')
        music_bouncy.build(music, self.DUR, groove_start=self.t0['reveal'], tapestop=(hit - 0.5, hit),
                           resume=hit + 1.0, burst=(self.t0['burst'], self.t0['endcard']), tada=self.t0['endcard'],
                           tag=self.t0['endcard'] + 1.0)
        inputs = [music, fx]
        mix = f'[1:a]atrim=0:{self.DUR},asetpts=N/SR/TB,afade=t=out:st={self.DUR - 0.6}:d=0.6[m];'
        if self.gag_audio and self.gag_sound_at is not None:
            inputs.append(Path(self.gag_audio))
            a = float(self.gag_sound_at)
            mix += (f'[3:a]atrim=start={a - 0.02}:end={a + 0.83},asetpts=N/SR/TB,highpass=f=60,lowpass=f=4200,'
                    f'equalizer=f=150:t=q:w=1.2:g=7,equalizer=f=3500:t=q:w=1.5:g=-6,'
                    f'agate=threshold=0.02:ratio=3:attack=2:release=80,volume=17dB,'
                    f'afade=t=in:d=0.01,afade=t=out:st=0.55:d=0.3,adelay={int(hit * 1000)}:all=1[f];'
                    f'[m][f][2:a]amix=inputs=3:normalize=0:duration=first,{AUDIO_TAIL}[a]')
        else:
            mix += f'[m][2:a]amix=inputs=2:normalize=0:duration=first,{AUDIO_TAIL}[a]'
        total = int(self.DUR * self.FPS)
        emit('render_started', seconds=self.DUR, frames=total)
        encode(lambda n: self.render(n / self.FPS), total, self.W, self.H, self.FPS, inputs, mix, out, self.DUR,
               on_progress=lambda p: emit('render_progress', percent=round(p * 100, 1)))
        meta = {'pipeline_id': PIPELINE, 'pipeline_version': VERSION, 'duration': self.DUR, 'fps': self.FPS,
                'size': [self.W, self.H], 'cutout_model': self.model,
                'cutout_license': cutout.MODELS.get(self.model), 'loupe_point': self.loupe_point}
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
        L = Launch(job, cutout_python=py)
        ts = [L.t0[n] + SCENE_LEN[n] * 0.7 for n in ORDER] + [L.t0['gag_launch'] + 1.3, L.t0['burst'] + 1.2,
                                                               L.t0['meter'] + 1.2, L.t0['spec_loupe'] + 1.8]
        sheet = Image.new('RGB', (6 * 300, 2 * 533))
        for i, t in enumerate(ts):
            sheet.paste(L.render(t).resize((300, 533)), ((i % 6) * 300, (i // 6) * 533))
        out = Path(job['output']).with_suffix('.stills.jpg')
        sheet.save(out, quality=88)
        print(json.dumps({'stills': str(out), 'loupe_point': L.loupe_point}))
        return 0
    try:
        Launch(job, cutout_python=py).run()
    except Exception as error:  # report as a pipeline event; the app shows the message
        emit('failed', message='런칭 패러디 렌더에 실패했습니다.', detail=str(error)[:400])
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
