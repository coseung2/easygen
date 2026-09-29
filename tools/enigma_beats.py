"""Detect beat times for the 21-enigma episode music and write beats.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from motion_graphics_pipeline import detect_beats_for
from lab_paths import series_path

EP = series_path("21-enigma-turing")

beats = detect_beats_for(EP / "ae" / "music-30s.wav", 30.0)
(EP / "music" / "beats.json").write_text(
    json.dumps({"beats": beats}, indent=1), encoding="utf-8"
)
print(json.dumps(beats))
