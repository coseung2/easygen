"""Build provider-neutral MiniMax H3 ComfyUI API graphs.

The UI graphs in ``worker/graphs`` are the app's fixed, versioned workflows. This
module converts them into ComfyUI API prompts and applies the few user inputs the
simple creation screen exposes. Modal and RunPod receive the same API graph, so a
provider switch never changes the generation path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GRAPH_ROOT = Path(__file__).with_name("graphs")
FPS = 24
MAX_SECONDS = 15
MODES = {"text", "image", "reference"}
SKIP = {
    "Note",
    "MarkdownNote",
    "FancyTimerNode",
    "DenoTextEncoderUnload",
    "Seed (rgthree)",
    "MiniMaxChunkFeedForward",
}
WIDGET_MAP = {
    "CLIPLoader": ["clip_name", "type", "device"],
    "UNETLoader": ["unet_name", "weight_dtype"],
    "VAELoader": ["vae_name"],
    "KSamplerSelect": ["sampler_name"],
    "BasicScheduler": ["scheduler", "steps", "denoise"],
    "LoraLoaderModelOnly": ["lora_name", "strength_model"],
    "MiniMaxH3SigmaShift": ["shift_video", "shift_audio"],
    "MinimaxH3LatentUpscaler3D": [
        "model_name", "mode", "mode.width", "mode.height", "align",
        "enable_temporal_chunking", "force_unload", "device", "precision",
    ],
}
# Memory-only nodes are skipped; their outputs are rewired to the matching input
# link so the graph stays connected. Keyed by node id, then output slot.
PASSTHROUGH = {
    "i2v": {"48": {0: "83", 1: "176"}, "261": {0: "801"}, "190": {0: "741"}},
    "r2v": {"257": {0: "862", 1: "863"}, "286": {0: "901"}, "181": {0: "738"}},
}
FINAL_SAVE = "33"
PREVIEW_DECODE = "9000"
PREVIEW_SAVE = "9001"
REFERENCE_VIDEO = "9002"


def frame_length(seconds: float) -> int:
    """H3 accepts 17k+5 frames at 24 fps; round up to the nearest valid length."""
    frames = max(5, round(float(seconds) * FPS))
    return frames + (5 - frames % 17) % 17


def half_bucket(value: int) -> int:
    """Half of a requested dimension, aligned to the 32px H3 bucket grid."""
    half = max(32, int(value) // 2)
    return half - half % 32


def _load(name: str) -> dict[str, Any]:
    return json.loads((GRAPH_ROOT / f"h3_{name}.ui.json").read_text(encoding="utf-8"))


def _convert(workflow: dict[str, Any], passthrough: dict[str, dict[int, str]]) -> dict[str, Any]:
    nodes = {
        str(node["id"]): node
        for node in workflow.get("nodes", [])
        if node.get("type") not in SKIP and node.get("mode", 0) != 4
    }
    links = {str(row[0]): row for row in workflow.get("links", [])}
    api: dict[str, Any] = {}
    for node_id, node in nodes.items():
        entry: dict[str, Any] = {"class_type": node["type"], "inputs": {}}
        inputs = node.get("inputs") or []
        for item in inputs:
            link_id = item.get("link")
            if link_id is None or str(link_id) not in links:
                continue
            link = links[str(link_id)]
            origin_id, origin_slot = str(link[1]), int(link[2])
            for _ in range(8):
                replacement = passthrough.get(origin_id, {}).get(origin_slot)
                if replacement is None or replacement not in links:
                    break
                origin_id, origin_slot = str(links[replacement][1]), int(links[replacement][2])
            if origin_id in nodes:
                entry["inputs"][item["name"]] = [origin_id, origin_slot]
        named = node.get("widgets_values_named")
        widgets = node.get("widgets_values")
        if isinstance(named, dict):
            # Exported graphs carry exact widget names; positional lists drift
            # when a node gains hidden or linked widgets.
            for name, value in named.items():
                if name != "videopreview":
                    entry["inputs"].setdefault(name, value)
        elif isinstance(widgets, dict):
            for name, value in widgets.items():
                if name != "videopreview":
                    entry["inputs"].setdefault(name, value)
        elif isinstance(widgets, list):
            names = [i["name"] for i in inputs if i.get("widget") and i.get("link") is None]
            for name, value in zip(WIDGET_MAP.get(node["type"], names), widgets):
                entry["inputs"].setdefault(name, value)
        api[node_id] = entry
    return api


def _find(api: dict[str, Any], class_type: str) -> list[str]:
    return [node_id for node_id, node in api.items() if node["class_type"] == class_type]


def _is_used(api: dict[str, Any], node_id: str) -> bool:
    return any(
        isinstance(value, list) and value and value[0] == node_id
        for node in api.values() for value in node["inputs"].values()
    )


def _prune(api: dict[str, Any], class_types: tuple[str, ...]) -> None:
    """Drop loaders/resizers whose output no longer feeds anything."""
    changed = True
    while changed:
        changed = False
        for node_id in [n for n, node in api.items() if node["class_type"] in class_types]:
            if not _is_used(api, node_id):
                api.pop(node_id)
                changed = True


def build_graph(
    *,
    mode: str,
    prompt: str,
    seconds: float,
    width: int,
    height: int,
    seed: int,
    output_prefix: str,
    image_name: str = "",
    video_name: str = "",
) -> dict[str, Any]:
    """Return a ComfyUI API prompt for the simple creation screen.

    ``image_name`` and ``video_name`` are ComfyUI input-folder relative names.
    The graph saves two MP4s that share frames and audio: ``<prefix>_preview``
    (sampled resolution, before the latent upscaler) and ``<prefix>_final``.
    """
    if mode not in MODES:
        raise ValueError(f"unsupported mode: {mode}")
    if not prompt.strip():
        raise ValueError("prompt is required")
    if mode == "image" and not image_name:
        raise ValueError("image mode needs a reference image")
    if mode == "reference" and not (image_name or video_name):
        raise ValueError("reference mode needs a reference image or video")
    seconds = min(max(float(seconds), 1.0), MAX_SECONDS)
    width, height = int(width) - int(width) % 32, int(height) - int(height) % 32
    if width < 256 or height < 256:
        raise ValueError("output size is too small")
    name = "r2v" if mode == "reference" else "i2v"
    api = _convert(_load(name), PASSTHROUGH[name])

    # Sage attention has no L40S kernel; use the dense Comfy Kitchen backend.
    for node_id in _find(api, "MiniMaxH3MemoryEfficientSageAttentionPatch"):
        api[node_id] = {"class_type": "ModelAttentionBackend",
                        "inputs": {"model": api[node_id]["inputs"]["model"],
                                   "attention": "comfy kitchen attention"}}
    for node_id in _find(api, "PrimitiveStringMultiline"):
        api[node_id]["inputs"]["value"] = prompt
    for node_id in _find(api, "RandomNoise"):
        api[node_id]["inputs"].update(noise_seed=int(seed), control_after_generate="fixed")
    for node_id in _find(api, "LoraLoaderModelOnly"):
        api[node_id]["inputs"]["lora_name"] = "H3/lightx2v_hybrid-4to8step-full-fusion_Turbo_pruned.safetensors"
    length = frame_length(seconds)
    for node_id in _find(api, "MiniMaxH3ImageToVideo") + _find(api, "DenoMiniMaxH3ReferenceToVideo"):
        api[node_id]["inputs"].update(width=half_bucket(width), height=half_bucket(height), length=length)
    for node_id in _find(api, "MinimaxH3LatentUpscaler3D"):
        api[node_id]["inputs"].update({"align": 1, "mode.width": width, "mode.height": height})

    if name == "i2v":
        for node_id in _find(api, "MiniMaxH3ImageToVideo"):
            inputs = api[node_id]["inputs"]
            # The same picture as a last frame would freeze motion at the end.
            inputs.pop("last_frame", None)
            if mode == "text":
                inputs.pop("first_frame", None)
        for node_id in _find(api, "LoadImage"):
            api[node_id]["inputs"]["image"] = image_name
        _prune(api, ("ImageResizeKJv2", "LoadImage"))
    else:
        references = _find(api, "DenoMiniMaxH3ReferenceToVideo")
        if image_name:
            for node_id in _find(api, "DenoMiniMaxH3ReferenceImageLoader"):
                api[node_id]["inputs"]["image_paths"] = image_name
        else:
            for node_id in references:
                api[node_id]["inputs"].pop("ref_images", None)
            _prune(api, ("DenoMiniMaxH3ReferenceImageLoader",))
        if video_name:
            api[REFERENCE_VIDEO] = {
                "class_type": "VHS_LoadVideo",
                "inputs": {
                    "video": video_name,
                    "force_rate": FPS,
                    "custom_width": 0,
                    "custom_height": 0,
                    "frame_load_cap": length,
                    "skip_first_frames": 0,
                    "select_every_nth": 1,
                    "format": "AnimateDiff",
                },
            }
            for node_id in references:
                api[node_id]["inputs"]["ref_videos.ref_video_0"] = [REFERENCE_VIDEO, 0]
                api[node_id]["inputs"]["ref_video_audios.ref_video_audio_0"] = [REFERENCE_VIDEO, 2]

    final = api[FINAL_SAVE]["inputs"]
    final.update(filename_prefix=f"{output_prefix}_final", frame_rate=FPS,
                 format="video/h264-mp4", crf=19, save_output=True)
    upscalers = _find(api, "MinimaxH3LatentUpscaler3D")
    decoders = _find(api, "VAEDecode")
    if not upscalers or not decoders:
        raise RuntimeError("H3 graph is missing its upscaler or decoder")
    # Decode the sampled latent before the upscaler for the comparison view.
    api[PREVIEW_DECODE] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": api[upscalers[0]]["inputs"]["latent"],
                   "vae": api[decoders[0]]["inputs"]["vae"]},
    }
    api[PREVIEW_SAVE] = {
        "class_type": "VHS_VideoCombine",
        "inputs": {**final, "images": [PREVIEW_DECODE, 0],
                   "filename_prefix": f"{output_prefix}_preview"},
    }
    return api


def collect_outputs(history_outputs: dict[str, Any]) -> dict[str, str]:
    """Map ComfyUI history outputs to {'final': path, 'preview': path}."""
    found: dict[str, str] = {}
    for node_id, label in ((FINAL_SAVE, "final"), (PREVIEW_SAVE, "preview")):
        node = history_outputs.get(node_id) or {}
        for key in ("gifs", "videos", "images"):
            for record in node.get(key) or []:
                filename = str(record.get("filename", ""))
                if filename.endswith(".mp4"):
                    found[label] = str(Path(record.get("subfolder", "")) / filename).replace("\\", "/")
                    break
            if label in found:
                break
    if "final" not in found:
        raise RuntimeError("ComfyUI finished without a final video")
    return found
