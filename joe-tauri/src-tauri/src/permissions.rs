//! Permissions store for the desktop app.
//!
//! Every native command that touches the user's machine (file system,
//! shell exec, git ops) has to clear a permission check first. The
//! checks come in three flavours:
//!
//!   - **path** grants: "this app may read/write under this path"
//!   - **repo** grants: "this app may run git commands in this repo"
//!   - **command** grants: "this app may exec this command name"
//!
//! Each grant has a scope: `Session` (forgotten on app quit) or
//! `Persistent` (saved to disk). The UI surfaces a Permissions pane
//! where the user can revoke any persistent grant at any time.
//!
//! Storage: ~/.joe-agent/desktop-permissions.json on macOS / Linux.
//! Default policy is **deny**: every new path / repo / command
//! requires an explicit grant. There is no "trust everything" toggle;
//! the explicit-grant flow is the entire point.

use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};

/// What the user authorised. Path / repo strings are stored as
/// canonical absolute paths; commands are stored as the program basename
/// (e.g. `git`, `cargo`, not `/usr/bin/git`).
#[derive(Default, Clone, Serialize, Deserialize)]
pub struct PermissionsFile {
    /// Paths under which file reads + writes are allowed.
    pub allowed_paths: HashSet<String>,
    /// Repos in which any git command may run.
    pub allowed_repos: HashSet<String>,
    /// Bare command names allowed via the shell-exec endpoint.
    pub allowed_commands: HashSet<String>,
}

#[derive(Default)]
pub struct Permissions {
    file: Mutex<PermissionsFile>,
    /// Session-only grants. Cleared on app quit.
    session_paths: Mutex<HashSet<String>>,
    session_repos: Mutex<HashSet<String>>,
    session_commands: Mutex<HashSet<String>>,
}

impl Permissions {
    /// Path to the on-disk permissions JSON. Lazily created on first
    /// `save`; returns an Err on weird-home-dir machines so callers
    /// can degrade to in-memory-only.
    pub fn storage_path() -> Result<PathBuf, String> {
        let home = directories::BaseDirs::new()
            .ok_or_else(|| "no home directory".to_string())?
            .home_dir()
            .to_path_buf();
        Ok(home.join(".joe-agent").join("desktop-permissions.json"))
    }

    /// Load persisted grants. Missing file = empty store (not an error).
    pub fn load() -> Self {
        let file = match Self::storage_path()
            .ok()
            .and_then(|p| fs::read_to_string(&p).ok())
            .and_then(|s| serde_json::from_str::<PermissionsFile>(&s).ok())
        {
            Some(f) => f,
            None => PermissionsFile::default(),
        };
        Self {
            file: Mutex::new(file),
            ..Self::default()
        }
    }

    /// Persist the on-disk grants to ~/.joe-agent/desktop-permissions.json.
    /// Session grants are never written.
    pub fn save(&self) -> Result<(), String> {
        let p = Self::storage_path()?;
        if let Some(parent) = p.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let file = self.file.lock().unwrap().clone();
        let json = serde_json::to_string_pretty(&file).map_err(|e| e.to_string())?;
        fs::write(&p, json).map_err(|e| e.to_string())
    }

    // ---------------------------------------------------------------
    // Mutation
    // ---------------------------------------------------------------

    pub fn grant_path(&self, path: &str, persistent: bool) {
        let canon = canonicalize_or_noop(path);
        if persistent {
            self.file.lock().unwrap().allowed_paths.insert(canon);
            let _ = self.save();
        } else {
            self.session_paths.lock().unwrap().insert(canon);
        }
    }

    pub fn grant_repo(&self, repo: &str, persistent: bool) {
        let canon = canonicalize_or_noop(repo);
        if persistent {
            self.file.lock().unwrap().allowed_repos.insert(canon);
            let _ = self.save();
        } else {
            self.session_repos.lock().unwrap().insert(canon);
        }
    }

    pub fn grant_command(&self, command: &str, persistent: bool) {
        let cmd = command.trim().to_lowercase();
        if persistent {
            self.file.lock().unwrap().allowed_commands.insert(cmd);
            let _ = self.save();
        } else {
            self.session_commands.lock().unwrap().insert(cmd);
        }
    }

    pub fn revoke_path(&self, path: &str) {
        let canon = canonicalize_or_noop(path);
        self.file.lock().unwrap().allowed_paths.remove(&canon);
        self.session_paths.lock().unwrap().remove(&canon);
        let _ = self.save();
    }

    pub fn revoke_repo(&self, repo: &str) {
        let canon = canonicalize_or_noop(repo);
        self.file.lock().unwrap().allowed_repos.remove(&canon);
        self.session_repos.lock().unwrap().remove(&canon);
        let _ = self.save();
    }

    pub fn revoke_command(&self, command: &str) {
        let cmd = command.trim().to_lowercase();
        self.file.lock().unwrap().allowed_commands.remove(&cmd);
        self.session_commands.lock().unwrap().remove(&cmd);
        let _ = self.save();
    }

    // ---------------------------------------------------------------
    // Checks
    // ---------------------------------------------------------------

    /// Is `path` (or any ancestor) authorised for read/write? Default deny.
    pub fn path_allowed(&self, path: &Path) -> bool {
        let canon = canonicalize_or_noop(&path.to_string_lossy());
        let persistent = self.file.lock().unwrap().allowed_paths.clone();
        let session = self.session_paths.lock().unwrap().clone();
        for granted in persistent.iter().chain(session.iter()) {
            if path_is_under(&canon, granted) {
                return true;
            }
        }
        false
    }

    pub fn repo_allowed(&self, repo: &Path) -> bool {
        let canon = canonicalize_or_noop(&repo.to_string_lossy());
        let persistent = self.file.lock().unwrap().allowed_repos.clone();
        let session = self.session_repos.lock().unwrap().clone();
        persistent.contains(&canon) || session.contains(&canon)
    }

    pub fn command_allowed(&self, command: &str) -> bool {
        let cmd = command.trim().to_lowercase();
        let persistent = self.file.lock().unwrap().allowed_commands.clone();
        let session = self.session_commands.lock().unwrap().clone();
        persistent.contains(&cmd) || session.contains(&cmd)
    }

    /// Snapshot for the UI permissions pane. Combines persistent + session.
    pub fn snapshot(&self) -> SnapshotForUi {
        let f = self.file.lock().unwrap().clone();
        let sp = self.session_paths.lock().unwrap().clone();
        let sr = self.session_repos.lock().unwrap().clone();
        let sc = self.session_commands.lock().unwrap().clone();
        SnapshotForUi {
            persistent_paths: sorted(&f.allowed_paths),
            persistent_repos: sorted(&f.allowed_repos),
            persistent_commands: sorted(&f.allowed_commands),
            session_paths: sorted(&sp),
            session_repos: sorted(&sr),
            session_commands: sorted(&sc),
        }
    }
}

#[derive(Serialize)]
pub struct SnapshotForUi {
    pub persistent_paths: Vec<String>,
    pub persistent_repos: Vec<String>,
    pub persistent_commands: Vec<String>,
    pub session_paths: Vec<String>,
    pub session_repos: Vec<String>,
    pub session_commands: Vec<String>,
}

// ---------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------

fn canonicalize_or_noop(p: &str) -> String {
    let path = Path::new(p);
    match path.canonicalize() {
        Ok(c) => c.to_string_lossy().to_string(),
        Err(_) => p.to_string(),
    }
}

/// True if `child` equals `parent` or is nested below it. Operates on
/// already-canonicalised strings so we don't get tripped up by symlinks.
fn path_is_under(child: &str, parent: &str) -> bool {
    if child == parent {
        return true;
    }
    let p = if parent.ends_with('/') {
        parent.to_string()
    } else {
        format!("{}/", parent)
    };
    child.starts_with(&p)
}

fn sorted(set: &HashSet<String>) -> Vec<String> {
    let mut v: Vec<String> = set.iter().cloned().collect();
    v.sort();
    v
}
