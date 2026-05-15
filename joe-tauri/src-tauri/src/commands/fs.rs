//! File system commands exposed to the renderer.
//!
//! Every command checks `Permissions::path_allowed` before touching
//! disk. If the path isn't granted yet, the command returns
//! `PermissionDeniedDetails { kind: "path", subject: <path> }` so the
//! frontend can pop the grant dialog and retry.

use std::fs;
use std::path::PathBuf;

use serde::Serialize;
use tauri::State;

use crate::permissions::Permissions;

/// Common error shape so the renderer can decide whether to prompt
/// for permission, surface a generic error, or just ignore.
#[derive(Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum FsError {
    PermissionDenied { subject: String, scope: &'static str },
    NotFound { path: String },
    IoError { message: String },
}

impl From<std::io::Error> for FsError {
    fn from(e: std::io::Error) -> Self {
        if e.kind() == std::io::ErrorKind::NotFound {
            FsError::NotFound { path: String::new() }
        } else {
            FsError::IoError { message: e.to_string() }
        }
    }
}

#[derive(Serialize)]
pub struct DirEntry {
    pub name: String,
    pub path: String,
    pub is_dir: bool,
    pub size: u64,
    pub modified_ms: Option<u128>,
}

#[derive(Serialize)]
pub struct FileContent {
    pub path: String,
    pub bytes: u64,
    /// Truncated to ~256 KB for safety; UI shows a "load full" affordance
    /// for larger files. binary files surface as is_binary=true with text=None.
    pub text: Option<String>,
    pub is_binary: bool,
    pub truncated: bool,
}

const MAX_INLINE_BYTES: u64 = 256 * 1024;

/// List immediate children of a directory. `.git`, `node_modules` etc.
/// are filtered out by default so the FileTree pane stays usable.
#[tauri::command]
pub fn list_dir(path: String, perms: State<'_, Permissions>) -> Result<Vec<DirEntry>, FsError> {
    let p = PathBuf::from(&path);
    if !perms.path_allowed(&p) {
        return Err(FsError::PermissionDenied { subject: path, scope: "path" });
    }
    let read = fs::read_dir(&p)?;
    let mut out = Vec::new();
    for entry in read.flatten() {
        let name = entry.file_name().to_string_lossy().to_string();
        if should_hide(&name) {
            continue;
        }
        let meta = entry.metadata()?;
        let modified_ms = meta
            .modified()
            .ok()
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_millis());
        out.push(DirEntry {
            name,
            path: entry.path().to_string_lossy().to_string(),
            is_dir: meta.is_dir(),
            size: meta.len(),
            modified_ms,
        });
    }
    out.sort_by(|a, b| match (a.is_dir, b.is_dir) {
        (true, false) => std::cmp::Ordering::Less,
        (false, true) => std::cmp::Ordering::Greater,
        _ => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
    });
    Ok(out)
}

/// Read a file. Refuses if path isn't permission-granted. Files larger
/// than MAX_INLINE_BYTES return the first chunk + truncated=true so the
/// UI can decide whether to paginate.
#[tauri::command]
pub fn read_file(path: String, perms: State<'_, Permissions>) -> Result<FileContent, FsError> {
    let p = PathBuf::from(&path);
    if !perms.path_allowed(&p) {
        return Err(FsError::PermissionDenied { subject: path, scope: "path" });
    }
    let meta = fs::metadata(&p).map_err(|e| match e.kind() {
        std::io::ErrorKind::NotFound => FsError::NotFound { path: path.clone() },
        _ => FsError::IoError { message: e.to_string() },
    })?;
    let total = meta.len();
    let to_read = std::cmp::min(total, MAX_INLINE_BYTES) as usize;
    let bytes = fs::read(&p)?;
    let slice = &bytes[..to_read.min(bytes.len())];
    let text = match std::str::from_utf8(slice) {
        Ok(s) => Some(s.to_string()),
        Err(_) => None,
    };
    Ok(FileContent {
        path,
        bytes: total,
        is_binary: text.is_none(),
        truncated: total > MAX_INLINE_BYTES,
        text,
    })
}

/// Write a file. Parent dir is created if missing. Permission check
/// uses the path being written; granting a directory grants writes
/// to any new file inside it.
#[tauri::command]
pub fn write_file(
    path: String,
    contents: String,
    perms: State<'_, Permissions>,
) -> Result<u64, FsError> {
    let p = PathBuf::from(&path);
    if !perms.path_allowed(&p) {
        return Err(FsError::PermissionDenied { subject: path, scope: "path" });
    }
    if let Some(parent) = p.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&p, &contents)?;
    Ok(contents.as_bytes().len() as u64)
}

/// Common dotfile / build-artifact dirs the file tree should hide by
/// default. The UI exposes a "show hidden" toggle that ignores this list.
fn should_hide(name: &str) -> bool {
    matches!(
        name,
        ".git"
            | "node_modules"
            | ".next"
            | "__pycache__"
            | "target"
            | ".venv"
            | "venv"
            | "dist"
            | "build"
            | ".pytest_cache"
            | ".joe-agent"
            | ".DS_Store"
    )
}
