mod accounts;
mod ai_chat;
mod chatgpt_auth;
mod connections;
mod database;
mod diagnostics;
mod jobs;
mod media;
mod paths;
mod pipeline;
mod studio;
mod studio_export;
mod studio_run;
mod studio_templates;
mod templates;
mod usage;
mod workflows;

use database::{init_db, AppState};
use rusqlite::Connection;
use serde::Serialize;
use std::sync::Mutex;
use tauri::{Manager, State};

#[derive(Serialize)]
struct Health {
    database: bool,
    sidecar: bool,
}

#[tauri::command]
fn health(state: State<AppState>) -> Result<Health, String> {
    let database = state.0.lock().map_err(|error| error.to_string()).is_ok();
    Ok(Health {
        database,
        sidecar: true,
    })
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let path = app.path().app_data_dir()?.join("database");
            std::fs::create_dir_all(&path)?;
            let conn = Connection::open(path.join("app.db"))?;
            init_db(&conn)?;
            // A job left mid-flight by the previous process can never finish.
            jobs::fail_interrupted_jobs(&conn)?;
            // Same for canvas runs: the worker or local pipeline is gone.
            studio_run::fail_interrupted_runs(&conn)?;
            // The two workflows this deployment actually has.
            workflows::seed_default_workflows(&conn)?;
            app.manage(AppState(Mutex::new(conn)));
            app.manage(studio::StudioRoot(paths::studio_root()));
            app.manage(chatgpt_auth::SecretsRoot(
                app.path().app_data_dir()?.join("secrets"),
            ));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            health,
            jobs::create_job,
            jobs::start_job,
            jobs::start_music,
            jobs::list_recent_jobs,
            accounts::list_modal_profiles,
            accounts::save_modal_profile,
            accounts::set_modal_profile_enabled,
            accounts::archive_modal_profile,
            usage::list_usage_rows,
            usage::sync_modal_billing,
            usage::studio_usage_summary,
            media::list_pipeline_inputs,
            media::read_json_file,
            media::make_thumbnail,
            media::generate_silence,
            media::generate_color_clip,
            media::generate_still_clip,
            media::write_json_file,
            media::reveal_in_explorer,
            pipeline::analyze_audio,
            pipeline::render_trailer,
            pipeline::render_spec,
            pipeline::build_storyboard,
            pipeline::list_renderers,
            templates::template_list,
            templates::template_render,
            studio::studio_list_projects,
            studio::studio_create_project,
            studio::studio_load_project,
            studio::studio_save_project,
            studio::studio_delete_project,
            studio::studio_import_asset,
            studio::studio_probe_path,
            studio_run::studio_start_node_run,
            studio_run::studio_start_local_run,
            studio_run::studio_finish_node_run,
            studio_run::studio_list_node_runs,
            studio_run::studio_retry_download,
            studio_run::studio_cancel_run,
            studio_export::studio_export_project,
            studio_export::studio_import_project,
            studio_templates::studio_template_list,
            studio_templates::studio_template_save,
            studio_templates::studio_template_delete,
            connections::connection_list,
            connections::connection_save,
            connections::connection_delete,
            connections::connection_set_enabled,
            connections::connection_set_tool_enabled,
            connections::connection_tools,
            connections::connection_test,
            connections::connection_call_tool,
            chatgpt_auth::chatgpt_login_start,
            chatgpt_auth::chatgpt_login_status,
            chatgpt_auth::chatgpt_login_cancel,
            chatgpt_auth::chatgpt_accounts,
            chatgpt_auth::chatgpt_logout,
            chatgpt_auth::chatgpt_ensure_fresh,
            ai_chat::ai_chat_ensure_session,
            ai_chat::ai_chat_send,
            ai_chat::ai_chat_interrupt,
            ai_chat::ai_chat_status,
            ai_chat::conversation_ensure,
            ai_chat::conversation_list,
            ai_chat::message_append,
            ai_chat::message_list,
            workflows::workflow_list,
            workflows::workflow_save,
            workflows::workflow_delete,
            media::open_with_default
        ])
        .run(tauri::generate_context!())
        .expect("error while running Modal GUI");
}

#[cfg(test)]
mod tests;
