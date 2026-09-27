"""Contract tests for renderer plugins.

These check the parts the GUI depends on: every plugin reports a usable
`PluginInfo`, the Autograph sidecar matches docs/autograph-template.md, and the
Cavalry handoff writes a script plus payload with the data our pipeline
computed. Rendering itself is not exercised here; that needs real media.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.renderers import RenderRequest, TextCue, all_plugins, describe_all, get_plugin
from tools.renderers.autograph_renderer import AutographRenderer, timecode
from tools.renderers.cavalry_renderer import CavalryRenderer
from tools.renderers.ffmpeg_renderer import FfmpegRenderer
from tools.renderers.ae_renderer import AeRenderer


def make_request(output: Path) -> RenderRequest:
    return RenderRequest(
        clips=[Path("C:/clips/a.mp4"), Path("C:/clips/b.mp4"), Path("C:/clips/c.mp4")],
        audio=Path("C:/music/track.flac"),
        output=output,
        shot_durations=[5.5, 5.7, 6.35],
        beats=[0.55, 1.25, 4.65],
        cues=[TextCue(0.0, 5.0, "PUBG: BATTLEGROUNDS", 86)],
        duration=17.55,
    )


class RegistryTest(unittest.TestCase):
    def test_ids_are_unique(self) -> None:
        ids = [plugin.id for plugin in all_plugins()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_execution_mode_is_known(self) -> None:
        for info in describe_all():
            self.assertIn(info["execution"], {"batch", "project_handoff"})

    def test_unavailable_plugins_explain_why(self) -> None:
        for info in describe_all():
            if not info["available"]:
                self.assertTrue(
                    info["unavailable_reason"],
                    f"{info['id']} is unavailable but gives no reason",
                )

    def test_available_plugins_report_an_executable(self) -> None:
        for info in describe_all():
            if info["available"]:
                self.assertTrue(info["executable"], f"{info['id']} claims available with no path")

    def test_unknown_id_raises(self) -> None:
        with self.assertRaises(KeyError):
            get_plugin("does-not-exist")


class FfmpegFilterTest(unittest.TestCase):
    def test_base_mode_has_no_drawtext(self) -> None:
        request = make_request(Path("C:/out/base.mp4"))
        graph = FfmpegRenderer().build_filter(request, graphics=False)
        self.assertNotIn("drawtext", graph)
        self.assertIn("concat=n=3", graph)

    def test_graphics_mode_draws_each_cue_and_beat(self) -> None:
        request = make_request(Path("C:/out/graphics.mp4"))
        graph = FfmpegRenderer().build_filter(request, graphics=True)
        self.assertEqual(graph.count("drawtext"), len(request.cues))
        # one flash box per beat, plus the single progress bar at the end
        self.assertEqual(graph.count("drawbox"), len(request.beats) + 1)

    def test_shot_durations_reach_the_trim_filters(self) -> None:
        request = make_request(Path("C:/out/graphics.mp4"))
        graph = FfmpegRenderer().build_filter(request, graphics=True)
        for seconds in request.shot_durations:
            self.assertIn(f"trim=duration={seconds:.3f}", graph)

    def test_fontsize_stays_constant(self) -> None:
        """An expression fontsize stalls drawtext on real 1080p input.

        It parses and works on small synthetic sources, then silently produces
        zero frames on actual footage. Keep the size literal.
        """
        request = make_request(Path("C:/out/graphics.mp4"))
        graph = FfmpegRenderer().build_filter(request, graphics=True)
        for cue in request.cues:
            self.assertIn(f"fontsize={cue.size}:", graph)
        self.assertNotIn("fontsize='", graph)

    def test_no_per_pixel_beat_expression(self) -> None:
        """blend's all_expr runs per pixel; beat sums there never finish."""
        request = make_request(Path("C:/out/graphics.mp4"))
        graph = FfmpegRenderer().build_filter(request, graphics=True)
        self.assertNotIn("all_expr", graph)

    def test_beat_expression_is_a_lookup_not_a_sum(self) -> None:
        """Summing one pulse per beat made ffmpeg evaluate all 47 every frame.

        The string still grows with beat count, but the emitted form is a
        time-keyed `if` tree, so evaluation descends to a single pulse instead of
        adding every term. Guard the shape, which is what fixed the hang.
        """
        from tools.renderers.ffmpeg_renderer import _beat_kick

        many = _beat_kick([index * 1.25 for index in range(47)])
        self.assertIn("if(lt(t,", many)
        # A flat sum would join terms with '+'; the tree must not.
        self.assertNotIn(")+max(", many)
        # One pulse per beat is present, reached by branching rather than summing.
        self.assertEqual(many.count("max(0,1-"), 47)

    def test_graph_fits_in_a_script_file_not_argv(self) -> None:
        """47 beats previously produced a 41 KB graph passed on the command line."""
        request = make_request(Path("C:/out/graphics.mp4"))
        request.beats = [index * 1.25 for index in range(47)]
        graph = FfmpegRenderer().build_filter(request, graphics=True)
        self.assertLess(len(graph), 32000, "graph must stay under the argv limit")


class FfmpegTypographyTest(unittest.TestCase):
    def _with_fonts(self, names: list[str]):
        folder = tempfile.TemporaryDirectory()
        root = Path(folder.name)
        for name in names:
            (root / name).write_bytes(b"font")
        module = __import__("tools.renderers.ffmpeg_renderer", fromlist=["WINDOWS_FONTS"])
        original = module.WINDOWS_FONTS
        module.WINDOWS_FONTS = root
        self.addCleanup(setattr, module, "WINDOWS_FONTS", original)
        self.addCleanup(folder.cleanup)

    def test_hangul_text_picks_a_hangul_capable_font(self) -> None:
        self._with_fonts(["malgunbd.ttf", "arialbd.ttf"])
        request = make_request(Path("C:/out/korean.mp4"))
        request.cues = [TextCue(0, 2, "한국어 타이포", 64)]
        self.assertTrue(FfmpegRenderer()._resolve_fonts(request)[0].endswith("malgunbd.ttf"))

    def test_missing_requested_font_emits_font_missing(self) -> None:
        self._with_fonts(["arialbd.ttf"])
        request = make_request(Path("C:/out/missing-font.mp4"))
        request.cues = [TextCue(0, 2, "English", 64, "No Such Font")]
        events: list[tuple[str, dict]] = []
        FfmpegRenderer()._resolve_fonts(request, lambda event, **fields: events.append((event, fields)))
        self.assertEqual(events[0][0], "font_missing")
        self.assertEqual(events[0][1]["requested"], "No Such Font")

    def test_non_hangul_cue_keeps_arial(self) -> None:
        self._with_fonts(["arialbd.ttf", "segoeuib.ttf"])
        request = make_request(Path("C:/out/english.mp4"))
        request.cues = [TextCue(0, 2, "English", 64)]
        self.assertTrue(FfmpegRenderer()._resolve_fonts(request)[0].endswith("arialbd.ttf"))

    def test_pretendard_bold_resolves_like_the_export_check(self) -> None:
        # Rust의 내보내기 글꼴 판정과 같은 이름을 Python도 알아야 한다.
        self._with_fonts(["Pretendard-Bold.ttf"])
        request = make_request(Path("C:/out/korean.mp4"))
        request.cues = [TextCue(0, 2, "한국어", 64, "Pretendard Bold")]
        events: list[tuple[str, dict]] = []
        fonts = FfmpegRenderer()._resolve_fonts(request, lambda event, **fields: events.append((event, fields)))
        self.assertTrue(fonts[0].endswith("Pretendard-Bold.ttf"))
        self.assertEqual(events, [])

    def test_korean_drawtext_references_the_hangul_font(self) -> None:
        self._with_fonts(["malgun.ttf", "arialbd.ttf"])
        request = make_request(Path("C:/out/korean.mp4"))
        request.cues = [TextCue(0, 2, "한국어", 64)]
        graph = FfmpegRenderer().build_filter(request, graphics=True)
        self.assertIn("malgun.ttf", graph)

    def test_font_path_in_the_graph_uses_forward_slashes(self) -> None:
        # ffmpeg 8.1.1 on Windows dies with 0xC0000005 on a backslash fontfile
        # path inside the filter script, so the graph must never carry one.
        self._with_fonts(["malgunbd.ttf"])
        request = make_request(Path("C:/out/korean.mp4"))
        request.cues = [TextCue(0, 2, "한국어", 64)]
        graph = FfmpegRenderer().build_filter(request, graphics=True)
        fontfile = re.search(r"fontfile='([^']+)'", graph)
        self.assertIsNotNone(fontfile)
        value = fontfile.group(1)
        self.assertNotIn("\\W", value)
        self.assertIn("/", value)
        self.assertTrue(value.startswith("C\\:"))


class AutographSidecarTest(unittest.TestCase):
    def test_timecode_matches_autograph_range_format(self) -> None:
        # `AutographRenderer.exe --help` documents range=H:MM:SS:FF;H:MM:SS:FF
        self.assertEqual(timecode(0, 24), "0:00:00:00")
        self.assertEqual(timecode(1, 24), "0:00:01:00")
        self.assertEqual(timecode(60, 24), "0:01:00:00")
        self.assertEqual(timecode(61.5, 24), "0:01:01:12")
        self.assertEqual(timecode(3661, 24), "1:01:01:00")

    def test_missing_template_prepares_instead_of_failing(self) -> None:
        events: list[tuple[str, dict]] = []

        def emit(event: str, **fields: object) -> None:
            events.append((event, dict(fields)))

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "out.mov"
            module = __import__(
                "tools.renderers.autograph_renderer", fromlist=["find_autograph"]
            )
            original = module.find_autograph
            module.find_autograph = lambda: "C:/fake/Autograph.exe"
            try:
                result = AutographRenderer().render(make_request(output), emit)
            finally:
                module.find_autograph = original

            self.assertEqual(result.suffix, ".json")
            self.assertTrue(result.exists())
            kinds = [name for name, _ in events]
            self.assertIn("prepared", kinds)
            self.assertNotIn("render_completed", kinds)

            payload = json.loads(result.read_text(encoding="utf-8"))
            # Keys the template in docs/autograph-template.md relies on.
            self.assertEqual(
                sorted(payload),
                ["audio", "beats", "clips", "cues", "shot_durations"],
            )
            self.assertAlmostEqual(sum(payload["shot_durations"]), 17.55, places=3)


class CavalryHandoffTest(unittest.TestCase):
    def test_writes_script_and_payload_and_never_reports_progress(self) -> None:
        events: list[tuple[str, dict]] = []

        def emit(event: str, **fields: object) -> None:
            events.append((event, dict(fields)))

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "out.mp4"
            module = __import__(
                "tools.renderers.cavalry_renderer", fromlist=["find_cavalry", "SCRIPT_DIR"]
            )
            original_find = module.find_cavalry
            original_dir = module.SCRIPT_DIR
            module.find_cavalry = lambda: "C:/fake/Cavalry.exe"
            module.SCRIPT_DIR = Path(folder) / "plugins"
            try:
                result = CavalryRenderer().render(make_request(output), emit)
            finally:
                module.find_cavalry = original_find
                module.SCRIPT_DIR = original_dir

            self.assertEqual(result.suffix, ".js")
            self.assertTrue(result.exists())
            kinds = [name for name, _ in events]
            self.assertIn("prepared", kinds)
            self.assertNotIn("render_progress", kinds)
            self.assertNotIn("render_completed", kinds)

            payload_path = output.with_name(output.stem + "-cavalry-payload.json")
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["shot_durations"]), 3)
            self.assertEqual(len(payload["beats"]), 3)
            self.assertEqual(len(payload["cues"]), 1)

            script = result.read_text(encoding="utf-8")
            self.assertIn("addRenderQueueItem", script)
            self.assertIn(payload_path.as_posix(), script)


class AeHandoffTest(unittest.TestCase):
    def test_describe_reports_honest_availability(self) -> None:
        info = AeRenderer().describe()
        self.assertIsInstance(info.available, bool)
        if info.available:
            self.assertTrue(info.executable)
        else:
            self.assertTrue(info.unavailable_reason)

    def test_writes_motion_json_and_extend_script(self) -> None:
        events: list[tuple[str, dict]] = []

        def emit(event: str, **fields: object) -> None:
            events.append((event, dict(fields)))

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "out.mp4"
            request = make_request(output)
            request.cues = [TextCue(1.0, 3.0, "한국어 자막", 72, "맑은 고딕")]
            result = AeRenderer().render(request, emit)
            motion_path = output.with_suffix(".motion.json")
            self.assertEqual(result, output.with_suffix(".ae.jsx"))
            self.assertTrue(motion_path.exists())
            self.assertTrue(result.exists())
            payload = json.loads(motion_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["durationTicks"], round(request.duration * 24000))
            self.assertEqual([layer["type"] for layer in payload["layers"]], ["video"] * 3 + ["text"])
            self.assertEqual(payload["layers"][-1]["startTick"], 24000)
            self.assertEqual(payload["layers"][-1]["endTick"], 72000)
            script = result.read_text(encoding="utf-8")
            self.assertIn("한국어 자막", script)
            self.assertIn(json.dumps(str(motion_path.resolve()), ensure_ascii=False), script)
            self.assertIn("app.project.save", script)
            # The handoff must not modify whatever project the user already has open.
            self.assertIn("app.newProject()", script)
            self.assertIn("confirm(", script)
            # Unattended mode is opt-in: only the instance the app launches
            # itself writes a log and quits, and it still refuses to touch a
            # project that is already open.
            self.assertIn("MODAL_GUI_AE_QUIET", script)
            self.assertIn(".ae.log", script)
            self.assertIn("app.quit()", script)
            self.assertIn("이미 다른 프로젝트가 열려 있습니다", script)
            # A non-empty untitled project is still the user's work.
            self.assertIn("app.project.numItems > 0", script)
            self.assertIn("제목 없는 프로젝트", script)
            # Only an empty untitled instance is ours to close, and a failed
            # read or a missing source must not be reported as completion.
            self.assertIn("!app.project.file && app.project.numItems === 0", script)
            self.assertIn("Motion JSON을 읽지 못했습니다", script)
            self.assertIn("누락 소재", script)
            self.assertIn("찾지 못해 프로젝트가 불완전합니다", script)
            self.assertNotIn("render_completed", [name for name, _ in events])

    def test_hangul_text_without_a_font_names_a_korean_font(self) -> None:
        # A text layer with no font keeps the AE default, which is not guaranteed
        # to carry Hangul glyphs; the handoff must name the Korean font instead.
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "out.mp4"
            request = make_request(output)
            request.cues = [
                TextCue(1.0, 3.0, "한국어 자막", 72),
                TextCue(3.0, 5.0, "Latin only", 72),
            ]
            AeRenderer().render(request, lambda *_, **__: None)
            payload = json.loads(output.with_suffix(".motion.json").read_text(encoding="utf-8"))
            fonts = [layer["font"] for layer in payload["layers"] if layer["type"] == "text"]
            self.assertEqual(fonts, ["Malgun Gothic", None])


CAVALRY_METADATA = Path(
    os.path.expandvars(
        r"%LOCALAPPDATA%\Programs\Cavalry\assets\MetaData\api_function_metadata.json"
    )
)


class CavalryApiContractTest(unittest.TestCase):
    """Every api.* call we generate must exist in Cavalry's own metadata.

    Cavalry has no CLI, so a typo in the generated script only surfaces when a
    human runs it. This catches that at build time instead.
    """

    def test_generated_script_uses_only_real_api_functions(self) -> None:
        if not CAVALRY_METADATA.exists():
            self.skipTest("Cavalry is not installed on this host")

        entries = json.loads(CAVALRY_METADATA.read_text(encoding="utf-8"))
        known = {entry["name"] for entry in entries if isinstance(entry, dict)}

        events: list[tuple[str, dict]] = []

        def emit(event: str, **fields: object) -> None:
            events.append((event, dict(fields)))

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "out.mp4"
            module = __import__(
                "tools.renderers.cavalry_renderer", fromlist=["find_cavalry", "SCRIPT_DIR"]
            )
            original_find = module.find_cavalry
            original_dir = module.SCRIPT_DIR
            module.find_cavalry = lambda: "C:/fake/Cavalry.exe"
            module.SCRIPT_DIR = Path(folder) / "plugins"
            try:
                script_path = CavalryRenderer().render(make_request(output), emit)
            finally:
                module.find_cavalry = original_find
                module.SCRIPT_DIR = original_dir

            script = script_path.read_text(encoding="utf-8")

        called = set(re.findall(r"\bapi\.([A-Za-z_][A-Za-z0-9_]*)\s*\(", script))
        self.assertTrue(called, "no api calls found in the generated script")
        unknown = sorted(called - known)
        self.assertEqual(unknown, [], f"generated script calls unknown Cavalry API: {unknown}")


class StoryboardTrimTest(unittest.TestCase):
    """The editable shot list only works if in-points reach the filter graph."""

    def test_head_of_clip_stays_unchanged(self) -> None:
        graph = FfmpegRenderer().build_filter(make_request(Path("C:/out/base.mp4")), False)
        self.assertIn("[0:v]trim=duration=5.500", graph)
        self.assertNotIn("start=", graph)

    def test_in_point_reaches_the_trim_filter(self) -> None:
        request = make_request(Path("C:/out/trim.mp4"))
        request.clip_starts = [1.25, 0.0, 2.5]
        graph = FfmpegRenderer().build_filter(request, False)
        self.assertIn("[0:v]trim=start=1.250:duration=5.500", graph)
        self.assertIn("[1:v]trim=duration=5.700", graph)
        self.assertIn("[2:v]trim=start=2.500:duration=6.350", graph)


if __name__ == "__main__":
    unittest.main()
