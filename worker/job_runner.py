import os, threading
from pathlib import Path
from typing import Callable, Any

DEFAULT_ATTESTATION = "minimax-h3-use-authorized-by-minimax"


def call_id_of(call: Any) -> str:
    """Modal FunctionCall의 실제 호출 id.

    `remote()`는 결과만 주고 호출 id를 남기지 않아 재조회가 불가능했다.
    spawn()이 돌려주는 호출 객체의 id를 기록해 두면 같은 실행을 다시 조회할 수 있다.
    """
    return str(getattr(call, "object_id", "") or "")


def unique_path(path: Path) -> Path:
    """Keep new H3 clips from overwriting an earlier clip in the flat material folder."""
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(str(path))

class JobRunner:
    def __init__(self, emit: Callable[[dict[str, Any]], None], modal_client: Any | None = None):
        self.emit = emit
        self.cancelled: set[str] = set()
        self.active: list[threading.Thread] = []
        self.modal = modal_client

    def _modal(self):
        if self.modal is None:
            import modal
            self.modal = modal
        return self.modal

    def handle(self, message: dict[str, Any]):
        kind, job_id = message["type"], message.get("job_id")
        if kind == "cancel_job":
            self.cancelled.add(job_id)
            # 취소 '요청'과 취소 '확인'은 다른 사실이다. 원격 작업은 계속될 수
            # 있으므로 여기서는 요청만 알리고, 확인은 원격 호출이 끝났을 때 보낸다.
            self.emit({"type":"cancel_requested","job_id":job_id,"message":"중단을 요청했습니다. 이미 시작한 원격 생성은 계속될 수 있습니다."})
            return
        if kind == "attach_job": self.emit({"type":"remote_attached","job_id":job_id,"function_call_id":message["function_call_id"]}); return
        if kind == "fetch_result":
            thread = threading.Thread(target=self._fetch_result, args=(message,), daemon=True)
            self.active.append(thread)
            thread.start()
            return
        if kind == "start_music":
            thread = threading.Thread(target=self._run_music, args=(message,), daemon=True)
            self.active.append(thread)
            thread.start()
            return
        if kind != "start_job": return
        thread = threading.Thread(target=self._run, args=(message,), daemon=True)
        self.active.append(thread)
        thread.start()

    def wait_for_jobs(self):
        for thread in self.active:
            thread.join()

    def _fetch_result(self, m: dict[str, Any]):
        """결과 수신만 다시 시도한다. 생성은 다시 하지 않는다.

        생성은 성공했는데 다운로드가 실패했거나, 취소 요청 뒤 결과를 받지
        않은 실행을 같은 원격 경로에서 복구할 때 쓴다.
        """
        job_id = m["job_id"]
        kind = str(m.get("kind", "video"))
        remote = str(m["remote_output_path"])
        try:
            modal = self._modal()
            if kind == "music":
                self.emit({"type":"stage","job_id":job_id,"stage":"AUDIO_DOWNLOADING"})
                volume = modal.Volume.from_name("yue2-outputs")
                music_root = Path(os.environ.get("MODAL_GUI_MUSIC_ROOT", r"F:\modal-gui\music")).expanduser()
                output_path = music_root / "gui" / job_id / Path(remote).name
                volume_path = remote
            else:
                self.emit({"type":"stage","job_id":job_id,"stage":"RESULT_DOWNLOADING"})
                volume = modal.Volume.from_name("minimax-h3-comfyui-data")
                output_root = Path(os.environ.get("MODAL_GUI_OUTPUT_ROOT", r"F:\modal-gui\h3-clips\generated")).expanduser()
                output_root.mkdir(parents=True, exist_ok=True)
                output_path = unique_path(output_root / Path(remote).name)
                volume_path = remote if remote.startswith("output/") else f"output/{remote}"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as handle:
                for chunk in volume.read_file(volume_path):
                    handle.write(chunk)
            payload = {"type":"completed","job_id":job_id,"remote_output_path":remote,"local_output_path":str(output_path.resolve())}
            if kind == "music":
                payload["kind"] = "music"
            self.emit(payload)
        except Exception as exc:
            self.emit({"type":"failed","job_id":job_id,"code":"RESULT_DOWNLOAD_FAILED","message":str(exc),"retryable":True})

    def _run_music(self, m: dict[str, Any]):
        job_id = m["job_id"]
        try:
            modal = self._modal()
            self.emit({"type":"stage","job_id":job_id,"stage":"MUSIC_GENERATING"})
            function = modal.Function.from_name("yue2-music", "generate_music")
            call = function.spawn(
                job_id,
                m["style"],
                m["lyrics"],
                int(m.get("seed", 4301) or 4301),
            )
            self.emit({"type":"remote_attached","job_id":job_id,"function_call_id":call_id_of(call) or f"modal-{job_id}"})
            result = call.get()
            relative = str(result["audio"])
            if job_id in self.cancelled:
                self.emit({"type":"cancelled","job_id":job_id,"message":"원격 생성이 끝났지만 중단 요청되어 결과를 내려받지 않았습니다.","remote_output_path":relative})
                return
            self.emit({"type":"stage","job_id":job_id,"stage":"AUDIO_DOWNLOADING"})
            volume = modal.Volume.from_name("yue2-outputs")
            music_root = Path(os.environ.get("MODAL_GUI_MUSIC_ROOT", r"F:\modal-gui\music")).expanduser()
            output_path = music_root / "gui" / job_id / Path(relative).name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as handle:
                for chunk in volume.read_file(relative):
                    handle.write(chunk)
            self.emit({"type":"completed","job_id":job_id,"remote_output_path":relative,"local_output_path":str(output_path.resolve()),"kind":"music"})
        except Exception as exc:
            self.emit({"type":"failed","job_id":job_id,"code":"MUSIC_GENERATION_FAILED","message":str(exc),"retryable":True})
    def _run(self, m: dict):
        job_id=m["job_id"]
        try:
            modal = self._modal()
            kind = str(m.get("kind", "t2v")).lower()
            attestation = os.environ.get("MINIMAX_H3_LICENSE_ATTESTATION") or DEFAULT_ATTESTATION
            input_path_value = m.get("input_path")
            input_path = Path(input_path_value).resolve() if input_path_value else None
            if kind != "t2v":
                if input_path is None or not input_path.is_file():
                    raise FileNotFoundError(f"입력 이미지가 없습니다: {input_path}")
                self.emit({"type":"stage","job_id":job_id,"stage":"INPUT_UPLOADING"})
            volume = modal.Volume.from_name("minimax-h3-comfyui-data")
            remote_input = ""
            if input_path is not None and input_path.is_file():
                remote_input = f"gui/{job_id}/{input_path.name}"
                with volume.batch_upload(force=True) as batch:
                    batch.put_file(input_path, remote_input)
            self.emit({"type":"stage","job_id":job_id,"stage":"CONTAINER_STARTING"})
            worker = modal.Cls.from_name("minimax-h3-latest-workflows", "LatestH3")()
            self.emit({"type":"stage","job_id":job_id,"stage":"GENERATING"})
            call = worker.generate.spawn(
                kind=kind,
                prompt=m["prompt"],
                input_filename=remote_input,
                seconds=float(m.get("duration", 5)),
                width=int(m.get("width", 1344)),
                height=int(m.get("height", 768)),
                seed=int(m.get("seed", 42) or 42),
                attestation=attestation,
            )
            self.emit({"type":"remote_attached","job_id":job_id,"function_call_id":call_id_of(call) or f"modal-{job_id}"})
            result = call.get()
            relative = result["relative_path"]
            if job_id in self.cancelled:
                self.emit({"type":"cancelled","job_id":job_id,"message":"원격 생성이 끝났지만 중단 요청되어 결과를 내려받지 않았습니다.","remote_output_path":relative})
                return
            self.emit({"type":"stage","job_id":job_id,"stage":"RESULT_DOWNLOADING"})
            output_root = Path(os.environ.get("MODAL_GUI_OUTPUT_ROOT", r"F:\modal-gui\h3-clips\generated")).expanduser()
            output_root.mkdir(parents=True, exist_ok=True)
            output_path = unique_path(output_root / Path(relative).name)
            with output_path.open("wb") as handle:
                for chunk in volume.read_file(f"output/{relative}"):
                    handle.write(chunk)
            self.emit({"type":"completed","job_id":job_id,"remote_output_path":relative,"local_output_path":str(output_path.resolve())})
        except Exception as exc:
            self.emit({"type":"failed","job_id":job_id,"code":"MODAL_GENERATION_FAILED","message":str(exc),"retryable":True})
