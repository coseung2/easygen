//! Unit tests for the SQLite layer behind the usage dashboard.
//!
//! The Modal CLI reports cost per app and interval, so most of the risk lives in
//! migrations and in the join/aggregate queries. These tests run against
//! in-memory databases and never touch the user's application database.

use crate::accounts::{
    archive_profile, is_valid_modal_profile_name, list_profiles, resolve_profile, save_profile,
    set_profile_enabled, ProfileInput,
};
use crate::database::{current_period, init_db, latest_billing_period, read_active_modal_profile};
use crate::diagnostics::{sanitize_detail, DETAIL_LIMIT};
use crate::jobs::{
    apply_worker_event, fail_interrupted_jobs, mark_spawn_failure_row, mark_start_failure_row,
    mark_worker_exit_row, recent_jobs, PROFILE_UNAVAILABLE_CODE, RESTART_ERROR_CODE,
};
use crate::usage::{usage_rows, value_as_f64, write_sync_summary};
use rusqlite::params;
use rusqlite::Connection;
use serde_json::json;
use serde_json::Value;

/// The schema as shipped before accounts and usage gained their newer columns.
fn legacy_db() -> Connection {
    let conn = Connection::open_in_memory().unwrap();
    conn.execute_batch(
        "CREATE TABLE modal_profiles (
           id TEXT PRIMARY KEY, name TEXT NOT NULL, workspace_label TEXT,
           enabled INTEGER NOT NULL DEFAULT 1, keychain_ref TEXT NOT NULL, budget_limit REAL,
           budget_used REAL NOT NULL DEFAULT 0, reserve_amount REAL NOT NULL DEFAULT 0,
           max_concurrency INTEGER NOT NULL DEFAULT 1, priority INTEGER NOT NULL DEFAULT 0,
           cooldown_until TEXT, last_error TEXT, last_used_at TEXT,
           created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
         CREATE TABLE jobs (
           id TEXT PRIMARY KEY, modal_profile_id TEXT, function_call_id TEXT,
           status TEXT NOT NULL, stage TEXT NOT NULL, prompt TEXT NOT NULL, input_path TEXT NOT NULL,
           output_path TEXT, thumbnail_path TEXT, duration INTEGER, resolution TEXT, seed INTEGER,
           progress REAL, error_code TEXT, error_message TEXT,
           retry_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, started_at TEXT,
           completed_at TEXT);
         CREATE TABLE job_events (
           id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, event_type TEXT NOT NULL,
           level TEXT, stage TEXT, message TEXT, payload_json TEXT, created_at TEXT NOT NULL);
         CREATE TABLE usage_records (
           id INTEGER PRIMARY KEY AUTOINCREMENT, modal_profile_id TEXT NOT NULL, job_id TEXT,
           source TEXT NOT NULL, amount REAL, raw_json TEXT, observed_at TEXT NOT NULL);",
    )
    .unwrap();
    conn
}

fn fresh_db() -> Connection {
    let conn = Connection::open_in_memory().unwrap();
    init_db(&conn).unwrap();
    conn
}

fn draft(id: Option<&str>, name: &str) -> ProfileInput {
    ProfileInput {
        id: id.map(str::to_string),
        name: name.to_string(),
        modal_profile_name: Some(String::from("mallagaenge")),
        workspace_label: Some(String::from("main")),
        keychain_ref: Some(String::from("keychain:modal/mallagaenge")),
        budget_limit: Some(12.5),
        max_concurrency: None,
        priority: None,
    }
}

#[test]
fn migrations_upgrade_the_previous_schema_without_losing_rows() {
    let conn = legacy_db();
    conn.execute(
        "INSERT INTO modal_profiles (id, name, keychain_ref, created_at, updated_at) \
         VALUES ('modal_01', '기존 계정', '', 'x', 'x')",
        [],
    )
    .unwrap();
    conn.execute(
        "INSERT INTO jobs (id, status, stage, prompt, input_path, created_at) \
         VALUES ('job_1', 'COMPLETED', 'COMPLETED', 'p', 'C:/a.png', 'x')",
        [],
    )
    .unwrap();
    init_db(&conn).unwrap();

    let profiles = list_profiles(&conn).unwrap();
    assert_eq!(profiles.len(), 1);
    assert_eq!(profiles[0].name, "기존 계정");
    assert_eq!(profiles[0].modal_profile_name, None);
    assert_eq!(profiles[0].month_cost, 0.0);
    let kind: Option<String> = conn
        .query_row("SELECT kind FROM jobs WHERE id = 'job_1'", [], |row| {
            row.get(0)
        })
        .unwrap();
    assert_eq!(kind, None);

    // Migrations are idempotent, so repeated startups stay harmless.
    init_db(&conn).unwrap();
    init_db(&conn).unwrap();
    assert_eq!(list_profiles(&conn).unwrap().len(), 1);
    let indexes: Vec<String> = conn
        .prepare(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'usage_records'",
        )
        .unwrap()
        .query_map([], |row| row.get(0))
        .unwrap()
        .collect::<rusqlite::Result<Vec<_>>>()
        .unwrap();
    assert!(
        indexes.contains(&String::from("usage_records_profile_period")),
        "{indexes:?}"
    );
    assert!(
        indexes.contains(&String::from("usage_records_job_id")),
        "{indexes:?}"
    );
}

#[test]
fn a_fresh_database_seeds_exactly_one_usable_account() {
    let conn = fresh_db();
    let profiles = list_profiles(&conn).unwrap();
    assert_eq!(profiles.len(), 1);
    assert_eq!(profiles[0].id, "modal_01");
    assert!(profiles[0].enabled);
    assert_eq!(profiles[0].keychain_ref, "");
    assert_eq!(profiles[0].budget_limit, None);
}

#[test]
fn saving_an_account_keeps_its_id_and_enabled_state() {
    let conn = fresh_db();
    set_profile_enabled(&conn, "modal_01", false).unwrap();
    let updated = save_profile(&conn, &draft(Some("modal_01"), "H3 계정")).unwrap();
    let profile = updated.iter().find(|item| item.id == "modal_01").unwrap();
    assert_eq!(profile.name, "H3 계정");
    assert_eq!(profile.modal_profile_name.as_deref(), Some("mallagaenge"));
    assert_eq!(profile.workspace_label.as_deref(), Some("main"));
    assert_eq!(profile.budget_limit, Some(12.5));
    assert_eq!(profile.keychain_ref, "keychain:modal/mallagaenge");
    assert!(!profile.enabled);

    let created = save_profile(&conn, &draft(None, "두 번째")).unwrap();
    assert_eq!(created.len(), 2);
    assert_eq!(created.iter().filter(|item| item.enabled).count(), 1);
    assert!(created
        .iter()
        .any(|item| item.name == "두 번째" && item.id != "modal_01"));
}

#[test]
fn account_totals_follow_the_stored_period_not_the_local_month() {
    let conn = fresh_db();
    // Deliberately not the local month: the read side must not go blank just
    // because the report period and the local calendar month disagree.
    for (source, period_tag, amount) in [
        ("modal_billing_report", "2000-01", 1.25_f64),
        ("modal_billing_report", "2000-01", 0.75),
        ("modal_billing_report", "1999-12", 99.0),
        ("job_usage", "2000-01", 5.0),
    ] {
        conn.execute(
            "INSERT INTO usage_records (modal_profile_id, job_id, source, amount, period, observed_at) \
             VALUES ('modal_01', NULL, ?1, ?2, ?3, 'now')",
            params![source, amount, period_tag],
        )
        .unwrap();
    }
    assert_eq!(latest_billing_period(&conn), "2000-01");
    let profiles = list_profiles(&conn).unwrap();
    assert_eq!(profiles[0].period, "2000-01");
    assert_eq!(profiles[0].month_cost, 2.0);
    assert_eq!(profiles[0].month_intervals, 2);

    // With nothing stored, the local month is the only honest label.
    let empty = Connection::open_in_memory().unwrap();
    init_db(&empty).unwrap();
    assert_eq!(latest_billing_period(&empty), current_period());
}

#[test]
fn usage_rows_pair_jobs_with_recorded_cost_only() {
    let conn = fresh_db();
    conn.execute(
        "INSERT INTO jobs (id, modal_profile_id, status, stage, kind, prompt, input_path, created_at) \
         VALUES ('job_a', 'modal_01', 'COMPLETED', 'COMPLETED', 'fl2v', '프롬프트 A', 'C:/a.png', \
                 '2026-09-01T00:00:00Z')",
        [],
    )
    .unwrap();
    conn.execute(
        "INSERT INTO jobs (id, modal_profile_id, status, stage, kind, prompt, input_path, created_at) \
         VALUES ('job_b', 'modal_01', 'QUEUED', 'JOB_CREATED', 'music', '프롬프트 B', '', \
                 '2026-09-02T00:00:00Z')",
        [],
    )
    .unwrap();
    conn.execute(
        "INSERT INTO usage_records (modal_profile_id, job_id, source, amount, period, observed_at) \
         VALUES ('modal_01', 'job_a', 'job_usage', 0.42, ?1, 'now')",
        params![current_period()],
    )
    .unwrap();

    let value = usage_rows(&conn, 50).unwrap();
    let jobs = value.get("jobs").and_then(Value::as_array).unwrap();
    assert_eq!(jobs.len(), 2);
    let job_a = jobs.iter().find(|item| item["id"] == "job_a").unwrap();
    assert_eq!(job_a["recorded_cost"].as_f64(), Some(0.42));
    assert_eq!(job_a["profile_name"].as_str(), Some("기본 Modal 계정"));
    let job_b = jobs.iter().find(|item| item["id"] == "job_b").unwrap();
    assert!(job_b["recorded_cost"].is_null());
    assert_eq!(job_b["kind"].as_str(), Some("music"));
    // App-level billing rows stay out of the per-job table.
    assert!(value
        .get("objects")
        .and_then(Value::as_array)
        .unwrap()
        .is_empty());
}

#[test]
fn archiving_an_account_keeps_its_jobs_and_cost_history() {
    let conn = fresh_db();
    conn.execute(
        "INSERT INTO jobs (id, modal_profile_id, status, stage, prompt, input_path, created_at) \
         VALUES ('job_a', 'modal_01', 'COMPLETED', 'COMPLETED', 'p', 'i', 'x')",
        [],
    )
    .unwrap();
    for (job_id, source, amount) in [
        (Some("job_a"), "job_usage", 0.4_f64),
        (None, "modal_billing_report", 3.5),
    ] {
        conn.execute(
            "INSERT INTO usage_records (modal_profile_id, job_id, source, amount, period, observed_at) \
             VALUES ('modal_01', ?1, ?2, ?3, ?4, 'now')",
            params![job_id, source, amount, current_period()],
        )
        .unwrap();
    }

    // The account disappears from the active list but nothing is destroyed.
    assert!(archive_profile(&conn, "modal_01").unwrap().is_empty());
    let (enabled, archived): (i64, Option<String>) = conn
        .query_row(
            "SELECT enabled, archived_at FROM modal_profiles WHERE id = 'modal_01'",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap();
    assert_eq!(enabled, 0);
    assert!(archived.is_some());
    let jobs: i64 = conn
        .query_row("SELECT COUNT(*) FROM jobs", [], |row| row.get(0))
        .unwrap();
    let records: i64 = conn
        .query_row("SELECT COUNT(*) FROM usage_records", [], |row| row.get(0))
        .unwrap();
    assert_eq!(jobs, 1);
    assert_eq!(records, 2);

    // History still resolves the account name from the tombstone.
    let rows = usage_rows(&conn, 50).unwrap();
    assert_eq!(
        rows["jobs"][0]["profile_name"].as_str(),
        Some("기본 Modal 계정")
    );
    assert!(archive_profile(&conn, "modal_01").is_err());
    assert!(archive_profile(&conn, "ghost").is_err());
}

#[test]
fn account_validation_rejects_bad_input_without_storing_secrets() {
    let conn = fresh_db();
    let blank = ProfileInput {
        name: String::from("   "),
        ..draft(None, "x")
    };
    assert!(save_profile(&conn, &blank).is_err());
    let bad_profile = ProfileInput {
        modal_profile_name: Some(String::from("bad name!")),
        ..draft(None, "ok")
    };
    assert!(save_profile(&conn, &bad_profile).is_err());

    assert!(is_valid_modal_profile_name("mallagaenge"));
    assert!(is_valid_modal_profile_name("team-1@example.com"));
    assert!(!is_valid_modal_profile_name(""));
    assert!(!is_valid_modal_profile_name("has space"));
    assert!(!is_valid_modal_profile_name(&"a".repeat(65)));

    // An unusable credit value becomes "unknown" instead of a guessed balance.
    let nan = ProfileInput {
        budget_limit: Some(f64::NAN),
        ..draft(Some("modal_01"), "계정")
    };
    assert_eq!(save_profile(&conn, &nan).unwrap()[0].budget_limit, None);
    let negative = ProfileInput {
        budget_limit: Some(-3.0),
        ..draft(Some("modal_01"), "계정")
    };
    assert_eq!(
        save_profile(&conn, &negative).unwrap()[0].budget_limit,
        None
    );
}

#[test]
fn an_explicit_account_is_never_switched_or_stopped_silently() {
    let conn = fresh_db();
    let (id, modal_profile) = resolve_profile(&conn, &Some(String::from("modal_01"))).unwrap();
    assert_eq!(id, "modal_01");
    assert_eq!(modal_profile.as_deref(), Some("mallagaenge"));
    let used: Option<String> = conn
        .query_row(
            "SELECT last_used_at FROM modal_profiles WHERE id = 'modal_01'",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert!(used.is_some());

    // A stale or archived id is an error, not a silent switch to another account.
    let stale = resolve_profile(&conn, &Some(String::from("ghost"))).unwrap_err();
    assert!(stale.contains("ghost"), "{stale}");

    // A higher-priority account is only chosen when the request is empty.
    let preferred = ProfileInput {
        priority: Some(50),
        ..draft(None, "우선 계정")
    };
    save_profile(&conn, &preferred).unwrap();
    assert_ne!(resolve_profile(&conn, &None).unwrap().0, "modal_01");
    assert_eq!(
        resolve_profile(&conn, &Some(String::from("modal_01")))
            .unwrap()
            .0,
        "modal_01"
    );

    // A stopped account is rejected even when it is named explicitly.
    set_profile_enabled(&conn, "modal_01", false).unwrap();
    let stopped = resolve_profile(&conn, &Some(String::from("modal_01"))).unwrap_err();
    assert!(stopped.contains("중지된"), "{stopped}");

    // No enabled account at all is rejected for both empty and named requests.
    let all: Vec<String> = list_profiles(&conn)
        .unwrap()
        .into_iter()
        .map(|item| item.id)
        .collect();
    assert_eq!(all.len(), 2);
    for id in all {
        set_profile_enabled(&conn, &id, false).unwrap();
    }
    assert!(resolve_profile(&conn, &None).is_err());
    assert!(resolve_profile(&conn, &Some(String::new())).is_err());

    // Archived accounts are not selectable either.
    archive_profile(&conn, "modal_01").unwrap();
    assert!(resolve_profile(&conn, &Some(String::from("modal_01"))).is_err());
}

#[test]
fn billing_totals_are_read_from_strings_or_numbers() {
    assert_eq!(value_as_f64(Some(&json!("7.24770579"))), Some(7.24770579));
    assert_eq!(value_as_f64(Some(&json!(2))), Some(2.0));
    assert_eq!(value_as_f64(Some(&json!("n/a"))), None);
    assert_eq!(value_as_f64(Some(&Value::Null)), None);
    assert_eq!(value_as_f64(None), None);
}

#[test]
fn worker_events_update_job_state_and_leave_an_audit_row() {
    let conn = fresh_db();
    conn.execute(
        "INSERT INTO jobs (id, modal_profile_id, status, stage, prompt, input_path, created_at) \
         VALUES ('job_1', 'modal_01', 'QUEUED', 'JOB_CREATED', 'p', 'C:/a.png', 'x')",
        [],
    )
    .unwrap();
    apply_worker_event(
        &conn,
        &json!({"type": "stage", "job_id": "job_1", "stage": "GENERATING"}),
    )
    .unwrap();
    let (status, stage, started): (String, String, Option<String>) = conn
        .query_row(
            "SELECT status, stage, started_at FROM jobs WHERE id = 'job_1'",
            [],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )
        .unwrap();
    assert_eq!(status, "RUNNING");
    assert_eq!(stage, "GENERATING");
    assert!(started.is_some());

    apply_worker_event(
        &conn,
        &json!({"type": "stage", "job_id": "job_1", "stage": "RESULT_DOWNLOADING"}),
    )
    .unwrap();
    let status: String = conn
        .query_row("SELECT status FROM jobs WHERE id = 'job_1'", [], |row| {
            row.get(0)
        })
        .unwrap();
    assert_eq!(status, "DOWNLOADING");

    apply_worker_event(
        &conn,
        &json!({"type": "completed", "job_id": "job_1", "local_output_path": "F:/out/clip.mp4"}),
    )
    .unwrap();
    let (status, stage, completed, output, progress): (
        String,
        String,
        Option<String>,
        Option<String>,
        Option<f64>,
    ) = conn
        .query_row(
            "SELECT status, stage, completed_at, output_path, progress FROM jobs WHERE id = 'job_1'",
            [],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?, row.get(4)?)),
        )
        .unwrap();
    assert_eq!(status, "COMPLETED");
    assert_eq!(stage, "COMPLETED");
    assert!(completed.is_some());
    assert_eq!(output.as_deref(), Some("F:/out/clip.mp4"));
    assert_eq!(progress, Some(100.0));

    conn.execute(
        "INSERT INTO jobs (id, status, stage, prompt, input_path, created_at) \
         VALUES ('job_2', 'RUNNING', 'GENERATING', 'p', '', 'x')",
        [],
    )
    .unwrap();
    apply_worker_event(
        &conn,
        &json!({
            "type": "failed",
            "job_id": "job_2",
            "code": "MODAL_GENERATION_FAILED",
            "message": "boom ak-0123456789abcdef0123\nsecond line"
        }),
    )
    .unwrap();
    let (status, code, message): (String, Option<String>, Option<String>) = conn
        .query_row(
            "SELECT status, error_code, error_message FROM jobs WHERE id = 'job_2'",
            [],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )
        .unwrap();
    assert_eq!(status, "FAILED");
    assert_eq!(code.as_deref(), Some("MODAL_GENERATION_FAILED"));
    let message = message.unwrap();
    assert!(!message.contains("0123456789abcdef"), "{message}");
    assert!(message.contains("<redacted>"), "{message}");
    assert!(!message.contains('\n'), "{message}");

    // Events for a job we do not know about are ignored, not errors.
    apply_worker_event(
        &conn,
        &json!({"type": "stage", "job_id": "ghost", "stage": "GENERATING"}),
    )
    .unwrap();
    assert!(apply_worker_event(&conn, &json!({"type": "stage"})).is_ok());
    let events: i64 = conn
        .query_row("SELECT COUNT(*) FROM job_events", [], |row| row.get(0))
        .unwrap();
    assert_eq!(events, 4);
}

#[test]
fn repeated_syncs_stay_duplicate_free_and_keep_older_months() {
    let conn = fresh_db();
    conn.execute(
        "INSERT INTO usage_records (modal_profile_id, job_id, source, amount, period, label, observed_at) \
         VALUES ('modal_01', NULL, 'modal_billing_report', 4.5, '2026-09', 'minimax-h3-latest-workflows', 'old')",
        [],
    )
    .unwrap();
    let october = json!({
        "period": "2026-10",
        "periods": ["2026-10"],
        "total": "1.25",
        "apps": [{"object_id": "ap-1", "description": "minimax-h3-latest-workflows", "cost": "1.25", "intervals": 1}],
        "rows": [{"object_id": "ap-1", "description": "minimax-h3-latest-workflows", "period": "2026-10", "cost": "1.25"}],
        "intervals": 1
    });
    let (intervals, objects, periods) =
        write_sync_summary(&conn, "modal_01", &october, "now").unwrap();
    assert_eq!((intervals, objects), (1, 1));
    assert_eq!(periods, vec![String::from("2026-10")]);
    write_sync_summary(&conn, "modal_01", &october, "later").unwrap();

    let count = |period_tag: &str| -> i64 {
        conn.query_row(
            "SELECT COUNT(*) FROM usage_records WHERE period = ?1",
            params![period_tag],
            |row| row.get(0),
        )
        .unwrap()
    };
    assert_eq!(count("2026-09"), 1);
    assert_eq!(count("2026-10"), 1);
    assert_eq!(latest_billing_period(&conn), "2026-10");
    let profiles = list_profiles(&conn).unwrap();
    assert_eq!(profiles[0].month_cost, 1.25);

    // A report with no intervals changes nothing at all.
    let empty = json!({"period": "2026-11", "periods": [], "total": "0", "rows": [], "apps": []});
    let (intervals, objects, periods) =
        write_sync_summary(&conn, "modal_01", &empty, "now").unwrap();
    assert_eq!((intervals, objects), (0, 0));
    assert!(periods.is_empty());
    let total: i64 = conn
        .query_row("SELECT COUNT(*) FROM usage_records", [], |row| row.get(0))
        .unwrap();
    assert_eq!(total, 2);
}

#[test]
fn sensitive_detail_is_redacted_and_clipped() {
    let message = sanitize_detail(
        "failed\nMODAL_TOKEN_SECRET=as-9876543210abcdef token=Bearer sk-abcdef0123456789 end",
        DETAIL_LIMIT,
    );
    assert!(!message.contains("9876543210abcdef"), "{message}");
    assert!(!message.contains("abcdef0123456789"), "{message}");
    assert!(!message.contains('\n'), "{message}");
    assert!(message.contains("<redacted>"), "{message}");

    let long = sanitize_detail(&"x".repeat(900), DETAIL_LIMIT);
    assert_eq!(long.chars().count(), DETAIL_LIMIT + 1);
    assert!(long.ends_with('…'));
    assert_eq!(
        sanitize_detail("  tidy   text  ", DETAIL_LIMIT),
        "tidy text"
    );
}

#[test]
fn quoted_and_nested_secrets_never_survive() {
    // The exact shapes reported by review: the quoted value used to survive.
    assert_eq!(
        sanitize_detail(r#"token="sess-abcdef123456""#, DETAIL_LIMIT),
        "token=<redacted>"
    );
    assert_eq!(
        sanitize_detail(r#"MODAL_TOKEN_SECRET="plainvalue123""#, DETAIL_LIMIT),
        "MODAL_TOKEN_SECRET=<redacted>"
    );
    // A quoted value used to stop at the quote and leave the secret in place.
    for (input, secret) in [
        (r#"token="sess-abcdef123456" done"#, "sess-abcdef123456"),
        (
            r#"MODAL_TOKEN_SECRET="plainvalue123" done"#,
            "plainvalue123",
        ),
        (
            r#"MODAL_TOKEN_SECRET = 'single-quoted-secret' end"#,
            "single-quoted-secret",
        ),
        (
            r#"MODAL_TOKEN_SECRET = "spaced-secret-321" end"#,
            "spaced-secret-321",
        ),
        (
            r#"token = `backtick-secret-222` end"#,
            "backtick-secret-222",
        ),
        (
            r#"Authorization: Bearer "quoted-bearer-secret" end"#,
            "quoted-bearer-secret",
        ),
        (
            r#"Authorization: Bearer bare-bearer-secret end"#,
            "bare-bearer-secret",
        ),
        (
            r#"{"token":"json-secret-987","other":1}"#,
            "json-secret-987",
        ),
        (
            r#"{"api":{"MODAL_TOKEN_SECRET":"nested-secret-654"}}"#,
            "nested-secret-654",
        ),
        (r#"token: colon-secret-777 end"#, "colon-secret-777"),
        (r#"token="esc\"aped-secret-111" end"#, "aped-secret-111"),
        (
            r#"token="unterminated-secret-999"#,
            "unterminated-secret-999",
        ),
        (
            r#"MODAL_TOKEN_SECRET=as-9876543210abcdef"#,
            "9876543210abcdef",
        ),
        (r#"key=ghp_abcdef0123456789"#, "abcdef0123456789"),
        (r#"token=ak-0123456789abcdef"#, "0123456789abcdef"),
        (r#"sk-abcdef0123456789"#, "abcdef0123456789"),
    ] {
        let cleaned = sanitize_detail(input, DETAIL_LIMIT);
        assert!(
            !cleaned.contains(secret),
            "leaked {secret} from {input} -> {cleaned}"
        );
        assert!(
            cleaned.contains("<redacted>"),
            "nothing redacted: {input} -> {cleaned}"
        );
    }
}

#[test]
fn redaction_markers_are_not_duplicated_or_added_without_a_value() {
    let collapsed = sanitize_detail("token=Bearer sk-abcdef0123456789 end", DETAIL_LIMIT);
    assert!(!collapsed.contains("abcdef0123456789"), "{collapsed}");
    assert_eq!(collapsed.matches("<redacted>").count(), 1, "{collapsed}");

    let already = sanitize_detail("a <redacted> <redacted> b", DETAIL_LIMIT);
    assert_eq!(already, "a <redacted> b");

    // A marker with nothing after it stays untouched and prose is preserved.
    assert_eq!(sanitize_detail("token=", DETAIL_LIMIT), "token=");
    assert_eq!(
        sanitize_detail("MODAL_TOKEN_SECRET= ", DETAIL_LIMIT),
        "MODAL_TOKEN_SECRET="
    );
    assert_eq!(
        sanitize_detail("MODAL_TOKEN_SECRET:   ", DETAIL_LIMIT),
        "MODAL_TOKEN_SECRET:"
    );
    assert_eq!(
        sanitize_detail("no token expired here", DETAIL_LIMIT),
        "no token expired here"
    );

    let clipped = sanitize_detail(&format!(r#"token="{}""#, "s".repeat(900)), DETAIL_LIMIT);
    assert!(!clipped.contains("ssss"), "{clipped}");
    assert_eq!(clipped, "token=<redacted>");
    assert_eq!(clipped.matches("<redacted>").count(), 1, "{clipped}");
}

#[test]
fn a_dead_or_unspawnable_worker_cannot_leave_a_job_running() {
    let conn = fresh_db();
    for id in ["job_running", "job_done", "job_queued"] {
        conn.execute(
            "INSERT INTO jobs (id, modal_profile_id, status, stage, prompt, input_path, created_at) \
             VALUES (?1, 'modal_01', 'RUNNING', 'GENERATING', 'p', '', 'x')",
            params![id],
        )
        .unwrap();
    }
    conn.execute(
        "UPDATE jobs SET status = 'COMPLETED', stage = 'COMPLETED' WHERE id = 'job_done'",
        [],
    )
    .unwrap();

    mark_worker_exit_row(&conn, "job_running", Some(1));
    mark_worker_exit_row(&conn, "job_done", Some(1));
    mark_spawn_failure_row(&conn, "job_queued", "python: not found");

    let row = |id: &str| -> (String, Option<String>, Option<String>) {
        conn.query_row(
            "SELECT status, error_code, completed_at FROM jobs WHERE id = ?1",
            params![id],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )
        .unwrap()
    };
    let (status, code, completed) = row("job_running");
    assert_eq!(status, "FAILED");
    assert_eq!(code.as_deref(), Some("WORKER_EXITED"));
    assert!(completed.is_some());
    // A finished job is never rewritten by a late exit report.
    assert_eq!(row("job_done").0, "COMPLETED");
    // A job that never reached a worker is reported instead of staying QUEUED.
    assert_eq!(row("job_queued").0, "FAILED");
}

#[test]
fn a_restart_closes_only_the_jobs_that_could_not_finish() {
    let conn = fresh_db();
    for (id, status) in [
        ("job_queued", "QUEUED"),
        ("job_running", "RUNNING"),
        ("job_downloading", "DOWNLOADING"),
        ("job_done", "COMPLETED"),
        ("job_cancelled", "CANCELLED"),
        ("job_failed", "FAILED"),
    ] {
        conn.execute(
            "INSERT INTO jobs (id, modal_profile_id, status, stage, prompt, input_path, created_at) \
             VALUES (?1, 'modal_01', ?2, 'GENERATING', 'p', '', 'x')",
            params![id, status],
        )
        .unwrap();
    }
    // A real failure keeps the reason it already had.
    conn.execute(
        "UPDATE jobs SET error_code = 'MODAL_GENERATION_FAILED', error_message = 'boom' \
         WHERE id = 'job_failed'",
        [],
    )
    .unwrap();

    assert_eq!(fail_interrupted_jobs(&conn).unwrap(), 3);
    let row = |id: &str| -> (String, Option<String>, Option<String>, Option<String>) {
        conn.query_row(
            "SELECT status, error_code, error_message, completed_at FROM jobs WHERE id = ?1",
            params![id],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
        )
        .unwrap()
    };
    for id in ["job_queued", "job_running", "job_downloading"] {
        let (status, code, message, completed) = row(id);
        assert_eq!(status, "FAILED", "{id}");
        assert_eq!(code.as_deref(), Some(RESTART_ERROR_CODE), "{id}");
        assert!(message.unwrap().contains("다시 시작"), "{id}");
        assert!(completed.is_some(), "{id}");
    }
    // Finished history is never rewritten, not even its own error details.
    assert_eq!(row("job_done").0, "COMPLETED");
    assert!(row("job_done").3.is_none());
    assert_eq!(row("job_cancelled").0, "CANCELLED");
    let (status, code, message, _) = row("job_failed");
    assert_eq!(status, "FAILED");
    assert_eq!(code.as_deref(), Some("MODAL_GENERATION_FAILED"));
    assert_eq!(message.as_deref(), Some("boom"));

    // A second startup has nothing left to close.
    assert_eq!(fail_interrupted_jobs(&conn).unwrap(), 0);
}

#[test]
fn late_events_cannot_resurrect_a_finished_job() {
    let conn = fresh_db();
    for (id, status) in [
        ("job_done", "COMPLETED"),
        ("job_cancelled", "CANCELLED"),
        ("job_failed", "FAILED"),
    ] {
        conn.execute(
            "INSERT INTO jobs (id, modal_profile_id, status, stage, prompt, input_path, created_at) \
             VALUES (?1, 'modal_01', ?2, 'GENERATING', 'p', '', 'x')",
            params![id, status],
        )
        .unwrap();
    }
    conn.execute(
        "UPDATE jobs SET stage = 'COMPLETED' WHERE id = 'job_done'",
        [],
    )
    .unwrap();

    for (id, stage) in [
        ("job_done", "GENERATING"),
        ("job_cancelled", "RESULT_DOWNLOADING"),
        ("job_failed", "RESULT_DOWNLOADING"),
    ] {
        apply_worker_event(
            &conn,
            &json!({"type": "stage", "job_id": id, "stage": stage, "progress": 42}),
        )
        .unwrap();
        apply_worker_event(
            &conn,
            &json!({"type": "remote_attached", "job_id": id, "function_call_id": "modal-late"}),
        )
        .unwrap();
    }
    // A replay of a terminal event is ignored as well.
    apply_worker_event(&conn, &json!({"type": "completed", "job_id": "job_failed"})).unwrap();
    apply_worker_event(
        &conn,
        &json!({"type": "failed", "job_id": "job_done", "code": "LATE", "message": "late"}),
    )
    .unwrap();

    let row = |id: &str| -> (String, String, Option<f64>) {
        conn.query_row(
            "SELECT status, stage, progress FROM jobs WHERE id = ?1",
            params![id],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )
        .unwrap()
    };
    assert_eq!(
        row("job_done"),
        (String::from("COMPLETED"), String::from("COMPLETED"), None)
    );
    assert_eq!(
        row("job_cancelled"),
        (String::from("CANCELLED"), String::from("GENERATING"), None)
    );
    assert_eq!(
        row("job_failed"),
        (String::from("FAILED"), String::from("GENERATING"), None)
    );
    let errors: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM jobs WHERE error_code IS NOT NULL",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(errors, 0);
    // Nothing was written, so the ignored events leave no audit rows either.
    let events: i64 = conn
        .query_row("SELECT COUNT(*) FROM job_events", [], |row| row.get(0))
        .unwrap();
    assert_eq!(events, 0);

    // A job still in flight keeps updating normally.
    conn.execute(
        "INSERT INTO jobs (id, modal_profile_id, status, stage, prompt, input_path, created_at) \
         VALUES ('job_live', 'modal_01', 'QUEUED', 'JOB_CREATED', 'p', '', 'x')",
        [],
    )
    .unwrap();
    apply_worker_event(
        &conn,
        &json!({"type": "stage", "job_id": "job_live", "stage": "GENERATING"}),
    )
    .unwrap();
    assert_eq!(row("job_live").0, "RUNNING");
}

#[test]
fn a_job_that_loses_its_account_before_start_is_closed_instead_of_staying_queued() {
    let conn = fresh_db();
    conn.execute(
        "INSERT INTO jobs (id, modal_profile_id, status, stage, prompt, input_path, created_at) \
         VALUES ('job_1', 'modal_01', 'QUEUED', 'JOB_CREATED', 'p', '', 'x')",
        [],
    )
    .unwrap();
    // The narrow race: the account is stopped after create_job, before start_job.
    set_profile_enabled(&conn, "modal_01", false).unwrap();
    let error = resolve_profile(&conn, &Some(String::from("modal_01"))).unwrap_err();
    mark_start_failure_row(&conn, "job_1", &error);

    let (status, code, message, completed): (
        String,
        Option<String>,
        Option<String>,
        Option<String>,
    ) = conn
        .query_row(
            "SELECT status, error_code, error_message, completed_at FROM jobs WHERE id = 'job_1'",
            [],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
        )
        .unwrap();
    assert_eq!(status, "FAILED");
    assert_eq!(code.as_deref(), Some(PROFILE_UNAVAILABLE_CODE));
    assert!(message.unwrap().contains("중지된"));
    assert!(completed.is_some());

    // A finished row is not rewritten by the same guard.
    conn.execute(
        "UPDATE jobs SET status = 'COMPLETED', stage = 'COMPLETED' WHERE id = 'job_1'",
        [],
    )
    .unwrap();
    mark_start_failure_row(&conn, "job_1", "ignored");
    let status: String = conn
        .query_row("SELECT status FROM jobs WHERE id = 'job_1'", [], |row| {
            row.get(0)
        })
        .unwrap();
    assert_eq!(status, "COMPLETED");
}

#[test]
fn recent_jobs_returns_the_newest_first_for_queue_hydration() {
    let conn = fresh_db();
    conn.execute(
        "INSERT INTO jobs (id, modal_profile_id, status, stage, prompt, input_path, created_at, completed_at, error_code, error_message) \
         VALUES ('job_old', 'modal_01', 'COMPLETED', 'COMPLETED', 'old', 'C:/a.png', '2026-09-01T00:00:00Z', '2026-09-01T00:10:00Z', NULL, NULL)",
        [],
    )
    .unwrap();
    conn.execute(
        "INSERT INTO jobs (id, modal_profile_id, status, stage, prompt, input_path, created_at, started_at) \
         VALUES ('job_new', 'modal_01', 'FAILED', 'GENERATING', 'new', '', '2026-09-02T00:00:00Z', '2026-09-02T00:01:00Z')",
        [],
    )
    .unwrap();
    conn.execute(
        "UPDATE jobs SET error_code = 'INTERRUPTED_BY_RESTART', error_message = '앱이 다시 시작되어 중단됨' \
         WHERE id = 'job_new'",
        [],
    )
    .unwrap();

    let rows = recent_jobs(&conn, 50).unwrap();
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[0].id, "job_new");
    assert_eq!(rows[0].status, "FAILED");
    assert_eq!(rows[0].error_code.as_deref(), Some(RESTART_ERROR_CODE));
    assert_eq!(rows[0].started_at.as_deref(), Some("2026-09-02T00:01:00Z"));
    assert_eq!(rows[1].id, "job_old");
    assert_eq!(
        rows[1].completed_at.as_deref(),
        Some("2026-09-01T00:10:00Z")
    );

    // The limit is honored so the queue cannot pull an unbounded history.
    assert_eq!(recent_jobs(&conn, 1).unwrap().len(), 1);
}

#[test]
fn the_active_modal_profile_returns_only_a_section_name() {
    let dir = std::env::temp_dir().join("modal-gui-active-profile-test");
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("modal.toml");
    std::fs::write(
        &path,
        "[first]\ntoken = \"a\"\ntoken = \"b\"\n\n[second]\ntoken = \"c\"\nactive = true\n",
    )
    .unwrap();
    // Only the section name comes back; token lines never leave the file read.
    assert_eq!(read_active_modal_profile(&path).as_deref(), Some("second"));
    assert!(!read_active_modal_profile(&path)
        .unwrap_or_default()
        .contains("token"));
    std::fs::write(&path, "[only]\ntoken = \"a\"\n").unwrap();
    assert_eq!(read_active_modal_profile(&path), None);
    assert_eq!(read_active_modal_profile(&dir.join("missing.toml")), None);
    let _ = std::fs::remove_dir_all(&dir);
}

fn temp_studio_file(name: &str) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join("modal-gui-studio-run-test");
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join(name);
    std::fs::write(&path, b"\x89PNG\r\n\x1a\n").unwrap();
    path
}

/// The canvas starts runs, but the pipeline underneath stays the existing job
/// path: one QUEUED row, one worker payload, one mirrored run record.
#[test]
fn studio_runs_link_the_canvas_to_the_job_pipeline() {
    use crate::studio_run::{
        apply_run_event, build_job, insert_run, list_runs, mark_run_worker_exit, StudioRunRequest,
    };
    let conn = fresh_db();
    let project = crate::studio::create_project(
        &conn,
        "실행 연결",
        r#"{"nodes":[],"assets":[],"edges":[],"shots":[]}"#,
    )
    .unwrap();
    let input = temp_studio_file("run-input.png");
    let request = StudioRunRequest {
        project_id: project.id.clone(),
        node_id: String::from("nd_video"),
        node_title: Some(String::from("영상 생성")),
        tool: String::from("modal-h3"),
        prompt: String::from("supply crate explodes in volcanic dust"),
        input_path: Some(input.to_string_lossy().to_string()),
        duration: Some(5),
        width: Some(1344),
        height: Some(768),
        seed: Some(42),
        profile_id: None,
        kind: None,
        style: None,
        lyrics: None,
        input_json: Some(String::from(r#"{"prompt":"crate"}"#)),
    };

    let (job, mode) = build_job(&request, "job_test_run").unwrap();
    assert!(matches!(mode, crate::jobs::StartMode::Video));
    assert_eq!(job.kind.as_deref(), Some("fl2v"));
    assert_eq!(job.resolution, "1344×768");
    crate::jobs::create_job_row(&conn, &job).unwrap();
    insert_run(&conn, "run_test", Some("job_test_run"), &request, "queued").unwrap();

    // The queue row keeps the link back to the canvas node.
    let (linked_project, linked_node): (Option<String>, Option<String>) = conn
        .query_row(
            "SELECT studio_project_id, studio_node_id FROM jobs WHERE id = 'job_test_run'",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap();
    assert_eq!(linked_project.as_deref(), Some(project.id.as_str()));
    assert_eq!(linked_node.as_deref(), Some("nd_video"));

    // The Modal account chosen on the node travels with the job row.
    crate::accounts::save_profile(&conn, &draft(Some("modal_01"), "기본 계정")).unwrap();
    let mut with_profile = request.clone();
    with_profile.profile_id = Some(String::from("modal_01"));
    with_profile.seed = Some(44);
    let (profile_job, _) = build_job(&with_profile, "job_profile_run").unwrap();
    crate::jobs::create_job_row(&conn, &profile_job).unwrap();
    let stored_profile: Option<String> = conn
        .query_row(
            "SELECT modal_profile_id FROM jobs WHERE id = 'job_profile_run'",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(stored_profile.as_deref(), Some("modal_01"));

    // Worker events drive the run state the canvas renders.
    apply_run_event(
        &conn,
        &json!({"type": "remote_attached", "job_id": "job_test_run", "function_call_id": "modal-job_test_run"}),
    )
    .unwrap();
    apply_run_event(
        &conn,
        &json!({"type": "stage", "job_id": "job_test_run", "stage": "GENERATING"}),
    )
    .unwrap();
    let runs = list_runs(&conn, &project.id).unwrap();
    assert_eq!(runs.len(), 1);
    assert_eq!(runs[0].status, "running");
    assert_eq!(runs[0].stage.as_deref(), Some("GENERATING"));
    assert_eq!(runs[0].node_id, "nd_video");

    apply_run_event(
        &conn,
        &json!({"type": "completed", "job_id": "job_test_run", "local_output_path": "sample-output/clip.mp4"}),
    )
    .unwrap();
    let runs = list_runs(&conn, &project.id).unwrap();
    assert_eq!(runs[0].status, "completed");
    assert_eq!(
        runs[0].output_path.as_deref(),
        Some("sample-output/clip.mp4")
    );

    // Late worker-exit events must not rewrite finished history.
    mark_run_worker_exit(&conn, "job_test_run", Some(1));
    assert_eq!(
        list_runs(&conn, &project.id).unwrap()[0].status,
        "completed"
    );

    // A run whose worker died mid-flight is closed instead of spinning forever.
    let mut second_request = request.clone();
    second_request.seed = Some(43);
    insert_run(
        &conn,
        "run_test_2",
        Some("job_test_run_2"),
        &second_request,
        "queued",
    )
    .unwrap();
    mark_run_worker_exit(&conn, "job_test_run_2", Some(1));
    let runs = list_runs(&conn, &project.id).unwrap();
    assert_eq!(runs[0].id, "run_test_2");
    assert_eq!(runs[0].status, "failed");
    assert_eq!(runs[0].error_code.as_deref(), Some("WORKER_EXITED"));
}

#[test]
fn studio_run_requests_are_validated_before_a_worker_starts() {
    use crate::studio_run::{build_job, StudioRunRequest};
    let base = StudioRunRequest {
        project_id: String::from("prj_1"),
        node_id: String::from("nd_1"),
        node_title: None,
        tool: String::from("modal-h3"),
        prompt: String::new(),
        input_path: None,
        duration: None,
        width: None,
        height: None,
        seed: None,
        profile_id: None,
        kind: None,
        style: None,
        lyrics: None,
        input_json: None,
    };

    assert!(build_job(&base, "job_1").is_err());

    let mut with_prompt = base.clone();
    with_prompt.prompt = String::from("a scene");
    let (job, mode) = build_job(&with_prompt, "job_1").unwrap();
    assert!(matches!(mode, crate::jobs::StartMode::Video));
    assert_eq!(job.kind.as_deref(), Some("t2v"));
    // 노드에서 고른 Modal 계정이 작업 기록까지 그대로 전달된다.
    assert_eq!(job.profile_id, None);
    let mut with_profile = with_prompt.clone();
    with_profile.profile_id = Some(String::from("modal_02"));
    let (job, _) = build_job(&with_profile, "job_1b").unwrap();
    assert_eq!(job.profile_id.as_deref(), Some("modal_02"));

    let mut fl2v = with_prompt.clone();
    fl2v.kind = Some(String::from("fl2v"));
    assert!(build_job(&fl2v, "job_2").is_err());

    let mut missing_input = with_prompt.clone();
    missing_input.input_path = Some(String::from("C:/missing/nope.png"));
    assert!(build_job(&missing_input, "job_3").is_err());

    let mut unknown_tool = with_prompt.clone();
    unknown_tool.tool = String::from("higgsfield");
    assert!(build_job(&unknown_tool, "job_4").is_err());

    let mut music = base.clone();
    music.tool = String::from("yue2-music");
    music.prompt = String::from("dark synth pulse");
    let (job, mode) = build_job(&music, "job_5").unwrap();
    assert!(matches!(mode, crate::jobs::StartMode::Music));
    assert_eq!(job.kind.as_deref(), Some("music"));
    assert_eq!(job.style.as_deref(), Some("dark synth pulse"));
}

#[test]
fn studio_finish_run_requires_the_result_file_to_exist() {
    use crate::studio_run::{finish_run, insert_run, list_runs, StudioRunRequest};
    let conn = fresh_db();
    let project = crate::studio::create_project(
        &conn,
        "로컬 렌더",
        r#"{"nodes":[],"assets":[],"edges":[],"shots":[]}"#,
    )
    .unwrap();
    let request = StudioRunRequest {
        project_id: project.id.clone(),
        node_id: String::from("nd_edit"),
        node_title: None,
        tool: String::from("local-ffmpeg"),
        prompt: String::new(),
        input_path: None,
        duration: None,
        width: None,
        height: None,
        seed: None,
        profile_id: None,
        kind: None,
        style: None,
        lyrics: None,
        input_json: None,
    };
    insert_run(&conn, "run_local", None, &request, "running").unwrap();

    assert!(finish_run(
        &conn,
        "run_local",
        "completed",
        Some("F:/missing/out.mp4"),
        None,
        None
    )
    .is_err());
    assert!(finish_run(&conn, "run_local", "nonsense", None, None, None).is_err());

    let output = temp_studio_file("render-output.mp4");
    let finished = finish_run(
        &conn,
        "run_local",
        "completed",
        Some(&output.to_string_lossy()),
        None,
        Some("ast_1"),
    )
    .unwrap();
    assert_eq!(finished.status, "completed");
    assert_eq!(finished.result_asset_id.as_deref(), Some("ast_1"));
    assert_eq!(
        finished.output_path.as_deref(),
        Some(output.to_string_lossy().as_ref())
    );
    let runs = list_runs(&conn, &project.id).unwrap();
    assert_eq!(runs.len(), 1);
}

#[test]
fn restart_closes_runs_that_cannot_continue() {
    use crate::studio_run::{
        fail_interrupted_runs, finish_run, insert_run, list_runs, StudioRunRequest,
    };
    let conn = fresh_db();
    let project = crate::studio::create_project(
        &conn,
        "재시작",
        r#"{"nodes":[],"assets":[],"edges":[],"shots":[]}"#,
    )
    .unwrap();
    let request = StudioRunRequest {
        project_id: project.id.clone(),
        node_id: String::from("nd_1"),
        node_title: None,
        tool: String::from("local-ffmpeg"),
        prompt: String::new(),
        input_path: None,
        duration: None,
        width: None,
        height: None,
        seed: None,
        profile_id: None,
        kind: None,
        style: None,
        lyrics: None,
        input_json: None,
    };
    insert_run(&conn, "run_open", None, &request, "running").unwrap();
    let mut queued_request = request.clone();
    queued_request.seed = Some(2);
    insert_run(&conn, "run_queued", None, &queued_request, "queued").unwrap();
    let mut done_request = request.clone();
    done_request.seed = Some(3);
    insert_run(&conn, "run_done", None, &done_request, "running").unwrap();
    let output = temp_studio_file("restart-output.mp4");
    finish_run(
        &conn,
        "run_done",
        "completed",
        Some(&output.to_string_lossy()),
        None,
        None,
    )
    .unwrap();

    let changed = fail_interrupted_runs(&conn).unwrap();
    assert_eq!(changed, 2);
    let runs = list_runs(&conn, &project.id).unwrap();
    let by_id = |id: &str| runs.iter().find(|run| run.id == id).unwrap();
    assert_eq!(by_id("run_open").status, "failed");
    assert_eq!(
        by_id("run_open").error_code.as_deref(),
        Some("INTERRUPTED_BY_RESTART")
    );
    assert_eq!(by_id("run_queued").status, "failed");
    // Finished history is never rewritten by a restart.
    assert_eq!(by_id("run_done").status, "completed");
    assert_eq!(fail_interrupted_runs(&conn).unwrap(), 0);
}

fn studio_run_request(project_id: &str, seed: i64) -> crate::studio_run::StudioRunRequest {
    crate::studio_run::StudioRunRequest {
        project_id: project_id.to_string(),
        node_id: String::from("nd_contract"),
        node_title: Some(String::from("계약 실행")),
        tool: String::from("local-contract"),
        prompt: String::from("same prompt"),
        input_path: None,
        duration: None,
        width: None,
        height: None,
        seed: Some(seed),
        profile_id: None,
        kind: None,
        style: None,
        lyrics: None,
        input_json: Some(String::from(r#"{"input":"same"}"#)),
    }
}

#[test]
fn studio_cancel_run_records_live_remote_and_local_outcomes() {
    use crate::studio_run::{cancel_run, insert_run};
    let conn = fresh_db();
    let project =
        crate::studio::create_project(&conn, "취소 계약", r#"{"nodes":[],"assets":[]}"#).unwrap();

    let live = studio_run_request(&project.id, 1);
    insert_run(&conn, "run_cancel_live", Some("job_live"), &live, "running").unwrap();
    let row = cancel_run(&conn, "run_cancel_live", true).unwrap();
    assert_eq!(row.status, "cancel_requested");
    assert_eq!(row.stage.as_deref(), Some("cancel_requested"));
    assert_eq!(row.error_message, None);

    let remote = studio_run_request(&project.id, 2);
    insert_run(
        &conn,
        "run_cancel_remote",
        Some("job_gone"),
        &remote,
        "running",
    )
    .unwrap();
    let row = cancel_run(&conn, "run_cancel_remote", false).unwrap();
    assert_eq!(row.status, "cancel_requested");
    assert_eq!(
        row.error_message.as_deref(),
        Some("원격 실행 상태를 확인할 수 없습니다. 앱을 다시 시작하면 중단으로 기록됩니다.")
    );

    let local = studio_run_request(&project.id, 3);
    insert_run(&conn, "run_cancel_local", None, &local, "running").unwrap();
    let row = cancel_run(&conn, "run_cancel_local", false).unwrap();
    assert_eq!(row.status, "cancel_requested");
    assert_eq!(
        row.error_message.as_deref(),
        Some("이 실행 도구는 원격 취소를 지원하지 않습니다. 완료되면 결과가 기록됩니다.")
    );
}

#[test]
fn studio_cancel_run_rejects_terminal_runs() {
    use crate::studio_run::{cancel_run, insert_run};
    let conn = fresh_db();
    let project =
        crate::studio::create_project(&conn, "종료 취소", r#"{"nodes":[],"assets":[]}"#).unwrap();
    let request = studio_run_request(&project.id, 4);
    insert_run(&conn, "run_terminal", None, &request, "completed").unwrap();
    match cancel_run(&conn, "run_terminal", false) {
        Err(error) => assert_eq!(error, "이미 끝난 실행은 취소할 수 없습니다."),
        Ok(_) => panic!("terminal run cancellation must fail"),
    }
}

#[test]
fn studio_restart_confirms_cancel_requested_as_cancelled() {
    use crate::studio_run::{cancel_run, fail_interrupted_runs, insert_run, list_runs};
    let conn = fresh_db();
    let project =
        crate::studio::create_project(&conn, "취소 복구", r#"{"nodes":[],"assets":[]}"#).unwrap();
    let request = studio_run_request(&project.id, 5);
    insert_run(&conn, "run_recover_cancel", None, &request, "running").unwrap();
    cancel_run(&conn, "run_recover_cancel", false).unwrap();
    assert_eq!(fail_interrupted_runs(&conn).unwrap(), 1);
    let row = &list_runs(&conn, &project.id).unwrap()[0];
    assert_eq!(row.status, "cancelled");
    assert_eq!(row.stage.as_deref(), Some("cancelled"));
    assert!(row
        .error_message
        .as_deref()
        .unwrap()
        .contains("원격 취소 결과를 확인하지 못했습니다"));
}

#[test]
fn studio_duplicate_submission_guard_respects_seed_and_age() {
    use crate::studio_run::{insert_run, submission_key};
    let conn = fresh_db();
    let project =
        crate::studio::create_project(&conn, "중복 제출", r#"{"nodes":[],"assets":[]}"#).unwrap();
    let request = studio_run_request(&project.id, 10);
    assert_eq!(submission_key(&request).len(), 8);
    insert_run(&conn, "run_first", None, &request, "running").unwrap();
    let error = insert_run(&conn, "run_duplicate", None, &request, "running").unwrap_err();
    assert_eq!(error, "같은 입력으로 이미 제출한 실행이 있습니다. 잠시 뒤에 다시 실행하거나 seed·입력을 바꿔 새 변주로 실행하세요.");

    let different_seed = studio_run_request(&project.id, 11);
    insert_run(&conn, "run_variant", None, &different_seed, "running").unwrap();

    conn.execute(
        "UPDATE studio_runs SET status = 'completed', created_at = '2020-01-01T00:00:00Z' \
         WHERE id = 'run_first'",
        [],
    )
    .unwrap();
    insert_run(&conn, "run_after_window", None, &request, "running").unwrap();
}

/// A result that arrives after a cancel request must keep both facts instead of
/// silently dropping the request, which is what a plain COALESCE would do.
#[test]
fn a_result_after_a_cancel_request_records_both_facts() {
    use crate::studio_run::{cancel_run, finish_run, insert_run, StudioRunRequest};
    let conn = fresh_db();
    let project = crate::studio::create_project(
        &conn,
        "취소 뒤 결과",
        r#"{"nodes":[],"assets":[],"edges":[],"shots":[]}"#,
    )
    .unwrap();
    let output = temp_studio_file("cancel-then-complete.mp4");
    std::fs::write(&output, b"clip").unwrap();
    let request = StudioRunRequest {
        project_id: project.id.clone(),
        node_id: String::from("nd_typo"),
        node_title: Some(String::from("타이포")),
        tool: String::from("local-ffmpeg"),
        prompt: String::new(),
        input_path: None,
        duration: Some(4),
        width: None,
        height: None,
        seed: None,
        profile_id: None,
        kind: None,
        style: None,
        lyrics: None,
        input_json: Some(String::from(r#"{"copy":["한 줄"]}"#)),
    };
    insert_run(&conn, "run_cancel_then_done", None, &request, "running").unwrap();
    let cancelled = cancel_run(&conn, "run_cancel_then_done", false).unwrap();
    assert_eq!(cancelled.status, "cancel_requested");

    let finished = finish_run(
        &conn,
        "run_cancel_then_done",
        "completed",
        Some(output.to_string_lossy().as_ref()),
        None,
        None,
    )
    .unwrap();
    assert_eq!(finished.status, "completed");
    assert_eq!(
        finished.error_message.as_deref(),
        Some("중단을 요청한 뒤 도착한 결과입니다. 결과 파일은 보관했습니다.")
    );
    std::fs::remove_file(&output).ok();
}

#[test]
fn studio_finish_run_accepts_prepared_only_with_an_artifact() {
    use crate::studio_run::{finish_run, insert_run};
    let conn = fresh_db();
    let project =
        crate::studio::create_project(&conn, "프로젝트 핸드오프", r#"{"nodes":[],"assets":[]}"#)
            .unwrap();
    let request = studio_run_request(&project.id, 20);
    insert_run(&conn, "run_prepared", None, &request, "running").unwrap();
    assert!(finish_run(
        &conn,
        "run_prepared",
        "prepared",
        Some("C:/missing/project.jsx"),
        None,
        None,
    )
    .is_err());
    let artifact = temp_studio_file("handoff.jsx");
    let row = finish_run(
        &conn,
        "run_prepared",
        "prepared",
        Some(artifact.to_string_lossy().as_ref()),
        None,
        None,
    )
    .unwrap();
    assert_eq!(row.status, "prepared");
    assert_eq!(row.stage.as_deref(), Some("prepared"));
}

#[test]
fn studio_usage_summary_classifies_confirmed_pending_and_unknown() {
    use crate::studio_run::insert_run;
    use crate::usage::studio_usage_summary_rows;
    let conn = fresh_db();
    let project =
        crate::studio::create_project(&conn, "비용 귀속", r#"{"nodes":[],"assets":[]}"#).unwrap();
    for (run_id, job_id, status, seed) in [
        ("run_confirmed", "job_confirmed", "completed", 31),
        ("run_pending", "job_pending", "running", 32),
        ("run_unknown", "job_unknown", "failed", 33),
    ] {
        let request = studio_run_request(&project.id, seed);
        insert_run(&conn, run_id, Some(job_id), &request, status).unwrap();
    }
    conn.execute(
        "INSERT INTO usage_records \
         (modal_profile_id, job_id, source, amount, period, observed_at) \
         VALUES ('modal_01', 'job_confirmed', 'job-test', 1.25, '2026-09', '2026-09-27T00:00:00Z'), \
                ('modal_01', 'job_confirmed', 'job-test', 0.75, '2026-09', '2026-09-27T00:01:00Z')",
        [],
    )
    .unwrap();
    let summary = studio_usage_summary_rows(&conn, &project.id).unwrap();
    assert_eq!(summary["confirmed_total"].as_f64(), Some(2.0));
    assert_eq!(summary["priced_runs"].as_i64(), Some(1));
    assert_eq!(summary["unpriced_runs"].as_i64(), Some(2));
    let runs = summary["runs"].as_array().unwrap();
    let by_id = |id: &str| runs.iter().find(|run| run["run_id"] == id).unwrap();
    assert_eq!(by_id("run_confirmed")["amount"].as_f64(), Some(2.0));
    assert_eq!(by_id("run_confirmed")["amount_kind"], "confirmed");
    assert_eq!(by_id("run_pending")["amount"], Value::Null);
    assert_eq!(by_id("run_pending")["amount_kind"], "pending");
    assert_eq!(by_id("run_unknown")["amount"], Value::Null);
    assert_eq!(by_id("run_unknown")["amount_kind"], "unknown");
}

#[test]
fn studio_export_import_round_trip_uses_exported_asset_and_no_secrets() {
    use crate::studio_export::{export_project, import_project};
    let conn = fresh_db();
    let root = std::env::temp_dir().join(format!(
        "modal-gui-studio-export-test-{}",
        chrono::Utc::now().timestamp_nanos_opt().unwrap()
    ));
    let source = root.join("source.png");
    let export_dir = root.join("export");
    std::fs::create_dir_all(&root).unwrap();
    std::fs::write(&source, b"real asset bytes").unwrap();
    let document = json!({
        "nodes": [{"id": "typo", "config": {"font": "Definitely Missing Test Font", "token": "must-remove"}}],
        "assets": [{"id": "ast_1", "name": "source.png", "kind": "image", "storedPath": source.to_string_lossy(), "hash": "1234567890abcdef", "auth_ref": "must-remove"}],
        "connections": [],
    });
    let project = crate::studio::create_project(&conn, "내보내기", &document.to_string()).unwrap();
    let result = export_project(&conn, &project.id, &export_dir).unwrap();
    assert_eq!(result["asset_count"].as_u64(), Some(1));
    let manifest: Value =
        serde_json::from_slice(&std::fs::read(export_dir.join("manifest.json")).unwrap()).unwrap();
    assert_eq!(manifest["secrets_included"], false);
    let exported: Value =
        serde_json::from_slice(&std::fs::read(export_dir.join("project.json")).unwrap()).unwrap();
    assert!(!exported.to_string().contains("must-remove"));

    let studio_root = root.join("studio-root");
    let imported = import_project(&conn, &studio_root, &export_dir).unwrap();
    let imported_id = imported["project_id"].as_str().unwrap();
    let loaded = crate::studio::load_project(&conn, imported_id).unwrap();
    // 첫 리비전은 문서 그대로, 두 번째 리비전은 프로젝트 폴더로 복사한 경로를 담는다.
    assert!(loaded.revision >= 1);
    assert_eq!(loaded.name, "내보내기 (가져옴)");
    let imported_document: Value = serde_json::from_str(&loaded.document_json).unwrap();
    let imported_path = imported_document["assets"][0]["storedPath"]
        .as_str()
        .unwrap();
    assert!(std::path::Path::new(imported_path).is_file());
    // 가져온 소재는 내보낸 폴더가 아니라 새 프로젝트 폴더로 복사된다.
    let imported_abs = std::path::Path::new(imported_path).canonicalize().unwrap();
    assert!(imported_abs.starts_with(studio_root.canonicalize().unwrap()));
    assert!(!imported_abs.starts_with(export_dir.canonicalize().unwrap()));
    std::fs::remove_dir_all(&root).unwrap();
}

/// A motion or edit spec holds its clips as plain paths. Exporting only the
/// registered assets would leave those files behind and the imported project
/// would render nothing, so the referenced files travel with the export.
#[test]
fn studio_export_copies_files_referenced_by_specs() {
    use crate::studio_export::export_project;
    let conn = fresh_db();
    let root = std::env::temp_dir().join(format!(
        "modal-gui-studio-export-ref-{}",
        chrono::Utc::now().timestamp_nanos_opt().unwrap()
    ));
    let export_dir = root.join("export");
    std::fs::create_dir_all(&root).unwrap();
    let clip = root.join("background.mp4");
    std::fs::write(&clip, b"clip bytes").unwrap();
    let spec = root.join("run_spec.motion.json");
    std::fs::write(
        &spec,
        json!({
            "name": "run_spec",
            "audio": root.join("missing-silence.wav").to_string_lossy(),
            "shots": [{"clip": clip.to_string_lossy(), "in": 0.0, "out": 4.0}],
        })
        .to_string(),
    )
    .unwrap();
    let document = json!({
        "nodes": [{"id": "typo"}],
        "assets": [{"id": "ast_spec", "name": "run_spec.motion.json", "kind": "other", "storedPath": spec.to_string_lossy(), "hash": "abcdef1234567890"}],
    });
    let project = crate::studio::create_project(&conn, "스펙 내보내기", &document.to_string()).unwrap();
    export_project(&conn, &project.id, &export_dir).unwrap();

    let manifest: Value =
        serde_json::from_slice(&std::fs::read(export_dir.join("manifest.json")).unwrap()).unwrap();
    let referenced = manifest["referenced"].as_array().unwrap();
    assert_eq!(referenced.len(), 1);
    let copied = export_dir.join(referenced[0]["file"].as_str().unwrap());
    assert!(copied.is_file(), "참조 클립이 함께 복사되어야 합니다");

    let exported_spec: Value = serde_json::from_slice(
        &std::fs::read(export_dir.join("assets").join("abcdef12-run_spec.motion.json")).unwrap(),
    )
    .unwrap();
    let exported_clip = exported_spec["shots"][0]["clip"].as_str().unwrap();
    assert!(exported_clip.starts_with(export_dir.to_string_lossy().as_ref()));
    assert!(std::path::Path::new(exported_clip).is_file());
    // 없는 참조는 조용히 넘어가고 남은 경로를 그대로 둔다.
    assert!(exported_spec["audio"]
        .as_str()
        .unwrap()
        .ends_with("missing-silence.wav"));

    // 가져오기는 참조 파일까지 프로젝트 폴더로 복사하고, 구성 안의 경로를
    // 새 위치로 바꾼다. 그래야 내보낸 폴더를 지워도 렌더가 이어진다.
    use crate::studio_export::import_project;
    let studio_root = root.join("studio-root");
    let imported = import_project(&conn, &studio_root, &export_dir).unwrap();
    let imported_id = imported["project_id"].as_str().unwrap();
    let loaded = crate::studio::load_project(&conn, imported_id).unwrap();
    let imported_document: Value = serde_json::from_str(&loaded.document_json).unwrap();
    let imported_spec_path = imported_document["assets"][0]["storedPath"].as_str().unwrap();
    let imported_spec: Value =
        serde_json::from_slice(&std::fs::read(imported_spec_path).unwrap()).unwrap();
    let imported_clip = imported_spec["shots"][0]["clip"].as_str().unwrap();
    assert!(std::path::Path::new(imported_clip).is_file());
    assert!(
        imported_clip
            .to_lowercase()
            .contains(&imported_id.to_lowercase()),
        "복사한 구성이 프로젝트 폴더를 가리켜야 합니다: {imported_clip}"
    );
    std::fs::remove_dir_all(&root).unwrap();
}

/// A font the user actually has must not be reported as missing after import,
/// even when the document stores a Korean display name like "맑은 고딕".
#[test]
fn imported_font_names_resolve_to_installed_files() {
    use crate::studio_export::{font_file_candidates, missing_fonts};
    assert!(font_file_candidates("맑은 고딕").contains(&String::from("malgunbd")));
    assert!(font_file_candidates("Pretendard Bold").contains(&String::from("pretendard-bold")));

    let missing = missing_fonts(&[
        String::from("arial"),
        String::from("No Such Font 9000"),
    ]);
    assert_eq!(missing, vec![String::from("No Such Font 9000")]);
}

/// 생성은 끝났는데 결과를 받지 못한 실행은 생성부터 다시 하지 않는다.
/// 원격 경로를 남겨 두고 결과 수신만 다시 시도할 수 있어야 한다.
#[test]
fn a_remote_result_can_be_fetched_again_without_regenerating() {
    use crate::studio_run::{
        apply_run_event, finish_run, insert_run, list_runs, prepare_retry_download,
        StudioRunRequest,
    };
    let conn = fresh_db();
    let project =
        crate::studio::create_project(&conn, "다시 받기", r#"{"nodes":[],"assets":[]}"#).unwrap();
    let request = StudioRunRequest {
        project_id: project.id.clone(),
        node_id: String::from("nd_video"),
        node_title: Some(String::from("영상 생성")),
        tool: String::from("modal-h3"),
        prompt: String::from("프롬프트"),
        input_path: None,
        duration: Some(5),
        width: None,
        height: None,
        seed: None,
        profile_id: None,
        kind: Some(String::from("t2v")),
        style: None,
        lyrics: None,
        input_json: None,
    };
    insert_run(&conn, "run_fetch", Some("job_fetch"), &request, "queued").unwrap();
    apply_run_event(
        &conn,
        &json!({
            "type": "cancelled",
            "job_id": "job_fetch",
            "message": "원격 생성이 끝났지만 중단 요청되어 결과를 내려받지 않았습니다.",
            "remote_output_path": "clip-0001.mp4",
        }),
    )
    .unwrap();
    let row = &list_runs(&conn, &project.id).unwrap()[0];
    assert_eq!(row.status, "cancelled");
    assert_eq!(row.remote_output_path.as_deref(), Some("clip-0001.mp4"));
    assert!(row
        .error_message
        .as_deref()
        .unwrap()
        .contains("원격 결과: clip-0001.mp4"));

    let (updated, message, _profile) = prepare_retry_download(&conn, "run_fetch").unwrap();
    assert_eq!(updated.status, "downloading");
    assert_eq!(message["type"], "fetch_result");
    assert_eq!(message["job_id"], "job_fetch");
    assert_eq!(message["remote_output_path"], "clip-0001.mp4");
    assert_eq!(message["kind"], "video");

    // 원격 경로가 없는 실행은 생성부터 다시 해야 한다.
    let other = StudioRunRequest {
        node_id: String::from("nd_video_2"),
        input_json: Some(String::from(r#"{"prompt":"다른 실행"}"#)),
        ..request
    };
    insert_run(&conn, "run_no_remote", None, &other, "running").unwrap();
    finish_run(&conn, "run_no_remote", "failed", None, Some("생성 실패"), None).unwrap();
    let error = prepare_retry_download(&conn, "run_no_remote").unwrap_err();
    assert!(error.contains("다시 받을 원격 결과가 없습니다"));
}

#[test]
fn studio_templates_save_list_delete_and_validate_documents() {
    use crate::studio_templates::{
        delete_template, list_templates, save_template, StudioTemplateInput,
    };
    let conn = fresh_db();
    let input = StudioTemplateInput {
        id: None,
        name: String::from("제품 광고"),
        description: Some(String::from("세 장면 구성")),
        document_json: String::from(r#"{"nodes":[{"id":"a"},{"id":"b"}],"assets":[]}"#),
    };
    let saved = save_template(&conn, &input).unwrap();
    assert!(saved.id.starts_with("tpl_"));
    let rows = list_templates(&conn).unwrap();
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].node_count, 2);

    let invalid = StudioTemplateInput {
        id: None,
        name: String::from("손상"),
        description: None,
        document_json: String::from("{oops"),
    };
    assert!(save_template(&conn, &invalid).is_err());
    let no_nodes = StudioTemplateInput {
        document_json: String::from(r#"{"assets":[]}"#),
        ..invalid
    };
    assert!(save_template(&conn, &no_nodes).is_err());
    delete_template(&conn, &saved.id).unwrap();
    assert!(list_templates(&conn).unwrap().is_empty());
}

#[test]
fn connection_registry_validates_configs_and_keeps_tool_choices() {
    use crate::connections::{
        delete_connection, list_connections, list_tools, save_connection, set_tool_enabled,
        store_tools, ConnectionInput, ConnectionToolRow,
    };
    let conn = fresh_db();

    // A local MCP connection without an executable is rejected up front.
    let nameless = ConnectionInput {
        id: None,
        name: String::from("실행 파일 없음"),
        kind: String::from("mcp-stdio"),
        config: Some(json!({})),
        auth_ref: None,
        enabled: None,
    };
    assert!(save_connection(&conn, &nameless).is_err());

    let url_less = ConnectionInput {
        id: None,
        name: String::from("URL 없음"),
        kind: String::from("mcp-http"),
        config: Some(json!({})),
        auth_ref: None,
        enabled: None,
    };
    assert!(save_connection(&conn, &url_less).is_err());

    let input = ConnectionInput {
        id: None,
        name: String::from("테스트 MCP"),
        kind: String::from("mcp-stdio"),
        config: Some(json!({"command": "python", "args": ["tools/test_mcp_server.py"]})),
        auth_ref: None,
        enabled: None,
    };
    let row = save_connection(&conn, &input).unwrap();
    assert_eq!(row.status, "saved");
    assert!(row.enabled);

    let tool = ConnectionToolRow {
        connection_id: row.id.clone(),
        name: String::from("echo"),
        description: Some(String::from("first")),
        input_schema: json!({"type": "object"}),
        enabled: true,
    };
    store_tools(&conn, &row.id, &[tool.clone()]).unwrap();
    set_tool_enabled(&conn, &row.id, "echo", false).unwrap();
    // A refresh updates the schema but must not re-enable a tool the user turned off.
    let refreshed = ConnectionToolRow {
        description: Some(String::from("second")),
        ..tool.clone()
    };
    store_tools(&conn, &row.id, &[refreshed]).unwrap();
    let tools = list_tools(&conn, &row.id).unwrap();
    assert_eq!(tools.len(), 1);
    assert_eq!(tools[0].description.as_deref(), Some("second"));
    assert!(!tools[0].enabled);

    let rows = list_connections(&conn).unwrap();
    assert_eq!(rows.len(), 1);
    assert_eq!(rows[0].tool_count, 1);

    delete_connection(&conn, &row.id).unwrap();
    assert!(list_connections(&conn).unwrap().is_empty());
    assert!(list_tools(&conn, &row.id).unwrap().is_empty());
}

/// A tool the server no longer reports must disappear from the cache. If it
/// stayed, the pre-run compatibility check would pass for a tool that is gone
/// and the call would go out anyway.
#[test]
fn refreshing_the_tool_cache_drops_tools_the_server_removed() {
    use crate::connections::{list_tools, store_tools, ConnectionToolRow};
    let conn = fresh_db();
    let tool = |name: &str| ConnectionToolRow {
        connection_id: String::from("conn_cache"),
        name: String::from(name),
        description: None,
        input_schema: json!({"type": "object", "properties": {"text": {"type": "string"}}}),
        enabled: true,
    };
    store_tools(&conn, "conn_cache", &[tool("keep"), tool("removed")]).unwrap();
    let names: Vec<String> = list_tools(&conn, "conn_cache")
        .unwrap()
        .into_iter()
        .map(|row| row.name)
        .collect();
    assert_eq!(names, vec![String::from("keep"), String::from("removed")]);

    store_tools(&conn, "conn_cache", &[tool("keep")]).unwrap();
    let names: Vec<String> = list_tools(&conn, "conn_cache")
        .unwrap()
        .into_iter()
        .map(|row| row.name)
        .collect();
    assert_eq!(names, vec![String::from("keep")]);

    // A user-disabled tool keeps its flag while it is still on the server.
    crate::connections::set_tool_enabled(&conn, "conn_cache", "keep", false).unwrap();
    store_tools(&conn, "conn_cache", &[tool("keep")]).unwrap();
    let kept = list_tools(&conn, "conn_cache").unwrap();
    assert_eq!(kept.len(), 1);
    assert!(!kept[0].enabled);
}

/// The client talks to a real stdio server: initialize, tools/list and
/// tools/call, including an error answer and a call that never answers.
#[test]
fn mcp_stdio_client_matches_a_real_server() {
    use crate::connections::{call_tool, probe};
    let root = crate::paths::repo_root();
    let script = root.join("tools").join("test_mcp_server.py");
    let config = json!({
        "command": "python",
        "args": [script.to_string_lossy()],
        "cwd": root.to_string_lossy(),
    });
    let timeout = std::time::Duration::from_secs(30);

    let (server, tools) = probe(&config, timeout, "conn_test").unwrap();
    assert_eq!(
        server
            .get("serverInfo")
            .and_then(|value| value.get("name"))
            .and_then(Value::as_str),
        Some("modal-gui-test-server")
    );
    let names: Vec<&str> = tools.iter().map(|tool| tool.name.as_str()).collect();
    for expected in ["echo", "write_frame", "slow", "fail"] {
        assert!(names.contains(&expected), "{names:?}");
    }

    let echoed = call_tool(&config, timeout, "echo", json!({"text": "안녕"})).unwrap();
    let text = echoed
        .get("content")
        .and_then(Value::as_array)
        .and_then(|items| items.first())
        .and_then(|item| item.get("text"))
        .and_then(Value::as_str)
        .unwrap_or_default();
    assert_eq!(text, "echo: 안녕");

    let written = call_tool(
        &config,
        timeout,
        "write_frame",
        json!({"name": "rust-test"}),
    )
    .unwrap();
    let path = written
        .get("structuredContent")
        .and_then(|value| value.get("path"))
        .and_then(Value::as_str)
        .unwrap_or_default();
    assert!(std::path::Path::new(path).is_file(), "{path}");

    // A tool that reports failure is a result, not a transport error.
    let failure = call_tool(&config, timeout, "fail", json!({})).unwrap();
    assert_eq!(failure.get("isError").and_then(Value::as_bool), Some(true));

    // A tool that never answers must be reported instead of hanging the app.
    let short = std::time::Duration::from_millis(700);
    let timed_out = call_tool(&config, short, "slow", json!({"seconds": 10}));
    assert!(timed_out.is_err());
}

// ---------------------------------------------------------------------------
// ChatGPT OAuth
// ---------------------------------------------------------------------------

fn start_mock_oauth() -> (std::process::Child, u16) {
    start_mock_oauth_with_delay(0)
}

/// Same mock server, but authorization-code token responses are delayed so a
/// cancel arriving during the exchange can be observed.
fn start_mock_oauth_with_delay(token_delay_ms: u32) -> (std::process::Child, u16) {
    use std::io::BufRead;
    let script = crate::paths::repo_root()
        .join("tools")
        .join("test_oauth_server.py");
    let mut child = std::process::Command::new("python")
        .arg(script)
        .args(["--port", "0", "--token-delay-ms", &token_delay_ms.to_string()])
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .spawn()
        .expect("mock oauth server");
    let stdout = child.stdout.take().expect("stdout");
    let mut reader = std::io::BufReader::new(stdout);
    let mut line = String::new();
    reader.read_line(&mut line).expect("port line");
    let port = line
        .trim()
        .rsplit(' ')
        .next()
        .and_then(|value| value.parse::<u16>().ok())
        .expect("port number");
    (child, port)
}

fn free_port() -> u16 {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").expect("free port");
    listener.local_addr().expect("addr").port()
}

fn test_endpoints(token_port: u16, callback_port: u16) -> crate::chatgpt_auth::OAuthEndpoints {
    crate::chatgpt_auth::OAuthEndpoints {
        authorize_url: format!("http://127.0.0.1:{token_port}/oauth/authorize"),
        token_url: format!("http://127.0.0.1:{token_port}/oauth/token"),
        client_id: String::from("test-client"),
        scope: String::from("openid profile email offline_access"),
        redirect_host: String::from("127.0.0.1"),
        redirect_port: callback_port,
        redirect_path: String::from("/auth/callback"),
        originator: String::from("modal-gui-test"),
    }
}

fn query_params(url: &str) -> std::collections::HashMap<String, String> {
    let query = url.split_once('?').map(|(_, value)| value).unwrap_or("");
    let (_, params) = crate::chatgpt_auth::parse_target(&format!("/?{query}"));
    params
}

#[test]
fn chatgpt_pkce_matches_the_rfc_vector() {
    // RFC 7636 appendix B.
    assert_eq!(
        crate::chatgpt_auth::pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"),
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    );
}

#[test]
fn chatgpt_callback_accepts_only_the_matching_state() {
    use crate::chatgpt_auth::{parse_target, validate_callback};
    let (path, params) = parse_target("/auth/callback?code=code-abc&state=st-1");
    assert_eq!(path, "/auth/callback");
    assert_eq!(validate_callback(&params, "st-1").unwrap(), "code-abc");
    assert!(validate_callback(&params, "st-2").is_err());
    assert!(validate_callback(&params, "").is_err());

    // Percent-encoded values survive the round trip.
    let (_, encoded) = parse_target("/auth/callback?code=code-a%2Bb&state=st%201");
    assert_eq!(encoded.get("code").map(String::as_str), Some("code-a+b"));
    assert_eq!(validate_callback(&encoded, "st 1").unwrap(), "code-a+b");

    // A denial answered by the provider is reported with its description.
    let (_, denial) =
        parse_target("/auth/callback?error=access_denied&error_description=nope&state=st-1");
    let message = validate_callback(&denial, "st-1").unwrap_err();
    assert!(message.contains("access_denied"), "{message}");
    assert!(message.contains("nope"), "{message}");
}

#[test]
fn chatgpt_account_claims_are_read_from_tokens() {
    use crate::chatgpt_auth::{extract_account_id, extract_email};
    use base64::Engine;
    fn jwt(payload: serde_json::Value) -> String {
        let header = base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(b"{\"alg\":\"none\"}");
        let body = base64::engine::general_purpose::URL_SAFE_NO_PAD
            .encode(serde_json::to_vec(&payload).unwrap());
        format!("{header}.{body}.signature")
    }
    let namespaced = jwt(json!({
        "email": "Tester@Example.com",
        "https://api.openai.com/auth": {"chatgpt_account_id": "acct-ns"}
    }));
    assert_eq!(
        extract_account_id(Some(&namespaced), "").as_deref(),
        Some("acct-ns")
    );
    assert_eq!(
        extract_email(Some(&namespaced), "").as_deref(),
        Some("tester@example.com")
    );

    let top_level = jwt(json!({"chatgpt_account_id": "acct-top", "email": "a@b.c"}));
    assert_eq!(
        extract_account_id(None, &top_level).as_deref(),
        Some("acct-top")
    );

    let organization = jwt(json!({"organizations": [{"id": "org-1"}]}));
    assert_eq!(
        extract_account_id(Some(&organization), "").as_deref(),
        Some("org-1")
    );

    assert_eq!(extract_account_id(None, "not-a-jwt"), None);
}

#[test]
fn chatgpt_refresh_window_respects_the_margin() {
    use crate::chatgpt_auth::{needs_refresh, Credentials};
    let now = 1_000_000;
    let mut credentials = Credentials {
        access: String::from("token"),
        expires_at: now + 3_600,
        ..Default::default()
    };
    assert!(!needs_refresh(&credentials, now));
    // Inside the 60 second margin the token is refreshed early.
    credentials.expires_at = now + 30;
    assert!(needs_refresh(&credentials, now));
    credentials.expires_at = now - 10;
    assert!(needs_refresh(&credentials, now));
    // A server that did not report an expiry is not refreshed on a guess.
    credentials.expires_at = 0;
    assert!(!needs_refresh(&credentials, now));
    credentials.access = String::new();
    assert!(needs_refresh(&credentials, now));
}

#[test]
fn chatgpt_login_completes_only_with_the_matching_callback() {
    use crate::chatgpt_auth::{attempt_handles, start_login, AttemptState};
    use std::io::{Read as _, Write as _};
    let (mut server, token_port) = start_mock_oauth();
    let callback_port = free_port();
    let endpoints = test_endpoints(token_port, callback_port);
    let (sender, receiver) = std::sync::mpsc::channel();
    let attempt = start_login(
        endpoints,
        std::time::Duration::from_secs(20),
        Box::new(move |outcome, _shared, _cancel| {
            let _ = sender.send(outcome);
        }),
    )
    .unwrap();
    let state = query_params(&attempt.auth_url)
        .get("state")
        .cloned()
        .expect("state in auth url");
    assert!(attempt.auth_url.contains("code_challenge_method=S256"));
    assert!(attempt.auth_url.contains("codex_cli_simplified_flow=true"));

    // A stray callback with the wrong state is refused and does not end the attempt.
    let mut wrong = std::net::TcpStream::connect(("127.0.0.1", callback_port)).unwrap();
    wrong
        .write_all(b"GET /auth/callback?code=code-wrong&state=stale HTTP/1.1\r\nHost: x\r\n\r\n")
        .unwrap();
    let mut refused = String::new();
    let _ = wrong.read_to_string(&mut refused);
    assert!(refused.starts_with("HTTP/1.1 400"), "{refused}");
    assert!(receiver
        .recv_timeout(std::time::Duration::from_millis(400))
        .is_err());
    let (state_arc, _cancel) = attempt_handles(&attempt.id).unwrap();
    assert!(matches!(*state_arc.lock().unwrap(), AttemptState::Pending));

    // The real callback exchanges the code and reports credentials.
    let mut good = std::net::TcpStream::connect(("127.0.0.1", callback_port)).unwrap();
    good.write_all(
        format!("GET /auth/callback?code=code-good&state={state} HTTP/1.1\r\nHost: x\r\n\r\n")
            .as_bytes(),
    )
    .unwrap();
    let mut accepted = String::new();
    let _ = good.read_to_string(&mut accepted);
    assert!(accepted.starts_with("HTTP/1.1 200"), "{accepted}");

    let credentials = receiver
        .recv_timeout(std::time::Duration::from_secs(15))
        .expect("callback delivered")
        .expect("exchange succeeded");
    assert_eq!(credentials.access, "access-1");
    assert_eq!(credentials.refresh, "refresh-1");
    assert_eq!(credentials.account_id.as_deref(), Some("acct-test-1"));
    assert_eq!(credentials.email.as_deref(), Some("tester@example.com"));
    assert!(credentials.expires_at > crate::chatgpt_auth::now_unix());
    server.kill().ok();
}

#[test]
fn chatgpt_login_reports_a_busy_callback_port() {
    use crate::chatgpt_auth::start_login;
    let blocker = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let port = blocker.local_addr().unwrap().port();
    // The callback binds whichever loopback family is free, so block both.
    let blocker_v6 = std::net::TcpListener::bind((std::net::Ipv6Addr::LOCALHOST, port));
    let endpoints = test_endpoints(1, port);
    let error = start_login(
        endpoints,
        std::time::Duration::from_secs(5),
        Box::new(|_outcome, _shared, _cancel| {}),
    )
    .err()
    .expect("busy port must fail");
    assert!(error.contains("사용할 수 없어"), "{error}");
    assert!(error.contains(&port.to_string()), "{error}");
    drop(blocker_v6);
}

#[test]
fn chatgpt_login_times_out_and_can_be_cancelled() {
    use crate::chatgpt_auth::{attempt_handles, start_login, AttemptState};
    let endpoints = test_endpoints(1, free_port());
    let attempt = start_login(
        endpoints,
        std::time::Duration::from_millis(600),
        Box::new(|_outcome, _shared, _cancel| {}),
    )
    .unwrap();
    std::thread::sleep(std::time::Duration::from_millis(1_400));
    let (state, _) = attempt_handles(&attempt.id).unwrap();
    match &*state.lock().unwrap() {
        AttemptState::Failed { error } => assert!(error.contains("시간이 초과"), "{error}"),
        other => panic!("expected timeout, got {other:?}"),
    }

    let endpoints = test_endpoints(1, free_port());
    let attempt = start_login(
        endpoints,
        std::time::Duration::from_secs(30),
        Box::new(|_outcome, _shared, _cancel| {}),
    )
    .unwrap();
    attempt
        .cancel
        .store(true, std::sync::atomic::Ordering::SeqCst);
    std::thread::sleep(std::time::Duration::from_millis(600));
    let (state, _) = attempt_handles(&attempt.id).unwrap();
    assert!(matches!(*state.lock().unwrap(), AttemptState::Cancelled));
}

/// A browser keeps speculative connections open without sending a request. One
/// of those must not park the callback loop: the login attempt still has to
/// time out and hand the port back for the next try.
#[test]
fn a_silent_callback_connection_does_not_hold_the_login_port() {
    use crate::chatgpt_auth::{attempt_handles, start_login, AttemptState};
    let port = free_port();
    let endpoints = test_endpoints(1, port);
    let attempt = start_login(
        endpoints,
        std::time::Duration::from_millis(900),
        Box::new(|_outcome, _shared, _cancel| {}),
    )
    .unwrap();
    let silent = std::net::TcpStream::connect(("127.0.0.1", port)).unwrap();
    std::thread::sleep(std::time::Duration::from_millis(3_500));
    let (state, _) = attempt_handles(&attempt.id).unwrap();
    match &*state.lock().unwrap() {
        AttemptState::Failed { error } => assert!(error.contains("시간이 초과"), "{error}"),
        other => panic!("expected timeout, got {other:?}"),
    }
    drop(silent);
    assert!(
        std::net::TcpListener::bind(("127.0.0.1", port)).is_ok(),
        "로그인 실패 뒤 콜백 포트가 해제되어야 합니다"
    );
}

/// A browser can connect first and send the request a moment later. The
/// accepted socket is non-blocking on Windows, so the callback has to wait for
/// the request instead of dropping the connection on the first `WouldBlock`.
#[test]
fn a_delayed_callback_request_is_still_accepted() {
    use std::io::{Read as _, Write as _};
    let (mut server, token_port) = start_mock_oauth();
    let port = free_port();
    let endpoints = test_endpoints(token_port, port);
    let (sender, receiver) = std::sync::mpsc::channel();
    let attempt = crate::chatgpt_auth::start_login(
        endpoints,
        std::time::Duration::from_secs(20),
        Box::new(move |outcome, _shared, _cancel| {
            let _ = sender.send(outcome);
        }),
    )
    .unwrap();
    let state = query_params(&attempt.auth_url)
        .get("state")
        .cloned()
        .expect("state in auth url");
    let mut stream = std::net::TcpStream::connect(("127.0.0.1", port)).unwrap();
    std::thread::sleep(std::time::Duration::from_millis(300));
    stream
        .write_all(
            format!("GET /auth/callback?code=code-late&state={state} HTTP/1.1\r\nHost: x\r\n\r\n")
                .as_bytes(),
        )
        .unwrap();
    let mut response = String::new();
    let _ = stream.read_to_string(&mut response);
    assert!(response.starts_with("HTTP/1.1 200"), "{response}");
    let credentials = receiver
        .recv_timeout(std::time::Duration::from_secs(15))
        .expect("delayed callback delivered")
        .expect("exchange succeeded");
    assert_eq!(credentials.access, "access-1");
    server.kill().ok();
}

/// The app records the exact URL it opened, with the whole query string, so a
/// browser or server error page can be matched against it later.
#[test]
fn the_opened_login_url_is_recorded_with_its_query_string() {
    use crate::chatgpt_auth::{append_login_log, login_log_line, LoginStart};
    let dir = std::env::temp_dir().join(format!("modal-gui-login-log-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    let start = LoginStart {
        attempt_id: String::from("login_test_1"),
        auth_url: String::from(
            "https://auth.openai.com/oauth/authorize?response_type=code&client_id=app_test&state=state_test",
        ),
        redirect_uri: String::from("http://localhost:1455/auth/callback"),
        expires_at: 1_800_000_000,
    };
    append_login_log(&dir, &start).unwrap();
    append_login_log(&dir, &start).unwrap();
    let text = std::fs::read_to_string(dir.join("chatgpt-login.log")).unwrap();
    assert_eq!(text.lines().count(), 2);
    assert!(text.contains("attempt=login_test_1"), "{text}");
    assert!(text.contains("expires_at=1800000000"), "{text}");
    // The whole query string survives: the incident was a URL cut at `&`.
    assert!(text.contains("client_id=app_test&state=state_test"), "{text}");
    assert_eq!(login_log_line(&start).matches("client_id=app_test").count(), 1);
    let _ = std::fs::remove_dir_all(&dir);
}

/// A pending attempt tells the UI when it stops holding the fixed callback
/// port, so a retry does not collide with the previous try.
#[test]
fn a_login_attempt_reports_when_it_stops_waiting() {
    use crate::chatgpt_auth::{attempt_deadline, now_unix};
    let before = now_unix();
    let deadline = attempt_deadline(std::time::Duration::from_secs(120));
    assert!(deadline >= before + 119, "{deadline} vs {before}");
    assert!(deadline <= before + 121, "{deadline} vs {before}");
}

/// A cancel that lands while the credentials are being stored must not be
/// reported as a completed login, and a stored account must not be reported as
/// cancelled afterwards.
#[test]
fn a_late_cancel_is_not_reported_as_a_completed_login() {
    use crate::chatgpt_auth::{settle_after_store, AccountRow, AttemptState};
    let account = AccountRow {
        id: String::from("acct-1"),
        provider: String::from("chatgpt"),
        account_id: Some(String::from("acct-1")),
        display_name: None,
        email: Some(String::from("tester@example.com")),
        expires_at: None,
        status: String::from("ok"),
        last_error: None,
        credential_ref: None,
        credential_version: 1,
        created_at: String::from("2026-09-27T00:00:00Z"),
        updated_at: String::from("2026-09-27T00:00:00Z"),
    };
    // The store skipped writing because the cancel arrived first.
    assert!(matches!(
        settle_after_store(true, None),
        AttemptState::Cancelled
    ));
    // Nothing was stored and nobody cancelled: a real failure.
    match settle_after_store(false, None) {
        AttemptState::Failed { error } => assert!(error.contains("저장하지 못했습니다"), "{error}"),
        other => panic!("expected failure, got {other:?}"),
    }
    // The credentials reached the database, so the login is complete even if a
    // cancel arrived right after.
    assert!(matches!(
        settle_after_store(true, Some(account)),
        AttemptState::Completed { .. }
    ));
}

/// Cancelling while the code is being exchanged must not store the credentials
/// the exchange eventually returns.
#[test]
fn cancelling_during_the_token_exchange_does_not_deliver_credentials() {
    use crate::chatgpt_auth::{attempt_handles, AttemptState};
    use std::io::Write as _;
    use std::sync::atomic::Ordering;
    let (mut server, token_port) = start_mock_oauth_with_delay(1_500);
    let port = free_port();
    let endpoints = test_endpoints(token_port, port);
    let (sender, receiver) = std::sync::mpsc::channel();
    let attempt = crate::chatgpt_auth::start_login(
        endpoints,
        std::time::Duration::from_secs(20),
        Box::new(move |outcome, _shared, _cancel| {
            let _ = sender.send(outcome);
        }),
    )
    .unwrap();
    let state = query_params(&attempt.auth_url)
        .get("state")
        .cloned()
        .expect("state in auth url");
    let mut stream = std::net::TcpStream::connect(("127.0.0.1", port)).unwrap();
    stream
        .write_all(
            format!("GET /auth/callback?code=code-slow&state={state} HTTP/1.1\r\nHost: x\r\n\r\n")
                .as_bytes(),
        )
        .unwrap();
    // The mock server holds the token response open, so this cancel lands while
    // the exchange is in flight.
    std::thread::sleep(std::time::Duration::from_millis(400));
    attempt.cancel.store(true, Ordering::SeqCst);
    assert!(
        receiver
            .recv_timeout(std::time::Duration::from_secs(4))
            .is_err(),
        "취소된 로그인이 자격증명을 전달하면 안 됩니다"
    );
    let (shared, _cancel) = attempt_handles(&attempt.id).unwrap();
    assert!(matches!(*shared.lock().unwrap(), AttemptState::Cancelled));
    server.kill().ok();
}

/// The shell receives the whole URL. The previous `cmd /C start` path cut it
/// at the first `&`, which is exactly the `missing_required_parameter` failure.
#[cfg(windows)]
#[test]
fn shell_target_keeps_the_oauth_query_intact() {
    let url = "https://auth.openai.com/oauth/authorize?response_type=code&client_id=app_x\
&redirect_uri=http%3A%2F%2Flocalhost%3A1455%2Fauth%2Fcallback&scope=openid%20profile\
&state=st-1&code_challenge=ch-1&code_challenge_method=S256&codex_cli_simplified_flow=true";
    let wide = crate::media::shell_target(url);
    assert_eq!(wide.last(), Some(&0), "NUL 종료가 필요합니다");
    let round_trip = String::from_utf16(&wide[..wide.len() - 1]).expect("utf-16");
    assert_eq!(round_trip, url);
    assert!(round_trip.contains("&client_id=app_x"), "{round_trip}");
    assert!(round_trip.contains("&code_challenge_method=S256"), "{round_trip}");
}

#[test]
fn chatgpt_refresh_is_single_flight_and_keeps_rotation_safe() {
    use crate::chatgpt_auth::{
        apply_refresh, ensure_fresh, load_credentials, store_credentials, AccountRow, Credentials,
    };
    let (mut server, token_port) = start_mock_oauth();
    let dir = std::env::temp_dir().join("modal-gui-chatgpt-refresh-test");
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let db_path = dir.join("accounts.db");
    let secrets = dir.join("secrets");
    let endpoints = test_endpoints(token_port, free_port());
    let conn = Connection::open(&db_path).unwrap();
    init_db(&conn).unwrap();
    let expired = Credentials {
        access: String::from("access-old"),
        refresh: String::from("refresh-1"),
        expires_at: crate::chatgpt_auth::now_unix() - 10,
        account_id: Some(String::from("acct-test-1")),
        email: Some(String::from("tester@example.com")),
        version: 0,
    };
    let account = store_credentials(&conn, &secrets, &expired).unwrap();
    assert_eq!(account.status, "ok");
    drop(conn);

    // Three callers at once: the account is refreshed exactly once.
    let results: Vec<Result<AccountRow, String>> = std::thread::scope(|scope| {
        let mut handles = Vec::new();
        for _ in 0..3 {
            let db_path = db_path.clone();
            let secrets = secrets.clone();
            let endpoints = endpoints.clone();
            let id = account.id.clone();
            handles.push(scope.spawn(move || {
                let conn = Connection::open(&db_path).unwrap();
                ensure_fresh(&conn, &secrets, &endpoints, &id)
            }));
        }
        handles
            .into_iter()
            .map(|handle| handle.join().unwrap())
            .collect()
    });
    assert!(results.iter().all(|result| result.is_ok()), "{results:?}");

    let stats: Value = serde_json::from_str(
        &ureq::get(&format!("http://127.0.0.1:{token_port}/stats"))
            .call()
            .unwrap()
            .into_string()
            .unwrap(),
    )
    .unwrap();
    assert_eq!(
        stats.get("refresh_requests").and_then(Value::as_i64),
        Some(1)
    );

    // The response omitted refresh_token, so the stored one is untouched.
    let stored = load_credentials(&secrets, "acct-test-1").unwrap();
    assert_eq!(stored.refresh, "refresh-1");
    assert_eq!(stored.access, "access-r1");
    assert!(stored.version >= 2);

    // A rotating server replaces it, and an auth failure asks for a new login.
    let conn = Connection::open(&db_path).unwrap();
    let rotating = Credentials {
        access: String::from("expired"),
        refresh: String::from("refresh-rotate-1"),
        expires_at: crate::chatgpt_auth::now_unix() - 5,
        account_id: Some(String::from("acct-test-1")),
        email: Some(String::from("tester@example.com")),
        version: 0,
    };
    store_credentials(&conn, &secrets, &rotating).unwrap();
    ensure_fresh(&conn, &secrets, &endpoints, "acct-test-1").unwrap();
    let rotated = load_credentials(&secrets, "acct-test-1").unwrap();
    assert_eq!(rotated.refresh, "refresh-r2");

    let revoked = Credentials {
        access: String::from("expired"),
        refresh: String::from("refresh-invalid-9"),
        expires_at: crate::chatgpt_auth::now_unix() - 5,
        account_id: Some(String::from("acct-test-1")),
        email: Some(String::from("tester@example.com")),
        version: 0,
    };
    store_credentials(&conn, &secrets, &revoked).unwrap();
    let failure = ensure_fresh(&conn, &secrets, &endpoints, "acct-test-1").unwrap_err();
    assert!(failure.contains("invalid_grant"), "{failure}");
    assert_eq!(
        crate::chatgpt_auth::get_account(&conn, "acct-test-1")
            .unwrap()
            .status,
        "relogin"
    );

    // A late refresh answer is dropped when the row moved on.
    let stale_version = crate::chatgpt_auth::get_account(&conn, "acct-test-1")
        .unwrap()
        .credential_version;
    let newer = Credentials {
        access: String::from("access-newer"),
        refresh: String::from("refresh-newer"),
        expires_at: crate::chatgpt_auth::now_unix() + 3_600,
        account_id: Some(String::from("acct-test-1")),
        email: Some(String::from("tester@example.com")),
        version: 0,
    };
    store_credentials(&conn, &secrets, &newer).unwrap();
    let late = Credentials {
        access: String::from("access-late"),
        refresh: String::from("refresh-late"),
        expires_at: crate::chatgpt_auth::now_unix() + 3_600,
        account_id: Some(String::from("acct-test-1")),
        email: Some(String::from("tester@example.com")),
        version: 0,
    };
    assert!(apply_refresh(&conn, &secrets, "acct-test-1", stale_version, &late).is_err());
    assert_eq!(
        load_credentials(&secrets, "acct-test-1").unwrap().access,
        "access-newer"
    );

    let _ = std::fs::remove_dir_all(&dir);
    server.kill().ok();
}

#[test]
fn chatgpt_credentials_are_encrypted_and_logout_removes_them() {
    use crate::chatgpt_auth::{load_credentials, logout_account, store_credentials, Credentials};
    let conn = fresh_db();
    let dir = std::env::temp_dir().join("modal-gui-chatgpt-secret-test");
    let _ = std::fs::remove_dir_all(&dir);
    let credentials = Credentials {
        access: String::from("access-secret"),
        refresh: String::from("refresh-secret"),
        expires_at: crate::chatgpt_auth::now_unix() + 3_600,
        account_id: Some(String::from("acct-secret")),
        email: Some(String::from("tester@example.com")),
        version: 0,
    };
    let account = store_credentials(&conn, &dir, &credentials).unwrap();
    let path = std::path::PathBuf::from(account.credential_ref.clone().unwrap());
    assert!(path.is_file());
    let raw = std::fs::read(&path).unwrap();
    assert!(
        !raw.windows(13).any(|window| window == b"access-secret"),
        "plaintext token must not be on disk"
    );
    let loaded = load_credentials(&dir, "acct-secret").unwrap();
    assert_eq!(loaded.access, "access-secret");
    assert_eq!(loaded.version, 1);
    // Writing again bumps the version instead of resetting it.
    let again = store_credentials(&conn, &dir, &credentials).unwrap();
    assert_eq!(again.credential_version, 2);

    logout_account(&conn, &dir, &account.id).unwrap();
    assert!(!path.exists());
    assert!(crate::chatgpt_auth::list_accounts(&conn)
        .unwrap()
        .is_empty());
    let _ = std::fs::remove_dir_all(&dir);
}

// ---------------------------------------------------------------------------
// Codex app-server chat adapter
// ---------------------------------------------------------------------------

#[test]
fn ai_chat_speaks_the_app_server_protocol() {
    use crate::ai_chat::AppServer;
    use std::sync::atomic::{AtomicI64, Ordering};
    let script = crate::paths::repo_root()
        .join("tools")
        .join("test_app_server.py");
    let dump_path = std::env::temp_dir().join("modal-gui-app-server-dump.jsonl");
    let _ = std::fs::remove_file(&dump_path);

    let events: std::sync::Arc<std::sync::Mutex<Vec<Value>>> =
        std::sync::Arc::new(std::sync::Mutex::new(Vec::new()));
    let events_sink = std::sync::Arc::clone(&events);
    let sink: crate::ai_chat::EventSink = std::sync::Arc::new(move |value| {
        if let Ok(mut guard) = events_sink.lock() {
            guard.push(value);
        }
    });
    let refresh_calls = std::sync::Arc::new(AtomicI64::new(0));
    let refresh_calls_handler = std::sync::Arc::clone(&refresh_calls);
    let refresh: crate::ai_chat::RefreshHandler = std::sync::Arc::new(move |_params| {
        refresh_calls_handler.fetch_add(1, Ordering::SeqCst);
        json!({"result": {"accessToken": "access-refreshed", "chatgptAccountId": "acct-test-1"}})
    });

    let session = AppServer::spawn_with(
        "python",
        &[
            script.to_string_lossy().to_string(),
            "--dump".to_string(),
            dump_path.to_string_lossy().to_string(),
        ],
        sink,
        refresh,
    )
    .unwrap();
    session.initialize().unwrap();

    let credentials = crate::chatgpt_auth::Credentials {
        access: String::from("access-1"),
        refresh: String::from("refresh-1"),
        expires_at: crate::chatgpt_auth::now_unix() + 3_600,
        account_id: Some(String::from("acct-test-1")),
        email: Some(String::from("tester@example.com")),
        version: 1,
    };
    session.login(&credentials).unwrap();
    let thread_id = session.ensure_thread("conv-a").unwrap();
    assert_eq!(thread_id, "thread-test-1");
    // The thread is reused instead of being recreated per message.
    assert_eq!(session.ensure_thread("conv-a").unwrap(), "thread-test-1");
    // 다른 대화는 다른 thread를 쓴다. 하나를 공유하면 프로젝트 맥락이 섞인다.
    let other_thread = session.ensure_thread("conv-b").unwrap();
    assert_eq!(other_thread, "thread-test-2");
    assert_ne!(other_thread, thread_id);

    let (turn, delivery) = session.send_turn(&thread_id, "안녕", &[]).unwrap();
    assert!(delivery.is_empty());
    assert_eq!(
        turn.get("turn")
            .and_then(|value| value.get("id"))
            .and_then(Value::as_str),
        Some("turn-test-1")
    );
    // 첨부는 app-server가 아는 항목 이름으로 나가야 한다. 서버가 `localImage`를
    // 기대하므로, 이름이 틀리면 실제 대화가 시작되지 않는다.
    let attachment = crate::ai_chat::ChatAttachment {
        path: crate::paths::repo_root()
            .join("docs")
            .join("creative-studio-architecture.md")
            .to_string_lossy()
            .to_string(),
        name: String::from("reference.md"),
        kind: Some(String::from("image")),
    };
    let (_turn, delivery) = session
        .send_turn(&thread_id, "이미지 확인", std::slice::from_ref(&attachment))
        .unwrap();
    assert_eq!(delivery.len(), 1);
    assert!(delivery[0].delivered, "이미지 첨부는 전달로 기록되어야 합니다");
    assert_eq!(delivery[0].note, None);
    let dumped = std::fs::read_to_string(&dump_path).unwrap_or_default();
    assert!(
        dumped.contains("localImage"),
        "첨부가 localImage 항목으로 전달되어야 합니다"
    );
    assert!(dumped.contains("reference.md") || dumped.contains("creative-studio-architecture"));

    // 지원하지 않는 형식은 파일 이름만 전달되고, 그 사실이 함께 보고된다.
    let named_only = crate::ai_chat::ChatAttachment {
        path: crate::paths::repo_root()
            .join("docs")
            .join("renderer-plugins.md")
            .to_string_lossy()
            .to_string(),
        name: String::from("renderer-plugins.md"),
        kind: None,
    };
    let (_turn, delivery) = session
        .send_turn(&thread_id, "문서 참고", std::slice::from_ref(&named_only))
        .unwrap();
    assert_eq!(delivery.len(), 1);
    assert!(
        !delivery[0].delivered,
        "이름만 전달된 첨부를 전달됨으로 기록하면 안 됩니다"
    );
    assert_eq!(delivery[0].note.as_deref(), Some("파일 이름만 전달"));

    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(20);
    loop {
        let done = events
            .lock()
            .map(|guard| {
                guard.iter().any(|event| {
                    event.get("method").and_then(Value::as_str) == Some("turn/completed")
                })
            })
            .unwrap_or(false);
        if done {
            break;
        }
        assert!(
            std::time::Instant::now() < deadline,
            "turn did not complete"
        );
        std::thread::sleep(std::time::Duration::from_millis(100));
    }

    let reply: String = events
        .lock()
        .unwrap()
        .iter()
        .filter(|event| {
            event.get("method").and_then(Value::as_str) == Some("item/agentMessage/delta")
        })
        .filter_map(|event| {
            event
                .get("params")
                .and_then(|params| params.get("delta"))
                .and_then(Value::as_str)
        })
        .collect();
    // 첨부 메시지까지 같은 스트림에 쌓이므로 첫 답변이 포함되어 있는지 본다.
    assert!(reply.contains("mock reply: 안녕 (done)"), "{reply}");
    assert!(reply.contains("mock reply: 이미지 확인 (done)"), "{reply}");
    // The runtime asked for tokens once and the host answered.
    assert!(refresh_calls.load(Ordering::SeqCst) >= 1);

    session.interrupt(&thread_id, "turn-test-1").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(300));

    let dump = std::fs::read_to_string(&dump_path).unwrap_or_default();
    assert!(dump.contains("\"account/login/start\""), "{dump}");
    assert!(
        dump.contains("access-1"),
        "login must carry the access token"
    );
    assert!(dump.contains("acct-test-1"), "{dump}");
    assert!(
        dump.contains("access-refreshed"),
        "the host must answer the refresh request"
    );
    assert!(dump.contains("\"turn/interrupt\""), "{dump}");
    let _ = std::fs::remove_file(&dump_path);
}

#[test]
fn conversations_and_messages_round_trip() {
    use crate::ai_chat::{append_message, ensure_conversation, list_conversations, list_messages};
    let conn = fresh_db();
    let project = crate::studio::create_project(
        &conn,
        "대화",
        r#"{"nodes":[],"assets":[],"edges":[],"shots":[]}"#,
    )
    .unwrap();
    let project_chat = ensure_conversation(&conn, &project.id, None).unwrap();
    let same = ensure_conversation(&conn, &project.id, None).unwrap();
    assert_eq!(project_chat.id, same.id);
    let node_chat = ensure_conversation(&conn, &project.id, Some("nd_video")).unwrap();
    assert_ne!(node_chat.id, project_chat.id);
    assert_eq!(node_chat.node_id.as_deref(), Some("nd_video"));

    append_message(&conn, &project_chat.id, "user", "샷을 세 개로 나눠줘", None).unwrap();
    append_message(
        &conn,
        &project_chat.id,
        "assistant",
        "세 샷으로 나눴습니다.",
        Some(&json!({"turnId": "t1", "threadId": "th1"})),
    )
    .unwrap();
    assert!(append_message(&conn, &project_chat.id, "nope", "x", None).is_err());

    let messages = list_messages(&conn, &project_chat.id, 50).unwrap();
    assert_eq!(messages.len(), 2);
    assert_eq!(messages[0].role, "user");
    assert_eq!(messages[1].content, "세 샷으로 나눴습니다.");
    assert_eq!(
        messages[1].meta.get("threadId").and_then(Value::as_str),
        Some("th1")
    );
    assert_eq!(list_conversations(&conn, &project.id).unwrap().len(), 2);
}

#[test]
fn studio_create_save_load_round_trip() {
    let conn = fresh_db();
    let first = r#"{"nodes":[{"id":"node-1"}],"assets":[]}"#;
    let second = r#"{"nodes":[{"id":"node-1"},{"id":"node-2"}],"assets":[{"id":"asset-1"}]}"#;
    let project = crate::studio::create_project(&conn, "초안", first).unwrap();
    let saved = crate::studio::save_project(&conn, &project.id, "완성본", second).unwrap();
    assert_eq!(saved.revision, 2);
    assert!(!saved.updated_at.is_empty());

    let loaded = crate::studio::load_project(&conn, &project.id).unwrap();
    assert_eq!(loaded.revision, 2);
    assert_eq!(loaded.document_json, second);
    assert_eq!(loaded.name, "완성본");

    let projects = crate::studio::list_projects(&conn).unwrap();
    assert_eq!(projects.len(), 1);
    assert_eq!(projects[0].node_count, 2);
    assert_eq!(projects[0].asset_count, 1);
    assert!(!projects[0].updated_at.is_empty());
}

#[test]
fn studio_invalid_document_is_rejected_without_new_revision() {
    let conn = fresh_db();
    let document = r#"{"nodes":[],"assets":[]}"#;
    let project = crate::studio::create_project(&conn, "초안", document).unwrap();

    assert!(crate::studio::save_project(&conn, &project.id, "손상", "{oops").is_err());
    assert!(crate::studio::create_project(&conn, "누락", r#"{"assets":[]}"#).is_err());
    let revision: i64 = conn
        .query_row(
            "SELECT revision FROM studio_projects WHERE id = ?1",
            params![project.id],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(revision, 1);
}

#[test]
fn studio_delete_removes_project_revisions_and_assets() {
    let conn = fresh_db();
    let project =
        crate::studio::create_project(&conn, "삭제", r#"{"nodes":[],"assets":[]}"#).unwrap();
    conn.execute(
        "INSERT INTO studio_assets \
         (project_id, file_name, stored_path, size_bytes, hash, kind, created_at) \
         VALUES (?1, 'a.png', 'x', 1, 'hash', 'image', 'now')",
        params![project.id],
    )
    .unwrap();

    crate::studio::delete_project(&conn, &project.id).unwrap();
    for table in [
        "studio_projects",
        "studio_project_revisions",
        "studio_assets",
    ] {
        let count: i64 = conn
            .query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |row| {
                row.get(0)
            })
            .unwrap();
        assert_eq!(count, 0, "{table}");
    }
    assert_eq!(
        crate::studio::load_project(&conn, &project.id)
            .err()
            .unwrap(),
        "프로젝트를 찾을 수 없습니다"
    );
}

#[test]
fn studio_import_asset_copies_hashes_and_validates_inputs() {
    let conn = fresh_db();
    let project =
        crate::studio::create_project(&conn, "자산", r#"{"nodes":[],"assets":[]}"#).unwrap();
    let test_root = std::env::temp_dir().join(format!(
        "modal-gui-studio-test-{}",
        chrono::Utc::now().timestamp_nanos_opt().unwrap()
    ));
    let source_dir = test_root.join("source");
    let asset_root = test_root.join("studio");
    std::fs::create_dir_all(&source_dir).unwrap();
    let source = source_dir.join("샘플.PNG");
    let bytes = b"known studio asset bytes";
    std::fs::write(&source, bytes).unwrap();

    let imported =
        crate::studio::import_asset(&conn, &asset_root, &project.id, source.to_str().unwrap())
            .unwrap();
    assert_eq!(imported.size_bytes, bytes.len() as i64);
    assert_eq!(imported.kind, "image");
    assert_eq!(imported.hash.len(), 16);
    assert!(imported
        .hash
        .chars()
        .all(|character| character.is_ascii_hexdigit()));
    assert!(std::path::Path::new(&imported.stored_path).is_file());
    assert!(std::path::Path::new(&imported.stored_path)
        .starts_with(asset_root.join(&project.id).join("assets")));

    let imported_again =
        crate::studio::import_asset(&conn, &asset_root, &project.id, source.to_str().unwrap())
            .unwrap();
    assert_eq!(imported_again.hash, imported.hash);
    assert!(crate::studio::import_asset(
        &conn,
        &asset_root,
        &project.id,
        source_dir.join("missing.png").to_str().unwrap(),
    )
    .is_err());
    assert_eq!(
        crate::studio::import_asset(
            &conn,
            &asset_root,
            "unknown-project",
            source.to_str().unwrap(),
        )
        .err()
        .unwrap(),
        "프로젝트를 찾을 수 없습니다"
    );

    std::fs::remove_dir_all(&test_root).unwrap();
}
