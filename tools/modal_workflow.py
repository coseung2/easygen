"""App-free Modal client. prepare is offline; submit is the only GPU submission."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from worker.h3_graph import build_graph, collect_outputs

APPS = {"video": "easygen-h3-v1", "image": "easygen-image-v1", "music": "yue2-music"}
H3_ATTESTATION = "minimax-h3-use-authorized-by-minimax"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_folder(value):
    folder = Path(value).expanduser().resolve()
    if folder.is_relative_to(ROOT):
        raise ValueError("Choose a run folder outside the repository")
    return folder


def prepare(kind, request_path, folder):
    request_path = Path(request_path).resolve()
    request = read(request_path)
    job = "easygen_" + uuid.uuid4().hex
    files = []
    graph = None
    if kind == "video":
        allowed = {"mode", "prompt", "seconds", "width", "height", "seed", "image_path", "video_path"}
        if set(request) - allowed:
            raise ValueError("Unsupported video fields: " + ", ".join(sorted(set(request) - allowed)))
        mode = request.get("mode", "text")
        image_name = video_name = ""
        for key, label, suffixes in (
            ("image_path", "image", {".png", ".jpg", ".jpeg", ".webp", ".bmp"}),
            ("video_path", "reference", {".mp4", ".mov", ".webm", ".mkv", ".m4v"}),
        ):
            if not request.get(key):
                continue
            if mode == "text" or (key == "video_path" and mode != "reference"):
                raise ValueError(f"{key} is not used by mode={mode}; remove it or change mode")
            source = Path(request[key]).expanduser()
            if not source.is_absolute():
                source = request_path.parent / source
            source = source.resolve()
            if not source.is_file() or source.suffix.lower() not in suffixes:
                raise ValueError(f"Missing or unsupported input: {key}")
            remote = f"easygen/{job}/{label}{source.suffix.lower()}"
            files.append({"local": str(source), "remote": remote,
                          "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
            if key == "image_path":
                image_name = remote
            else:
                video_name = remote
        graph = build_graph(mode=mode, prompt=request.get("prompt", ""),
                            seconds=float(request.get("seconds", 5)),
                            width=int(request.get("width", 1344)), height=int(request.get("height", 768)),
                            seed=int(request.get("seed", 42)), output_prefix=f"easygen/{job}",
                            image_name=image_name, video_name=video_name)
    elif kind == "image":
        allowed = {"model", "prompt", "width", "height", "seed", "count", "text"}
        if set(request) - allowed:
            raise ValueError("Unsupported image fields: " + ", ".join(sorted(set(request) - allowed)))
        request = {"model": "krea", "width": 1024, "height": 1024, "seed": 1,
                   "count": 1, "text": "", **request}
        if request["model"] not in {"krea", "ideogram"} or not request.get("prompt", "").strip():
            raise ValueError("Choose krea/ideogram and provide a prompt")
        for key in ("width", "height", "seed", "count"):
            request[key] = int(request[key])
        if min(request["width"], request["height"]) < 256 or not 1 <= request["count"] <= 4:
            raise ValueError("Image dimensions must be >=256; count must be 1..4")
    else:
        if set(request) - {"style", "lyrics", "seed"}:
            raise ValueError("Music supports only style, lyrics, seed; there is no duration parameter")
        if not request.get("style", "").strip():
            raise ValueError("Music style is required")
        request = {"lyrics": "", "seed": 4301, **request}
        request["seed"] = int(request["seed"])
    folder.mkdir(parents=True, exist_ok=False)
    write(folder / "request.json", request)
    if graph is not None:
        write(folder / "graph.json", graph)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    write(folder / "state.json", {"kind": kind, "app": APPS[kind], "job_id": job,
                                 "status": "prepared", "files": files,
                                 "git_commit": revision.stdout.strip() or None})


def submit(folder, modal):
    # Exclusive persistent lock also protects against two agents submitting the same folder.
    # Retain it on all failures: network failure can mean the server accepted the call.
    state = read(folder / "state.json")
    if state["status"] != "prepared":
        raise ValueError("Already submitted or uncertain; use status, never automatically resubmit")
    request = read(folder / "request.json")
    graph = read(folder / "graph.json") if state["kind"] == "video" else None
    with (folder / "submit.lock").open("x", encoding="utf-8") as handle:
        handle.write("Do not remove automatically: submission may have been accepted.\n")
    state["status"] = "submitting"
    write(folder / "state.json", state)
    if state["files"]:
        for item in state["files"]:
            if hashlib.sha256(Path(item["local"]).read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("An input changed after prepare; prepare a new run before submission")
        volume = modal.Volume.from_name("minimax-h3-comfyui-data")
        with volume.batch_upload() as batch:
            for item in state["files"]:
                batch.put_file(item["local"], "input/" + item["remote"])
    if state["kind"] == "video":
        call = modal.Cls.from_name(state["app"], "EasygenH3")().run_graph.spawn(
            graph=graph, attestation=H3_ATTESTATION)
    elif state["kind"] == "image":
        call = modal.Cls.from_name(state["app"], "EasygenImage")().generate.spawn(**request)
    else:
        call = modal.Function.from_name(state["app"], "generate_music").spawn(
            job_id=state["job_id"], **request)
    state.update(status="submitted", call_id=call.object_id)
    write(folder / "state.json", state)


def status(folder, modal):
    state = read(folder / "state.json")
    if state["status"] in {"completed", "downloaded", "failed", "cancel_requested"}:
        return
    if not state.get("call_id"):
        raise ValueError("No call ID recorded. Inspect Modal call history; do not resubmit")
    call = modal.FunctionCall.from_id(state["call_id"])
    try:
        result = call.get(timeout=0)
    except modal.exception.FunctionTimeoutError:
        state["status"] = "failed"
        write(folder / "state.json", state)
        raise
    except (TimeoutError, modal.exception.TimeoutError):
        return  # Still running. The agent chooses the next polling interval.
    except Exception:
        # An RPC/network error is not evidence that the remote function failed.
        raise
    write(folder / "remote-result.json", result)
    state["status"] = "completed"
    write(folder / "state.json", state)


def download(folder, modal):
    state = read(folder / "state.json")
    if state["status"] not in {"completed", "downloaded"}:
        raise ValueError("Run status first and wait for completed")
    result = read(folder / "remote-result.json")
    outputs = {}
    if state["kind"] == "image":
        for index, encoded in enumerate(result.get("images", []), 1):
            target = folder / f"image-{index}.png"
            target.write_bytes(base64.b64decode(encoded, validate=True))
            outputs[target.name] = target
    else:
        is_video = state["kind"] == "video"
        paths = collect_outputs(result["outputs"]) if is_video else {"audio": result["audio"]}
        volume = modal.Volume.from_name("minimax-h3-comfyui-data" if is_video else "yue2-outputs")
        for label, relative in paths.items():
            remote = PurePosixPath(relative)
            if remote.is_absolute() or ".." in remote.parts or "\\" in relative:
                raise ValueError("Unexpected remote output path")
            target = folder / (f"{label}.mp4" if is_video else "audio.flac")
            temporary = target.with_suffix(target.suffix + ".part")
            with temporary.open("wb") as handle:
                for chunk in volume.read_file(("output/" if is_video else "") + relative):
                    handle.write(chunk)
            temporary.replace(target)
            outputs[target.name] = target
    if not outputs or any(path.stat().st_size == 0 for path in outputs.values()):
        raise ValueError("Missing or empty output")
    write(folder / "outputs.json", {name: {"bytes": path.stat().st_size,
          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for name, path in outputs.items()})
    state["status"] = "downloaded"
    write(folder / "state.json", state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="Offline: validate request, save inputs and H3 graph")
    prep.add_argument("kind", choices=APPS)
    prep.add_argument("--request", required=True)
    prep.add_argument("--out", required=True, help="New directory outside the repository")
    for name in ("submit", "status", "download", "cancel"):
        command = commands.add_parser(name)
        command.add_argument("run", help="Run directory created by prepare")
    args = parser.parse_args()
    folder = run_folder(args.out if args.command == "prepare" else args.run)
    if args.command == "prepare":
        prepare(args.kind, args.request, folder)
    else:
        import modal
        if args.command == "cancel":
            state = read(folder / "state.json")
            modal.FunctionCall.from_id(state["call_id"]).cancel()
            state["status"] = "cancel_requested"
            write(folder / "state.json", state)
        else:
            {"submit": submit, "status": status, "download": download}[args.command](folder, modal)
    state = read(folder / "state.json")
    print(json.dumps({key: state[key] for key in ("job_id", "app", "status", "call_id") if key in state}))


if __name__ == "__main__":
    main()
