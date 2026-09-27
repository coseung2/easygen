"""Seal the new candidate only; do not use for a released version."""
import hashlib
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
folder = root / 'pipelines/h3-refvideo/1.0'
manifest = {
    'id': 'h3-refvideo', 'version': '1.0', 'status': 'candidate',
    'kind': 'video', 'engine': 'modal-comfyui',
    'summary': 'Blender motion reference video and optional appearance image to H3 video',
    'inputs': {'reference_video': 'required; relative file under /data/input', 'image': 'optional',
               'prompt': 'required; explicitly use <Video 1>', 'seconds': '1-15', 'seed': 'optional'},
    'outputs': {'video': 'mp4; 24fps; duration rounded up to 17k+5 frames'},
    'runtime': {'modal_app': 'h3-refvideo-v1', 'gpu': 'L40S',
                'container_image': 'base im-AYSPVNRooQYXy8IgQlPWOJ plus legacy cached node layers',
                'model_volume': 'minimax-h3-models', 'model_files': [], 'model_hashes_verified': False},
    'files': {name: 'sha256:' + hashlib.sha256((folder / name).read_bytes()).hexdigest()
              for name in ('worker.py', 'workflow.ui.json')},
    'released_at': None,
    'notes': 'Candidate only. Local graph tests do not establish live model motion adherence. No reference audio. Model hashes and real output gate remain pending.'
}
(folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
registry_path = root / 'pipelines/registry.json'
registry = json.loads(registry_path.read_text(encoding='utf-8'))
registry['pipelines']['h3-refvideo'] = {'1.0': {
    'status': 'candidate', 'label': '3D motion reference', 'engine': 'modal-comfyui',
    'kind': 'video', 'path': 'h3-refvideo/1.0'}}
registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
