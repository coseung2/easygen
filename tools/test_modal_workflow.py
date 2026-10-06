import base64
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock

from tools import modal_workflow as client


class WaitTimeout(Exception):
    pass


class FunctionTimeout(WaitTimeout):
    pass


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "run"

    def prepare(self, kind="video", **request):
        source = self.root / "request.json"
        source.write_text(json.dumps(request), encoding="utf-8")
        client.prepare(kind, source, self.folder)

    def modal(self, call):
        return types.SimpleNamespace(
            FunctionCall=types.SimpleNamespace(from_id=Mock(return_value=call)),
            exception=types.SimpleNamespace(TimeoutError=WaitTimeout, FunctionTimeoutError=FunctionTimeout))

    def test_modes_keep_connected_graph_and_two_outputs(self):
        for mode, inputs in (("text", {}), ("image", {"image_name": "a.png"}),
                             ("reference", {"video_name": "v.mp4"}),
                             ("reference", {"image_name": "a.png", "video_name": "v.mp4"})):
            graph = client.build_graph(mode=mode, prompt="a lake", seconds=2, width=1344,
                                       height=768, seed=0, output_prefix="test", **inputs)
            self.assertEqual(graph["33"]["inputs"]["filename_prefix"], "test_final")
            self.assertEqual(graph["9001"]["inputs"]["filename_prefix"], "test_preview")
            for node in graph.values():
                for value in node["inputs"].values():
                    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                        self.assertIn(value[0], graph)

    def test_prepare_offline_relative_input_and_zero_seed(self):
        (self.root / "image.png").write_bytes(b"fixture")
        self.prepare(mode="image", prompt="test", image_path="image.png", seed=0)
        state = client.read(self.folder / "state.json")
        self.assertEqual(state["status"], "prepared")
        self.assertEqual(Path(state["files"][0]["local"]), self.root / "image.png")
        graph = client.read(self.folder / "graph.json")
        noise = [node for node in graph.values() if node["class_type"] == "RandomNoise"]
        self.assertTrue(all(node["inputs"]["noise_seed"] == 0 for node in noise))

    def test_no_ignored_video_input(self):
        with self.assertRaises(ValueError):
            self.prepare(mode="text", prompt="test", image_path="missing.png")
        self.assertFalse(self.folder.exists())

    def test_submit_passes_existing_attestation_and_refuses_repeat(self):
        self.prepare(mode="text", prompt="test")
        spawn = Mock(return_value=types.SimpleNamespace(object_id="fc-test"))
        worker = types.SimpleNamespace(run_graph=types.SimpleNamespace(spawn=spawn))
        modal = types.SimpleNamespace(Cls=types.SimpleNamespace(from_name=lambda *args: lambda: worker))
        client.submit(self.folder, modal)
        self.assertEqual(spawn.call_args.kwargs["attestation"], client.H3_ATTESTATION)
        self.assertEqual(client.read(self.folder / "state.json")["call_id"], "fc-test")
        with self.assertRaises(ValueError):
            client.submit(self.folder, modal)
        self.assertEqual(spawn.call_count, 1)

    def test_ambiguous_submission_does_not_retry(self):
        self.prepare(mode="text", prompt="test")
        spawn = Mock(side_effect=ConnectionError("reply lost"))
        worker = types.SimpleNamespace(run_graph=types.SimpleNamespace(spawn=spawn))
        modal = types.SimpleNamespace(Cls=types.SimpleNamespace(from_name=lambda *args: lambda: worker))
        with self.assertRaises(ConnectionError):
            client.submit(self.folder, modal)
        self.assertEqual(client.read(self.folder / "state.json")["status"], "submitting")
        with self.assertRaises(ValueError):
            client.submit(self.folder, modal)
        self.assertEqual(spawn.call_count, 1)

    def test_exclusive_lock_blocks_second_submitter(self):
        self.prepare(mode="text", prompt="test")
        (self.folder / "submit.lock").touch()
        with self.assertRaises(FileExistsError):
            client.submit(self.folder, None)

    def test_waiting_and_function_timeout_are_distinct(self):
        self.prepare(mode="text", prompt="test")
        state = client.read(self.folder / "state.json")
        state.update(status="submitted", call_id="fc-test")
        client.write(self.folder / "state.json", state)
        call = types.SimpleNamespace(get=Mock(side_effect=WaitTimeout()))
        client.status(self.folder, self.modal(call))
        self.assertEqual(client.read(self.folder / "state.json")["status"], "submitted")
        call.get.side_effect = FunctionTimeout()
        with self.assertRaises(FunctionTimeout):
            client.status(self.folder, self.modal(call))
        self.assertEqual(client.read(self.folder / "state.json")["status"], "failed")

    def test_image_response_is_saved_then_downloaded_without_resubmit(self):
        self.prepare("image", model="krea", prompt="a cup")
        state = client.read(self.folder / "state.json")
        state.update(status="submitted", call_id="fc-test")
        client.write(self.folder / "state.json", state)
        call = types.SimpleNamespace(get=Mock(return_value={"images": [base64.b64encode(b"fixture").decode()]}))
        client.status(self.folder, self.modal(call))
        client.download(self.folder, None)
        self.assertEqual((self.folder / "image-1.png").read_bytes(), b"fixture")
        self.assertEqual(client.read(self.folder / "state.json")["status"], "downloaded")

    def test_music_rejects_unsupported_duration(self):
        with self.assertRaises(ValueError):
            self.prepare("music", style="folk", duration=10)

    def test_music_submission_preserves_zero_seed(self):
        self.prepare("music", style="folk", lyrics="verse", seed=0)
        spawn = Mock(return_value=types.SimpleNamespace(object_id="fc-music"))
        modal = types.SimpleNamespace(Function=types.SimpleNamespace(
            from_name=Mock(return_value=types.SimpleNamespace(spawn=spawn))))
        client.submit(self.folder, modal)
        self.assertEqual(spawn.call_args.kwargs["seed"], 0)
        self.assertEqual(spawn.call_args.kwargs["job_id"], client.read(self.folder / "state.json")["job_id"])

    def test_video_download_uses_returned_volume_paths(self):
        self.prepare(mode="text", prompt="test")
        state = client.read(self.folder / "state.json")
        state["status"] = "completed"
        client.write(self.folder / "state.json", state)
        client.write(self.folder / "remote-result.json", {"outputs": {
            "33": {"gifs": [{"filename": "final_00001.mp4", "subfolder": "easygen/job"}]},
            "9001": {"gifs": [{"filename": "preview_00001.mp4", "subfolder": "easygen/job"}]}}})
        read_file = Mock(return_value=[b"fixture"])
        modal = types.SimpleNamespace(Volume=types.SimpleNamespace(from_name=Mock(
            return_value=types.SimpleNamespace(read_file=read_file))))
        client.download(self.folder, modal)
        self.assertEqual([c.args[0] for c in read_file.call_args_list],
                         ["output/easygen/job/final_00001.mp4", "output/easygen/job/preview_00001.mp4"])
        self.assertEqual(set(client.read(self.folder / "outputs.json")), {"final.mp4", "preview.mp4"})

    def test_missing_image_prompt_creates_no_run_folder(self):
        with self.assertRaises(ValueError):
            self.prepare("image", model="krea")
        self.assertFalse(self.folder.exists())


if __name__ == "__main__":
    unittest.main()
