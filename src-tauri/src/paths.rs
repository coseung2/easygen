//! Local, untracked workspace locations shared by native commands and the worker.

use std::path::PathBuf;

pub(crate) fn data_root() -> PathBuf {
    if let Some(root) = std::env::var_os("MODAL_GUI_DATA_ROOT")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .filter(|path| path.is_absolute())
    {
        return root;
    }
    #[cfg(windows)]
    {
        let base = std::env::var_os("LOCALAPPDATA")
            .or_else(|| std::env::var_os("APPDATA"))
            .or_else(|| {
                std::env::var_os("USERPROFILE")
                    .map(|home| PathBuf::from(home).join("AppData/Local").into_os_string())
            })
            .expect("a Windows user data directory is required");
        PathBuf::from(base).join("modal-gui")
    }
    #[cfg(not(windows))]
    {
        let base = std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .filter(|path| path.is_absolute())
            .or_else(|| {
                std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".local/share"))
            })
            .expect("a user data directory is required");
        base.join("modal-gui")
    }
}

pub(crate) fn repo_root() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..")
}

fn configured_root(name: &str) -> Option<PathBuf> {
    std::env::var_os(name)
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .filter(|path| path.is_absolute())
}

pub(crate) fn deliverables_root() -> std::path::PathBuf {
    data_root().join("deliverables")
}

pub(crate) fn thumbs_root() -> std::path::PathBuf {
    data_root().join("thumbs")
}

pub(crate) fn default_clips_root() -> std::path::PathBuf {
    configured_root("MODAL_GUI_OUTPUT_ROOT").unwrap_or_else(|| data_root().join("h3-clips/generated"))
}

pub(crate) fn default_music_root() -> std::path::PathBuf {
    configured_root("MODAL_GUI_MUSIC_ROOT").unwrap_or_else(|| data_root().join("music"))
}

pub(crate) fn edits_root() -> std::path::PathBuf {
    data_root().join("edits")
}

pub(crate) fn studio_root() -> std::path::PathBuf {
    data_root().join("studio")
}
