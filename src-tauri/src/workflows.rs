//! Registered generation workflows: what a canvas node can run, where it lives
//! and which inputs/outputs it declares.
//!
//! Two real workflows are seeded on first start: the verified H3 video workflow
//! and the YuE2 music workflow. A workflow is never marked `verified` by
//! registration alone.
use crate::database::{now_rfc3339, AppState};
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::State;

pub(crate) const STATUS_REGISTERED: &str = "registered";
pub(crate) const STATUS_VERIFIED: &str = "verified";

#[derive(Serialize, Clone)]
pub(crate) struct WorkflowRow {
    pub(crate) id: String,
    pub(crate) name: String,
    pub(crate) tool: String,
    pub(crate) location: Option<String>,
    pub(crate) status: String,
    pub(crate) inputs: Value,
    pub(crate) outputs: Value,
    pub(crate) notes: Option<String>,
    pub(crate) created_at: String,
    pub(crate) updated_at: String,
}

#[derive(Deserialize)]
pub(crate) struct WorkflowInput {
    pub(crate) id: Option<String>,
    pub(crate) name: String,
    pub(crate) tool: String,
    #[serde(default)]
    pub(crate) location: Option<String>,
    #[serde(default)]
    pub(crate) inputs: Option<Value>,
    #[serde(default)]
    pub(crate) outputs: Option<Value>,
    #[serde(default)]
    pub(crate) notes: Option<String>,
    #[serde(default)]
    pub(crate) status: Option<String>,
}

const WORKFLOW_COLUMNS: &str = "id, name, tool, location, status, inputs_json, outputs_json, \
     notes, created_at, updated_at";

fn map_workflow(row: &rusqlite::Row<'_>) -> rusqlite::Result<WorkflowRow> {
    let inputs_json: Option<String> = row.get(5)?;
    let outputs_json: Option<String> = row.get(6)?;
    Ok(WorkflowRow {
        id: row.get(0)?,
        name: row.get(1)?,
        tool: row.get(2)?,
        location: row.get(3)?,
        status: row.get(4)?,
        inputs: inputs_json
            .and_then(|text| serde_json::from_str(&text).ok())
            .unwrap_or_else(|| json!({})),
        outputs: outputs_json
            .and_then(|text| serde_json::from_str(&text).ok())
            .unwrap_or_else(|| json!({})),
        notes: row.get(7)?,
        created_at: row.get(8)?,
        updated_at: row.get(9)?,
    })
}

pub(crate) fn list_workflows(conn: &Connection) -> Result<Vec<WorkflowRow>, String> {
    let mut statement = conn
        .prepare(&format!(
            "SELECT {WORKFLOW_COLUMNS} FROM workflow_definitions ORDER BY created_at"
        ))
        .map_err(|error| error.to_string())?;
    let rows = statement
        .query_map([], |row| map_workflow(row))
        .map_err(|error| error.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|error| error.to_string())
}

pub(crate) fn get_workflow(conn: &Connection, id: &str) -> Result<WorkflowRow, String> {
    conn.query_row(
        &format!("SELECT {WORKFLOW_COLUMNS} FROM workflow_definitions WHERE id = ?1"),
        params![id],
        |row| map_workflow(row),
    )
    .map_err(|error| match error {
        rusqlite::Error::QueryReturnedNoRows => String::from("워크플로를 찾을 수 없습니다"),
        _ => error.to_string(),
    })
}

pub(crate) fn save_workflow(
    conn: &Connection,
    input: &WorkflowInput,
) -> Result<WorkflowRow, String> {
    let name = input.name.trim();
    if name.is_empty() {
        return Err(String::from("워크플로 이름을 입력하세요."));
    }
    let tool = input.tool.trim();
    if !matches!(tool, "modal-h3" | "yue2-music") {
        return Err(format!("아직 실행할 수 없는 워크플로 도구입니다: {tool}"));
    }
    let status = input.status.as_deref().unwrap_or(STATUS_REGISTERED);
    if !matches!(status, STATUS_REGISTERED | STATUS_VERIFIED) {
        return Err(format!("알 수 없는 상태입니다: {status}"));
    }
    let now = now_rfc3339();
    let inputs_json = input
        .inputs
        .clone()
        .unwrap_or_else(|| json!({}))
        .to_string();
    let outputs_json = input
        .outputs
        .clone()
        .unwrap_or_else(|| json!({}))
        .to_string();
    let id = match input
        .id
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        Some(existing) => {
            let changed = conn
                .execute(
                    "UPDATE workflow_definitions SET name = ?2, tool = ?3, location = ?4, status = ?5, \
                     inputs_json = ?6, outputs_json = ?7, notes = ?8, updated_at = ?9 WHERE id = ?1",
                    params![existing, name, tool, input.location, status, inputs_json, outputs_json, input.notes, now],
                )
                .map_err(|error| error.to_string())?;
            if changed == 0 {
                return Err(String::from("워크플로를 찾을 수 없습니다"));
            }
            existing.to_string()
        }
        None => {
            let id = format!(
                "wf_{}_{}",
                chrono::Utc::now().timestamp_millis(),
                crate::database::id_suffix()
            );
            conn.execute(
                "INSERT INTO workflow_definitions (id, name, tool, location, status, inputs_json, outputs_json, notes, created_at, updated_at) \
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?9)",
                params![id, name, tool, input.location, status, inputs_json, outputs_json, input.notes, now],
            )
            .map_err(|error| error.to_string())?;
            id
        }
    };
    get_workflow(conn, &id)
}

pub(crate) fn delete_workflow(conn: &Connection, id: &str) -> Result<(), String> {
    conn.execute(
        "DELETE FROM workflow_definitions WHERE id = ?1",
        params![id],
    )
    .map_err(|error| error.to_string())?;
    Ok(())
}

/// First start: the two workflows that actually exist in this deployment.
pub(crate) fn seed_default_workflows(conn: &Connection) -> rusqlite::Result<usize> {
    let existing: i64 = conn.query_row("SELECT COUNT(*) FROM workflow_definitions", [], |row| {
        row.get(0)
    })?;
    if existing > 0 {
        return Ok(0);
    }
    let now = now_rfc3339();
    let seeds = [
        (
            "wf_modal_h3",
            "H3 영상 생성 (T2V/FL2V/Ref2V)",
            "modal-h3",
            "modal:minimax-h3-latest-workflows",
            STATUS_VERIFIED,
            json!({"prompt": "text", "input_image": "image?", "seconds": "number", "width": "number", "height": "number", "seed": "number"}),
            json!({"video": "file"}),
            "네이티브 앱에서 FL2V 실실행으로 검증함",
        ),
        (
            "wf_yue2_music",
            "YuE2 음악 생성",
            "yue2-music",
            "modal:yue2-music",
            STATUS_REGISTERED,
            json!({"style": "text", "lyrics": "text?", "seed": "number"}),
            json!({"audio": "file"}),
            "입출력 형식이 다른 두 번째 워크플로. 앱에서의 실행 검증은 아직",
        ),
    ];
    for (id, name, tool, location, status, inputs, outputs, notes) in seeds {
        conn.execute(
            "INSERT OR IGNORE INTO workflow_definitions (id, name, tool, location, status, inputs_json, outputs_json, notes, created_at, updated_at) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?9)",
            params![id, name, tool, location, status, inputs.to_string(), outputs.to_string(), notes, now],
        )?;
    }
    Ok(2)
}

#[tauri::command]
pub(crate) fn workflow_list(state: State<AppState>) -> Result<Vec<WorkflowRow>, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    list_workflows(&conn)
}

#[tauri::command]
pub(crate) fn workflow_save(
    state: State<AppState>,
    input: WorkflowInput,
) -> Result<WorkflowRow, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    save_workflow(&conn, &input)
}

#[tauri::command]
pub(crate) fn workflow_delete(state: State<AppState>, workflow_id: String) -> Result<(), String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    delete_workflow(&conn, &workflow_id)
}
