//! Renderer-facing permissions API. Lets the UI grant / revoke
//! permissions and read the current snapshot for the Permissions
//! pane.

use tauri::State;

use crate::permissions::{Permissions, SnapshotForUi};

#[tauri::command]
pub fn perms_snapshot(perms: State<'_, Permissions>) -> SnapshotForUi {
    perms.snapshot()
}

#[tauri::command]
pub fn perms_grant_path(
    path: String,
    persistent: bool,
    perms: State<'_, Permissions>,
) -> Result<(), String> {
    perms.grant_path(&path, persistent);
    Ok(())
}

#[tauri::command]
pub fn perms_grant_repo(
    repo: String,
    persistent: bool,
    perms: State<'_, Permissions>,
) -> Result<(), String> {
    perms.grant_repo(&repo, persistent);
    Ok(())
}

#[tauri::command]
pub fn perms_grant_command(
    command: String,
    persistent: bool,
    perms: State<'_, Permissions>,
) -> Result<(), String> {
    perms.grant_command(&command, persistent);
    Ok(())
}

#[tauri::command]
pub fn perms_revoke_path(path: String, perms: State<'_, Permissions>) -> Result<(), String> {
    perms.revoke_path(&path);
    Ok(())
}

#[tauri::command]
pub fn perms_revoke_repo(repo: String, perms: State<'_, Permissions>) -> Result<(), String> {
    perms.revoke_repo(&repo);
    Ok(())
}

#[tauri::command]
pub fn perms_revoke_command(
    command: String,
    perms: State<'_, Permissions>,
) -> Result<(), String> {
    perms.revoke_command(&command);
    Ok(())
}
