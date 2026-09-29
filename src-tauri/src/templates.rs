//! Local-python video templates registered under `pipelines/` (제3조).
//!
//! `template_list` reads `pipelines/registry.json` plus each manifest so the canvas can offer
//! them by `id@version`. `template_render` writes the job JSON the template expects and spawns
//! `pipelines/<id>/<ver>/render.py`, forwarding its JSON-line events as `pipeline-event` with the
//! run id attached, exactly like the other local pipelines. Before running, the manifest's
//! recorded file hashes are checked so a changed candidate cannot run under an old version.
use crate::paths::repo_root;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use tauri::Emitter;

/// Python with rembg (BRIA / BiRefNet) available. A project-local venv is used unless
/// `MODAL_GUI_TEMPLATE_PYTHON` points to another compatible interpreter.

#[derive(Serialize, Clone)]
pub(crate) struct TemplateInfo {
    pub(crate) id: String,
    pub(crate) version: String,
    pub(crate) status: String,
    pub(crate) label: String,
    pub(crate) summary: String,
    pub(crate) tone: Option<String>,
    pub(crate) schema: Value,
    pub(crate) runnable: bool,
    pub(crate) unavailable_reason: Option<String>,
}

#[derive(Deserialize)]
pub(crate) struct TemplateRenderRequest {
    pub(crate) run_id: String,
    pub(crate) template: String,
    pub(crate) job: Value,
    pub(crate) output: String,
}

fn pipelines_root() -> PathBuf {
    repo_root().join("pipelines")
}

pub(crate) fn template_python() -> PathBuf {
    std::env::var("MODAL_GUI_TEMPLATE_PYTHON")
        .map(PathBuf::from)
        .unwrap_or_else(|_| repo_root().join(".venv").join("Scripts").join("python.exe"))
}

fn read_json(path: &Path) -> Result<Value, String> {
    let text = std::fs::read_to_string(path).map_err(|error| format!("{}: {error}", path.display()))?;
    serde_json::from_str(&text).map_err(|error| format!("{}: {error}", path.display()))
}

fn file_hash(path: &Path) -> Result<String, String> {
    let bytes = std::fs::read(path).map_err(|error| format!("{}: {error}", path.display()))?;
    Ok(format!("sha256:{:x}", Sha256::digest(&bytes)))
}

/// Every file hash in the manifest must match what is on disk. Paths are relative to the
/// version folder, or to `pipelines/` for shared files such as `_shared/motionkit.py`.
pub(crate) fn verify_manifest(folder: &Path, manifest: &Value) -> Result<(), String> {
    let files = manifest
        .get("files")
        .and_then(Value::as_object)
        .filter(|files| !files.is_empty())
        .ok_or_else(|| String::from("매니페스트에 파일 해시가 없습니다. pipelines/seal.py를 실행하세요."))?;
    for (name, expected) in files {
        let local = folder.join(name);
        let path = if local.exists() { local } else { pipelines_root().join(name) };
        let actual = file_hash(&path)?;
        if Some(actual.as_str()) != expected.as_str() {
            return Err(format!("{name} 파일이 매니페스트와 다릅니다. 새 버전을 만들거나 다시 봉인하세요."));
        }
    }
    Ok(())
}

/// Splits `id@version` and resolves the version folder under `pipelines/`.
pub(crate) fn resolve(template: &str) -> Result<(String, String, PathBuf), String> {
    let (id, version) = template
        .split_once('@')
        .ok_or_else(|| format!("템플릿은 id@version 형식이어야 합니다: {template}"))?;
    let valid = |part: &str| !part.is_empty() && part.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '.');
    if !valid(id) || !valid(version) || id.starts_with('_') {
        return Err(format!("잘못된 템플릿 이름입니다: {template}"));
    }
    Ok((id.to_string(), version.to_string(), pipelines_root().join(id).join(version)))
}

#[tauri::command]
pub(crate) fn template_list() -> Result<Vec<TemplateInfo>, String> {
    let registry = read_json(&pipelines_root().join("registry.json"))?;
    let python = template_python();
    let mut out = Vec::new();
    let pipelines = registry.get("pipelines").and_then(Value::as_object).cloned().unwrap_or_default();
    for (id, versions) in pipelines {
        for (version, entry) in versions.as_object().cloned().unwrap_or_default() {
            if entry.get("engine").and_then(Value::as_str) != Some("local-python") {
                continue;
            }
            let status = entry.get("status").and_then(Value::as_str).unwrap_or("draft").to_string();
            // 제3조 §5: draft는 개발자 설정에서만, deprecated/retired는 새 작업에 내지 않는다.
            if !matches!(status.as_str(), "candidate" | "released") {
                continue;
            }
            let folder = pipelines_root().join(&id).join(&version);
            let manifest = read_json(&folder.join("manifest.json"))?;
            let schema = manifest
                .get("schema")
                .and_then(Value::as_str)
                .map(|name| read_json(&folder.join(name)))
                .transpose()?
                .unwrap_or_else(|| json!({}));
            let unavailable_reason = if !python.exists() {
                Some(format!("템플릿 실행용 Python을 찾지 못했습니다: {}", python.display()))
            } else if let Err(error) = verify_manifest(&folder, &manifest) {
                Some(error)
            } else {
                None
            };
            out.push(TemplateInfo {
                id: id.clone(),
                version,
                status,
                label: manifest.get("label").and_then(Value::as_str).unwrap_or(&id).to_string(),
                summary: manifest.get("summary").and_then(Value::as_str).unwrap_or_default().to_string(),
                tone: manifest.get("tone").and_then(Value::as_str).map(str::to_string),
                schema,
                runnable: unavailable_reason.is_none(),
                unavailable_reason,
            });
        }
    }
    out.sort_by(|a, b| a.label.cmp(&b.label));
    Ok(out)
}

#[tauri::command]
pub(crate) fn template_render(app: tauri::AppHandle, request: TemplateRenderRequest) -> Result<(), String> {
    let (id, version, folder) = resolve(&request.template)?;
    let manifest = read_json(&folder.join("manifest.json"))?;
    verify_manifest(&folder, &manifest)?;
    let python = template_python();
    if !python.exists() {
        return Err(format!("템플릿 실행용 Python을 찾지 못했습니다: {}", python.display()));
    }
    let output = PathBuf::from(&request.output);
    let parent = output.parent().ok_or_else(|| String::from("출력 경로가 올바르지 않습니다."))?;
    std::fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    let mut job = request.job.clone();
    let object = job.as_object_mut().ok_or_else(|| String::from("템플릿 입력은 JSON 객체여야 합니다."))?;
    object.insert("output".into(), Value::String(request.output.clone()));
    let job_path = output.with_extension("job.json");
    std::fs::write(&job_path, serde_json::to_string_pretty(&job).map_err(|error| error.to_string())?)
        .map_err(|error| error.to_string())?;

    let mut child = Command::new(&python)
        .arg(folder.join("render.py"))
        .arg(&job_path)
        .arg("--cutout-python")
        .arg(&python)
        .current_dir(repo_root())
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUNBUFFERED", "1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|error| error.to_string())?;
    let stdout = child.stdout.take();
    let stderr = child.stderr.take();
    let run_id = request.run_id.clone();
    let pipeline = format!("{id}@{version}");
    thread::spawn(move || {
        if let Some(stdout) = stdout {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                let mut value = serde_json::from_str::<Value>(&line)
                    .unwrap_or_else(|_| json!({"type": "log", "message": line}));
                if let Some(object) = value.as_object_mut() {
                    object.insert("run_id".into(), Value::String(run_id.clone()));
                    object.entry("pipeline").or_insert(Value::String(pipeline.clone()));
                }
                crate::pipeline::persist_pipeline_outcome(&app, &value);
                let _ = app.emit("pipeline-event", value);
            }
        }
        let mut tail: Vec<String> = Vec::new();
        if let Some(stderr) = stderr {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                tail.push(line);
                if tail.len() > 20 {
                    tail.remove(0);
                }
            }
        }
        let ok = child.wait().map(|status| status.success()).unwrap_or(false);
        if !ok {
            let event = json!({
                "type": "failed", "run_id": run_id, "pipeline": pipeline,
                "message": "템플릿 렌더가 비정상 종료되었습니다.", "detail": tail.join("\n"),
            });
            crate::pipeline::persist_pipeline_outcome(&app, &event);
            let _ = app.emit("pipeline-event", event);
        }
        let _ = app.emit("pipeline-event", json!({"type": "process_exit", "run_id": run_id, "success": ok}));
    });
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolve_rejects_traversal_and_shared() {
        assert!(resolve("local-launch-spoof@1.0").is_ok());
        assert!(resolve("../etc@1.0").is_err());
        assert!(resolve("_shared@1.0").is_err());
        assert!(resolve("local-launch-spoof").is_err());
        assert!(resolve("a@1.0/../x").is_err());
    }

    #[test]
    fn registered_templates_verify_against_disk() {
        let list = template_list().expect("registry readable");
        let ids: Vec<String> = list.iter().map(|t| format!("{}@{}", t.id, t.version)).collect();
        assert!(ids.contains(&"local-launch-spoof@1.0".to_string()), "{ids:?}");
        assert!(ids.contains(&"local-freeze-cast@1.0".to_string()), "{ids:?}");
        for template in &list {
            let (_, _, folder) = resolve(&format!("{}@{}", template.id, template.version)).unwrap();
            let manifest = read_json(&folder.join("manifest.json")).unwrap();
            verify_manifest(&folder, &manifest).expect("sealed hashes match");
            assert!(template.schema.get("properties").is_some());
        }
    }

    /// End-to-end: the same python + render.py invocation template_render uses, on a job that
    /// differs from the golden one (photo + video cast, pastel palette). Slow (cutouts), so
    /// it only runs with `cargo test -- --ignored`.
    #[test]
    #[ignore]
    fn freeze_cast_renders_a_new_job() {
        let (_, _, folder) = resolve("local-freeze-cast@1.0").unwrap();
        let data_root = PathBuf::from(std::env::var("MODAL_GUI_DATA_ROOT").expect("set MODAL_GUI_DATA_ROOT for the ignored integration test"));
        let test_root = data_root.join("pipelines").join("local-freeze-cast").join("1.0");
        let job = test_root.join("golden-inputs").join("smoke-2cast.json");
        let out = test_root.join("release-check").join("smoke-2cast.mp4");
        let mut value = read_json(&job).unwrap();
        value["output"] = Value::String(out.display().to_string());
        let job_path = out.with_extension("job.json");
        std::fs::create_dir_all(out.parent().unwrap()).unwrap();
        std::fs::write(&job_path, serde_json::to_string(&value).unwrap()).unwrap();
        let python = template_python();
        let output = Command::new(&python)
            .arg(folder.join("render.py"))
            .arg(&job_path)
            .arg("--cutout-python")
            .arg(&python)
            .current_dir(repo_root())
            .env("PYTHONIOENCODING", "utf-8")
            .output()
            .unwrap();
        let stdout = String::from_utf8_lossy(&output.stdout);
        assert!(output.status.success(), "{stdout}\n{}", String::from_utf8_lossy(&output.stderr));
        let done = stdout
            .lines()
            .filter_map(|line| serde_json::from_str::<Value>(line).ok())
            .find(|event| event["type"] == "render_completed")
            .expect("render_completed event");
        assert_eq!(done["seconds"].as_f64(), Some(1.6 + 3.2 * 2.0 + 3.2));
        assert!(out.exists());
    }
}
