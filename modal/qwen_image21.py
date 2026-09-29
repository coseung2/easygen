"""Private, research-only Qwen-Image 2.1 ComfyUI worker on Modal.

This is an independent experiment, not a released Modal GUI pipeline. The
weights are subject to the Qwen Research License (no commercial use).
"""

from __future__ import annotations

import json
import io
import math
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import modal


app = modal.App("qwen-image-21-research")
weights = modal.Volume.from_name("qwen-image-21-research-weights", create_if_missing=True)

REPO = "Comfy-Org/Qwen-Image-2.1"
REVISION = "9a44dbdb47cefd046be9c0a13476192f34c8db8e"
COMFY_REVISION = "73c9bad4d21e7addbe1d13bc92eee0f1431b017d"
FILES = (
    "diffusion_models/qwen_image_2.1_int8_convrot.safetensors",
    "text_encoders/qwen3vl_8b_int8_convrot.safetensors",
    "vae/qwen_image_2.1_vae_bf16.safetensors",
)
MODEL_DIR = Path("/models")
COMFY_DIR = Path("/root/ComfyUI")
INPUT_DIR = Path("/tmp/qwen-input")
OUTPUT_DIR = Path("/tmp/qwen-output")
PORT = 8188

download_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "huggingface-hub>=0.36,<1"
)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .run_commands(
        "git clone --depth 1 --branch v0.37.0 https://github.com/Comfy-Org/ComfyUI.git /root/ComfyUI",
        f"cd /root/ComfyUI && test $(git rev-parse HEAD) = {COMFY_REVISION}",
        "python -m pip install -r /root/ComfyUI/requirements.txt",
    )
)


@app.function(image=download_image, volumes={str(MODEL_DIR): weights}, timeout=3600)
def download_weights() -> dict[str, int]:
    """Download only the three files used by the supplied INT8 workflow."""
    from huggingface_hub import hf_hub_download

    sizes = {}
    for filename in FILES:
        path = hf_hub_download(REPO, filename, revision=REVISION, local_dir=str(MODEL_DIR))
        sizes[filename] = Path(path).stat().st_size
    weights.commit()
    return sizes


def _graph(prompt: str, width: int, height: int, seed: int, steps: int, edit: bool) -> dict:
    """Core-node equivalent of the Deno workflow, without its resize UI node."""
    graph = {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": Path(FILES[0]).name, "weight_dtype": "default"}},
        "2": {"class_type": "QwenImage21Cache", "inputs": {
            "model": ["1", 0], "device": "auto", "dtype": "default"}},
        "3": {"class_type": "ModelSamplingFlux", "inputs": {
            "model": ["2", 0], "max_shift": 0.693548, "base_shift": 0.5,
            "width": width, "height": height}},
        "4": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": Path(FILES[1]).name, "type": "qwen_image", "device": "default"}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": Path(FILES[2]).name}},
        "6": {"class_type": "TextEncodeQwenImage21", "inputs": {
            "clip": ["4", 0], "vae": ["5", 0], "prompt": prompt,
            "negative_prompt": "", "resolution": 1024}},
        "8": {"class_type": "KSampler", "inputs": {
            "model": ["3", 0], "positive": ["6", 0], "negative": ["6", 1],
            "latent_image": ["7", 0], "seed": seed, "steps": steps,
            "cfg": 1, "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
        "9": {"class_type": "VAEDecode", "inputs": {
            "samples": ["8", 0], "vae": ["5", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {
            "images": ["9", 0], "filename_prefix": "qwen21-research"}},
    }
    if edit:
        graph["11"] = {"class_type": "LoadImage", "inputs": {"image": "reference.png"}}
        graph["6"]["inputs"]["images.image_1"] = ["11", 0]
        graph["8"]["inputs"]["latent_image"] = ["6", 2]
    else:
        graph["7"] = {"class_type": "EmptyLatentImage", "inputs": {
            "width": width, "height": height, "batch_size": 1}}
    return graph


@app.cls(
    image=image, gpu="L40S", volumes={str(MODEL_DIR): weights},
    timeout=900, startup_timeout=600, scaledown_window=30, max_containers=1,
)
class QwenImage21:
    @modal.enter()
    def start(self):
        for filename in FILES:
            source = MODEL_DIR / filename
            if not source.is_file():
                raise RuntimeError(f"Missing model file: {filename}; run download_weights first")
            dest = COMFY_DIR / "models" / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(source)
        INPUT_DIR.mkdir(exist_ok=True)
        OUTPUT_DIR.mkdir(exist_ok=True)
        self.server = subprocess.Popen(
            ["python", "main.py", "--listen", "127.0.0.1", "--port", str(PORT),
             "--input-directory", str(INPUT_DIR), "--output-directory", str(OUTPUT_DIR)],
            cwd=COMFY_DIR,
        )
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                raise RuntimeError("ComfyUI exited before becoming ready")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/system_stats", timeout=3):
                    return
            except (OSError, TimeoutError):
                time.sleep(2)
        raise TimeoutError("ComfyUI did not become ready")

    @modal.exit()
    def stop(self):
        self.server.terminate()
        self.server.wait(timeout=10)

    @modal.method()
    def generate(
        self, prompt: str, width: int = 1024, height: int = 1024,
        seed: int = 42, steps: int = 40, reference_png: bytes | None = None,
    ) -> bytes:
        """Return one PNG. An input PNG switches to image editing."""
        if not prompt or len(prompt) > 10000:
            raise ValueError("Prompt must contain 1-10000 characters")
        if (width % 32 or height % 32 or min(width, height) < 512
                or width * height > 2048 * 2048):
            raise ValueError("Dimensions must be multiples of 32, >=512 and <=4MP")
        if not 1 <= steps <= 40:
            raise ValueError("Steps must be between 1 and 40")
        if reference_png is not None:
            if len(reference_png) > 20_000_000 or not reference_png.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Reference must be a PNG of at most 20MB")
            from PIL import Image

            with Image.open(io.BytesIO(reference_png)) as reference:
                ratio = reference.width / reference.height
            # TextEncodeQwenImage21's resolution=1024 makes the output latent
            # follow the first reference. Sampling shifts if these sizes differ.
            width = max(32, round(math.sqrt(1024 * 1024 * ratio) / 32) * 32)
            height = max(32, round(math.sqrt(1024 * 1024 / ratio) / 32) * 32)
            if width * height > 2048 * 2048:
                raise ValueError("Reference aspect ratio produces an output over 4MP")
            (INPUT_DIR / "reference.png").write_bytes(reference_png)
        graph = _graph(prompt, width, height, seed, steps, reference_png is not None)
        prompt_id = str(uuid.uuid4())
        request = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/prompt",
            data=json.dumps({"prompt": graph, "prompt_id": prompt_id}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                prompt_id = json.load(response)["prompt_id"]
        except urllib.error.HTTPError as exc:
            raise RuntimeError(exc.read().decode("utf-8", "replace")) from exc
        deadline = time.monotonic() + 780
        while time.monotonic() < deadline:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/history/{prompt_id}", timeout=30) as response:
                entry = json.load(response).get(prompt_id)
            if entry:
                if entry.get("status", {}).get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI failed: {entry['status'].get('messages')}")
                if entry.get("status", {}).get("completed"):
                    outputs = entry.get("outputs", {}).get("10", {}).get("images", [])
                    if not outputs:
                        raise RuntimeError("ComfyUI completed without an image")
                    result = outputs[0]
                    return (OUTPUT_DIR / result.get("subfolder", "") / result["filename"]).read_bytes()
            time.sleep(3)
        raise TimeoutError("Qwen image generation timed out")

    @modal.method()
    def health(self) -> dict[str, str]:
        """Check model files and ComfyUI readiness without generating an image."""
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/object_info/TextEncodeQwenImage21", timeout=15) as response:
            info = json.load(response)
        if "TextEncodeQwenImage21" not in info:
            raise RuntimeError("ComfyUI lacks Qwen-Image 2.1 nodes")
        return {"status": "ready", "model_revision": REVISION}


@app.local_entrypoint()
def smoke() -> None:
    print(QwenImage21().health.remote())
