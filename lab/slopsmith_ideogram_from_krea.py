import json
from pathlib import Path
import modal

app = modal.App("slopsmith-ideogram-from-krea")
OUT = Path(r"F:\modal-gui\lab\2026-09-29-slopsmith-brand")

PROFILE_DESC = "A bold sculptural S-shaped monogram matching the supplied Krea reference: the left half is rough, pitted dark graphite casting with irregular hammered texture; the right half is a smooth brushed silver metal ribbon with clean machined edges; a thin acid-lime finishing line glows through the central seam. The S is one continuous recognizable symbol, centered, high contrast, with no other objects."

BANNER = {
    "high_level_description": "A YouTube channel banner for SLOPSMITH, where rough AI ideas are refined into crafted work. The visual identity is based on the supplied Krea profile emblem.",
    "style_description": {"aesthetics":"Premium industrial design studio identity, tactile metal, restrained editorial composition","lighting":"Raking light reveals rough graphite and brushed silver; a controlled acid-lime glow traces the seam","medium":"graphic_design","art_style":"Photographic sculptural emblem with precise bold typography","color_palette":["#101214","#25282A","#D1D7D2","#8CFF56","#F3F0E8"]},
    "compositional_deconstruction": {"background":"A continuous matte near-black charcoal field with subtle graphite grain. Keep all important content inside the central horizontal safe band for YouTube cropping.","elements":[{"type":"obj","bbox":[300,100,700,400],"desc":PROFILE_DESC+" Place the emblem large on the left side of the central safe band, partially cropped by the left edge like a monumental workshop mark.","color_palette":["#25282A","#D1D7D2","#8CFF56"]},{"type":"text","bbox":[390,450,610,900],"text":"SLOPSMITH","desc":"The exact word SLOPSMITH in one line, bold condensed uppercase sans-serif, off-white, centered in the safe band to the right of the emblem, clean spacing and no extra words.","color_palette":["#F3F0E8"]}]}
}

PROFILE = {
    "high_level_description":"A square YouTube profile icon rebuilding the supplied Krea S monogram as a crisp brand mark.",
    "style_description": {"aesthetics":"Minimal premium industrial identity, bold silhouette, legible at small size","lighting":"One soft raking highlight across the polished silver half and a restrained lime seam glow","medium":"graphic_design","art_style":"Sculptural metal monogram on a flat dark field","color_palette":["#101214","#25282A","#D1D7D2","#8CFF56"]},
    "compositional_deconstruction": {"background":"A uniform near-black circular-safe field with generous margin.","elements":[{"type":"obj","bbox":[140,140,860,860],"desc":PROFILE_DESC+" Center the symbol with no text, no border, no tools and no additional decoration. It must remain clearly readable when cropped into a small round profile image.","color_palette":["#25282A","#D1D7D2","#8CFF56"]}]}
}

@app.local_entrypoint()
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    worker = modal.Cls.from_name("local-image-gen-modal-test", "ImageGen")()
    vol = modal.Volume.from_name("local-image-gen-results-v1")
    jobs = [("ideogram-slopsmith-banner-v2", BANNER, 2048, 1152, 29103),("ideogram-slopsmith-profile-v2", PROFILE, 1024, 1024, 29104)]
    for name, caption, width, height, seed in jobs:
        result = worker.generate.remote("ideogram4", json.dumps(caption, ensure_ascii=False), width, height, seed)
        target = OUT / f"{name}.png"
        with target.open("wb") as f:
            for chunk in vol.read_file(f"ideogram4-{seed}.png"):
                f.write(chunk)
        print({"name":name,"result":result,"path":str(target)}, flush=True)
