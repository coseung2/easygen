"""One-time construction of the isolated h3-refvideo candidate from legacy source."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'pipelines/h3-refvideo/1.0'
DEST.mkdir(parents=True, exist_ok=True)
source = (ROOT / 'modal/app.py').read_text(encoding='utf-8')
source = source.replace('app = modal.App("minimax-h3-latest-workflows")', 'app = modal.App("h3-refvideo-v1")')
source = source.replace('data = modal.Volume', 'image = image.add_local_dir(Path(__file__).parent, "/opt/h3-refvideo")\n\ndata = modal.Volume', 1)
source = source.replace('class LatestH3:', 'class RefVideoH3:')
start = source.index('    @modal.method()\n    def generate(')
end = source.index('        prompt_id = _post_prompt(api)', start)
source = source[:start] + '''    @modal.method()
    def generate(self, prompt: str, reference_video: str, input_filename: str = "", seconds: float = 4, width: int = 1280, height: int = 736, seed: int = 42, attestation: str | None = None) -> dict:
        import sys
        sys.path.insert(0, "/root/h3_service")
        from h3_service.license_gate import require_attestation
        require_attestation(attestation, purpose="H3 reference-video generation")
        data.reload()
        api, metadata = build_reference_video(prompt, reference_video, input_filename, seconds, width, height, seed)
        for filename in (reference_video, input_filename):
            if filename and not (ROOT / "input" / safe_input(filename)).is_file():
                raise FileNotFoundError(filename)
        # Persist the exact submitted graph and provenance before inference.
        run_dir = ROOT / "output" / "h3-refvideo" / uuid.uuid4().hex
        run_dir.mkdir(parents=True)
        (run_dir / "prompt.json").write_text(json.dumps(api), encoding="utf-8")
        (run_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        data.commit()
''' + source[end:]
source = source.replace('"kind": kind}', '"kind": "refvideo", **metadata}')
helper = '''
def safe_input(value: str) -> str:
    from pathlib import PurePosixPath
    value = value.replace("\\\\", "/")
    if value.startswith("input/"):
        value = value[6:]
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or ":" in value or "\\n" in value:
        raise ValueError("Expected one relative file under /data/input")
    return path.as_posix()


def build_reference_video(prompt, reference_video, input_filename="", seconds=4, width=1280, height=736, seed=42):
    import hashlib
    import math
    directory = Path(__file__).parent
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    for name, expected in manifest["files"].items():
        actual = "sha256:" + hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError("Pipeline integrity mismatch: " + name)
    video = safe_input(reference_video)
    if Path(video).suffix.lower() not in {".mp4", ".mov", ".webm", ".mkv"}:
        raise ValueError("Reference must be a video file")
    if not math.isfinite(seconds) or not 1 <= seconds <= 15:
        raise ValueError("seconds must be between 1 and 15")
    if any(not isinstance(v, int) or v < 256 or v > 1920 or v % 32 for v in (width, height)):
        raise ValueError("Dimensions must be multiples of 32 between 256 and 1920")
    if not prompt.strip():
        raise ValueError("A prompt assigning <Video 1> its motion/camera role is required")
    if "<Video 1>" not in prompt:
        raise ValueError("Prompt must explicitly reference <Video 1>")
    image_name = safe_input(input_filename) if input_filename else ""
    workflow = json.loads((directory / "workflow.ui.json").read_text(encoding="utf-8"))
    api = _convert(workflow, prompt, image_name, "h3-refvideo/1.0/clip", seconds, width, height, seed)
    refs = [n for n in api.values() if n["class_type"] == "DenoMiniMaxH3ReferenceToVideo"]
    if len(refs) != 2:
        raise ValueError("Expected both reference conditioning stages")
    loader_id = "refvideo_loader_v1"
    api[loader_id] = {"class_type": "VHS_LoadVideoPath", "inputs": {
        "video": "/data/input/" + video, "force_rate": 24,
        "custom_width": width, "custom_height": height,
        "frame_load_cap": round(seconds * 24), "skip_first_frames": 0,
        "select_every_nth": 1}}
    for node in refs:
        node["inputs"]["ref_videos.ref_video_0"] = [loader_id, 0]
        if not image_name:
            node["inputs"].pop("ref_images", None)
    if not image_name:
        api = {key: node for key, node in api.items() if node["class_type"] != "DenoMiniMaxH3ReferenceImageLoader"}
    metadata = {"pipeline_id": "h3-refvideo", "pipeline_version": "1.0",
        "status": "candidate", "manifest_hash": hashlib.sha256(manifest_bytes).hexdigest(),
        "reference_video": video, "reference_image": image_name,
        "requested_seconds": seconds, "generated_frames": refs[0]["inputs"]["length"],
        "fps": 24, "reference_audio": False}
    return api, metadata


'''
source = source.replace('\ndef _post_prompt', '\n' + helper + 'def _post_prompt')
(DEST / 'worker.py').write_text(source, encoding='utf-8')
workflow = json.loads(Path('F:/modal-gui/lab/2026-09-28-iron-ball-test/h3-r2v-current.json').read_text(encoding='utf-8'))
for node in workflow['nodes']:
    for field in ('widgets_values', 'widgets_values_named'):
        if isinstance(node.get(field), dict):
            node[field].pop('videopreview', None)
(DEST / 'workflow.ui.json').write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding='utf-8')
print(DEST)
