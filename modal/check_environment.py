"""Build public image and check node registration on CPU; no model download or GPU."""
import sys
from pathlib import Path
import modal
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from easygen_runtime.images import comfy_image
app = modal.App('easygen-environment-check')
image = comfy_image()


@app.function(image=image, timeout=900, memory=8192)
def check():
    import json
    import subprocess
    import time
    import urllib.request
    required = {'MiniMaxH3ImageToVideo', 'DenoMiniMaxH3ReferenceToVideo',
                'DenoMiniMaxH3ReferenceImageLoader', 'MinimaxH3LatentUpscaler3D',
                'VHS_LoadVideo', 'VHS_VideoCombine', 'ImageResizeKJv2', 'BlockSparseAttention',
                'ModelAttentionBackend', 'ComfyMathExpression', 'ResolutionSelector',
                'Ideogram4Scheduler', 'DualModelGuider', 'CFGOverride'}
    log = open('/tmp/comfy-check.log', 'wb')
    process = subprocess.Popen(['python', 'main.py', '--cpu', '--listen', '127.0.0.1', '--port', '8188',
                                '--database-url', 'sqlite:////tmp/check.db'], cwd='/root/ComfyUI', stdout=log, stderr=log)
    try:
        for _ in range(180):
            if process.poll() is not None:
                raise RuntimeError('ComfyUI exited: ' + Path('/tmp/comfy-check.log').read_text()[-4000:])
            try:
                with urllib.request.urlopen('http://127.0.0.1:8188/object_info', timeout=5) as response:
                    info = json.load(response)
                missing = sorted(required - set(info))
                if missing:
                    raise RuntimeError('Missing nodes: ' + str(missing))
                return {'status': 'ready', 'nodes': sorted(required), 'gpu_tested': False}
            except OSError:
                time.sleep(2)
        raise TimeoutError('ComfyUI startup timeout')
    finally:
        process.terminate()
        process.wait(timeout=30)
        log.close()


@app.local_entrypoint()
def main():
    print(check.remote())
