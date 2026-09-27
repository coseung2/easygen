//! Connection registry and MCP client (stdio and Streamable HTTP).
//!
//! The registry stores configuration, never secret values: environment and
//! header entries hold *names* that are resolved from the process environment
//! (or a keychain reference) at call time.
use crate::database::{now_rfc3339, AppState};
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tauri::State;

const PROTOCOL_VERSION: &str = "2025-06-18";
const CLIENT_NAME: &str = "modal-gui";
const CLIENT_VERSION: &str = "0.1.0";
const DEFAULT_TIMEOUT_MS: u64 = 120_000;
/// How many stderr lines are kept to explain a failed session.
const STDERR_TAIL: usize = 12;

pub(crate) const KIND_STDIO: &str = "mcp-stdio";
pub(crate) const KIND_HTTP: &str = "mcp-http";

#[derive(Serialize)]
pub(crate) struct ConnectionRow {
    pub(crate) id: String,
    pub(crate) name: String,
    pub(crate) kind: String,
    pub(crate) enabled: bool,
    pub(crate) config: Value,
    pub(crate) auth_ref: Option<String>,
    pub(crate) status: String,
    pub(crate) last_error: Option<String>,
    pub(crate) last_checked_at: Option<String>,
    pub(crate) created_at: String,
    pub(crate) updated_at: String,
    pub(crate) tool_count: i64,
}

#[derive(Deserialize)]
pub(crate) struct ConnectionInput {
    pub(crate) id: Option<String>,
    pub(crate) name: String,
    pub(crate) kind: String,
    #[serde(default)]
    pub(crate) config: Option<Value>,
    #[serde(default)]
    pub(crate) auth_ref: Option<String>,
    #[serde(default)]
    pub(crate) enabled: Option<bool>,
}

#[derive(Serialize, Clone)]
pub(crate) struct ConnectionToolRow {
    pub(crate) connection_id: String,
    pub(crate) name: String,
    pub(crate) description: Option<String>,
    pub(crate) input_schema: Value,
    pub(crate) enabled: bool,
}

#[derive(Serialize)]
pub(crate) struct ConnectionTestResult {
    pub(crate) connection_id: String,
    pub(crate) status: String,
    pub(crate) server_info: Value,
    pub(crate) protocol_version: Option<String>,
    pub(crate) tools: Vec<ConnectionToolRow>,
    pub(crate) message: Option<String>,
}

fn map_connection(row: &rusqlite::Row<'_>) -> rusqlite::Result<ConnectionRow> {
    let config_json: Option<String> = row.get(4)?;
    Ok(ConnectionRow {
        id: row.get(0)?,
        name: row.get(1)?,
        kind: row.get(2)?,
        enabled: row.get::<_, i64>(3)? == 1,
        config: config_json
            .and_then(|text| serde_json::from_str(&text).ok())
            .unwrap_or_else(|| json!({})),
        auth_ref: row.get(5)?,
        status: row.get(6)?,
        last_error: row.get(7)?,
        last_checked_at: row.get(8)?,
        created_at: row.get(9)?,
        updated_at: row.get(10)?,
        tool_count: row.get(11)?,
    })
}

const CONNECTION_SELECT: &str =
    "SELECT c.id, c.name, c.kind, c.enabled, c.config_json, c.auth_ref, c.status, c.last_error, \
     c.last_checked_at, c.created_at, c.updated_at, \
     (SELECT COUNT(*) FROM connection_tools t WHERE t.connection_id = c.id) \
     FROM connections c";

pub(crate) fn list_connections(conn: &Connection) -> Result<Vec<ConnectionRow>, String> {
    let mut statement = conn
        .prepare(&format!("{CONNECTION_SELECT} ORDER BY c.created_at ASC"))
        .map_err(|error| error.to_string())?;
    let rows = statement
        .query_map([], |row| map_connection(row))
        .map_err(|error| error.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|error| error.to_string())
}

pub(crate) fn get_connection(conn: &Connection, id: &str) -> Result<ConnectionRow, String> {
    conn.query_row(
        &format!("{CONNECTION_SELECT} WHERE c.id = ?1"),
        params![id],
        |row| map_connection(row),
    )
    .map_err(|error| match error {
        rusqlite::Error::QueryReturnedNoRows => String::from("연결을 찾을 수 없습니다"),
        _ => error.to_string(),
    })
}

pub(crate) fn save_connection(
    conn: &Connection,
    input: &ConnectionInput,
) -> Result<ConnectionRow, String> {
    let name = input.name.trim();
    if name.is_empty() {
        return Err(String::from("연결 이름을 입력하세요."));
    }
    let kind = input.kind.trim();
    if !matches!(
        kind,
        KIND_STDIO | KIND_HTTP | "service-api" | "modal" | "local-tool"
    ) {
        return Err(format!("알 수 없는 연결 종류입니다: {kind}"));
    }
    let config_json = input
        .config
        .as_ref()
        .map(|value| value.to_string())
        .unwrap_or_else(|| String::from("{}"));
    if kind == KIND_STDIO {
        let command = input
            .config
            .as_ref()
            .and_then(|value| value.get("command"))
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty());
        if command.is_none() {
            return Err(String::from(
                "로컬 MCP 연결에는 실행 파일(command)이 필요합니다.",
            ));
        }
    }
    if kind == KIND_HTTP {
        let url = input
            .config
            .as_ref()
            .and_then(|value| value.get("url"))
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty());
        if url.is_none() {
            return Err(String::from("원격 MCP 연결에는 서버 URL이 필요합니다."));
        }
    }
    let now = now_rfc3339();
    let id = match input
        .id
        .as_deref()
        .map(str::trim)
        .filter(|value| !value.is_empty())
    {
        Some(existing) => {
            let changed = conn
                .execute(
                    "UPDATE connections SET name = ?2, kind = ?3, config_json = ?4, auth_ref = ?5, \
                     enabled = COALESCE(?6, enabled), updated_at = ?7 WHERE id = ?1",
                    params![
                        existing,
                        name,
                        kind,
                        config_json,
                        input.auth_ref,
                        input.enabled.map(|value| i64::from(value)),
                        now
                    ],
                )
                .map_err(|error| error.to_string())?;
            if changed == 0 {
                return Err(String::from("연결을 찾을 수 없습니다"));
            }
            existing.to_string()
        }
        None => {
            let id = format!("conn_{}", chrono::Utc::now().timestamp_millis());
            conn.execute(
                "INSERT INTO connections (id, name, kind, enabled, config_json, auth_ref, status, created_at, updated_at) \
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'saved', ?7, ?7)",
                params![
                    id,
                    name,
                    kind,
                    input.enabled.map(|value| i64::from(value)).unwrap_or(1),
                    config_json,
                    input.auth_ref,
                    now
                ],
            )
            .map_err(|error| error.to_string())?;
            id
        }
    };
    get_connection(conn, &id)
}

pub(crate) fn delete_connection(conn: &Connection, id: &str) -> Result<(), String> {
    conn.execute(
        "DELETE FROM connection_tools WHERE connection_id = ?1",
        params![id],
    )
    .map_err(|error| error.to_string())?;
    conn.execute("DELETE FROM connections WHERE id = ?1", params![id])
        .map_err(|error| error.to_string())?;
    Ok(())
}

pub(crate) fn set_connection_enabled(
    conn: &Connection,
    id: &str,
    enabled: bool,
) -> Result<ConnectionRow, String> {
    conn.execute(
        "UPDATE connections SET enabled = ?2, updated_at = ?3 WHERE id = ?1",
        params![id, i64::from(enabled), now_rfc3339()],
    )
    .map_err(|error| error.to_string())?;
    get_connection(conn, id)
}

pub(crate) fn set_tool_enabled(
    conn: &Connection,
    connection_id: &str,
    name: &str,
    enabled: bool,
) -> Result<(), String> {
    conn.execute(
        "UPDATE connection_tools SET enabled = ?3 WHERE connection_id = ?1 AND name = ?2",
        params![connection_id, name, i64::from(enabled)],
    )
    .map_err(|error| error.to_string())?;
    Ok(())
}

pub(crate) fn list_tools(
    conn: &Connection,
    connection_id: &str,
) -> Result<Vec<ConnectionToolRow>, String> {
    let mut statement = conn
        .prepare(
            "SELECT connection_id, name, description, input_schema_json, enabled \
             FROM connection_tools WHERE connection_id = ?1 ORDER BY name",
        )
        .map_err(|error| error.to_string())?;
    let rows = statement
        .query_map(params![connection_id], |row| {
            let schema_json: Option<String> = row.get(3)?;
            Ok(ConnectionToolRow {
                connection_id: row.get(0)?,
                name: row.get(1)?,
                description: row.get(2)?,
                input_schema: schema_json
                    .and_then(|text| serde_json::from_str(&text).ok())
                    .unwrap_or_else(|| json!({})),
                enabled: row.get::<_, i64>(4)? == 1,
            })
        })
        .map_err(|error| error.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|error| error.to_string())
}

/// Cached tool list from a server. Existing rows keep their enabled flag so a
/// refresh never silently turns a tool the user disabled back on.
/// Tools the server no longer reports are deleted: leaving them cached would
/// let the pre-run compatibility check pass for a tool that is gone.
pub(crate) fn store_tools(
    conn: &Connection,
    connection_id: &str,
    tools: &[ConnectionToolRow],
) -> Result<(), String> {
    let now = now_rfc3339();
    let mut statement = conn
        .prepare(
            "INSERT INTO connection_tools (connection_id, name, description, input_schema_json, enabled, discovered_at) \
             VALUES (?1, ?2, ?3, ?4, COALESCE((SELECT enabled FROM connection_tools WHERE connection_id = ?1 AND name = ?2), 1), ?5) \
             ON CONFLICT(connection_id, name) DO UPDATE SET description = excluded.description, \
               input_schema_json = excluded.input_schema_json, discovered_at = excluded.discovered_at",
        )
        .map_err(|error| error.to_string())?;
    for tool in tools {
        statement
            .execute(params![
                connection_id,
                tool.name,
                tool.description,
                tool.input_schema.to_string(),
                now
            ])
            .map_err(|error| error.to_string())?;
    }
    drop(statement);
    let discovered: std::collections::HashSet<&str> =
        tools.iter().map(|tool| tool.name.as_str()).collect();
    let cached: Vec<String> = {
        let mut query = conn
            .prepare("SELECT name FROM connection_tools WHERE connection_id = ?1")
            .map_err(|error| error.to_string())?;
        let rows = query
            .query_map(params![connection_id], |row| row.get::<_, String>(0))
            .map_err(|error| error.to_string())?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(|error| error.to_string())?
    };
    for name in cached {
        if discovered.contains(name.as_str()) {
            continue;
        }
        conn.execute(
            "DELETE FROM connection_tools WHERE connection_id = ?1 AND name = ?2",
            params![connection_id, name],
        )
        .map_err(|error| error.to_string())?;
    }
    Ok(())
}

pub(crate) fn mark_status(
    conn: &Connection,
    id: &str,
    status: &str,
    error: Option<&str>,
) -> Result<(), String> {
    conn.execute(
        "UPDATE connections SET status = ?2, last_error = ?3, last_checked_at = ?4, updated_at = ?4 WHERE id = ?1",
        params![id, status, error, now_rfc3339()],
    )
    .map_err(|error| error.to_string())?;
    Ok(())
}

// ---------------------------------------------------------------------------
// MCP client
// ---------------------------------------------------------------------------

enum Transport {
    Stdio {
        child: Child,
        responses: Receiver<String>,
        stderr: Arc<Mutex<Vec<String>>>,
    },
    Http {
        url: String,
        headers: Vec<(String, String)>,
        session: Option<String>,
        timeout: Duration,
    },
}

struct McpSession {
    transport: Transport,
    next_id: i64,
    timeout: Duration,
}

fn stderr_tail(buffer: &Arc<Mutex<Vec<String>>>) -> String {
    buffer
        .lock()
        .map(|lines| lines.join("\n"))
        .unwrap_or_default()
}

impl McpSession {
    fn open(config: &Value, timeout: Duration) -> Result<McpSession, String> {
        // A URL-only configuration speaks Streamable HTTP; anything else is a
        // local stdio server started from an executable plus arguments.
        if let Some(url) = config
            .get("url")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
        {
            // 헤더 값도 이름만 저장한다. 값은 앱 프로세스 환경에서 읽는다.
            let mut headers = Vec::new();
            if let Some(entries) = config.get("headers").and_then(Value::as_array) {
                for entry in entries {
                    let Some(name) = entry.get("name").and_then(Value::as_str) else {
                        continue;
                    };
                    let reference = entry.get("ref").and_then(Value::as_str).unwrap_or(name);
                    if let Ok(value) = std::env::var(reference) {
                        headers.push((name.to_string(), value));
                    }
                }
            }
            return Ok(McpSession {
                transport: Transport::Http {
                    url: url.to_string(),
                    headers,
                    session: None,
                    timeout,
                },
                next_id: 1,
                timeout,
            });
        }
        let command = config
            .get("command")
            .and_then(Value::as_str)
            .ok_or_else(|| String::from("로컬 MCP 설정에 실행 파일(command)이 없습니다."))?;
        let args: Vec<String> = config
            .get("args")
            .and_then(Value::as_array)
            .map(|items| {
                items
                    .iter()
                    .filter_map(|item| item.as_str().map(str::to_string))
                    .collect()
            })
            .unwrap_or_default();
        let mut child = Command::new(command);
        child.args(&args);
        if let Some(cwd) = config
            .get("cwd")
            .and_then(Value::as_str)
            .filter(|value| !value.trim().is_empty())
        {
            child.current_dir(cwd);
        }
        // 환경변수는 이름만 저장한다. 값은 앱 프로세스 환경에서 읽어 전달한다.
        if let Some(entries) = config.get("env").and_then(Value::as_array) {
            for entry in entries {
                if let Some(name) = entry.get("name").and_then(Value::as_str) {
                    if let Ok(value) = std::env::var(name) {
                        child.env(name, value);
                    }
                }
            }
        }
        let mut spawned = child
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| format!("MCP 서버를 실행하지 못했습니다: {error}"))?;

        let stdout = spawned
            .stdout
            .take()
            .ok_or_else(|| String::from("MCP 서버 stdout을 열지 못했습니다."))?;
        let stderr = spawned
            .stderr
            .take()
            .ok_or_else(|| String::from("MCP 서버 stderr를 열지 못했습니다."))?;
        let (sender, responses) = mpsc::channel();
        thread::spawn(move || {
            for line in BufReader::new(stdout).lines().flatten() {
                if sender.send(line).is_err() {
                    break;
                }
            }
        });
        let stderr_buffer = Arc::new(Mutex::new(Vec::new()));
        let stderr_writer = Arc::clone(&stderr_buffer);
        thread::spawn(move || {
            for line in BufReader::new(stderr).lines().flatten() {
                if let Ok(mut lines) = stderr_writer.lock() {
                    lines.push(line);
                    if lines.len() > STDERR_TAIL {
                        lines.remove(0);
                    }
                }
            }
        });

        Ok(McpSession {
            transport: Transport::Stdio {
                child: spawned,
                responses,
                stderr: stderr_buffer,
            },
            next_id: 1,
            timeout,
        })
    }

    fn request(&mut self, method: &str, params: Value) -> Result<Value, String> {
        let id = self.next_id;
        self.next_id += 1;
        let message = json!({"jsonrpc": "2.0", "id": id, "method": method, "params": params});
        match &mut self.transport {
            Transport::Stdio {
                child,
                responses,
                stderr,
            } => {
                let stdin = child
                    .stdin
                    .as_mut()
                    .ok_or_else(|| String::from("MCP 서버 stdin이 닫혔습니다."))?;
                writeln!(stdin, "{message}").map_err(|error| error.to_string())?;
                stdin.flush().map_err(|error| error.to_string())?;
                loop {
                    match responses.recv_timeout(self.timeout) {
                        Ok(line) => {
                            let Ok(value) = serde_json::from_str::<Value>(&line) else {
                                continue;
                            };
                            if value.get("id").and_then(Value::as_i64) != Some(id) {
                                continue;
                            }
                            return jsonrpc_result(value);
                        }
                        Err(RecvTimeoutError::Timeout) => {
                            return Err(format!(
                                "{method} 응답이 {:?} 안에 오지 않았습니다.{}",
                                self.timeout,
                                tail_hint(stderr)
                            ));
                        }
                        Err(RecvTimeoutError::Disconnected) => {
                            return Err(format!(
                                "MCP 서버가 응답 없이 종료했습니다.{}",
                                tail_hint(stderr)
                            ));
                        }
                    }
                }
            }
            Transport::Http {
                url,
                headers,
                session,
                timeout,
            } => {
                let (value, session_id) =
                    http_post(url, headers, session.as_deref(), &message, *timeout)?;
                if session_id.is_some() {
                    *session = session_id;
                }
                jsonrpc_result(value)
            }
        }
    }

    fn notify(&mut self, method: &str, params: Value) -> Result<(), String> {
        let message = json!({"jsonrpc": "2.0", "method": method, "params": params});
        match &mut self.transport {
            Transport::Stdio { child, .. } => {
                let stdin = child
                    .stdin
                    .as_mut()
                    .ok_or_else(|| String::from("MCP 서버 stdin이 닫혔습니다."))?;
                writeln!(stdin, "{message}").map_err(|error| error.to_string())?;
                stdin.flush().map_err(|error| error.to_string())?;
                Ok(())
            }
            Transport::Http {
                url,
                headers,
                session,
                timeout,
            } => {
                let _ = http_post(url, headers, session.as_deref(), &message, *timeout)?;
                Ok(())
            }
        }
    }

    fn initialize(&mut self) -> Result<Value, String> {
        let result = self.request(
            "initialize",
            json!({
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION}
            }),
        )?;
        self.notify("notifications/initialized", json!({}))?;
        Ok(result)
    }

    fn close(&mut self) {
        if let Transport::Stdio { child, .. } = &mut self.transport {
            let _ = child.stdin.take();
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn tail_hint(stderr: &Arc<Mutex<Vec<String>>>) -> String {
    let tail = stderr_tail(stderr);
    if tail.trim().is_empty() {
        String::new()
    } else {
        format!("\n서버 로그: {}", tail)
    }
}

fn jsonrpc_result(value: Value) -> Result<Value, String> {
    if let Some(error) = value.get("error") {
        let message = error
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("알 수 없는 JSON-RPC 오류");
        return Err(format!("MCP 오류: {message}"));
    }
    Ok(value.get("result").cloned().unwrap_or(Value::Null))
}

fn parse_jsonrpc_body(text: &str) -> Result<Value, String> {
    let trimmed = text.trim();
    if trimmed.starts_with('{') {
        return serde_json::from_str(trimmed)
            .map_err(|error| format!("응답 JSON을 읽지 못했습니다: {error}"));
    }
    let mut last: Option<Value> = None;
    for line in trimmed.lines() {
        if let Some(data) = line.strip_prefix("data:") {
            let data = data.trim();
            if data.is_empty() {
                continue;
            }
            if let Ok(value) = serde_json::from_str::<Value>(data) {
                last = Some(value);
            }
        }
    }
    last.ok_or_else(|| String::from("SSE 응답에서 JSON-RPC 메시지를 찾지 못했습니다."))
}

fn http_post(
    url: &str,
    headers: &[(String, String)],
    session: Option<&str>,
    body: &Value,
    timeout: Duration,
) -> Result<(Value, Option<String>), String> {
    let mut request = ureq::post(url)
        .timeout(timeout)
        .set("Content-Type", "application/json")
        .set("Accept", "application/json, text/event-stream");
    if let Some(id) = session {
        request = request.set("Mcp-Session-Id", id);
    }
    for (name, value) in headers {
        request = request.set(name, value);
    }
    match request.send_json(body.clone()) {
        Ok(response) => {
            let session_id = response.header("mcp-session-id").map(str::to_string);
            let text = response
                .into_string()
                .map_err(|error| format!("응답을 읽지 못했습니다: {error}"))?;
            Ok((parse_jsonrpc_body(&text)?, session_id))
        }
        Err(ureq::Error::Status(code, response)) => {
            let text = response.into_string().unwrap_or_default();
            let clipped: String = text.chars().take(300).collect();
            Err(format!("HTTP {code} 응답: {clipped}"))
        }
        Err(error) => Err(format!("MCP 서버에 연결하지 못했습니다: {error}")),
    }
}

fn parse_tools(result: &Value, connection_id: &str) -> Vec<ConnectionToolRow> {
    result
        .get("tools")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| {
                    let name = item.get("name").and_then(Value::as_str)?.to_string();
                    Some(ConnectionToolRow {
                        connection_id: connection_id.to_string(),
                        name,
                        description: item
                            .get("description")
                            .and_then(Value::as_str)
                            .map(str::to_string),
                        input_schema: item
                            .get("inputSchema")
                            .cloned()
                            .unwrap_or_else(|| json!({})),
                        enabled: true,
                    })
                })
                .collect()
        })
        .unwrap_or_default()
}

/// Initializes a session and lists tools. Shared by the test command and the
/// tool-node run path so both always speak the same protocol.
pub(crate) fn probe(
    config: &Value,
    timeout: Duration,
    connection_id: &str,
) -> Result<(Value, Vec<ConnectionToolRow>), String> {
    let mut session = McpSession::open(config, timeout)?;
    let result = match session.initialize() {
        Ok(value) => value,
        Err(error) => {
            session.close();
            return Err(error);
        }
    };
    let tools_result = match session.request("tools/list", json!({})) {
        Ok(value) => value,
        Err(error) => {
            session.close();
            return Err(error);
        }
    };
    session.close();
    Ok((result, parse_tools(&tools_result, connection_id)))
}

pub(crate) fn call_tool(
    config: &Value,
    timeout: Duration,
    tool: &str,
    arguments: Value,
) -> Result<Value, String> {
    let mut session = McpSession::open(config, timeout)?;
    let outcome = session
        .initialize()
        .and_then(|_| session.request("tools/call", json!({"name": tool, "arguments": arguments})));
    session.close();
    outcome
}

fn load_config(conn: &Connection, id: &str) -> Result<(String, Value), String> {
    let row = get_connection(conn, id)?;
    Ok((row.kind, row.config))
}

fn supports_probe(kind: &str) -> bool {
    kind == KIND_STDIO || kind == KIND_HTTP
}

#[tauri::command]
pub(crate) fn connection_list(state: State<AppState>) -> Result<Vec<ConnectionRow>, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    list_connections(&conn)
}

#[tauri::command]
pub(crate) fn connection_save(
    state: State<AppState>,
    input: ConnectionInput,
) -> Result<ConnectionRow, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    save_connection(&conn, &input)
}

#[tauri::command]
pub(crate) fn connection_delete(
    state: State<AppState>,
    connection_id: String,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    delete_connection(&conn, &connection_id)
}

#[tauri::command]
pub(crate) fn connection_set_enabled(
    state: State<AppState>,
    connection_id: String,
    enabled: bool,
) -> Result<ConnectionRow, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    set_connection_enabled(&conn, &connection_id, enabled)
}

#[tauri::command]
pub(crate) fn connection_set_tool_enabled(
    state: State<AppState>,
    connection_id: String,
    name: String,
    enabled: bool,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    set_tool_enabled(&conn, &connection_id, &name, enabled)
}

#[tauri::command]
pub(crate) fn connection_tools(
    state: State<AppState>,
    connection_id: String,
) -> Result<Vec<ConnectionToolRow>, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    list_tools(&conn, &connection_id)
}

#[tauri::command]
pub(crate) fn connection_test(
    state: State<AppState>,
    connection_id: String,
    timeout_ms: Option<u64>,
) -> Result<ConnectionTestResult, String> {
    let (kind, config) = {
        let conn = state.0.lock().map_err(|error| error.to_string())?;
        load_config(&conn, &connection_id)?
    };
    let timeout = Duration::from_millis(timeout_ms.unwrap_or(DEFAULT_TIMEOUT_MS));

    if !supports_probe(&kind) {
        let conn = state.0.lock().map_err(|error| error.to_string())?;
        mark_status(&conn, &connection_id, "connected", None)?;
        return Ok(ConnectionTestResult {
            connection_id,
            status: String::from("connected"),
            server_info: json!({}),
            protocol_version: None,
            tools: Vec::new(),
            message: Some(String::from(
                "이 연결 종류의 자동 점검은 아직 없습니다. 설정만 저장했습니다.",
            )),
        });
    }

    match probe(&config, timeout, &connection_id) {
        Ok((server, tools)) => {
            let conn = state.0.lock().map_err(|error| error.to_string())?;
            store_tools(&conn, &connection_id, &tools)?;
            mark_status(&conn, &connection_id, "tools-ready", None)?;
            let stored = list_tools(&conn, &connection_id)?;
            Ok(ConnectionTestResult {
                connection_id,
                status: String::from("tools-ready"),
                server_info: server
                    .get("serverInfo")
                    .cloned()
                    .unwrap_or_else(|| json!({})),
                protocol_version: server
                    .get("protocolVersion")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                tools: stored,
                message: None,
            })
        }
        Err(error) => {
            let conn = state
                .0
                .lock()
                .map_err(|lock_error| lock_error.to_string())?;
            let _ = mark_status(&conn, &connection_id, "error", Some(&error));
            Err(error)
        }
    }
}

#[tauri::command]
pub(crate) fn connection_call_tool(
    state: State<AppState>,
    connection_id: String,
    tool: String,
    arguments: Option<Value>,
    timeout_ms: Option<u64>,
) -> Result<Value, String> {
    let (kind, config) = {
        let conn = state.0.lock().map_err(|error| error.to_string())?;
        load_config(&conn, &connection_id)?
    };
    if !supports_probe(&kind) {
        return Err(String::from(
            "이 연결 종류는 아직 도구 호출을 지원하지 않습니다.",
        ));
    }
    let timeout = Duration::from_millis(timeout_ms.unwrap_or(DEFAULT_TIMEOUT_MS));
    let arguments = arguments.unwrap_or_else(|| json!({}));
    match call_tool(&config, timeout, &tool, arguments) {
        Ok(result) => {
            let conn = state.0.lock().map_err(|error| error.to_string())?;
            let _ = mark_status(&conn, &connection_id, "verified", None);
            Ok(result)
        }
        Err(error) => {
            let conn = state
                .0
                .lock()
                .map_err(|lock_error| lock_error.to_string())?;
            let _ = mark_status(&conn, &connection_id, "tools-ready", Some(&error));
            Err(error)
        }
    }
}
