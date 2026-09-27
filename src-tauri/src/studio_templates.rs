//! Reusable studio documents stored independently from projects.
use crate::database::{id_suffix, now_rfc3339, AppState};
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::State;

#[derive(Serialize)]
pub(crate) struct StudioTemplateSummary {
    pub(crate) id: String,
    pub(crate) name: String,
    pub(crate) description: Option<String>,
    pub(crate) node_count: i64,
    /// 캔버스에 바로 놓을 수 있도록 목록에도 문서를 함께 돌려준다.
    pub(crate) document_json: String,
    pub(crate) created_at: String,
    pub(crate) updated_at: String,
}

#[derive(Serialize)]
pub(crate) struct StudioTemplateRow {
    pub(crate) id: String,
    pub(crate) name: String,
    pub(crate) description: Option<String>,
    pub(crate) document_json: String,
    pub(crate) created_at: String,
    pub(crate) updated_at: String,
}

#[derive(Deserialize)]
pub(crate) struct StudioTemplateInput {
    #[serde(default)]
    pub(crate) id: Option<String>,
    pub(crate) name: String,
    #[serde(default)]
    pub(crate) description: Option<String>,
    pub(crate) document_json: String,
}

fn validate_document(document_json: &str) -> Result<i64, String> {
    let document: Value = serde_json::from_str(document_json)
        .map_err(|_| String::from("템플릿 문서는 nodes 배열을 가진 JSON 객체여야 합니다."))?;
    document
        .as_object()
        .and_then(|object| object.get("nodes"))
        .and_then(Value::as_array)
        .map(|nodes| nodes.len() as i64)
        .ok_or_else(|| String::from("템플릿 문서는 nodes 배열을 가진 JSON 객체여야 합니다."))
}

fn get_template(conn: &Connection, id: &str) -> Result<StudioTemplateRow, String> {
    conn.query_row(
        "SELECT id, name, description, document_json, created_at, updated_at \
         FROM studio_templates WHERE id = ?1",
        params![id],
        |row| {
            Ok(StudioTemplateRow {
                id: row.get(0)?,
                name: row.get(1)?,
                description: row.get(2)?,
                document_json: row.get(3)?,
                created_at: row.get(4)?,
                updated_at: row.get(5)?,
            })
        },
    )
    .map_err(|error| match error {
        rusqlite::Error::QueryReturnedNoRows => String::from("템플릿을 찾을 수 없습니다."),
        _ => error.to_string(),
    })
}

pub(crate) fn list_templates(conn: &Connection) -> Result<Vec<StudioTemplateSummary>, String> {
    let mut statement = conn
        .prepare(
            "SELECT id, name, description, document_json, created_at, updated_at \
             FROM studio_templates ORDER BY updated_at DESC, rowid DESC",
        )
        .map_err(|error| error.to_string())?;
    let rows = statement
        .query_map([], |row| {
            let document_json: String = row.get(3)?;
            let node_count = serde_json::from_str::<Value>(&document_json)
                .ok()
                .and_then(|document| {
                    document
                        .get("nodes")
                        .and_then(Value::as_array)
                        .map(Vec::len)
                })
                .unwrap_or(0) as i64;
            Ok(StudioTemplateSummary {
                id: row.get(0)?,
                name: row.get(1)?,
                description: row.get(2)?,
                node_count,
                document_json,
                created_at: row.get(4)?,
                updated_at: row.get(5)?,
            })
        })
        .map_err(|error| error.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|error| error.to_string())
}

pub(crate) fn save_template(
    conn: &Connection,
    input: &StudioTemplateInput,
) -> Result<StudioTemplateRow, String> {
    let name = input.name.trim();
    if name.is_empty() {
        return Err(String::from("템플릿 이름을 입력하세요."));
    }
    validate_document(&input.document_json)?;
    let description = input
        .description
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty());
    let now = now_rfc3339();
    let id = if let Some(id) = input
        .id
        .as_deref()
        .map(str::trim)
        .filter(|id| !id.is_empty())
    {
        let changed = conn
            .execute(
                "UPDATE studio_templates SET name = ?2, description = ?3, document_json = ?4, \
                 updated_at = ?5 WHERE id = ?1",
                params![id, name, description, input.document_json, now],
            )
            .map_err(|error| error.to_string())?;
        if changed == 0 {
            return Err(String::from("템플릿을 찾을 수 없습니다."));
        }
        id.to_string()
    } else {
        let id = format!(
            "tpl_{}_{}",
            chrono::Utc::now().timestamp_millis(),
            id_suffix()
        );
        conn.execute(
            "INSERT INTO studio_templates \
             (id, name, description, document_json, created_at, updated_at) \
             VALUES (?1, ?2, ?3, ?4, ?5, ?5)",
            params![id, name, description, input.document_json, now],
        )
        .map_err(|error| error.to_string())?;
        id
    };
    get_template(conn, &id)
}

pub(crate) fn delete_template(conn: &Connection, template_id: &str) -> Result<(), String> {
    let changed = conn
        .execute(
            "DELETE FROM studio_templates WHERE id = ?1",
            params![template_id],
        )
        .map_err(|error| error.to_string())?;
    if changed == 0 {
        return Err(String::from("템플릿을 찾을 수 없습니다."));
    }
    Ok(())
}

#[tauri::command]
pub(crate) fn studio_template_list(
    state: State<AppState>,
) -> Result<Vec<StudioTemplateSummary>, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    list_templates(&conn)
}

#[tauri::command]
pub(crate) fn studio_template_save(
    state: State<AppState>,
    input: StudioTemplateInput,
) -> Result<StudioTemplateRow, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    save_template(&conn, &input)
}

#[tauri::command]
pub(crate) fn studio_template_delete(
    state: State<AppState>,
    template_id: String,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    delete_template(&conn, &template_id)
}
