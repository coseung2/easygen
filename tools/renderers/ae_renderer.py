"""After Effects project handoff renderer.

The renderer prepares an editable motion description and an ExtendScript file.
After Effects performs the actual import, project creation, and later render.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from .base import Capability, Emit, PluginInfo, RenderRequest


def _registry_installs() -> list[tuple[str, str | None]]:
    try:
        import winreg
    except ImportError:
        return []

    found: list[tuple[str, str | None]] = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            root = r"Software\Adobe\After Effects"
            try:
                with winreg.OpenKey(hive, root, 0, winreg.KEY_READ | view) as key:
                    for index in range(winreg.QueryInfoKey(key)[0]):
                        version = winreg.EnumKey(key, index)
                        with winreg.OpenKey(key, version) as version_key:
                            install_path = None
                            for value_name in ("InstallPath", "installationPath"):
                                try:
                                    install_path = str(winreg.QueryValueEx(version_key, value_name)[0])
                                    break
                                except OSError:
                                    continue
                        found.append((version, install_path))
            except OSError:
                continue
    return found


def _find_after_effects() -> tuple[str | None, str | None]:
    aerender = shutil.which("aerender")
    if aerender:
        return aerender, None

    registry = _registry_installs()
    for version, install_path in registry:
        candidates = []
        if install_path:
            candidates.append(Path(install_path) / "Support Files" / "aerender.exe")
            candidates.append(Path(install_path) / "aerender.exe")
        candidates.extend(Path(path) for path in (
            rf"C:\Program Files\Adobe\Adobe After Effects {version}\Support Files\aerender.exe",
            rf"C:\Program Files\Adobe\Adobe After Effects {version}\aerender.exe",
        ))
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate), version
        if install_path:
            return install_path, version

    for candidate in sorted(Path(r"C:\Program Files\Adobe").glob("Adobe After Effects *")):
        if candidate.is_dir():
            match = re.search(r"After Effects\s+(.+)$", candidate.name)
            version = match.group(1) if match else None
            aerender_path = candidate / "Support Files" / "aerender.exe"
            return str(aerender_path if aerender_path.is_file() else candidate), version
    return None, None


def _js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _duration_ticks(seconds: float) -> int:
    return round(seconds * 24000)


def _motion_payload(request: RenderRequest) -> dict:
    layers: list[dict] = []
    cursor = 0.0
    for index, (clip, duration) in enumerate(zip(request.clips, request.shot_durations)):
        start = cursor
        end = start + duration
        in_point = request.clip_starts[index] if index < len(request.clip_starts) else 0.0
        layers.append({
            "type": "video",
            "index": index,
            "source": str(clip.resolve()),
            "startTick": _duration_ticks(start),
            "endTick": _duration_ticks(end),
            "inPoint": _duration_ticks(in_point),
            "inPointTick": _duration_ticks(in_point),
        })
        cursor = end

    for index, cue in enumerate(request.cues):
        span = max(0.2, cue.end - cue.start)
        fade_in = min(0.45, span / 3)
        fade_out = min(0.25, span / 5)
        layers.append({
            "type": "text",
            "index": index,
            "text": cue.text,
            "font": _text_font(cue),
            "size": cue.size,
            "startTick": _duration_ticks(cue.start),
            "endTick": _duration_ticks(cue.end),
            "opacityKeyframes": [
                {"tick": _duration_ticks(cue.start), "value": 0},
                {"tick": _duration_ticks(cue.start + fade_in), "value": 100},
                {"tick": _duration_ticks(cue.end - fade_out), "value": 100},
                {"tick": _duration_ticks(cue.end), "value": 0},
            ],
        })
    return {
        "version": 1,
        "name": request.output.stem,
        "width": request.width,
        "height": request.height,
        "fps": request.fps,
        "durationTicks": _duration_ticks(request.duration),
        "durationSeconds": request.duration,
        "audio": str(request.audio.resolve()),
        "layers": layers,
    }


def _build_script(motion_path: Path, project_path: Path, cue_texts: list[str]) -> str:
    motion_literal = _js_string(str(motion_path.resolve()))
    project_literal = _js_string(str(project_path.resolve()))
    cue_texts_literal = json.dumps(cue_texts, ensure_ascii=False)
    return """(function () {
  var motionPath = %s;
  var projectPath = %s;
  var cueTexts = %s;
  // Unattended mode: the app sets MODAL_GUI_AE_QUIET=1 only for the After
  // Effects instance it launches itself. A user's own session never has that
  // variable, so alerts and confirmations keep working there.
  var quiet = $.getenv("MODAL_GUI_AE_QUIET") === "1";
  // Only an empty, untitled instance belongs to this run. A title-less project
  // that already has items is still the user's work: it must not be closed.
  var startedEmpty = !app.project.file && app.project.numItems === 0;
  var logFile = new File(projectPath.replace(/\\.aep$/i, ".ae.log"));
  function note(message) {
    if (!quiet) {
      return;
    }
    try {
      logFile.open("a");
      logFile.writeln(new Date().toString() + " " + message);
      logFile.close();
    } catch (error) {
      // 로그를 쓰지 못해도 프로젝트 생성은 계속한다.
    }
  }
  function finish(message, failed) {
    if (!quiet) {
      alert(message);
      return;
    }
    note((failed ? "실패: " : "완료: ") + message);
    if (startedEmpty) {
      app.quit();
    }
  }
  var file = new File(motionPath);
  if (!file.exists) {
    finish("Motion JSON을 찾지 못했습니다: " + motionPath, true);
    return;
  }
  note("시작: " + motionPath);
  var data = null;
  try {
    file.open("r");
    data = eval("(" + file.read() + ")");
    file.close();
  } catch (error) {
    finish("Motion JSON을 읽지 못했습니다: " + error.toString(), true);
    return;
  }
  if (!data || !data.layers) {
    finish("Motion JSON 형식이 올바르지 않습니다: " + motionPath, true);
    return;
  }

  // Never touch whatever project the user already has open: the handoff builds
  // its own project and saves it to the path this script was written for.
  var target = new File(projectPath);
  var current = app.project.file;
  // An untitled project can still hold unsaved work; treat a non-empty one
  // like any other project the user might not want to lose.
  var otherProject = current && current.fsName !== target.fsName;
  var untitledWork = !current && app.project.numItems > 0;
  if (otherProject || untitledWork) {
    if (quiet) {
      note("중단: 이미 다른 프로젝트가 열려 있습니다: " + (current ? current.fsName : "제목 없는 프로젝트"));
      return;
    }
    if (!confirm("현재 열린 프로젝트를 닫고 준비된 프로젝트를 새로 만듭니다. 저장하지 않은 변경이 있으면 먼저 저장하세요. 계속할까요?")) {
      return;
    }
  }
  app.newProject();

  app.beginUndoGroup("Modal GUI motion handoff");
  var failure = null;
  var missing = [];
  try {
    var comp = app.project.items.addComp(data.name, data.width, data.height, 1.0,
      data.durationSeconds, data.fps);
    var layer;
    var item;
    var i;
    var j;
    var startSeconds;
    var endSeconds;
    for (i = 0; i < data.layers.length; i++) {
      item = data.layers[i];
      startSeconds = item.startTick / 24000.0;
      endSeconds = item.endTick / 24000.0;
      if (item.type === "video") {
        var footage = new File(item.source);
        if (footage.exists) {
          var imported = app.project.importFile(new ImportOptions(footage));
          layer = comp.layers.add(imported);
          layer.startTime = startSeconds - item.inPointTick / 24000.0;
          layer.inPoint = startSeconds;
          layer.outPoint = endSeconds;
        } else {
          missing.push(item.source);
        }
      } else if (item.type === "text") {
        layer = comp.layers.addText(item.text);
        layer.startTime = startSeconds;
        layer.inPoint = startSeconds;
        layer.outPoint = endSeconds;
        var document = layer.property("Source Text");
        var textDocument = document.value;
        if (item.font) {
          textDocument.font = item.font;
        }
        textDocument.fontSize = item.size;
        document.setValue(textDocument);
        var opacity = layer.property("Transform").property("Opacity");
        for (j = 0; j < item.opacityKeyframes.length; j++) {
          opacity.setValueAtTime(item.opacityKeyframes[j].tick / 24000.0,
            item.opacityKeyframes[j].value);
        }
      }
    }
    var audioFile = new File(data.audio);
    if (audioFile.exists) {
      var audioItem = app.project.importFile(new ImportOptions(audioFile));
      comp.layers.add(audioItem);
    } else {
      missing.push(data.audio);
    }
  } catch (error) {
    failure = error.toString();
  }
  app.endUndoGroup();
  if (!failure) {
    try {
      app.project.save(new File(projectPath));
    } catch (error) {
      failure = error.toString();
    }
  }
  if (failure) {
    finish("프로젝트 생성 중 오류: " + failure, true);
    return;
  }
  note("저장: " + projectPath);
  note("구성: " + comp.name + " " + comp.width + "x" + comp.height + " · " + data.durationSeconds + "초 · 레이어 " + comp.numLayers + "개");
  if (cueTexts.length > 0) {
    note("문구: " + cueTexts.join(" / "));
  }
  if (missing.length > 0) {
    // 소재가 빠진 프로젝트를 완성으로 기록하지 않는다.
    note("누락 소재: " + missing.join(", "));
    finish("필요한 소재 " + missing.length + "개를 찾지 못해 프로젝트가 불완전합니다: " + missing.join(", "), true);
    return;
  }
  if (comp.numLayers === 0) {
    finish("구성에 레이어가 없어 빈 프로젝트만 만들어졌습니다.", true);
    return;
  }
  finish("After Effects 프로젝트를 만들었습니다. Composition을 확인한 뒤 Render Queue에서 수동으로 렌더하세요.", false);
})();
""" % (motion_literal, project_literal, cue_texts_literal)


class AeRenderer:
    id = "ae"
    name = "After Effects"
    execution = "project_handoff"

    def describe(self) -> PluginInfo:
        executable, version = _find_after_effects()
        return PluginInfo(
            id=self.id,
            name=self.name,
            execution=self.execution,
            available=bool(executable),
            executable=executable,
            version=version,
            unavailable_reason=None if executable else "After Effects 설치를 확인하지 못했습니다.",
            capabilities=Capability(
                kinetic_typography=True,
                beat_reactive_cuts=False,
                beat_reactive_effects=False,
                audio_mux=True,
                expressions=True,
                watermark=False,
                max_resolution=None,
            ),
            notes="ExtendScript(.jsx) 프로젝트 생성 후 After Effects에서 열어 렌더합니다.",
        )

    def render(self, request: RenderRequest, emit: Emit) -> Path:
        info = self.describe()
        if not info.available:
            emit("tool_missing", tool="ae", reason=info.unavailable_reason or "After Effects 설치를 확인하지 못했습니다.")
        motion_path = request.output.with_suffix(".motion.json")
        script_path = request.output.with_suffix(".ae.jsx")
        project_path = request.output.with_suffix(".aep")
        motion_path.parent.mkdir(parents=True, exist_ok=True)
        emit("prepare_started", output=str(script_path), renderer=self.id)
        motion_path.write_text(json.dumps(_motion_payload(request), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        script_path.write_text(
            _build_script(motion_path, project_path, [cue.text for cue in request.cues]),
            encoding="utf-8",
        )
        emit("prepare_completed", artifact=str(script_path), renderer=self.id)
        return script_path
def _has_hangul(text: str) -> bool:
    return any(
        0xAC00 <= ord(character) <= 0xD7A3
        or 0x1100 <= ord(character) <= 0x11FF
        or 0x3130 <= ord(character) <= 0x318F
        for character in text
    )


def _text_font(cue) -> str | None:
    """After Effects needs a Korean font named for Hangul text.

    A text layer without an explicit font keeps the application default, which
    is not guaranteed to carry Hangul glyphs, so Korean copy names the Windows
    Korean font instead of silently rendering boxes.
    """
    if cue.font:
        return cue.font
    return "Malgun Gothic" if _has_hangul(cue.text) else None
