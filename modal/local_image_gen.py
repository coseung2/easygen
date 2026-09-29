"""Modal test app for the supplied local-image-gen ComfyUI assets.

Downloads the two public Comfy-Org model sets into a dedicated Volume and
tests one Krea 2 Turbo job plus one Ideogram 4 job. This is an evaluation app,
not a production GUI pipeline.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import modal


app = modal.App("local-image-gen-modal-test")
models = modal.Volume.from_name("local-image-gen-models-v1", create_if_missing=True)
results = modal.Volume.from_name("local-image-gen-results-v1", create_if_missing=True)
MODEL_DIR = Path("/models")
RESULT_DIR = Path("/results")
COMFY_DIR = Path("/root/ComfyUI")
PORT = 8188

MODEL_FILES = {
    "krea2": [
        ("Comfy-Org/Krea-2", "diffusion_models/krea2_turbo_fp8_scaled.safetensors"),
        ("Comfy-Org/Krea-2", "text_encoders/qwen3vl_4b_fp8_scaled.safetensors"),
        ("Comfy-Org/Krea-2", "vae/qwen_image_vae.safetensors"),
    ],
    "ideogram4": [
        ("Comfy-Org/Ideogram-4", "diffusion_models/ideogram4_fp8_scaled.safetensors"),
        ("Comfy-Org/Ideogram-4", "diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors"),
        ("Comfy-Org/Qwen3-VL", "text_encoders/qwen3vl_8b_fp8_scaled.safetensors"),
        ("Comfy-Org/flux2-dev", "split_files/vae/flux2-vae.safetensors"),
    ],
}

image = modal.Image.from_id("im-AYSPVNRooQYXy8IgQlPWOJ").run_commands(
    "git -C /root/ComfyUI fetch --depth 1 origin tag v0.37.0 && git -C /root/ComfyUI checkout --detach v0.37.0",
    "cd /root/ComfyUI && test $(git rev-parse HEAD) = 73c9bad4d21e7addbe1d13bc92eee0f1431b017d",
    "python -m pip install -r /root/ComfyUI/requirements.txt",
)
download_image = modal.Image.debian_slim(python_version="3.12").pip_install("huggingface_hub>=0.36,<1")


@app.function(image=download_image, volumes={str(MODEL_DIR): models}, timeout=3600)
def download_models() -> dict[str, list[str]]:
    from huggingface_hub import hf_hub_download

    downloaded: dict[str, list[str]] = {"krea2": [], "ideogram4": []}
    for model_name, files in MODEL_FILES.items():
        for repo_id, filename in files:
            path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=str(MODEL_DIR))
            downloaded[model_name].append(str(path))
    models.commit()
    return downloaded


def krea_graph(prompt: str, width: int, height: int, seed: int, prefix: str) -> dict:
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "krea2_turbo_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "seed": seed, "steps": 8, "cfg": 1, "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": prefix}},
    }


def ideogram_graph(caption: str, width: int, height: int, seed: int, prefix: str) -> dict:
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "ideogram4_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "ideogram4_unconditional_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_8b_fp8_scaled.safetensors", "type": "ideogram4", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": caption}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "7": {"class_type": "CFGOverride", "inputs": {"model": ["1", 0], "cfg": 3, "start_percent": 0.7, "end_percent": 1}},
        "8": {"class_type": "DualModelGuider", "inputs": {"model": ["7", 0], "model_negative": ["2", 0], "positive": ["5", 0], "negative": ["6", 0], "cfg": 7}},
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "10": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "11": {"class_type": "Ideogram4Scheduler", "inputs": {"steps": 20, "width": width, "height": height, "mu": 0.0, "std": 1.75}},
        "12": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["8", 0], "sampler": ["10", 0], "sigmas": ["11", 0], "latent_image": ["12", 0]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["4", 0]}},
        "15": {"class_type": "SaveImage", "inputs": {"images": ["14", 0], "filename_prefix": prefix}},
    }


@app.cls(image=image, gpu="L40S", volumes={"/models": models, "/results": results}, timeout=1200, startup_timeout=600, scaledown_window=30, max_containers=1)
class ImageGen:
    @modal.enter()
    def start(self):
        for model_name, files in MODEL_FILES.items():
            for _, filename in files:
                path = MODEL_DIR / filename
                if not path.is_file():
                    raise FileNotFoundError(path)
                target_name = "vae/flux2-vae.safetensors" if filename == "split_files/vae/flux2-vae.safetensors" else filename
                target = COMFY_DIR / "models" / target_name
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() or target.is_symlink():
                    target.unlink()
                target.symlink_to(path)
        self.input_dir = Path("/tmp/image-input")
        self.output_dir = Path("/tmp/image-output")
        self.user_dir = Path("/tmp/image-user")
        for directory in (self.input_dir, self.output_dir, self.user_dir):
            directory.mkdir(exist_ok=True)
        self.server = subprocess.Popen([
            "python", "main.py", "--listen", "127.0.0.1", "--port", str(PORT),
            "--input-directory", str(self.input_dir), "--output-directory", str(self.output_dir),
            "--user-directory", str(self.user_dir), "--database-url", "sqlite:////tmp/image.db",
        ], cwd=COMFY_DIR)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                raise RuntimeError("ComfyUI stopped during startup")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/system_stats", timeout=4):
                    return
            except OSError:
                time.sleep(2)
        raise TimeoutError("ComfyUI startup timed out")

    @modal.exit()
    def stop(self):
        self.server.terminate()

    @modal.method()
    def generate(self, model_name: str, prompt_or_caption: str, width: int, height: int, seed: int) -> dict:
        graph = krea_graph(prompt_or_caption, width, height, seed, "local-image-gen/krea2") if model_name == "krea2" else ideogram_graph(prompt_or_caption, width, height, seed, "local-image-gen/ideogram4")
        prompt_id = str(uuid.uuid4())
        request = urllib.request.Request(f"http://127.0.0.1:{PORT}/prompt", data=json.dumps({"prompt": graph, "prompt_id": prompt_id}).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:
            prompt_id = json.load(response)["prompt_id"]
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/history/{prompt_id}", timeout=30) as response:
                entry = json.load(response).get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(str(status.get("messages")))
                if status.get("completed"):
                    images = [i for node in entry.get("outputs", {}).values() for i in node.get("images", [])]
                    if not images:
                        raise RuntimeError("No image output")
                    record = images[0]
                    source = self.output_dir / record.get("subfolder", "") / record["filename"]
                    data = source.read_bytes()
                    target = RESULT_DIR / f"{model_name}-{seed}.png"
                    with results.batch_upload(force=True) as upload:
                        upload.put_file(source, str(target.relative_to(RESULT_DIR)))
                    return {"model": model_name, "prompt_id": prompt_id, "filename": record["filename"], "bytes": len(data)}
            time.sleep(2)
        raise TimeoutError("Image generation timed out")


@app.local_entrypoint()
def test() -> None:
    download_models.remote()
    worker = ImageGen()
    jobs = [
        ("krea2", "A cinematic portrait of a young Korean woman in a rainy neon cafe, soft reflections, textured film grain, blue and amber light", 1024, 1024, 12001),
        ("ideogram4", '{"high_level_description":"A minimal square label design reading \\"DENO STUDIO\\" in centered capitals above a thin rust-colored rule on a flat cream field.","style_description":{"aesthetics":"Restrained editorial label, precise spacing, generous margins, no ornament","lighting":"Flat even print lighting","medium":"graphic_design","art_style":"Two-color flat vector label","color_palette":["#F1EBDF","#1B1B1B","#B4633A"]},"compositional_deconstruction":{"background":"A flat cream field filling the square.","elements":[{"type":"text","bbox":[400,150,520,850],"text":"DENO STUDIO","desc":"Centered letter-spaced sans-serif capitals in near-black.","color_palette":["#1B1B1B"]},{"type":"obj","bbox":[560,380,572,620],"desc":"A thin horizontal rust-colored rule centered below the wordmark.","color_palette":["#B4633A"]}]}}', 1024, 1024, 12002),
    ]
    for job in jobs:
        print(worker.generate.remote(*job))
