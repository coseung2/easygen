"""Assemble the six MiniMax Ref2V sky clips into a finished MP4."""
from __future__ import annotations
import subprocess
from pathlib import Path
from lab_paths import font_path, series_path

ROOT = series_path("09-violet-sky")
CLIPS = [ROOT / "clips" / f"c{i}.mp4" for i in range(1, 7)]
MUSIC = series_path("music-beds", "es-bed-04.flac")
OUT = ROOT / "final" / "09_violet_sky_ref2v.mp4"
WORK = ROOT / "final" / "work"
FONT = font_path("BMJUA_ttf.ttf")
CAPTIONS = [
    "하늘은 사실 보라색이어야 해요",
    "햇빛은 여러 색으로 이루어져요",
    "파란빛과 보랏빛은 더 잘 흩어져요",
    "우리 눈에는 파란 하늘로 보여요",
    "빛이 흩어지는 길이가 달라서 그래요",
    "하늘빛에는 빛의 과학이 숨어 있어요",
]

def fp(path: Path) -> str:
    return path.as_posix().replace("\\", "/").replace(":", r"\:")

def main() -> None:
    if not all(p.is_file() for p in CLIPS):
        raise SystemExit("missing Ref2V clip")
    WORK.mkdir(parents=True, exist_ok=True); OUT.parent.mkdir(parents=True, exist_ok=True)
    caps=[]
    for i, value in enumerate(CAPTIONS, 1):
        p=WORK/f"caption-{i:02d}.txt"; p.write_text(value, encoding="utf-8"); caps.append(p)
    args=[]
    for p in CLIPS: args += ["-i", str(p)]
    args += ["-i", str(MUSIC)]
    g=[]
    for i in range(6):
        g += [f"[{i}:v]trim=duration=5,setpts=PTS-STARTPTS,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=24,setsar=1[v{i}]", f"[{i}:a]atrim=duration=5,asetpts=PTS-STARTPTS,aresample=48000[a{i}]"]
    g.append("".join(f"[v{i}][a{i}]" for i in range(6))+"concat=n=6:v=1:a=1[basev][basea]")
    cur="basev"
    for i,p in enumerate(caps):
        out=f"cap{i}"; g.append(f"[{cur}]drawtext=fontfile='{fp(FONT)}':textfile='{fp(p)}':fontcolor=white:fontsize=64:line_spacing=14:borderw=5:bordercolor=black@0.65:shadowx=0:shadowy=3:x=(w-text_w)/2:y=850:enable='between(t,{i*5},{i*5+5})'[{out}]"); cur=out
    g += [f"[{cur}]null[finalv]", "[basea]volume=0.22[clipa]", "[6:a]atrim=duration=30,asetpts=PTS-STARTPTS,volume=0.55,afade=t=out:st=28:d=2[mus]", "[clipa][mus]amix=inputs=2:duration=first:normalize=0[finala]"]
    cmd=["ffmpeg","-y",*args,"-filter_complex",";".join(g),"-map","[finalv]","-map","[finala]","-c:v","libx264","-preset","fast","-crf","19","-pix_fmt","yuv420p","-r","24","-c:a","aac","-b:a","192k","-ar","48000","-t","30","-movflags","+faststart",str(OUT)]
    subprocess.run(cmd, check=True); print(OUT)

if __name__ == "__main__": main()
