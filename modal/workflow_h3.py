"""Easygen MiniMax H3 runtime on Modal.

Runs graphs from ``worker/h3_graph.py`` in the caller's independently built
image and prefix-scoped model/data volumes. No personal-app resources are used.
"""

from __future__ import annotations

import json
import os
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

APP_NAME = resource("h3")
app = modal.App(APP_NAME)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from easygen_runtime.images import comfy_image
image = comfy_image()
data = modal.Volume.from_name(resource("h3-data"), create_if_missing=True)
models = modal.Volume.from_name(resource("h3-models"), create_if_missing=True)
PORT = 8188
MODEL_LINKS = {
    "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors": "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors": "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
    "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors": "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
    "vae/minimax_h3_video_vae_int8_convrot.safetensors": "vae/minimax_h3_video_vae_int8_convrot.safetensors",
    "vae/minimax_h3_audio_vae_fp32.safetensors": "vae/minimax_h3_audio_vae_fp32.safetensors",
    "latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_fp32.pth": "latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_fp32.pth",
    "loras/lightx2v_hybrid-4to8step-full-fusion_Turbo_pruned.safetensors": "loras/H3/lightx2v_hybrid-4to8step-full-fusion_Turbo_pruned.safetensors",
}


def _link_models() -> None:
    for source, target in MODEL_LINKS.items():
        destination = Path("/root/ComfyUI/models") / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            destination.unlink()
        model_path = Path("/models") / source
        if not model_path.is_file():
            raise FileNotFoundError(f"Run modal/bootstrap.py first: {source}")
        os.symlink(model_path, destination)


def _post(api: dict) -> str:
    prompt_id = str(uuid.uuid4())
    body = json.dumps({"prompt": api, "prompt_id": prompt_id, "client_id": APP_NAME}).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}/prompt", data=body,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response).get("prompt_id", prompt_id)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
            lines = [
                f"{node_id} {detail.get('class_type', '')}: {error.get('message')} ({error.get('details')})"
                for node_id, detail in (body.get("node_errors") or {}).items()
                for error in detail.get("errors", [])
            ]
            summary = body.get("error", {}).get("message", "invalid graph")
            raise RuntimeError(f"{summary}: " + "; ".join(lines[:12])) from exc
        except ValueError:
            raise RuntimeError(raw[:1500]) from exc


def _wait(prompt_id: str, timeout: float = 3300) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/history/{prompt_id}", timeout=60) as response:
                entry = json.load(response).get(prompt_id)
        except (urllib.error.URLError, TimeoutError):
            # A long sampling step can stall the history endpoint; keep waiting.
            time.sleep(5)
            continue
        if entry:
            status = entry.get("status", {})
            if status.get("completed"):
                return entry
            if status.get("status_str") == "error":
                messages = status.get("messages", [])
                raise RuntimeError(f"ComfyUI failed: {messages[-1][1] if messages else status}")
        time.sleep(5)
    raise TimeoutError(f"generation did not finish: {prompt_id}")


@app.cls(image=image, gpu="L40S", volumes={"/data": data, "/models": models},
         timeout=3600, startup_timeout=1800, scaledown_window=60, max_containers=1)
class EasygenH3:
    @modal.enter()
    def start(self) -> None:
        for directory in ('input', 'output', 'user'):
            (Path('/data') / directory).mkdir(parents=True, exist_ok=True)
        _link_models()
        self.log = open("/tmp/comfyui.log", "wb")
        self.server = subprocess.Popen([
            "python", "main.py", "--listen", "127.0.0.1", "--port", str(PORT),
            "--input-directory", "/data/input", "--output-directory", "/data/output",
            "--user-directory", "/data/user", "--database-url", "sqlite:////tmp/h3.db",
        ], cwd="/root/ComfyUI", stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.time() + 900
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/system_stats", timeout=5):
                    return
            except Exception:
                time.sleep(2)
        raise RuntimeError("ComfyUI did not become ready")

    @modal.exit()
    def stop(self) -> None:
        self.server.terminate()

    @modal.method()
    def run_graph(self, graph: dict, attestation: str | None = None) -> dict:
        # Users already hold H3 authorization; no private license package is required.
        # Inputs are uploaded right before the call; a warm container must see them.
        data.reload()
        # Reject a malformed graph before queueing GPU sampling.
        checked = self.validate_graph.local(graph)
        if not checked["ok"]:
            raise RuntimeError("graph validation failed: " + "; ".join(checked["problems"][:10]))
        started = time.time()
        try:
            entry = _wait(_post(graph))
        except Exception as exc:
            tail = Path("/tmp/comfyui.log").read_bytes()[-3000:].decode("utf-8", "replace")
            # Modal truncates oversized exceptions; keep the message compact.
            raise RuntimeError(f"{str(exc)[:1800]}\n--- log ---\n{tail[-1200:]}") from None
        data.commit()
        return {"outputs": entry.get("outputs", {}), "seconds": round(time.time() - started, 1)}

    @modal.method()
    def health(self) -> dict:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/object_info", timeout=60) as response:
            info = json.load(response)
        required = {"ModelAttentionBackend", "BlockSparseAttention", "VHS_LoadVideo", "VHS_VideoCombine",
                    "DenoMiniMaxH3ReferenceToVideo", "MinimaxH3LatentUpscaler3D", "MiniMaxH3ImageToVideo"}
        missing = sorted(required - set(info))
        if missing:
            raise RuntimeError(f"missing ComfyUI nodes: {missing}")
        return {"status": "ready", "nodes": sorted(required)}

    @modal.method()
    def validate_graph(self, graph: dict) -> dict:
        """Check a graph against the live node definitions without sampling.

        Mirrors ComfyUI's required-input and option checks so a malformed graph
        is rejected in seconds instead of after a GPU generation is queued.
        """
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/object_info", timeout=60) as response:
            info = json.load(response)
        problems = []
        for node_id, node in graph.items():
            spec = info.get(node["class_type"])
            if spec is None:
                problems.append(f"{node_id}: unknown node {node['class_type']}")
                continue
            inputs = node.get("inputs", {})
            for name, definition in (spec.get("input", {}).get("required") or {}).items():
                # Autogrow groups ("values") are sent as "values.a", "values.b", ...
                if name not in inputs and not any(key.startswith(f"{name}.") for key in inputs):
                    problems.append(f"{node_id} {node['class_type']}: missing {name}")
                    continue
                if name not in inputs:
                    continue
                options = definition[0] if isinstance(definition, list) and definition else None
                value = inputs[name]
                # File pickers list the input folder at startup; new uploads are not in it yet.
                file_choice = name in {"image", "video"}
                if isinstance(options, list) and not file_choice and not isinstance(value, list) and value not in options:
                    problems.append(f"{node_id} {node['class_type']}: {name}={value!r} not in options")
            for name, value in inputs.items():
                if isinstance(value, list) and len(value) == 2 and str(value[0]) not in graph:
                    problems.append(f"{node_id}: {name} links to missing node {value[0]}")
        return {"ok": not problems, "problems": problems[:50]}
