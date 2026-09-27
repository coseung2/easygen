//! SQLite lifecycle, migrations and shared time/period queries.
use base64::Engine;
use rusqlite::{params, Connection};
use std::sync::Mutex;

pub(crate) struct AppState(pub(crate) Mutex<Connection>);

pub(crate) fn init_db(conn: &Connection) -> rusqlite::Result<()> {
    conn.execute_batch(
        r#"
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS modal_profiles (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          workspace_label TEXT,
          enabled INTEGER NOT NULL DEFAULT 1,
          keychain_ref TEXT NOT NULL,
          budget_limit REAL,
          budget_used REAL NOT NULL DEFAULT 0,
          reserve_amount REAL NOT NULL DEFAULT 0,
          max_concurrency INTEGER NOT NULL DEFAULT 1,
          priority INTEGER NOT NULL DEFAULT 0,
          cooldown_until TEXT,
          last_error TEXT,
          last_used_at TEXT,
          modal_profile_name TEXT,
          last_synced_at TEXT,
          last_sync_error TEXT,
          archived_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY,
          modal_profile_id TEXT,
          function_call_id TEXT,
          status TEXT NOT NULL,
          stage TEXT NOT NULL,
          kind TEXT,
          prompt TEXT NOT NULL,
          input_path TEXT NOT NULL,
          output_path TEXT,
          thumbnail_path TEXT,
          duration INTEGER,
          resolution TEXT,
          seed INTEGER,
          progress REAL,
          error_code TEXT,
          error_message TEXT,
          retry_count INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          started_at TEXT,
          completed_at TEXT,
          FOREIGN KEY (modal_profile_id) REFERENCES modal_profiles(id)
        );
        CREATE TABLE IF NOT EXISTS job_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          job_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          level TEXT,
          stage TEXT,
          message TEXT,
          payload_json TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY (job_id) REFERENCES jobs(id)
        );
        CREATE TABLE IF NOT EXISTS usage_records (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          modal_profile_id TEXT NOT NULL,
          job_id TEXT,
          source TEXT NOT NULL,
          amount REAL,
          period TEXT,
          label TEXT,
          object_id TEXT,
          raw_json TEXT,
          observed_at TEXT NOT NULL,
          FOREIGN KEY (modal_profile_id) REFERENCES modal_profiles(id)
        );
        CREATE TABLE IF NOT EXISTS studio_projects (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          revision INTEGER NOT NULL DEFAULT 1,
          node_count INTEGER NOT NULL DEFAULT 0,
          asset_count INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS studio_project_revisions (
          project_id TEXT NOT NULL,
          revision INTEGER NOT NULL,
          document_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (project_id, revision),
          FOREIGN KEY (project_id) REFERENCES studio_projects(id)
        );
        CREATE TABLE IF NOT EXISTS studio_assets (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          project_id TEXT NOT NULL,
          file_name TEXT NOT NULL,
          stored_path TEXT NOT NULL,
          size_bytes INTEGER NOT NULL,
          hash TEXT NOT NULL,
          kind TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (project_id) REFERENCES studio_projects(id)
        );
        CREATE TABLE IF NOT EXISTS studio_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          node_id TEXT NOT NULL,
          node_title TEXT,
          tool TEXT NOT NULL,
          status TEXT NOT NULL,
          stage TEXT,
          job_id TEXT,
          output_path TEXT,
          result_asset_id TEXT,
          input_json TEXT,
          submission_key TEXT,
          error_code TEXT,
          error_message TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS connections (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          kind TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          config_json TEXT,
          auth_ref TEXT,
          status TEXT NOT NULL DEFAULT 'saved',
          last_error TEXT,
          last_checked_at TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS connection_tools (
          connection_id TEXT NOT NULL,
          name TEXT NOT NULL,
          description TEXT,
          input_schema_json TEXT,
          enabled INTEGER NOT NULL DEFAULT 1,
          discovered_at TEXT NOT NULL,
          PRIMARY KEY (connection_id, name)
        );
        CREATE TABLE IF NOT EXISTS provider_accounts (
          id TEXT PRIMARY KEY,
          provider TEXT NOT NULL,
          account_id TEXT,
          display_name TEXT,
          email TEXT,
          expires_at INTEGER,
          status TEXT NOT NULL DEFAULT 'ok',
          last_error TEXT,
          credential_ref TEXT,
          credential_version INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversations (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL,
          node_id TEXT,
          title TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY,
          conversation_id TEXT NOT NULL,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          meta_json TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );
        CREATE TABLE IF NOT EXISTS workflow_definitions (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          tool TEXT NOT NULL,
          location TEXT,
          status TEXT NOT NULL DEFAULT 'registered',
          inputs_json TEXT,
          outputs_json TEXT,
          notes TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS studio_templates (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          description TEXT,
          document_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        "#,
    )?;
    // Columns added after the first release; CREATE TABLE IF NOT EXISTS cannot add them.
    ensure_column(conn, "modal_profiles", "modal_profile_name", "TEXT")?;
    ensure_column(conn, "modal_profiles", "last_synced_at", "TEXT")?;
    ensure_column(conn, "modal_profiles", "last_sync_error", "TEXT")?;
    ensure_column(conn, "modal_profiles", "archived_at", "TEXT")?;
    ensure_column(conn, "jobs", "kind", "TEXT")?;
    // Studio projects reuse the job pipeline; these columns are how a job is
    // traced back to the canvas node that requested it.
    ensure_column(conn, "jobs", "studio_project_id", "TEXT")?;
    ensure_column(conn, "jobs", "studio_node_id", "TEXT")?;
    ensure_column(conn, "studio_runs", "submission_key", "TEXT")?;
    ensure_column(conn, "usage_records", "period", "TEXT")?;
    ensure_column(conn, "usage_records", "label", "TEXT")?;
    ensure_column(conn, "usage_records", "object_id", "TEXT")?;
    // 취소·다운로드 실패 뒤에도 원격 결과를 다시 받을 수 있게 위치를 남긴다.
    ensure_column(conn, "studio_runs", "remote_output_path", "TEXT")?;
    // The index touches a new column, so it must be created after the migrations.
    conn.execute_batch(
        "CREATE INDEX IF NOT EXISTS usage_records_profile_period
           ON usage_records (modal_profile_id, source, period);
         CREATE INDEX IF NOT EXISTS usage_records_job_id
           ON usage_records (job_id);
         CREATE INDEX IF NOT EXISTS studio_runs_project_created
           ON studio_runs (project_id, created_at);
         CREATE INDEX IF NOT EXISTS studio_runs_job_id
           ON studio_runs (job_id);
         CREATE INDEX IF NOT EXISTS studio_runs_submission
           ON studio_runs (project_id, submission_key, created_at);
         CREATE INDEX IF NOT EXISTS jobs_studio_project
           ON jobs (studio_project_id, created_at);
         CREATE INDEX IF NOT EXISTS connection_tools_connection
           ON connection_tools (connection_id, name);
         CREATE INDEX IF NOT EXISTS conversations_project
           ON conversations (project_id, created_at);
         CREATE INDEX IF NOT EXISTS messages_conversation
           ON messages (conversation_id, created_at);",
    )?;
    seed_default_profile(conn)
}

fn ensure_column(conn: &Connection, table: &str, column: &str, ddl: &str) -> rusqlite::Result<()> {
    let existing: Vec<String> = conn
        .prepare(&format!("PRAGMA table_info({table})"))?
        .query_map([], |row| row.get::<_, String>(1))?
        .collect::<rusqlite::Result<Vec<_>>>()?;
    if !existing.iter().any(|name| name == column) {
        conn.execute_batch(&format!("ALTER TABLE {table} ADD COLUMN {column} {ddl}"))?;
    }
    Ok(())
}

pub(crate) fn now_rfc3339() -> String {
    chrono::Utc::now().to_rfc3339()
}

/// Short random suffix so ids created in the same millisecond cannot collide
/// (two conversations, two runs, two jobs). Filesystem-safe on purpose.
pub(crate) fn id_suffix() -> String {
    let mut buffer = [0u8; 4];
    match getrandom::getrandom(&mut buffer) {
        Ok(()) => base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(buffer),
        Err(_) => format!("{}", chrono::Utc::now().timestamp_subsec_nanos()),
    }
}

/// Month tag (UTC) that keeps one billing period per profile.
pub(crate) fn current_period() -> String {
    chrono::Utc::now().format("%Y-%m").to_string()
}

/// Finds which local Modal profile is active by reading `~/.modal.toml`.
///
/// The file has to be read as a whole to find the `active` flag, so token lines
/// pass through memory here. They are never returned, stored, logged, or sent
/// anywhere: the only value that leaves this function is one section name.
fn detect_active_modal_profile() -> Option<String> {
    let path = std::env::var("MODAL_CONFIG_PATH")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .map(std::path::PathBuf::from)
        .or_else(|| {
            std::env::var("USERPROFILE")
                .ok()
                .map(|home| std::path::PathBuf::from(home).join(".modal.toml"))
        })?;
    read_active_modal_profile(&path)
}

pub(crate) fn read_active_modal_profile(path: &std::path::Path) -> Option<String> {
    let text = std::fs::read_to_string(path).ok()?;
    let mut section: Option<String> = None;
    for line in text.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') && trimmed.ends_with(']') {
            section = Some(
                trimmed
                    .trim_matches(|c| c == '[' || c == ']')
                    .trim()
                    .to_string(),
            );
            continue;
        }
        let mut parts = trimmed.splitn(2, '=');
        if parts.next().map(|key| key.trim()) == Some("active")
            && parts.next().map(|value| value.trim()) == Some("true")
        {
            return section;
        }
    }
    None
}

/// Keeps the first run usable: one account row pointing at whatever profile the
/// local Modal CLI currently uses. Created only when no account exists yet.
fn seed_default_profile(conn: &Connection) -> rusqlite::Result<()> {
    let existing: i64 =
        conn.query_row("SELECT COUNT(*) FROM modal_profiles", [], |row| row.get(0))?;
    if existing > 0 {
        return Ok(());
    }
    let now = now_rfc3339();
    let detected = detect_active_modal_profile();
    conn.execute(
        "INSERT INTO modal_profiles (id, name, workspace_label, enabled, keychain_ref, budget_limit, \
         budget_used, reserve_amount, max_concurrency, priority, modal_profile_name, created_at, updated_at) \
         VALUES (?1, ?2, ?3, 1, '', NULL, 0, 0, 1, 0, ?4, ?5, ?5)",
        params!["modal_01", "기본 Modal 계정", detected.clone(), detected, now],
    )?;
    Ok(())
}

/// The newest billing period actually stored, not the local month. A report whose
/// period differs from the local month (KST month start versus UTC) must not make
/// every account read as zero.
pub(crate) fn latest_billing_period(conn: &Connection) -> String {
    conn.query_row(
        "SELECT MAX(period) FROM usage_records \
         WHERE source = 'modal_billing_report' AND period IS NOT NULL",
        [],
        |row| row.get::<_, Option<String>>(0),
    )
    .ok()
    .flatten()
    .unwrap_or_else(current_period)
}
