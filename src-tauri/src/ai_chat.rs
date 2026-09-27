//! Codex app-server client: ChatGPT-account conversations from the app core.
//!
//! The host owns the OAuth tokens (see `chatgpt_auth`) and hands them to a
//! per-account app-server process with `account/login/start`
//! (`chatgptAuthTokens`). When the runtime asks for new tokens through the
//! `account/chatgptAuthTokens/refresh` server request, this module answers from
//! the stored account, so the runtime never reads the developer's Codex login.
//!
//! Conversations and messages live in `conversations`/`messages`; the frontend
//! only ever sees account metadata, never an access token.
use crate::chatgpt_auth::{self, SecretsRoot};
use crate::database::{now_rfc3339, AppState};
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{Emitter, Manager};

const DEFAULT_TIMEOUT: Duration = Duration::from_secs(180);
/// 세션 준비(initialize/login/thread)는 빨리 실패해야 한다.
const SETUP_TIMEOUT: Duration = Duration::from_secs(20);
const INTERRUPT_TIMEOUT: Duration = Duration::from_secs(30);

pub(crate) type EventSink = Arc<dyn Fn(Value) + Send + Sync>;
pub(crate) type RefreshHandler = Arc<dyn Fn(Value) -> Value + Send + Sync>;

fn binary() -> String {
    codex_launch().0
}

fn binary_args() -> Vec<String> {
    let mut args = codex_launch().1;
    args.extend(match std::env::var("MODAL_GUI_CODEX_ARGS") {
        Ok(value) if !value.trim().is_empty() => {
            value.split_whitespace().map(str::to_string).collect()
        }
        _ => vec![String::from("app-server")],
    });
    args
}

/// The program and base arguments that start the Codex app-server.
///
/// `npm i -g @openai/codex` installs `codex.cmd` (and a shell script), and
/// CreateProcess cannot run a batch shim, so the shim has to go through
/// `cmd /C`. A native `codex.exe` on PATH is preferred when it exists.
fn codex_launch() -> (String, Vec<String>) {
    if let Ok(value) = std::env::var("MODAL_GUI_CODEX_BIN") {
        if !value.trim().is_empty() {
            return (value, Vec::new());
        }
    }
    let path = std::env::var("PATH").unwrap_or_default();
    let mut shim: Option<String> = None;
    for entry in path.split(';').map(str::trim).filter(|item| !item.is_empty()) {
        let dir = std::path::Path::new(entry.trim_matches('"'));
        let exe = dir.join("codex.exe");
        if exe.is_file() {
            return (exe.to_string_lossy().to_string(), Vec::new());
        }
        if shim.is_none() {
            for name in ["codex.cmd", "codex.bat"] {
                let candidate = dir.join(name);
                if candidate.is_file() {
                    shim = Some(candidate.to_string_lossy().to_string());
                }
            }
        }
    }
    match shim {
        Some(command) => (String::from("cmd"), vec![String::from("/C"), command]),
        None => (String::from("codex"), Vec::new()),
    }
}

/// A project asset the user attached to one chat message.
#[derive(Deserialize, Clone)]
pub(crate) struct ChatAttachment {
    pub path: String,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub kind: Option<String>,
}

/// What actually happened to one attachment, reported back to the UI so the
/// message shows the difference between an uploaded image and a name-only note.
#[derive(Serialize, Clone)]
pub(crate) struct ChatAttachmentDelivery {
    /// The asset path the frontend asked for, so two attachments with the same
    /// display name keep their own delivery result.
    pub path: String,
    pub name: String,
    pub delivered: bool,
    pub note: Option<String>,
}

fn is_image(path: &str) -> bool {
    matches_extension(
        path,
        &["png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff", "avif"],
    )
}

fn is_audio(path: &str) -> bool {
    matches_extension(path, &["wav", "mp3", "flac", "m4a", "aac", "ogg"])
}

fn matches_extension(path: &str, extensions: &[&str]) -> bool {
    let extension = std::path::Path::new(path)
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or_default()
        .to_ascii_lowercase();
    extensions.contains(&extension.as_str())
}

pub(crate) struct AppServer {
    child: Mutex<Child>,
    writer: Arc<Mutex<ChildStdin>>,
    next_id: AtomicI64,
    pending: Arc<Mutex<HashMap<i64, Sender<Value>>>>,
    /// One model thread per conversation. A single thread per account mixed the
    /// context of every project and node the user was working on.
    threads: Mutex<HashMap<String, String>>,
}

impl AppServer {
    pub(crate) fn spawn_with(
        binary: &str,
        args: &[String],
        sink: EventSink,
        refresh: RefreshHandler,
    ) -> Result<Arc<AppServer>, String> {
        let mut child = Command::new(binary)
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|error| format!("Codex app-server를 실행하지 못했습니다: {error}"))?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| String::from("app-server stdin을 열지 못했습니다."))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| String::from("app-server stdout을 열지 못했습니다."))?;
        let writer = Arc::new(Mutex::new(stdin));
        let pending: Arc<Mutex<HashMap<i64, Sender<Value>>>> = Arc::new(Mutex::new(HashMap::new()));
        let reader_pending = Arc::clone(&pending);
        let reader_writer = Arc::clone(&writer);
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines().flatten() {
                let Ok(value) = serde_json::from_str::<Value>(&line) else {
                    continue;
                };
                let has_id = value.get("id").is_some();
                let is_response = value.get("result").is_some() || value.get("error").is_some();
                if has_id && is_response && value.get("method").is_none() {
                    if let Some(id) = value.get("id").and_then(Value::as_i64) {
                        if let Ok(mut map) = reader_pending.lock() {
                            if let Some(sender) = map.remove(&id) {
                                let _ = sender.send(value);
                            }
                        }
                    }
                    continue;
                }
                if let Some(method) = value.get("method").and_then(Value::as_str) {
                    if has_id {
                        // Server -> client request (for example a token refresh).
                        let id = value.get("id").cloned().unwrap_or(Value::Null);
                        let mut payload = if method == "account/chatgptAuthTokens/refresh" {
                            refresh(value.get("params").cloned().unwrap_or(Value::Null))
                        } else {
                            json!({"error": {"code": -32601, "message": format!("지원하지 않는 서버 요청: {method}")}})
                        };
                        if let Some(object) = payload.as_object_mut() {
                            object.insert(String::from("id"), id);
                        }
                        if let Ok(mut writer) = reader_writer.lock() {
                            let _ = writeln!(writer, "{payload}");
                            let _ = writer.flush();
                        }
                        continue;
                    }
                    sink(value);
                }
            }
        });
        Ok(Arc::new(AppServer {
            child: Mutex::new(child),
            writer,
            next_id: AtomicI64::new(1),
            pending,
        threads: Mutex::new(HashMap::new()),
        }))
    }

    pub(crate) fn write_message(&self, value: &Value) -> Result<(), String> {
        let mut writer = self.writer.lock().map_err(|error| error.to_string())?;
        writeln!(writer, "{value}").map_err(|error| error.to_string())?;
        writer.flush().map_err(|error| error.to_string())
    }

    pub(crate) fn request(
        &self,
        method: &str,
        params: Value,
        timeout: Duration,
    ) -> Result<Value, String> {
        let id = self.next_id.fetch_add(1, Ordering::SeqCst);
        let (sender, receiver) = mpsc::channel();
        self.pending
            .lock()
            .map_err(|error| error.to_string())?
            .insert(id, sender);
        self.write_message(
            &json!({"jsonrpc": "2.0", "id": id, "method": method, "params": params}),
        )?;
        match receiver.recv_timeout(timeout) {
            Ok(value) => {
                if let Some(error) = value.get("error") {
                    let message = error
                        .get("message")
                        .and_then(Value::as_str)
                        .unwrap_or("알 수 없는 오류");
                    return Err(format!("app-server 오류: {message}"));
                }
                Ok(value.get("result").cloned().unwrap_or(Value::Null))
            }
            Err(RecvTimeoutError::Timeout) => {
                if let Ok(mut map) = self.pending.lock() {
                    map.remove(&id);
                }
                Err(format!("{method} 응답이 시간 안에 오지 않았습니다."))
            }
            Err(RecvTimeoutError::Disconnected) => {
                Err(String::from("app-server 연결이 끊겼습니다."))
            }
        }
    }

    pub(crate) fn initialize(&self) -> Result<Value, String> {
        // The ChatGPT token login lives behind the app-server's experimental
        // capability; without it the server refuses `account/login/start`
        // with "requires experimentalApi capability".
        self.request(
            "initialize",
            json!({
                "clientInfo": {"name": "modal-gui", "version": "0.1.0"},
                "capabilities": {"experimentalApi": true},
            }),
            SETUP_TIMEOUT,
        )
    }

    pub(crate) fn login(&self, credentials: &chatgpt_auth::Credentials) -> Result<(), String> {
        let account_id = credentials
            .account_id
            .clone()
            .ok_or_else(|| String::from("계정 식별자가 없습니다. 다시 로그인해 주세요."))?;
        self.request(
            "account/login/start",
            json!({
                "type": "chatgptAuthTokens",
                "accessToken": credentials.access,
                "chatgptAccountId": account_id,
                "chatgptPlanType": Value::Null,
            }),
            SETUP_TIMEOUT,
        )?;
        Ok(())
    }

    /// 대화(프로젝트·노드)마다 별도 thread를 연다. 하나의 thread를 공유하면
    /// 다른 프로젝트의 맥락이 섞인다.
    pub(crate) fn ensure_thread(&self, conversation_id: &str) -> Result<String, String> {
        let scope = if conversation_id.trim().is_empty() {
            "default"
        } else {
            conversation_id.trim()
        };
        if let Some(existing) = self
            .threads
            .lock()
            .ok()
            .and_then(|guard| guard.get(scope).cloned())
        {
            return Ok(existing);
        }
        let result = self.request("thread/start", json!({}), SETUP_TIMEOUT)?;
        let id = result
            .get("thread")
            .and_then(|thread| thread.get("id"))
            .and_then(Value::as_str)
            .or_else(|| result.get("threadId").and_then(Value::as_str))
            .or_else(|| result.get("id").and_then(Value::as_str))
            .map(str::to_string)
            .ok_or_else(|| String::from("스레드 id를 받지 못했습니다."))?;
        if let Ok(mut guard) = self.threads.lock() {
            guard.insert(scope.to_string(), id.clone());
        }
        Ok(id)
    }

    /// `attachments` are project assets already on disk. Images and audio
    /// travel as app-server input items; anything else is named in the text so
    /// the model knows the file exists without pretending it was uploaded. The
    /// returned list says what actually happened to each attachment, so the
    /// conversation does not claim a delivery that never occurred.
    pub(crate) fn send_turn(
        &self,
        thread_id: &str,
        message: &str,
        attachments: &[ChatAttachment],
    ) -> Result<(Value, Vec<ChatAttachmentDelivery>), String> {
        let mut input = vec![json!({"type": "text", "text": message})];
        let mut others: Vec<String> = Vec::new();
        let mut delivery: Vec<ChatAttachmentDelivery> = Vec::new();
        for item in attachments {
            if !std::path::Path::new(&item.path).is_file() {
                others.push(format!("{} (파일 없음)", item.name));
                delivery.push(ChatAttachmentDelivery {
                    path: item.path.clone(),
                    name: item.name.clone(),
                    delivered: false,
                    note: Some(String::from("파일 없음")),
                });
                continue;
            }
            // 등록된 소재 종류를 우선 믿고, 없으면 확장자로 판단한다.
            if item.kind.as_deref() == Some("image") || is_image(&item.path) {
                // app-server가 받는 항목 이름은 `localImage`다(서버 오류 메시지로 확인).
                input.push(json!({"type": "localImage", "path": item.path}));
                delivery.push(ChatAttachmentDelivery {
                    path: item.path.clone(),
                    name: item.name.clone(),
                    delivered: true,
                    note: None,
                });
            } else if item.kind.as_deref() == Some("audio") || is_audio(&item.path) {
                input.push(json!({"type": "localAudio", "path": item.path}));
                delivery.push(ChatAttachmentDelivery {
                    path: item.path.clone(),
                    name: item.name.clone(),
                    delivered: true,
                    note: None,
                });
            } else {
                others.push(item.name.clone());
                delivery.push(ChatAttachmentDelivery {
                    path: item.path.clone(),
                    name: item.name.clone(),
                    delivered: false,
                    note: Some(String::from("파일 이름만 전달")),
                });
            }
        }
        if !others.is_empty() {
            input.push(json!({
                "type": "text",
                "text": format!("첨부한 프로젝트 소재(파일 경로만 참고): {}", others.join(", ")),
            }));
        }
        let response = self.request(
            "turn/start",
            json!({
                "threadId": thread_id,
                "input": input,
            }),
            DEFAULT_TIMEOUT,
        )?;
        Ok((response, delivery))
    }

    pub(crate) fn interrupt(&self, thread_id: &str, turn_id: &str) -> Result<(), String> {
        self.request(
            "turn/interrupt",
            json!({"threadId": thread_id, "turnId": turn_id}),
            INTERRUPT_TIMEOUT,
        )?;
        Ok(())
    }
}

impl Drop for AppServer {
    fn drop(&mut self) {
        if let Ok(mut child) = self.child.lock() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

// ---------------------------------------------------------------------------
// Per-account sessions
// ---------------------------------------------------------------------------

fn sessions() -> &'static Mutex<HashMap<String, Arc<AppServer>>> {
    static SESSIONS: std::sync::OnceLock<Mutex<HashMap<String, Arc<AppServer>>>> =
        std::sync::OnceLock::new();
    SESSIONS.get_or_init(|| Mutex::new(HashMap::new()))
}

fn account_key_for(account: &chatgpt_auth::AccountRow) -> String {
    account
        .account_id
        .clone()
        .or_else(|| account.email.clone())
        .unwrap_or_else(|| account.id.clone())
}

/// Refreshes the stored tokens on behalf of the runtime. The runtime asks only
/// when it saw a 401, so this forces a refresh even if the stored expiry has
/// not passed; otherwise the same refused token would be handed back.
fn refresh_for_runtime(
    app: &tauri::AppHandle,
    account_id: &str,
) -> Result<(String, String), String> {
    let state = app
        .try_state::<AppState>()
        .ok_or_else(|| String::from("앱 상태를 읽지 못했습니다."))?;
    let secrets = app
        .try_state::<SecretsRoot>()
        .ok_or_else(|| String::from("자격증명 저장소를 읽지 못했습니다."))?;
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    let account = chatgpt_auth::force_refresh(
        &conn,
        &secrets.0,
        &chatgpt_auth::production_endpoints(),
        account_id,
    )?;
    let key = account_key_for(&account);
    let credentials = chatgpt_auth::load_credentials(&secrets.0, &key)?;
    Ok((credentials.access, credentials.account_id.unwrap_or(key)))
}

fn get_or_spawn(app: &tauri::AppHandle, account_id: &str) -> Result<Arc<AppServer>, String> {
    if let Some(existing) = sessions()
        .lock()
        .ok()
        .and_then(|map| map.get(account_id).cloned())
    {
        return Ok(existing);
    }
    let app_for_events = app.clone();
    let sink: EventSink = Arc::new(move |value| {
        let _ = app_for_events.emit("ai-chat-event", value);
    });
    let app_for_refresh = app.clone();
    let account_for_refresh = account_id.to_string();
    let refresh: RefreshHandler = Arc::new(move |_params| {
        match refresh_for_runtime(&app_for_refresh, &account_for_refresh) {
            Ok((access, account)) => json!({
                "result": {
                    "accessToken": access,
                    "chatgptAccountId": account,
                    "chatgptPlanType": Value::Null,
                }
            }),
            Err(error) => json!({"error": {"code": -32000, "message": error}}),
        }
    });
    let session = AppServer::spawn_with(&binary(), &binary_args(), sink, refresh)?;
    session.initialize()?;
    let mut guard = sessions().lock().map_err(|error| error.to_string())?;
    guard.insert(account_id.to_string(), Arc::clone(&session));
    Ok(session)
}

fn load_credentials_for(
    state: &tauri::State<AppState>,
    secrets: &tauri::State<SecretsRoot>,
    account_id: &str,
) -> Result<(chatgpt_auth::AccountRow, chatgpt_auth::Credentials), String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    let account = chatgpt_auth::ensure_fresh(
        &conn,
        &secrets.0,
        &chatgpt_auth::production_endpoints(),
        account_id,
    )?;
    let key = account_key_for(&account);
    let credentials = chatgpt_auth::load_credentials(&secrets.0, &key)?;
    Ok((account, credentials))
}

#[derive(Serialize)]
pub(crate) struct ChatSessionInfo {
    pub account_id: String,
    pub thread_id: String,
    pub binary: String,
}

#[tauri::command]
pub(crate) fn ai_chat_ensure_session(
    app: tauri::AppHandle,
    state: tauri::State<AppState>,
    secrets: tauri::State<SecretsRoot>,
    account_id: String,
    conversation_id: Option<String>,
) -> Result<ChatSessionInfo, String> {
    let (_account, credentials) = load_credentials_for(&state, &secrets, &account_id)?;
    let session = get_or_spawn(&app, &account_id)?;
    session.login(&credentials)?;
    let thread_id = session.ensure_thread(conversation_id.as_deref().unwrap_or_default())?;
    Ok(ChatSessionInfo {
        account_id,
        thread_id,
        binary: binary(),
    })
}

#[derive(Serialize)]
pub(crate) struct ChatTurnInfo {
    pub thread_id: String,
    pub turn_id: Option<String>,
    pub attachments: Vec<ChatAttachmentDelivery>,
}

#[tauri::command]
pub(crate) fn ai_chat_send(
    app: tauri::AppHandle,
    state: tauri::State<AppState>,
    secrets: tauri::State<SecretsRoot>,
    account_id: String,
    conversation_id: Option<String>,
    attachments: Option<Vec<ChatAttachment>>,
    message: String,
) -> Result<ChatTurnInfo, String> {
    if message.trim().is_empty() {
        return Err(String::from("보낼 메시지가 비어 있습니다."));
    }
    let (account, credentials) = load_credentials_for(&state, &secrets, &account_id)?;
    let session = get_or_spawn(&app, &account_id)?;
    session.login(&credentials)?;
    let thread_id = session.ensure_thread(conversation_id.as_deref().unwrap_or_default())?;
    let attachments = attachments.unwrap_or_default();
    let (result, attachments) = session.send_turn(&thread_id, message.trim(), &attachments)?;
    let turn_id = result
        .get("turn")
        .and_then(|turn| turn.get("id"))
        .and_then(Value::as_str)
        .or_else(|| result.get("turnId").and_then(Value::as_str))
        .map(str::to_string);
    let _ = account;
    Ok(ChatTurnInfo {
        thread_id,
        turn_id,
        attachments,
    })
}

#[tauri::command]
pub(crate) fn ai_chat_interrupt(
    app: tauri::AppHandle,
    account_id: String,
    thread_id: String,
    turn_id: String,
) -> Result<(), String> {
    let session = sessions()
        .lock()
        .ok()
        .and_then(|map| map.get(&account_id).cloned())
        .ok_or_else(|| String::from("실행 중인 대화 세션이 없습니다."))?;
    let _ = &app;
    session.interrupt(&thread_id, &turn_id)
}

#[tauri::command]
pub(crate) fn ai_chat_status(account_id: String) -> Result<Option<ChatSessionInfo>, String> {
    let session = sessions()
        .lock()
        .ok()
        .and_then(|map| map.get(&account_id).cloned());
    Ok(session.map(|value| ChatSessionInfo {
        account_id,
        // 대화별 thread는 세션 안에 여러 개다. 대표 값으로 마지막 하나만 돌려준다.
        thread_id: value
            .threads
            .lock()
            .ok()
            .and_then(|guard| guard.values().next().cloned())
            .unwrap_or_default(),
        binary: binary(),
    }))
}

// ---------------------------------------------------------------------------
// Conversations and messages
// ---------------------------------------------------------------------------

#[derive(Serialize, Clone)]
pub(crate) struct ConversationRow {
    pub id: String,
    pub project_id: String,
    pub node_id: Option<String>,
    pub title: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Serialize, Clone)]
pub(crate) struct MessageRow {
    pub id: String,
    pub conversation_id: String,
    pub role: String,
    pub content: String,
    pub meta: Value,
    pub created_at: String,
}

fn map_conversation(row: &rusqlite::Row<'_>) -> rusqlite::Result<ConversationRow> {
    Ok(ConversationRow {
        id: row.get(0)?,
        project_id: row.get(1)?,
        node_id: row.get(2)?,
        title: row.get(3)?,
        created_at: row.get(4)?,
        updated_at: row.get(5)?,
    })
}

const CONVERSATION_COLUMNS: &str = "id, project_id, node_id, title, created_at, updated_at";

pub(crate) fn ensure_conversation(
    conn: &Connection,
    project_id: &str,
    node_id: Option<&str>,
) -> Result<ConversationRow, String> {
    let existing = conn
        .query_row(
            &format!(
                "SELECT {CONVERSATION_COLUMNS} FROM conversations WHERE project_id = ?1 \
                 AND ((node_id IS NULL AND ?2 IS NULL) OR node_id = ?2) ORDER BY created_at LIMIT 1"
            ),
            params![project_id, node_id],
            |row| map_conversation(row),
        )
        .ok();
    if let Some(row) = existing {
        return Ok(row);
    }
    let id = format!(
        "conv_{}_{}",
        chrono::Utc::now().timestamp_millis(),
        crate::database::id_suffix()
    );
    let now = now_rfc3339();
    conn.execute(
        "INSERT INTO conversations (id, project_id, node_id, title, created_at, updated_at) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?5)",
        params![
            id,
            project_id,
            node_id,
            node_id.map(|_| String::from("노드 대화")),
            now
        ],
    )
    .map_err(|error| error.to_string())?;
    conn.query_row(
        &format!("SELECT {CONVERSATION_COLUMNS} FROM conversations WHERE id = ?1"),
        params![id],
        |row| map_conversation(row),
    )
    .map_err(|error| error.to_string())
}

pub(crate) fn list_conversations(
    conn: &Connection,
    project_id: &str,
) -> Result<Vec<ConversationRow>, String> {
    let mut statement = conn
        .prepare(&format!(
            "SELECT {CONVERSATION_COLUMNS} FROM conversations WHERE project_id = ?1 ORDER BY created_at"
        ))
        .map_err(|error| error.to_string())?;
    let rows = statement
        .query_map(params![project_id], |row| map_conversation(row))
        .map_err(|error| error.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|error| error.to_string())
}

pub(crate) fn append_message(
    conn: &Connection,
    conversation_id: &str,
    role: &str,
    content: &str,
    meta: Option<&Value>,
) -> Result<MessageRow, String> {
    if !matches!(role, "user" | "assistant" | "system" | "tool") {
        return Err(format!("알 수 없는 메시지 역할입니다: {role}"));
    }
    let id = format!(
        "msg_{}_{}",
        chrono::Utc::now().timestamp_micros(),
        crate::database::id_suffix()
    );
    let now = now_rfc3339();
    conn.execute(
        "INSERT INTO messages (id, conversation_id, role, content, meta_json, created_at) \
         VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
        params![
            id,
            conversation_id,
            role,
            content,
            meta.map(|value| value.to_string()),
            now
        ],
    )
    .map_err(|error| error.to_string())?;
    conn.execute(
        "UPDATE conversations SET updated_at = ?2 WHERE id = ?1",
        params![conversation_id, now],
    )
    .map_err(|error| error.to_string())?;
    conn.query_row(
        "SELECT id, conversation_id, role, content, meta_json, created_at FROM messages WHERE id = ?1",
        params![id],
        |row| {
            let meta_json: Option<String> = row.get(4)?;
            Ok(MessageRow {
                id: row.get(0)?,
                conversation_id: row.get(1)?,
                role: row.get(2)?,
                content: row.get(3)?,
                meta: meta_json
                    .and_then(|text| serde_json::from_str(&text).ok())
                    .unwrap_or(Value::Null),
                created_at: row.get(5)?,
            })
        },
    )
    .map_err(|error| error.to_string())
}

pub(crate) fn list_messages(
    conn: &Connection,
    conversation_id: &str,
    limit: i64,
) -> Result<Vec<MessageRow>, String> {
    let mut statement = conn
        .prepare(
            "SELECT id, conversation_id, role, content, meta_json, created_at FROM messages \
             WHERE conversation_id = ?1 ORDER BY created_at DESC LIMIT ?2",
        )
        .map_err(|error| error.to_string())?;
    let rows = statement
        .query_map(params![conversation_id, limit], |row| {
            let meta_json: Option<String> = row.get(4)?;
            Ok(MessageRow {
                id: row.get(0)?,
                conversation_id: row.get(1)?,
                role: row.get(2)?,
                content: row.get(3)?,
                meta: meta_json
                    .and_then(|text| serde_json::from_str(&text).ok())
                    .unwrap_or(Value::Null),
                created_at: row.get(5)?,
            })
        })
        .map_err(|error| error.to_string())?;
    let mut items = rows
        .collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|error| error.to_string())?;
    items.reverse();
    Ok(items)
}

#[tauri::command]
pub(crate) fn conversation_ensure(
    state: tauri::State<AppState>,
    project_id: String,
    node_id: Option<String>,
) -> Result<ConversationRow, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    ensure_conversation(&conn, &project_id, node_id.as_deref())
}

#[tauri::command]
pub(crate) fn conversation_list(
    state: tauri::State<AppState>,
    project_id: String,
) -> Result<Vec<ConversationRow>, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    list_conversations(&conn, &project_id)
}

#[tauri::command]
pub(crate) fn message_append(
    state: tauri::State<AppState>,
    conversation_id: String,
    role: String,
    content: String,
    meta: Option<Value>,
) -> Result<MessageRow, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    append_message(&conn, &conversation_id, &role, &content, meta.as_ref())
}

#[tauri::command]
pub(crate) fn message_list(
    state: tauri::State<AppState>,
    conversation_id: String,
    limit: Option<i64>,
) -> Result<Vec<MessageRow>, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    list_messages(&conn, &conversation_id, limit.unwrap_or(200))
}
