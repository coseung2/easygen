"""python -m modal run modal/bootstrap.py --target h3 (CPU downloads only)."""
import os
import sys
from pathlib import Path
import modal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from easygen_runtime.config import resource
app = modal.App(resource('bootstrap'))
models_h3 = modal.Volume.from_name(resource('h3-models'), create_if_missing=True)
models_image = modal.Volume.from_name(resource('image-models'), create_if_missing=True)
models_music = modal.Volume.from_name(resource('music-models'), create_if_missing=True)
image = (modal.Image.debian_slim(python_version='3.12').pip_install('huggingface-hub==0.36.2')
         .add_local_dir(ROOT / 'easygen_runtime', '/root/easygen_runtime'))
secrets = [modal.Secret.from_name(os.environ['EASYGEN_HF_SECRET'])] if os.environ.get('EASYGEN_HF_SECRET') else []


@app.function(image=image, volumes={'/h3': models_h3, '/image': models_image, '/music': models_music},
              secrets=secrets, timeout=86400, max_containers=1)
def prepare_models(target: str, verify_only: bool = False):
    from easygen_runtime.provision import provision
    if target not in {'h3', 'image', 'music'}:
        raise ValueError('target must be h3, image or music')
    volume = {'h3': models_h3, 'image': models_image, 'music': models_music}[target]
    volume.reload()
    try:
        return provision(target, '/' + target, verify_only)
    finally:
        volume.commit()  # Preserve completed files and partial downloads for a later explicit resume.


@app.local_entrypoint()
def main(target: str = 'h3', verify_only: bool = False):
    result = prepare_models.remote(target, verify_only)
    print({'target': target, 'verified_files': len(result), 'bytes': sum(x['bytes'] for x in result)})
