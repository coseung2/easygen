"""Assemble the six MiniMax Ref2V rainbow clips into a verified MP4."""

from __future__ import annotations

import subprocess
from pathlib import Path
from lab_paths import font_path, series_path


ROOT = series_path("08-rainbow")
CLIPS = [ROOT / "clips-ref2v" / f"c{i}-ref2v.mp4" for i in range(1, 7)]
MUSIC = series_path("music-beds", "es-bed-02.flac")
OUT = ROOT / "final" / "08_rainbow_ref2v.mp4"
WORK = ROOT / "final" / "work"
FONT = font_path("BMJUA_ttf.ttf")

CAPTIONS = [
    "무지개는 반원일까?",
    "햇빛과 물방울이 만나\n빛이 나뉘어요",
    "땅이 아래쪽을 가려요",
    "높은 곳에선 원이 보여요",
    "무지개는 보는 사람을\n중심으로 생겨요",
    "무지개는 원!\n땅에서는 일부만 보일 뿐",
]


def filter_path(path: Path) -> str:
    return path.as_posix().replace("\\", "/").replace(":", r"\:")


def main() -> None:
    if not all(path.is_file() for path in CLIPS):
        missing = [str(path) for path in CLIPS if not path.is_file()]
        raise SystemExit(f"missing Ref2V clips: {missing}")
    if not MUSIC.is_file():
        raise SystemExit(f"missing music: {MUSIC}")
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    caption_files = []
    for index, caption in enumerate(CAPTIONS, 1):
        path = WORK / f"caption-{index:02d}.txt"
        path.write_text(caption, encoding="utf-8")
        caption_files.append(path)

    inputs = []
    for clip in CLIPS:
        inputs += ["-i", str(clip)]
    inputs += ["-i", str(MUSIC)]
    graph = []
    for index in range(6):
        graph.append(
            f"[{index}:v]trim=duration=5,setpts=PTS-STARTPTS,"
            f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=24,setsar=1[v{index}]"
        )
        graph.append(
            f"[{index}:a]atrim=duration=5,asetpts=PTS-STARTPTS,aresample=48000[a{index}]"
        )
    graph.append("".join(f"[v{i}][a{i}]" for i in range(6)) + "concat=n=6:v=1:a=1[basev][basea]")
    current = "basev"
    for index, caption in enumerate(caption_files):
        out = f"cap{index}"
        start = index * 5
        graph.append(
            f"[{current}]drawtext=fontfile='{filter_path(FONT)}':"
            f"textfile='{filter_path(caption)}':fontcolor=white:fontsize=64:"
            f"line_spacing=14:borderw=5:bordercolor=black@0.65:shadowx=0:shadowy=3:"
            f"x=(w-text_w)/2:y=850:enable='between(t,{start},{start + 5})'[{out}]"
        )
        current = out
    graph.append(f"[{current}]null[finalv]")
    graph.append("[basea]volume=0.22[clipa]")
    graph.append("[6:a]atrim=duration=30,asetpts=PTS-STARTPTS,volume=0.55,afade=t=out:st=28:d=2[mus]")
    graph.append("[clipa][mus]amix=inputs=2:duration=first:normalize=0[finala]")
    command = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", "[finalv]", "-map", "[finala]", "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", "24", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", "30", "-movflags", "+faststart", str(OUT)]
    subprocess.run(command, check=True)
    print(OUT)


if __name__ == "__main__":
    main()
