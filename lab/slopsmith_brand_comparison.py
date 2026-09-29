"""Preview Slopsmith channel visuals on the deployed Modal image app."""
from __future__ import annotations

import json
from pathlib import Path

import modal

app = modal.App("slopsmith-brand-comparison")
OUT = Path(r"F:\modal-gui\lab\2026-09-29-slopsmith-brand")

BANNER = (
    "A cinematic wide brand workshop scene for a YouTube channel about polishing rough AI ideas into crafted work. "
    "At the center, a single chunky imperfect graphite-colored lump is being carved and polished into a precise "
    "angular S-shaped metal emblem by a small steel burnishing tool. Fine metal dust and controlled sparks, one "
    "diagonal trail of transformation, dark charcoal workbench, cold polished silver highlights, a restrained acid-lime "
    "light accent. The key sculpture stays compact in the middle third of the wide frame, with calm dark open space "
    "around it. Tactile high-end macro product photography, art-directed not fantasy. No people or written words."
)
PROFILE = (
    "A single bold sculptural S-shaped monogram forged from an imperfect dark graphite chunk, one half rough and "
    "pitted like an unfinished casting, the other half precisely polished into a smooth brushed steel edge. A tiny "
    "acid-lime glint marks the finishing stroke. Centered front view on a solid near-black field, clean silhouette "
    "and generous margin, readable when cropped to a small circle. Tactile contemporary studio identity, one object "
    "only, no person, no lettering, no extra tools."
)
STYLE = {
    "aesthetics": "Inventive design studio identity, precise editorial hierarchy, restrained industrial tactility",
    "lighting": "Raking light skims rough graphite and polished steel; one tiny acid-lime highlight",
    "medium": "graphic_design",
    "art_style": "Sculptural industrial monogram integrated with clean typography",
    "color_palette": ["#111416", "#C8CFCC", "#8CFF56", "#F2F0E8"],
}
IDEOGRAM_BANNER = {
    "high_level_description": "A YouTube channel banner for SLOPSMITH, where rough AI ideas become precisely crafted work.",
    "style_description": STYLE,
    "compositional_deconstruction": {
        "background": "Matte charcoal with restrained grit and broad dark negative space. All important content sits inside a central narrow horizontal band for mobile crop.",
        "elements": [
            {"type": "obj", "bbox": [350, 255, 650, 440], "desc": "One thick angular S emblem, left side raw dark textured cast metal, right side refined brushed steel with crisp facets. A single small acid-lime polishing spark at their boundary. Bold silhouette without tools or people.", "color_palette": ["#22272A", "#BEC6C3", "#8CFF56"]},
            {"type": "text", "bbox": [405, 455, 595, 780], "text": "SLOPSMITH", "desc": "The only text, exactly SLOPSMITH in one line, large condensed bold uppercase geometric sans-serif with generous spacing, centered in the horizontal band.", "color_palette": ["#F2F0E8"]},
        ],
    },
}
IDEOGRAM_PROFILE = {
    "high_level_description": "A small circular-crop-ready profile emblem for SLOPSMITH, a studio refining raw AI ideas.",
    "style_description": STYLE,
    "compositional_deconstruction": {
        "background": "One uniform near-black field with ample clear margin for a circular crop.",
        "elements": [{"type": "obj", "bbox": [200, 200, 800, 800], "desc": "A single bold angular S monogram carved from a dark rough cast-metal block and refined into a polished silver edge on its right half. One tiny acid-lime finishing spark. Thick continuous silhouette, no other objects, legible as a small icon.", "color_palette": ["#24282A", "#D1D7D2", "#8CFF56"]}],
    },
}

@app.local_entrypoint()
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    worker = modal.Cls.from_name("local-image-gen-modal-test", "ImageGen")()
    volume = modal.Volume.from_name("local-image-gen-results-v1")
    jobs = [
        ("krea-banner", "krea2", BANNER, 2048, 1152, 29001),
        ("krea-profile", "krea2", PROFILE, 1024, 1024, 29002),
        ("ideogram-banner", "ideogram4", json.dumps(IDEOGRAM_BANNER, ensure_ascii=False), 2048, 1152, 29003),
        ("ideogram-profile", "ideogram4", json.dumps(IDEOGRAM_PROFILE, ensure_ascii=False), 1024, 1024, 29004),
    ]
    for name, model, prompt, width, height, seed in jobs:
        destination = OUT / (name + ".png")
        if destination.exists():
            print(f"already exists: {destination}", flush=True)
            continue
        print(f"starting {name}", flush=True)
        record = worker.generate.remote(model, prompt, width, height, seed)
        with destination.open("xb") as target:
            for chunk in volume.read_file(f"{model}-{seed}.png"):
                target.write(chunk)
        print(json.dumps({"name": name, "result": record, "path": str(destination)}, ensure_ascii=False), flush=True)
