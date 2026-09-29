"""Run one H3 clip end-to-end: upload input image, generate on Modal, download result."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import modal

DEFAULT_ATTESTATION = "minimax-h3-use-authorized-by-minimax"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(str(path))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", default="fl2v")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--input", default="")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--width", type=int, default=1344)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--job-id", default="")
    parser.add_argument("--out-root", default=str(data_path("h3-clips", "generated")))
    parser.add_argument("--out-name", default="")
    parser.add_argument("--manifest", default="")
    args = parser.parse_args()

    attestation = os.environ.get("MINIMAX_H3_LICENSE_ATTESTATION") or DEFAULT_ATTESTATION
    job_id = args.job_id or f"cli-{os.getpid()}"
    volume = modal.Volume.from_name("minimax-h3-comfyui-data")

    remote_input = ""
    if args.input:
        input_path = Path(args.input).resolve()
        if not input_path.is_file():
            sys.exit(f"input not found: {input_path}")
        # ComfyUI is launched with /data/input as its input directory. Keep
        # the uploaded file under that directory; pass the path with the
        # leading `input/` so the deployed worker can normalise it back to
        # the ComfyUI-relative path for both LoadImage and Ref2V loaders.
        remote_input = f"input/gui/{job_id}/{input_path.name}"
        with volume.batch_upload(force=True) as batch:
            batch.put_file(input_path, remote_input)

    worker = modal.Cls.from_name("minimax-h3-latest-workflows", "LatestH3")()
    result = worker.generate.remote(
        kind=args.kind,
        prompt=args.prompt,
        input_filename=remote_input,
        seconds=args.seconds,
        width=args.width,
        height=args.height,
        seed=args.seed,
        attestation=attestation,
    )

    relative = result["relative_path"]
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    target_name = args.out_name or Path(relative).name
    out_path = unique_path(out_root / target_name)
    with out_path.open("wb") as handle:
        for chunk in volume.read_file(f"output/{relative}"):
            handle.write(chunk)

    record = {
        "status": "success",
        "job_id": job_id,
        "kind": args.kind,
        "input": args.input,
        "remote_path": relative,
        "local_path": str(out_path.resolve()),
        "seconds": args.seconds,
        "width": args.width,
        "height": args.height,
        "seed": args.seed,
        "prompt": args.prompt,
    }
    print(json.dumps(record, ensure_ascii=False), flush=True)

    if args.manifest:
        manifest_path = Path(args.manifest)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
