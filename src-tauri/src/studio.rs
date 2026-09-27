//! Studio project and imported-asset persistence.
use crate::database::{now_rfc3339, AppState};
use rusqlite::{params, Connection, ErrorCode};
use serde::Serialize;
use serde_json::Value;
use std::io::Read;
use std::path::{Path, PathBuf};
use tauri::State;

#[derive(Serialize)]
pub(crate) struct StudioProjectSummary {
    pub(crate) id: String,
    pub(crate) name: String,
    pub(crate) revision: i64,
    pub(crate) node_count: i64,
    pub(crate) asset_count: i64,
    pub(crate) created_at: String,
    pub(crate) updated_at: String,
}

#[derive(Serialize)]
pub(crate) struct StudioProject {
    pub(crate) id: String,
    pub(crate) name: String,
    pub(crate) revision: i64,
    pub(crate) document_json: String,
    pub(crate) created_at: String,
    pub(crate) updated_at: String,
}

#[derive(Serialize)]
pub(crate) struct StudioSaveResult {
    pub(crate) id: String,
    pub(crate) revision: i64,
    pub(crate) updated_at: String,
}

#[derive(Serialize)]
pub(crate) struct StudioImportedAsset {
    pub(crate) file_name: String,
    pub(crate) stored_path: String,
    pub(crate) size_bytes: i64,
    pub(crate) hash: String,
    pub(crate) kind: String,
}

pub(crate) struct StudioRoot(pub(crate) PathBuf);

fn document_counts(document_json: &str) -> Result<(i64, i64), String> {
    let document: Value = serde_json::from_str(document_json).map_err(|_| {
        String::from("스튜디오 문서는 nodes 배열과 assets 배열을 가진 JSON 객체여야 합니다.")
    })?;
    let object = document.as_object().ok_or_else(|| {
        String::from("스튜디오 문서는 nodes 배열과 assets 배열을 가진 JSON 객체여야 합니다.")
    })?;
    let nodes = object
        .get("nodes")
        .and_then(Value::as_array)
        .ok_or_else(|| {
            String::from("스튜디오 문서는 nodes 배열과 assets 배열을 가진 JSON 객체여야 합니다.")
        })?;
    let assets = object
        .get("assets")
        .and_then(Value::as_array)
        .ok_or_else(|| {
            String::from("스튜디오 문서는 nodes 배열과 assets 배열을 가진 JSON 객체여야 합니다.")
        })?;
    Ok((nodes.len() as i64, assets.len() as i64))
}

pub(crate) fn list_projects(conn: &Connection) -> Result<Vec<StudioProjectSummary>, String> {
    let mut statement = conn
        .prepare(
            "SELECT id, name, revision, node_count, asset_count, created_at, updated_at \
             FROM studio_projects ORDER BY updated_at DESC",
        )
        .map_err(|error| error.to_string())?;
    let rows = statement
        .query_map([], |row| {
            Ok(StudioProjectSummary {
                id: row.get(0)?,
                name: row.get(1)?,
                revision: row.get(2)?,
                node_count: row.get(3)?,
                asset_count: row.get(4)?,
                created_at: row.get(5)?,
                updated_at: row.get(6)?,
            })
        })
        .map_err(|error| error.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|error| error.to_string())
}

pub(crate) fn create_project(
    conn: &Connection,
    name: &str,
    document_json: &str,
) -> Result<StudioProject, String> {
    let (node_count, asset_count) = document_counts(document_json)?;
    let transaction = conn
        .unchecked_transaction()
        .map_err(|error| error.to_string())?;
    let base_id = format!("prj_{}", chrono::Utc::now().timestamp_millis());
    let now = now_rfc3339();
    let mut suffix = 1;
    let id = loop {
        let candidate = if suffix == 1 {
            base_id.clone()
        } else {
            format!("{base_id}_{suffix}")
        };
        match transaction.execute(
            "INSERT INTO studio_projects \
             (id, name, revision, node_count, asset_count, created_at, updated_at) \
             VALUES (?1, ?2, 1, ?3, ?4, ?5, ?5)",
            params![candidate, name, node_count, asset_count, now],
        ) {
            Ok(_) => break candidate,
            Err(rusqlite::Error::SqliteFailure(error, _))
                if error.code == ErrorCode::ConstraintViolation =>
            {
                suffix += 1;
            }
            Err(error) => return Err(error.to_string()),
        }
    };
    transaction
        .execute(
            "INSERT INTO studio_project_revisions \
             (project_id, revision, document_json, created_at) VALUES (?1, 1, ?2, ?3)",
            params![id, document_json, now],
        )
        .map_err(|error| error.to_string())?;
    transaction.commit().map_err(|error| error.to_string())?;
    Ok(StudioProject {
        id,
        name: name.to_string(),
        revision: 1,
        document_json: document_json.to_string(),
        created_at: now.clone(),
        updated_at: now,
    })
}

pub(crate) fn load_project(conn: &Connection, project_id: &str) -> Result<StudioProject, String> {
    conn.query_row(
        "SELECT p.id, p.name, p.revision, r.document_json, p.created_at, p.updated_at \
         FROM studio_projects p JOIN studio_project_revisions r \
           ON r.project_id = p.id AND r.revision = p.revision \
         WHERE p.id = ?1",
        params![project_id],
        |row| {
            Ok(StudioProject {
                id: row.get(0)?,
                name: row.get(1)?,
                revision: row.get(2)?,
                document_json: row.get(3)?,
                created_at: row.get(4)?,
                updated_at: row.get(5)?,
            })
        },
    )
    .map_err(|error| match error {
        rusqlite::Error::QueryReturnedNoRows => String::from("프로젝트를 찾을 수 없습니다"),
        _ => error.to_string(),
    })
}

pub(crate) fn save_project(
    conn: &Connection,
    project_id: &str,
    name: &str,
    document_json: &str,
) -> Result<StudioSaveResult, String> {
    let (node_count, asset_count) = document_counts(document_json)?;
    let transaction = conn
        .unchecked_transaction()
        .map_err(|error| error.to_string())?;
    let revision = transaction
        .query_row(
            "SELECT revision FROM studio_projects WHERE id = ?1",
            params![project_id],
            |row| row.get::<_, i64>(0),
        )
        .map_err(|error| match error {
            rusqlite::Error::QueryReturnedNoRows => String::from("프로젝트를 찾을 수 없습니다"),
            _ => error.to_string(),
        })?
        + 1;
    let now = now_rfc3339();
    transaction
        .execute(
            "INSERT INTO studio_project_revisions \
             (project_id, revision, document_json, created_at) VALUES (?1, ?2, ?3, ?4)",
            params![project_id, revision, document_json, now],
        )
        .map_err(|error| error.to_string())?;
    transaction
        .execute(
            "UPDATE studio_projects SET name = ?2, revision = ?3, node_count = ?4, \
             asset_count = ?5, updated_at = ?6 WHERE id = ?1",
            params![project_id, name, revision, node_count, asset_count, now],
        )
        .map_err(|error| error.to_string())?;
    transaction.commit().map_err(|error| error.to_string())?;
    Ok(StudioSaveResult {
        id: project_id.to_string(),
        revision,
        updated_at: now,
    })
}

pub(crate) fn delete_project(conn: &Connection, project_id: &str) -> Result<(), String> {
    let transaction = conn
        .unchecked_transaction()
        .map_err(|error| error.to_string())?;
    transaction
        .execute(
            "DELETE FROM studio_assets WHERE project_id = ?1",
            params![project_id],
        )
        .map_err(|error| error.to_string())?;
    transaction
        .execute(
            "DELETE FROM studio_project_revisions WHERE project_id = ?1",
            params![project_id],
        )
        .map_err(|error| error.to_string())?;
    transaction
        .execute(
            "DELETE FROM studio_projects WHERE id = ?1",
            params![project_id],
        )
        .map_err(|error| error.to_string())?;
    transaction.commit().map_err(|error| error.to_string())
}

fn asset_kind(path: &Path) -> &'static str {
    match path
        .extension()
        .and_then(|value| value.to_str())
        .map(str::to_lowercase)
        .as_deref()
    {
        Some("png" | "jpg" | "jpeg" | "webp" | "gif" | "bmp" | "tif" | "tiff" | "avif") => "image",
        Some("mp4" | "mov" | "webm" | "mkv" | "avi" | "m4v") => "video",
        Some("wav" | "mp3" | "flac" | "m4a" | "aac" | "ogg") => "audio",
        _ => "other",
    }
}

fn sanitized_basename(path: &Path) -> Result<String, String> {
    let name = path
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or_else(|| String::from("가져올 파일 이름을 확인할 수 없습니다."))?;
    Ok(name
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
        .collect())
}

fn fnv1a_hash(path: &Path) -> Result<String, String> {
    let mut file = std::fs::File::open(path).map_err(|error| error.to_string())?;
    let mut hash = 0xcbf29ce484222325_u64;
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let read = file.read(&mut buffer).map_err(|error| error.to_string())?;
        if read == 0 {
            break;
        }
        for byte in &buffer[..read] {
            hash ^= u64::from(*byte);
            hash = hash.wrapping_mul(0x100000001b3);
        }
    }
    Ok(format!("{hash:016x}"))
}

pub(crate) fn import_asset(
    conn: &Connection,
    root: &Path,
    project_id: &str,
    source_path: &str,
) -> Result<StudioImportedAsset, String> {
    let source = Path::new(source_path);
    if !source.is_file() {
        return Err(String::from("가져올 원본 파일을 찾을 수 없습니다."));
    }
    let exists: i64 = conn
        .query_row(
            "SELECT EXISTS(SELECT 1 FROM studio_projects WHERE id = ?1)",
            params![project_id],
            |row| row.get(0),
        )
        .map_err(|error| error.to_string())?;
    if exists == 0 {
        return Err(String::from("프로젝트를 찾을 수 없습니다"));
    }

    let file_name = sanitized_basename(source)?;
    let hash = fnv1a_hash(source)?;
    let kind = asset_kind(source).to_string();
    let destination_dir = root.join(project_id).join("assets");
    std::fs::create_dir_all(&destination_dir).map_err(|error| error.to_string())?;
    let destination = destination_dir.join(format!("{hash}_{file_name}"));
    std::fs::copy(source, &destination).map_err(|error| error.to_string())?;
    let size_bytes = i64::try_from(
        std::fs::metadata(&destination)
            .map_err(|error| error.to_string())?
            .len(),
    )
    .map_err(|error| error.to_string())?;
    let stored_path = destination.to_string_lossy().to_string();
    conn.execute(
        "INSERT INTO studio_assets \
         (project_id, file_name, stored_path, size_bytes, hash, kind, created_at) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
        params![
            project_id,
            file_name,
            stored_path,
            size_bytes,
            hash,
            kind,
            now_rfc3339()
        ],
    )
    .map_err(|error| error.to_string())?;
    Ok(StudioImportedAsset {
        file_name,
        stored_path,
        size_bytes,
        hash,
        kind,
    })
}

#[tauri::command]
pub(crate) fn studio_list_projects(
    state: State<AppState>,
) -> Result<Vec<StudioProjectSummary>, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    list_projects(&conn)
}

#[tauri::command]
pub(crate) fn studio_create_project(
    state: State<AppState>,
    name: String,
    document_json: String,
) -> Result<StudioProject, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    create_project(&conn, &name, &document_json)
}

#[tauri::command]
pub(crate) fn studio_load_project(
    state: State<AppState>,
    project_id: String,
) -> Result<StudioProject, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    load_project(&conn, &project_id)
}

#[tauri::command]
pub(crate) fn studio_save_project(
    state: State<AppState>,
    project_id: String,
    name: String,
    document_json: String,
) -> Result<StudioSaveResult, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    save_project(&conn, &project_id, &name, &document_json)
}

#[tauri::command]
pub(crate) fn studio_delete_project(
    state: State<AppState>,
    project_id: String,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    delete_project(&conn, &project_id)
}

#[tauri::command]
pub(crate) fn studio_import_asset(
    state: State<AppState>,
    root: State<StudioRoot>,
    project_id: String,
    source_path: String,
) -> Result<StudioImportedAsset, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    import_asset(&conn, &root.0, &project_id, &source_path)
}

/// Lightweight existence/size check used when a tool result mentions a file.
/// The frontend only offers to register paths this command confirms.
#[derive(Serialize)]
pub(crate) struct PathProbe {
    pub(crate) exists: bool,
    pub(crate) is_file: bool,
    pub(crate) size_bytes: i64,
    pub(crate) kind: String,
}

#[tauri::command]
pub(crate) fn studio_probe_path(path: String) -> Result<PathProbe, String> {
    let candidate = Path::new(path.trim());
    let metadata = std::fs::metadata(candidate).ok();
    let is_file = metadata
        .as_ref()
        .map(|value| value.is_file())
        .unwrap_or(false);
    Ok(PathProbe {
        exists: metadata.is_some(),
        is_file,
        size_bytes: metadata
            .map(|value| i64::try_from(value.len()).unwrap_or(0))
            .unwrap_or(0),
        kind: asset_kind(candidate).to_string(),
    })
}
