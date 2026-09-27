"""Prepare a pinned reference-video graph locally; generation requires --execute."""
import argparse
import importlib.util
import json
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1] / 'pipelines/h3-refvideo/1.0'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--reference-video', required=True, help='Relative file already uploaded under /data/input')
    p.add_argument('--reference-image', default='')
    p.add_argument('--prompt', required=True)
    p.add_argument('--seconds', type=float, default=4)
    p.add_argument('--width', type=int, default=1280)
    p.add_argument('--height', type=int, default=736)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--execute', action='store_true', help='Run paid Modal GPU inference')
    p.add_argument('--attestation', help='Existing MiniMax license authorization, required for execution')
    args = p.parse_args()
    spec = importlib.util.spec_from_file_location('h3_refvideo_candidate', PIPELINE / 'worker.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    api, metadata = module.build_reference_video(args.prompt, args.reference_video, args.reference_image,
                                                args.seconds, args.width, args.height, args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'prompt.json').write_text(json.dumps(api, indent=2), encoding='utf-8')
    (args.output_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    if not args.execute:
        print(json.dumps({'state': 'prepared_locally', 'gpu_started': False, **metadata}, indent=2))
        return
    if not args.attestation:
        p.error('--attestation is required with --execute')
    import modal
    worker = modal.Cls.from_name('h3-refvideo-v1', 'RefVideoH3')()
    result = worker.generate.remote(prompt=args.prompt, reference_video=args.reference_video,
        input_filename=args.reference_image, seconds=args.seconds, width=args.width,
        height=args.height, seed=args.seed, attestation=args.attestation)
    (args.output_dir / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
