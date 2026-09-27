//! Portable studio project export/import without authentication material.
use crate::database::{now_rfc3339, AppState};
use crate::studio;
use rusqlite::{params, Connection};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Component, Path, PathBuf};
use tauri::State;

const PROJECT_FORMAT: &str = "modal-gui.studio-project";
const MANIFEST_FORMAT: &str = "modal-gui.studio-manifest";

fn path_tag(path: &str) -> String {
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    for byte in path.as_bytes() {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
    format!("{:08x}", ((hash >> 32) as u32) ^ (hash as u32))
}

fn safe_file_name(path: &Path) -> String {
    path.file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("asset")
        .chars()
        .map(|character| {
            if character.is_control()
                || matches!(
                    character,
                    '<' | '>' | ':' | '"' | '/' | '\\' | '|' | '?' | '*'
                )
            {
                '_'
            } else {
                character
            }
        })
        .collect()
}

fn is_secret_key(key: &str) -> bool {
    let normalized: String = key
        .chars()
        .filter(|character| character.is_ascii_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect();
    matches!(
        normalized.as_str(),
        "auth"
            | "authref"
            | "authorization"
            | "token"
            | "tokens"
            | "accesstoken"
            | "refreshtoken"
            | "idtoken"
            | "credential"
            | "credentials"
            | "credentialref"
            | "apikey"
            | "secret"
            | "clientsecret"
            | "password"
            | "bearer"
    )
}

fn strip_secrets(value: &mut Value) {
    match value {
        Value::Object(object) => {
            object.retain(|key, _| !is_secret_key(key));
            for child in object.values_mut() {
                strip_secrets(child);
            }
        }
        Value::Array(items) => items.iter_mut().for_each(strip_secrets),
        // A tool node keeps its arguments as a JSON string. Secret keys inside
        // that text have to be removed too, or the export would carry a token
        // while still claiming `secrets_included: false`.
        Value::String(text) => {
            let trimmed = text.trim();
            if !(trimmed.starts_with('{') || trimmed.starts_with('[')) {
                return;
            }
            if let Ok(mut nested) = serde_json::from_str::<Value>(trimmed) {
                strip_secrets(&mut nested);
                if let Ok(serialized) = serde_json::to_string(&nested) {
                    *text = serialized;
                }
            }
        }
        _ => {}
    }
}

fn fonts_from_document(document: &Value) -> Vec<String> {
    let mut fonts = BTreeSet::new();
    if let Some(nodes) = document.get("nodes").and_then(Value::as_array) {
        for node in nodes {
            if let Some(config) = node.get("config").and_then(Value::as_object) {
                for key in ["font", "fontFamily", "font_family"] {
                    if let Some(font) = config
                        .get(key)
                        .and_then(Value::as_str)
                        .map(str::trim)
                        .filter(|font| !font.is_empty())
                    {
                        fonts.insert(font.to_string());
                    }
                }
            }
        }
    }
    fonts.into_iter().collect()
}

fn document_assets_mut(document: &mut Value) -> Result<&mut Vec<Value>, String> {
    document
        .get_mut("assets")
        .and_then(Value::as_array_mut)
        .ok_or_else(|| String::from("프로젝트 문서에 assets 배열이 없습니다."))
}

fn exported_asset_path(source_dir: &Path, relative: &str) -> Result<PathBuf, String> {
    let relative_path = Path::new(relative);
    if relative_path.is_absolute()
        || relative_path
            .components()
            .any(|component| !matches!(component, Component::Normal(_)))
    {
        return Err(String::from(
            "내보낸 소재 경로가 프로젝트 폴더를 벗어납니다.",
        ));
    }
    Ok(source_dir.join(relative_path))
}

/// Absolute Windows paths that appear anywhere inside a JSON value. Motion and
/// edit specs keep their clip and audio paths as plain strings, so an export
/// that only copies registered assets would leave those files behind.
fn absolute_paths(value: &Value, found: &mut Vec<String>) {
    match value {
        Value::String(text) => {
            let trimmed = text.trim();
            let bytes = trimmed.as_bytes();
            if bytes.len() > 3
                && bytes[0].is_ascii_alphabetic()
                && bytes[1] == b':'
                && (bytes[2] == b'\\' || bytes[2] == b'/')
            {
                found.push(trimmed.to_string());
            }
        }
        Value::Array(items) => {
            for item in items {
                absolute_paths(item, found);
            }
        }
        Value::Object(map) => {
            for item in map.values() {
                absolute_paths(item, found);
            }
        }
        _ => {}
    }
}

/// Rewrites absolute path strings whose file name matches a copied file. The
/// export writes the paths of the machine that exported, so matching by name
/// survives a different folder prefix (temp folders, another drive letter).
fn rewrite_paths_by_name(value: &mut Value, by_name: &BTreeMap<String, String>) {
    match value {
        Value::String(text) => {
            let trimmed = text.trim();
            let bytes = trimmed.as_bytes();
            let looks_absolute = bytes.len() > 3
                && bytes[0].is_ascii_alphabetic()
                && bytes[1] == b':'
                && (bytes[2] == b'\\' || bytes[2] == b'/');
            if !looks_absolute {
                return;
            }
            let file_name = trimmed
                .rsplit(['\\', '/'])
                .next()
                .unwrap_or_default()
                .to_lowercase();
            if let Some(replacement) = by_name.get(&file_name) {
                *text = replacement.clone();
            }
        }
        Value::Array(items) => {
            for item in items {
                rewrite_paths_by_name(item, by_name);
            }
        }
        Value::Object(map) => {
            for item in map.values_mut() {
                rewrite_paths_by_name(item, by_name);
            }
        }
        _ => {}
    }
}

fn is_text_asset(path: &Path) -> bool {
    path.extension()
        .and_then(|value| value.to_str())
        .map(|value| value.eq_ignore_ascii_case("json") || value.eq_ignore_ascii_case("jsx"))
        .unwrap_or(false)
}

/// Copies one exported file into the project's own asset folder.
fn copy_into_project(
    conn: &Connection,
    root: &Path,
    project_id: &str,
    source: &Path,
) -> Result<String, String> {
    let imported = studio::import_asset(conn, root, project_id, &source.to_string_lossy())?;
    Ok(imported.stored_path)
}

/// Rewrites the paths a copied spec still points at (export folder) to the
/// project folder copies, so the imported project is self-contained.
fn rewrite_asset_file(
    path: &Path,
    mapping: &BTreeMap<String, String>,
    by_name: &BTreeMap<String, String>,
) {
    let Ok(text) = std::fs::read_to_string(path) else {
        return;
    };
    if let Ok(mut value) = serde_json::from_str::<Value>(&text) {
        rewrite_paths(&mut value, mapping);
        rewrite_paths_by_name(&mut value, by_name);
        if let Ok(body) = serde_json::to_vec_pretty(&value) {
            let _ = std::fs::write(path, body);
        }
        return;
    }
    let mut updated = text;
    for (from, to) in mapping {
        if updated.contains(from.as_str()) {
            updated = updated.replace(from.as_str(), to.as_str());
        }
    }
    let _ = std::fs::write(path, updated);
}

fn rewrite_paths(value: &mut Value, mapping: &BTreeMap<String, String>) {
    match value {
        Value::String(text) => {
            if let Some(replacement) = mapping.get(text.trim()) {
                *text = replacement.clone();
            }
        }
        Value::Array(items) => {
            for item in items {
                rewrite_paths(item, mapping);
            }
        }
        Value::Object(map) => {
            for item in map.values_mut() {
                rewrite_paths(item, mapping);
            }
        }
        _ => {}
    }
}

pub(crate) fn export_project(
    conn: &Connection,
    project_id: &str,
    target_dir: &Path,
) -> Result<Value, String> {
    let project = studio::load_project(conn, project_id)?;
    std::fs::create_dir_all(target_dir).map_err(|error| error.to_string())?;
    let assets_dir = target_dir.join("assets");
    let mut document: Value = serde_json::from_str(&project.document_json)
        .map_err(|error| format!("프로젝트 문서를 읽지 못했습니다: {error}"))?;
    strip_secrets(&mut document);
    let fonts = fonts_from_document(&document);
    let mut manifest_assets = Vec::new();
    let mut referenced_files: Vec<Value> = Vec::new();
    let mut missing_assets = Vec::new();
    let mut files = vec![String::from("project.json"), String::from("manifest.json")];

    for asset in document_assets_mut(&mut document)? {
        let Some(object) = asset.as_object_mut() else {
            continue;
        };
        let stored_path = object
            .get("storedPath")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();
        if stored_path.trim().is_empty() {
            continue;
        }
        let source = Path::new(&stored_path);
        if !source.is_file() {
            missing_assets.push(stored_path);
            continue;
        }
        std::fs::create_dir_all(&assets_dir).map_err(|error| error.to_string())?;
        let hash = object
            .get("hash")
            .and_then(Value::as_str)
            .filter(|value| {
                value.len() >= 8 && value.as_bytes().iter().take(8).all(u8::is_ascii_hexdigit)
            })
            .map(|value| value[..8].to_string())
            .unwrap_or_else(|| path_tag(source.to_string_lossy().as_ref()));
        let relative = format!("assets/{}-{}", hash, safe_file_name(source));
        std::fs::copy(source, target_dir.join(Path::new(&relative)))
            .map_err(|error| format!("소재를 복사하지 못했습니다: {error}"))?;
        object.insert("storedPath".into(), Value::String(relative.clone()));
        files.push(relative.clone());
        manifest_assets.push(json!({
            "id": object.get("id").and_then(Value::as_str).unwrap_or_default(),
            "name": object.get("name").and_then(Value::as_str).unwrap_or_else(|| source.file_name().and_then(|value| value.to_str()).unwrap_or("asset")),
            "kind": object.get("kind").and_then(Value::as_str).unwrap_or("other"),
            "file": relative,
        }));

        // 구성(모션·편집 스펙) JSON은 클립·오디오를 문자열 경로로 들고 있다.
        // 그 파일들까지 함께 복사하고, 내보낸 사본의 경로로 바꿔 둔다.
        if source
            .extension()
            .map(|value| {
                value.eq_ignore_ascii_case("json") || value.eq_ignore_ascii_case("jsx")
            })
            .unwrap_or(false)
        {
            // JSON 구성은 구조를 유지한 채 경로를 바꾸고, AE 준비 스크립트는
            // 같은 경로 문자열을 그대로 치환한다.
            let is_json = source
                .extension()
                .map(|value| value.eq_ignore_ascii_case("json"))
                .unwrap_or(false);
            let mut spec = if is_json {
                match read_json(source) {
                    Ok(value) => value,
                    Err(_) => continue,
                }
            } else {
                match std::fs::read_to_string(source) {
                    Ok(text) => Value::String(text),
                    Err(_) => continue,
                }
            };
            {
                let mut paths = Vec::new();
                absolute_paths(&spec, &mut paths);
                let mut mapping = BTreeMap::new();
                for path in paths {
                    if mapping.contains_key(&path) {
                        continue;
                    }
                    let referenced = Path::new(&path);
                    if !referenced.is_file() {
                        continue;
                    }
                    let relative_reference =
                        format!("assets/{}-{}", path_tag(&path), safe_file_name(referenced));
                    let exported = target_dir.join(Path::new(&relative_reference));
                    if !exported.exists() {
                        std::fs::copy(referenced, &exported)
                            .map_err(|error| format!("참조 파일을 복사하지 못했습니다: {error}"))?;
                    }
                    files.push(relative_reference.clone());
                    referenced_files.push(json!({
                        "original": path,
                        "file": relative_reference,
                    }));
                    mapping.insert(path, exported.to_string_lossy().to_string());
                }
                if !mapping.is_empty() {
                    rewrite_paths(&mut spec, &mapping);
                    let body = if is_json {
                        serde_json::to_vec_pretty(&spec).map_err(|error| error.to_string())?
                    } else {
                        spec.as_str().unwrap_or_default().as_bytes().to_vec()
                    };
                    std::fs::write(target_dir.join(Path::new(&relative)), body)
                        .map_err(|error| error.to_string())?;
                }
            }
        }
    }

    let connections = conn
        .prepare("SELECT id, name, kind FROM connections ORDER BY name COLLATE NOCASE")
        .and_then(|mut statement| {
            statement.query_map([], |row| Ok(json!({"id": row.get::<_, String>(0)?, "name": row.get::<_, String>(1)?, "kind": row.get::<_, String>(2)?})))?
                .collect::<rusqlite::Result<Vec<_>>>()
        })
        .map_err(|error| error.to_string())?;
    let workflows = conn
        .prepare("SELECT id, name, tool, status FROM workflow_definitions ORDER BY name COLLATE NOCASE")
        .and_then(|mut statement| {
            statement.query_map([], |row| Ok(json!({"id": row.get::<_, String>(0)?, "name": row.get::<_, String>(1)?, "tool": row.get::<_, String>(2)?, "status": row.get::<_, String>(3)?})))?
                .collect::<rusqlite::Result<Vec<_>>>()
        })
        .map_err(|error| error.to_string())?;
    let project_json = json!({
        "format": PROJECT_FORMAT,
        "version": 1,
        "exported_at": now_rfc3339(),
        "name": project.name,
        "revision": project.revision,
        "document": document,
    });
    let manifest_json = json!({
        "format": MANIFEST_FORMAT,
        "version": 1,
        "app": "modal-gui",
        "secrets_included": false,
        "assets": manifest_assets,
        "referenced": referenced_files,
        "connections": connections,
        "workflows": workflows,
        "fonts": fonts,
    });
    std::fs::write(
        target_dir.join("project.json"),
        serde_json::to_vec_pretty(&project_json).map_err(|error| error.to_string())?,
    )
    .map_err(|error| error.to_string())?;
    std::fs::write(
        target_dir.join("manifest.json"),
        serde_json::to_vec_pretty(&manifest_json).map_err(|error| error.to_string())?,
    )
    .map_err(|error| error.to_string())?;
    Ok(json!({
        "dir": target_dir.to_string_lossy(),
        "asset_count": manifest_json["assets"].as_array().map(Vec::len).unwrap_or(0),
        "missing_assets": missing_assets,
        "files": files,
    }))
}

fn read_json(path: &Path) -> Result<Value, String> {
    let bytes = std::fs::read(path)
        .map_err(|error| format!("{} 파일을 읽지 못했습니다: {error}", path.display()))?;
    serde_json::from_slice(&bytes)
        .map_err(|error| format!("{} JSON을 읽지 못했습니다: {error}", path.display()))
}

fn require_format(value: &Value, expected: &str) -> Result<(), String> {
    if value.get("format").and_then(Value::as_str) != Some(expected)
        || value.get("version").and_then(Value::as_i64) != Some(1)
    {
        return Err(String::from("지원하지 않는 스튜디오 프로젝트 형식입니다."));
    }
    Ok(())
}

fn names_missing(conn: &Connection, table: &str, names: &[String]) -> Result<Vec<String>, String> {
    let sql = format!("SELECT EXISTS(SELECT 1 FROM {table} WHERE name = ?1 COLLATE NOCASE)");
    let mut missing = Vec::new();
    for name in names {
        let exists: i64 = conn
            .query_row(&sql, params![name], |row| row.get(0))
            .map_err(|error| error.to_string())?;
        if exists == 0 {
            missing.push(name.clone());
        }
    }
    Ok(missing)
}

fn manifest_names(manifest: &Value, key: &str) -> Vec<String> {
    manifest
        .get(key)
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|item| item.get("name").and_then(Value::as_str))
        .map(str::to_string)
        .collect()
}

/// Font names the renderer already knows how to resolve, mapped to the file
/// stems they can live under. Kept in step with the Python renderer's table so
/// an available font is never reported as missing on import.
pub(crate) fn font_file_candidates(font: &str) -> Vec<String> {
    let key: String = font
        .chars()
        .filter(|character| !character.is_whitespace())
        .flat_map(char::to_lowercase)
        .collect();
    match key.as_str() {
        "pretendard" | "pretendardbold" => vec![String::from("pretendard-bold"), String::from("pretendard")],
        "맑은고딕" | "malgungothic" | "malgun" => {
            vec![String::from("malgunbd"), String::from("malgun")]
        }
        "나눔고딕" | "nanumgothic" => vec![
            String::from("nanumgothicbold"),
            String::from("nanumgothic"),
        ],
        "arial" | "arialbold" => vec![String::from("arialbd"), String::from("arial")],
        "segoeui" | "segoeuibold" => vec![String::from("segoeuib"), String::from("segoeui")],
        _ => Vec::new(),
    }
}

fn font_is_available(font: &str, available: &BTreeSet<String>) -> bool {
    let lower = font.to_lowercase();
    if available.contains(&lower) {
        return true;
    }
    let compact: String = lower.chars().filter(|character| !character.is_whitespace()).collect();
    if compact.is_empty() {
        return false;
    }
    if available.contains(&compact) || available.iter().any(|stem| stem.contains(&compact)) {
        return true;
    }
    font_file_candidates(font)
        .iter()
        .any(|candidate| available.contains(candidate))
}

pub(crate) fn missing_fonts(fonts: &[String]) -> Vec<String> {
    let available: BTreeSet<String> = std::fs::read_dir("C:/Windows/Fonts")
        .into_iter()
        .flatten()
        .flatten()
        .filter_map(|entry| {
            entry
                .path()
                .file_stem()
                .and_then(|stem| stem.to_str())
                .map(|stem| stem.to_ascii_lowercase())
        })
        .collect();
    fonts
        .iter()
        .filter(|font| !font_is_available(font, &available))
        .cloned()
        .collect()
}

/// Exported files are copied into the new project's own folder, so the imported
/// project keeps working after the export folder is moved or deleted.
pub(crate) fn import_project(
    conn: &Connection,
    root: &Path,
    source_dir: &Path,
) -> Result<Value, String> {
    if !source_dir.is_dir() {
        return Err(format!("가져올 폴더를 찾을 수 없습니다: {}", source_dir.display()));
    }
    let source_dir = source_dir.to_path_buf();
    let project_json = read_json(&source_dir.join("project.json"))?;
    let manifest = read_json(&source_dir.join("manifest.json"))?;
    require_format(&project_json, PROJECT_FORMAT)?;
    require_format(&manifest, MANIFEST_FORMAT)?;
    let mut document = project_json
        .get("document")
        .cloned()
        .ok_or_else(|| String::from("project.json에 document가 없습니다."))?;
    strip_secrets(&mut document);
    let source_name = project_json
        .get("name")
        .and_then(Value::as_str)
        .unwrap_or("프로젝트");
    let name = format!("{source_name} (가져옴)");
    let project = studio::create_project(conn, &name, &document.to_string())?;

    // 내보낸 폴더의 파일을 프로젝트 폴더로 복사하고, 문서와 구성 JSON 안의
    // 경로를 새 위치로 바꾼다.
    let mut mapping: BTreeMap<String, String> = BTreeMap::new();
    let mut by_name: BTreeMap<String, String> = BTreeMap::new();
    let mut missing_assets: Vec<String> = Vec::new();
    let mut exported_assets: Vec<(usize, String)> = Vec::new();
    let mut copied_specs: Vec<String> = Vec::new();
    {
        let assets = document_assets_mut(&mut document)?;
        for (index, asset) in assets.iter_mut().enumerate() {
            let Some(object) = asset.as_object_mut() else {
                continue;
            };
            let Some(relative) = object
                .get("storedPath")
                .and_then(Value::as_str)
                .map(str::to_string)
            else {
                continue;
            };
            let exported = exported_asset_path(&source_dir, &relative)?;
            exported_assets.push((index, exported.to_string_lossy().to_string()));
        }
    }
    for (index, exported) in &exported_assets {
        let exported_path = Path::new(exported);
        let copied = copy_into_project(conn, root, &project.id, exported_path);
        match copied {
            Ok(stored_path) => {
                mapping.insert(exported.clone(), stored_path.clone());
                if let Some(name) = Path::new(exported).file_name().and_then(|value| value.to_str())
                {
                    by_name.insert(name.to_lowercase(), stored_path.clone());
                }
                if is_text_asset(Path::new(exported)) {
                    copied_specs.push(stored_path.clone());
                }
                if let Some(asset) = document_assets_mut(&mut document)?.get_mut(*index) {
                    if let Some(object) = asset.as_object_mut() {
                        object.insert("storedPath".into(), Value::String(stored_path));
                    }
                }
            }
            Err(_) => missing_assets.push(exported.clone()),
        }
    }
    // 구성 JSON·AE 스크립트가 참조하는 파일도 함께 복사하고 내용을 고친다.
    for entry in manifest
        .get("referenced")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
    {
        let Some(relative) = entry.get("file").and_then(Value::as_str) else {
            continue;
        };
        let exported = exported_asset_path(&source_dir, relative)?;
        if let Ok(stored_path) = copy_into_project(conn, root, &project.id, &exported) {
            if let Some(name) = exported.file_name().and_then(|value| value.to_str()) {
                by_name.insert(name.to_lowercase(), stored_path.clone());
            }
            mapping.insert(exported.to_string_lossy().to_string(), stored_path);
        }
    }
    if !mapping.is_empty() {
        for path in &copied_specs {
            rewrite_asset_file(Path::new(path), &mapping, &by_name);
        }
        studio::save_project(conn, &project.id, &project.name, &document.to_string())?;
    }
    let connection_names = manifest_names(&manifest, "connections");
    let workflow_names = manifest_names(&manifest, "workflows");
    let fonts: Vec<String> = manifest
        .get("fonts")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(str::to_string)
        .collect();
    Ok(json!({
        "project_id": project.id,
        "name": project.name,
        "missing": {
            "connections": names_missing(conn, "connections", &connection_names)?,
            "workflows": names_missing(conn, "workflow_definitions", &workflow_names)?,
            "fonts": missing_fonts(&fonts),
        }
    }))
}

#[tauri::command]
pub(crate) fn studio_export_project(
    state: State<AppState>,
    project_id: String,
    target_dir: String,
) -> Result<Value, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    export_project(&conn, &project_id, &PathBuf::from(target_dir))
}

#[tauri::command]
pub(crate) fn studio_import_project(
    state: State<AppState>,
    root: State<studio::StudioRoot>,
    source_dir: String,
) -> Result<Value, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    import_project(&conn, &root.0, &PathBuf::from(source_dir))
}
