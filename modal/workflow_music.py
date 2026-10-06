"""Independent YuE2 workflow in the caller's own Modal workspace."""

from __future__ import annotations

import json
from pathlib import Path

import modal
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from easygen_runtime.config import resource


app = modal.App(resource("music"))
model_volume = modal.Volume.from_name(resource("music-models"), create_if_missing=True)
output_volume = modal.Volume.from_name(resource("music-outputs"), create_if_missing=True)

image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04",
        add_python="3.12",
    )
    .apt_install("git", "ffmpeg")
    .pip_install(
        "torch==2.10.0",
        "transformers==4.57.6",
        "huggingface-hub==0.36.2",
        "safetensors==0.7.0",
        "tiktoken==0.12.0",
        "numpy==2.2.6",
        "soundfile==0.13.1",
        "accelerate==1.13.0",
    )
    .run_commands(
        "git init /root/YuE && git -C /root/YuE remote add origin https://github.com/multimodal-art-projection/YuE.git && git -C /root/YuE fetch --depth 1 origin 1647252d68b70cbead046ffd3f7caf036dde47ee && git -C /root/YuE checkout --detach 1647252d68b70cbead046ffd3f7caf036dde47ee",
        "python -m pip install --no-deps /root/YuE",
    )
    .add_local_dir(Path(__file__).resolve().parents[1] / 'easygen_runtime', '/root/easygen_runtime')
)


@app.function(
    image=image,
    gpu="L40S",
    volumes={"/models": model_volume, "/outputs": output_volume},
    timeout=3600,
    startup_timeout=1800,
    scaledown_window=60,
    max_containers=1,
)
def generate_music(
    job_id: str,
    style: str,
    lyrics: str,
    seed: int = 4301,
) -> dict[str, object]:
    from yue2 import YuE2Pipeline

    model_volume.reload()
    for name in ('YuE2-3B', 'YuE2-Vae'):
        if not (Path('/models') / name / 'model.safetensors').is_file():
            raise FileNotFoundError('Run modal/bootstrap.py --target music before generation')

    output_dir = Path("/outputs") / job_id
    output_dir.mkdir(parents=True, exist_ok=False)
    request = {
        "style": style,
        "lyrics": lyrics,
        "cot": "full",
        "seed": seed,
    }
    with YuE2Pipeline.from_pretrained(
        "/models/YuE2-3B",
        vae="/models/YuE2-Vae",
        device="cuda",
        local_files_only=True,
    ) as pipe:
        song = pipe(**request)
        song.save_artifacts(output_dir)
        truncated = dict(song.truncated)
    metadata = {
        "job_id": job_id,
        "model": "m-a-p/YuE2-3B",
        "vae": "m-a-p/YuE2-Vae",
        "request": request,
        "audio": f"{job_id}/audio.flac",
        "truncated": truncated,
        "license": "See upstream model terms; no maintainer-specific permission is transferred",
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_volume.commit()
    return metadata


if __name__ == "__main__":
    with app.run():
        print("deployed yue2-music")
