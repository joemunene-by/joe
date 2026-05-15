//! Git commands. Implemented by shelling out to the `git` binary
//! rather than linking libgit2. Keeps the binary smaller, matches
//! exactly what the user gets at the shell, and lets us inherit
//! their configured credential helper / SSH agent without ceremony.
//!
//! Every command requires `Permissions::repo_allowed(repo_path)`.

use std::path::PathBuf;
use std::process::Command;

use serde::Serialize;
use tauri::State;

use crate::permissions::Permissions;

#[derive(Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum GitError {
    PermissionDenied { subject: String, scope: &'static str },
    NotARepo { path: String },
    GitFailed { command: String, stderr: String, exit_code: i32 },
    SpawnFailed { message: String },
}

#[derive(Serialize)]
pub struct GitStatus {
    pub branch: String,
    pub upstream: Option<String>,
    pub ahead: u32,
    pub behind: u32,
    pub clean: bool,
    pub entries: Vec<GitStatusEntry>,
}

#[derive(Serialize)]
pub struct GitStatusEntry {
    pub path: String,
    /// Two-char status from `git status --porcelain=v1` (e.g. "M ", " M", "??", "A ").
    pub status: String,
}

fn run_git(repo: &PathBuf, args: &[&str]) -> Result<String, GitError> {
    let output = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .output()
        .map_err(|e| GitError::SpawnFailed { message: e.to_string() })?;
    if !output.status.success() {
        return Err(GitError::GitFailed {
            command: format!("git {}", args.join(" ")),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
            exit_code: output.status.code().unwrap_or(-1),
        });
    }
    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

fn check_repo(repo: &str, perms: &State<'_, Permissions>) -> Result<PathBuf, GitError> {
    let p = PathBuf::from(repo);
    if !perms.repo_allowed(&p) {
        return Err(GitError::PermissionDenied {
            subject: repo.to_string(),
            scope: "repo",
        });
    }
    // Quick sanity: does the .git dir exist? Catch typos before they
    // reach git and produce a clearer error for the user.
    if !p.join(".git").exists() && !p.join(".git").is_file() {
        return Err(GitError::NotARepo { path: repo.to_string() });
    }
    Ok(p)
}

#[tauri::command]
pub fn git_status(repo: String, perms: State<'_, Permissions>) -> Result<GitStatus, GitError> {
    let p = check_repo(&repo, &perms)?;
    let porcelain = run_git(&p, &["status", "--porcelain=v1", "-b"])?;
    let mut branch = "HEAD".to_string();
    let mut upstream: Option<String> = None;
    let mut ahead: u32 = 0;
    let mut behind: u32 = 0;
    let mut entries = Vec::new();
    for line in porcelain.lines() {
        if let Some(rest) = line.strip_prefix("## ") {
            // Form: "main...origin/main [ahead 1, behind 3]"
            let segments: Vec<&str> = rest.split(' ').collect();
            if let Some(head) = segments.first() {
                let (b, u) = match head.split_once("...") {
                    Some((b, u)) => (b.to_string(), Some(u.to_string())),
                    None => (head.to_string(), None),
                };
                branch = b;
                upstream = u;
            }
            // Parse trailing "[ahead N, behind M]".
            if let Some(idx) = rest.find('[') {
                let stats = &rest[idx + 1..];
                let stats = stats.trim_end_matches(']');
                for piece in stats.split(',') {
                    let piece = piece.trim();
                    if let Some(n) = piece.strip_prefix("ahead ") {
                        ahead = n.parse().unwrap_or(0);
                    } else if let Some(n) = piece.strip_prefix("behind ") {
                        behind = n.parse().unwrap_or(0);
                    }
                }
            }
        } else if line.len() >= 3 {
            entries.push(GitStatusEntry {
                status: line[..2].to_string(),
                path: line[3..].to_string(),
            });
        }
    }
    let clean = entries.is_empty();
    Ok(GitStatus { branch, upstream, ahead, behind, clean, entries })
}

#[tauri::command]
pub fn git_diff(
    repo: String,
    path: Option<String>,
    staged: bool,
    perms: State<'_, Permissions>,
) -> Result<String, GitError> {
    let p = check_repo(&repo, &perms)?;
    let mut args = vec!["diff"];
    if staged {
        args.push("--staged");
    }
    if let Some(ref pth) = path {
        args.push("--");
        args.push(pth);
    }
    run_git(&p, &args)
}

#[tauri::command]
pub fn git_log(
    repo: String,
    limit: Option<u32>,
    perms: State<'_, Permissions>,
) -> Result<String, GitError> {
    let p = check_repo(&repo, &perms)?;
    let n = limit.unwrap_or(20).to_string();
    run_git(
        &p,
        &[
            "log",
            "--oneline",
            "--decorate",
            "--graph",
            &format!("-n {}", n),
        ],
    )
}

#[tauri::command]
pub fn git_branches(
    repo: String,
    perms: State<'_, Permissions>,
) -> Result<Vec<String>, GitError> {
    let p = check_repo(&repo, &perms)?;
    let out = run_git(&p, &["branch", "--format=%(refname:short)"])?;
    Ok(out.lines().map(|s| s.trim().to_string()).filter(|s| !s.is_empty()).collect())
}

#[tauri::command]
pub fn git_stage(
    repo: String,
    paths: Vec<String>,
    perms: State<'_, Permissions>,
) -> Result<(), GitError> {
    let p = check_repo(&repo, &perms)?;
    let mut args = vec!["add", "--"];
    let paths_refs: Vec<&str> = paths.iter().map(|s| s.as_str()).collect();
    args.extend(paths_refs);
    run_git(&p, &args)?;
    Ok(())
}

#[tauri::command]
pub fn git_unstage(
    repo: String,
    paths: Vec<String>,
    perms: State<'_, Permissions>,
) -> Result<(), GitError> {
    let p = check_repo(&repo, &perms)?;
    let mut args = vec!["restore", "--staged", "--"];
    let paths_refs: Vec<&str> = paths.iter().map(|s| s.as_str()).collect();
    args.extend(paths_refs);
    run_git(&p, &args)?;
    Ok(())
}

#[tauri::command]
pub fn git_commit(
    repo: String,
    message: String,
    perms: State<'_, Permissions>,
) -> Result<String, GitError> {
    let p = check_repo(&repo, &perms)?;
    run_git(&p, &["commit", "-m", &message])
}

#[tauri::command]
pub fn git_push(repo: String, perms: State<'_, Permissions>) -> Result<String, GitError> {
    let p = check_repo(&repo, &perms)?;
    run_git(&p, &["push"])
}

#[tauri::command]
pub fn git_pull(repo: String, perms: State<'_, Permissions>) -> Result<String, GitError> {
    let p = check_repo(&repo, &perms)?;
    run_git(&p, &["pull", "--ff-only"])
}
