"""Build from public sources; no workspace-owned image IDs."""
import json
from pathlib import Path
import modal

ROOT = Path(__file__).resolve().parent


def comfy_image():
    image = (modal.Image.from_registry('nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04', add_python='3.12')
             .apt_install('git', 'ffmpeg', 'libgl1', 'libglib2.0-0', 'build-essential')
             .pip_install('torch==2.10.0', 'torchvision==0.25.0', 'torchaudio==2.10.0',
                          index_url='https://download.pytorch.org/whl/cu128'))
    for source in json.loads((ROOT / 'sources.json').read_text(encoding='utf-8')):
        target, commit = source['target'], source['commit']
        image = image.run_commands(
            f"git init {target} && git -C {target} remote add origin https://github.com/{source['repo']}.git && "
            f"git -C {target} fetch --depth 1 origin {commit} && git -C {target} checkout --detach {commit}",
            f"if [ -f {target}/requirements.txt ]; then python -m pip install -r {target}/requirements.txt; fi")
    return image.run_commands('python -m pip check').add_local_dir(ROOT, '/root/easygen_runtime')
