"""One-shot Enigma rotor A/B: Sol-Attn with Sage versus Comfy Kitchen.

Research-only Lab experiment. Never deploy this App or modify the H3 worker.
Each variant is called at most once, with a 20-minute Modal timeout.
"""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import modal
from tools.lab_paths import lab_path


REPO = Path(__file__).resolve().parents[1]
SOURCE = lab_path("2026-09-28-turing-enigma", "v7")
RESULTS = lab_path("2026-09-29-h3-attention-compare")
WORKFLOW = RESULTS / "source-r2v.json"
INPUT = SOURCE / "h3" / "inputs" / "r2-rotors.png"
PORT = 8188
PROMPT = (
    "Preserve the exact photographic reference: composition, objects, lighting, "
    "desaturated 1940s film look and grain. Do not add, remove, or reshape objects. "
    "No text, letters, numbers, logos, subtitles or UI. No faces. One continuous "
    "shot, no cuts. Animate: the center rotor wheel clicks forward one notch at a "
    "time, three distinct mechanical steps with a brief pause between them, the "
    "neighbouring rotors stay still, light glints move across the brass ridges. "
    "Camera locked."
)

app = modal.App("h3-attention-compare-lab")
image = modal.Image.from_id("im-AYSPVNRooQYXy8IgQlPWOJ").run_commands(
    "git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git /root/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite",
    "if [ -f /root/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt ]; then python -m pip install -r /root/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt; fi",
    "git clone https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler.git /root/ComfyUI/custom_nodes/Comfyui_Minimax_h3_latent_Upscaler",
    "if [ -f /root/ComfyUI/custom_nodes/Comfyui_Minimax_h3_latent_Upscaler/requirements.txt ]; then python -m pip install -r /root/ComfyUI/custom_nodes/Comfyui_Minimax_h3_latent_Upscaler/requirements.txt; fi",
    "git clone https://github.com/Zironic/H3-Optimizations.git /root/ComfyUI/custom_nodes/H3-Optimizations",
    "if [ -f /root/ComfyUI/custom_nodes/H3-Optimizations/requirements.txt ]; then python -m pip install -r /root/ComfyUI/custom_nodes/H3-Optimizations/requirements.txt; fi",
    "git clone https://github.com/Deno2026/comfyui-deno-custom-nodes.git /root/ComfyUI/custom_nodes/comfyui-deno-custom-nodes",
    "if [ -f /root/ComfyUI/custom_nodes/comfyui-deno-custom-nodes/requirements.txt ]; then python -m pip install -r /root/ComfyUI/custom_nodes/comfyui-deno-custom-nodes/requirements.txt; fi",
    "git -C /root/ComfyUI fetch --depth 1 origin tag v0.37.0 && git -C /root/ComfyUI checkout --detach v0.37.0",
    "cd /root/ComfyUI && test $(git rev-parse HEAD) = 73c9bad4d21e7addbe1d13bc92eee0f1431b017d",
    "python -m pip install -r /root/ComfyUI/requirements.txt",
)
models = modal.Volume.from_name("minimax-h3-models")


@app.function(image=image, timeout=300)
def preflight_nodes() -> dict[str, bool]:
    """CPU-only registration check; no H3 model load or GPU generation."""
    user = Path("/tmp/h3-compare-preflight-user")
    user.mkdir(exist_ok=True)
    server = subprocess.Popen([
        "python", "main.py", "--cpu", "--listen", "127.0.0.1",
        "--port", str(PORT), "--user-directory", str(user),
        "--database-url", "sqlite:////tmp/h3-compare-preflight.db",
    ], cwd="/root/ComfyUI", stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError("CPU ComfyUI exited during preflight")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/object_info", timeout=10) as response:
                    info = json.load(response)
                return {name: name in info for name in (
                    "BlockSparseAttention", "ModelAttentionBackend",
                    "MiniMaxH3MemoryEfficientSageAttentionPatch")}
            except (OSError, TimeoutError):
                time.sleep(2)
        raise TimeoutError("CPU ComfyUI preflight timed out")
    finally:
        server.terminate()
        server.wait(timeout=10)


@app.local_entrypoint()
def check() -> None:
    print(preflight_nodes.remote())


def graph_for(variant: str) -> dict:
    source = runpy.run_path(str(REPO / "modal" / "app.py"))
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    graph = source["_convert"](
        workflow, PROMPT, "rotor.png", f"attention-compare/{variant}",
        5, 768, 1344, 21702,
    )
    sparse = next(n for n in workflow["nodes"] if n["id"] == 272)
    assert sparse["type"] == "BlockSparseAttention"
    assert sparse["widgets_values_named"]["selection"] == "sol-attn"
    graph["272"] = {"class_type": "BlockSparseAttention", "inputs": {
        "model": ["332", 0], **sparse["widgets_values_named"]}}
    graph["332"] = {
        "class_type": ("MiniMaxH3MemoryEfficientSageAttentionPatch"
                       if variant == "sage" else "ModelAttentionBackend"),
        "inputs": {"model": ["336", 0], **(
            {} if variant == "sage" else {"attention": "comfy kitchen attention"})},
    }
    # The workflow has a dense guide and a separate Sol-Attn guide. Preserve both.
    graph["12"]["inputs"]["model"] = ["332", 0]
    graph["146"]["inputs"]["model"] = ["272", 0]
    for node in graph.values():
        for value in node["inputs"].values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                if value[0] not in graph:
                    raise ValueError(f"Missing dependency {value[0]}")
    return graph


@app.cls(image=image, gpu="L40S", volumes={"/models": models},
         timeout=1200, startup_timeout=600, scaledown_window=30, max_containers=1)
class H3Compare:
    @modal.enter()
    def start(self):
        import os

        base = Path("/models")
        comfy = Path("/root/ComfyUI/models")
        mappings = {
            "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors": "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
            "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors": "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
            "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors": "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
            "vae/minimax_h3_video_vae_int8_convrot.safetensors": "vae/minimax_h3_video_vae_int8_convrot.safetensors",
            "vae/minimax_h3_audio_vae_fp32.safetensors": "vae/minimax_h3_audio_vae_fp32.safetensors",
            "latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_fp32.pth": "latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_fp32.pth",
            "loras/lightx2v_hybrid-4to8step-full-fusion_Turbo_pruned.safetensors": "loras/H3/lightx2v_hybrid-4to8step-full-fusion_Turbo_pruned.safetensors",
        }
        for source, target in mappings.items():
            src, dst = base / source, comfy / target
            if not src.is_file():
                raise FileNotFoundError(src)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            os.symlink(src, dst)
        self.input_dir = Path("/tmp/h3-compare-input")
        self.output_dir = Path("/tmp/h3-compare-output")
        self.user_dir = Path("/tmp/h3-compare-user")
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        self.user_dir.mkdir(exist_ok=True)
        self.server = subprocess.Popen([
            "python", "main.py", "--listen", "127.0.0.1", "--port", str(PORT),
            "--input-directory", str(self.input_dir),
            "--output-directory", str(self.output_dir),
            "--user-directory", str(self.user_dir),
            "--database-url", "sqlite:////tmp/h3-compare.db",
        ], cwd="/root/ComfyUI")
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                raise RuntimeError("ComfyUI stopped during startup")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/system_stats", timeout=4):
                    return
            except (OSError, TimeoutError):
                time.sleep(2)
        raise TimeoutError("ComfyUI startup timed out")

    @modal.exit()
    def stop(self):
        self.server.terminate()

    @modal.method()
    def render(self, variant: str, graph: dict, image_bytes: bytes,
               attestation: str) -> dict:
        sys.path.insert(0, "/root/h3_service")
        from h3_service.license_gate import require_attestation

        require_attestation(attestation, purpose="H3 attention comparison")
        if variant not in {"sage", "kitchen"}:
            raise ValueError("Unknown attention variant")
        if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Input must be a PNG")
        (self.input_dir / "rotor.png").write_bytes(image_bytes)
        for kind in ("BlockSparseAttention", graph["332"]["class_type"]):
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/object_info/{kind}", timeout=20) as response:
                if kind not in json.load(response):
                    raise RuntimeError(f"Missing node: {kind}")
        prompt_id = str(uuid.uuid4())
        request = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/prompt",
            data=json.dumps({"prompt": graph, "prompt_id": prompt_id}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                prompt_id = json.load(response)["prompt_id"]
        except urllib.error.HTTPError as error:
            raise RuntimeError(error.read().decode("utf-8", "replace")) from error
        started = time.monotonic()
        deadline = started + 1080
        while time.monotonic() < deadline:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/history/{prompt_id}", timeout=30) as response:
                entry = json.load(response).get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI failed: {status.get('messages')}")
                if status.get("completed"):
                    outputs = []
                    for node in entry.get("outputs", {}).values():
                        outputs.extend(node.get("gifs", []) or [])
                        outputs.extend(node.get("videos", []) or [])
                    if not outputs:
                        raise RuntimeError("Prompt completed without video")
                    record = outputs[0]
                    file = self.output_dir / record.get("subfolder", "") / record["filename"]
                    return {"bytes": file.read_bytes(), "seconds": time.monotonic() - started,
                            "prompt_id": prompt_id, "filename": file.name}
            time.sleep(5)
        raise TimeoutError("Sampling exceeded 18 minutes")


@app.local_entrypoint()
def compare() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    image_bytes = INPUT.read_bytes()
    attestation = "minimax-h3-use-authorized-by-minimax"
    worker = H3Compare()
    for variant in ("sage", "kitchen"):
        path = RESULTS / f"rotors-{variant}.mp4"
        if path.exists():
            raise FileExistsError(path)
        graph = graph_for(variant)
        print(f"Starting {variant} (one call, no retries)", flush=True)
        started = time.monotonic()
        try:
            result = worker.render.remote(variant, graph, image_bytes, attestation)
            path.write_bytes(result.pop("bytes"))
            record = {"variant": variant, "status": "success", "path": str(path),
                      "elapsed_wall_seconds": time.monotonic() - started, **result}
        except Exception as error:
            record = {"variant": variant, "status": "failed", "error": str(error),
                      "elapsed_wall_seconds": time.monotonic() - started}
        with (RESULTS / "manifest.jsonl").open("a", encoding="utf-8") as manifest:
            manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps(record, ensure_ascii=False), flush=True)
        if record["status"] == "failed" and "Missing node: BlockSparseAttention" in record["error"]:
            # A shared precondition failed; the second variant cannot work.
            break
