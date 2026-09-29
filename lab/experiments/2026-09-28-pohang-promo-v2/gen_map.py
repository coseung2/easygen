"""삽화 지도 생성 (3단계, ima2-gen oauth/gpt-5.5). 가이드 이미지를 참조로 해안선·핀 위치를 유지시킨다.

사용: python gen_map.py [출력이름]   -> map/<이름>.png (기본 illustrated_v1)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
IMA2 = Path(os.environ.get("IMA2_ROOT", ""))
if not IMA2:
    raise RuntimeError("Set IMA2_ROOT to the separately installed image-generation tool")
GUIDE = HERE / "map" / "guide.png"

PROMPT = (
    "Use case: illustrated tourist map for a vertical short-form travel video. "
    "Input image 1 is a layout guide: green is land, blue is sea, the black line is the exact coastline, "
    "and the six red dots are landmark positions. Keep the coastline shape, the bay and the peninsula "
    "exactly where they are in image 1, and place each landmark exactly on its red dot. Do not draw the red dots.\n"
    "Style: charming hand-drawn illustrated travel map, soft watercolor and colored-pencil texture, warm cream land "
    "with small green hills and clustered trees, turquoise sea with gentle wave strokes, a few tiny boats and seagulls. "
    "A clear light-colored coastal road runs along the whole shoreline from the top dot to the bottom-right dot, "
    "wide enough for a small car to drive on. Top-down map view with slightly raised, cute 3/4 landmark icons.\n"
    "Landmarks (small, clearly readable icons on their dots, north to south):\n"
    "1 top dot: a wooden pier-shaped observation deck shaped like a ship anchor stretching into the sea.\n"
    "2 second dot: a green mountain peak with two colorful paragliders above it.\n"
    "3 third dot: a steel looping walkway sculpture shaped like a roller-coaster track on a hill.\n"
    "4 fourth dot: a traditional Korean pavilion standing over the sea beside a sandy beach.\n"
    "5 the red dot at the far north-east TIP of the big peninsula on the right side (upper right, not inside the bay): "
    "a giant bronze hand sculpture rising from the open sea just off that tip, with a rising sun on the eastern horizon. "
    "Nothing is placed inside the bay; the bay's inner shore stays plain.\n"
    "6 bottom-right dot: a narrow street of old two-story wooden houses with dark tiled roofs and stone steps.\n"
    "Leave calm empty margins at the very top and bottom. "
    "Avoid: any text, letters, numbers, labels, map legends, compass text, watermark, logos, red dots."
)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "illustrated_v1"
    out = HERE / "map" / f"{name}.png"
    (HERE / "map" / f"{name}.prompt.txt").write_text(PROMPT, encoding="utf-8")
    cmd = ["node", "bin/ima2.js", "gen", "--stdin", "--model", "oauth/gpt-5.5", "-q", "high",
           "-s", "1024x1824", "--ref", str(GUIDE), "-o", str(out), "--timeout", "400", "--json"]
    p = subprocess.run(cmd, cwd=IMA2, input=PROMPT, capture_output=True, text=True, encoding="utf-8")
    tail = (p.stdout.strip().splitlines() or [""])[-1]
    try:
        info = json.loads(tail)
        print(json.dumps({"ok": info.get("ok"), "images": info.get("images")}, ensure_ascii=False))
    except Exception:
        print("FAIL rc", p.returncode, p.stdout[-400:], p.stderr[-400:])


if __name__ == "__main__":
    main()
