"""Easygen image runtime on Modal: Krea 2 Turbo and Ideogram 4.

Uses the caller's prefix-scoped model volume prepared by ``modal/bootstrap.py``.
The public image is built from sources, with configurable batch size and text prompts.
The generate method does not accept reference images.
"""

from __future__ import annotations

import base64
import json
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import modal
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from easygen_runtime.config import resource

APP_NAME = resource("image")
app = modal.App(APP_NAME)
models = modal.Volume.from_name(resource("image-models"), create_if_missing=True)
MODEL_DIR = Path("/models")
COMFY_DIR = Path("/root/ComfyUI")
PORT = 8188
MODEL_FILES = [
    "diffusion_models/krea2_turbo_fp8_scaled.safetensors",
    "text_encoders/qwen3vl_4b_fp8_scaled.safetensors",
    "vae/qwen_image_vae.safetensors",
    "diffusion_models/ideogram4_fp8_scaled.safetensors",
    "diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors",
    "text_encoders/qwen3vl_8b_fp8_scaled.safetensors",
    "split_files/vae/flux2-vae.safetensors",
]

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from easygen_runtime.images import comfy_image
image = comfy_image()


def krea_graph(prompt: str, width: int, height: int, seed: int, count: int) -> dict:
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "krea2_turbo_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": count}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "seed": seed, "steps": 8, "cfg": 1, "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "easygen/krea"}},
    }


def ideogram_graph(caption: str, width: int, height: int, seed: int, count: int) -> dict:
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
        "12": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": count}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["9", 0], "guider": ["8", 0], "sampler": ["10", 0], "sigmas": ["11", 0], "latent_image": ["12", 0]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["4", 0]}},
        "15": {"class_type": "SaveImage", "inputs": {"images": ["14", 0], "filename_prefix": "easygen/ideogram"}},
    }


def ideogram_caption(prompt: str, text: str) -> str:
    """Ideogram 4 reads a full structured caption.

    A bare description without style, background and element boxes makes the
    model fall back to a gray "blocked" placeholder, so plain prompts are
    expanded into the complete schema the evaluated captions used.
    """
    stripped = prompt.strip()
    if stripped.startswith("{"):
        return stripped
    elements = []
    if text.strip():
        elements.append({
            "type": "text",
            "bbox": [380, 120, 560, 880],
            "text": text.strip(),
            "desc": f"The exact text {text.strip()} in one line, bold, crisp and correctly spelled, centered. "
                    "This is the only text in the image.",
        })
        elements.append({
            "type": "obj",
            "bbox": [580, 260, 620, 740],
            "desc": "A simple decorative graphic accent that matches the description, placed below the text. "
                    "Purely graphic: no letters, words or numbers.",
        })
    else:
        elements.append({"type": "obj", "bbox": [150, 150, 850, 850], "desc": stripped})
    caption = {
        "high_level_description": stripped,
        "style_description": {
            "aesthetics": "Clean, deliberate composition with balanced spacing",
            "lighting": "Even, soft lighting",
            "medium": "graphic_design" if text.strip() else "photograph",
            "art_style": "Polished professional design" if text.strip() else "Natural high-detail image",
            "color_palette": [],
        },
        "compositional_deconstruction": {
            "background": stripped + (" No additional text, captions or taglines anywhere." if text.strip() else ""),
            "elements": elements,
        },
    }
    return json.dumps(caption, ensure_ascii=False)


def looks_blocked(path: Path) -> bool:
    """The model's learned refusal is a flat gray card; reject it instead of saving."""
    from PIL import Image, ImageStat

    with Image.open(path) as image:
        small = image.convert("RGB").resize((64, 64))
        stat = ImageStat.Stat(small)
    spread = max(stat.stddev)
    mean = sum(stat.mean) / 3
    channel_gap = max(stat.mean) - min(stat.mean)
    return spread < 12 and 70 < mean < 150 and channel_gap < 6


@app.cls(image=image, gpu="L40S", volumes={str(MODEL_DIR): models}, timeout=1200,
         startup_timeout=900, scaledown_window=60, max_containers=1)
class EasygenImage:
    @modal.enter()
    def start(self) -> None:
        for filename in MODEL_FILES:
            source = MODEL_DIR / filename
            if not source.is_file():
                raise FileNotFoundError(source)
            target_name = "vae/flux2-vae.safetensors" if filename.endswith("flux2-vae.safetensors") else filename
            target = COMFY_DIR / "models" / target_name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(source)
        self.output = Path("/tmp/image-output")
        self.output.mkdir(exist_ok=True)
        self.log = open("/tmp/comfyui.log", "wb")
        self.server = subprocess.Popen([
            "python", "main.py", "--listen", "127.0.0.1", "--port", str(PORT),
            "--output-directory", str(self.output), "--database-url", "sqlite:////tmp/image.db",
        ], cwd=COMFY_DIR, stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 600
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/system_stats", timeout=4):
                    return
            except OSError:
                time.sleep(2)
        raise TimeoutError("ComfyUI startup timed out")

    @modal.exit()
    def stop(self) -> None:
        self.server.terminate()

    @modal.method()
    def generate(self, model: str, prompt: str, width: int, height: int, seed: int, count: int = 1, text: str = "") -> dict:
        if model not in {"krea", "ideogram"}:
            raise ValueError(f"unknown model: {model}")
        count = max(1, min(int(count), 4))
        width, height = int(width) - int(width) % 16, int(height) - int(height) % 16
        graph = krea_graph(prompt, width, height, seed, count) if model == "krea" else ideogram_graph(ideogram_caption(prompt, text), width, height, seed, count)
        started = time.time()
        prompt_id = str(uuid.uuid4())
        request = urllib.request.Request(f"http://127.0.0.1:{PORT}/prompt",
                                         data=json.dumps({"prompt": graph, "prompt_id": prompt_id}).encode(),
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                prompt_id = json.load(response)["prompt_id"]
        except urllib.error.HTTPError as exc:
            raise RuntimeError(exc.read().decode("utf-8", "replace")[:1500]) from None
        deadline = time.time() + 1000
        while time.time() < deadline:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/history/{prompt_id}", timeout=60) as response:
                entry = json.load(response).get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(str(status.get("messages"))[:1500])
                if status.get("completed"):
                    records = [r for node in entry.get("outputs", {}).values() for r in node.get("images", [])]
                    if not records:
                        raise RuntimeError("no image output")
                    paths = [self.output / r.get("subfolder", "") / r["filename"] for r in records]
                    kept = [path for path in paths if not looks_blocked(path)]
                    if not kept:
                        raise RuntimeError("모델이 이미지를 만들지 않았습니다(빈 회색 결과). 프롬프트를 더 구체적으로 바꿔 다시 시도하세요.")
                    images = [base64.b64encode(path.read_bytes()).decode() for path in kept]
                    return {"images": images, "seconds": round(time.time() - started, 1), "width": width, "height": height,
                            "rejected": len(paths) - len(kept)}
            time.sleep(2)
        raise TimeoutError("image generation timed out")
