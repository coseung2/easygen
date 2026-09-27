//! Studio node runs: one row per execution attempt from the canvas.
//!
//! Modal-backed runs keep a `jobs` row as well, so the queue, usage and cost
//! history stay in one place. Local runs (render pipeline) only need this table.
use crate::database::{now_rfc3339, AppState};
use crate::jobs::{self, NewJob, StartMode};
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::path::Path;
use tauri::State;

/// Run states follow section 12.1 of the studio design document.
pub(crate) const RUN_TERMINAL: &str = "('completed', 'prepared', 'failed', 'cancelled')";
const DUPLICATE_MESSAGE: &str =
    "같은 입력으로 이미 제출한 실행이 있습니다. 잠시 뒤에 다시 실행하거나 seed·입력을 바꿔 새 변주로 실행하세요.";

#[derive(Deserialize, Clone)]
pub(crate) struct StudioRunRequest {
    pub(crate) project_id: String,
    pub(crate) node_id: String,
    #[serde(default)]
    pub(crate) node_title: Option<String>,
    pub(crate) tool: String,
    #[serde(default)]
    pub(crate) prompt: String,
    #[serde(default)]
    pub(crate) input_path: Option<String>,
    #[serde(default)]
    pub(crate) duration: Option<i64>,
    #[serde(default)]
    pub(crate) width: Option<i64>,
    #[serde(default)]
    pub(crate) height: Option<i64>,
    #[serde(default)]
    pub(crate) seed: Option<i64>,
    #[serde(default)]
    pub(crate) profile_id: Option<String>,
    #[serde(default)]
    pub(crate) kind: Option<String>,
    #[serde(default)]
    pub(crate) style: Option<String>,
    #[serde(default)]
    pub(crate) lyrics: Option<String>,
    #[serde(default)]
    pub(crate) input_json: Option<String>,
}

#[derive(Serialize, Clone, Debug)]
pub(crate) struct StudioRunRow {
    pub(crate) id: String,
    pub(crate) project_id: String,
    pub(crate) node_id: String,
    pub(crate) node_title: Option<String>,
    pub(crate) tool: String,
    pub(crate) status: String,
    pub(crate) stage: Option<String>,
    pub(crate) job_id: Option<String>,
    pub(crate) output_path: Option<String>,
    pub(crate) result_asset_id: Option<String>,
    pub(crate) error_code: Option<String>,
    pub(crate) error_message: Option<String>,
    /// 취소·다운로드 실패 뒤에도 남는 원격 결과 위치. 다시 받을 때 쓴다.
    pub(crate) remote_output_path: Option<String>,
    pub(crate) created_at: String,
    pub(crate) updated_at: String,
}

const RUN_COLUMNS: &str = "id, project_id, node_id, node_title, tool, status, stage, job_id, \
     output_path, result_asset_id, error_code, error_message, remote_output_path, created_at, updated_at";

fn map_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<StudioRunRow> {
    Ok(StudioRunRow {
        id: row.get(0)?,
        project_id: row.get(1)?,
        node_id: row.get(2)?,
        node_title: row.get(3)?,
        tool: row.get(4)?,
        status: row.get(5)?,
        stage: row.get(6)?,
        job_id: row.get(7)?,
        output_path: row.get(8)?,
        result_asset_id: row.get(9)?,
        error_code: row.get(10)?,
        error_message: row.get(11)?,
        remote_output_path: row.get(12)?,
        created_at: row.get(13)?,
        updated_at: row.get(14)?,
    })
}

pub(crate) fn list_runs(conn: &Connection, project_id: &str) -> Result<Vec<StudioRunRow>, String> {
    let mut statement = conn
        .prepare(&format!(
            "SELECT {RUN_COLUMNS} FROM studio_runs WHERE project_id = ?1 \
             ORDER BY created_at DESC, rowid DESC LIMIT 300"
        ))
        .map_err(|error| error.to_string())?;
    let rows = statement
        .query_map(params![project_id], |row| map_row(row))
        .map_err(|error| error.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|error| error.to_string())
}

fn get_run(conn: &Connection, run_id: &str) -> Result<StudioRunRow, String> {
    conn.query_row(
        &format!("SELECT {RUN_COLUMNS} FROM studio_runs WHERE id = ?1"),
        params![run_id],
        |row| map_row(row),
    )
    .map_err(|error| match error {
        rusqlite::Error::QueryReturnedNoRows => String::from("실행 기록을 찾을 수 없습니다"),
        _ => error.to_string(),
    })
}

pub(crate) fn submission_key(request: &StudioRunRequest) -> String {
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    let input = request.input_json.as_deref().unwrap_or_default();
    let seed = request
        .seed
        .map(|value| value.to_string())
        .unwrap_or_default();
    for value in [
        request.project_id.as_str(),
        request.node_id.as_str(),
        request.tool.as_str(),
        input,
        seed.as_str(),
    ] {
        for byte in value.as_bytes() {
            hash ^= u64::from(*byte);
            hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
        }
    }
    format!("{:08x}", ((hash >> 32) as u32) ^ (hash as u32))
}

fn reject_duplicate(
    conn: &Connection,
    request: &StudioRunRequest,
    key: &str,
) -> Result<(), String> {
    let duplicate: i64 = conn
        .query_row(
            &format!(
                "SELECT EXISTS(SELECT 1 FROM studio_runs WHERE project_id = ?1 \
                 AND submission_key = ?2 AND (status NOT IN {RUN_TERMINAL} \
                 OR julianday(created_at) >= julianday('now', '-30 seconds')))"
            ),
            params![request.project_id, key],
            |row| row.get(0),
        )
        .map_err(|error| error.to_string())?;
    if duplicate == 1 {
        return Err(String::from(DUPLICATE_MESSAGE));
    }
    Ok(())
}

pub(crate) fn insert_run(
    conn: &Connection,
    run_id: &str,
    job_id: Option<&str>,
    request: &StudioRunRequest,
    status: &str,
) -> Result<(), String> {
    let now = now_rfc3339();
    let key = submission_key(request);
    reject_duplicate(conn, request, &key)?;
    conn.execute(
        "INSERT INTO studio_runs \
         (id, project_id, node_id, node_title, tool, status, stage, job_id, input_json, submission_key, created_at, updated_at) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, NULL, ?7, ?8, ?9, ?10, ?10)",
        params![
            run_id,
            request.project_id,
            request.node_id,
            request.node_title,
            request.tool.trim(),
            status,
            job_id,
            request.input_json,
            key,
            now
        ],
    )
    .map_err(|error| error.to_string())?;
    Ok(())
}

/// Mirrors one worker event onto the run that owns the job. Unknown job ids and
/// databases without the studio tables are ignored on purpose.
pub(crate) fn apply_run_event(conn: &Connection, event: &Value) -> Result<(), String> {
    let Some(job_id) = event
        .get("job_id")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
    else {
        return Ok(());
    };
    let event_type = event
        .get("type")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let stage = event.get("stage").and_then(Value::as_str);
    let output_path = event.get("local_output_path").and_then(Value::as_str);
    let remote_output_path = event.get("remote_output_path").and_then(Value::as_str);
    let error_code = event.get("code").and_then(Value::as_str);
    // 취소 뒤 원격 결과가 남아 있으면 그 위치를 함께 기록한다. 결과를 내려받지
    // 않았더라도 다시 받을 수 있는 경로를 잃지 않기 위해서다.
    let detail = match event_type {
        // 결과를 받은 실행에는 "내려받지 않았다"는 안내를 붙이지 않는다.
        "completed" | "prepared" => event
            .get("message")
            .and_then(Value::as_str)
            .map(str::to_string),
        _ => match (
            event.get("message").and_then(Value::as_str),
            event.get("remote_output_path").and_then(Value::as_str),
        ) {
            (Some(message), Some(path)) => Some(format!("{message} 원격 결과: {path}")),
            (Some(message), None) => Some(message.to_string()),
            (None, Some(path)) => {
                Some(format!("원격 결과를 내려받지 않았습니다. 원격 경로: {path}"))
            }
            (None, None) => None,
        },
    };

    let (status, stage_value) = match event_type {
        "completed" => (Some("completed"), Some("completed")),
        "failed" => (Some("failed"), stage),
        "cancelled" => (Some("cancelled"), stage),
        "remote_attached" => (Some("running"), None),
        "stage" => {
            let value = stage.unwrap_or_default();
            let status = if value == "RESULT_DOWNLOADING" || value == "AUDIO_DOWNLOADING" {
                "downloading"
            } else {
                "running"
            };
            (Some(status), stage)
        }
        _ => (None, stage),
    };
    if status.is_none() && stage_value.is_none() && output_path.is_none() {
        return Ok(());
    }

    let _ = conn.execute(
        &format!(
            "UPDATE studio_runs SET status = COALESCE(?2, status), stage = COALESCE(?3, stage), \
         output_path = COALESCE(?4, output_path), error_code = COALESCE(?5, error_code), \
         error_message = COALESCE(?6, error_message), remote_output_path = COALESCE(?7, remote_output_path), \
         updated_at = ?8 \
         WHERE job_id = ?1 AND status NOT IN {RUN_TERMINAL}"
        ),
        params![
            job_id,
            status,
            stage_value,
            output_path,
            error_code,
            detail,
            remote_output_path,
            now_rfc3339()
        ],
    );
    Ok(())
}

/// A worker that dies without a terminal event must not leave a run spinning.
pub(crate) fn mark_run_worker_exit(conn: &Connection, job_id: &str, code: Option<i32>) {
    let _ = conn.execute(
        &format!(
            "UPDATE studio_runs SET status = 'failed', error_code = 'WORKER_EXITED', \
             error_message = ?2, updated_at = ?3 \
             WHERE job_id = ?1 AND status NOT IN {RUN_TERMINAL}"
        ),
        params![
            job_id,
            format!("worker가 비정상 종료했습니다 (exit code {:?})", code),
            now_rfc3339()
        ],
    );
}

/// Startup recovery for runs this process cannot continue: the worker and the
/// local pipeline are children of the previous app process. Modal jobs are
/// already closed by `fail_interrupted_jobs`; this keeps the canvas honest too.
pub(crate) fn fail_interrupted_runs(conn: &Connection) -> rusqlite::Result<usize> {
    // A cancel request that never got a remote answer is not the same fact as a
    // confirmed cancel: the remote work may have finished. The run closes as
    // cancelled, and the note says which part stayed unconfirmed.
    let cancelled = conn.execute(
        "UPDATE studio_runs SET status = 'cancelled', stage = 'cancelled', \
         error_message = '앱이 다시 시작되어 원격 취소 결과를 확인하지 못했습니다. 원격 작업은 계속됐을 수 있습니다.', \
         updated_at = ?1 \
         WHERE status = 'cancel_requested'",
        params![now_rfc3339()],
    )?;
    let failed = conn.execute(
        &format!(
            "UPDATE studio_runs SET status = 'failed', error_code = 'INTERRUPTED_BY_RESTART', \
             error_message = '앱이 다시 시작되어 중단된 실행입니다. 다시 실행해 주세요.', \
             updated_at = ?1 WHERE status NOT IN {RUN_TERMINAL}"
        ),
        params![now_rfc3339()],
    )?;
    Ok(cancelled + failed)
}

pub(crate) fn cancel_run(
    conn: &Connection,
    run_id: &str,
    has_live_worker: bool,
) -> Result<StudioRunRow, String> {
    let run = get_run(conn, run_id)?;
    if matches!(
        run.status.as_str(),
        "completed" | "prepared" | "failed" | "cancelled"
    ) {
        return Err(String::from("이미 끝난 실행은 취소할 수 없습니다."));
    }
    let note = if has_live_worker {
        None
    } else if run.job_id.is_some() {
        Some("원격 실행 상태를 확인할 수 없습니다. 앱을 다시 시작하면 중단으로 기록됩니다.")
    } else {
        Some("이 실행 도구는 원격 취소를 지원하지 않습니다. 완료되면 결과가 기록됩니다.")
    };
    conn.execute(
        "UPDATE studio_runs SET status = 'cancel_requested', stage = 'cancel_requested', \
         error_message = COALESCE(?2, error_message), updated_at = ?3 WHERE id = ?1",
        params![run_id, note, now_rfc3339()],
    )
    .map_err(|error| error.to_string())?;
    get_run(conn, run_id)
}

pub(crate) fn finish_run(
    conn: &Connection,
    run_id: &str,
    status: &str,
    output_path: Option<&str>,
    error_message: Option<&str>,
    result_asset_id: Option<&str>,
) -> Result<StudioRunRow, String> {
    if !matches!(
        status,
        "running" | "completed" | "prepared" | "failed" | "cancelled"
    ) {
        return Err(format!("알 수 없는 실행 상태입니다: {status}"));
    }
    if matches!(status, "completed" | "prepared") {
        let path = output_path
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| String::from("완료로 기록하려면 결과 파일 경로가 필요합니다."))?;
        if !Path::new(path).is_file() {
            return Err(format!("결과 파일을 찾을 수 없습니다: {path}"));
        }
    }
    // A result that arrives after a cancel request keeps both facts: the run is
    // finished, and the user had asked to stop it. The caller does not have to
    // remember the request — the stored state is the authority.
    let message = match error_message {
        Some(value) => Some(value.to_string()),
        None => {
            let previous: Option<String> = conn
                .query_row(
                    "SELECT status FROM studio_runs WHERE id = ?1",
                    params![run_id],
                    |row| row.get(0),
                )
                .ok();
            match previous.as_deref() {
                Some("cancel_requested") if matches!(status, "completed" | "prepared") => Some(
                    String::from("중단을 요청한 뒤 도착한 결과입니다. 결과 파일은 보관했습니다."),
                ),
                _ => None,
            }
        }
    };
    let changed = conn
        .execute(
            "UPDATE studio_runs SET status = ?2, \
             output_path = COALESCE(?3, output_path), \
             error_message = COALESCE(?4, error_message), \
             result_asset_id = COALESCE(?5, result_asset_id), \
             stage = CASE WHEN ?2 IN ('completed', 'prepared') THEN ?2 ELSE stage END, \
             updated_at = ?6 WHERE id = ?1",
            params![
                run_id,
                status,
                output_path,
                message,
                result_asset_id,
                now_rfc3339()
            ],
        )
        .map_err(|error| error.to_string())?;
    if changed == 0 {
        return Err(String::from("실행 기록을 찾을 수 없습니다"));
    }
    get_run(conn, run_id)
}

/// Builds the worker payload for a canvas node. Kept pure so the mapping from
/// node settings to the existing job pipeline is covered by tests.
pub(crate) fn build_job(
    request: &StudioRunRequest,
    job_id: &str,
) -> Result<(NewJob, StartMode), String> {
    let studio_project_id = Some(request.project_id.clone());
    let studio_node_id = Some(request.node_id.clone());
    match request.tool.trim() {
        "modal-h3" => {
            let prompt = request.prompt.trim();
            if prompt.is_empty() {
                return Err(String::from("프롬프트를 입력하세요."));
            }
            let input_path = request
                .input_path
                .clone()
                .map(|value| value.trim().to_string())
                .filter(|value| !value.is_empty());
            let kind = request
                .kind
                .clone()
                .filter(|value| !value.trim().is_empty())
                .unwrap_or_else(|| {
                    if input_path.is_some() {
                        String::from("fl2v")
                    } else {
                        String::from("t2v")
                    }
                });
            if kind != "t2v" {
                let path = input_path
                    .as_deref()
                    .ok_or_else(|| String::from("시작 프레임 이미지를 노드에 연결하세요."))?;
                if !Path::new(path).is_file() {
                    return Err(format!("입력 이미지를 찾을 수 없습니다: {path}"));
                }
            }
            let width = request.width.unwrap_or(1344).clamp(64, 4096);
            let height = request.height.unwrap_or(768).clamp(64, 4096);
            Ok((
                NewJob {
                    id: job_id.to_string(),
                    prompt: prompt.to_string(),
                    input_path: input_path.unwrap_or_default(),
                    duration: request.duration.unwrap_or(5).clamp(1, 60),
                    resolution: format!("{width}×{height}"),
                    kind: Some(kind),
                    profile_id: request.profile_id.clone(),
                    width: Some(width),
                    height: Some(height),
                    seed: request.seed,
                    style: None,
                    lyrics: None,
                    studio_project_id,
                    studio_node_id,
                },
                StartMode::Video,
            ))
        }
        "yue2-music" => {
            let style = request
                .style
                .clone()
                .or_else(|| Some(request.prompt.clone()))
                .map(|value| value.trim().to_string())
                .filter(|value| !value.is_empty())
                .ok_or_else(|| String::from("음악 스타일을 입력하세요."))?;
            Ok((
                NewJob {
                    id: job_id.to_string(),
                    prompt: style.clone(),
                    input_path: String::new(),
                    duration: request.duration.unwrap_or(60).clamp(10, 300),
                    resolution: String::from("48 kHz stereo"),
                    kind: Some(String::from("music")),
                    profile_id: request.profile_id.clone(),
                    width: None,
                    height: None,
                    seed: request.seed,
                    style: Some(style),
                    lyrics: request.lyrics.clone(),
                    studio_project_id,
                    studio_node_id,
                },
                StartMode::Music,
            ))
        }
        other => Err(format!("이 실행 도구는 아직 연결되지 않았습니다: {other}")),
    }
}

fn project_exists(conn: &Connection, project_id: &str) -> Result<bool, String> {
    conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM studio_projects WHERE id = ?1)",
        params![project_id],
        |row| row.get::<_, i64>(0),
    )
    .map(|value| value == 1)
    .map_err(|error| error.to_string())
}

/// 다시 내려받을 수 있는 원격 결과가 있는 실행인지 확인하고, worker에 보낼
/// `fetch_result` 메시지를 만든다. 다운로드만 실패했거나 취소된 실행은
/// 생성부터 다시 하지 않고 결과 수신부터 복구한다.
pub(crate) fn prepare_retry_download(
    conn: &Connection,
    run_id: &str,
) -> Result<(StudioRunRow, Value, Option<String>), String> {
    let run = get_run(conn, run_id)?;
    let remote = run
        .remote_output_path
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| {
            String::from("이 실행에는 다시 받을 원격 결과가 없습니다. 생성부터 다시 실행하세요.")
        })?;
    let job_id = run
        .job_id
        .clone()
        .ok_or_else(|| String::from("원격 실행 기록이 없습니다. 생성부터 다시 실행하세요."))?;
    let kind = if run.tool == "yue2-music" {
        "music"
    } else {
        "video"
    };
    let profile: Option<String> = conn
        .query_row(
            "SELECT p.modal_profile_name FROM jobs j \
             LEFT JOIN modal_profiles p ON p.id = j.modal_profile_id WHERE j.id = ?1",
            params![job_id],
            |row| row.get(0),
        )
        .ok()
        .flatten();
    conn.execute(
        "UPDATE studio_runs SET status = 'downloading', stage = 'RESULT_DOWNLOADING', \
         error_message = NULL, updated_at = ?2 WHERE id = ?1",
        params![run_id, now_rfc3339()],
    )
    .map_err(|error| error.to_string())?;
    let updated = get_run(conn, run_id)?;
    let message = json!({
        "type": "fetch_result",
        "job_id": job_id,
        "remote_output_path": remote,
        "kind": kind,
    });
    Ok((updated, message, profile))
}

#[tauri::command]
pub(crate) fn studio_retry_download(
    app: tauri::AppHandle,
    state: State<AppState>,
    run_id: String,
) -> Result<StudioRunRow, String> {
    let (run, message, profile) = {
        let conn = state.0.lock().map_err(|error| error.to_string())?;
        prepare_retry_download(&conn, &run_id)?
    };
    if let Err(error) = jobs::spawn_worker_message(app, message, profile.as_deref()) {
        let conn = state.0.lock().map_err(|lock| lock.to_string())?;
        let _ = finish_run(&conn, &run_id, "failed", None, Some(&error), None);
        return Err(error);
    }
    Ok(run)
}

#[tauri::command]
pub(crate) fn studio_start_node_run(
    app: tauri::AppHandle,
    state: State<AppState>,
    request: StudioRunRequest,
) -> Result<StudioRunRow, String> {
    let stamp = chrono::Utc::now().timestamp_millis();
    let suffix = crate::database::id_suffix();
    let run_id = format!("run_{stamp}_{suffix}");
    let job_id = format!("job_{stamp}_{suffix}");
    let (job, mode) = build_job(&request, &job_id)?;
    {
        let conn = state.0.lock().map_err(|error| error.to_string())?;
        if !project_exists(&conn, &request.project_id)? {
            return Err(String::from("프로젝트를 찾을 수 없습니다"));
        }
        let transaction = conn
            .unchecked_transaction()
            .map_err(|error| error.to_string())?;
        jobs::create_job_row(&transaction, &job)?;
        insert_run(&transaction, &run_id, Some(&job_id), &request, "queued")?;
        transaction.commit().map_err(|error| error.to_string())?;
    }
    if let Err(error) = jobs::start_job_inner(app, &state, job, mode) {
        let conn = state
            .0
            .lock()
            .map_err(|lock_error| lock_error.to_string())?;
        let _ = finish_run(&conn, &run_id, "failed", None, Some(&error), None);
        return Err(error);
    }
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    get_run(&conn, &run_id)
}

/// Local (non-Modal) runs such as the FFmpeg render pipeline.
#[tauri::command]
pub(crate) fn studio_start_local_run(
    state: State<AppState>,
    request: StudioRunRequest,
) -> Result<StudioRunRow, String> {
    let run_id = format!(
        "run_{}_{}",
        chrono::Utc::now().timestamp_millis(),
        crate::database::id_suffix()
    );
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    if !project_exists(&conn, &request.project_id)? {
        return Err(String::from("프로젝트를 찾을 수 없습니다"));
    }
    insert_run(&conn, &run_id, None, &request, "running")?;
    get_run(&conn, &run_id)
}

/// Used by frontend-driven runs (local renders) to record how they ended. The
/// backend still checks that a completed run points at a real file.
#[tauri::command]
pub(crate) fn studio_finish_node_run(
    state: State<AppState>,
    run_id: String,
    status: String,
    output_path: Option<String>,
    error_message: Option<String>,
    result_asset_id: Option<String>,
) -> Result<StudioRunRow, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    finish_run(
        &conn,
        &run_id,
        &status,
        output_path.as_deref(),
        error_message.as_deref(),
        result_asset_id.as_deref(),
    )
}

#[tauri::command]
pub(crate) fn studio_list_node_runs(
    state: State<AppState>,
    project_id: String,
) -> Result<Vec<StudioRunRow>, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    list_runs(&conn, &project_id)
}

#[tauri::command]
pub(crate) fn studio_cancel_run(
    state: State<AppState>,
    run_id: String,
) -> Result<StudioRunRow, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    let run = get_run(&conn, &run_id)?;
    if matches!(
        run.status.as_str(),
        "completed" | "prepared" | "failed" | "cancelled"
    ) {
        return Err(String::from("이미 끝난 실행은 취소할 수 없습니다."));
    }
    let live = match run.job_id.as_deref() {
        Some(job_id) => jobs::cancel_live_worker(job_id)?,
        None => false,
    };
    cancel_run(&conn, &run_id, live)
}
