use serde::Serialize;

use crate::paths;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct StoragePaths {
    clips: String,
    music: String,
    deliverables: String,
    thumbs: String,
    edits: String,
    studio: String,
}

#[tauri::command]
pub(crate) fn storage_paths() -> StoragePaths {
    StoragePaths {
        clips: paths::default_clips_root().to_string_lossy().into_owned(),
        music: paths::default_music_root().to_string_lossy().into_owned(),
        deliverables: paths::deliverables_root().to_string_lossy().into_owned(),
        thumbs: paths::thumbs_root().to_string_lossy().into_owned(),
        edits: paths::edits_root().to_string_lossy().into_owned(),
        studio: paths::studio_root().to_string_lossy().into_owned(),
    }
}
