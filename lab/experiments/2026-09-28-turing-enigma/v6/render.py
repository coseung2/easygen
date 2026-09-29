"""Render V6 master with aerender, then encode H.264 + AAC with the V6 soundtrack."""
from pathlib import Path
import subprocess, time, json

R = Path(__file__).resolve().parent
AE = 'C:/Program Files/Adobe/Adobe After Effects 2021/Support Files/aerender.exe'
(R / 'render').mkdir(exist_ok=True)
native = R / 'render/native.avi'
log = R / 'render/aerender.log'
t0 = time.time()
with log.open('w', encoding='utf-8', errors='replace') as f:
    p = subprocess.Popen([AE, '-project', str(R / 'enigma-v6.aep'), '-comp', 'ENIGMA / V6 MASTER',
                          '-output', str(native), '-v', 'ERRORS_AND_PROGRESS'], stdout=f, stderr=subprocess.STDOUT)
    while p.poll() is None:
        time.sleep(15)
        print(json.dumps({'event': 'ae_render_running', 'sec': int(time.time() - t0)}), flush=True)
if p.returncode:
    raise RuntimeError(f'aerender exited {p.returncode}; see {log}')
out = R / 'enigma-v6.mp4'
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(native), '-i', str(R / 'soundtrack.wav'),
                '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p',
                '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', str(out)], check=True)
native.unlink()
print(json.dumps({'event': 'done', 'out': str(out), 'sec': int(time.time() - t0)}))
