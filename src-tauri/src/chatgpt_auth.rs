//! ChatGPT OAuth (authorization code + PKCE) and account storage.
//!
//! The flow follows the reference implementation in `coseung2/oauth-collect`
//! (commit fd42ba1): fixed loopback redirect `http://localhost:1455/auth/callback`,
//! PKCE S256, one accepted `state`, and form-encoded token requests.
//!
//! Access tokens never leave this module: commands return account metadata and
//! credentials are stored DPAPI-encrypted (current user) on disk. The database
//! keeps only a reference and a version number.
use crate::database::{now_rfc3339, AppState};
use base64::Engine;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::env;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tauri::Manager;

const AUTH_URL: &str = "https://auth.openai.com/oauth/authorize";
const TOKEN_URL: &str = "https://auth.openai.com/oauth/token";
const CLIENT_ID: &str = "app_EMoamEEZ73f0CkXaXp7hrann";
const SCOPE: &str = "openid profile email offline_access api.connectors.read api.connectors.invoke";
const CALLBACK_HOST: &str = "localhost";
const CALLBACK_PORT: u16 = 1455;
const CALLBACK_PATH: &str = "/auth/callback";
const ORIGINATOR: &str = "modal-gui";
/// Refresh slightly before the server-reported expiry.
const REFRESH_MARGIN_SECS: i64 = 60;
const DEFAULT_TIMEOUT: Duration = Duration::from_secs(300);
/// How long one accepted callback connection may take to send its request.
const CALLBACK_READ_TIMEOUT: Duration = Duration::from_secs(2);
const TOKEN_TIMEOUT: Duration = Duration::from_secs(60);
const POLL_INTERVAL: Duration = Duration::from_millis(120);

pub(crate) struct SecretsRoot(pub(crate) PathBuf);

#[derive(Clone)]
pub(crate) struct OAuthEndpoints {
    pub authorize_url: String,
    pub token_url: String,
    pub client_id: String,
    pub scope: String,
    pub redirect_host: String,
    pub redirect_port: u16,
    pub redirect_path: String,
    pub originator: String,
}

impl OAuthEndpoints {
    pub(crate) fn redirect_uri(&self) -> String {
        format!(
            "http://{}:{}{}",
            self.redirect_host, self.redirect_port, self.redirect_path
        )
    }
}

pub(crate) fn production_endpoints() -> OAuthEndpoints {
    // Deployment/testing overrides mirror the existing MODAL_GUI_* env pattern.
    OAuthEndpoints {
        authorize_url: env::var("MODAL_GUI_CHATGPT_AUTH_URL")
            .unwrap_or_else(|_| AUTH_URL.to_string()),
        token_url: env::var("MODAL_GUI_CHATGPT_TOKEN_URL")
            .unwrap_or_else(|_| TOKEN_URL.to_string()),
        client_id: CLIENT_ID.to_string(),
        scope: SCOPE.to_string(),
        redirect_host: CALLBACK_HOST.to_string(),
        redirect_port: env::var("MODAL_GUI_CHATGPT_CALLBACK_PORT")
            .ok()
            .and_then(|value| value.parse().ok())
            .unwrap_or(CALLBACK_PORT),
        redirect_path: CALLBACK_PATH.to_string(),
        originator: ORIGINATOR.to_string(),
    }
}

#[derive(Serialize, Deserialize, Clone, Default, Debug)]
pub(crate) struct Credentials {
    pub access: String,
    #[serde(default)]
    pub refresh: String,
    /// Unix seconds. 0 when the server did not say.
    #[serde(default)]
    pub expires_at: i64,
    #[serde(default)]
    pub account_id: Option<String>,
    #[serde(default)]
    pub email: Option<String>,
    /// Bumped on every write so late responses can be discarded.
    #[serde(default)]
    pub version: i64,
}

#[derive(Serialize, Clone, Debug)]
pub(crate) struct AccountRow {
    pub id: String,
    pub provider: String,
    pub account_id: Option<String>,
    pub display_name: Option<String>,
    pub email: Option<String>,
    pub expires_at: Option<i64>,
    pub status: String,
    pub last_error: Option<String>,
    pub credential_ref: Option<String>,
    pub credential_version: i64,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Serialize, Clone, Debug)]
#[serde(tag = "state", rename_all = "snake_case")]
pub(crate) enum AttemptState {
    Pending,
    Completed { account: AccountRow },
    Failed { error: String },
    Cancelled,
}

pub(crate) struct LoginAttempt {
    pub id: String,
    pub auth_url: String,
    pub redirect_uri: String,
    pub cancel: Arc<AtomicBool>,
}

pub(crate) struct AttemptHandles {
    pub state: Arc<Mutex<AttemptState>>,
    pub cancel: Arc<AtomicBool>,
}

/// Runs after the code exchange. It receives the attempt's cancel flag so a
/// cancel that arrives while the credentials are being stored still wins.
type CompletionFn = Box<
    dyn FnOnce(Result<Credentials, String>, Arc<Mutex<AttemptState>>, Arc<AtomicBool>) + Send,
>;

fn attempts() -> &'static Mutex<HashMap<String, AttemptHandles>> {
    static ATTEMPTS: std::sync::OnceLock<Mutex<HashMap<String, AttemptHandles>>> =
        std::sync::OnceLock::new();
    ATTEMPTS.get_or_init(|| Mutex::new(HashMap::new()))
}

fn remember_attempt(id: &str, handles: AttemptHandles) {
    if let Ok(mut map) = attempts().lock() {
        map.insert(id.to_string(), handles);
        while map.len() > 8 {
            let oldest = map.keys().next().cloned();
            if let Some(key) = oldest {
                map.remove(&key);
            }
        }
    }
}

pub(crate) fn attempt_handles(id: &str) -> Option<(Arc<Mutex<AttemptState>>, Arc<AtomicBool>)> {
    let map = attempts().lock().ok()?;
    let handles = map.get(id)?;
    Some((Arc::clone(&handles.state), Arc::clone(&handles.cancel)))
}

// ---------------------------------------------------------------------------
// PKCE, URLs and JWT helpers
// ---------------------------------------------------------------------------

fn base64url(bytes: &[u8]) -> String {
    base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(bytes)
}

fn random_urlsafe(bytes: usize) -> Result<String, String> {
    let mut buffer = vec![0u8; bytes];
    getrandom::getrandom(&mut buffer).map_err(|error| error.to_string())?;
    Ok(base64url(&buffer))
}

/// RFC 7636 S256: BASE64URL(SHA256(ASCII(verifier))).
pub(crate) fn pkce_challenge(verifier: &str) -> String {
    let digest = Sha256::digest(verifier.as_bytes());
    base64url(&digest)
}

fn percent_encode(value: &str) -> String {
    let mut output = String::new();
    for byte in value.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                output.push(byte as char)
            }
            _ => output.push_str(&format!("%{byte:02X}")),
        }
    }
    output
}

fn percent_decode(value: &str) -> String {
    let bytes = value.as_bytes();
    let mut output = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        match bytes[index] {
            b'%' if index + 2 < bytes.len() => {
                let hex = std::str::from_utf8(&bytes[index + 1..index + 3]).unwrap_or("");
                if let Ok(byte) = u8::from_str_radix(hex, 16) {
                    output.push(byte);
                    index += 3;
                    continue;
                }
                output.push(b'%');
                index += 1;
            }
            b'+' => {
                output.push(b' ');
                index += 1;
            }
            byte => {
                output.push(byte);
                index += 1;
            }
        }
    }
    String::from_utf8_lossy(&output).to_string()
}

pub(crate) fn build_authorize_url(
    endpoints: &OAuthEndpoints,
    state: &str,
    challenge: &str,
    force_login: bool,
) -> String {
    let mut params: Vec<(&str, String)> = vec![
        ("response_type", "code".to_string()),
        ("client_id", endpoints.client_id.clone()),
        ("redirect_uri", endpoints.redirect_uri()),
        ("scope", endpoints.scope.clone()),
        ("code_challenge", challenge.to_string()),
        ("code_challenge_method", "S256".to_string()),
        ("state", state.to_string()),
        ("codex_cli_simplified_flow", "true".to_string()),
        ("originator", endpoints.originator.clone()),
        ("id_token_add_organizations", "true".to_string()),
    ];
    if force_login {
        params.push(("prompt", "login".to_string()));
    }
    let query = params
        .iter()
        .map(|(key, value)| format!("{}={}", percent_encode(key), percent_encode(value)))
        .collect::<Vec<_>>()
        .join("&");
    format!("{}?{}", endpoints.authorize_url, query)
}

/// Splits a request target into path and query pairs.
pub(crate) fn parse_target(target: &str) -> (String, HashMap<String, String>) {
    let mut parts = target.splitn(2, '?');
    let path = parts.next().unwrap_or("").to_string();
    let mut params = HashMap::new();
    if let Some(query) = parts.next() {
        for pair in query.split('&') {
            if pair.is_empty() {
                continue;
            }
            let mut key_value = pair.splitn(2, '=');
            let key = percent_decode(key_value.next().unwrap_or(""));
            let value = percent_decode(key_value.next().unwrap_or(""));
            params.insert(key, value);
        }
    }
    (path, params)
}

/// A callback is accepted only when its state matches this attempt exactly.
pub(crate) fn validate_callback(
    params: &HashMap<String, String>,
    expected_state: &str,
) -> Result<String, String> {
    if let Some(error) = params.get("error") {
        let description = params.get("error_description").cloned().unwrap_or_default();
        return Err(if description.is_empty() {
            format!("인증이 거부되었습니다: {error}")
        } else {
            format!("인증이 거부되었습니다: {error} ({description})")
        });
    }
    match params.get("state") {
        Some(state) if state == expected_state => {}
        _ => return Err(String::from("state가 일치하지 않습니다.")),
    }
    params
        .get("code")
        .filter(|code| !code.is_empty())
        .cloned()
        .ok_or_else(|| String::from("콜백에 authorization code가 없습니다."))
}

pub(crate) fn decode_jwt_payload(token: &str) -> Option<Value> {
    let mut parts = token.split('.');
    let _header = parts.next()?;
    let payload = parts.next()?;
    let bytes = base64::engine::general_purpose::URL_SAFE_NO_PAD
        .decode(payload)
        .ok()?;
    serde_json::from_slice(&bytes).ok()
}

/// The account id lives in one of three claims depending on account type.
pub(crate) fn extract_account_id(id_token: Option<&str>, access_token: &str) -> Option<String> {
    for token in [id_token, Some(access_token)].into_iter().flatten() {
        let Some(payload) = decode_jwt_payload(token) else {
            continue;
        };
        if let Some(value) = payload.get("chatgpt_account_id").and_then(Value::as_str) {
            return Some(value.to_string());
        }
        if let Some(value) = payload
            .get("https://api.openai.com/auth")
            .and_then(|auth| auth.get("chatgpt_account_id"))
            .and_then(Value::as_str)
        {
            return Some(value.to_string());
        }
        if let Some(value) = payload
            .get("organizations")
            .and_then(Value::as_array)
            .and_then(|items| items.first())
            .and_then(|org| org.get("id"))
            .and_then(Value::as_str)
        {
            return Some(value.to_string());
        }
    }
    None
}

pub(crate) fn extract_email(id_token: Option<&str>, access_token: &str) -> Option<String> {
    for token in [id_token, Some(access_token)].into_iter().flatten() {
        if let Some(value) = decode_jwt_payload(token).and_then(|payload| {
            payload
                .get("email")
                .and_then(Value::as_str)
                .map(str::to_string)
        }) {
            return Some(value.to_lowercase());
        }
    }
    None
}

pub(crate) fn now_unix() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|value| value.as_secs() as i64)
        .unwrap_or(0)
}

/// Refreshes when the access token is missing or about to expire.
pub(crate) fn needs_refresh(credentials: &Credentials, now: i64) -> bool {
    if credentials.access.trim().is_empty() {
        return true;
    }
    if credentials.expires_at == 0 {
        return false;
    }
    credentials.expires_at - REFRESH_MARGIN_SECS <= now
}

// ---------------------------------------------------------------------------
// Token endpoint
// ---------------------------------------------------------------------------

fn credentials_from_token(data: &Value) -> Result<Credentials, String> {
    let access = data
        .get("access_token")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| String::from("토큰 응답에 access_token이 없습니다."))?
        .to_string();
    let id_token = data.get("id_token").and_then(Value::as_str);
    let expires_in = data
        .get("expires_in")
        .and_then(Value::as_i64)
        .unwrap_or(3600);
    Ok(Credentials {
        access: access.clone(),
        refresh: data
            .get("refresh_token")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string(),
        expires_at: now_unix() + expires_in,
        account_id: extract_account_id(id_token, &access),
        email: extract_email(id_token, &access),
        version: 0,
    })
}

fn post_form(url: &str, form: &[(&str, String)]) -> Result<Value, String> {
    let body = form
        .iter()
        .map(|(key, value)| format!("{}={}", percent_encode(key), percent_encode(value)))
        .collect::<Vec<_>>()
        .join("&");
    match ureq::post(url)
        .timeout(TOKEN_TIMEOUT)
        .set("Content-Type", "application/x-www-form-urlencoded")
        .send_string(&body)
    {
        Ok(response) => {
            let text = response
                .into_string()
                .map_err(|error| format!("토큰 응답을 읽지 못했습니다: {error}"))?;
            serde_json::from_str(&text)
                .map_err(|error| format!("토큰 응답이 JSON이 아닙니다: {error}"))
        }
        Err(ureq::Error::Status(code, response)) => {
            let text = response.into_string().unwrap_or_default();
            let clipped: String = text.chars().take(200).collect();
            Err(format!("HTTP {code}: {clipped}"))
        }
        Err(error) => Err(format!("토큰 서버에 연결하지 못했습니다: {error}")),
    }
}

pub(crate) fn exchange_code(
    endpoints: &OAuthEndpoints,
    code: &str,
    verifier: &str,
) -> Result<Credentials, String> {
    let data = post_form(
        &endpoints.token_url,
        &[
            ("grant_type", "authorization_code".to_string()),
            ("client_id", endpoints.client_id.clone()),
            ("code", code.to_string()),
            ("redirect_uri", endpoints.redirect_uri()),
            ("code_verifier", verifier.to_string()),
        ],
    )?;
    credentials_from_token(&data)
}

pub(crate) fn refresh_credentials(
    endpoints: &OAuthEndpoints,
    previous: &Credentials,
) -> Result<Credentials, String> {
    if previous.refresh.trim().is_empty() {
        return Err(String::from(
            "refresh token이 없습니다. 다시 로그인해 주세요.",
        ));
    }
    let data = post_form(
        &endpoints.token_url,
        &[
            ("grant_type", "refresh_token".to_string()),
            ("client_id", endpoints.client_id.clone()),
            ("refresh_token", previous.refresh.clone()),
        ],
    )?;
    let mut next = credentials_from_token(&data)?;
    // A response that omits the refresh token must not blank a valid one.
    if next.refresh.trim().is_empty() {
        next.refresh = previous.refresh.clone();
    }
    if next.account_id.is_none() {
        next.account_id = previous.account_id.clone();
    }
    if next.email.is_none() {
        next.email = previous.email.clone();
    }
    next.version = previous.version;
    Ok(next)
}

/// Auth failures need a new login; everything else may just be transient.
pub(crate) fn is_auth_failure(error: &str) -> bool {
    error.contains("invalid_grant")
        || error.contains("invalid_request")
        || error.contains("HTTP 400")
        || error.contains("HTTP 401")
        || error.contains("HTTP 403")
}

// ---------------------------------------------------------------------------
// Secret storage (DPAPI, current user)
// ---------------------------------------------------------------------------

#[cfg(windows)]
fn dpapi(data: &[u8], protect: bool) -> Result<Vec<u8>, String> {
    use windows_sys::Win32::Foundation::LocalFree;
    use windows_sys::Win32::Security::Cryptography::{
        CryptProtectData, CryptUnprotectData, CRYPT_INTEGER_BLOB,
    };
    unsafe {
        let mut input = CRYPT_INTEGER_BLOB {
            cbData: data.len() as u32,
            pbData: data.as_ptr() as *mut u8,
        };
        let mut output = CRYPT_INTEGER_BLOB {
            cbData: 0,
            pbData: std::ptr::null_mut(),
        };
        let ok = if protect {
            CryptProtectData(
                &mut input,
                std::ptr::null(),
                std::ptr::null(),
                std::ptr::null(),
                std::ptr::null(),
                0,
                &mut output,
            )
        } else {
            CryptUnprotectData(
                &mut input,
                std::ptr::null_mut(),
                std::ptr::null(),
                std::ptr::null(),
                std::ptr::null(),
                0,
                &mut output,
            )
        };
        if ok == 0 {
            return Err(String::from(
                "자격증명을 운영체제 저장소로 보호하지 못했습니다 (DPAPI).",
            ));
        }
        let value = std::slice::from_raw_parts(output.pbData, output.cbData as usize).to_vec();
        LocalFree(output.pbData as *mut core::ffi::c_void);
        Ok(value)
    }
}

#[cfg(not(windows))]
fn dpapi(_data: &[u8], _protect: bool) -> Result<Vec<u8>, String> {
    Err(String::from(
        "이 플랫폼에서는 자격증명 암호화를 지원하지 않습니다.",
    ))
}

fn secret_path(root: &Path, key: &str) -> PathBuf {
    let safe: String = key
        .chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() || character == '-' || character == '_' {
                character
            } else {
                '_'
            }
        })
        .collect();
    root.join(format!("chatgpt-{safe}.bin"))
}

pub(crate) fn save_credentials(
    root: &Path,
    key: &str,
    credentials: &Credentials,
) -> Result<Credentials, String> {
    let previous = load_credentials(root, key).unwrap_or_default();
    let mut next = credentials.clone();
    next.version = previous.version + 1;
    std::fs::create_dir_all(root).map_err(|error| error.to_string())?;
    let plain = serde_json::to_vec(&next).map_err(|error| error.to_string())?;
    let sealed = dpapi(&plain, true)?;
    std::fs::write(secret_path(root, key), sealed).map_err(|error| error.to_string())?;
    Ok(next)
}

pub(crate) fn load_credentials(root: &Path, key: &str) -> Result<Credentials, String> {
    let path = secret_path(root, key);
    let sealed = std::fs::read(&path).map_err(|error| error.to_string())?;
    let plain = dpapi(&sealed, false)?;
    serde_json::from_slice(&plain).map_err(|error| error.to_string())
}

pub(crate) fn account_key(credentials: &Credentials) -> String {
    credentials
        .account_id
        .clone()
        .or_else(|| credentials.email.clone())
        .unwrap_or_else(|| String::from("default"))
}

// ---------------------------------------------------------------------------
// Account rows
// ---------------------------------------------------------------------------

fn map_account(row: &rusqlite::Row<'_>) -> rusqlite::Result<AccountRow> {
    Ok(AccountRow {
        id: row.get(0)?,
        provider: row.get(1)?,
        account_id: row.get(2)?,
        display_name: row.get(3)?,
        email: row.get(4)?,
        expires_at: row.get(5)?,
        status: row.get(6)?,
        last_error: row.get(7)?,
        credential_ref: row.get(8)?,
        credential_version: row.get(9)?,
        created_at: row.get(10)?,
        updated_at: row.get(11)?,
    })
}

const ACCOUNT_COLUMNS: &str = "id, provider, account_id, display_name, email, expires_at, status, \
     last_error, credential_ref, credential_version, created_at, updated_at";

pub(crate) fn list_accounts(conn: &Connection) -> Result<Vec<AccountRow>, String> {
    let mut statement = conn
        .prepare(&format!(
            "SELECT {ACCOUNT_COLUMNS} FROM provider_accounts WHERE provider = 'chatgpt' ORDER BY created_at"
        ))
        .map_err(|error| error.to_string())?;
    let rows = statement
        .query_map([], |row| map_account(row))
        .map_err(|error| error.to_string())?;
    rows.collect::<rusqlite::Result<Vec<_>>>()
        .map_err(|error| error.to_string())
}

pub(crate) fn get_account(conn: &Connection, id: &str) -> Result<AccountRow, String> {
    conn.query_row(
        &format!("SELECT {ACCOUNT_COLUMNS} FROM provider_accounts WHERE id = ?1"),
        params![id],
        |row| map_account(row),
    )
    .map_err(|error| match error {
        rusqlite::Error::QueryReturnedNoRows => String::from("계정을 찾을 수 없습니다"),
        _ => error.to_string(),
    })
}

fn upsert_account(
    conn: &Connection,
    credentials: &Credentials,
    reference: &str,
) -> Result<AccountRow, String> {
    let id = account_key(credentials);
    let display = credentials
        .email
        .clone()
        .or_else(|| credentials.account_id.clone());
    let now = now_rfc3339();
    conn.execute(
        "INSERT INTO provider_accounts (id, provider, account_id, display_name, email, expires_at, status, last_error, credential_ref, credential_version, created_at, updated_at) \
         VALUES (?1, 'chatgpt', ?2, ?3, ?4, ?5, 'ok', NULL, ?6, ?7, ?8, ?8) \
         ON CONFLICT(id) DO UPDATE SET account_id = excluded.account_id, display_name = excluded.display_name, \
           email = excluded.email, expires_at = excluded.expires_at, status = 'ok', last_error = NULL, \
           credential_ref = excluded.credential_ref, credential_version = excluded.credential_version, updated_at = excluded.updated_at",
        params![
            id,
            credentials.account_id,
            display,
            credentials.email,
            credentials.expires_at,
            reference,
            credentials.version,
            now
        ],
    )
    .map_err(|error| error.to_string())?;
    get_account(conn, &id)
}

/// Stores credentials on disk and refreshes the account row they belong to.
pub(crate) fn store_credentials(
    conn: &Connection,
    secrets_root: &Path,
    credentials: &Credentials,
) -> Result<AccountRow, String> {
    let key = account_key(credentials);
    let stored = save_credentials(secrets_root, &key, credentials)?;
    upsert_account(
        conn,
        &stored,
        &secret_path(secrets_root, &key).to_string_lossy(),
    )
}

fn mark_account_error(
    conn: &Connection,
    id: &str,
    status: &str,
    error: &str,
) -> Result<(), String> {
    conn.execute(
        "UPDATE provider_accounts SET status = ?2, last_error = ?3, updated_at = ?4 WHERE id = ?1",
        params![id, status, error, now_rfc3339()],
    )
    .map_err(|error| error.to_string())?;
    Ok(())
}

pub(crate) fn logout_account(conn: &Connection, root: &Path, id: &str) -> Result<(), String> {
    let account = get_account(conn, id)?;
    conn.execute("DELETE FROM provider_accounts WHERE id = ?1", params![id])
        .map_err(|error| error.to_string())?;
    if let Some(reference) = account.credential_ref {
        let _ = std::fs::remove_file(reference);
    }
    let _ = std::fs::remove_file(secret_path(root, id));
    Ok(())
}

// ---------------------------------------------------------------------------
// Refresh with one request per account and a version guard
// ---------------------------------------------------------------------------

fn account_lock(key: &str) -> Arc<Mutex<()>> {
    static LOCKS: std::sync::OnceLock<Mutex<HashMap<String, Arc<Mutex<()>>>>> =
        std::sync::OnceLock::new();
    let locks = LOCKS.get_or_init(|| Mutex::new(HashMap::new()));
    let mut map = locks.lock().expect("account lock map");
    map.entry(key.to_string())
        .or_insert_with(|| Arc::new(Mutex::new(())))
        .clone()
}

/// Ensures a usable access token for the account, refreshing at most once even
/// when several nodes ask at the same time.
pub(crate) fn ensure_fresh(
    conn: &Connection,
    secrets_root: &Path,
    endpoints: &OAuthEndpoints,
    id: &str,
) -> Result<AccountRow, String> {
    let account = get_account(conn, id)?;
    let key = account_key(&Credentials {
        account_id: account.account_id.clone(),
        email: account.email.clone(),
        ..Default::default()
    });
    let current = load_credentials(secrets_root, &key)?;
    if !needs_refresh(&current, now_unix()) {
        return Ok(account);
    }

    let lock = account_lock(&key);
    let _guard = lock.lock().map_err(|error| error.to_string())?;
    // Double check after waiting for an in-flight refresh.
    let account = get_account(conn, id)?;
    let current = load_credentials(secrets_root, &key)?;
    if !needs_refresh(&current, now_unix()) {
        return Ok(account);
    }

    refresh_with_guard(conn, secrets_root, endpoints, id, &current)?;
    get_account(conn, id)
}

/// Refreshes even when the stored expiry has not passed yet.
///
/// The model runtime asks for a refresh only after the server rejected the
/// current token with a 401, so waiting for the clock would keep handing back
/// the token the server already refused.
pub(crate) fn force_refresh(
    conn: &Connection,
    secrets_root: &Path,
    endpoints: &OAuthEndpoints,
    id: &str,
) -> Result<AccountRow, String> {
    let account = get_account(conn, id)?;
    let key = account_key(&Credentials {
        account_id: account.account_id.clone(),
        email: account.email.clone(),
        ..Default::default()
    });
    let lock = account_lock(&key);
    let _guard = lock.lock().map_err(|error| error.to_string())?;
    let current = load_credentials(secrets_root, &key)?;
    refresh_with_guard(conn, secrets_root, endpoints, id, &current)?;
    get_account(conn, id)
}

/// One refresh request under the account lock, with the version guard that
/// keeps a late answer from overwriting a newer login.
fn refresh_with_guard(
    conn: &Connection,
    secrets_root: &Path,
    endpoints: &OAuthEndpoints,
    id: &str,
    current: &Credentials,
) -> Result<(), String> {
    match refresh_credentials(endpoints, current) {
        Ok(next) => {
            apply_refresh(conn, secrets_root, id, current.version, &next)?;
            Ok(())
        }
        Err(error) => {
            let status = if is_auth_failure(&error) {
                "relogin"
            } else {
                "ok"
            };
            let _ = mark_account_error(conn, id, status, &error);
            Err(error)
        }
    }
}

/// Writes a refreshed credential only when the account row did not change while
/// the request was in flight. A late answer must not resurrect a logged-out
/// account or overwrite a newer login.
pub(crate) fn apply_refresh(
    conn: &Connection,
    secrets_root: &Path,
    id: &str,
    expected_version: i64,
    next: &Credentials,
) -> Result<AccountRow, String> {
    match get_account(conn, id) {
        Ok(row) if row.credential_version == expected_version => {
            store_credentials(conn, secrets_root, next)
        }
        _ => Err(String::from(
            "갱신 중에 계정이 변경되어 결과를 반영하지 않았습니다.",
        )),
    }
}

// ---------------------------------------------------------------------------
// Loopback callback listener
// ---------------------------------------------------------------------------

fn respond(mut stream: TcpStream, status: u16, message: &str) {
    let reason = match status {
        200 => "OK",
        400 => "Bad Request",
        _ => "Not Found",
    };
    let body = format!(
        "<!doctype html><meta charset=\"utf-8\"><title>Modal GUI</title>\
         <body style=\"font-family:sans-serif;background:#0b0e13;color:#f3f6fa;padding:40px\">\
         <h1 style=\"font-size:18px\">MODAL GUI</h1><p>{message}</p></body>"
    );
    let response = format!(
        "HTTP/1.1 {status} {reason}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let _ = stream.write_all(response.as_bytes());
    let _ = stream.flush();
}

/// Reads the request line set from an accepted callback connection.
///
/// The accepted socket inherits the listener's non-blocking mode on Windows, so
/// the first read often returns `WouldBlock` before the browser's request has
/// arrived; dropping the connection there loses legitimate callbacks. Wait up
/// to `CALLBACK_READ_TIMEOUT` (never past the attempt deadline) and release
/// connections that never send anything.
fn read_callback_request(stream: &mut TcpStream, attempt_deadline: Instant) -> Option<String> {
    let read_deadline = std::cmp::min(Instant::now() + CALLBACK_READ_TIMEOUT, attempt_deadline);
    let mut buffer = [0u8; 8192];
    let mut filled = 0usize;
    loop {
        match stream.read(&mut buffer[filled..]) {
            Ok(0) => break,
            Ok(read) => {
                filled += read;
                if filled >= 4
                    && buffer[..filled]
                        .windows(4)
                        .any(|window| window == b"\r\n\r\n")
                {
                    break;
                }
                if filled == buffer.len() {
                    break;
                }
            }
            Err(error)
                if error.kind() == std::io::ErrorKind::WouldBlock
                    || error.kind() == std::io::ErrorKind::TimedOut =>
            {
                if Instant::now() >= read_deadline {
                    break;
                }
                std::thread::sleep(Duration::from_millis(20));
            }
            Err(_) => break,
        }
    }
    if filled == 0 {
        return None;
    }
    Some(String::from_utf8_lossy(&buffer[..filled]).to_string())
}

/// The redirect URI says `localhost`, which may resolve to either loopback
/// address; accept the callback on whichever family the browser picked.
fn bind_callback(port: u16) -> Result<Vec<TcpListener>, String> {
    let mut listeners = Vec::new();
    let mut ipv4_error: Option<String> = None;
    match TcpListener::bind((std::net::Ipv4Addr::LOCALHOST, port)) {
        Ok(listener) => {
            listener
                .set_nonblocking(true)
                .map_err(|error| error.to_string())?;
            listeners.push(listener);
        }
        Err(error) => ipv4_error = Some(error.to_string()),
    }
    if let Ok(listener) = TcpListener::bind((std::net::Ipv6Addr::LOCALHOST, port)) {
        listener
            .set_nonblocking(true)
            .map_err(|error| error.to_string())?;
        listeners.push(listener);
    }
    if listeners.is_empty() {
        return Err(format!(
            "포트 {port}을 사용할 수 없어 로그인 콜백을 열지 못했습니다: {}. \
             이 포트를 쓰는 다른 프로그램을 종료한 뒤 다시 시도하세요.",
            ipv4_error.unwrap_or_else(|| String::from("알 수 없는 오류"))
        ));
    }
    Ok(listeners)
}

fn accept_any(listeners: &[TcpListener]) -> Result<Option<TcpStream>, String> {
    for listener in listeners {
        match listener.accept() {
            Ok((stream, _)) => return Ok(Some(stream)),
            Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {}
            Err(error) => return Err(error.to_string()),
        }
    }
    Ok(None)
}

/// Binds the callback port immediately so a busy port is reported before the
/// browser opens, then accepts exactly one matching callback.
pub(crate) fn start_login(
    endpoints: OAuthEndpoints,
    timeout: Duration,
    on_credentials: CompletionFn,
) -> Result<LoginAttempt, String> {
    let verifier = random_urlsafe(64)?;
    let challenge = pkce_challenge(&verifier);
    let state_value = random_urlsafe(32)?;
    let listeners = bind_callback(endpoints.redirect_port)?;

    // Random suffix: two attempts in the same second must not share an id.
    let attempt_id = format!(
        "login_{}_{}",
        now_unix(),
        random_urlsafe(4).unwrap_or_default()
    );
    let auth_url = build_authorize_url(&endpoints, &state_value, &challenge, false);
    let cancel = Arc::new(AtomicBool::new(false));
    let state = Arc::new(Mutex::new(AttemptState::Pending));
    remember_attempt(
        &attempt_id,
        AttemptHandles {
            state: Arc::clone(&state),
            cancel: Arc::clone(&cancel),
        },
    );

    let thread_state = Arc::clone(&state);
    let thread_cancel = Arc::clone(&cancel);
    let deadline = Instant::now() + timeout;
    let redirect_uri = endpoints.redirect_uri();
    std::thread::spawn(move || {
        let mut completion = Some(on_credentials);
        fn finish(state: &Arc<Mutex<AttemptState>>, value: AttemptState) {
            if let Ok(mut guard) = state.lock() {
                *guard = value;
            }
        }
        loop {
            if thread_cancel.load(Ordering::SeqCst) {
                finish(&thread_state, AttemptState::Cancelled);
                return;
            }
            if Instant::now() >= deadline {
                finish(
                    &thread_state,
                    AttemptState::Failed {
                        error: String::from("로그인 시간이 초과되었습니다. 다시 시도하세요."),
                    },
                );
                return;
            }
            match accept_any(&listeners) {
                Ok(Some(mut stream)) => {
                    // Browsers open speculative connections that never send a
                    // request, and the accepted socket is non-blocking on
                    // Windows, so the request can arrive after the first read.
                    let _ = stream.set_read_timeout(Some(CALLBACK_READ_TIMEOUT));
                    let request = match read_callback_request(&mut stream, deadline) {
                        Some(request) => request,
                        None => continue,
                    };
                    let target = request
                        .lines()
                        .next()
                        .and_then(|line| line.split_whitespace().nth(1))
                        .unwrap_or("")
                        .to_string();
                    let (path, params) = parse_target(&target);
                    if path != endpoints.redirect_path {
                        respond(stream, 404, "알 수 없는 경로입니다.");
                        continue;
                    }
                    match validate_callback(&params, &state_value) {
                        Ok(code) => {
                            respond(stream, 200, "로그인이 완료되었습니다. 앱으로 돌아가세요.");
                            let outcome = exchange_code(&endpoints, &code, &verifier);
                            // A cancel that arrived while the code was being
                            // exchanged must not store credentials afterwards.
                            if thread_cancel.load(Ordering::SeqCst) {
                                finish(&thread_state, AttemptState::Cancelled);
                                return;
                            }
                            if let Some(callback) = completion.take() {
                                callback(
                                    outcome,
                                    Arc::clone(&thread_state),
                                    Arc::clone(&thread_cancel),
                                );
                            }
                            return;
                        }
                        Err(error) => {
                            // A stray callback (for example from an older
                            // attempt) is refused without ending this attempt.
                            let fatal = params.contains_key("error");
                            respond(stream, 400, &error);
                            if fatal {
                                finish(&thread_state, AttemptState::Failed { error });
                                return;
                            }
                            continue;
                        }
                    }
                }
                Ok(None) => {
                    std::thread::sleep(POLL_INTERVAL);
                }
                Err(error) => {
                    finish(&thread_state, AttemptState::Failed { error });
                    return;
                }
            }
        }
    });

    Ok(LoginAttempt {
        id: attempt_id,
        auth_url,
        redirect_uri,
        cancel,
    })
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

#[derive(Serialize)]
pub(crate) struct LoginStart {
    pub attempt_id: String,
    pub auth_url: String,
    pub redirect_uri: String,
    /// Unix seconds when the attempt stops waiting for the callback.
    pub expires_at: i64,
}

#[derive(Serialize)]
pub(crate) struct LoginStatus {
    pub state: AttemptState,
}

#[tauri::command]
pub(crate) fn chatgpt_login_start(
    app: tauri::AppHandle,
    secrets: tauri::State<SecretsRoot>,
    timeout_ms: Option<u64>,
) -> Result<LoginStart, String> {
    let endpoints = production_endpoints();
    let secrets_root = secrets.0.clone();
    let app_handle = app.clone();
    let timeout = timeout_ms
        .map(Duration::from_millis)
        .unwrap_or(DEFAULT_TIMEOUT);
    let attempt = start_login(
        endpoints,
        timeout,
        Box::new(move |outcome, shared, cancel| {
            let next = match outcome {
                Ok(credentials) => {
                    // The cancel check happens while the database lock is held:
                    // a cancel that arrives during that wait must not store the
                    // credentials and then report a completed login.
                    let stored = app_handle.try_state::<AppState>().and_then(|state| {
                        state.0.lock().ok().and_then(|conn| {
                            if cancel.load(Ordering::SeqCst) {
                                return None;
                            }
                            store_credentials(&conn, &secrets_root, &credentials).ok()
                        })
                    });
                    settle_after_store(cancel.load(Ordering::SeqCst), stored)
                }
                Err(error) => {
                    if cancel.load(Ordering::SeqCst) {
                        AttemptState::Cancelled
                    } else {
                        AttemptState::Failed { error }
                    }
                }
            };
            if let Ok(mut guard) = shared.lock() {
                *guard = next;
            }
        }),
    )?;
    // Automated runs can keep the browser closed and open the URL themselves.
    if env::var("MODAL_GUI_CHATGPT_NO_BROWSER").is_err() {
        if let Err(error) = open_in_browser(&attempt.auth_url) {
            attempt.cancel.store(true, Ordering::SeqCst);
            return Err(format!("브라우저를 열지 못했습니다: {error}"));
        }
    }
    let start = LoginStart {
        attempt_id: attempt.id,
        auth_url: attempt.auth_url,
        redirect_uri: attempt.redirect_uri,
        expires_at: attempt_deadline(timeout),
    };
    // Keep the exact URL that was opened, so a server-side error page can be
    // matched against it later (see the 2026-09-27 login incident record).
    if let Ok(data_dir) = app.path().app_data_dir() {
        let _ = append_login_log(&data_dir.join("logs"), &start);
    }
    Ok(start)
}

pub(crate) fn open_in_browser(url: &str) -> Result<(), String> {
    // The shell API receives the whole URL; `cmd /C start` cut it at the first
    // `&`, so the authorize request arrived without client_id and failed.
    crate::media::open_with_shell(url)
}

/// One line per opened login attempt.
///
/// A browser or server error can be matched against the exact URL the app
/// opened, which is what the incident record asked for.
pub(crate) fn login_log_line(start: &LoginStart) -> String {
    format!(
        "{} attempt={} expires_at={} url={}",
        now_unix(),
        start.attempt_id,
        start.expires_at,
        start.auth_url
    )
}

pub(crate) fn append_login_log(dir: &Path, start: &LoginStart) -> std::io::Result<()> {
    std::fs::create_dir_all(dir)?;
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join("chatgpt-login.log"))?;
    writeln!(file, "{}", login_log_line(start))
}

/// Unix seconds when an attempt with this timeout stops waiting. The UI shows
/// the remaining time, and the fixed callback port is released at that point.
pub(crate) fn attempt_deadline(timeout: Duration) -> i64 {
    now_unix() + timeout.as_secs() as i64
}

/// Decides the attempt state after the code exchange.
///
/// `stored` is `None` when the credentials were not written, which includes a
/// cancel that arrived while the store was waiting for the database lock. A
/// cancel must never turn into a completed login, and a stored account must not
/// be reported as cancelled.
pub(crate) fn settle_after_store(cancelled: bool, stored: Option<AccountRow>) -> AttemptState {
    match (stored, cancelled) {
        (Some(account), _) => AttemptState::Completed { account },
        (None, true) => AttemptState::Cancelled,
        (None, false) => AttemptState::Failed {
            error: String::from("계정 정보를 저장하지 못했습니다."),
        },
    }
}

#[tauri::command]
pub(crate) fn chatgpt_login_status(attempt_id: String) -> Result<LoginStatus, String> {
    let (state, _) = attempt_handles(&attempt_id)
        .ok_or_else(|| String::from("로그인 시도를 찾을 수 없습니다"))?;
    let snapshot = state.lock().map_err(|error| error.to_string())?.clone();
    Ok(LoginStatus { state: snapshot })
}

#[tauri::command]
pub(crate) fn chatgpt_login_cancel(attempt_id: String) -> Result<(), String> {
    let (_, cancel) = attempt_handles(&attempt_id)
        .ok_or_else(|| String::from("로그인 시도를 찾을 수 없습니다"))?;
    cancel.store(true, Ordering::SeqCst);
    Ok(())
}

#[tauri::command]
pub(crate) fn chatgpt_accounts(state: tauri::State<AppState>) -> Result<Vec<AccountRow>, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    list_accounts(&conn)
}

#[tauri::command]
pub(crate) fn chatgpt_logout(
    state: tauri::State<AppState>,
    secrets: tauri::State<SecretsRoot>,
    account_id: String,
) -> Result<(), String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    logout_account(&conn, &secrets.0, &account_id)
}

/// Refreshes the account when the token is near expiry. Returns metadata only.
#[tauri::command]
pub(crate) fn chatgpt_ensure_fresh(
    state: tauri::State<AppState>,
    secrets: tauri::State<SecretsRoot>,
    account_id: String,
) -> Result<AccountRow, String> {
    let conn = state.0.lock().map_err(|error| error.to_string())?;
    ensure_fresh(&conn, &secrets.0, &production_endpoints(), &account_id)
}
