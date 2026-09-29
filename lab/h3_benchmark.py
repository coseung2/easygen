"""Isolated baseline/Kitchen benchmark with persisted Modal call identity."""
from __future__ import annotations
import json
import os
import runpy
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(r"F:\modal-gui\lab\2026-09-29-h3-controlled-ab")


def remote_benchmark(graph, reference, case):
    import threading
    import importlib.metadata
    original = runpy.run_path('/root/bench_original.py')
    original['_prepare_models']()
    work = Path('/tmp/controlled-bench')
    for folder in ('input', 'output', 'user'):
        (work / folder).mkdir(parents=True, exist_ok=True)
    (work / 'input/rotor.png').write_bytes(reference)
    log = (work / 'comfy.log').open('w')
    begin = time.monotonic()
    server = subprocess.Popen([
        'python', 'main.py', '--listen', '127.0.0.1', '--port', '8188',
        '--input-directory', str(work/'input'), '--output-directory', str(work/'output'),
        '--user-directory', str(work/'user'), '--database-url', 'sqlite:////tmp/controlled-bench.db',
        '--cache-none',
    ], cwd='/root/ComfyUI', stdout=log, stderr=subprocess.STDOUT)
    samples = []
    stop = threading.Event()
    def monitor():
        while not stop.is_set():
            try:
                value = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu', '--format=csv,noheader,nounits'],text=True)
                memory, utilization = map(int, value.strip().split(','))
                samples.append((time.monotonic()-begin, memory, utilization))
            except Exception:
                pass
            stop.wait(1)
    threading.Thread(target=monitor,daemon=True).start()
    def get(endpoint):
        with urllib.request.urlopen('http://127.0.0.1:8188/'+endpoint,timeout=15) as response:
            return json.load(response)
    results = []
    try:
        deadline = time.monotonic()+240
        while True:
            if server.poll() is not None:
                raise RuntimeError('ComfyUI startup failed')
            try:
                info=get('object_info')
                break
            except OSError:
                if time.monotonic()>deadline:
                    raise TimeoutError('ComfyUI startup')
                time.sleep(1)
        startup=time.monotonic()-begin
        missing=sorted({n['class_type'] for n in graph.values()}-set(info))
        if missing:
            raise RuntimeError('Missing nodes: '+str(missing))
        if case=='kitchen':
            definition=info['ModelAttentionBackend']['input']['required']['attention']
            options=definition[0] if isinstance(definition[0],list) else definition[1].get('options',[])
            if 'comfy kitchen attention' not in options:
                raise RuntimeError('Kitchen GPU attention unavailable: '+repr(definition))
        for index in range(2):
            prompt_id=str(uuid.uuid4())
            mark=len(samples)
            start=time.monotonic()
            req=urllib.request.Request('http://127.0.0.1:8188/prompt',
                data=json.dumps({'prompt':graph,'prompt_id':prompt_id}).encode(),
                headers={'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=20) as response:
                    submitted=json.load(response)
            except urllib.error.HTTPError as exc:
                raise RuntimeError(exc.read().decode()) from exc
            if submitted.get('node_errors'):
                raise RuntimeError(str(submitted['node_errors']))
            deadline=time.monotonic()+900
            while True:
                entry=get('history/'+prompt_id).get(prompt_id)
                if entry:
                    status=entry.get('status',{})
                    if status.get('status_str')=='error':
                        errors=[m[1] for m in status.get('messages',[]) if m[0]=='execution_error']
                        raise RuntimeError(str([(e.get('node_type'),e.get('exception_message')) for e in errors]))
                    if status.get('completed'):
                        break
                if time.monotonic()>deadline:
                    raise TimeoutError('Generation exceeded 15 minutes')
                time.sleep(.5)
            elapsed=time.monotonic()-start
            files=[f for n in entry['outputs'].values() for k in ('gifs','videos') for f in n.get(k,[]) if f.get('filename','').endswith('.mp4')]
            if not files:
                raise RuntimeError('No MP4 returned')
            f=files[0]
            data=(work/'output'/f.get('subfolder','')/f['filename']).read_bytes()
            messages={m[0]:m[1].get('timestamp') for m in status.get('messages',[]) if isinstance(m[1],dict)}
            record={'index':index,'state':'cold' if index==0 else 'warm','wall_seconds':elapsed,
                'prompt_seconds':(messages['execution_success']-messages['execution_start'])/1000,
                'peak_vram_mib':max((s[1] for s in samples[mark:]),default=None),'bytes':data,'prompt_id':prompt_id}
            results.append(record)
            print(json.dumps({k:v for k,v in record.items() if k!='bytes'}),flush=True)
        return {'status':'success','case':case,'startup_seconds':startup,'results':results,
                'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],text=True).strip(),
                'comfy_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd='/root/ComfyUI',text=True).strip(),
                'packages':{n:importlib.metadata.version(n) for n in ('torch','comfy-kitchen')},
                'log':(work/'comfy.log').read_text(errors='replace')}
    except Exception as exc:
        return {'status':'failed','case':case,'error':str(exc),'results':results,
                'log':(work/'comfy.log').read_text(errors='replace')}
    finally:
        stop.set()
        server.terminate()
        server.wait(timeout=15)
        log.close()


def main():
    case,gpu=sys.argv[1:3]
    attempt=sys.argv[3] if len(sys.argv)>3 else ''
    assert case in ('baseline','kitchen')
    destination=OUT/(case+'-'+gpu+attempt)
    destination.mkdir(parents=True,exist_ok=True)
    lock=destination/'submitted.json'
    if lock.exists():
        raise RuntimeError('Already submitted; recover using saved call ID, never resubmit')
    source=runpy.run_path(str(ROOT/'modal/app.py'))
    helper=runpy.run_path(str(ROOT/'lab/h3_attention_compare.py'))
    workflow=json.loads(helper['WORKFLOW'].read_text(encoding='utf-8'))
    graph=source['_convert'](workflow,helper['PROMPT'],'rotor.png','controlled/'+case,5,768,1344,21702)
    if case=='kitchen':
        graph=helper['graph_for']('kitchen')
        graph['272']['inputs']['verbose']=True
    (destination/'graph.json').write_text(json.dumps(graph,indent=2),encoding='utf-8')
    image=source['image'] if case=='baseline' else modal.Image.from_id('im-mE4U8UoV5yb2JzCqZ6k0r6')
    image=image.add_local_file(str(ROOT/'modal/app.py'),'/root/bench_original.py')
    app=modal.App('h3-controlled-'+case+'-'+gpu.lower())
    worker=app.function(image=image,gpu=gpu,volumes={'/models':modal.Volume.from_name('minimax-h3-models')},
        timeout=1200,retries=0,max_containers=1,scaledown_window=2)(remote_benchmark)
    with lock.open('x',encoding='utf-8') as f:
        json.dump({'status':'preparing','case':case,'gpu':gpu},f)
    with app.run():
        call=worker.spawn(graph,helper['INPUT'].read_bytes(),case)
        lock.write_text(json.dumps({'app_id':app.app_id,'call_id':call.object_id}),encoding='utf-8')
        print('BENCH_CALL '+lock.read_text(),flush=True)
        start=time.monotonic()
        result=call.get()
        result['client_seconds']=time.monotonic()-start
        for entry in result.get('results',[]):
            (destination/(entry['state']+'.mp4')).write_bytes(entry.pop('bytes'))
        (destination/'comfy.log').write_text(result.pop('log'),encoding='utf-8')
        (destination/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
    if result['status']!='success':
        raise SystemExit(1)


if __name__=='__main__':
    main()
