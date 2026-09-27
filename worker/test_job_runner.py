import tempfile
import types
import unittest
from pathlib import Path

from worker.job_runner import JobRunner, unique_path


class FakeVolume:
    def __init__(self):
        self.reads = 0

    def read_file(self, _path):
        self.reads += 1
        return [b"result"]


class FakeRemote:
    def __init__(self, result, call_id="fc-test-1"):
        self.result = result
        self.calls = 0
        self.call_id = call_id

    def remote(self, *_args, **_kwargs):
        self.calls += 1
        return self.result

    def spawn(self, *_args, **_kwargs):
        self.calls += 1
        return types.SimpleNamespace(object_id=self.call_id, get=lambda: self.result)


class FakeModal:
    def __init__(self, result, call_id="fc-test-1"):
        self.volume = FakeVolume()
        self.worker = FakeRemote(result, call_id)
        self.Cls = types.SimpleNamespace(from_name=lambda *_args: lambda: types.SimpleNamespace(generate=self.worker))
        self.Function = types.SimpleNamespace(from_name=lambda *_args: self.worker)
        self.Volume = types.SimpleNamespace(from_name=lambda *_args: self.volume)


class UniquePathTest(unittest.TestCase):
    def test_free_name_is_used_as_is(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "fl2v_00010-audio.mp4"
            self.assertEqual(unique_path(target), target)

    def test_existing_clip_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = root / "fl2v_00010-audio.mp4"
            first.write_bytes(b"clip")
            (root / "fl2v_00010-audio-2.mp4").write_bytes(b"clip")
            resolved = unique_path(first)
            self.assertEqual(resolved.name, "fl2v_00010-audio-3.mp4")
            self.assertEqual(resolved.parent, root)


class RemoteCallIdTest(unittest.TestCase):
    """`remote()`는 호출 id를 남기지 않아 재조회가 불가능했다. spawn()의 id를 기록한다."""

    def test_video_reports_the_real_modal_call_id(self):
        events = []
        fake = FakeModal({"relative_path": "clip.mp4"}, call_id="fc-abc123")
        with tempfile.TemporaryDirectory() as folder:
            runner = JobRunner(events.append, modal_client=fake)
            import os
            os.environ["MODAL_GUI_OUTPUT_ROOT"] = folder
            runner._run({"job_id": "job-id", "kind": "t2v", "prompt": "test"})
            attached = [event for event in events if event["type"] == "remote_attached"]
            self.assertEqual(attached[0]["function_call_id"], "fc-abc123")
            self.assertNotIn("modal-job-id", str(attached))

    def test_music_reports_the_real_modal_call_id(self):
        events = []
        fake = FakeModal({"audio": "song/audio.flac"}, call_id="fc-music-9")
        with tempfile.TemporaryDirectory() as folder:
            runner = JobRunner(events.append, modal_client=fake)
            import os
            os.environ["MODAL_GUI_MUSIC_ROOT"] = folder
            runner._run_music({"job_id": "job-id", "style": "lofi", "lyrics": "la"})
            attached = [event for event in events if event["type"] == "remote_attached"]
            self.assertEqual(attached[0]["function_call_id"], "fc-music-9")


class FetchResultTest(unittest.TestCase):
    """생성은 성공했고 다운로드만 실패한 실행은 결과 수신부터 복구한다."""

    def test_video_result_is_downloaded_from_the_recorded_path(self):
        events = []
        fake = FakeModal({})
        with tempfile.TemporaryDirectory() as folder:
            import os
            os.environ["MODAL_GUI_OUTPUT_ROOT"] = folder
            runner = JobRunner(events.append, modal_client=fake)
            runner._fetch_result({
                "job_id": "job-1",
                "remote_output_path": "clip.mp4",
                "kind": "video",
            })
            completed = events[-1]
            self.assertEqual(completed["type"], "completed")
            self.assertTrue(completed["local_output_path"].endswith("clip.mp4"))
            self.assertTrue(Path(completed["local_output_path"]).is_file())
            self.assertEqual(completed["remote_output_path"], "clip.mp4")

    def test_music_result_is_downloaded_from_the_recorded_path(self):
        events = []
        fake = FakeModal({})
        with tempfile.TemporaryDirectory() as folder:
            import os
            os.environ["MODAL_GUI_MUSIC_ROOT"] = folder
            runner = JobRunner(events.append, modal_client=fake)
            runner._fetch_result({
                "job_id": "job-2",
                "remote_output_path": "job-2/audio.flac",
                "kind": "music",
            })
            completed = events[-1]
            self.assertEqual(completed["type"], "completed")
            self.assertEqual(completed["kind"], "music")
            self.assertTrue(Path(completed["local_output_path"]).is_file())

    def test_download_failure_is_reported_as_failed(self):
        events = []

        class BrokenVolume(FakeVolume):
            def read_file(self, _path):
                raise RuntimeError("volume unavailable")

        fake = FakeModal({})
        fake.volume = BrokenVolume()
        fake.Volume = types.SimpleNamespace(from_name=lambda *_args: fake.volume)
        with tempfile.TemporaryDirectory() as folder:
            import os
            os.environ["MODAL_GUI_OUTPUT_ROOT"] = folder
            runner = JobRunner(events.append, modal_client=fake)
            runner._fetch_result({
                "job_id": "job-3",
                "remote_output_path": "clip.mp4",
                "kind": "video",
            })
            self.assertEqual(events[-1]["type"], "failed")
            self.assertEqual(events[-1]["code"], "RESULT_DOWNLOAD_FAILED")


class CancelAfterRemoteCompletionTest(unittest.TestCase):
    def test_video_cancel_skips_download_after_remote_completion(self):
        events = []
        fake = FakeModal({"relative_path": "clip.mp4"})
        with tempfile.TemporaryDirectory() as folder:
            runner = JobRunner(events.append, modal_client=fake)
            runner.cancelled.add("job-1")
            runner._run({"job_id": "job-1", "kind": "t2v", "prompt": "test"})
            self.assertEqual(fake.volume.reads, 0)
            self.assertEqual(events[-1]["type"], "cancelled")
            self.assertEqual(events[-1]["remote_output_path"], "clip.mp4")
            self.assertNotIn("completed", [event["type"] for event in events])

    def test_music_cancel_skips_download_after_remote_completion(self):
        events = []
        fake = FakeModal({"audio": "audio.wav"})
        runner = JobRunner(events.append, modal_client=fake)
        runner.cancelled.add("music-1")
        runner._run_music({"job_id": "music-1", "style": "ambient", "lyrics": ""})
        self.assertEqual(fake.volume.reads, 0)
        self.assertEqual(events[-1]["type"], "cancelled")
        self.assertEqual(events[-1]["remote_output_path"], "audio.wav")

    def test_cancel_reply_explains_remote_work_can_continue(self):
        events = []
        runner = JobRunner(events.append, modal_client=FakeModal({}))
        runner.handle({"type": "cancel_job", "job_id": "job-2"})
        self.assertEqual(events[-1], {
            # 요청과 확인을 구분한다. 원격 취소가 확인되기 전에는 cancelled가 아니다.
            "type": "cancel_requested",
            "job_id": "job-2",
            "message": "중단을 요청했습니다. 이미 시작한 원격 생성은 계속될 수 있습니다.",
        })


if __name__ == "__main__":
    unittest.main()
